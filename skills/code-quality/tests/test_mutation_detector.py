"""D4 — mutation testing: do the tests DETECT a defect, or merely pass?

THE DEFECT THIS FIXES
---------------------
`code-quality-golden-rule.md § 5` lists D4 as LOCKED contract — mutmut for
Python, Stryker for TypeScript, floors at 60 and 80. All four detectors returned
the same thing:

    return self.unavailable("d4", "mutation_low", "mutmut integration is not configured")

Because `unavailable()` emits SOFT_CAP, `PASS` was unreachable in any project and
`/implement` converted the soft cap into a WARN. The gate that answers the one
question coverage does not — *do the tests detect a defect?* — was declared,
versioned, documented, and did not run.

THE PROOF THAT THE GATE IS WORTH IT
-----------------------------------
Measured 2026-08-26 with mutmut 3.5 on a 4-line module covered by a tautological
test (`assert isinstance(discount(100, 10), float)`):

    {"killed": 1, "survived": 7, "total": 8, ...}   -> score 12.5%

Line coverage: 100%. It is exactly the test that passes without proving anything,
and no other detector in this pile sees it.

TWO MUTMUT BEHAVIOURS THE DETECTOR CANNOT IGNORE
------------------------------------------------
1. **It exits 0 even when it ran nothing.** With tests outside the layout it
   collects, the output carries `failed to collect stats. runner returned 5` and
   the process ends successfully. A detector reading the exit code would record a
   run that never happened — the same defect the coverage gate had when it turned
   an exit code into a measurement.
2. **It does not even load without `source_paths` configured.** `mutmut --help`
   outside a configured project raises `FileNotFoundError` on import. Missing
   configuration is therefore indistinguishable from a missing tool if the
   detector only looks at the exception — and the two demand different actions
   from whoever reads the report.
"""
from __future__ import annotations

import os
import time
import json
from pathlib import Path

import pytest

from scripts.detectors import _mutation

#: Real output of `mutmut export-cicd-stats`, captured 2026-08-26 (mutmut 3.5).
_STATS_STRONG = {"killed": 3, "survived": 0, "total": 3, "no_tests": 0, "skipped": 0,
                 "suspicious": 0, "timeout": 0, "check_was_interrupted_by_user": 0, "segfault": 0}
_STATS_WEAK = {"killed": 1, "survived": 7, "total": 8, "no_tests": 0, "skipped": 0,
               "suspicious": 0, "timeout": 0, "check_was_interrupted_by_user": 0, "segfault": 0}


def _python_project(root: Path, stats: dict | None) -> Path:
    (root / "calc").mkdir(parents=True, exist_ok=True)
    (root / "calc" / "core.py").write_text("def f(x):\n    return x + 1\n", encoding="utf-8")
    (root / "setup.cfg").write_text("[mutmut]\nsource_paths=calc/\n", encoding="utf-8")
    if stats is not None:
        (root / "mutants").mkdir(exist_ok=True)
        (root / "mutants" / "mutmut-cicd-stats.json").write_text(json.dumps(stats), encoding="utf-8")
    return root


def _runner_ok(*_args, **_kwargs) -> tuple[int, str, str]:
    return 0, "", ""


def _runner_missing(*_args, **_kwargs):
    raise FileNotFoundError("mutmut")


# ---------------------------------------------------------------------------
# Score -> severity
# ---------------------------------------------------------------------------

def test_a_strong_suite_produces_no_capping_finding(tmp_path: Path) -> None:
    _python_project(tmp_path, _STATS_STRONG)
    findings = _mutation.detect_mutation_score("python", tmp_path, runner=_runner_ok)
    assert [f for f in findings if f.severity in ("SOFT_CAP", "SOFT_FLOOR", "HARD")] == []
    info = [f for f in findings if f.severity == "INFO"]
    assert len(info) == 1, "the measured score must appear in the report even when it passes"
    assert "100.0%" in info[0].message


