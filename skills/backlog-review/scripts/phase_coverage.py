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



# --------------------------------------------------------------------------------------------
# ADR 0012 — three classes of record, not one.
#
# The scan above answers "does a file for this item exist in this phase's directory". That is the
# right question for two phases and the wrong one for three, and grading them all the same way
# produced a report that named as gaps two things that are not:
#
#   plan, review    PER-ITEM and mandatory. A plan that exists only in someone's head is an
#                   intention; a review verdict nobody wrote down cannot be checked against the
#                   findings that produced it.
#   code-quality    PER-SLICE. `/code-quality` scores a TREE — `cq_invoke` takes a plan slug and
#                   audits the whole checkout — so a per-item audit would assert a measurement
#                   that never happened. One record per release slice, naming its items.
#   release         PER-RELEASE. One release carries many items; an item is covered when a release
#                   record names it.
#   discover        Satisfied by the item's own `evidence:` block. `cycle-discover.md` has two
#                   entry paths and only one writes an opportunity file — a `--sweep` finding
#                   registers directly with evidence attached.
#
# A percentage that rises because the metric was corrected is not progress, so `main` prints BOTH:
# the strict per-item scan and this grading. Anyone can check which one moved.


_EVIDENCE_RE = re.compile(r"^evidence:\s*(.*)$", re.MULTILINE)
_PLAN_FIELD_RE = re.compile(r"^plan:\s*not-warranted\s*$", re.MULTILINE)

MANDATORY_PER_ITEM = (Phase.PLAN, Phase.REVIEW)


@dataclass
class GradedItem:
    coverage: ItemCoverage
    satisfied: set[Phase] = field(default_factory=set)

    @property
    def item(self) -> str:
        return self.coverage.item

    @property
    def gaps(self) -> list[Phase]:
        if not self.coverage.expects_full_loop:
            return []
        return [p for p in Phase if p not in self.satisfied]


def _blocks(registry: Path) -> dict[str, str]:
    text = registry.read_text(encoding="utf-8")
    matches = list(_ITEM_RE.finditer(text))
    out: dict[str, str] = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[m.group(1)] = text[m.end():end]
    return out


def grade(report: list[ItemCoverage], registry: Path) -> list[GradedItem]:
    """Apply ADR 0012 on top of the strict scan."""
    blocks = _blocks(registry)
    graded: list[GradedItem] = []
    for r in report:
        satisfied = set(r.phases)
        block = blocks.get(r.item, "")

        # discover — the registry block's own evidence counts, unless it is the absence marker.
        evidence = _EVIDENCE_RE.search(block)
        if evidence and evidence.group(1).strip() not in ("", "none-yet"):
            satisfied.add(Phase.DISCOVER)

        # plan — a change the contract says needs none is not a gap.
        if _PLAN_FIELD_RE.search(block):
            satisfied.add(Phase.PLAN)

        graded.append(GradedItem(coverage=r, satisfied=satisfied))
    return graded


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
    live = [r for r in report if r.expects_full_loop]
    total = len(live)
    graded = [g for g in grade(report, args.registry) if g.coverage.expects_full_loop]

    print(f"{total} items expect the full loop ({len(report) - total} killed, excluded)\n")

    # BOTH numbers, always. A percentage that rises because the metric was corrected is not
    # progress, and printing only the graded one would hide which of the two moved.
    print(f"  {'phase':14} {'strict':>10}   {'ADR 0012':>10}")
    for phase in Phase:
        strict = sum(1 for r in live if phase in r.phases)
        adr = sum(1 for g in graded if phase in g.satisfied)
        pct_s = (strict * 100 // total) if total else 0
        pct_a = (adr * 100 // total) if total else 0
        print(f"  {phase.value:14} {strict:3}/{total} {pct_s:3}%   {adr:3}/{total} {pct_a:3}%")

    strict_complete = [r for r in live if not r.missing]
    adr_complete = [g for g in graded if not g.gaps]
    print(f"\n  complete: {len(strict_complete)}/{total} strict, {len(adr_complete)}/{total} graded")

    gaps = [g for g in graded if g.gaps]
    if args.show == "all" or gaps:
        print("\nitems with a gap under ADR 0012:")
        for g in gaps:
            print(f"  {g.item} [{g.coverage.status}] missing: {', '.join(p.value for p in g.gaps)}")

    print(
        "\nA missing record is a QUESTION, not a verdict: a one-line change needs no plan"
        "\n(cycle-plan.md), and this cannot see whether an artifact that exists is any good.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
