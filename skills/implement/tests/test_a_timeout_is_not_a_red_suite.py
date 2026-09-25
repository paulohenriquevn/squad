"""A check that ran out of budget did not fail, and it did not pass.

Measured on a consumer 2026-09-24: `npm test` took 657.90s against a hardcoded 600s budget and
exits 0 (`Tests 8421 passed`); `npm run lint` took 197.13s against 180s and exits 0. Both were
rendered `FAIL`, `exit_code: -1` — so that repository could never pass the gate whatever the change
did — while `test_execution` beside them read PASS, "a suite ran", about the same unfinished suite.

`cycle-acceptance.md` already draws the line this gate collapsed: "we could not check" and "we
checked and it is broken" are different facts. A timeout is now its own status, the run's verdict is
`NOT_VALIDATED` (never PASS, never FAIL), and the budgets are read from the project's thresholds file.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from run_validation import check_npm_lint, check_npm_test
from suite_runners import check_test_execution

SCRIPT = Path(__file__).parent.parent / "scripts" / "run_validation.py"


def _fake_npm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> None:
    """An `npm` on PATH whose behaviour the test chooses. `exec` so the timeout kills the sleeper
    itself — a grandchild holding the pipe open would make the test wait out the whole sleep."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    npm = bin_dir / "npm"
    npm.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    npm.chmod(npm.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


def _project(tmp_path: Path, budgets: dict[str, str]) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / ".git").mkdir()
    (root / "package.json").write_text(
        json.dumps({"scripts": {"test": "x", "lint": "x"}}), encoding="utf-8")
    if budgets:
        (root / "rules").mkdir()
        (root / "rules" / "code-quality-thresholds.txt").write_text(
            "".join(f"{key} = {value}\n" for key, value in budgets.items()), encoding="utf-8")
    return root


def test_a_suite_that_outlives_its_budget_is_reported_as_timed_out(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_npm(tmp_path, monkeypatch, "exec sleep 30")
    root = _project(tmp_path, {"validation.timeout_s.npm_test": "1"})

    check = check_npm_test(root)

    assert check["status"] == "TIMEOUT"
    assert check["timeout_s"] == 1
    assert check["budget_source"] == "project"
    assert "validation.timeout_s.npm_test" in check["reason"]


def test_a_red_suite_is_still_a_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The control: a change that renders every non-zero exit as TIMEOUT would pass the test above."""
    _fake_npm(tmp_path, monkeypatch, "echo 'Tests 1 failed' >&2; exit 1")
    root = _project(tmp_path, {})

    assert check_npm_test(root)["status"] == "FAIL"


def test_the_linter_budget_is_the_projects_to_set(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_npm(tmp_path, monkeypatch, "exec sleep 30")
    root = _project(tmp_path, {"validation.timeout_s.npm_lint": "1"})

    check = check_npm_lint(root)

    assert (check["status"], check["timeout_s"]) == ("TIMEOUT", 1)


def test_an_unfinished_suite_is_not_counted_as_a_suite_that_ran(tmp_path: Path) -> None:
    root = _project(tmp_path, {})
    timed_out = {"name": "npm test", "status": "TIMEOUT", "timeout_s": 1}

    check = check_test_execution(root, [timed_out])

    assert check["status"] == "TIMEOUT"
    assert check["suites_executed"] == []
    assert check["suites_timed_out"] == ["npm test"]


def test_a_budget_that_is_not_a_positive_number_is_refused(tmp_path: Path) -> None:
    """A typo in the budget must not silently fall back to the default the author meant to raise."""
    root = _project(tmp_path, {"validation.timeout_s.npm_test": "ten minutes"})

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "s", "--project-root", str(root), "--no-write-report",
         "--no-code-quality"],
        capture_output=True, text=True, check=False)

    assert result.returncode == 2
    assert "validation.timeout_s.npm_test" in result.stderr


def test_a_run_whose_suite_timed_out_is_not_validated(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_npm(tmp_path, monkeypatch, 'case "$1" in test) exec sleep 30;; esac; exit 0')
    root = _project(tmp_path, {"validation.timeout_s.npm_test": "1"})

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "s", "--project-root", str(root), "--no-write-report",
         "--no-code-quality"],
        capture_output=True, text=True, check=False)
    report = json.loads(result.stdout)

    assert report["overall_status"] == "NOT_VALIDATED"
    assert result.returncode == 1  # not a pass: nothing may proceed on an unfinished check
    assert "npm test" in report["timed_out"]
    summary = report["summary"]
    assert summary["timeout"] >= 1
    assert sum(summary[b] for b in ("pass", "fail", "skip", "warn", "partial", "n_a", "timeout")) \
        == summary["total"]
