"""Tests for check_progress_schema — fail-fast validation of the checkpoint."""
from __future__ import annotations

import json
from pathlib import Path

from check_progress_schema import check_progress_schema, validate_progress


def _write(tmp_path: Path, data) -> Path:
    p = tmp_path / ".progress-foo.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_valid_checkpoint_passes(tmp_path: Path) -> None:
    p = _write(tmp_path, {
        "slug": "foo",
        "tasks": [
            {"id": "T1.1", "phase": "1", "status": "committed",
             "files": ["src/foo.py"], "commit_sha": "abc123",
             "wiring": {"a": "pass", "b": "pass", "c": "n/a"}},
        ],
    })
    report = check_progress_schema(p)
    assert report.status == "PASS"
    assert report.task_count == 1


def test_missing_file_is_skip(tmp_path: Path) -> None:
    report = check_progress_schema(tmp_path / "nope.json")
    assert report.status == "SKIP"
    assert report.exists is False


def test_malformed_json_is_blocker(tmp_path: Path) -> None:
    p = tmp_path / ".progress-foo.json"
    p.write_text("{ not json", encoding="utf-8")
    report = check_progress_schema(p)
    assert report.status == "FAIL"
    assert "progress_malformed_json" in [f.code for f in report.findings]


def test_bare_object_without_tasks_envelope_fails(tmp_path: Path) -> None:
    """GAP found in review: the prompt example wrote a bare task object; gates read
    data['tasks']. A bare object has no consumable tasks."""
    p = _write(tmp_path, {"task_id": "T1.1", "status": "committed"})
    report = check_progress_schema(p)
    assert report.status == "FAIL"
    assert "progress_missing_tasks" in [f.code for f in report.findings]


def test_task_id_key_instead_of_id_is_flagged(tmp_path: Path) -> None:
    p = _write(tmp_path, {"tasks": [{"task_id": "T1.1", "phase": "1", "status": "committed"}]})
    findings = validate_progress(json.loads(p.read_text()))
    codes = [f.code for f in findings]
    assert "task_uses_task_id_key" in codes


def test_task_missing_phase_is_flagged(tmp_path: Path) -> None:
    p = _write(tmp_path, {"tasks": [{"id": "T1.1", "status": "committed"}]})
    findings = validate_progress(json.loads(p.read_text()))
    assert "task_missing_phase" in [f.code for f in findings]


def test_invalid_status_is_flagged(tmp_path: Path) -> None:
    findings = validate_progress({"tasks": [{"id": "T1.1", "phase": "1", "status": "donezo"}]})
    assert "task_invalid_status" in [f.code for f in findings]


def test_committed_without_sha_is_flagged(tmp_path: Path) -> None:
    findings = validate_progress({"tasks": [{"id": "T1.1", "phase": "1", "status": "committed"}]})
    assert "committed_without_sha" in [f.code for f in findings]


def test_blocked_without_reason_is_flagged(tmp_path: Path) -> None:
    findings = validate_progress({"tasks": [{"id": "T1.1", "phase": "1", "status": "blocked"}]})
    assert "blocked_without_reason" in [f.code for f in findings]


def test_tasks_not_a_list_fails(tmp_path: Path) -> None:
    findings = validate_progress({"tasks": {"id": "T1.1"}})
    assert "tasks_not_array" in [f.code for f in findings]


# ---------------------------------------------------------------------------
# `done` — a status the schema accepted and no consumer recognised
#
# Measured 2026-09-08 while reviewing the loop's own documentation. `done` was in
# `_VALID_STATUSES`, so a checkpoint carrying it validated clean. But the loop's exit
# condition is `committed` OR `blocked`, and `check_phase_completeness.py` computes
# pendency exactly that way:
#
#     pending = [t for t in tasks if t.get("status") not in ("committed", "blocked")]
#
# So a task marked `done` counted as PENDING forever, the completion promise was never
# emitted, and the loop ran until the no-observable-progress brake or a cancellation —
# with a diagnostic that pointed nowhere near the cause.
#
# Of the six consumers, the only occurrence of the word in any of them was inside a
# COMMENT. And `done` is the most natural word an agent would reach for to say
# "finished", which is what made the trap cheap to fall into and expensive to see.
#
# Accepted-then-ignored is the exact defect this validator was written to end — it
# already does it for three other fields. This closes the fourth.
# ---------------------------------------------------------------------------

def test_done_is_refused_with_a_message_that_names_the_replacement(tmp_path: Path) -> None:
    p = _write(tmp_path, {"tasks": [{"id": "T1.1", "phase": "1", "status": "done"}]})

    report = check_progress_schema(p)

    assert report.status == "FAIL"
    codes = [f.code for f in report.findings]
    assert "task_status_done" in codes, codes

    finding = next(f for f in report.findings if f.code == "task_status_done")
    # The message has to say what to write instead. "not one of [...]" would send the
    # reader to the list, and the list is not where the answer is.
    assert "committed" in finding.message
    assert "blocked" in finding.message


def test_the_two_terminal_statuses_still_pass(tmp_path: Path) -> None:
    """The correction must not make the working states harder to express."""
    p = _write(tmp_path, {"tasks": [
        {"id": "T1", "phase": "1", "status": "committed", "commit_sha": "abc123"},
        {"id": "T2", "phase": "1", "status": "blocked", "blocked_reason": "no credential"},
    ]})

    assert check_progress_schema(p).status == "PASS"


def test_every_valid_status_is_reachable_by_a_consumer() -> None:
    """The property whose absence produced the trap.

    A status the schema accepts and nothing consumes is a value that behaves like a
    decision and is not one. This pins the set to what the loop can actually act on:
    five in-flight states, and two terminal ones.
    """
    from check_progress_schema import _VALID_STATUSES

    assert "done" not in _VALID_STATUSES
    assert _VALID_STATUSES == {
        "pending", "red", "green", "refactor", "wired",   # in flight
        "committed", "blocked",                           # terminal
    }
