#!/usr/bin/env python3
"""Which cycle phases left a record for each backlog item?

WHY THIS EXISTS
---------------
A stop gate and I spent four rounds disagreeing about whether every item had been through every
phase of the Squad loop. Neither of us had measured it. `BACKLOG.md` records an item's STATUS and
nothing about which phases produced it, so "the loop ran" and "the loop did not run" were both
assertions — and an assertion dressed as a measurement is the defect this ecosystem exists to
refuse.

So this counts. For each `B-NNN` it asks which cycle artifacts exist on disk:

    DISCOVER      knowledge-base/discoveries/opportunities/
    PLAN          knowledge-base/plans/
    CODE_QUALITY  knowledge-base/audits/
    REVIEW        knowledge-base/reviews/
    RELEASE       knowledge-base/releases/

IMPLEMENT is deliberately absent. Its evidence is the commit history, not a knowledge-base file,
and a directory scan that pretended otherwise would report absence for every item whose work
landed as commits — which is all of them.

WHAT IT CANNOT TELL YOU, first, because it is the whole limit
-------------------------------------------------------------
An artifact's EXISTENCE is not proof the phase was done well. A review file can be thin; a plan
can be a placeholder. This measures whether a phase left a RECORD — the same distinction
`gate-scope.mjs` draws between "inspected 354 files" and "inspected them properly".

It also cannot see a phase that legitimately produced nothing. `cycle-plan.md` says a one-line
change needs no plan, and a killed item ends at DISCOVER by design. So a missing artifact is a
QUESTION, never a verdict — which is why this reports and never fails.

Usage:
    python3 phase_coverage.py --registry BACKLOG.md --knowledge-base .claude/knowledge-base
"""
from __future__ import annotations

import argparse
import enum
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


class Phase(enum.Enum):
    DISCOVER = "discover"
    PLAN = "plan"
    CODE_QUALITY = "code-quality"
    REVIEW = "review"
    RELEASE = "release"


_DIRS: dict[Phase, str] = {
    Phase.DISCOVER: "discoveries/opportunities",
    Phase.PLAN: "plans",
    Phase.CODE_QUALITY: "audits",
    Phase.REVIEW: "reviews",
    Phase.RELEASE: "releases",
}

# `b010-` must not be satisfied by `b100-...`: the id is followed by a separator or the end.
# This is the shape a naive `str.startswith` gets wrong, and it gets it wrong silently.
def _slug_re(item: str) -> re.Pattern[str]:
    number = item.split("-")[1]
    return re.compile(rf"\bb0*{int(number)}(?![0-9])", re.IGNORECASE)


def _mentions(path: Path, item: str, slug: re.Pattern[str]) -> bool:
    if slug.search(path.name):
        return True
    try:
        return item in path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def coverage_for_item(item: str, knowledge_base: Path) -> set[Phase]:
    """The phases that left a record for this item."""
    slug = _slug_re(item)
    found: set[Phase] = set()
    for phase, relative in _DIRS.items():
        directory = knowledge_base / relative
        if not directory.is_dir():
            continue
        for candidate in directory.rglob("*"):
            if candidate.is_file() and _mentions(candidate, item, slug):
                found.add(phase)
                break
    return found


@dataclass
class ItemCoverage:
    item: str
    status: str
    phases: set[Phase] = field(default_factory=set)

    @property
    def expects_full_loop(self) -> bool:
        """A killed item ends at DISCOVER by design; its absent phases are not a gap.

        `cycle-discover.md` calls killing an item a SUCCESSFUL outcome — it stopped work that a
        hunch would otherwise have justified. Counting its missing plan as debt would report the
        cycle working correctly as a failure.
        """
        return self.status != "killed"

    @property
    def missing(self) -> list[Phase]:
        if not self.expects_full_loop:
            return []
        return [p for p in Phase if p not in self.phases]


_ITEM_RE = re.compile(r"^## (B-\d+) — .*?$", re.MULTILINE)


def scan_registry(registry: Path, knowledge_base: Path) -> list[ItemCoverage]:
    text = registry.read_text(encoding="utf-8")
    out: list[ItemCoverage] = []
    matches = list(_ITEM_RE.finditer(text))
    for i, m in enumerate(matches):
        body = text[m.end(): matches[i + 1].start() if i + 1 < len(matches) else len(text)]
        status = re.search(r"^status:\s*(\S+)", body, re.MULTILINE)
        out.append(ItemCoverage(
            item=m.group(1),
            status=status.group(1) if status else "?",
            phases=coverage_for_item(m.group(1), knowledge_base),
        ))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--knowledge-base", type=Path, required=True)
    parser.add_argument("--show", choices=["gaps", "all"], default="gaps")
    args = parser.parse_args(argv)

    if not args.registry.is_file():
        print(f"phase-coverage: no registry at {args.registry}", file=sys.stderr)
        return 2
    if not args.knowledge_base.is_dir():
        print(f"phase-coverage: no knowledge-base at {args.knowledge_base}", file=sys.stderr)
        return 2

    report = scan_registry(args.registry, args.knowledge_base)
    graded = [r for r in report if r.expects_full_loop]

    per_phase = {p: sum(1 for r in graded if p in r.phases) for p in Phase}
    total = len(graded)
    print(f"{total} items expect the full loop ({len(report) - total} killed, excluded)\n")
    for phase in Phase:
        n = per_phase[phase]
        pct = (n * 100 // total) if total else 0
        print(f"  {phase.value:14} {n:3}/{total}  {pct:3}%")

    complete = [r for r in graded if not r.missing]
    print(f"\n  all five recorded: {len(complete)}/{total}")

    if args.show == "all" or complete != graded:
        print("\nitems missing a record for at least one phase:")
        for r in graded:
            if r.missing:
                print(f"  {r.item} [{r.status}] missing: {', '.join(p.value for p in r.missing)}")

    print(
        "\nA missing record is a QUESTION, not a verdict: a one-line change needs no plan"
        "\n(cycle-plan.md), and this cannot see whether an artifact that exists is any good.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
