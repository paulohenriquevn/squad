"""The critic returns work; it does not stop the chain.

That constraint is the whole design. `verdict-bands.txt` already separates the two axes
— `FAIL_SOFT` is `redo` and deliberately does NOT block, because walling ordinary rework
"would wall every loop that is working correctly". The critic sits in that band.

And the ceiling is the other half: a critic with no round limit stops the chain by
another route, since two parties disagreeing forever is a halt nobody declared.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_CYCLE = Path(__file__).resolve().parents[3] / "mechanisms" / "cycle"
if str(_CYCLE) not in sys.path:
    sys.path.insert(0, str(_CYCLE))

from critic_round import (  # noqa: E402
    MIN_FINDING_WORDS,
    VERDICTS,
    brief,
    cast,
    load_phases,
)

FINDING = "the report names ACCEPTED and the script emitted NOT_VALIDATED for criterion three"


def _project(tmp_path: Path, *, rounds: int = 2) -> Path:
    rules = tmp_path / "rules"
    rules.mkdir(parents=True, exist_ok=True)
    (rules / "critic-phases.txt").write_text(
        f"acceptance | rules/cycle-acceptance.md | {rounds} | does the report match the script\n",
        encoding="utf-8")
    (rules / "cycle-acceptance.md").write_text("# Acceptance\n", encoding="utf-8")
    return tmp_path


# ------------------------------------------------------------------ it does not block


def test_a_returned_round_does_not_end_the_chain(tmp_path: Path) -> None:
    """Exit 1, not a halt. The agent fixes what was named and the phase runs again
    inside the same autonomous span."""
    out = cast(_project(tmp_path), "acceptance", "M3", "returned", FINDING)

    assert out["outcome"] == "CRITIC_RETURNED"
    assert out["exit"] == 1


def test_rounds_exhausted_hands_over_rather_than_halting(tmp_path: Path) -> None:
    """A critic with no ceiling stops the chain by another route — two parties
    disagreeing forever is a halt nobody declared and nobody can see.

    The disposition passes to `halt_disposition.py`, which is where this kit already
    decides whether a stop returns the item to the registry or waits for a person. A
    critic adds a reader, not a second way of halting.
    """
    proj = _project(tmp_path, rounds=2)

    first = cast(proj, "acceptance", "M3", "returned", FINDING)
    second = cast(proj, "acceptance", "M3", "returned", FINDING)

    assert first["outcome"] == "CRITIC_RETURNED"
    assert second["outcome"] == "CRITIC_EXHAUSTED"
    assert second["exit"] == 3


def test_an_accepted_round_lets_the_phase_proceed(tmp_path: Path) -> None:
    out = cast(_project(tmp_path), "acceptance", "M3", "accepted", "")

    assert out["outcome"] == "CRITIC_ACCEPTED"
    assert out["exit"] == 0


def test_accepting_needs_no_finding(tmp_path: Path) -> None:
    """The floor is on returning, not on agreeing. Requiring a justification to accept
    would make accepting the expensive option."""
    assert cast(_project(tmp_path), "acceptance", "M3", "accepted", "")["exit"] == 0


# ------------------------------------------------------------------ the refusals


def test_a_returned_with_no_finding_is_refused(tmp_path: Path) -> None:
    """"I disagree" returns the work and tells the agent nothing to change, which
    produces this round again and the one after it."""
    with pytest.raises(SystemExit, match="Name what to change"):
        cast(_project(tmp_path), "acceptance", "M3", "returned", "nope")


def test_a_phase_with_no_critic_is_refused(tmp_path: Path) -> None:
    """`rules/critic-phases.txt` is the population, and a phase absent from it has no
    critic ON PURPOSE — asking for one is asking to add a fourth opinion where three
    reviewers already vote."""
    with pytest.raises(SystemExit, match="no critic declared"):
        cast(_project(tmp_path), "plan", "B-014", "accepted", "")


def test_an_invented_verdict_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        cast(_project(tmp_path), "acceptance", "M3", "maybe", FINDING)


# ------------------------------------------------------------------ the brief


def test_the_brief_carries_the_prior_rounds(tmp_path: Path) -> None:
    """A critic repeating a finding the agent already addressed burns a round, and that
    is how a ceiling gets reached for nothing."""
    proj = _project(tmp_path)
    cast(proj, "acceptance", "M3", "returned", FINDING)

    text = brief(load_phases(proj)["acceptance"], proj, "M3")

    assert "PRIOR ROUNDS" in text
    assert "criterion three" in text
    assert "Round 2 of 2" in text


def test_the_brief_states_that_the_critic_does_not_halt(tmp_path: Path) -> None:
    proj = _project(tmp_path)

    text = brief(load_phases(proj)["acceptance"], proj, "M3")

    assert "you do not stop the chain" in text
    assert "halt_disposition" in text


# ------------------------------------------------------------------ the population


def test_the_kit_declares_critics_only_where_nothing_reviews() -> None:
    """Measured 2026-09-11: discover, plan and design have a three-reviewer panel;
    brainstorm and implement have a judge and a scorer. A critic there is a fourth
    opinion over three, and redundant output teaches people to ignore the validator."""
    repo = Path(__file__).resolve().parents[3]
    declared = set(load_phases(repo))
    panel = (repo / "rules" / "review-panel.txt").read_text(encoding="utf-8")
    gated = {p.strip() for line in panel.splitlines() if line.startswith("panel_phases")
             for p in line.split("=")[1].split(",")}

    assert declared == {"acceptance", "code-quality", "backlog", "release"}
    assert not (declared & gated), declared & gated


def test_every_critic_phase_names_a_contract_that_exists() -> None:
    """A critic with no contract grades against taste."""
    repo = Path(__file__).resolve().parents[3]

    for phase, critic in load_phases(repo).items():
        assert (repo / critic.contract).is_file(), f"{phase} → {critic.contract}"
        assert critic.max_rounds >= 1
        assert len(critic.asked.split()) >= 10, phase


def test_every_verdict_is_declared_in_the_bands_registry() -> None:
    repo = Path(__file__).resolve().parents[3]
    bands = (repo / "rules" / "verdict-bands.txt").read_text(encoding="utf-8")
    declared = {line.split("|")[0].strip() for line in bands.splitlines()
                if "|" in line and not line.lstrip().startswith("#")}

    assert {"CRITIC_ACCEPTED", "CRITIC_RETURNED", "CRITIC_EXHAUSTED"} <= declared


def test_returned_is_banded_redo_not_structural() -> None:
    """Banding it structural would make it block, which is the one thing it must not
    do — the chain has to keep moving."""
    repo = Path(__file__).resolve().parents[3]
    for line in (repo / "rules" / "verdict-bands.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith("CRITIC_RETURNED"):
            assert line.split("|")[1].strip() == "redo"
            return
    pytest.fail("CRITIC_RETURNED is not in the bands registry")


def test_the_record_accumulates_rather_than_overwriting(tmp_path: Path) -> None:
    proj = _project(tmp_path, rounds=5)
    cast(proj, "acceptance", "M3", "returned", FINDING)
    out = cast(proj, "acceptance", "M3", "returned", FINDING + " and also the caveat list")

    record = json.loads(Path(out["record"]).read_text(encoding="utf-8"))

    assert len(record["rounds"]) == 2
    assert MIN_FINDING_WORDS == 10
    assert set(VERDICTS) == {"accepted", "returned"}
