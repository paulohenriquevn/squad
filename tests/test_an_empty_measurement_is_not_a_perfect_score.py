"""Four checkers answered "nothing to measure" with the score for "measured, perfect".

The kit's dominant defect class, one more time: an inability to measure published as a
measurement.

* `check_coverage_matrix`: a Coverage Matrix heading whose rows do not parse yields
  `total_gaps == 0` and `coverage_ratio = 1.0` — "100% of nothing" — which clears the
  `coverage_lt_100` hard cap, one of the two caps that force INVALID.
* `edge_case_coverage`: a plan from which no edge case could be extracted reports
  `coverage_ratio: 1.0` with the note "vacuously true". `consolidate_findings` gates
  the review verdict on that number at 0.80.
* `compute_acceptance_verdict`: an empty criteria list returns ACCEPTED, with the
  reason "all 0 criteria exercised and evidenced in the live system".
* `check_criterion_executability`: criteria absent from a plan produce the same
  acceptable and executable ratios as criteria that are present and good.

None of these is a case where a pass is a sensible default. A plan with no parseable
coverage matrix has not been checked for coverage; a release nobody wrote criteria for
has not been accepted. The verdict for "could not measure" is not the verdict for
"measured and clean".
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "skills" / "plan-confidence" / "scripts"))
sys.path.insert(0, str(_ROOT / "skills" / "acceptance" / "scripts"))
sys.path.insert(0, str(_ROOT / "skills" / "review" / "scripts"))

from check_coverage_matrix import (  # noqa: E402 — post-bootstrap import
    check_coverage_matrix,
)
from compute_acceptance_verdict import compute  # noqa: E402 — post-bootstrap import


def test_a_matrix_with_no_parseable_rows_is_not_complete(tmp_path: Path) -> None:
    plan = tmp_path / "a-plan.md"
    plan.write_text("# Plan\n\n## Coverage Matrix\n\nthe rows were never written\n",
                    encoding="utf-8")

    report = check_coverage_matrix(plan)

    assert not report.is_complete, (
        f"0 gaps scored as {report.coverage_ratio:.0%} complete, which clears the "
        f"hard cap that forces INVALID")


def test_a_matrix_with_rows_that_map_is_complete(tmp_path: Path) -> None:
    """The other side, so the fix above is not simply "always incomplete"."""
    plan = tmp_path / "a-plan.md"
    plan.write_text(
        "# Plan\n\n## Coverage Matrix\n\n"
        "| # | Gap | Task(s) | Resolution |\n"
        "|---|-----|---------|------------|\n"
        "| 1 | a gap | T1.1 | done |\n", encoding="utf-8")

    assert check_coverage_matrix(plan).is_complete


def test_no_criteria_is_not_an_acceptance() -> None:
    result = compute(criteria=[], results=[], defects=[])

    assert result["verdict"] != "ACCEPTED", (
        f'an empty criteria list returned {result["verdict"]}: {result["reasons"]}')


def test_criteria_that_are_all_met_is_an_acceptance() -> None:
    criteria = [{"id": "AC-1", "text": "it works"}]
    results = [{"id": "AC-1", "status": "passed", "evidence": "a screenshot"}]

    result = compute(criteria=criteria, results=results, defects=[])

    assert result["verdict"] == "ACCEPTED", result
