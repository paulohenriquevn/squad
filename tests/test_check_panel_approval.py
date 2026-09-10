"""Nothing advances out of DISCOVER or PLAN that the panel did not carry.

The load-bearing test in this file is `test_a_missing_record_is_not_an_approval`.
Everything else guards a way the check could be true and useless.

For a day, `rules/cycle-discover.md` said the phase advanced on 2 of 3 signed
approvals while nothing convened a panel (issue #65): the rule, the tally, the intake
premise and 377 lines of tests all existed, and every document passed a gate nobody
ran. A phase that never convened its panel must not be indistinguishable from one
whose reviewers all approved — that is this repository's governing sentence turned on
its own governance.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mechanisms" / "gates"))

from check_panel_approval import (
    APPROVED,
    DID_NOT_CONVENE,
    NOT_APPROVED,
    UNCHECKED,
    check,
)

ROSTER = """
reviewer = discover | nemesis | claude-opus-5   | builtin
reviewer = discover | leo     | claude-sonnet-5 | builtin
reviewer = discover | judge   | gpt-5-codex     | codex
panel_phases = discover
"""

PANEL = ["nemesis", "leo", "judge"]

#: Long enough to clear MIN_REASON_WORDS. A verdict with no reasoning is a tick, and
#: a tick is what a panel exists to be more than.
WHY = ("checked every code pointer in corner one against the tree at the cited "
       "revision and the failing test reproduces exactly as claimed")


def _roster(tmp_path: Path) -> Path:
    p = tmp_path / "review-panel.txt"
    p.write_text(ROSTER, encoding="utf-8")
    return p


def _vote(reviewer: str, model: str, verdict: str, reason: str = WHY) -> dict:
    return {"reviewer": reviewer, "model": model, "verdict": verdict, "reason": reason}


def _project(tmp_path: Path, *, votes=None, assigned=PANEL, slug="B-014") -> Path:
    root = tmp_path / "proj"
    panels = root / ".squad" / "records" / "panels"
    panels.mkdir(parents=True, exist_ok=True)
    if assigned is not None:
        (panels / f"{slug}-discover.assignment.json").write_text(
            json.dumps({"assigned": assigned}), encoding="utf-8")
    if votes is not None:
        (panels / f"{slug}-discover.json").write_text(json.dumps({
            "slug": slug, "phase": "discover", "artifact": "opportunity.md",
            "author": "daedalus-tech-lead", "votes": votes}), encoding="utf-8")
    return root


def _check(tmp_path: Path, **kw):
    slug = kw.pop("slug", "B-014")
    return check(slug, kw.pop("phase", "discover"),
                 project=_project(tmp_path, slug=slug, **kw),
                 panel_path=_roster(tmp_path))


def test_a_missing_record_is_not_an_approval(tmp_path: Path) -> None:
    """The one that matters.

    Absence of evidence read as approval is the exact failure this kit exists to
    refuse. A phase that skipped its panel and one whose panel approved must not
    produce the same exit code.
    """
    code, result = _check(tmp_path, votes=None)

    assert code == NOT_APPROVED
    assert result["status"] == "no_record"
    assert "NOT an approval" in result["detail"]


def test_a_majority_carries_the_document(tmp_path: Path) -> None:
    code, result = _check(tmp_path, votes=[
        _vote("nemesis", "claude-opus-5", "approve"),
        _vote("leo", "claude-sonnet-5", "approve"),
        _vote("judge", "gpt-5-codex", "return"),
    ])

    assert code == APPROVED
    assert result["approvals"] == 2


def test_the_losing_minority_is_kept(tmp_path: Path) -> None:
    """A minority that loses is the most interesting thing in the record."""
    _, result = _check(tmp_path, votes=[
        _vote("nemesis", "claude-opus-5", "approve"),
        _vote("leo", "claude-sonnet-5", "approve"),
        _vote("judge", "gpt-5-codex", "return"),
    ])

    assert result["dissent"] == ["judge"]


def test_below_the_majority_the_document_is_returned(tmp_path: Path) -> None:
    code, result = _check(tmp_path, votes=[
        _vote("nemesis", "claude-opus-5", "return"),
        _vote("leo", "claude-sonnet-5", "return"),
        _vote("judge", "gpt-5-codex", "approve"),
    ])

    assert code == NOT_APPROVED
    assert result["status"] == "returned"


def test_a_substituted_reviewer_means_the_panel_did_not_convene(tmp_path: Path) -> None:
    """Convening is theatre if the record may name reviewers the assignment did not.

    Three approvals, all with reasons, all from two families — and one of the voters
    was never assigned. Without this refusal a document could be routed to the
    specialists its content demands and signed off by three others.
    """
    code, result = _check(tmp_path, votes=[
        _vote("nemesis", "claude-opus-5", "approve"),
        _vote("hermes-scrum-master", "claude-sonnet-5", "approve"),
        _vote("judge", "gpt-5-codex", "approve"),
    ])

    assert code == DID_NOT_CONVENE
    assert "not the panel that was convened" in result["detail"]


def test_votes_without_an_assignment_prove_nothing(tmp_path: Path) -> None:
    """A record that supplies its own list of assignees is checked against itself."""
    code, result = _check(tmp_path, assigned=None, votes=[
        _vote("a", "claude-opus-5", "approve"),
        _vote("b", "claude-sonnet-5", "approve"),
        _vote("c", "gpt-5-codex", "approve"),
    ])

    assert code == DID_NOT_CONVENE
    assert "no panel was convened" in result["detail"]


def test_an_abstention_is_not_agreement(tmp_path: Path) -> None:
    """Two approvals out of two is not 2-of-3.

    The threshold is over a FULL panel, so a reviewer that could not run leaves the
    panel unconvened — a different fact from the document being wrong, and one that
    takes a different action.
    """
    code, result = _check(tmp_path, votes=[
        _vote("nemesis", "claude-opus-5", "approve"),
        _vote("leo", "claude-sonnet-5", "approve"),
        _vote("judge", "gpt-5-codex", "abstain"),
    ])

    assert code == DID_NOT_CONVENE
    assert "did not convene" in result["detail"]


def test_a_tick_is_not_a_verdict(tmp_path: Path) -> None:
    code, result = _check(tmp_path, votes=[
        _vote("nemesis", "claude-opus-5", "approve", "lgtm"),
        _vote("leo", "claude-sonnet-5", "approve"),
        _vote("judge", "gpt-5-codex", "approve"),
    ])

    assert code == DID_NOT_CONVENE
    assert "words" in result["detail"]


def test_an_ungated_phase_passes_untouched(tmp_path: Path) -> None:
    """CODE-QUALITY and RELEASE already derive their verdict from a script."""
    code, result = _check(tmp_path, phase="release", votes=None, assigned=None)

    assert code == APPROVED
    assert result["status"] == "not_gated"


def test_an_unreadable_record_is_not_a_pass(tmp_path: Path) -> None:
    project = _project(tmp_path, votes=[])
    (project / ".squad" / "records" / "panels" / "B-014-discover.json").write_text(
        "{ not json", encoding="utf-8")

    code, result = check("B-014", "discover", project=project,
                         panel_path=_roster(tmp_path))

    assert code == UNCHECKED
    assert result["status"] == "unchecked"


def test_the_gate_reads_the_one_write_root_whatever_the_layout(tmp_path: Path) -> None:
    """Regression: the writer and the reader must resolve the same directory.

    Both paths were hardcoded to `<project>/records/panels` while the kit wrote under
    `.claude/records` in a plugin install, so on every plugin consumer the gate looked
    in a directory nothing writes, reported `no_record` forever, and held every
    DISCOVER and PLAN permanently. Fail-closed in the wrong place is still a jammed
    pipeline.

    Centralising on `<project>/.squad/` removes the class rather than the instance:
    there is one root, so a layout cannot separate the writer from the reader. This
    project is shaped like a plugin install — `.claude/` present — and the panel is
    still found.
    """
    root = tmp_path / "plugin-shaped"
    (root / ".claude" / "skills").mkdir(parents=True)
    panels = root / ".squad" / "records" / "panels"
    panels.mkdir(parents=True)
    (panels / "B-014-discover.assignment.json").write_text(
        json.dumps({"assigned": PANEL}), encoding="utf-8")
    (panels / "B-014-discover.json").write_text(json.dumps({
        "slug": "B-014", "phase": "discover", "artifact": "op.md",
        "author": "daedalus-tech-lead",
        "votes": [_vote("nemesis", "claude-opus-5", "approve"),
                  _vote("leo", "claude-sonnet-5", "approve"),
                  _vote("judge", "gpt-5-codex", "approve")]}), encoding="utf-8")

    code, result = check("B-014", "discover", project=root,
                         panel_path=_roster(tmp_path))

    assert code == APPROVED, result
