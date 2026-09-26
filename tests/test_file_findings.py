"""The audit finds defects and nothing turns them into work.

`kit_audit_workflow.js` hunts the kit for the patterns it has shipped more than
once and puts every claim through an agent whose job is to refute it. What
survives is returned — and returned to nobody. Measured 2026-09-03: the kit's
tracker held zero open issues while four real defects sat in a session report,
and the fleet had nothing to do because of it. A finding mentioned and not filed
is the worst outcome: it reads as coverage and is never worked.

This is the step between. What it refuses matters more than what it files.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_FLEET = Path(__file__).resolve().parents[1] / "mechanisms" / "fleet"
if str(_FLEET) not in sys.path:
    sys.path.insert(0, str(_FLEET))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
import file_findings  # noqa: E402 — post-bootstrap import


def _finding(**over: object) -> dict:
    base = {"title": "check_x reports an absence as an answer",
            "file": "mechanisms/gates/check_x.py", "line": 42,
            "evidence": "run against an empty tree it prints `Overall: PASS`",
            "why_it_matters": "a clean report over an empty sweep",
            "lens": "absence-as-answer", "verdict": {"refuted": False}}
    base.update(over)
    return base


# ── what it refuses to file ───────────────────────────────────────────────────


def test_a_refuted_finding_is_never_filed() -> None:
    kept, skipped = file_findings.triage([_finding(verdict={"refuted": True})], existing=[])
    assert kept == []
    assert "refuted" in skipped[0][1]


def test_a_finding_with_no_evidence_is_never_filed() -> None:
    """An issue without a repro or a measurement spends a maintainer's attention
    and teaches them to skim the next one."""
    kept, skipped = file_findings.triage([_finding(evidence="")], existing=[])
    assert kept == []
    assert "evidence" in skipped[0][1]


def test_a_finding_naming_no_file_is_never_filed() -> None:
    kept, skipped = file_findings.triage([_finding(file="")], existing=[])
    assert kept == []


def test_a_finding_already_tracked_is_not_filed_twice() -> None:
    existing = [{"number": 7, "title": "check_x reports an absence as an answer",
                 "body": "", "state": "OPEN"}]
    kept, skipped = file_findings.triage([_finding()], existing=existing)
    assert kept == []
    assert "#7" in skipped[0][1]


def test_a_finding_matching_a_closed_issue_is_not_refiled() -> None:
    """A closed issue is a decision somebody made. Re-filing it silently reopens
    an argument that was already had."""
    existing = [{"number": 7, "title": "check_x reports an absence as an answer",
                 "body": "", "state": "CLOSED"}]
    kept, _ = file_findings.triage([_finding()], existing=existing)
    assert kept == []


def test_the_same_file_and_line_counts_as_a_duplicate_even_if_worded_differently() -> None:
    existing = [{"number": 9, "title": "something else entirely", "state": "OPEN",
                 "body": "the defect is at `mechanisms/gates/check_x.py:42` and ..."}]
    kept, skipped = file_findings.triage([_finding()], existing=existing)
    assert kept == []
    assert "#9" in skipped[0][1]


def test_a_genuinely_new_finding_is_kept() -> None:
    existing = [{"number": 7, "title": "an unrelated defect", "body": "", "state": "OPEN"}]
    kept, _ = file_findings.triage([_finding()], existing=existing)
    assert [f["title"] for f in kept] == ["check_x reports an absence as an answer"]


# ── absence is never a measurement ────────────────────────────────────────────


def test_an_unreadable_tracker_files_nothing_at_all(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the existing issues there is no dedup, and filing without dedup
    turns one real defect into a duplicate every time the audit runs."""
    def boom(_repo: str, **_kw: object) -> list[dict]:
        raise file_findings.TrackerUnavailable("`gh` is not installed")
    monkeypatch.setattr(file_findings, "existing_issues", boom)
    filed, notes, code = file_findings.run([_finding()], repo="o/r", apply=False)
    assert filed == []
    assert code != 0
    assert any("not installed" in n for n in notes)
    assert not any("no known defects" in n.lower() for n in notes)


# ── the body it writes ────────────────────────────────────────────────────────


def test_the_body_carries_the_evidence_and_the_lens() -> None:
    body = file_findings.body(_finding(), repo_hint="the kit")
    assert "mechanisms/gates/check_x.py:42" in body
    assert "Overall: PASS" in body
    assert "absence-as-answer" in body


def test_the_body_says_the_finding_survived_refutation() -> None:
    body = file_findings.body(_finding(), repo_hint="the kit")
    assert "refut" in body.lower(), (
        "a reader needs to know an agent tried to kill this and could not")


def test_a_duplicate_check_that_could_not_run_blocks_the_comment(monkeypatch) -> None:
    """The guard failed OPEN while its comment claimed it failed closed.

    `already_commented` returned `False` when `gh` was missing or the call raised —
    justified inline as "don't spam on error" — and False is exactly the value that lets
    the comment through. The one thing between a re-detected finding and a comment on
    every single run stopped standing there precisely when the tracker was unreachable.
    """
    import file_findings as ff

    monkeypatch.setattr(ff, "already_commented", lambda *_a, **_k: None)

    posted, why = ff.comment_duplicate("owner/name", 7, "a.py:1", apply=True)

    assert posted is False, "a comment was posted on the strength of a check that did not run"
    assert "could not ask" in why


def test_an_issue_that_already_carries_the_comment_is_still_suppressed(monkeypatch) -> None:
    import file_findings as ff

    monkeypatch.setattr(ff, "already_commented", lambda *_a, **_k: True)

    posted, why = ff.comment_duplicate("owner/name", 7, "a.py:1", apply=True)

    assert posted is True
    assert "already commented" in why
