#!/usr/bin/env python3
"""Route declared work to a lane that can take it, and remember what it routed.

WHY THIS EXISTS
---------------

Every unit of work this fleet has ever completed was typed in by a person. Not
because a component was broken — each one was correct and tested in isolation:

    select_backlog_item.py   names what may start in the consumer
    kit_issues.py            names what the kit owes
    session_ready.py         says which lane can take something
    dispatch_to_lane.sh      hands one unit to one lane

The segment between them was a human reading one output and composing the next
input. Measured 2026-09-03: three lanes idle for **10h33m** with four actionable
kit issues open. Nothing was broken. The wiring did not exist.

WHAT IT IS NOT
--------------

It is not a decision-maker. It routes units the sources already declared
startable, and it cannot make a held item startable — that is the whole point of
the hold. It never invents work: every unit it hands out is an id you can open.

THE STATE
---------

An append-only log, replayed on every run. The lead kept its state in memory and
lost all of it when the process died; a router that forgets is a router that
double-assigns. Each line is one event, and the current assignment set is the
replay of the log rather than a field anyone maintains.

A line it cannot parse raises rather than being skipped: a log with a hole in it
under-reports what is in flight, and under-reporting in-flight work is exactly
how the same unit reaches two lanes.

Usage:
    fleet_router.py --lanes squad1,squad2,squad3 --kit-repo owner/name
    fleet_router.py --lanes squad1,squad2 --project /path/to/consumer --apply

Exit codes:
    0  ran; the plan is on stdout (assignments empty is a legitimate answer)
    1  a source could not be read — the plan is partial and says so
    2  invocation error
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import kit_issues  # noqa: E402
import session_ready  # noqa: E402


class StateUnreadable(RuntimeError):
    """The assignment log could not be replayed.

    Distinct from "nothing is in flight". Treating a hole in the log as an empty
    set is how one unit reaches two lanes.
    """


@dataclass(frozen=True)
class Unit:
    """One thing a lane may be asked to do. Always an id someone can open."""
    slug: str
    title: str
    source: str          # "kit" · "backlog"

    @property
    def number(self) -> str:
        return self.slug.split("#")[-1]


@dataclass(frozen=True)
class Assignment:
    lane: str
    unit: Unit


@dataclass
class Plan:
    assignments: list[Assignment] = field(default_factory=list)
    unassigned: list[str] = field(default_factory=list)
    idle_reason: str = ""
    notes: list[str] = field(default_factory=list)


# ── the log ───────────────────────────────────────────────────────────────────

#: How long a unit may sit on a free lane with nothing to show before it is
#: called abandoned. Long enough that a lane which simply had not started yet is
#: never reaped; short enough that a dead lane does not hold a unit for a day.
GRACE = 1800.0

#: How long the fleet waits before sweeping itself again. A sweep on every idle
#: pass fills the tracker with the same claims until nobody reads it, and a
#: tracker nobody reads is worse than an empty one.
AUDIT_COOLDOWN = 21600.0

#: The one unit that is not an id somebody filed. It exists so that "nothing is
#: owed" stops meaning "stop", and it is the LAST source for a reason: a fleet
#: that prefers auditing itself to shipping the product is worse than an idle
#: one, because it looks busy.
AUDIT_SLUG = "kit-audit"


def record(log: Path, event: str, **fields: object) -> None:
    """Append one event. The log is the state; nothing else is."""
    log.parent.mkdir(parents=True, exist_ok=True)
    row = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "at_epoch": time.time(), "event": event, **fields}
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def in_flight(log: Path) -> dict[str, str]:
    """`{unit slug: lane}` for everything assigned and not yet released.

    Replayed from the log on every call rather than cached, because the process
    that wrote a line is often not the process that needs to read it.
    """
    if not log.is_file():
        return {}
    held: dict[str, str] = {}
    for number, line in enumerate(log.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise StateUnreadable(
                f"{log}:{number} is not JSON ({exc}). Refusing to report an "
                f"in-flight set from a log with a hole in it — under-reporting "
                f"in-flight work is how one unit reaches two lanes.") from exc
        unit = row.get("unit")
        if not unit:
            continue
        if row.get("event") == "assigned":
            held[unit] = row.get("lane", "")
        elif row.get("event") == "released":
            held.pop(unit, None)
    return held


def reap(log: Path, *, lanes: dict[str, str], branches: set[str],
         now: float | None = None) -> list[str]:
    """Release units nobody is working on any more, and return what was released.

    Three facts must hold together, because each on its own is normal:

    - the lane is **free** — not busy (a lane taking a long time is the commonest
      case, and reaping it hands the same unit to a second writer) and not
      `unknown`, which means the check did not run and is never grounds to act;
    - **no branch exists** — a branch means the lane did the work and stopped,
      which is what a lane is supposed to do; landing it belongs to the lander;
    - the grace period has passed, so a lane that had not started yet is safe.

    Without this the log is correct-looking state over work nobody is doing: the
    router never re-offers the unit and no lane is on it. That is the fleet's
    10h33m idle failure rebuilt one level up.
    """
    now = time.time() if now is None else now
    assigned = _assignment_rows(log)
    released: list[str] = []
    for unit, (lane, when) in assigned.items():
        if lanes.get(lane) != "free":
            continue
        number = unit.split("#")[-1]
        if any(re.match(rf"^fix/kit{re.escape(number)}(?![0-9])", b) for b in branches):
            continue
        if now - when < GRACE:
            continue
        record(log, "released", unit=unit, lane=lane,
               reason=f"{lane} has been free for over {int(GRACE)}s with no branch "
                      f"for {unit}; treating it as abandoned so it can be offered again")
        released.append(unit)
    return released


def _assignment_rows(log: Path) -> dict[str, tuple[str, float]]:
    """`{unit: (lane, assigned_at)}`, replayed like `in_flight` but keeping the
    timestamp the reaper needs."""
    if not log.is_file():
        return {}
    held: dict[str, tuple[str, float]] = {}
    for number, line in enumerate(log.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise StateUnreadable(f"{log}:{number} is not JSON ({exc})") from exc
        unit = row.get("unit")
        if not unit:
            continue
        if row.get("event") == "assigned":
            held[unit] = (row.get("lane", ""), float(row.get("at_epoch") or 0.0))
        elif row.get("event") == "released":
            held.pop(unit, None)
    return held


def audit_unit(log: Path, *, has_work: bool, now: float | None = None) -> "Unit | None":
    """A sweep of the kit, or `None`.

    Offered only when both real sources are empty and the cooldown has passed.
    The kit HAS a way to find work nobody has filed yet — `kit_audit_workflow.js`
    hunts the patterns it has shipped more than once and puts every claim through
    an agent whose only job is to refute it — and until now nothing ever ran it.
    """
    if has_work:
        return None
    now = time.time() if now is None else now
    # `None`, not 0.0: a fleet that has never swept must sweep, and starting the
    # clock at the epoch would make that depend on what today's date happens to be.
    last: float | None = None
    if log.is_file():
        for line in log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("unit") == AUDIT_SLUG and row.get("event") == "assigned":
                seen = float(row.get("at_epoch") or 0.0)
                last = seen if last is None else max(last, seen)
    if last is not None and now - last < AUDIT_COOLDOWN:
        return None
    return Unit(AUDIT_SLUG, "sweep the kit for defects nobody has filed yet", "audit")


# ── the sources ───────────────────────────────────────────────────────────────

def kit_units(repo: str, *, timeout: int = 60) -> tuple[list[Unit], str]:
    """What the kit owes, and a note a person can act on.

    The note never says the kit is clean on the strength of a tool that did not
    run. `kit_issues.Unavailable` carries its own reason and it is passed through
    verbatim.
    """
    try:
        actionable, held = kit_issues.fleet_work(repo, timeout=timeout)
    except kit_issues.Unavailable as exc:
        return [], f"the kit registry could not be read: {exc}"
    units = [Unit(i.slug, i.title, "kit") for i in actionable]
    note = f"the kit registry is readable: {len(units)} actionable"
    if held:
        # Named, not counted. An issue nobody can see is an issue nobody decides.
        note += (f", {len(held)} waiting on a person "
                 f"({', '.join(i.slug for i in held)})")
    return units, note


def backlog_units(project: Path, *, timeout: int = 120) -> tuple[list[Unit], str]:
    """What the consumer's registry says may start. Always outranks kit work.

    A fleet that prefers auditing itself to shipping the product is worse than an
    idle one: it looks busy.
    """
    selector = project / ".claude/skills/backlog-review/scripts/select_backlog_item.py"
    if not selector.is_file():
        return [], f"no selector at {selector}; the consumer's queue was not read"
    try:
        done = subprocess.run(  # noqa: PLW1510 — the exit code is a verdict, read below
            [sys.executable, str(selector), str(project / "BACKLOG.md"), "--json"],
            capture_output=True, text=True, timeout=timeout, cwd=str(project),
            stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as exc:
        return [], f"the consumer's selector could not be run ({exc})"
    # Read stdout BEFORE the returncode. SELECT ends on `0 if ITEM_SELECTED else 1`,
    # so a held backlog always exits non-zero with the verdict on stdout — the
    # exact ordering that made the lead log `SELECT exited 1: ` with a blank reason.
    try:
        answer = json.loads(done.stdout)
    except json.JSONDecodeError:
        detail = (done.stderr or done.stdout or "").strip()[:200]
        return [], f"the consumer's selector returned no usable answer: {detail or 'no output'}"
    queue = [q for q in (answer.get("queue") or []) if q]
    if not queue:
        awaiting = answer.get("awaiting_human") or []
        note = f"{answer.get('verdict', 'no verdict')}: {answer.get('reason', '')}"
        if awaiting:
            note += f" [awaiting a person: {', '.join(awaiting)}]"
        return [], note
    return ([Unit(q, "", "backlog") for q in queue],
            f"the consumer's queue has {len(queue)} startable item(s)")


# ── the lanes ─────────────────────────────────────────────────────────────────

def lane_states(lanes: list[str]) -> dict[str, str]:
    """`free` · `holding` · `busy` · `gone` · `dialog`, per lane.

    `holding` is its own answer and not a flavour of free: a lane sitting on text
    somebody typed and never submitted looks exactly like an idle one, and typing
    into it appends to their line.
    """
    out: dict[str, str] = {}
    for lane in lanes:
        verdict, _evidence = session_ready.state(lane)
        if verdict != "ready":
            out[lane] = verdict
            continue
        screen = session_ready.screen(lane) or ""
        left = session_ready.composer_text(screen)
        if left is None:
            # No readable composer. Not free, and not a measurement either.
            out[lane] = "unreadable"
        else:
            out[lane] = "free" if left == "" else "holding"
    return out


# ── the brief ─────────────────────────────────────────────────────────────────

_AUDIT_BRIEF = """\
# Work unit: a sweep of the kit

