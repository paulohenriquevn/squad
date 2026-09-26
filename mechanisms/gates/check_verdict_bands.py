#!/usr/bin/env python3
"""Every verdict a contract declares must say which band it is in.

    python3 mechanisms/gates/check_verdict_bands.py
    python3 mechanisms/gates/check_verdict_bands.py --json

## The sibling relationship

`check_orphan_verdicts.py` reads `## Verdicts` and asks *can anything emit this?*.
This one reads the same sections and asks *does anything know what it MEANS for the
flow?* — the complementary half, and the one that was missing.

## What it would have caught

Measured 2026-09-08: of 47 verdicts reachable in the event stream, 14 were in
`blocking-verdicts.txt`, 16 in a frozenset hardcoded inside `check_phase_drift.py`,
and **23 in neither**. `check_phase_drift` reads "was the previous verdict clean?"
to tell legitimate rework from a step out of sequence, and an unclassified verdict
was assumed not-clean — so three SUCCESS verdicts (`PRE_RELEASED`,
`ITEM_VERIFIED_LOCAL`, `PRODUCT_ALIGNED`) switched the disorder check off with
nothing in the output to notice.

That is the failure this gate exists to make loud: not a wrong classification, but
an absent one that behaves like a decision.

## Two directions, two different defects

    declared but unclassified   a token in the event stream nobody can place
    blocking but unclassified   a token that holds an item and grades nothing

## Why an unreadable registry is not a pass

A gate that looks, sees nothing and approves produces confidence where there was no
verification — the defect this repository's own CI notes record about `check_xrefs.py`
running without `--strict`.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "cycle"))

#: The extraction is `check_orphan_verdicts`'s, imported rather than repeated. Two
#: definitions of "a declared verdict" would drift, and the drift would be invisible:
#: this gate would pass while sweeping a different set from its sibling.
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
import importlib.util  # noqa: E402 — post-bootstrap import

from verdict_bands import (  # noqa: E402 — post-bootstrap import
    BandEntry,
    load_bands,
    load_local_bands,
)

_spec = importlib.util.spec_from_file_location(
    "_orphan_verdicts", _HERE / "check_orphan_verdicts.py")
_orphan = importlib.util.module_from_spec(_spec)
sys.modules["_orphan_verdicts"] = _orphan
_spec.loader.exec_module(_orphan)


class BandCoverage(Enum):
    COMPLETE = "complete"
    DRIFTED = "drifted"
    UNREADABLE = "unreadable"

    @property
    def exit_code(self) -> int:
        return {"complete": 0, "drifted": 1, "unreadable": 2}[self.value]


@dataclass
class BandReport:
    coverage: BandCoverage = BandCoverage.COMPLETE
    swept: int = 0
    classified: int = 0
    unclassified: list[str] = field(default_factory=list)
    blocking_unclassified: list[str] = field(default_factory=list)
    #: How many of `classified` came from the consumer's own registry. Reported, because
    #: a reader debugging a classification otherwise has two files to search and no hint
    #: which one to open.
    locally_classified: int = 0
    #: Verdicts the local registry tried to reclassify. The kit's file is authoritative
    #: for the kit's own entries — a silent override is the drift a single registry
    #: existed to prevent, and two files must not buy the extension at that price.
    overrides_the_kit: list[str] = field(default_factory=list)
    detail: str = ""

    def as_dict(self) -> dict:
        return {
            "coverage": self.coverage.value,
            "swept": self.swept,
            "classified": self.classified,
            "unclassified": self.unclassified,
            "blocking_unclassified": self.blocking_unclassified,
            "detail": self.detail,
        }


def _declared_verdicts(repo_root: Path) -> set[str]:
    """Every verdict named in a `## Verdicts` section, by the canonical extraction."""
    found: set[str] = set()
    for rule in sorted((repo_root / "rules").glob("cycle-*.md")):
        section = _orphan._SECTION_RE.search(rule.read_text(encoding="utf-8"))
        if not section:
            continue
        for row in _orphan._rows(section.group(2)):
            names = [n for n in _orphan._VERDICT_RE.findall(row)
                     if n not in _orphan._NOT_VERDICTS]
            if names:
                found.add(names[0])
    return found


def _blocking_verdicts(repo_root: Path) -> set[str]:
    path = repo_root / "rules" / "blocking-verdicts.txt"
    if not path.exists():
        return set()
    return {
        line.strip() for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def check_verdict_bands(repo_root: Path) -> BandReport:
    report = BandReport()

    try:
        entries: dict[str, BandEntry] = load_bands(
            repo_root / "rules" / "verdict-bands.txt")
    except (OSError, ValueError) as exc:
        report.coverage = BandCoverage.UNREADABLE
        report.detail = str(exc)
        return report

    try:
        local, clashes = load_local_bands(repo_root / "rules" / "verdict-bands.txt")
    except (OSError, ValueError) as exc:
        report.coverage = BandCoverage.UNREADABLE
        report.detail = f"rules/verdict-bands.local.txt: {exc}"
        return report
    report.locally_classified = len(local)
    report.overrides_the_kit = clashes
    entries.update(local)

    report.classified = len(entries)
    declared = _declared_verdicts(repo_root)
    report.swept = len(declared)

    report.unclassified = sorted(declared - set(entries))
    report.blocking_unclassified = sorted(_blocking_verdicts(repo_root) - set(entries))

    if report.unclassified or report.blocking_unclassified or report.overrides_the_kit:
        report.coverage = BandCoverage.DRIFTED

    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Check that every declared verdict is classified into a band.")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    report = check_verdict_bands(args.root)

    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
        return report.coverage.exit_code

    print(f"verdict bands — {args.root}")
    print(f"  verdict: {report.coverage.value.upper()}")
    if report.coverage is BandCoverage.UNREADABLE:
        print(f"  rules/verdict-bands.txt could not be read: {report.detail}")
        print("  This is NOT a pass — nothing was verified.")
        return report.coverage.exit_code

    if report.locally_classified:
        # Which file, said out loud. A reader debugging a classification otherwise has
        # two registries to search and no hint which one carries the row.
        print(f"  {report.swept} declared in rules, {report.classified} classified "
              f"({report.locally_classified} of them in rules/verdict-bands.local.txt)")
    else:
        print(f"  {report.swept} declared in rules, {report.classified} classified")
    for v in report.overrides_the_kit:
        print(f"  [overrides the kit] {v} is classified in rules/verdict-bands.txt and "
              f"again in rules/verdict-bands.local.txt. The kit's file is authoritative "
              f"for the kit's own verdicts — the local row was NOT applied. Remove it, "
              f"or open an issue if the kit's band is wrong")
    for v in report.unclassified:
        print(f"  [unclassified] {v} — declared in a rule, in no band")
    for v in report.blocking_unclassified:
        print(f"  [unclassified] {v} — holds an item, and grades nothing")
    if report.coverage is BandCoverage.COMPLETE:
        print("  every declared and every blocking verdict names its band")

    return report.coverage.exit_code


if __name__ == "__main__":
    sys.exit(main())
