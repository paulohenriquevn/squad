"""Tests for check_diff_cohesion."""
from __future__ import annotations

import json
from pathlib import Path

from check_diff_cohesion import check_diff_cohesion


def _write_progress(tmp_path: Path, tasks: list[dict]) -> Path:
    p = tmp_path / ".progress-foo.json"
    p.write_text(json.dumps({"slug": "foo", "tasks": tasks}), encoding="utf-8")
    return p


def _write_plan(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "foo-plan.md"
    p.write_text(body, encoding="utf-8")
    return p


def test_no_drift_when_modified_matches_declared(tmp_path: Path) -> None:
    plan_body = (
        "## Phase 1\n"
        "### T1.1 — Foo\n"
        "#### Files to edit\n- src/foo.py\n- src/foo_test.py\n"
        "#### TDD\nRED: test_foo\n"
    )
    progress = _write_progress(tmp_path, [
        {"id": "T1.1", "phase": "1", "status": "committed",
         "files": ["src/foo.py", "src/foo_test.py"]},
    ])
    plan = _write_plan(tmp_path, plan_body)
    report = check_diff_cohesion(plan, progress, "1")
    assert report.drift_files == ()
    assert report.has_high_or_blocker is False
    assert report.diff_source == "progress"


def test_drift_detected_when_extra_file_modified(tmp_path: Path) -> None:
    plan_body = (
        "## Phase 1\n"
        "### T1.1 — Foo\n"
        "#### Files to edit\n- src/foo.py\n"
    )
    progress = _write_progress(tmp_path, [
        {"id": "T1.1", "phase": "1", "status": "committed",
         "files": ["src/foo.py", "src/unauthorized.py"]},
    ])
    plan = _write_plan(tmp_path, plan_body)
    report = check_diff_cohesion(plan, progress, "1")
    assert "src/unauthorized.py" in report.drift_files
    assert report.has_high_or_blocker is True
    codes = [f.code for f in report.findings if f.severity == "HIGH"]
    assert "scope_drift" in codes


def test_non_source_files_not_flagged_as_drift(tmp_path: Path) -> None:
    """CHANGELOG.md, package.json etc are allowed even if not declared."""
    plan_body = (
        "## Phase 1\n"
        "### T1.1 — Foo\n"
        "#### Files to edit\n- src/foo.py\n"
    )
    progress = _write_progress(tmp_path, [
        {"id": "T1.1", "phase": "1", "status": "committed",
         "files": ["src/foo.py", "CHANGELOG.md", "package.json"]},
    ])
    plan = _write_plan(tmp_path, plan_body)
    report = check_diff_cohesion(plan, progress, "1")
    assert report.drift_files == ()
    assert report.has_high_or_blocker is False


def test_no_declared_scope_blocks_when_files_were_modified(tmp_path: Path) -> None:
    """B-038 — this test previously asserted the DEFECT, and the change is deliberate.

    It read `assert "no_declared_scope" in medium_codes` and `# MEDIUM should not block`, pinning
    the behaviour the item was filed against: a phase declaring nothing and modifying `src/foo.py`
    got the same verdict a fully-declared phase gets.

    Rewriting a failing test is normally the forbidden fix (`cycle-implement.md`). It is the correct
    one here for one reason: the assertion WAS the defect under repair, not evidence of it. The
    behaviour it pinned is the one B-038's DoD says must change, and leaving it would mean the gate
    could never be fixed without "weakening a test".

    The MEDIUM case is not lost — it moved to
    `test_an_undeclared_phase_that_changed_nothing_stays_medium`, where it belongs.
    """
    plan_body = "## Phase 1\n### T1.1 — Foo\n#### TDD\nRED\n"  # no Files to edit
    progress = _write_progress(tmp_path, [
        {"id": "T1.1", "phase": "1", "status": "committed", "files": ["src/foo.py"]},
    ])
    plan = _write_plan(tmp_path, plan_body)
    report = check_diff_cohesion(plan, progress, "1")
    finding = next(f for f in report.findings if f.code == "no_declared_scope")
    assert finding.severity == "HIGH"
    assert report.has_high_or_blocker is True


def test_no_diff_source_when_progress_empty(tmp_path: Path) -> None:
    plan_body = "## Phase 1\n### T1.1 — Foo\n#### Files to edit\n- src/foo.py\n"
    # Task without 'files' field at all
    progress = _write_progress(tmp_path, [
        {"id": "T1.1", "phase": "1", "status": "committed"},
    ])
    plan = _write_plan(tmp_path, plan_body)
    report = check_diff_cohesion(plan, progress, "1")
    medium_codes = [f.code for f in report.findings if f.severity == "MEDIUM"]
    assert "no_diff_source" in medium_codes
    assert report.diff_source == "none"


def test_cross_layer_check_skipped_always(tmp_path: Path) -> None:
    """Cross-layer detector is a future feature — must always record INFO skip."""
    plan_body = "## Phase 1\n### T1.1 — Foo\n#### Files to edit\n- src/foo.py\n"
    progress = _write_progress(tmp_path, [
        {"id": "T1.1", "phase": "1", "status": "committed", "files": ["src/foo.py"]},
    ])
    plan = _write_plan(tmp_path, plan_body)
    report = check_diff_cohesion(plan, progress, "1")
    info_codes = [f.code for f in report.findings if f.severity == "INFO"]
    assert "cross_layer_check_skipped" in info_codes
    assert report.cross_layer_checked is False


# B-038 — a phase that declared NOTHING got the verdict a fully-declared phase gets.
#
# Measured on the b033 phase-2 mini review of 2026-08-18: declared_files 0, modified_files 14,
# drift_files 0, verdict PHASE_REVIEW_PASS. Meanwhile the same check flagged four files on b025
# phase 1, one on phase 3, two on b020 and one on b034 — each correctly, each needing a fix.
#
# So declaring some files bought scrutiny and declaring none bought a pass. That is not a coverage
# gap, it is an incentive pointing the wrong way.
#
# "Cannot compare" is not "compared, and fine" — the same distinction cycle-acceptance draws between
# NOT_VALIDATED and ACCEPTED, and coverage_gate.py between WARN and PASS.


def test_an_undeclared_phase_that_changed_files_is_high(tmp_path: Path) -> None:
    plan_body = (
        "## Phase 1\n"
        "### T1.1 — Foo\n"
        "#### TDD\nRED: test_foo\n"
    )
    progress = _write_progress(tmp_path, [
        {"id": "T1.1", "phase": "1", "status": "committed",
         "files": [f"src/file{i}.py" for i in range(14)]},
    ])
    plan = _write_plan(tmp_path, plan_body)

    report = check_diff_cohesion(plan, progress, "1")

    assert report.has_high_or_blocker is True
    finding = next(f for f in report.findings if f.code == "no_declared_scope")
    assert finding.severity == "HIGH"


def test_an_undeclared_phase_that_changed_nothing_stays_medium(tmp_path: Path) -> None:
    # A documentation phase, or an empty one. There is nothing that could have drifted, and failing
    # it would teach people to declare a file they did not touch — the workaround that kills gates.
    plan_body = (
        "## Phase 1\n"
        "### T1.1 — Foo\n"
        "#### TDD\nRED: test_foo\n"
    )
    progress = _write_progress(tmp_path, [
        {"id": "T1.1", "phase": "1", "status": "committed", "files": []},
    ])
    plan = _write_plan(tmp_path, plan_body)

    report = check_diff_cohesion(plan, progress, "1")

    finding = next(f for f in report.findings if f.code == "no_declared_scope")
    assert finding.severity == "MEDIUM"
    assert report.has_high_or_blocker is False


def test_the_message_names_the_files_it_could_not_check(tmp_path: Path) -> None:
    # "scope-drift detection skipped" tells the reader a check did not run and nothing about what to
    # do. Naming the files makes the fix mechanical: declare them, or say why they are out of scope.
    plan_body = "## Phase 1\n### T1.1 — Foo\n#### TDD\nRED: test_foo\n"
    progress = _write_progress(tmp_path, [
        {"id": "T1.1", "phase": "1", "status": "committed",
         "files": [f"src/file{i}.py" for i in range(14)]},
    ])
    plan = _write_plan(tmp_path, plan_body)

    report = check_diff_cohesion(plan, progress, "1")

    message = next(f for f in report.findings if f.code == "no_declared_scope").message
    assert "src/file0.py" in message
    # Capped, matching `scope_drift`'s existing sample size — a 40-file phase must not bury the
    # sentence that matters.
    assert message.count("src/file") <= 5
