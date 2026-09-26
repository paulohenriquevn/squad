#!/usr/bin/env python3
"""Schedule many backlog items through the cycle, one stage each, concurrently.

WHAT IT IS AND WHAT IT IS NOT
-----------------------------
`skills/_kit-rules/parallelism-shapes.md` names two shapes. This kit had FAN-OUT — N agents
on the same work from different angles — and no PIPELINE: N items at different
stages at once. `cycle-idea-to-release` chains its seven phases for one item at a
time, so with 22 triaged items in one consumer, every phase sits idle whenever it
is not the current one.

This decides WHICH item may enter WHICH stage and WHEN. It never decides whether
a stage PASSED — the phases keep their own gates, verdicts and thresholds, and a
scheduler that could overrule one would be a way around it rather than a way
through.

ALIGNED AT 91%, AFTER A REFUSAL
-------------------------------
An alignment judge REFUSED the first draft, and three of its findings shaped this
file. The brief itself was a run record and run records are not carried in this
repository's index, so the findings are pinned here — where they cannot go missing:

  - The chain is SEVEN stages. The draft drew five, omitting CODE-QUALITY and
    ACCEPTANCE — a pipeline missing stages schedules work that never runs.
  - Backward propagation had no requirement at all, in a brief resting on a rule
    that names it as one of three things the shape needs.
  - The lane budget was asserted as `8`. It is DERIVED here, because 8 lanes with
    one in REVIEW needs 8+7=15 agents against a cap of 10 — the draft deadlocked
    against the very limit it cited.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        sys.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
from squad import shared_file  # noqa: E402 — post-bootstrap import

#: The chain `cycle-idea-to-release` declares. Seven, not five.
STAGES: tuple[str, ...] = (
    "DISCOVER", "PLAN", "IMPLEMENT", "CODE-QUALITY", "REVIEW", "RELEASE", "ACCEPTANCE",
)

#: How each stage consumes work, in swarm-forge's vocabulary. `batch` stages
#: review several items together because doing five at once costs less than five
#: times one; `task` stages take one because their work is per item.
CONSUMPTION: dict[str, str] = {
    "DISCOVER": "task", "PLAN": "task", "IMPLEMENT": "task",
    "CODE-QUALITY": "batch", "REVIEW": "task", "RELEASE": "task",
    "ACCEPTANCE": "batch",
}

#: REVIEW fans out to 5–7 reviewers, so it holds a lane by itself.
REVIEW_FANOUT = 7

#: One retry, then park — the convention `cycle-idea-to-release.md:80` already
#: uses. There it halts and asks a human; here the item parks AND is surfaced,
#: which is the same halt without pretending an agent answered for the person.
MAX_ATTEMPTS = 2


def lane_budget(cpus: int | None = None, review_fanout: int = REVIEW_FANOUT) -> int:
    """How many lanes may run at once, derived rather than chosen.

    The Workflow tool caps concurrent agents at `min(16, cpus - 2)`. One lane may
    be in REVIEW, which spends `review_fanout` of that cap by itself, so the rest
    is what remains. Floors at 1: a pipeline of one lane is a sequential chain,
    which is worse than this but better than a deadlock.
    """
    cpus = cpus if cpus is not None else (os.cpu_count() or 4)
    cap = min(16, max(1, cpus - 2))
    return max(1, cap - review_fanout)


@dataclass
class Item:
    slug: str
    stage: str = STAGES[0]
    attempts: int = 0
    parked: bool = False
    surfaced: bool = False
    park_reason: str = ""
    worktree: str | None = None
    #: A commit handed back from a later stage. The upstream stage MERGES it and
    #: does not treat it as new work — `back-one` in swarm-forge's terms.
    merge_only: str | None = None
    #: What the registry says is holding this item, as of the moment the queue was
    #: built. Carried on the item rather than looked up, because the scheduler must
    #: not read `BACKLOG.md`: it schedules, and something else decides eligibility.
    #: An EMPTY LIST means blocked by something with no item to point at — a sponsor
    #: decision, an external action — which is a real impediment, so `None` is the
    #: only value that means "not blocked".
    blocked_by: list[str] | None = None
    #: What the registry said this item was when the queue was built, carried for the
    #: same reason `blocked_by` is: the scheduler must not read `BACKLOG.md`. It is
    #: needed because some transitions are legal only from a specific status, and a
    #: pipeline that cannot see the current one emits writes that get refused.
    #: `None` means the caller did not supply it — then nothing gated on it may run.
    status: str | None = None

    @property
    def blocked(self) -> bool:
        return self.blocked_by is not None

    @property
    def done(self) -> bool:
        return self.stage == "__done__"


#: What a completed stage means for the item's registry status. The pipeline moves an
#: item between STAGES; the registry records how far it got. Mapping the two was missing
#: entirely until 2026-08-30, so an item parked in a lane still read `triaged` on disk —
#: and the disk is the only copy that outlives the session.
#:
#: Keyed by the stage being ENTERED, because entering one is the evidence the previous
#: finished. Stages with no entry are stages that do not change the registry.
#: `PLAN` is deliberately absent, and its absence is the fix for the defect that made
#: IMPLEMENT unreachable.
#:
#: It used to write `triaged` on entering PLAN — reading "DISCOVER finished, so the item
#: is measured". True, but the item was ALREADY past it: `cycle-backlog` puts `approved`
#: after `triaged`, and only `approved` may become `planned`. So the map demoted an
#: approved item to `triaged` on its way into PLAN, and one stage later `REQUIRES_STATUS`
#: refused `planned` because the registry now said `triaged`. Every item parked at
#: IMPLEMENT, whatever its status had been.
#:
#: Traced 2026-09-15 on a consumer that ran three days and shipped nothing: the scheduler
#: could not reach the stage that writes code, and the park it produced looked like a
#: gate holding rather than a scheduler contradicting itself.
#:
#: A status only ever moves FORWARD here. Entering PLAN proves DISCOVER finished, which
#: an item at `approved` has already recorded — there is nothing left to write.
STATUS_ON_ENTERING = {
    "IMPLEMENT": "planned",
    "__done__": "shipped",
}

#: The same mapping for a BACKWARD hop, and deliberately not the same table.
#:
#: A send-back to PLAN means review rejected the plan. It did not withdraw the
#: decision to do the work, so the item lands at `approved` — the stage that
#: PRODUCES plans — and not at `triaged`, which is where the decision has not been
#: made yet. Reusing the forward map demotes past the decision and then requires
#: it to be made again, by the only thing present, which is this pipeline.
#:
#: `planned -> triaged` is not in `backlog_status.ALLOWED` either, so the shared
#: table did not merely mean the wrong thing — it emitted a write that `advance()`
#: refuses.
STATUS_ON_SEND_BACK = {
    "PLAN": "approved",
}

#: What the registry must ALREADY say before the pipeline may write a status.
#:
#: Only one entry, and it is the whole governance question. `planned` is legal from
#: `approved` alone, so an item that has not been approved cannot be planned — and
#: the pipeline may not approve it on the way past.
#:
#: That refusal is read, not chosen. `rules/decision-delegation.txt` sorts walls
#: into a delegable set and a retained one, and retains `governance`: "the item
#: itself names autonomous execution as the bypass its governance exists to
#: prevent. Delegation cannot authorize the thing it would be a bypass OF."
#: `approved` records that somebody with the authority decided; a pipeline writing
#: it makes the state mean "the pipeline got here" instead. So no consumer's
#: delegation file can hand this over — moving `governance` to the delegated column
#: is the exact move that clause forbids.
#:
#: The cost is that automation stops where a person is required. That is what the
#: state is for, and it is the reason this is a park with a stated reason rather
#: than a silent halt.
REQUIRES_STATUS = {
    "planned": ("approved",),
}


@dataclass
class StatusWrite:
    """One pending change to BACKLOG.md, to be applied by `mechanisms/cycle/backlog_status.py`.

    The pipeline accumulates these instead of writing, so that scheduling stays a pure
    function of its own state and a run can be replayed, inspected, or aborted without
    having already edited the registry.
    """
    slug: str
    status: str | None = None
    block_on: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class Pipeline:
    items: list[Item]
    lanes: int = field(default_factory=lane_budget)
    running: list[Item] = field(default_factory=list)
    live_worktrees: set[str] = field(default_factory=set)
    released_worktrees: set[str] = field(default_factory=set)
    #: Registry changes this run has earned, oldest first. Drained by the runner.
    pending_writes: list[StatusWrite] = field(default_factory=list)

    # ── queries ────────────────────────────────────────────────────────────
    def item(self, slug: str) -> Item:
        """The item with this slug, or a KeyError NAMING it and what is known.

        A bare `next()` with no default raises StopIteration, and `complete`, `fail`,
        `park`, `unpark`, `block`, `send_back` and `force_stage` all route through here.
        A slug that is not in `self.items` — a typo, an item dropped by a re-read of
        SELECT, a stage brief naming yesterday's id — surfaced as StopIteration, which
        says nothing about which slug or which pipeline, and which a `for` loop one frame
        up silently reads as "the sequence ended".
        """
        for candidate in self.items:
            if candidate.slug == slug:
                return candidate
        known = ", ".join(i.slug for i in self.items) or "none"
        raise KeyError(f"{slug!r} is not in this pipeline. Known: {known}")

    def _eligible(self) -> list[Item]:
        """Work that can start, FURTHEST ALONG FIRST.

        The order is the whole scheduling policy, and until 2026-09-15 there was none:
        lanes were filled in registry order, so an item at DISCOVER took a lane ahead of
        one at IMPLEMENT that was three stages from landing.

        Measured on a consumer over three days, and the shape is unmistakable:

            12/09   44 discover ·  3 plan
            13/09   13 discover ·  3 align ·  9 plan
            14/09                  29 align ·  2 plan ·  1 implement
            15/09                   6 align ·  1 plan ·  7 implement

        Everything advanced one phase before anything advanced two. With 93 items that
        means nothing reaches RELEASE until nearly everything has crossed every phase
        before it — 501 artefacts, zero shipped.

        Finishing beats starting. An item at IMPLEMENT is worth more lane-time than one
        at DISCOVER because it is closer to being work somebody can use, and the item
        left waiting loses nothing it would not have lost anyway.

        Ties keep registry order, which `cycle-maintenance` already ranks: triaged
        before raw, then oldest first. So within a stage the existing fairness rule
        still decides, and only ACROSS stages does this reorder anything.
        """
        busy = {i.slug for i in self.running}
        ready = [i for i in self.items
                 if not i.parked and not i.done and not i.blocked and i.slug not in busy]
        return sorted(ready, key=lambda i: -STAGES.index(i.stage))

    # ── scheduling ─────────────────────────────────────────────────────────
    def schedule(self) -> list[Item]:
        """Fill free lanes. Returns what started this call, not everything running."""
        started: list[Item] = []
        for item in self._eligible():
            if len(self.running) >= self.lanes:
                break
            # REVIEW spends the fan-out budget by itself; two at once need 14
            # agents against a cap of 10.
            if item.stage == "REVIEW" and any(r.stage == "REVIEW" for r in self.running):
                continue
            item.worktree = f"wt/{item.slug}-{item.stage.lower()}"
            self.live_worktrees.add(item.worktree)
            self.running.append(item)
            started.append(item)
        return started

    def take_batch(self, stage: str) -> list[Item]:
        """Everything queued at `stage` for a batch stage; one for a task stage."""
        queued = [i for i in self.items
                  if i.stage == stage and not i.parked and not i.done]
        if stage == "REVIEW":
            return queued[:1]
        return queued if CONSUMPTION.get(stage) == "batch" else queued[:1]

    # ── transitions ────────────────────────────────────────────────────────
    def complete(self, slug: str, verdict: str = "PASS") -> None:
        item = self.item(slug)
        self._release(item)
        if verdict != "PASS":
            # The scheduler obeys the gate; it does not reinterpret it.
            self.park(slug, reason=verdict)
            return
        item.attempts = 0
        item.merge_only = None
        nxt = STAGES.index(item.stage) + 1
        item.stage = STAGES[nxt] if nxt < len(STAGES) else "__done__"
        self._record(item, STATUS_ON_ENTERING.get(item.stage))

    def _record(self, item: Item, status: str | None) -> None:
        """Queue a registry write, or park if the contract will not accept it.

        The item has ALREADY moved to the new stage when this runs, so parking here
        leaves it at the stage it reached — unparking resumes the work rather than
        discarding the phase that just finished.
        """
        if not status:
            return
        needed = REQUIRES_STATUS.get(status, ())
        if needed and item.status not in needed:
            self.park(item.slug, surface=True, reason=(
                f"{status} is legal only from {' or '.join(needed)}; the registry says "
                f"{item.status or 'nothing'}. The pipeline may not approve — "
                f"rules/decision-delegation.txt retains governance decisions, and "
                f"approving is the autonomous-execution bypass that clause names."
            ))
            return
        self.pending_writes.append(StatusWrite(item.slug, status=status))
        item.status = status

    def fail(self, slug: str, reason: str) -> None:
        item = self.item(slug)
        item.attempts += 1
        self._release(item)
        if item.attempts >= MAX_ATTEMPTS:
            self.park(slug, reason=reason, surface=True)

    def park(self, slug: str, reason: str, surface: bool = False) -> None:
        item = self.item(slug)
        item.parked = True
        item.park_reason = reason
        item.surfaced = surface or item.surfaced
        self._release(item)

    def unpark(self, slug: str) -> None:
        """Resumes at the stage it stopped in. Restarting from DISCOVER would
        throw away the wait that parked it."""
        item = self.item(slug)
        item.parked = False
        item.attempts = 0
        item.blocked_by = None

    def block(self, slug: str, blockers: list[str] | None = None, note: str = "") -> None:
        """An item that discovered mid-flight it needs another item.

        This is the case the registry had no way to express: work starts, and partway
        through it turns out to depend on something else — a new item to be filed, or
        one already in the backlog. The lane is freed (holding it would burn a slot on
        something that cannot move) and the dependency is recorded where it survives
        the session, which is the registry rather than this object.

        The item keeps its STAGE. It resumes where it stopped, because the stage is
        exactly the fact needed to resume, and `blocked` is derived from the pair.
        """
        blockers = list(blockers or [])
        if not blockers and not note.strip():
            raise ValueError("an impediment needs either an item id or a stated reason")
        item = self.item(slug)
        item.parked = True
        item.park_reason = note or f"blocked by {', '.join(blockers)}"
        item.surfaced = True
        item.blocked_by = blockers
        self._release(item)
        self.pending_writes.append(StatusWrite(slug, block_on=blockers, note=note))

    def send_back(self, slug: str, to: str, commit: str) -> None:
        """A merge-only hop to an earlier stage: carries a commit, not a task."""
        if STAGES.index(to) >= STAGES.index(self.item(slug).stage):
            raise ValueError(f"{to} is not upstream of {self.item(slug).stage}")
        item = self.item(slug)
        self._release(item)
        item.stage = to
        item.merge_only = commit
        item.parked = False
        # A send-back demotes the registry too. An item whose plan did not survive
        # review is no longer `planned`, and leaving it so tells every later reader
        # that a plan exists which review already rejected. It lands at the decision
        # that still stands, not before it — see STATUS_ON_SEND_BACK.
        self._record(item, STATUS_ON_SEND_BACK.get(to))

    def force_stage(self, slug: str, stage: str) -> None:
        """Test and recovery seam: place an item without running the stages."""
        self.item(slug).stage = stage

    # ── the registry ───────────────────────────────────────────────────────
    def drain_writes(self) -> list[StatusWrite]:
        """Hand over the pending registry changes and forget them."""
        writes, self.pending_writes = self.pending_writes, []
        return writes

    # ── worktrees ──────────────────────────────────────────────────────────
    def _release(self, item: Item) -> None:
        if item in self.running:
            self.running.remove(item)
        if item.worktree:
            self.live_worktrees.discard(item.worktree)
            self.released_worktrees.add(item.worktree)
            item.worktree = None



def from_selection(selection: dict, lanes: int | None = None) -> Pipeline:
    """Build a pipeline from what `select_backlog_item.py --json` produced.

    The bridge is the DATA, not an import. `scripts/` does not import from `skills/`
    anywhere in this kit — the dependency runs the other way, with skills importing
    `route_domain.py` — and having the scheduler reach into a skill to read
    `BACKLOG.md` would both invert that and give it a second job. It schedules;
    something else decides who is eligible.

    Items named in `walls` are carried too, blocked. Dropping them would make the
    pipeline unable to report why an item it was asked about is not running, and
    `unpark()` could never bring one back without rebuilding the whole object.
    """
    walls = selection.get("walls") or {}
    items = [Item(slug=slug) for slug in selection.get("queue") or []]

    # Items at `approved` enter at PLAN, not at DISCOVER.
    #
    # `queue` is what SELECT hands to `/discover-plan`, and `cycle-maintenance.md §
    # Chain` sends an approved item to `/plan-write` instead — so an approved item is
    # correctly absent from it. Reading only `queue` meant a registry of 87 approved and
    # 5 triaged items handed this scheduler FIVE, measured on a consumer 2026-09-15.
    #
    # The stage machine handled an approved item correctly the whole time; it was never
    # given one through the documented path. Two mechanisms, each right alone,
    # disagreeing at the seam nobody ran — the same shape as the demotion that made
    # IMPLEMENT unreachable.
    #
    # They start at PLAN because DISCOVER already ran: that is what `approved` records,
    # and re-measuring would discard the opportunity file the decision rests on.
    for slug in selection.get("awaiting_plan") or []:
        item = Item(slug=slug, status="approved")
        item.stage = "PLAN"
        items.append(item)

    # In flight: `planned` says work STARTED, never how far it got. An item whose
    # IMPLEMENT wrote a record has passed that stage and enters at REVIEW; one without a
    # record has not, and enters at IMPLEMENT — whose brief now stops if another lane
    # already holds it.
    #
    # Third instance of one seam walking forward, and the reason a test of this function
    # alone would not have caught any of them: `approved` was absent from `queue`, then
    # nobody wrote `planned`, and then writing it removed the item from every key this
    # function reads. Measured on a consumer 2026-09-15: an item with a passing gate
    # report was reachable only by typing its slug.
    implemented = set(selection.get("in_flight_implemented") or [])
    for slug in selection.get("in_flight") or []:
        item = Item(slug=slug, status="planned")
        item.stage = "REVIEW" if slug in implemented else "IMPLEMENT"
        items.append(item)

    items += [Item(slug=slug, parked=True, surfaced=True, blocked_by=list(blockers),
                   park_reason=("blocked by " + ", ".join(blockers)) if blockers
                               else "blocked by something with no item to point at")
              for slug, blockers in sorted(walls.items())]
    return Pipeline(items=items, lanes=lanes) if lanes else Pipeline(items=items)

def apply_writes(backlog: Path, writes: list[StatusWrite]) -> list[str]:
    """Apply pending registry changes, returning the refusals rather than raising.

    Refusals are RETURNED, not raised, because one illegal transition must not abort
    the others. A run that discovers three things and can record two of them should
    record two — the third comes back as a line for a human to read, which is the
    honest outcome when the writer and the registry disagree about what is legal.
    """
    # `mechanisms/cycle/` on the path first. This was a bare `import backlog_status`,
    # which resolved only because the two test files that called `apply_writes` had
    # already put that directory on `sys.path` themselves — so the function worked in
    # the suite and raised ModuleNotFoundError the first time it was called from
    # anywhere else. Found by giving this module the CLI it never had.
    _cycle = Path(__file__).resolve().parents[1] / "cycle"
    if str(_cycle) not in sys.path:
        sys.path.insert(0, str(_cycle))
    import backlog_status as bs

    # One transaction over the shared registry. This read the file, folded every pending
    # write into the string and put the whole thing back — no lock across the span and no
    # atomic replace at the end — while `mechanisms/cycle/backlog_status.py` does the same
    # from its own CLI and the briefs this orchestrator dispatches tell every lane to run
    # it. Two writers that read the same bytes lost one set of transitions silently, and
    # a writer interrupted mid-write left a truncated registry the next reader parses as
    # a shorter one. `squad/shared_file.py` carries the measurement.
    refusals: list[str] = []

    def fold(content: str) -> str:
        for write in writes:
            try:
                if write.block_on or write.note:
                    content = bs.block(content, write.slug.upper(), write.block_on, write.note)
                if write.status:
                    content = bs.advance(content, write.slug.upper(), write.status)
            except bs.Refused as exc:
                refusals.append(f"{write.slug}: {exc}")
        return content

    shared_file.update(backlog, fold)
    return refusals


def main(argv: list[str] | None = None) -> int:
    """The entry point this module did not have.

    `schedule`, `take_batch`, `complete`, `fail`, `park`, `unpark`, `block`,
    `send_back`, `force_stage`, `drain_writes`, `from_selection` and `apply_writes`
    were reachable from exactly two places in the tree, both of them test files.
    `skills/pipeline/SKILL.md` names `from_selection()` in prose and gives no command
    that reaches it, and `StatusWrite`'s own docstring says its writes are "to be
    applied by mechanisms/cycle/backlog_status.py" — by a runner that does not exist.

    So the registry write-back, the scheduler and the whole stage machinery were a
    library nothing outside the suite could call. This is the door: SELECT's JSON in,
    the schedule out, and `--apply` to drain the pending writes into the registry the
    way the docstring always said they would be.
    """
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selection", type=Path, required=True,
                    help="SELECT's JSON (`select_backlog_item.py --json`)")
    ap.add_argument("--backlog", type=Path, default=Path("BACKLOG.md"))
    ap.add_argument("--lanes", type=int, default=None)
    ap.add_argument("--stage", default="", help="print the batch waiting at this stage")
    ap.add_argument("--apply", action="store_true",
                    help="drain the pending status writes into the registry")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        selection = json.loads(args.selection.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"could not read {args.selection}: {exc}", file=sys.stderr)
        return 2

    pipeline = from_selection(selection, lanes=args.lanes)
    running = pipeline.schedule()
    batch = pipeline.take_batch(args.stage) if args.stage else []

    refusals: list[str] = []
    if args.apply:
        if not args.backlog.is_file():
            print(f"no registry at {args.backlog}; nothing to write", file=sys.stderr)
            return 2
        refusals = apply_writes(args.backlog, pipeline.drain_writes())

    out = {
        "scheduled": [i.slug for i in running],
        "batch": [i.slug for i in batch],
        "stage": args.stage,
        "applied": args.apply,
        # Returned, never raised: one illegal transition must not abort the others, and
        # a refusal nobody printed is a transition that silently did not happen.
        "refusals": refusals,
    }
    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(f"scheduled {len(running)}: {', '.join(out['scheduled']) or '(none)'}")
        if args.stage:
            print(f"batch at {args.stage}: {', '.join(out['batch']) or '(none)'}")
        for line in refusals:
            print(f"  REFUSED {line}", file=sys.stderr)
    return 1 if refusals else 0


if __name__ == "__main__":
    raise SystemExit(main())
