#!/usr/bin/env python3
"""Pick the next eligible backlog item — and refuse the ones whose turn has not come.

`rules/cycle-maintenance.md § Chain` has specified this since it was written:

    SELECT next item:
         read BACKLOG.md
         filter status in {raw, triaged}
         rank: triaged before raw (measured beats unmeasured)
               then by age (oldest first — a registry that always works the
               newest item starves the rest and stops being a backlog)
         pick the first

Nothing implemented it. The rule carries its own ranking section explaining WHY
triaged outranks raw and age outranks everything else, and no code read it — so the
order was a paragraph an agent was asked to remember while scrolling a file, and the
one runner that exists (`pipeline_workflow.js`) carried a literal list of three ids.

Measured on 2026-08-30: of the eight verdicts `cycle-maintenance.md` declares, four
appear in no skill and no script. It is the largest contract-without-executor in the
kit, and it was invisible to `check_gate_mechanisms.py` because that sweep reads
`## Hard gates` and this rule has no such section.

## Age is the id

The ranking says "oldest first". This reads the id, not the date: ids are monotonic
and never reused (the contract says so and `check_backlog_structure.py` enforces it
as `renumbered`), so a lower number was registered earlier. Measured in one real
registry: 166 items, 52 carrying a registration date — 31%. Ordering by the date
would leave two thirds of the backlog with no key at all, and would be a second
source for a fact the id already carries.

## Blocked items are not eligible

The chain's filter — `status in {raw, triaged}` — predates impediments and is no
longer sufficient on its own. An item waiting on another item is `triaged` on disk
and cannot be worked on, so eligibility is computed from the DERIVED state.

Exit codes: 0 an item was selected · 1 nothing may start
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_backlog_structure import (
    OPEN_STATUS,
    Item,
    _parse_items,
    carries_prose,
    declares_impediment,
    parse_blocked_by,
)

#: The chain's filter. `planned` is open but already has a plan — SELECT hands work
#: to `/discover-plan` or `/idea-to-release`, and an item that has one is in flight.
SELECTABLE = ("triaged", "raw")

#: Triaged before raw: a triaged item carries measured evidence, so its cost to finish
#: is known and a raw item's is not.
_RANK = {status: i for i, status in enumerate(SELECTABLE)}


#: What `--check` answers for an item that is not selectable and not blocked. The
#: verdicts are `cycle-maintenance.md`'s own; SELECT reaches them by a shorter route
#: than ADVANCE does — reading the registry rather than watching a cycle finish — and
#: the meaning is the same either way: this item is past the point where SELECT hands
#: out work.
#:
#: Added on 2026-08-31 after using the tool: an item that had gone to `planned` and
#: whose blocker had SHIPPED came back `BACKLOG_BLOCKED`, which is a lie in the exact
#: direction that matters. Nothing was blocking it; it was ready for the next phase.
#: One verdict was carrying two states — "held back by an impediment" and "already
#: past this gate" — and only the first is a wall.
NOT_SELECTABLE = {
    "planned": "ITEM_IN_FLIGHT",
    "shipped": "ITEM_SHIPPED",
    "killed": "ITEM_KILLED",
}


@dataclass
class Selection:
    verdict: str                      # ITEM_SELECTED · BACKLOG_EMPTY · BACKLOG_BLOCKED
                                      # · ITEM_IN_FLIGHT · ITEM_SHIPPED · ITEM_KILLED
                                      # · ITEM_HALTED
    item_id: str | None = None
    reason: str = ""
    #: Every selectable item held back, and what holds it. Reported even on success,
    #: because "what else is waiting, and on what" is the next question and answering
    #: it should not need a second run.
    walls: dict[str, list[str]] | None = None
    #: Selectable items in the order they would be picked. Lets a caller take a batch
    #: without re-running, which is what the pipeline needs to fill more than one lane.
    queue: list[str] | None = None
    #: Items held by something only a PERSON can open — a decision, an approval, a
    #: dependency in another repository. This is `AWAITING_HUMAN`, the verdict five
    #: cycle rules declare with **Emit it.** and that nothing emitted until
    #: 2026-09-02: `check_orphan_verdicts` could not see the gap because it tested
    #: membership by substring and `AWAITING_HUMAN` matched inside
    #: `INVALID_AWAITING_HUMAN`, in a comment. The defect hid itself.
    #:
    #: Those rules say what the absence costs, and it is measurable: "without the
    #: event it leaves no trace, and every reader — the board, the drift checker,
    #: the selector, the watchdog — sees an item that was never touched." Measured
    #: on a consumer the same day: 14 items in exactly that state, indistinguishable
    #: from untouched, while a fleet ran 13 rounds reporting nothing to do.
    awaiting_human: list[str] | None = None
    #: Items a phase stopped on and wrote a BLOCKED report for. Held out of the queue
    #: and named, because they are neither free nor blocked by another item.
    halted: list[str] | None = None

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "item_id": self.item_id,
            "reason": self.reason,
            "walls": self.walls or {},
            "queue": self.queue or [],
            # Emitted even when empty. A reader that has to infer "no item is
            # awaiting a person" from a missing key cannot tell it apart from a
            # selector too old to report the field — and the whole point of this
            # verdict is that an item held by a person should leave a trace.
            "awaiting_human": self.awaiting_human or [],
        }


def _number(item: Item) -> int:
    try:
        return int(item.item_id.split("-")[1])
    except (IndexError, ValueError):
        return 1 << 30


def live_blockers(item: Item, statuses: dict[str, str]) -> list[str] | None:
    """What still holds this item back, or None when nothing does.

    An empty LIST and None mean different things and the difference matters: the list
    is "blocked by something with no item to point at" (a sponsor decision, an
    external action), and None is "not blocked". Collapsing them would make a prose
    impediment invisible to the caller that has to decide whether to start the work.
    """
    raw = item.fields.get("blocked_by", "")
    if not declares_impediment(raw):
        return None
    ids = parse_blocked_by(raw)
    # An item cannot block itself, and `blocked_by` is prose: the parser lifts every
    # `B-NNN` it finds, so a sentence that names the item — "same prose as B-079" —
    # made B-079 its own blocker. That is a deadlock no work can clear, and it reads
    # like a legitimate impediment: measured on a consumer 2026-09-02, where 26
    # selectable items sat behind seven roots and two of the seven were holding
    # themselves. Dropped here rather than reported, because the registry is prose
    # and an incidental mention is not a claim; `check_backlog_structure` is where a
    # malformed field belongs.
    ids = [b for b in ids if b != item.item_id]
    if not ids:
        return []
    open_ids = [b for b in ids if statuses.get(b, "") in OPEN_STATUS]
    if open_ids:
        return open_ids

    # No OPEN item is named — but that only means the impediment is over when the
    # value was nothing BUT item ids. When it states a reason, the ids in it are
    # context and the reason is the barrier.
    #
    # Measured on a consumer 2026-09-02. B-060 reads "aguardando disposição de
    # status: ... bala 2 movida para B-061 (shipped) ... Vide report B-060". The
    # parser lifts B-061 and B-060; the self-mention is dropped above; B-061 is
    # shipped, so no open id remains, and the item was returned as NOT BLOCKED and
    # handed to the queue as the next thing to work on. An incidental mention of a
    # closed item had erased a decision a person still owes. B-126 the same way.
    # Both were the entire remote queue that day.
    #
    # `check_backlog_structure` has held this exact rule for `stale_block` all
    # along — "a value that also states a reason outlives its item edge, and
    # nothing in this repository can tell whether the sponsor has ratified". Third
    # time in one day that a rule lived in one script and was missing from the
    # other reading the same field.
    return [] if carries_prose(raw) else None


def rank(items: list[Item], unblocking: frozenset[str] = frozenset()) -> list[Item]:
    """The chain's order: what unblocks a halt first, then triaged before raw, then
    oldest first.

    Age normally decides, and it still decides among equals. But an item that some
    halted item's BLOCKED report names as its cause is not an equal: finishing it
    turns a stopped item back into a moving one, and every hour it waits is an hour
    the halted item also waits.

    Measured on 2026-08-31: B-033 halted on three named causes — B-168, B-169, B-170,
    all triaged — and by age alone the queue would have reached them after twenty
    other items. The halt would have outlived all of them.

    This is ORDER, not eligibility. An unblocking item that is itself blocked or
    halted is still held by the rules that hold it; it never gets in ahead of them.
    """
    return sorted(items, key=lambda i: (i.item_id not in unblocking,
                                        _RANK.get(i.fields.get("status", ""), 99),
                                        _number(i)))


def select(text: str, requested: str | None = None,
           halted: frozenset[str] = frozenset(),
           unblocking: frozenset[str] = frozenset()) -> Selection:
    """Choose the next item, or explain why none may start.

    `requested` asks the narrower question — may THIS one start? — which is the form
    the gate takes when a human has already picked. Same computation either way, so
    the gate and the selector cannot disagree.
    """
    items = _parse_items(text)
    by_id = {i.item_id: i for i in items}
    statuses = {i.item_id: i.fields.get("status", "") for i in items}

    selectable = [i for i in items if i.fields.get("status", "") in SELECTABLE]
    walls: dict[str, list[str]] = {}
    free: list[Item] = []
    stopped: list[str] = []
    for item in selectable:
        # A phase already stopped on this one and wrote down why. Handing it out again
        # restarts the thing that halted — measured on 2026-08-31: B-033 was `triaged`
        # with a BLOCKED report on disk and the oldest id among unblocked items, so a
        # caller that only asked SELECT would have relaunched it forever.
        #
        # This is a MEASUREMENT, not a decision: the report exists or it does not.
        # What to DO about the halt stays with whoever the report addresses.
        if item.item_id in halted:
            stopped.append(item.item_id)
            continue
        blockers = live_blockers(item, statuses)
        if blockers is None:
            free.append(item)
        else:
            walls[item.item_id] = blockers

    ordered = rank(free, unblocking)
    queue = [i.item_id for i in ordered]

    # An empty wall list means the impediment names no item — a person's decision,
    # an approval, another repository. Reported on EVERY verdict, not only when the
    # queue is empty: an item awaiting a person is awaiting one whether or not
    # other work exists, and the rules that declare this verdict say the cost of
    # not emitting it is that "every reader sees an item that was never touched".
    awaiting = sorted(k for k, v in walls.items() if not v)

    if requested:
        if requested not in by_id:
            return Selection("BACKLOG_BLOCKED", reason=f"{requested} is not in this backlog",
                             walls=walls, queue=queue, halted=stopped, awaiting_human=awaiting)
        status = statuses.get(requested, "")
        if status not in SELECTABLE:
            verdict = NOT_SELECTABLE.get(status)
            if verdict is None:
                return Selection("BACKLOG_BLOCKED", item_id=requested,
                                 reason=f"{requested} carries no status this contract knows"
                                        f" ({status or 'the field is absent'})",
                                 walls=walls, queue=queue, halted=stopped, awaiting_human=awaiting)
            nexts = {"ITEM_IN_FLIGHT": " It has a plan; continue with /idea-to-release.",
                     "ITEM_SHIPPED": "", "ITEM_KILLED": ""}
            return Selection(verdict, item_id=requested,
                             reason=f"{requested} is {status}, past the point where SELECT hands"
                                    f" out work.{nexts[verdict]}",
                             walls=walls, queue=queue, halted=stopped, awaiting_human=awaiting)
        if requested in halted:
            return Selection(
                "ITEM_HALTED", item_id=requested,
                reason=(f"{requested} is {status}, but a phase stopped on it and wrote a "
                        f"BLOCKED report. Starting it again reruns what halted; read the "
                        f"report first."),
                walls=walls, queue=queue, halted=stopped, awaiting_human=awaiting)
        blockers = live_blockers(by_id[requested], statuses)
        if blockers is not None:
            waiting = ", ".join(blockers) if blockers else "something with no item to point at"
            return Selection(
                "BACKLOG_BLOCKED", item_id=requested,
                reason=(f"{requested} waits on {waiting}. Starting it now would build "
                        f"against a dependency that does not exist yet."),
                walls=walls, queue=queue, halted=stopped, awaiting_human=awaiting)
        return Selection("ITEM_SELECTED", item_id=requested,
                         reason=f"{requested} is {status} and nothing blocks it",
                         walls=walls, queue=queue, halted=stopped, awaiting_human=awaiting)

    if ordered:
        chosen = ordered[0]
        if chosen.item_id in unblocking:
            # Said explicitly: the queue departed from age, and a reader who does not
            # know why will read the pick as a bug.
            reason = (f"{chosen.item_id} is {statuses[chosen.item_id]} and a halted "
                      f"item's report names it as a cause, so it comes before older "
                      f"work — finishing it is what lets the halt move")
        else:
            reason = (f"{chosen.item_id} is {statuses[chosen.item_id]}, the oldest "
                      f"unblocked item of the highest-ranked status")
        return Selection("ITEM_SELECTED", item_id=chosen.item_id, reason=reason,
                         walls=walls, queue=queue, halted=stopped, awaiting_human=awaiting)

    if walls or stopped:
        held = len(walls) + len(stopped)
        # An empty wall list means the impediment names no item — a person's
        # decision, an approval, another repository. That is a different fact from
        # "waits on B-075", and conflating them is what made 14 items look like a
        # queue somebody could work through.
        by_item = len(walls) - len(awaiting)
        return Selection(
            "BACKLOG_BLOCKED",
            reason=(f"{held} selectable item(s) remain and every one is held "
                    f"({by_item} by another item, {len(awaiting)} AWAITING_HUMAN — a "
                    f"decision, approval or dependency only a person opens — and "
                    f"{len(stopped)} by a phase that halted). "
                    f"This is not an empty backlog — running a sweep would add items "
                    f"beside a wall instead of clearing it."),
            walls=walls, queue=queue, halted=stopped,
            awaiting_human=awaiting)

    return Selection("BACKLOG_EMPTY",
                     reason=("nothing is raw or triaged. Not a finish line — "
                             "run /discover-execute --sweep {domain}."),
                     walls=walls, queue=queue, halted=stopped, awaiting_human=awaiting)


def main() -> int:
    parser = argparse.ArgumentParser(description="Select the next eligible backlog item.")
    parser.add_argument("backlog", type=Path, nargs="?", default=Path("BACKLOG.md"))
    parser.add_argument("--check", metavar="B-NNN",
                        help="ask whether THIS item may start, instead of picking one")
    parser.add_argument("--queue", type=int, metavar="N",
                        help="print the first N eligible items in order, for a batch caller")
    parser.add_argument("--ignore-halts", action="store_true",
                        help="hand out an item even if a phase halted on it and wrote "
                             "a BLOCKED report (read the report first)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.backlog.is_file():
        print(f"FATAL: {args.backlog} does not exist", file=sys.stderr)
        return 1

    # Read from the project the backlog sits in, so the CLI answers the same question
    # the board does. `--ignore-halts` exists for the one caller who has read the
    # report and decided to rerun anyway; it is never the default, because a default
    # that ignores a halt turns every stop into a loop.
    text = args.backlog.read_text(encoding="utf-8")
    project = args.backlog.resolve().parent
    halted: frozenset[str] = frozenset()
    unblocking: frozenset[str] = frozenset()
    if not args.ignore_halts:
        try:
            from squad_boss import halt_reports, unblocking_ids
            halted = frozenset(halt_reports(project))
            statuses_for_boss = {i.item_id: i.fields.get("status", "")
                                 for i in _parse_items(text)}
            unblocking = frozenset(unblocking_ids(project, statuses_for_boss))
        except ImportError as error:
            print(f"halt detection unavailable ({error}); proceeding without it",
                  file=sys.stderr)

    result = select(text, args.check, halted, unblocking)

    if args.json:
        print(json.dumps(result.as_dict(), indent=2, ensure_ascii=False))
    elif args.queue:
        for item_id in (result.queue or [])[:args.queue]:
            print(item_id)
    else:
        print(f"{result.verdict}: {result.item_id or '—'}")
        print(f"  {result.reason}")
        if result.halted:
            print("  halted (a phase stopped and wrote a report):")
            for item_id in result.halted:
                print(f"    {item_id}")
        if result.walls:
            print("  blocked:")
            for iid, blockers in sorted(result.walls.items()):
                waiting = ", ".join(blockers) if blockers else "a decision, no item named"
                print(f"    {iid} <- {waiting}")

    return 0 if result.verdict == "ITEM_SELECTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
