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

from check_backlog_structure import (  # noqa: E402
    OPEN_STATUS,
    Item,
    _parse_items,
    declares_impediment,
    parse_blocked_by,
)

#: The chain's filter. `planned` is open but already has a plan — SELECT hands work
#: to `/discover-plan` or `/idea-to-release`, and an item that has one is in flight.
SELECTABLE = ("triaged", "raw")

#: Triaged before raw: a triaged item carries measured evidence, so its cost to finish
#: is known and a raw item's is not.
_RANK = {status: i for i, status in enumerate(SELECTABLE)}


@dataclass
class Selection:
    verdict: str                      # ITEM_SELECTED · BACKLOG_EMPTY · BACKLOG_BLOCKED
    item_id: str | None = None
    reason: str = ""
    #: Every selectable item held back, and what holds it. Reported even on success,
    #: because "what else is waiting, and on what" is the next question and answering
    #: it should not need a second run.
    walls: dict[str, list[str]] | None = None
    #: Selectable items in the order they would be picked. Lets a caller take a batch
    #: without re-running, which is what the pipeline needs to fill more than one lane.
    queue: list[str] | None = None

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "item_id": self.item_id,
            "reason": self.reason,
            "walls": self.walls or {},
            "queue": self.queue or [],
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
    if not ids:
        return []
    open_ids = [b for b in ids if statuses.get(b, "") in OPEN_STATUS]
    return open_ids or None


def rank(items: list[Item]) -> list[Item]:
    """The chain's order: triaged before raw, then oldest first."""
    return sorted(items, key=lambda i: (_RANK.get(i.fields.get("status", ""), 99), _number(i)))


def select(text: str, requested: str | None = None) -> Selection:
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
    for item in selectable:
        blockers = live_blockers(item, statuses)
        if blockers is None:
            free.append(item)
        else:
            walls[item.item_id] = blockers

    ordered = rank(free)
    queue = [i.item_id for i in ordered]

    if requested:
        if requested not in by_id:
            return Selection("BACKLOG_BLOCKED", reason=f"{requested} is not in this backlog",
                             walls=walls, queue=queue)
        status = statuses.get(requested, "")
        if status not in SELECTABLE:
            return Selection("BACKLOG_BLOCKED", item_id=requested,
                             reason=f"{requested} is {status or 'missing a status'}, not selectable",
                             walls=walls, queue=queue)
        blockers = live_blockers(by_id[requested], statuses)
        if blockers is not None:
            waiting = ", ".join(blockers) if blockers else "something with no item to point at"
            return Selection(
                "BACKLOG_BLOCKED", item_id=requested,
                reason=(f"{requested} waits on {waiting}. Starting it now would build "
                        f"against a dependency that does not exist yet."),
                walls=walls, queue=queue)
        return Selection("ITEM_SELECTED", item_id=requested,
                         reason=f"{requested} is {status} and nothing blocks it",
                         walls=walls, queue=queue)

    if ordered:
        chosen = ordered[0]
        return Selection("ITEM_SELECTED", item_id=chosen.item_id,
                         reason=(f"{chosen.item_id} is {statuses[chosen.item_id]}, the oldest "
                                 f"unblocked item of the highest-ranked status"),
                         walls=walls, queue=queue)

    if walls:
        return Selection(
            "BACKLOG_BLOCKED",
            reason=(f"{len(walls)} selectable item(s) remain and every one is blocked. "
                    f"This is not an empty backlog — running a sweep would add items "
                    f"beside a wall instead of clearing it."),
            walls=walls, queue=queue)

    return Selection("BACKLOG_EMPTY",
                     reason=("nothing is raw or triaged. Not a finish line — "
                             "run /discover-execute --sweep {domain}."),
                     walls=walls, queue=queue)


def main() -> int:
    parser = argparse.ArgumentParser(description="Select the next eligible backlog item.")
    parser.add_argument("backlog", type=Path, nargs="?", default=Path("BACKLOG.md"))
    parser.add_argument("--check", metavar="B-NNN",
                        help="ask whether THIS item may start, instead of picking one")
    parser.add_argument("--queue", type=int, metavar="N",
                        help="print the first N eligible items in order, for a batch caller")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.backlog.is_file():
        print(f"FATAL: {args.backlog} does not exist", file=sys.stderr)
        return 1

    result = select(args.backlog.read_text(encoding="utf-8"), args.check)

    if args.json:
        print(json.dumps(result.as_dict(), indent=2, ensure_ascii=False))
    elif args.queue:
        for item_id in (result.queue or [])[:args.queue]:
            print(item_id)
    else:
        print(f"{result.verdict}: {result.item_id or '—'}")
        print(f"  {result.reason}")
        if result.walls:
            print("  blocked:")
            for iid, blockers in sorted(result.walls.items()):
                waiting = ", ".join(blockers) if blockers else "a decision, no item named"
                print(f"    {iid} <- {waiting}")

    return 0 if result.verdict == "ITEM_SELECTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
