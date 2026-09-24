"""A run that was killed must not be recorded, or read, as a suite that failed.

Measured 2026-09-24 on this tree. A full-suite run was killed externally, and the
record it left was:

    {"suites":31,"failed_suites":31,"passed":0,"failed":0,"tree_moved":false}

Every suite counted as a failure because its pytest was terminated, and not one test
ran. `check_verification_freshness` reads that and reports `failing` with the detail
"0 test(s) in 31 suite(s) failed on the last run" — a sentence that contradicts
itself and reads, to anyone who does not stop on the zero, as total breakage.

The three states are different facts and only one of them is about the code:

    failing       tests ran and some did not pass
    interrupted   nothing ran; the run was stopped
    verified      tests ran and all passed

`unattributable` already exists for a run whose tree moved, on exactly this
argument: a result about no single state of the repository is not a verdict. An
interrupted run is the same kind of non-verdict, and it was wearing the vocabulary
of the one state a reader must act on.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "mechanisms" / "gates"))
sys.path.insert(0, str(_ROOT / "mechanisms" / "conventions"))

from check_verification_freshness import check, record_path  # noqa: E402


def _tree(tmp_path: Path, record: dict) -> Path:
    path = record_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record), encoding="utf-8")
    return tmp_path


def _killed(head: str = "") -> dict:
    return {"at": "2026-09-24T08:59:21Z", "head": head, "suites": 31,
            "failed_suites": 31, "passed": 0, "failed": 0, "tree_moved": False}


def test_a_killed_run_is_not_reported_as_failing(tmp_path: Path) -> None:
    code, report = check(_tree(tmp_path, _killed()))
    assert report["state"] == "interrupted", report
    assert code != 0, "an interrupted run is not a pass either"
    assert "0 test(s)" not in report["detail"], (
        "the detail still counts failures that did not happen: " + report["detail"])


def test_a_genuinely_failing_run_keeps_its_verdict(tmp_path: Path) -> None:
    """The discrimination that matters: real failures must still read as failures."""
    rec = {"at": "x", "head": "", "suites": 31, "failed_suites": 1,
           "passed": 6000, "failed": 43, "tree_moved": False}
    code, report = check(_tree(tmp_path, rec))
    assert report["state"] == "failing", report
    assert code == 1


def test_a_clean_run_still_verifies(tmp_path: Path) -> None:
    rec = {"at": "x", "head": "", "suites": 31, "failed_suites": 0,
           "passed": 6119, "failed": 0, "tree_moved": False}
    code, report = check(_tree(tmp_path, rec))
    assert report["state"] == "verified", report
    assert code == 0


def test_a_run_where_some_suites_died_is_interrupted_not_failing(tmp_path: Path) -> None:
    """Partial kill: some tests ran, some suites never reported. Still not a verdict.

    Reading this as `failing` would name the code for a stop that had nothing to do
    with it; reading it as `verified` would hide that most of the suite never ran.
    """
    rec = {"at": "x", "head": "", "suites": 31, "failed_suites": 20,
           "passed": 400, "failed": 0, "tree_moved": False}
    code, report = check(_tree(tmp_path, rec))
    assert report["state"] == "interrupted", report
    assert code != 0
