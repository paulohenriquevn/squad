#!/usr/bin/env python3
"""Attack the cause of a halt instead of stepping over it.

    python3 skills/backlog-review/scripts/squad_boss.py ~/dev/theo

## The signal this exists for

Measured on 2026-08-31. `/implement` halted on B-033 and wrote a BLOCKED report
naming three pre-existing test failures it could not fix, and naming the items it had
just registered for them: B-168, B-169, B-170. The report then offered a sponsor
three paths — fix them first, accept the failure with a caveat, or change the gate.

The queue sat still for 85 minutes. Not because the answer was hard, but because
every route out of a halt was modelled as a DECISION, and decisions wait for people.

One of those routes is not a decision. B-033 fails its gate because three named items
are unfinished; finishing them makes it pass. Nobody has to choose that — it is what
the report measured. What needs choosing is only whether to SKIP the gate, and that
stays with a person, permanently.

## What it does, and the line it does not cross

It reads the BLOCKED reports on disk, takes the item ids they cite, keeps the ones
still open, and hands the selector an order: work that unblocks a halted item goes
first. That is the whole mechanism.

It does NOT decide anything about the halted item. It does not write `blocked_by`
(that is the report's "Path B", a path nobody chose), does not mark the item blocked,
does not touch its status, and never relaxes the gate that halted it. The halted item
stays exactly where the phase left it, waiting for the person the report addresses —
while the causes it named get built.

## Where it lives

Beside the selector and the board, not in `scripts/`: they are its only callers, and
the registry parsing it leans on lives here too. `scripts/` may not import `skills/`,
so putting it there would have meant duplicating the parse.

## Why this is code and not an agent

Extracting `B-\\d{3,}` from a file and sorting a list needs no judgement, and
`squad_lead.py` already records what a second agent costs: the supervisor that shipped
a NameError on the day it supervised. Every decision this thing does not make is a
decision it cannot get wrong.

The one place judgement could enter — "which of the ids in this prose is really the
cause?" — is answered by measurement instead: an id counts when the registry says it
is still open. A finished item cannot be what holds anything, whatever the prose
around it says. Over-including costs a reordering of the queue; under-including costs
the halt staying put, so the rule leans the cheap way.

Exit codes: 0 reported · 1 the project or its registry is unreadable
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

#: Phase output directory -> the phase that writes there. A BLOCKED report is named
#: `{slug}-BLOCKED.md` and lives beside the phase's other artefacts.
HALT_DIRS = {"implementations": "implement", "reviews": "review", "releases": "release"}

#: Statuses that mean an item is still work. A shipped or killed cause cannot be what
#: holds anything, however the report's prose reads.
OPEN_STATUS = ("raw", "triaged", "planned")

_ITEM_RE = re.compile(r"\bB-(\d{3,})\b")
_SLUG_ITEM_RE = re.compile(r"\bb-?(\d{3,})\b", re.IGNORECASE)


def _records_dir(project_root: Path) -> Path | None:
    for relative in (".claude/records", "records"):
        candidate = project_root / relative
        if candidate.is_dir():
            return candidate
    return None


def _item_of(name: str) -> str:
    """`b033-prometheus-url-dev-public-BLOCKED.md` -> `B-033`."""
    match = _SLUG_ITEM_RE.search(name)
    return f"B-{match.group(1)}" if match else ""


def halt_reports(project_root: Path) -> dict[str, Path]:
    """Item id -> the BLOCKED report a phase left for it.

    The single reader of these files. `board_state.halted_items` and the selector both
    come through here, because two scans of the same directory drift the way two copies
    of a blocking-verdict list already did in this repository.
    """
    records = _records_dir(project_root)
    if records is None:
        return {}
    found: dict[str, Path] = {}
    for base in HALT_DIRS:
        directory = records / base
        if not directory.is_dir():
            continue
        for entry in sorted(directory.glob("*-BLOCKED.md")):
            item = _item_of(entry.name)
            if item:
                found.setdefault(item, entry)
    return found


def causes_named(report: Path, halted_item: str) -> list[str]:
    """Item ids the report cites, minus the item it is about.

    Prose, read with a regex, because that is what the reports are: `/implement` writes
    them for a person. A stricter parser would need the reports to carry a machine
    section, and inventing that format would leave every report already on disk
    unreadable — including the one that revealed this gap.
    """
    try:
        body = report.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    seen: list[str] = []
    for match in _ITEM_RE.finditer(body):
        item = f"B-{match.group(1)}"
        if item != halted_item and item not in seen:
            seen.append(item)
    return seen


def attack_plan(project_root: Path, statuses: dict[str, str]) -> dict[str, list[str]]:
    """Halted item -> the OPEN items its report names as the cause.

    An entry survives only when at least one cause is still open. A halt whose causes
    all shipped is not something to attack; it is something to re-run, and deciding
    that is the person's.
    """
    plan: dict[str, list[str]] = {}
    for item, report in halt_reports(project_root).items():
        live = [c for c in causes_named(report, item)
                if statuses.get(c, "") in OPEN_STATUS]
        if live:
            plan[item] = live
    return plan


def unblocking_ids(project_root: Path, statuses: dict[str, str]) -> set[str]:
    """Every open item that some halted item's report names as its cause.

    This is the whole contribution to the selector: membership in this set moves an
    item to the front of the queue. It changes ORDER, never eligibility — an item here
    that is blocked or halted is still held by the rules that hold it.
    """
    return {cause for causes in attack_plan(project_root, statuses).values()
            for cause in causes}


def _statuses_from(backlog: Path) -> dict[str, str]:
    """Read `status:` per item, for the CLI only.

    The library path takes statuses from its caller — the selector already parsed the
    registry and re-parsing it here would be a second reading of one file, free to
    disagree with the first.
    """
    body = backlog.read_text(encoding="utf-8-sig", errors="replace")
    out: dict[str, str] = {}
    for block in re.split(r"^(?=## B-\d)", body, flags=re.MULTILINE)[1:]:
        header = re.match(r"## (B-\d+)", block)
        status = re.search(r"^status:\s*(\S+)\s*$", block, re.MULTILINE)
        if header:
            out[header.group(1)] = status.group(1) if status else ""
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project", type=Path, nargs="?", default=Path("."),
                        help="project whose records and BACKLOG.md to read")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    project = args.project.expanduser().resolve()
    backlog = project / "BACKLOG.md"
    if not backlog.is_file():
        print(f"FATAL: no BACKLOG.md under {project}", file=sys.stderr)
        return 1

    statuses = _statuses_from(backlog)
    reports = halt_reports(project)
    plan = attack_plan(project, statuses)

    if args.json:
        print(json.dumps({
            "halted": sorted(reports),
            "attack_plan": {k: v for k, v in sorted(plan.items())},
            "unblocking": sorted(unblocking_ids(project, statuses)),
        }, indent=2))
        return 0

    if not reports:
        print("No phase has halted. Nothing to attack.")
        return 0

    for item in sorted(reports):
        causes = plan.get(item, [])
        print(f"{item} — halted, report at {reports[item].name}")
        if not causes:
            # Said plainly, because this is the case a person must still resolve and
            # the one most easily read as "handled".
            print("  names no open item as its cause — only a person can move this")
            continue
        print(f"  unblocked by: {', '.join(causes)}")
        for cause in causes:
            print(f"    {cause} is {statuses.get(cause, '?')}")
    unblocking = sorted(unblocking_ids(project, statuses))
    if unblocking:
        print()
        print(f"{len(unblocking)} item(s) move to the front of the queue: "
              f"{', '.join(unblocking)}")
        print("Order only. Nothing here decides anything about the halted item, and "
              "the gate that halted it is untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