def test_a_tautological_suite_is_capped(tmp_path: Path) -> None:
    """The measured case: 100% line coverage, 12.5% mutation score."""
    _python_project(tmp_path, _STATS_WEAK)
    findings = _mutation.detect_mutation_score("python", tmp_path, runner=_runner_ok)
    caps = [f for f in findings if f.severity == "SOFT_CAP"]
    assert len(caps) == 1
    assert "12.5%" in caps[0].message
    assert caps[0].allowlist_key.endswith("soft_cap_mutation_score_low_python")


def test_a_medium_score_is_a_floor_not_a_cap(tmp_path: Path) -> None:
    _python_project(tmp_path, {**_STATS_STRONG, "killed": 7, "survived": 3, "total": 10})
    findings = _mutation.detect_mutation_score("python", tmp_path, runner=_runner_ok)
    floors = [f for f in findings if f.severity == "SOFT_FLOOR"]
    assert len(floors) == 1
    assert "70.0%" in floors[0].message


def test_a_timeout_counts_as_detected(tmp_path: Path) -> None:
    """A mutant that hangs the test WAS detected — the suite reacted to the mutation."""
    _python_project(tmp_path, {**_STATS_STRONG, "killed": 6, "timeout": 2, "survived": 2, "total": 10})
    findings = _mutation.detect_mutation_score("python", tmp_path, runner=_runner_ok)
    assert "80.0%" in [f.message for f in findings][0]


def test_skipped_mutants_leave_the_denominator(tmp_path: Path) -> None:
    """`skipped` is deliberate exclusion; keeping them in the denominator would punish the decision."""
    _python_project(tmp_path, {**_STATS_STRONG, "killed": 5, "survived": 0, "skipped": 5, "total": 10})
    findings = _mutation.detect_mutation_score("python", tmp_path, runner=_runner_ok)
    assert "100.0%" in [f.message for f in findings][0]


def test_uncovered_mutants_stay_in_the_denominator(tmp_path: Path) -> None:
    """`no_tests` is a mutant no test reaches — undetected, by definition."""
    _python_project(tmp_path, {**_STATS_STRONG, "killed": 5, "survived": 0, "no_tests": 5, "total": 10})
    findings = _mutation.detect_mutation_score("python", tmp_path, runner=_runner_ok)
    caps = [f for f in findings if f.severity == "SOFT_CAP"]
    assert len(caps) == 1
    assert "50.0%" in caps[0].message


# ---------------------------------------------------------------------------
# The failure modes that must not turn green
# ---------------------------------------------------------------------------

def test_zero_mutants_is_never_a_perfect_score(tmp_path: Path) -> None:
    """A zero denominator is absence of measurement, not perfect measurement.

    100% of zero mutants is the worst possible output: absolute green with nothing
    measured.
    """
    _python_project(tmp_path, {**_STATS_STRONG, "killed": 0, "survived": 0, "total": 0})
    findings = _mutation.detect_mutation_score("python", tmp_path, runner=_runner_ok)
    assert len(findings) == 1
    assert findings[0].severity == "SOFT_CAP"
    assert "no mutants" in findings[0].message


def test_a_run_that_produced_no_stats_is_unavailable_not_clean(tmp_path: Path) -> None:
    """Measured: mutmut exits 0 even when pytest collected no test at all.

    Without the stats file there was no measurement — and the detector has to say
    so instead of inheriting the exit code as a verdict.
    """
    _python_project(tmp_path, None)
    findings = _mutation.detect_mutation_score("python", tmp_path, runner=_runner_ok)
    assert len(findings) == 1
    assert findings[0].severity == "SOFT_CAP"
    assert "auditor unavailable" in findings[0].message
    assert "no stats file" in findings[0].message


def test_a_missing_tool_is_reported_as_such(tmp_path: Path) -> None:
    _python_project(tmp_path, None)
    findings = _mutation.detect_mutation_score("python", tmp_path, runner=_runner_missing)
    assert len(findings) == 1
    assert "not found in PATH" in findings[0].message


