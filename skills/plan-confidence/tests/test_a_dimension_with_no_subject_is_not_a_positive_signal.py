"""A dimension nobody exercised was reported as a positive signal at full weight.

`check_adr_completeness` returns `completeness_ratio=1.0` for a plan with zero ADRs — deliberate,
and `plan-template.md` says so: *"`/plan-confidence` accepts a plan with NO `## ADRs` section…
deliberately."* A plan with one way to do a thing has no decision to record.

But `run_structural` then reads that ratio twice:

    adr_score = 20.0 * adr.completeness_ratio            # :245 — full 20 of 100
    sign_adr = "positive" if ratio >= 1.0 else "negative" # :252 — a POSITIVE signal

So an empty set contributed a perfect score and read as evidence. The same shape sits on TDD:
a plan with no bug-fix task scores 20/20 for `tdd.coverage_ratio`.

WHAT THIS CHANGES AND WHAT IT DELIBERATELY DOES NOT. The SIGN becomes `neutral` and the label says
NOT MEASURED, because a dimension with no subject is neither positive nor negative and the reader
is the one who needs to know. The SCORE is unchanged: the weights come from `rubric-v1.md` and the
Phase 4.3 algorithm, and the 90% threshold is calibrated against that formula — redistributing 20
points when a dimension is unexercised would silently recalibrate every verdict in the kit, which
is a rubric decision and not a defect fix.

The argument for reporting it is the kit's own, from `check_install_drift`: *"a 0 that means 'not
reported' and a 0 that means 'none' are different facts, and summing them silently is how a total
becomes fiction."* Reported here as `neutral`, so nothing is summed silently.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SCRIPT = _ROOT / "skills" / "plan-confidence" / "scripts" / "run_structural.py"


@pytest.fixture(scope="module")
def mod():
    sys.path.insert(0, str(_SCRIPT.parent))
    spec = importlib.util.spec_from_file_location(_SCRIPT.stem, _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[_SCRIPT.stem] = module
    spec.loader.exec_module(module)
    return module


class _Cov:
    is_complete = True
    coverage_ratio = 1.0


class _Adr:
    def __init__(self, total: int, with_alt: int) -> None:
        self.total_adrs = total
        self.with_alternatives = with_alt
        self.completeness_ratio = 1.0 if total == 0 else with_alt / total


class _Tdd:
    def __init__(self, total: int, with_tdd: int) -> None:
        self.total_bugfix_tasks = total
        self.with_tdd = with_tdd
        self.coverage_ratio = 1.0 if total == 0 else with_tdd / total


def _reason(mod, label_fragment: str, adr, tdd):
    _score, reasons = mod._compute_completeness(_Cov(), adr, tdd)
    for reason in reasons:
        if label_fragment in reason.label:
            return reason
    raise AssertionError(f"no reason labelled {label_fragment!r}: {[r.label for r in reasons]}")


def test_zero_adrs_is_neutral_and_says_it_was_not_measured(mod) -> None:
    reason = _reason(mod, "ADR", _Adr(0, 0), _Tdd(1, 1))

    assert reason.sign == "neutral", (
        f"a plan with no ADR reads as a POSITIVE signal: sign={reason.sign!r}")
    assert "NOT MEASURED" in reason.label, reason.label


def test_zero_bugfix_tasks_is_neutral_too(mod) -> None:
    """The same shape on the other 20-point dimension."""
    reason = _reason(mod, "TDD", _Adr(2, 2), _Tdd(0, 0))

    assert reason.sign == "neutral", reason.sign
    assert "NOT MEASURED" in reason.label, reason.label


def test_a_dimension_that_was_measured_and_holds_is_still_positive(mod) -> None:
    """The control. A change that makes everything neutral measures nothing."""
    reason = _reason(mod, "ADR", _Adr(3, 3), _Tdd(1, 1))

    assert reason.sign == "positive", reason.sign
    assert "NOT MEASURED" not in reason.label


def test_a_dimension_that_was_measured_and_fails_is_still_negative(mod) -> None:
    reason = _reason(mod, "ADR", _Adr(3, 1), _Tdd(1, 1))

    assert reason.sign == "negative", reason.sign


def test_the_score_is_unchanged_by_this(mod) -> None:
    """Deliberate: the weights are the rubric's and the 90% threshold is calibrated to them.

    Redistributing 20 points when a dimension is unexercised would recalibrate every verdict in
    the kit silently. That is a rubric decision, and this is a reporting fix.
    """
    empty, _ = mod._compute_completeness(_Cov(), _Adr(0, 0), _Tdd(0, 0))
    full, _ = mod._compute_completeness(_Cov(), _Adr(2, 2), _Tdd(1, 1))

    assert empty == full == 100.0, (empty, full)