Repository: {repo}

Both real queues are empty — the consumer's backlog is walled on decisions only a
person can make, and the kit's tracker has nothing a lane may take. That is not a
reason to stop. It is the moment to look for what nobody has filed yet.

## What to do

1. Run the kit's own audit, which hunts the defect patterns this kit has shipped
   more than once:
   `Workflow` with `mechanisms/fleet/kit_audit_workflow.js` and `args.repo = {repo}`
2. It ends by putting every claim in front of an agent whose only instruction is
   to REFUTE it, defaulting to refuted when it cannot confirm the behaviour
   itself. Write the result to a JSON file.
3. File only what survived that:
   `python3 {repo}/mechanisms/fleet/file_findings.py --repo {tracker} --findings <file> --apply`
   It refuses a killed claim, a claim with no evidence, and one the tracker
   already holds. Read what it skipped — the skips are as much the result as the
   filings.
4. Report the counts: claims hunted, claims refuted, issues filed, duplicates.

## Absolute limits — no exception, ever

- Write NO code. This unit produces issues, not commits. There is no worktree
  because there is nothing to write.
- Do not file a finding the refuter killed, and do not soften a refutation to
  keep a finding alive.
- An empty sweep is a real answer. Report it as one. Padding a sweep to look
  productive is the failure this whole mechanism exists to avoid.