def test_a_project_without_mutation_config_says_so(tmp_path: Path) -> None:
    """Without `[mutmut] source_paths` the tool does not even load — and the action
    for whoever reads the report is to configure, not to install."""
    (tmp_path / "calc").mkdir()
    (tmp_path / "calc" / "core.py").write_text("def f(x):\n    return x\n", encoding="utf-8")

    findings = _mutation.detect_mutation_score("python", tmp_path, runner=_runner_ok)

    assert len(findings) == 1
    assert findings[0].severity == "SOFT_CAP"
    assert "no mutation config" in findings[0].message
    assert "source_paths" in findings[0].message


def test_a_corrupt_stats_file_is_unavailable_not_zero(tmp_path: Path) -> None:
    _python_project(tmp_path, None)
    (tmp_path / "mutants").mkdir(exist_ok=True)
    (tmp_path / "mutants" / "mutmut-cicd-stats.json").write_text("{not json", encoding="utf-8")

    findings = _mutation.detect_mutation_score("python", tmp_path, runner=_runner_ok)

    assert findings[0].severity == "SOFT_CAP"
    assert "auditor unavailable" in findings[0].message


# ---------------------------------------------------------------------------
# TypeScript — schema mutation-testing-elements (Stryker)
# ---------------------------------------------------------------------------

def _stryker_project(root: Path, statuses: list[str] | None) -> Path:
    (root / "package.json").write_text('{"name": "p"}', encoding="utf-8")
    (root / "stryker.config.json").write_text('{"testRunner": "jest"}', encoding="utf-8")
    if statuses is not None:
        report = (root / "reports" / "mutation")
        report.mkdir(parents=True, exist_ok=True)
        (report / "mutation.json").write_text(json.dumps({
            "files": {"src/a.ts": {"mutants": [{"id": str(i), "status": s}
                                                for i, s in enumerate(statuses)]}}
        }), encoding="utf-8")
    return root


def test_typescript_reads_the_stryker_report(tmp_path: Path) -> None:
    _stryker_project(tmp_path, ["Killed", "Killed", "Survived", "Timeout"])
    findings = _mutation.detect_mutation_score("typescript", tmp_path, runner=_runner_ok)
    assert "75.0%" in [f.message for f in findings][0]


def test_typescript_ignored_mutants_leave_the_denominator(tmp_path: Path) -> None:
    _stryker_project(tmp_path, ["Killed", "Ignored", "CompileError"])
    findings = _mutation.detect_mutation_score("typescript", tmp_path, runner=_runner_ok)
    assert "100.0%" in [f.message for f in findings][0]


def test_typescript_without_stryker_config_says_so(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"name": "p"}', encoding="utf-8")
    findings = _mutation.detect_mutation_score("typescript", tmp_path, runner=_runner_ok)
    assert "no mutation config" in findings[0].message


# ---------------------------------------------------------------------------
# Contrato
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("language", ["rust", "go"])
def test_deferred_languages_declare_the_deferral(tmp_path: Path, language: str) -> None:
    """The golden rule § 5 declares Rust and Go deferred. Deferred and declared is
    honest; deferred and presented as implemented is the defect this module closes."""
    findings = _mutation.detect_mutation_score(language, tmp_path, runner=_runner_ok)
    assert len(findings) == 1
    assert findings[0].severity == "SOFT_CAP"
    assert "deferred" in findings[0].message


def test_floors_come_from_the_caller_not_from_a_constant(tmp_path: Path) -> None:
    """`code-quality-thresholds.txt` documents `mutation.score_floor_low/high`.
    A hard-coded floor would make that file lie about being configurable."""
    _python_project(tmp_path, {**_STATS_STRONG, "killed": 7, "survived": 3, "total": 10})

    strict = _mutation.detect_mutation_score(
        "python", tmp_path, floor_low=75, floor_high=95, runner=_runner_ok)
    lenient = _mutation.detect_mutation_score(
        "python", tmp_path, floor_low=50, floor_high=60, runner=_runner_ok)

    assert [f.severity for f in strict] == ["SOFT_CAP"], "70% below a floor of 75 is a cap"
    assert [f.severity for f in lenient] == ["INFO"], "70% above a floor of 60 passes"


