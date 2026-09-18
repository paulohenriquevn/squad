"""The step between "a panel is required" and "a panel voted".

`convene_panel.py` assigns and `review_panel.py` tallies; issue #65 named what sat
between them — nothing. The mechanisms were right and unreachable.

The tests that matter are the refusals `cast_vote` makes EARLY. `review_panel` validates
a complete panel and refuses it whole, which is right at tally time and useless while
collecting: the session learns its first vote was invalid after spending three
invocations.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_CYCLE = Path(__file__).resolve().parents[3] / "mechanisms" / "cycle"
if str(_CYCLE) not in sys.path:
    sys.path.insert(0, str(_CYCLE))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from cast_vote import (  # noqa: E402 — post-bootstrap import
    MIN_REASON_WORDS,
    VERDICTS,
    cast,
)
from panel_brief import PHASE_SOURCES, build  # noqa: E402 — post-bootstrap import

REASON = "checked D4 against the charts and the store it names is present in the sibling repository"


def _project(tmp_path: Path, *, author: str = "claude/opus-5",
             assigned: tuple[str, ...] = ("vera", "nemesis", "codex")) -> Path:
    panels = tmp_path / ".squad" / "records" / "panels"
    panels.mkdir(parents=True)
    (panels / "s-design.assignment.json").write_text(json.dumps({
        "status": "assigned", "slug": "s", "phase": "design", "author": author,
        "assigned": list(assigned),
        "seats": [{"agent": a, "model": "claude-opus-5", "family": "anthropic",
                   "invocation": "builtin"} for a in assigned],
    }), encoding="utf-8")
    return tmp_path


# ------------------------------------------------------------------ early refusals


def test_an_unassigned_reviewer_is_refused_when_it_votes(tmp_path: Path) -> None:
    """The tally would drop it and report a panel short one vote — incomplete rather
    than approved. Refusing here costs one invocation instead of three."""
    with pytest.raises(SystemExit) as exc:
        cast(_project(tmp_path), "s", "design", "intruder", "m", "approve", REASON)

    assert exc.value.code == 1


def test_the_author_cannot_vote_on_their_own_artifact(tmp_path: Path) -> None:
    proj = _project(tmp_path, author="vera", assigned=("vera", "nemesis", "codex"))

    with pytest.raises(SystemExit):
        cast(proj, "s", "design", "vera", "m", "approve", REASON)


def test_a_thin_reason_is_refused(tmp_path: Path) -> None:
    """A vote nobody can argue with is a vote nobody can overturn."""
    with pytest.raises(SystemExit):
        cast(_project(tmp_path), "s", "design", "vera", "m", "approve", "looks fine")


def test_a_second_vote_from_one_seat_is_refused(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    cast(proj, "s", "design", "vera", "m", "approve", REASON)

    with pytest.raises(SystemExit):
        cast(proj, "s", "design", "vera", "m", "return", REASON)


def test_an_invented_verdict_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        cast(_project(tmp_path), "s", "design", "vera", "m", "looks-good", REASON)


def test_abstain_is_a_valid_verdict(tmp_path: Path) -> None:
    """A reviewer that could not audit must be able to say so. Counted as an
    incomplete panel, never as agreement — but it has to be recordable."""
    assert "abstain" in VERDICTS

    out = cast(_project(tmp_path), "s", "design", "vera", "m", "abstain", REASON)

    assert out["votes"] == 1


def test_no_assignment_records_nothing(tmp_path: Path) -> None:
    """A vote with no assignment behind it is one the tally refuses."""
    with pytest.raises(SystemExit) as exc:
        cast(tmp_path, "s", "design", "vera", "m", "approve", REASON)

    assert exc.value.code == 2


# ------------------------------------------------------------------ accumulation


def test_votes_accumulate_and_the_remainder_is_named(tmp_path: Path) -> None:
    proj = _project(tmp_path)

    first = cast(proj, "s", "design", "vera", "m", "approve", REASON)
    second = cast(proj, "s", "design", "nemesis", "m", "return", REASON)

    assert first["remaining"] == ["nemesis", "codex"]
    assert second["remaining"] == ["codex"]


def test_the_record_carries_the_assignment_it_was_cast_against(tmp_path: Path) -> None:
    """`review_panel` reports a weaker claim when nobody checked the roster. Carrying
    it means the tally can check rather than assume."""
    proj = _project(tmp_path)
    cast(proj, "s", "design", "vera", "m", "approve", REASON)

    record = json.loads((proj / ".squad" / "records" / "panels" / "s-design.json")
                        .read_text(encoding="utf-8"))

    assert record["assigned"] == ["vera", "nemesis", "codex"]
    assert record["author"] == "claude/opus-5"


# ------------------------------------------------------------------ the brief


def test_a_phase_with_no_contract_is_refused(tmp_path: Path) -> None:
    """A panel with no golden rule grades against taste, and three reviewers grading
    against taste disagree for reasons nobody can adjudicate."""
    with pytest.raises(SystemExit, match="no contract declared"):
        build(_project(tmp_path), "s", "nosuchphase")


def test_every_panel_phase_has_a_contract() -> None:
    """`rules/review-panel.txt` declares which phases are gated; each must be briefable,
    or the panel runs without the contract its phase declares."""
    panel = Path(__file__).resolve().parents[3] / "rules" / "review-panel.txt"
    declared = [ln.split("=", 1)[1] for ln in panel.read_text(encoding="utf-8").splitlines()
                if ln.startswith("panel_phases")]
    phases = {p.strip() for p in declared[0].split(",")} if declared else set()

    assert phases, "no panel_phases declared"
    assert phases <= set(PHASE_SOURCES), phases - set(PHASE_SOURCES)


def test_the_brief_names_the_contract_the_artifact_and_the_author() -> None:
    """A reviewer told "review this" reviews whatever it decided to look at, and three
    such reviews are three opinions about three different questions."""
    from panel_brief import _brief

    text = _brief({"agent": "vera", "model": "claude-opus-5"}, "s", "design",
                  Path("/k/rules/design-golden-rule.md"), [], [], "claude/opus-5")

    assert "design-golden-rule.md" in text
    assert "claude/opus-5" in text
    assert "you may not edit it" in text
    assert str(MIN_REASON_WORDS) in text or "fifteen" in text
    for verdict in VERDICTS:
        assert verdict in text


def test_the_brief_states_that_an_abstention_is_not_agreement() -> None:
    from panel_brief import _brief

    text = _brief({"agent": "v", "model": "m"}, "s", "design", Path("/c.md"), [], [], "a")

    assert "never as agreement" in text