- Everything written into the tracker is in ENGLISH, and carries no secrets.
"""


_CONSUMER_BRIEF = """\
# Work unit: {slug}

Repository: {project}
Read the item first: it is in `{project}/BACKLOG.md`, under the `## {slug}` heading.
Read the WHOLE block — `evidence`, `why_now`, `dod`, and any dated note under it.

This is a CONSUMER project item, not a kit issue. There is no GitHub issue for
it and `gh issue view {slug}` will not resolve — the id lives in the registry
above and nowhere else.

## What to do

The item carries a `suggested_mode` field. Enter the cycle at the point that
mode asks for — the modes do not share an entry point, and the item's own
registry rules say which is which. Read the mode, then run the cycle it names.

Do not substitute a shape the item did not ask for: a backlog item is not a
repair branch, and inventing a worktree-and-test pass for one produces a branch
the cycle never asked for.

## What the DoD means

The item's `dod` block is the contract. A bullet that is already satisfied is
reported as satisfied WITH the measurement that shows it; a bullet that cannot be
satisfied from this session is reported as such, naming what it needs. Neither is
a failure. Silently skipping one is.

## When there is no code-shaped work left

Check this BEFORE planning anything. An item can be legitimately open while none
of its bullets is buildable right now — every bullet terminal (shipped, or
refused with a reason) and the rest deferred behind a measurement nobody has
taken. Say so and stop. Writing a plan whose content is "do nothing until
someone measures" is fabrication, and a plan built on it produces a branch that
implements nothing.

