"""A document advances on a majority of signed approvals, or it goes back.

Decided 2026-09-08. DISCOVER produces an opportunity and PLAN produces a plan;
both are judged by three reviewers, at least one of them outside the Anthropic
family, and both need 2 of 3 to advance.

WHAT THIS MECHANISM IS FOR, AND IT IS NOT THE COUNTING

Counting to two is trivial. Everything of value here is in what the panel REFUSES
to count, because each refusal corresponds to a way a panel can look convened and
be a rubber stamp:

  - the author voting on their own document;
  - three votes that are really one model asked three times;
  - a reviewer that could not run, silently read as agreement;
  - a verdict with no reasoning behind it;
  - one reviewer voting twice.

A panel that cannot refuse is a signature ceremony. `alignment_judge.py` was
exactly that until this existed: it took `--verdict signed` on the command line
and stamped it, so its independence depended entirely on who invoked it and
nothing verified that.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "mechanisms" / "cycle"))

from review_panel import (
    PANEL_SIZE,
    Panel,
    PanelInvalid,
    PanelOutcome,
    Vote,
    family_of,
    main,
)

REASON = (
    "checked the four corners against the cited evidence and followed every file:line "
    "pointer to the source, all of which resolve and support the stated conclusion"
)


def _vote(reviewer: str, model: str, verdict: str = "approve", reason: str = REASON) -> Vote:
    return Vote(reviewer=reviewer, model=model, verdict=verdict, reason=reason)


def _panel(*votes: Vote, author: str = "agent/author-session") -> Panel:
    return Panel(slug="B-014", phase="discover", artifact="x-opportunity.md",
                 author=author, votes=list(votes))


def _mixed(*verdicts: str) -> Panel:
    """A structurally valid panel — distinct reviewers, one non-Anthropic family."""
    models = ["claude-opus-5", "gpt-5-codex", "claude-sonnet-5"]
    return _panel(*[
        _vote(f"reviewer/{i}", models[i], v) for i, v in enumerate(verdicts)
    ])


# ---------------------------------------------------------------------------
# The tally
# ---------------------------------------------------------------------------

def test_two_of_three_approvals_advance_the_document() -> None:
    assert _mixed("approve", "approve", "return").tally() is PanelOutcome.APPROVED


def test_unanimous_approval_advances() -> None:
    assert _mixed("approve", "approve", "approve").tally() is PanelOutcome.APPROVED


def test_two_returns_send_the_document_back() -> None:
    assert _mixed("approve", "return", "return").tally() is PanelOutcome.RETURNED


def test_a_lone_approval_is_not_a_majority() -> None:
    assert _mixed("return", "return", "return").tally() is PanelOutcome.RETURNED


def test_the_dissent_survives_the_tally() -> None:
    """A minority vote that loses is still the most interesting thing in the record.

    Reporting only the outcome would discard exactly the signal a panel exists to
    produce — the kit already says this about Claude and Codex disagreeing.
    """
    panel = _mixed("approve", "approve", "return")

    assert panel.tally() is PanelOutcome.APPROVED
    dissent = panel.dissenting()
    assert len(dissent) == 1
    assert dissent[0].reviewer == "reviewer/2"
    assert dissent[0].reason


# ---------------------------------------------------------------------------
# What the panel refuses to count — the whole point
# ---------------------------------------------------------------------------

def test_the_author_may_not_sit_on_the_panel() -> None:
    """The rule `alignment-threshold.md` has always made, finally mechanised."""
    panel = _panel(
        _vote("agent/author-session", "claude-opus-5"),
        _vote("reviewer/1", "gpt-5-codex"),
        _vote("reviewer/2", "claude-sonnet-5"),
        author="agent/author-session",
    )

    with pytest.raises(PanelInvalid, match="author"):
        panel.tally()


def test_three_votes_from_one_family_do_not_form_a_panel() -> None:
    """Three Claudes asked three times share their failure modes.

    This is not a reprimand of the models — it is what correlation means. A plausible
    fabrication that survives one of them tends to survive its siblings, which is the
    single thing an orthogonal reviewer is there to catch.
    """
    panel = _panel(
        _vote("reviewer/0", "claude-opus-5"),
        _vote("reviewer/1", "claude-sonnet-5"),
        _vote("reviewer/2", "claude-haiku-4-5"),
    )

    with pytest.raises(PanelInvalid, match="famil"):
        panel.tally()


def test_an_unknown_model_string_cannot_supply_the_diversity() -> None:
    """Otherwise `--model anything` proves orthogonality by typing.

    An unrecognised model counts toward NOTHING: not the Anthropic side, not the
    outside. The requirement is a vote from a *recognised* family that is not
    Anthropic's.
    """
    panel = _panel(
        _vote("reviewer/0", "claude-opus-5"),
        _vote("reviewer/1", "claude-sonnet-5"),
        _vote("reviewer/2", "totally-made-up-model"),
    )

    with pytest.raises(PanelInvalid, match="famil"):
        panel.tally()


def test_fewer_than_three_votes_is_not_a_panel_that_returned() -> None:
    """The distinction that keeps an incomplete panel from reading as a rejection.

    Two approvals out of two is not 2-of-3. The threshold is over a FULL panel, and
    a missing reviewer is an abstention — abstention approves nothing and rejects
    nothing. It means the panel did not convene.
    """
    panel = _panel(
        _vote("reviewer/0", "claude-opus-5"),
        _vote("reviewer/1", "gpt-5-codex"),
    )

    with pytest.raises(PanelInvalid, match="did not convene|3 vote"):
        panel.tally()


def test_a_reviewer_may_not_vote_twice() -> None:
    panel = _panel(
        _vote("reviewer/0", "claude-opus-5"),
        _vote("reviewer/0", "claude-opus-5"),
        _vote("reviewer/1", "gpt-5-codex"),
    )

    with pytest.raises(PanelInvalid, match="twice|distinct"):
        panel.tally()


def test_a_verdict_without_reasoning_is_not_a_vote() -> None:
    """Same floor `alignment_judge.py` applies to a signature, for the same reason:
    a verdict with no reasoning is a tick, and a tick is what this exists to beat."""
    panel = _panel(
        _vote("reviewer/0", "claude-opus-5", reason="looks fine"),
        _vote("reviewer/1", "gpt-5-codex"),
        _vote("reviewer/2", "claude-sonnet-5"),
    )

    with pytest.raises(PanelInvalid, match="reason"):
        panel.tally()


def test_a_reviewer_that_could_not_run_never_reads_as_approval() -> None:
    """`abstain` is a real verdict and it is counted as what it is.

    Reading a failed reviewer as agreement is the defect the kit names about
    `check_xrefs` without `--strict`: a gate that looks, sees nothing, and approves
    produces confidence where there was no verification.
    """
    panel = _mixed("approve", "approve", "abstain")

    # Two approvals and an abstention is not a full panel of three votes.
    with pytest.raises(PanelInvalid, match="did not convene|abstain"):
        panel.tally()


# ---------------------------------------------------------------------------
# Family resolution
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("model", "family"),
    [
        ("claude-opus-5", "anthropic"),
        ("claude-sonnet-5", "anthropic"),
        ("claude-haiku-4-5-20251001", "anthropic"),
        ("gpt-5-codex", "openai"),
        ("o4-mini", "openai"),
        ("gemini-2.5-pro", "google"),
        ("llama-4-scout", "meta"),
        ("mistral-large", "mistral"),
        ("nonsense", "unknown"),
        ("", "unknown"),
    ],
)
def test_family_resolution(model: str, family: str) -> None:
    assert family_of(model) == family


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------

def test_the_panel_size_is_odd_so_a_tie_cannot_happen() -> None:
    assert PANEL_SIZE % 2 == 1


def test_a_valid_panel_reports_who_sat_on_it() -> None:
    """The record has to say which models judged, or "approved by a panel" is a
    claim nobody downstream can check."""
    panel = _mixed("approve", "approve", "return")
    record = panel.record()

    assert record["outcome"] == "approved"
    assert record["approvals"] == 2
    assert sorted(record["families"]) == ["anthropic", "openai"]
    assert len(record["votes"]) == 3
    assert all(v["reason"] for v in record["votes"])


# ------------------------------------------------------------------ #79


def _record_file(tmp_path, votes):
    import json
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "rec.json"
    path.write_text(json.dumps({
        "slug": "s", "phase": "design", "author": "claude/opus-5", "artifact": "x.md",
        "assigned": ["a", "b", "c"], "votes": votes,
    }), encoding="utf-8")
    return path


_LONG = ("checked the drawing against the code and found nothing that contradicts it "
         "anywhere in the five files under review here today")


def test_a_dissenting_panel_renders_instead_of_raising(tmp_path, capsys) -> None:
    """#79. `dissent` was enriched from a bare name to reviewer + family + reason — the
    comment above it argues correctly that the objection must travel — and the only
    place that renders it was left doing `', '.join(...)` over dicts.

    It survived because it fires only on DISAGREEMENT, which is the case a panel is
    bought for. Every unanimous panel skipped the line.
    """
    record = _record_file(tmp_path, [
        {"reviewer": "a", "model": "claude-opus-5", "verdict": "approve", "reason": _LONG},
        {"reviewer": "b", "model": "gpt-5-codex", "verdict": "approve", "reason": _LONG},
        {"reviewer": "c", "model": "claude-sonnet-5", "verdict": "return", "reason": _LONG},
    ])

    code = main(["--record", str(record)])
    out = capsys.readouterr().out

    assert code == 0
    assert "Traceback" not in out
    assert "c (anthropic)" in out, out


def test_the_crash_exit_code_was_indistinguishable_from_a_verdict(tmp_path) -> None:
    """`main()` returns 1 for any non-approved outcome, and an uncaught TypeError also
    exits 1 — so a caller reading the exit code saw the right number for the wrong
    reason. The rendering must not be able to raise at all."""
    record = _record_file(tmp_path, [
        {"reviewer": "a", "model": "claude-opus-5", "verdict": "approve", "reason": _LONG},
        {"reviewer": "b", "model": "claude-sonnet-5", "verdict": "approve", "reason": _LONG},
        {"reviewer": "c", "model": "gpt-5-codex", "verdict": "return", "reason": _LONG},
    ])

    assert main(["--record", str(record)]) == 1


def test_the_losing_side_is_labelled_by_which_side_it_is(tmp_path, capsys) -> None:
    """`dissenting()` returns the LOSING side and that flips with the outcome: under
    APPROVED it is the reviewers who returned, under RETURNED it is the reviewers who
    approved. Printing both as "dissent" reported two approvals as objections."""
    returned = _record_file(tmp_path, [
        {"reviewer": "a", "model": "claude-opus-5", "verdict": "approve", "reason": _LONG},
        {"reviewer": "b", "model": "claude-sonnet-5", "verdict": "approve", "reason": _LONG},
        {"reviewer": "c", "model": "gpt-5-codex", "verdict": "return", "reason": _LONG},
    ])
    main(["--record", str(returned)])
    assert "approvals, which did not carry" in capsys.readouterr().out

    approved = _record_file(tmp_path / "two", [
        {"reviewer": "a", "model": "claude-opus-5", "verdict": "approve", "reason": _LONG},
        {"reviewer": "b", "model": "gpt-5-codex", "verdict": "approve", "reason": _LONG},
        {"reviewer": "c", "model": "claude-sonnet-5", "verdict": "return", "reason": _LONG},
    ])
    main(["--record", str(approved)])
    assert "objections, over which this was approved" in capsys.readouterr().out


def test_the_reason_is_not_truncated_in_the_dissent(tmp_path, capsys) -> None:
    """The vote list truncates at 90 chars for scanning; the objection must not. A
    dissent cut mid-sentence is the defect this payload was enriched to prevent."""
    record = _record_file(tmp_path, [
        {"reviewer": "a", "model": "claude-opus-5", "verdict": "approve", "reason": _LONG},
        {"reviewer": "b", "model": "gpt-5-codex", "verdict": "approve", "reason": _LONG},
        {"reviewer": "c", "model": "claude-sonnet-5", "verdict": "return", "reason": _LONG},
    ])

    main(["--record", str(record)])

    assert _LONG in capsys.readouterr().out
