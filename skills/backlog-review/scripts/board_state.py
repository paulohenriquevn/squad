#!/usr/bin/env python3
"""The whole picture, as one JSON document: every item, where it is, what holds it.

Two sources, and they answer different questions:

  BACKLOG.md              WHERE each item stands right now — the state that survives
                          the session, and the only one that exists for work done
                          before the cycle was instrumented.
  cycle-events.jsonl      WHAT HAPPENED and when — the phase transitions, with the
                          verdict each one reached.

The second is the richer one and the one that is usually empty. It is per-machine and
per-session by decision (`.gitignore` carries the reason: one machine's run history
does not belong in everyone's diff), and it starts empty in every clone. So the board
must be legible from the registry ALONE, and treat the stream as detail it may or may
not have — a board that needs the stream shows an empty screen in the exact situation
someone first opens it.

Position is therefore derived twice, in order of confidence:

  1. the last phase the stream says finished, when there is a stream
  2. otherwise the phase implied by `status`, which is all the registry can say

`stream` vs `derived` is reported per item, because a board that presents an inference
and a measurement in the same typeface is doing the thing this ecosystem caps plans
at 49 for.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_backlog_structure import (  # noqa: E402
    OPEN_STATUS,
    _parse_items,
    declares_impediment,
    parse_blocked_by,
)

#: The board's columns, in cycle order. `killed` is a lane rather than a column: it is
#: a terminal OUTCOME, and the contract is explicit that it is a successful one, so
#: burying it after `release` would put a success at the end of a pipeline it left
#: early.
PHASES = ("backlog", "discover", "plan", "implement", "code-quality", "review",
          "release", "acceptance")

#: What a registry status implies about position when no stream exists: the last
#: phase the status proves ENDED. Not the next one — entering a phase is a guess.
#:
#: `shipped` and `killed` are the exception, and deliberately so. They are not
#: positions in the cycle, they are OUTCOMES: the work left. Drawing `shipped` in
#: `release` put 133 of 170 items in one column and left `done` — a column the board
#: has always rendered — permanently empty. The operator could not read the board,
#: and the reason was that the column meaning "finished" was never given anyone.
STATUS_PHASE = {
    "raw": "backlog",
    "triaged": "discover",
    "planned": "plan",
    "shipped": "done",
    "killed": "killed",
}


#: An item id anywhere in a slug, with or without the hyphen.
_SLUG_ITEM_RE = re.compile(r"\bb-?(\d{3,})\b", re.IGNORECASE)


def item_id_of(slug: str) -> str:
    """The `B-NNN` a stream slug refers to, normalised.

    Two conventions reach the stream and both are correct in their own phase. The
    phases instrumented for the maintenance chain emit the ITEM id — `B-033` — because
    that is what the registry keys on. The phases that were already emitting
    (`implement`, `code-quality`, `review`) emit the PLAN slug — `b033-prometheus-url-
    dev-public` — because that is what names the artefact they produced.

    Matching on the raw string loses the second kind entirely. Measured on the first
    real run: 12 events, 6 of them plan slugs, and every one of those six invisible on
    the board — half the execution, missing from the view built to show it.
    """
    match = _SLUG_ITEM_RE.search(slug or "")
    return f"B-{match.group(1)}" if match else (slug or "").upper()


def _events_path(project_root: Path) -> Path | None:
    for rel in (".claude/records/cycle-events.jsonl", "records/cycle-events.jsonl"):
        candidate = project_root / rel
        if candidate.is_file():
            return candidate
    return None


def read_events(project_root: Path) -> list[dict]:
    path = _events_path(project_root)
    if path is None:
        return []
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            # A truncated last line is normal in an append-only file being written
            # right now. Dropping it beats refusing to render the board.
            continue
    return events


#: Mirrors `squad_lead.py`'s own `--stalled` default. Below this the session has moved
#: recently enough that the lead would not call it stalled, so any stall in the log is
#: one it already recovered from.
_STALL_HORIZON_SECONDS = 900



#: Where each phase leaves its work. Globbed by the item's slug rather than named
#: exactly, because a slug is `b033-prometheus-url-dev-public` while the id is `B-033`
#: and several artefacts carry a date as well.
_ARTEFACT_DIRS = (
    ("discover", "discoveries/opportunities"),
    ("discover", "discoveries/plans"),
    ("plan", "plans"),
    ("plan", "alignment"),
    ("implement", "implementations"),
    ("code-quality", "audits"),
    ("review", "reviews"),
    ("release", "releases"),
)

#: Where the shared list lives. The board used to keep its own copy, and the copies
#: disagreed: the drift checker called `implement FAIL` a verdict that forbids
#: advancing while this panel said "no gate is holding this item" about the same
#: event. One repository must not give two answers about one item.
_VERDICTS_RULE = "blocking-verdicts.txt"


def blocking_verdicts(project_root: Path) -> frozenset[str]:
    """Read `rules/blocking-verdicts.txt`.

    An absent file returns nothing and the panel says so, rather than claiming the
    item is unheld: the board reports what it can read, and a missing rule file is
    something it could not read — not evidence that no gate is closed.
    """
    for relative in ("rules", ".claude/rules"):
        candidate = project_root / relative / _VERDICTS_RULE
        if candidate.is_file():
            verdicts = {
                line.split("#", 1)[0].strip().upper()
                for line in candidate.read_text(encoding="utf-8",
                                                errors="replace").splitlines()
            }
            verdicts.discard("")
            return frozenset(verdicts)
    return frozenset()


#: The progress file is named `.progress-<slug>.json`, so the slug is not simply the
#: stem: stripping only the suffix leaves `progress-b033-…`, which matches no plan and
#: no artefact. Latent in `_slug_for` too — it happened to look in `plans` first.
_PROGRESS_PREFIX = "progress-"


#: Directory a phase writes into -> the phase's name on the board.
_PHASE_OF_DIR = {"implementations": "implement", "reviews": "review",
                 "releases": "release"}


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat(timespec="seconds")


def _slug_from_filename(name: str, suffix: str) -> str:
    slug = name.lstrip(".")[: -len(suffix)]
    return slug[len(_PROGRESS_PREFIX):] if slug.startswith(_PROGRESS_PREFIX) else slug


def _slug_for(item_id: str, records: Path) -> str | None:
    """The plan slug an item goes by on disk, e.g. `b033-prometheus-url-dev-public`.

    Derived from what exists rather than constructed, because only the phase that
    wrote the artefact knows the words after the number.
    """
    number = item_id.replace("-", "").lower()          # B-033 -> b033
    for base in ("plans", "implementations", "alignment"):
        directory = records / base
        if not directory.is_dir():
            continue
        for entry in sorted(directory.glob(f"*{number}*")):
            name = entry.name.lstrip(".")
            for suffix in ("-plan.md", "-implementation.md", "-alignment.md", ".json"):
                if name.endswith(suffix):
                    return _slug_from_filename(entry.name, suffix)
    return None


#: Task statuses that mean the work is finished. `committed` is what this cycle
#: writes; anything else counts as outstanding rather than being guessed at.
_DONE_TASK_STATUS = frozenset({"committed", "done", "completed", "merged"})


def _records_dir(project_root: Path) -> Path | None:
    for rel in (".claude/records", "records"):
        candidate = project_root / rel
        if candidate.is_dir():
            return candidate
    return None


def halted_items(project_root: Path) -> set[str]:
    """Items a phase stopped on and wrote a BLOCKED report for.

    Separate from the registry's `blocked_by`, and deliberately so: that field is a
    person declaring an impediment, this is a phase declaring it stopped. Both hold
    the item; different things must be done about them, so the board counts them
    apart rather than folding one into the other.

    The scan itself lives in `scripts/squad_boss.py`, which is the single reader of
    these files. Two scans of one directory drift the way two copies of a
    blocking-verdict list already did in this repository.
    """
    try:
        from squad_boss import halt_reports
    except ImportError:
        return set()
    return set(halt_reports(project_root))


def planned_items(project_root: Path) -> dict[str, str]:
    """Item id -> plan slug, for every item the cycle has actually planned on disk.

    One directory listing for the whole registry. The alternative — asking
    `item_detail` per item — reads every plan and progress file to answer a yes/no
    question, and this registry holds 170 of them.
    """
    records = _records_dir(project_root)
    if records is None:
        return {}
    found: dict[str, str] = {}
    for base, suffix in (("plans", "-plan.md"), ("implementations", ".json")):
        directory = records / base
        if not directory.is_dir():
            continue
        for entry in sorted(directory.iterdir()):
            name = entry.name.lstrip(".")
            if not entry.is_file() or not name.endswith(suffix):
                continue
            slug = _slug_from_filename(entry.name, suffix)
            item = item_id_of(slug)
            # `item_id_of` upper-cases whatever it cannot parse, so a file with no
            # item number in its name would land here under its own name.
            if item.startswith("B-"):
                found.setdefault(item, slug)
    return found


def _item_block(project_root: Path, item_id: str) -> str | None:
    """The registry block for one item, or None."""
    backlog = project_root / "BACKLOG.md"
    if not backlog.is_file():
        return None
    body = backlog.read_text(encoding="utf-8-sig", errors="replace")
    match = re.search(rf"^## {re.escape(item_id)} — .*?(?=^## B-|\Z)", body,
                      re.MULTILINE | re.DOTALL)
    return match.group(0) if match else None


def item_detail(project_root: Path, item_id: str) -> dict:
    """Everything the cycle left behind for one item.

    Loaded on demand rather than folded into the board: one registry here carries 167
    items, and reading every plan and every progress file to render a column of cards
    would spend the whole page budget on work nobody asked to see.
    """
    records = _records_dir(project_root)
    out: dict = {"id": item_id, "slug": None, "phases": [], "tasks": [],
                 "artefacts": [], "verdicts": [], "blocking": [],
                 "done_ratio": None, "specialist": None, "domain": None,
                 "halted": None, "attest": None}
    if records is None:
        return out

    slug = _slug_for(item_id, records)
    out["slug"] = slug

    # ── the plan's own phases, and the tasks under them ────────────────────
    if slug:
        plan = records / "plans" / f"{slug}-plan.md"
        if plan.is_file():
            body = plan.read_text(encoding="utf-8", errors="replace")
            out["phases"] = [
                {"key": m.group(1).strip(), "title": m.group(2).strip()}
                for m in re.finditer(r"^##+\s*(?:Phase|Fase)\s*([0-9]+)\s*[:—-]\s*(.+?)\s*$",
                                     body, re.MULTILINE)
            ]

        progress = records / "implementations" / f".progress-{slug}.json"
        if progress.is_file():
            try:
                data = json.loads(progress.read_text(encoding="utf-8", errors="replace"))
                for task in data.get("tasks", []):
                    out["tasks"].append({
                        "id": task.get("id"),
                        "phase": str(task.get("phase", "")),
                        "status": task.get("status", "unknown"),
                        "files": task.get("files") or [],
                        "iterations": task.get("iterations_used"),
                        "commit": task.get("commit_sha"),
                    })
            except (json.JSONDecodeError, OSError):
                pass

        # ── what each phase left on disk ──────────────────────────────────
        seen: set[str] = set()
        for phase, base in _ARTEFACT_DIRS:
            directory = records / base
            if not directory.is_dir():
                continue
            for entry in sorted(directory.glob(f"*{slug}*")):
                if not entry.is_file() or entry.name.startswith("."):
                    continue
                rel = str(entry.relative_to(records.parent))
                if rel in seen:
                    continue
                seen.add(rel)
                out["artefacts"].append({
                    "phase": phase, "path": rel, "name": entry.name,
                    "bytes": entry.stat().st_size,
                })

    # ── a phase that halted and wrote down why ────────────────────────────
    # `/implement` writes `{slug}-BLOCKED.md` when it stops and needs a person. That
    # file is the phase's own statement of what holds the item — stronger evidence
    # than a verdict token, and the only one that says WHY.
    #
    # Measured on 2026-08-31: B-033 had such a report, naming three pre-existing test
    # failures it cannot fix and three paths for a sponsor to choose between. The
    # board listed the file among seven artefacts and said nothing. The item sat for
    # 85 minutes waiting for a person while the page showed a verdict token.
    if slug:
        for base in ("implementations", "reviews", "releases"):
            report = records / base / f"{slug}-BLOCKED.md"
            if report.is_file():
                first = ""
                for line in report.read_text(encoding="utf-8", errors="replace").splitlines():
                    stripped = line.strip()
                    # The report's own one-line reason, not a summary invented here.
                    if stripped.startswith("**Emitted by:**"):
                        first = stripped[len("**Emitted by:**"):].strip()
                        break
                out["halted"] = {
                    "phase": _PHASE_OF_DIR.get(base, base),
                    "path": str(report.relative_to(records.parent)),
                    "reason": first,
                    "at": _iso(report.stat().st_mtime),
                }
                break

    # ── was the plan changed after it was attested? ───────────────────────
    # The implementation record states the sha it was built against. If the plan on
    # disk hashes to something else, the work was done against a plan that has since
    # moved — which is exactly what attesting exists to catch, and nothing was
    # catching it. B-033: attested 4c7ae5d5…, plan now 88e243ab….
    if slug:
        impl = records / "implementations" / f"{slug}-implementation.md"
        plan_file = records / "plans" / f"{slug}-plan.md"
        if impl.is_file() and plan_file.is_file():
            match = re.search(r"\*\*Attest sha:\*\*\s*`?([0-9a-f]{16,})`?",
                              impl.read_text(encoding="utf-8", errors="replace"))
            if match:
                current = hashlib.sha256(plan_file.read_bytes()).hexdigest()
                out["attest"] = {
                    "attested": match.group(1),
                    "current": current,
                    "drifted": match.group(1) != current,
                }

    # ── how much of the plan is finished ──────────────────────────────────
    # Counted from task status, which is the only place that knows. `committed` is the
    # terminal one this repository writes; the others are treated as not-done rather
    # than guessed at, because a status nobody has seen must not round up.
    if out["tasks"]:
        done = sum(1 for t in out["tasks"] if t["status"] in _DONE_TASK_STATUS)
        out["done_ratio"] = round(done / len(out["tasks"]), 3)

    # ── who owns this work ────────────────────────────────────────────────
    # The item's `domain` routes to a specialist, and that file is the closest thing
    # to a name. It is the ASSIGNED specialist, not proof of who ran the last command:
    # nothing in the stream carries an author, and inventing one from the session that
    # happens to be open would be a guess dressed as a record.
    block = _item_block(project_root, item_id)
    if block:
        match = re.search(r"^domain:\s*(\S+)\s*$", block, re.MULTILINE)
        if match:
            out["domain"] = match.group(1)
            for base in (".claude/agents", "agents"):
                candidate = project_root / base / f"{match.group(1)}.md"
                if candidate.is_file():
                    out["specialist"] = f"{base}/{match.group(1)}.md"
                    break

    # ── every verdict, not only the last ──────────────────────────────────
    # The board's card shows one. This item ended `code-quality` ten times, and a
    # single FAIL_SOFT hides that it was iterating rather than advancing.
    blocking = blocking_verdicts(project_root)
    for event in read_events(project_root):
        if event.get("type") != "cycle:phase:end":
            continue
        if item_id_of(event.get("slug") or "") != item_id:
            continue
        verdict = event.get("verdict")
        out["verdicts"].append({
            "phase": event.get("cycle"), "verdict": verdict, "at": event.get("timestamp"),
        })
        if verdict and verdict.upper() in blocking:
            out["blocking"].append({"phase": event.get("cycle"), "verdict": verdict,
                                    "at": event.get("timestamp")})

    # Only the LAST blocking verdict per phase still applies: an earlier INVALID that a
    # later run cleared is history, and listing it would report a gate that is open.
    latest: dict[str, dict] = {}
    for entry in out["blocking"]:
        latest[entry["phase"]] = entry
    still_blocking = []
    for phase, entry in latest.items():
        last_for_phase = [v for v in out["verdicts"] if v["phase"] == phase]
        last = last_for_phase[-1]["verdict"] if last_for_phase else None
        if last and last.upper() in blocking:
            still_blocking.append(entry)
    out["blocking"] = still_blocking
    return out


def read_lead(log_path: Path | None, marker_path: Path | None) -> dict:
    """What the supervisor decided, and whether the executing session is moving.

    This exists because of a question that had no answer on the board: the session had
    handed its turn back and sat still for two hours, and the only way to find out was
    to attach to a tmux pane and read it. A board that shows every item and not whether
    anything is working shows the shape of the work and not its state.

    Both sources are optional. A board with no supervisor is the normal case — the
    fields come back empty rather than absent, so the page renders one way.
    """
    out: dict = {"decisions": [], "idle_seconds": None, "watching": False}

    if marker_path is not None and marker_path.exists():
        out["watching"] = True
        try:
            out["idle_seconds"] = max(0, int(time.time() - marker_path.stat().st_mtime))
        except OSError:
            pass

    if log_path is None or not log_path.is_file():
        return out
    entries = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    decisions = list(reversed(entries))

    # A stall the session already recovered from is history, not news. It stays in the
    # log — that file is the audit trail and nothing is removed from it — but the board
    # answers "what is true now", and a resolved stall shown beside a live decision
    # says the opposite of the truth.
    #
    # Recovered is measured, not guessed: the session's own marker moved recently
    # enough that the lead would no longer call it stalled. When the idle time is
    # unknown, the stall is kept — dropping it would be asserting a recovery nobody
    # observed.
    idle = out["idle_seconds"]
    if idle is not None and idle < _STALL_HORIZON_SECONDS:
        decisions = [d for d in decisions if d.get("event") != "stalled"]

    # Newest first: the question is always "what just happened", never "what happened
    # first". Capped because a long-running lead's log outgrows a page.
    out["decisions"] = decisions[:12]
    return out


def build_state(project_root: Path, lead_log: Path | None = None,
                lead_marker: Path | None = None) -> dict:
    backlog = project_root / "BACKLOG.md"
    if not backlog.is_file():
        return {"error": f"no BACKLOG.md under {project_root}", "items": [],
                "phases": list(PHASES), "lead": read_lead(lead_log, lead_marker)}

    items = _parse_items(backlog.read_text(encoding="utf-8-sig"))
    statuses = {i.item_id: i.fields.get("status", "") for i in items}
    events = read_events(project_root)
    plans = planned_items(project_root)
    halted = halted_items(project_root)

    # A phase that STARTED and has not ended is work happening right now. Without it
    # the board can only draw what finished, which is a picture of the past: an item
    # under active work showed the verdict of a phase that was already over, and
    # nothing on the page said anything was running.
    running: dict[str, dict] = {}
    for event in events:
        slug = item_id_of(event.get("slug") or "")
        cycle = event.get("cycle") or ""
        if not slug or cycle not in PHASES:
            continue
        if event.get("type") == "cycle:phase:start":
            running[slug] = {"phase": cycle, "since": event.get("timestamp")}
        elif event.get("type") == "cycle:phase:end" and running.get(slug, {}).get("phase") == cycle:
            running.pop(slug, None)

    # Last finished phase per item, from the stream.
    reached: dict[str, dict] = {}
    for event in events:
        slug = item_id_of(event.get("slug") or "")
        cycle = event.get("cycle") or ""
        if not slug or cycle not in PHASES or event.get("type") != "cycle:phase:end":
            continue
        if cycle in PHASES:
            # The LAST phase observed, not the furthest one. "Furthest wins" assumes the
            # cycle only moves forward, and it does not: a plan that review rejects goes
            # back, and an implementation that fails its own gate is worked again.
            #
            # Measured on 2026-08-31: an item's last event was `implement FAIL` at
            # 16:36:01 and the board showed `code-quality`, because code-quality sits
            # later in the sequence. The operator asked whether that was right. It was
            # not — the item had gone back, and hiding that is the same defect as
            # predicting the next phase, one step removed.
            #
            # The stream is append-only, so file order is chronological.
            reached[slug] = {"phase": cycle, "verdict": event.get("verdict"),
                             "at": event.get("timestamp")}

    out_items = []
    for item in items:
        iid = item.item_id
        status = item.fields.get("status", "")
        raw_block = item.fields.get("blocked_by", "")
        blockers = parse_blocked_by(raw_block)
        live = [b for b in blockers if statuses.get(b, "") in OPEN_STATUS]
        # `bool(...)`, because `and` yields its last truthy operand: without it the
        # field carried the blocker LIST where the contract says boolean. The page
        # happened to work — a non-empty array is truthy in JS — which is the kind of
        # accident that survives until someone reads the JSON and believes the type.
        impeded = bool(status in OPEN_STATUS and declares_impediment(raw_block)
                       and (live or not blockers))

        # NOT `live`: that name already holds this item's live blockers a few lines up,
        # and shadowing it silently emptied every `blockers` list on the board.
        in_flight = running.get(iid)
        hit = reached.get(iid)
        if in_flight:
            # Observed: a phase started and has not ended.
            phase, source = in_flight["phase"], "running"
        elif hit:
            # Observed: a phase ENDED. The item is drawn there, not in the one after.
            #
            # It used to advance to the next phase, and that was a prediction dressed as
            # a fact. Measured on 2026-08-31: an item had sixteen events, all `end`, with
            # `code-quality` appearing TEN times — it was iterating against that gate,
            # not moving past it. The board put it in `review`, which it had never
            # entered, and the operator read the column as where the work was.
            #
            # Ending a phase is a fact; entering the next one is a guess, and a board
            # that guesses is a board nobody can check against reality.
            phase, source = hit["phase"], "stream"
        else:
            phase = STATUS_PHASE.get(status, "backlog")
            source = "derived"

        out_items.append({
            "id": iid,
            # The phase being worked on NOW, if any.
            "running_phase": (in_flight or {}).get("phase"),
            "running_since": (in_flight or {}).get("since"),
            "title": item.title,
            "status": status,
            "phase": phase,
            "position_from": source,
            "blocked": impeded,
            "blockers": live,
            "blocked_note": raw_block.strip() if impeded and not live else "",
            "domain": item.fields.get("domain", ""),
            "repo": item.fields.get("repo", ""),
            "evidence": item.fields.get("evidence", ""),
            "last_verdict": (hit or {}).get("verdict"),
            "last_at": (hit or {}).get("at"),
            # Present only when a plan for this item exists on disk. It is what makes
            # the implementation view a measurement: an item with no plan has no
            # steps to show, and inventing a placeholder would be a drawing of a
            # process rather than a report of one.
            "plan_slug": plans.get(iid),
            # A phase stopped here and said so in writing.
            "halted": iid in halted,
        })

    # ── what the stream carries and this board cannot place ──────────────
    # Measured on 2026-08-31 against theo: 3 of 28 events had `slug: null` and two
    # more named cycles outside the declared chain. All five were dropped in silence.
    # A board that discards an eighth of its evidence without saying so is reporting
    # a stream it did not read — the same defect as predicting a phase, one step
    # earlier in the pipeline.
    unplaced_no_item = 0
    unplaced_off_chain: dict[str, int] = {}
    # Starts count too. A phase that BEGAN and cannot be placed is work the board
    # shows nobody doing — `idea-to-release` opened on this stream and no card moved.
    for event in events:
        if event.get("type") not in ("cycle:phase:start", "cycle:phase:end"):
            continue
        slug = item_id_of(event.get("slug") or "")
        cycle = event.get("cycle") or ""
        if not slug or not slug.startswith("B-"):
            unplaced_no_item += 1
        elif cycle not in PHASES:
            unplaced_off_chain[cycle] = unplaced_off_chain.get(cycle, 0) + 1

    out_items.sort(key=lambda d: _number(d["id"]))
    return {
        "project": project_root.name,
        "project_path": str(project_root),
        "phases": list(PHASES),
        "items": out_items,
        "events": events[-200:],
        "event_total": len(events),
        "lead": read_lead(lead_log, lead_marker),
        "running": sorted(running.keys()),
        "has_stream": _events_path(project_root) is not None,
        "unplaced": {
            "without_item": unplaced_no_item,
            "off_chain": dict(sorted(unplaced_off_chain.items())),
        },
    }


def _number(item_id: str) -> int:
    match = re.search(r"(\d+)", item_id)
    return int(match.group(1)) if match else 1 << 30


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    print(json.dumps(build_state(root), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