That is a REAL and complete answer. Report which bullets are terminal, which are
deferred and on what, and hand the item back.

## Absolute limits — no exception, ever

- No `--no-verify`, no `--force`, no `--allow-dirty-tree`, no `--skip-checks`.
- Do not move a threshold, a baseline or an allowlist to make anything pass.
- Do not edit `BACKLOG.md` to unblock an item a person must unblock.
- Never add a `Co-Authored-By:` trailer or any second author to a commit.
- Everything written into the repository is in ENGLISH.
- If the only way forward is a bypass, STOP and report instead of deciding alone.
"""


_BRIEF = """\
# Work unit: {slug}

Repository: {repo}
Read the issue first: `gh issue view {number} --repo {tracker}`

## What to do

1. Create your own git worktree so you do not collide with the other lanes:
   `git -C {repo} worktree add -b {branch} "/tmp/squad-repair/{safe}-$(date +%s)" origin/workspace`
   Work ONLY inside that worktree.
2. Write the FAILING TEST FIRST. Show it failing on the current tree, for the
   right reason, before you touch any production code. A test written after the
   code passes on the code you happened to write.
3. Make the change. Prefer closing the mechanism that let the defect return over
   closing the single instance of it.
4. Run the full suite in your worktree. Report the number.
5. Add a CHANGELOG.md entry under [Unreleased] referencing (#{number}).
6. Commit on your branch. Do NOT push.
7. Report both runs: the test failing before, and the suite passing after.

## Absolute limits — no exception, ever

- No `--no-verify`, no `--force`, no `--allow-dirty-tree`, no `--skip-checks`.
- Do not move a threshold, a baseline or an allowlist to make anything pass.
- Do not edit anything outside your worktree.
- Never add a `Co-Authored-By:` trailer or any second author to a commit.
- Everything written into the repository is in ENGLISH.
- If the only way forward is a bypass, STOP and report instead of deciding alone.
"""


def brief(unit: Unit, *, repo: str, tracker: str = "paulohenriquevn/squad",
          project: str = "") -> str:
    """The instruction a lane receives. Written here rather than by hand.

    Hand-written briefs were the other half of the missing wiring, and on
    2026-09-03 one of them sent a lane to the wrong issue because a substitution
    pattern missed `issue view 19`.

    Three sources, three briefs. A consumer item and a kit issue are NOT variants
    of one instruction: they name different repositories, different registries
    and different entry points. Measured 2026-09-04 (kit#27) when they shared
    one — B-165 was dispatched telling the lane to work in the kit and run
    `gh issue view B-165 --repo <kit>`, and neither resolves: the id lives in the
    consumer's BACKLOG.md and the kit's registry is GitHub issues, which cannot
    hold a B-NNN. The lane halted rather than guess, which was correct and cost
    the pass.
    """
    if unit.source == "audit":
        return _AUDIT_BRIEF.format(repo=repo, tracker=tracker)
    if unit.source == "backlog":
        if not project:
            raise ValueError(
                f"{unit.slug} is a consumer backlog item and no project path was "
                f"given. Briefing it against the kit would send the lane to a "
                f"repository the item does not live in (kit#27)")
        return _CONSUMER_BRIEF.format(slug=unit.slug, project=project)
    safe = unit.slug.replace("#", "").replace("/", "-")
    return _BRIEF.format(slug=unit.slug, repo=repo, number=unit.number,
                         tracker=tracker, branch=f"fix/{safe}", safe=safe)


# ── the plan ──────────────────────────────────────────────────────────────────

def open_branches(repo: Path, *, timeout: int = 30) -> set[str] | None:
    """Every branch name in `repo`, local and remote, or `None` when git could not
    be asked. `None` is not `set()` — see `plan`."""
    try:
        done = subprocess.run(  # noqa: PLW1510
            ["git", "-C", str(repo), "branch", "-a", "--format=%(refname:short)"],
            capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return {ln.strip().removeprefix("origin/") for ln in done.stdout.splitlines() if ln.strip()}


def closed_in_history(repo: Path, *, ref: str = "origin/workspace",
                      timeout: int = 30) -> set[str]:
    """Issue numbers a commit reachable from `ref` already claims to close.

    The branch guard cannot see work done straight on the working branch, which is
    how kit#22 and kit#25 were offered back after being fixed. An empty set here is
    safe in a way an empty branch set is not: it can only cause a unit to be
    offered, and the tracker remains the authority on whether it is still open.
    """
    try:
        done = subprocess.run(  # noqa: PLW1510
            ["git", "-C", str(repo), "log", "--format=%B", "-n", "400", ref],
            capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return set()
    if done.returncode != 0:
        return set()
    return set(re.findall(r"(?i)\bcloses?\b[^\n#]{0,20}#(\d+)", done.stdout))


def plan(*, units: list[Unit], lanes: dict[str, str], log: Path,
         branches: set[str] | None, closed: set[str] | None = None) -> Plan:
    """Who gets what. Pure: it decides, and writes nothing.

    `branches` is the second evidence of work in flight, and it is not optional.
    The log knows only what THIS mechanism did; a branch is an observable fact
    that survives a person dispatching by hand and survives the router dying
    between handing a unit over and recording it — the exact window where memory
    alone loses a unit and offers it to a second lane.

    `None` means git could not be asked, and it raises. Reading "no branches
    exist" off a failed call would re-offer everything already being worked on,
    which is this kit's most-found defect with the highest possible blast radius.
    """
    if branches is None:
        raise StateUnreadable(
            "the repository's branches could not be listed, so whether a unit is "
            "already being worked on is unknown. Refusing to plan: treating that "
            "as 'nothing is in flight' hands work already under way to a second lane.")
    result = Plan()
    held = in_flight(log)
    free = [name for name, verdict in sorted(lanes.items()) if verdict == "free"]
    if not free:
        result.idle_reason = "; ".join(f"{n}: {v}" for n, v in sorted(lanes.items()))

    def branched(unit: Unit) -> str | None:
        # Anchored on the digits so `fix/kit2-...` cannot hold kit#21. A prefix
        # match would starve the queue quietly and read as an empty backlog.
        pattern = re.compile(rf"^fix/kit{re.escape(unit.number)}(?![0-9])")
        return next((b for b in sorted(branches) if pattern.match(b)), None)

    startable = []
    for unit in units:
        if unit.slug in held:
            result.notes.append(f"{unit.slug} is already with {held[unit.slug]}")
            continue
        branch = branched(unit)
        if branch:
            result.notes.append(f"{unit.slug} already has a branch ({branch})")
            continue
        if unit.number in (closed or set()):
            result.notes.append(f"{unit.slug} is already closed by a commit in history")
            continue
        startable.append(unit)

    for lane, unit in zip(free, startable, strict=False):
        result.assignments.append(Assignment(lane, unit))
    result.unassigned = [u.slug for u in startable[len(result.assignments):]]
    return result


def resolve_unit_payload(unit: Unit, *, repo: str, tracker: str) -> dict:
    """Fetch full unit metadata and return structured payload for workflow.

    Fetches issue body via gh CLI and returns a dict suitable for passing
    to fleet_dispatch_workflow.js as args.

    Returns:
        Dict with keys: repo, tracker, unit{slug, number, title, body, branch},
        worktreeRoot
    """
    # Extract branch name from slug (fix/kit<number>[-suffix])
    safe = unit.slug.replace("#", "").replace("/", "-")
    branch = f"fix/{safe}"

    # If the unit has a body already (from kit_issues), use it.
    # Otherwise, fetch via gh issue view
    body = ""
    if tracker == "github":
        try:
            # Try to fetch issue body from GitHub
            result = subprocess.run(
                ["gh", "issue", "view", unit.number, "--json", "body", "-q", ".body"],
                capture_output=True, text=True, check=False
            )
            if result.returncode == 0:
                body = result.stdout.strip()
        except Exception:
            body = unit.title  # Fallback to title if fetch fails

    return {
        "repo": repo,
        "tracker": tracker,
        "unit": {
            "slug": unit.slug,
            "number": int(unit.number),
            "title": unit.title,
            "body": body or unit.title,
            "branch": branch,
        },
        "worktreeRoot": "/tmp/squad-dispatch",
    }


def dispatch(assignment: Assignment, *, repo: str, log: Path,
             tracker: str, apply: bool, mode: str = "tmux",
             project: str = "") -> tuple[bool, str]:
    """Hand one unit over, and record it only once the keystroke landed.

    Recording on the decision rather than on delivery would reserve a unit for a
    lane that never received it — and the log is what stops a re-run from
    assigning it elsewhere.

    Args:
        assignment: (lane, unit) pair
        repo: Repository path
        log: Assignment log path
        tracker: Tracker type (github, jira, etc.)
        apply: Whether to actually dispatch (else dry-run)
        mode: "tmux" (default, backward compatible) or "workflow" (new structured dispatch)
    """
    if mode == "workflow":
        # New workflow mode: write structured JSON payload
        payload = resolve_unit_payload(assignment.unit, repo=repo, tracker=tracker)
        drop = Path("/tmp/squad-router") / f"{assignment.unit.slug.replace('#', '')}.json"
        if not apply:
            return True, f"dry-run: would dispatch {assignment.unit.slug} to {assignment.lane} (workflow mode)"
        drop.parent.mkdir(parents=True, exist_ok=True)
        drop.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        workflow_prompt = (
            f"Read {drop} and invoke the fleet_dispatch_workflow with this payload. "
            f"The JSON contains all metadata needed: repo, tracker, unit(slug, number, title, body, branch), worktreeRoot."
        )
    else:
        # Traditional tmux mode: write markdown brief
        text = brief(assignment.unit, repo=repo, tracker=tracker, project=project)
        drop = Path("/tmp/squad-router") / f"{assignment.unit.slug.replace('#', '')}.md"
        if not apply:
            return True, f"dry-run: would dispatch {assignment.unit.slug} to {assignment.lane}"
        drop.parent.mkdir(parents=True, exist_ok=True)
        drop.write_text(text, encoding="utf-8")
        workflow_prompt = (
            f"Read {drop} and do exactly what it says. "
            f"Follow every limit in it without exception."
        )

    done = subprocess.run(  # noqa: PLW1510 — every exit code below is meaningful
        ["bash", str(_HERE / "dispatch_to_lane.sh"), "--lane", assignment.lane,
         "--prompt", workflow_prompt],
        capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if done.returncode != 0:
        # Not recorded. An unrecorded unit is offered again next run, which is the
        # right failure: the alternative is a unit nobody holds and nobody retries.
        return False, (f"{assignment.unit.slug} was NOT delivered to "
                       f"{assignment.lane} (exit {done.returncode}): "
                       f"{(done.stderr or done.stdout).strip()[:160]}")
    record(log, "assigned", unit=assignment.unit.slug, lane=assignment.lane,
           source=assignment.unit.source, brief=str(drop), mode=mode)
    return True, f"{assignment.unit.slug} -> {assignment.lane} (mode={mode})"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lanes", required=True, help="comma-separated tmux session names")
    ap.add_argument("--kit-repo", default="", help="owner/name of the kit's tracker")
    ap.add_argument("--kit-path", default=str(_HERE.parents[1]),
                    help="working copy the lanes clone worktrees from")
    ap.add_argument("--project", default="", help="consumer whose backlog outranks kit work")
    ap.add_argument("--log", default=str(Path.home() / ".squad-fleet" / "assignments.jsonl"))
    ap.add_argument("--apply", action="store_true",
                    help="actually dispatch; without it nothing is typed anywhere")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    lanes = [name.strip() for name in args.lanes.split(",") if name.strip()]
    if not lanes:
        print("no lanes given", file=sys.stderr)
        return 2
    log = Path(args.log)

    notes: list[str] = []
    units: list[Unit] = []
    partial = False

    # The consumer's backlog always wins. Kit work is where the fleet goes when the
    # alternative is idling, never a shortcut around the product.
    if args.project:
        found, note = backlog_units(Path(args.project))
        notes.append(f"backlog: {note}")
        units.extend(found)
    if args.kit_repo and not units:
        found, note = kit_units(args.kit_repo)
        notes.append(f"kit: {note}")
        if "could not be read" in note:
            partial = True
        units.extend(found)

    # Last, and only when both real sources came back empty. `units` being empty
    # is the condition, not "the sources failed" — a source that could not be read
    # already said so in its own note above, and sweeping on the strength of a
    # failed read would be inventing work out of an absent measurement.
    audit = audit_unit(log, has_work=bool(units))
    if audit is not None:
        units.append(audit)
        notes.append("both queues are empty; offering a sweep of the kit instead of idling")

    try:
        states = lane_states(lanes)
        branches = open_branches(Path(args.kit_path))
        if branches is None:
            raise StateUnreadable(
                "the repository's branches could not be listed, so whether a unit "
                "is already being worked on is unknown. Refusing to plan.")
        # Reaped BEFORE planning: a unit released now is offered in the same run,
        # which is the difference between recovering and merely noticing.
        for freed in reap(log, lanes=states, branches=branches):
            notes.append(f"released {freed}: its lane is free with nothing to show")
        the_plan = plan(units=units, lanes=states, log=log, branches=branches,
                        closed=closed_in_history(Path(args.kit_path)))
    except StateUnreadable as exc:
        print(str(exc), file=sys.stderr)
        return 1

    delivered: list[str] = []
    for assignment in the_plan.assignments:
        ok, line = dispatch(assignment, repo=args.kit_path, log=log,
                            tracker=args.kit_repo or "paulohenriquevn/squad",
                            apply=args.apply, project=args.project)
        (delivered if ok else notes).append(line)

    report = {
        "lanes": states,
        "units": [u.slug for u in units],
        "delivered": delivered,
        "unassigned": the_plan.unassigned,
        "idle_reason": the_plan.idle_reason,
        "notes": notes + the_plan.notes,
        "applied": args.apply,
    }
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"lanes    : {', '.join(f'{k}={v}' for k, v in sorted(states.items()))}")
        print(f"units    : {len(units)}")
        for line in delivered:
            print(f"  -> {line}")
        if the_plan.unassigned:
            print(f"unassigned: {', '.join(the_plan.unassigned)} (no free lane)")
        if the_plan.idle_reason:
            print(f"no free lane: {the_plan.idle_reason}")
        for note in notes + the_plan.notes:
            print(f"note     : {note}")
    return 1 if partial else 0


if __name__ == "__main__":
    raise SystemExit(main())
