"""The calibration starts saying HOW MUCH of the code it would block.

THE DEFECT THIS FIXES
-----------------------
`SKILL.md` promete: "calibrates adaptive thresholds ... from the project's actual
p90 metrics — never generic defaults", e § "Why p90 and not p50 or max?" explica
that the p90 exists so the gate does not start out rejecting the code already
there.

It does, and nobody measured it. Measured 2026-08-26 by running `/quality-init`
against this repository and then passing every file through the generated hook:

    limiares: complexity=10, function_lines=29, nesting=3, params=4, file_lines=367
    result: 156 of 256 versioned files would be BLOCKED (61%)

The arithmetic is simple and the p90 does not cover it: it is computed PER METRIC
— the 90th percentile of the project's functions — while the gate rejects a FILE
when ANY of its functions exceeds ANY threshold. A file with thirty functions has
thirty independent chances of holding one of the worst 10%, and five metrics
multiply that. p90 per function is not p90 per file, and the difference is the
distance between a gate that starts green and one that locks two thirds of the
repository.

A gate that starts red is switched off within the hour, and what remains is the
worse of the two situations: the hook in `settings.json`, the belief that it
protects something, and a bypass flag in the hand of whoever works there.

This does not fix the calibration — it fixes the SILENCE about it. Whoever
switches the gate on now knows what they are switching on.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from init_quality_gates import ThresholdCalibration, measure_blocking_rate

_CLEAN = """def soma(a, b):
    return a + b
"""

#: Violates nesting ONLY — two parameters, short body. Isolating the metric is the
#: point: a fixture violating three thresholds at once cannot prove the rate reacts
#: to the threshold the test is varying.
_COMPLEX = """def decide(a, b):
    if a:
        if b:
            if a > b:
                return 1
    return 0
"""


def _calibration(**over) -> ThresholdCalibration:
    values = {
        "max_complexity": 10,
        "max_function_lines": 29,
        "max_nesting_depth": 3,
        "max_parameters": 4,
        "max_file_lines": 367,
        "duplicate_min_lines": 4,
    }
    values.update(over)
    return ThresholdCalibration(**values)


def test_a_clean_project_reports_zero(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text(_CLEAN, encoding="utf-8")
    (tmp_path / "b.py").write_text(_CLEAN, encoding="utf-8")

    rate = measure_blocking_rate(tmp_path, _calibration())

    assert rate.files_measured == 2
    assert rate.files_blocked == 0
    assert rate.percent == 0.0


def test_a_violating_file_is_counted(tmp_path: Path) -> None:
    (tmp_path / "ok.py").write_text(_CLEAN, encoding="utf-8")
    (tmp_path / "deep.py").write_text(_COMPLEX, encoding="utf-8")

    rate = measure_blocking_rate(tmp_path, _calibration(max_nesting_depth=2))

    assert rate.files_measured == 2
    assert rate.files_blocked == 1
    assert rate.percent == 50.0
    assert "deep.py" in " ".join(rate.worst_offenders)


def test_the_rate_reacts_to_the_thresholds(tmp_path: Path) -> None:
    """The point of the number: it changes when the calibration changes."""
    (tmp_path / "deep.py").write_text(_COMPLEX, encoding="utf-8")

    strict = measure_blocking_rate(tmp_path, _calibration(max_nesting_depth=2))
    lenient = measure_blocking_rate(tmp_path, _calibration(max_nesting_depth=9))

    assert strict.files_blocked == 1
    assert lenient.files_blocked == 0


def test_an_empty_project_is_not_a_perfect_score(tmp_path: Path) -> None:
    """Zero files measured is absence of measurement — the same rule as D4's zero
    denominator and the unreadable coverage report."""
    rate = measure_blocking_rate(tmp_path, _calibration())
    assert rate.files_measured == 0
    assert rate.percent is None
    assert rate.verdict == "NOT_MEASURED"


def test_a_low_rate_is_reported_as_ready(tmp_path: Path) -> None:
    for i in range(20):
        (tmp_path / f"f{i}.py").write_text(_CLEAN, encoding="utf-8")
    assert measure_blocking_rate(tmp_path, _calibration()).verdict == "READY"


def test_a_high_rate_refuses_to_call_the_calibration_ready(tmp_path: Path) -> None:
    """The verdict is what stops the report saying 'calibrated' about a gate that
    rejects most of the code it is supposed to protect."""
    for i in range(10):
        (tmp_path / f"f{i}.py").write_text(_COMPLEX, encoding="utf-8")

    rate = measure_blocking_rate(tmp_path, _calibration(max_nesting_depth=2))

    assert rate.percent == 100.0
    assert rate.verdict == "TOO_STRICT"
    assert "switched off" in rate.advice


def test_test_files_are_excluded_when_asked(tmp_path: Path) -> None:
    """`--skip-tests` already exists in the calibration; the rate measures the same set."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text(_CLEAN, encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text(_COMPLEX, encoding="utf-8")

    rate = measure_blocking_rate(tmp_path, _calibration(max_nesting_depth=2), skip_tests=True)

    assert rate.files_measured == 1
    assert rate.files_blocked == 0
