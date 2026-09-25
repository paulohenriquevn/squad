"""The alignment brief's sign-off had no convened reviewer, so it was filled by hand.

`skills/plan-alignment/SKILL.md:63` states the contract:

    `alignment_judge.py` | `<!-- signed-by: judge/alignment-judge -->` | a second agent that
    read the EVIDENCE, not only the brief, and could refuse

And `alignment_judge.py` says what it is, at its line 38: *"It takes its verdict on the command
line. It does not read the evidence itself."* It is a RECORDER for a verdict some agent reached.
Nothing convened that agent. `rules/review-panel.txt` declared `discover`, `plan` and `design`
and no `alignment`, and `convene_panel.py` resolves seats only for a phase the roster names.

Measured consequence on a consumer: four briefs at 34/34 `AWAITING_REVIEW`, and the practical
path to a signature was messaging another session — which depends on one being alive and idle.
One item took five rounds that way. The five rounds found 14 real defects, so the rigour is
working; what was missing is the convocation.

WHY ONE SEAT AND NOT THREE. A panel VOTES — three seats, 2 of 3, and the majority is the
property. An alignment sign-off is four checkboxes ticked by ONE reviewer who is not the author,
and `score_alignment` reports the weakest signer of the set. A majority has no meaning over it,
so `PANEL_SIZE` is now per phase rather than a single constant.

WHY THE OUTSIDE-FAMILY RULE DOES NOT REACH A SINGLE SEAT. It exists because "correlated models
share failure modes and a plausible fabrication that survives one tends to survive its
siblings" — an argument about a MAJORITY being fooled together. For one reviewer the guarantee
that matters is *not the author*, which the signature vocabulary already records. Measured
2026-09-23: two same-family sessions reviewing each other refuted three claims, and one of those
refutations found a root cause neither had seen — same-family review is not empty review.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "mechanisms" / "cycle"))

ROSTER = _ROOT / "rules" / "review-panel.txt"
CONVENE = _ROOT / "mechanisms" / "cycle" / "convene_panel.py"


def test_the_roster_declares_an_alignment_seat() -> None:
    from review_panel import seats_for

    seats = seats_for(ROSTER.read_text(encoding="utf-8"), "alignment")

    assert seats, (
        "no `alignment` seat in rules/review-panel.txt, so nothing convenes the reviewer the "
        "sign-off contract requires and an author fills it by hand or by messaging a peer")
    assert len(seats) == 1, f"the sign-off is one reviewer, not a panel: {seats}"


def test_the_seated_agent_is_one_that_confronts_claims_with_evidence() -> None:
    from review_panel import seats_for

    seat = seats_for(ROSTER.read_text(encoding="utf-8"), "alignment")[0]
    agent_file = _ROOT / "agents" / f"{seat.agent}.md"

    assert agent_file.is_file(), f"the seat names `{seat.agent}` and no such agent ships"
    description = agent_file.read_text(encoding="utf-8")[:1200].lower()
    assert "evidence" in description, (
        f"`{seat.agent}` is seated to read the EVIDENCE and its own description does not "
        f"mention any — the contract asks for a reviewer that could refuse")


def test_convene_resolves_the_alignment_seat() -> None:
    out = subprocess.run(
        [sys.executable, str(CONVENE), "--slug", "x", "--phase", "alignment", "--json"],
        capture_output=True, text=True, check=False, cwd=str(_ROOT))

    assert out.returncode == 0, (out.stdout + out.stderr)[-1500:]
    assert "alignment" in out.stdout, out.stdout[-800:]


def test_a_panel_phase_still_needs_three_seats() -> None:
    """The change is per phase. A voting panel that shrank to one would lose its majority."""
    from review_panel import panel_size_for

    assert panel_size_for("plan") == 3
    assert panel_size_for("discover") == 3
    assert panel_size_for("alignment") == 1


@pytest.mark.usefixtures("reachable_review_panel")
def test_the_capability_gate_accepts_the_roster_as_shipped() -> None:
    gate = _ROOT / "mechanisms" / "gates" / "check_panel_capability.py"
    out = subprocess.run([sys.executable, str(gate), "--panel", str(ROSTER)],
                         capture_output=True, text=True, check=False, cwd=str(_ROOT))

    assert out.returncode == 0, (
        "the kit's own roster does not satisfy the kit's own capability gate:\n"
        + (out.stdout + out.stderr)[-1500:])
