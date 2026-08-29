"""The gate that stops an unaligned item from being built.

WHY THIS IS THE MOST IMPORTANT TEST FILE IN plan-confidence
-----------------------------------------------------------
Until this check existed, the 90% alignment threshold was PROSE. It was written
in `rules/alignment-threshold.md`, restated as a pre-condition in
`cycle-implement.md`, and listed as a phase contract in `cycle-plan.md` — and a
grep across the kit for anything that READ `records/alignment/` returned nothing.
Three documents said the item must not be built; no code could stop it.

That is the exact defect this kit has now measured five times in one week under
five different names: a mechanism with no contract, a contract with no mechanism,
a hook declared in one of two files, a rule implemented on one of two branches.
A gate whose execution depends on somebody remembering is a note.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/plan-confidence/scripts"
sys.path.insert(0, str(SCRIPTS))

from check_alignment_gate import check_alignment_gate  # noqa: E402

PLAN = """---
version: 1.0
---

# Plan: Reduce the trace explorer p95

## Context

Implements B-014 from the backlog. Evidence gathered by `/discover-plan`.

## Tasks

### T1.1 — Profile the shard scan
"""

ALIGNED_BRIEF = """
# Alignment: B-014

## Reviewer sign-off
- [x] CHK001 The stated problem is the one we actually have. [Judgement]
- [x] CHK002 The flows drawn are the flows that matter. [Judgement]
"""


def _plan(tmp_path: Path, body: str = PLAN, slug: str = "b-014-trace-p95") -> Path:
    d = tmp_path / "records" / "plans"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{slug}-plan.md"
    p.write_text(body, encoding="utf-8")
    return p


def _brief(tmp_path: Path, body: str, slug: str = "b-014-trace-p95") -> Path:
    d = tmp_path / "records" / "alignment"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{slug}-alignment.md"
    p.write_text(body, encoding="utf-8")
    return p


def _complete_brief() -> str:
    """A brief that clears the machine threshold, built from the scorer's fixture."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                          / "skills/shared-understanding/tests"))
    from test_score_alignment import COMPLETE_V2
    return COMPLETE_V2


def test_a_plan_citing_a_backlog_item_with_no_brief_is_capped(tmp_path: Path) -> None:
    """The case the whole gate exists for, and the one that used to sail through.

    The plan says it implements B-014. No alignment brief exists. That is not a
    claim about the item — it is a fact about the process: the alignment never
    happened. A hard cap is the honest response, and it is the difference from
    `check_deps_audit`, where a missing report soft-floors because a hard cap
    there would assert a CVE nobody measured.
    """
    report = check_alignment_gate(_plan(tmp_path))
    assert report.applies
    assert report.hard_cap == 49
    assert "B-014" in report.reason


def test_a_blocked_brief_is_capped(tmp_path: Path) -> None:
    """Below 90% the item is not built. That is the threshold, mechanised."""
    _brief(tmp_path, "# Alignment: B-014\n\n## Problem\nIt is slow.\n")
    report = check_alignment_gate(_plan(tmp_path))
    assert report.hard_cap == 49
    assert report.verdict == "BLOCKED"


def test_a_perfect_machine_score_without_sign_off_is_still_capped(tmp_path: Path) -> None:
    """AWAITING_REVIEW is not a pass, and this is where that gets enforced.

    A brief at 100% with no human tick is the state most likely to be misread as
    approval — it looks finished, every criterion is green, and the only thing
    missing is the half the agent does not own. If the cap did not fire here, the
    reviewer sign-off would be decoration.
    """
    _brief(tmp_path, _complete_brief())
    report = check_alignment_gate(_plan(tmp_path))
    assert report.verdict == "AWAITING_REVIEW"
    assert report.hard_cap == 49


def test_an_aligned_item_passes_cleanly(tmp_path: Path) -> None:
    """The bar has to be reachable or the gate gets switched off."""
    _brief(tmp_path, _complete_brief() + ALIGNED_BRIEF.split("## Reviewer sign-off")[0]
           + "## Reviewer sign-off\n"
           + "- [x] CHK001 The stated problem is the one we actually have. [Judgement]\n"
           + "- [x] CHK002 The flows drawn are the flows that matter. [Judgement]\n"
           + "- [x] CHK003 The numbers in the NFRs are the right numbers. [Judgement]\n")
    report = check_alignment_gate(_plan(tmp_path))
    assert report.verdict == "ALIGNED"
    assert report.hard_cap is None
    assert report.soft_floor is None


def test_a_plan_with_no_backlog_item_gets_a_named_soft_floor(tmp_path: Path) -> None:
    """The boundary the script cannot decide, stated instead of hidden.

    A plan citing no `B-NNN` may be a legitimate hotfix, or it may be an item
    that skipped intake precisely to skip this gate. No regex separates those.
    Refusing outright would block every ad-hoc fix; passing silently would leave
    a one-line bypass (omit the id). A soft floor records that nobody checked and
    names it in the verdict, which is the same shape `check_deps_audit` uses for
    an unaudited dependency.
    """
    no_item = PLAN.replace("Implements B-014 from the backlog.", "A one-line hotfix.")
    report = check_alignment_gate(_plan(tmp_path, no_item, slug="hotfix-log-typo"))
    assert not report.applies
    assert report.soft_floor == 89
    assert report.hard_cap is None
    assert "no backlog item" in report.reason.lower()


def test_a_brief_found_by_slug_applies_even_without_a_cited_id(tmp_path: Path) -> None:
    """Deleting the `B-NNN` from the plan must not delete the gate.

    If an alignment brief exists for this slug, the item went through alignment
    and the plan is answerable to its verdict, whether or not the prose still
    names the id.
    """
    no_item = PLAN.replace("Implements B-014 from the backlog.", "A change.")
    _brief(tmp_path, "# Alignment\n\n## Problem\nvague\n")
    report = check_alignment_gate(_plan(tmp_path, no_item))
    assert report.applies
    assert report.hard_cap == 49


def test_an_unreadable_brief_is_not_a_passing_one(tmp_path: Path) -> None:
    """Same rule as a zero denominator: not measured is never approved."""
    p = _brief(tmp_path, "")
    p.write_bytes(b"\xff\xfe\x00garbage\x00")
    report = check_alignment_gate(_plan(tmp_path))
    assert report.hard_cap == 49
    assert "unreadable" in report.reason.lower()


def test_the_reason_always_names_what_to_do_next(tmp_path: Path) -> None:
    """A cap that does not say how to clear it trains people to route around it."""
    for setup in (lambda: None,
                  lambda: _brief(tmp_path, "# Alignment: B-014\n\n## Problem\nslow\n")):
        setup()
        report = check_alignment_gate(_plan(tmp_path))
        assert "shared-understanding" in report.reason or "sign-off" in report.reason, \
            report.reason
