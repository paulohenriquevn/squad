"""The 'seen again' comment was written, tested for existence, and never sent.

`comment_duplicate()` and `already_commented()` implement a complete behaviour — post
a FINDING_DUPLICATE_V1 note on the issue that already tracks the pattern, with an
anti-spam guard that fails closed when the tracker cannot be asked. Nothing called
either one. `triage()` recorded the duplicate as a skip note and dropped the issue
number, so `run()` knew a duplicate existed and could do nothing with it.

The old test file asserted `hasattr(file_findings, "comment_duplicate")` and five
bodies that were `pass`. An existence check is satisfied by a function nothing calls —
which is exactly the state it was passing in.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "mechanisms" / "fleet"))

import file_findings  # noqa: E402 — post-bootstrap import


def _finding(**over: object) -> dict:
    base = {"title": "a thing is wrong", "file": "a.py", "line": 42,
            "evidence": "measured: 3 of 7", "why": "because"}
    base.update(over)
    return base


def test_a_duplicate_carries_the_issue_it_duplicates() -> None:
    existing = [{"number": 77, "title": "unrelated", "body": "cites a.py:42", "state": "open"}]

    _, skipped = file_findings.triage([_finding()], existing=existing)

    assert len(skipped) == 1
    assert skipped[0].related_issue == 77
    assert skipped[0].related_state == "open"


def test_a_skip_that_is_not_a_duplicate_names_no_issue() -> None:
    _, skipped = file_findings.triage([_finding(evidence="")], existing=[])

    assert skipped[0].related_issue is None, "there is no issue to comment on"


def test_a_closed_issue_is_still_the_issue_it_duplicates() -> None:
    existing = [{"number": 9, "title": "a thing is wrong", "body": "", "state": "CLOSED"}]

    _, skipped = file_findings.triage([_finding()], existing=existing)

    assert skipped[0].related_issue == 9
    assert skipped[0].related_state == "closed"


def test_the_duplicate_path_actually_comments(monkeypatch) -> None:
    """The behaviour the whole pair exists for, and the one nothing exercised."""
    calls: list[tuple] = []

    def _fake(repo: str, issue_number: int, anchor: str, *, apply: bool = True,
              timeout: int = 60) -> tuple[bool, str]:
        calls.append((repo, issue_number, anchor, apply))
        return True, f"commented on #{issue_number}"

    monkeypatch.setattr(file_findings, "comment_duplicate", _fake)
    monkeypatch.setattr(file_findings, "existing_issues", lambda repo: [
        {"number": 77, "title": "unrelated", "body": "cites a.py:42", "state": "open"}])

    _, notes, code = file_findings.run([_finding()], repo="o/n", apply=True)

    assert code == 0
    assert calls == [("o/n", 77, "a.py:42", True)], calls
    assert "commented on #77" in notes[0]


def test_nothing_is_commented_for_a_finding_that_is_not_a_duplicate(monkeypatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(file_findings, "comment_duplicate",
                        lambda *a, **k: (calls.append(a), (True, ""))[1])
    monkeypatch.setattr(file_findings, "existing_issues", lambda repo: [])
    monkeypatch.setattr(file_findings, "file_one", lambda f, **k: (True, "filed #1"))

    file_findings.run([_finding()], repo="o/n", apply=True)

    assert calls == []