def test_findings_carry_a_wellformed_allowlist_key(tmp_path: Path) -> None:
    _python_project(tmp_path, _STATS_WEAK)
    for finding in _mutation.detect_mutation_score("python", tmp_path, runner=_runner_ok):
        assert finding.allowlist_key.count("|") == 3, finding.allowlist_key


# ---------------------------------------------------------------------------
# B-012 — a 22-minute gate is a gate people bypass
# ---------------------------------------------------------------------------
#
# Measured in `theokit-skills` on 2026-08-27: `npx stryker run` took 1347s, and
# `run_structural.py` calls /code-quality internally, so EVERY /plan-confidence in
# that repository cost 22.5 minutes. The detector re-ran the tool on every
# invocation and read no existing report — mutation testing is a periodic deep
# check, and D4 was treating it as a per-invocation gate.


def _stryker_report(tmp_path, killed=9, survived=1):
    cfg = tmp_path / "stryker.config.json"
    cfg.write_text("{}", encoding="utf-8")
    report = tmp_path / "reports" / "mutation" / "mutation.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    mutants = [{"status": "Killed"}] * killed + [{"status": "Survived"}] * survived
    report.write_text(json.dumps({"files": {"a.ts": {"mutants": mutants}}}), encoding="utf-8")
    return report


def test_a_fresh_report_is_reused_instead_of_rerunning_the_tool(tmp_path):
    _stryker_report(tmp_path)
    calls = []

    def runner(cmd, cwd, timeout):
        calls.append(cmd)
        return (0, "", "")

    findings = _mutation.detect_mutation_score(
        "typescript", tmp_path, runner=runner, max_report_age_minutes=1440)

    assert calls == [], f"a fresh report must not trigger a re-run, ran: {calls}"
    assert findings[0].message.startswith("mutation score 90.0%")


def test_reusing_a_report_states_its_age_rather_than_hiding_it(tmp_path):
    # The DoD's second bullet: reading a cached score without knowing its age is
    # exactly the drift this kit fights elsewhere. The number alone is a claim
    # about NOW; the number plus its age is a claim about when it was true.
    _stryker_report(tmp_path)
    findings = _mutation.detect_mutation_score(
        "typescript", tmp_path, runner=lambda *a, **k: (0, "", ""),
        max_report_age_minutes=1440)

    assert "read from a report" in findings[0].message
    assert "old" in findings[0].message


def test_a_stale_report_is_re_measured(tmp_path):
    report = _stryker_report(tmp_path)
    old = time.time() - 60 * 60 * 48
    os.utime(report, (old, old))
    calls = []

    def runner(cmd, cwd, timeout):
        calls.append(cmd)
        return (0, "", "")

    _mutation.detect_mutation_score(
        "typescript", tmp_path, runner=runner, max_report_age_minutes=1440)

    assert calls, "a report older than the window must be re-measured, not trusted"


def test_a_report_older_than_the_sources_it_grades_says_so(tmp_path):
    # Age alone is not freshness. A report can be four minutes old and already
    # describe a tree two commits behind. The window bounds how stale it gets;
    # this sentence is what stops it looking current.
    _stryker_report(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    (src / "later.ts").write_text("export const x = 1;\n", encoding="utf-8")

    findings = _mutation.detect_mutation_score(
        "typescript", tmp_path, runner=lambda *a, **k: (0, "", ""),
        max_report_age_minutes=1440)

    assert "changed since" in findings[0].message


def test_no_report_still_runs_the_tool(tmp_path):
    (tmp_path / "stryker.config.json").write_text("{}", encoding="utf-8")
    calls = []

    def runner(cmd, cwd, timeout):
        calls.append(cmd)
        return (0, "", "")

    _mutation.detect_mutation_score("typescript", tmp_path, runner=runner)

    assert calls, "with no report at all there is nothing to reuse — measure"
