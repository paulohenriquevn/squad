"""`partial` was documented in three places and emitted by none.

`classify_coverage` returned only "covered" or "missing", so the `partial` key in the
JSON was 0 on every run and a consumer counting partials to decide whether coverage
was genuinely complete read a constant.

The status has a real subject: the keyword fallback. A grep hit is evidence that
SOMETHING in the tree mentions the words — not that this edge case has a test. The
named-test route proves an identifier exists; the fallback guesses. Calling both
"covered" told the reader the two carried the same weight.

`coverage_ratio` deliberately still counts covered + partial, so the 0.80 verdict gate
in `consolidate_findings` sees the number it always saw. `confirmed_ratio` is the new,
stricter figure, and it is additive rather than a redefinition.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "skills" / "review" / "scripts"))

from edge_case_coverage import classify_coverage  # noqa: E402 — post-bootstrap import


def _tests_dir(tmp_path: Path, body: str, name: str = "test_thing.py") -> Path:
    tests = tmp_path / "tests"
    tests.mkdir(exist_ok=True)
    (tests / name).write_text(body, encoding="utf-8")
    return tests


def test_a_named_test_that_exists_is_covered(tmp_path: Path) -> None:
    tests = _tests_dir(tmp_path, "def test_rejects_a_negative_balance():\n    pass\n")
    case = {"description": "rejects a negative balance",
            "named_tests": ["test_rejects_a_negative_balance"]}

    assert classify_coverage(case, tests)["status"] == "covered"


def test_a_keyword_hit_alone_is_partial(tmp_path: Path) -> None:
    """Something mentions the words. That is not proof this case has a test."""
    tests = _tests_dir(tmp_path, "def test_balance_handling():\n    negative = 1\n")
    case = {"description": "rejects a negative balance", "named_tests": []}

    result = classify_coverage(case, tests)

    assert result["route"] == "keyword-fallback"
    assert result["status"] == "partial", result


def test_nothing_found_is_missing(tmp_path: Path) -> None:
    tests = _tests_dir(tmp_path, "def test_unrelated():\n    pass\n")
    case = {"description": "rejects a negative balance", "named_tests": []}

    assert classify_coverage(case, tests)["status"] == "missing"
