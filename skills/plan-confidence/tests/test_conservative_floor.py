"""L5 — Conservative floor / fail-closed asymmetric bias."""
from __future__ import annotations

from pathlib import Path

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from run_structural import run_structural  # noqa: E402 — post-bootstrap import

SKILL_ROOT = Path(__file__).parent.parent
RUBRIC = SKILL_ROOT / "templates" / "rubric-v1.md"
THRESHOLDS = SKILL_ROOT.parent.parent / "rules" / "plan-confidence-thresholds.txt"


def test_high_smell_density_caps_at_89(tmp_path: Path) -> None:
    """30+ smell hits prevents SHIPPABLE — caps at SHIPPABLE_WITH_CAVEATS max.

    The cap can fire via either: (a) smell penalty pushing structural_risk low
    enough that composite < 89, or (b) soft_floor explicitly capping at 89.
    Either path satisfies the user-facing invariant.
    """
    smell_text = "should " * 35  # 35 weak imperatives in prose
    plan = tmp_path / "smelly.md"
    plan.write_text(
        f"# Plan\n\n## ADRs\n### D1 — toy\n- Rationale: the alternative was rejected.\n\n"
        f"{smell_text}\n\n"
        f"## Coverage Matrix\n\n"
        f"| # | Gap | Task(s) | Resolution |\n"
        f"|---|-----|---------|------------|\n"
        f"| 1 | g | T1.1 | done |\n",
        encoding="utf-8",
    )
    report = run_structural(plan, RUBRIC, THRESHOLDS, structural_only=True)
    assert report.final_score_after_caps <= 89, (
        f"high-smell plan got {report.final_score_after_caps} > 89 (should be capped)"
    )


def test_a_capped_plan_names_the_soft_floor_that_capped_it(tmp_path: Path) -> None:
    """The MARKER, not only the number.

    This was called `test_soft_floor_marker_fires_when_floor_binds` and asserted only
    `final_score_after_caps <= 89` — the identical assertion `test_high_smell_density_
    caps_at_89` makes on a near-identical fixture, one function above. The marker the
    name promised was read by no line, so a release that stopped emitting markers
    entirely would have left both tests green.

    A score of 89 with no marker is the failure that matters here: the author is told
    their plan is capped and not told by what, which is the one thing they need to fix
    it. So the marker is what gets asserted, and the score is the corroboration.
    """
    smell_text = "should " * 30
    plan = tmp_path / "edge.md"
    plan.write_text(
        f"# Plan\n\n## ADRs\n### D1 — toy\n- Rationale: the alternative was rejected.\n\n"
        f"{smell_text}\n\n"
        f"## Coverage Matrix\n\n"
        f"| # | Gap | Task(s) | Resolution |\n"
        f"|---|-----|---------|------------|\n"
        f"| 1 | g | T1.1 | done |\n",
        encoding="utf-8",
    )
    report = run_structural(plan, RUBRIC, THRESHOLDS, structural_only=True)

    assert report.final_score_after_caps <= 89
    floors = [c for c in report.hard_caps_triggered if c.startswith("soft_floor_")]
    assert floors, (
        f"capped at {report.final_score_after_caps} and named no soft floor; the "
        f"author is told the plan is held and not told by what. "
        f"caps: {report.hard_caps_triggered}")


def test_high_deferred_ratio_caps_at_89(tmp_path: Path) -> None:
    """If >20% of gaps deferred, fail-closed → cap at 89."""
    # 10 gaps, 3 deferred (30% > 20%)
    rows = [f"| {i + 1} | g{i} | T1.{i + 1} | done |" for i in range(7)]
    rows.extend([
        "| 8 | g7 | N/A — D9 out-of-scope | deferred |",
        "| 9 | g8 | N/A — D9 out-of-scope | deferred |",
        "| 10 | g9 | N/A — D9 out-of-scope | deferred |",
    ])
    plan = tmp_path / "deferred.md"
    plan.write_text(
        "# Plan\n\n## ADRs\n### D1 — toy\n- Rationale: the alternative was rejected.\n\n"
        "## Coverage Matrix\n\n"
        "| # | Gap | Task(s) | Resolution |\n"
        "|---|-----|---------|------------|\n"
        + "\n".join(rows),
        encoding="utf-8",
    )
    report = run_structural(plan, RUBRIC, THRESHOLDS, structural_only=True)
    assert report.final_score_after_caps <= 89, (
        f"high-deferred plan got {report.final_score_after_caps} > 89"
    )


def test_clean_plan_can_still_score_high(tmp_path: Path) -> None:
    """Plan with no smells AND no deferrals can still reach SHIPPABLE."""
    plan = tmp_path / "clean.md"
    plan.write_text(
        "# Plan\n\nPlain prose.\n\n"
        "## ADRs\n### D1 — toy\n- Rationale: the alternative was rejected.\n\n"
        "## Coverage Matrix\n\n"
        "| # | Gap | Task(s) | Resolution |\n"
        "|---|-----|---------|------------|\n"
        "| 1 | gap a | T1.1 | done |\n",
        encoding="utf-8",
    )
    report = run_structural(plan, RUBRIC, THRESHOLDS, structural_only=True)
    assert report.final_score_after_caps >= 70


def test_borderline_deferred_does_not_cap(tmp_path: Path) -> None:
    """1 deferred out of 10 (10% ratio) is OK — under 20% threshold."""
    rows = [f"| {i + 1} | g{i} | T1.{i + 1} | done |" for i in range(9)]
    rows.append("| 10 | g9 | N/A — D9 out-of-scope | deferred |")
    plan = tmp_path / "ok-deferred.md"
    plan.write_text(
        "# Plan\n\n## ADRs\n### D1 — toy\n- Rationale: the alternative was rejected.\n\n"
        "## Coverage Matrix\n\n"
        "| # | Gap | Task(s) | Resolution |\n"
        "|---|-----|---------|------------|\n"
        + "\n".join(rows),
        encoding="utf-8",
    )
    report = run_structural(plan, RUBRIC, THRESHOLDS, structural_only=True)
    # 1/10 = 10% deferred — under threshold, no soft cap from deferred
    soft_caps = [c for c in report.hard_caps_triggered if "soft_floor" in c]
    assert "soft_floor_high_deferred_ratio" not in soft_caps


def test_fail_closed_principle_documented_in_skill() -> None:
    """L5: SKILL.md should mention the fail-closed bias."""
    skill_md = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    # Look for any mention of conservative/fail-closed
    text_lower = skill_md.lower()
    assert "fail-closed" in text_lower or "conservative" in text_lower or "fail closed" in text_lower
