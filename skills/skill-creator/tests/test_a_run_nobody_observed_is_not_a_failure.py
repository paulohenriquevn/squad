"""The loop recombined a distinction `run_eval` had gone out of its way to make.

`summarise_runs` emits verdict NOT_OBSERVED with `pass=None` and a separate
`not_observed` count, on the stated grounds that "3/5 with two timeouts and 3/5 with two
real misses are different facts". `run_loop` then computed `failed = total - passed`,
so every `None` landed in the failure column — and the loop's summary, its report and
its stopping decision all read a timeout as a miss.

The direction matters: it reports the skill as WORSE than measured, so the loop keeps
rewriting a description that was never shown to be wrong.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "skills" / "skill-creator"))

from scripts.run_loop import _summarise  # noqa: E402 — post-bootstrap import


def _results(*outcomes: bool | None) -> list[dict]:
    return [{"query": f"q{i}", "pass": outcome} for i, outcome in enumerate(outcomes)]


def test_an_unobserved_run_is_counted_on_its_own() -> None:
    summary = _summarise(_results(True, True, True, None, None))

    assert summary["passed"] == 3
    assert summary["failed"] == 0, "two timeouts were counted as two misses"
    assert summary["not_observed"] == 2
    assert summary["total"] == 5


def test_real_misses_are_still_failures() -> None:
    summary = _summarise(_results(True, True, True, False, False))

    assert summary == {"passed": 3, "failed": 2, "not_observed": 0,
                       "total": 5, "observed": 5}


def test_the_two_cases_are_distinguishable() -> None:
    """The whole point: 3/5 with timeouts and 3/5 with misses are different facts."""
    timeouts = _summarise(_results(True, True, True, None, None))
    misses = _summarise(_results(True, True, True, False, False))

    assert timeouts != misses
    assert timeouts["observed"] == 3 and misses["observed"] == 5


def test_an_empty_run_is_all_zeroes() -> None:
    assert _summarise([]) == {"passed": 0, "failed": 0, "not_observed": 0,
                              "total": 0, "observed": 0}
