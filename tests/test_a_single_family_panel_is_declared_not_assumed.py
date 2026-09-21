"""A project may waive the cross-family panel. It may not do so quietly.

WHY THIS EXISTS
---------------
`rules/review-panel.txt` states the one constraint the kit imposes: *"At least one
counted vote must come from a recognised family outside the one the kit itself runs on.
Three Claudes asked three times share their failure modes: a plausible fabrication that
survives one tends to survive its siblings."* `check_panel_capability.py` refuses a
roster of one family at intake — "Fails everywhere, CI included" — and
`review_panel.tally()` returns any document whose approving majority does not span two.

A project with no non-Anthropic provider configured cannot satisfy that, and the honest
options are two: run no panel at all, or run one and say what it is worth. This is the
second. `rules/review-panel.txt` is the layer the installer PRESERVES precisely because
which models a project can reach is not the kit's business — so the waiver lives there,
carries a reason, and the kit keeps the rule and the argument for every other consumer.

WHAT THE WAIVER MUST NOT DO
---------------------------
Disappear. A panel that no longer spans two families is worth less than one that does,
and a reader who cannot tell them apart has been handed the ceremony without the
guarantee. Every outcome carries the waiver, so `APPROVED` under it reads as what it is.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
for _rel in ("mechanisms/cycle", "mechanisms/gates"):
    _p = str(REPO / _rel)
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.path.insert(0, str(REPO))

ROSTER = REPO / "rules" / "review-panel.txt"


def test_the_roster_declares_the_waiver_with_a_reason() -> None:
    text = ROSTER.read_text(encoding="utf-8")
    data = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]

    assert any(ln.startswith("single_family_panel") for ln in data), (
        "every seat is Anthropic, so the cross-family rule is waived — and a waiver "
        "nobody declared is indistinguishable from a roster somebody got wrong")
    assert any(ln.startswith("single_family_reason") for ln in data), (
        "an exemption with no reason is an escape hatch, not a record")


def test_the_capability_gate_accepts_the_declared_waiver() -> None:
    """HOLDS, and the line saying so carries why it holds."""
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(REPO / "mechanisms" / "gates" / "check_panel_capability.py")],
        capture_output=True, text=True, cwd=REPO)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SINGLE FAMILY, BY DECLARATION" in proc.stdout, (
        "the gate must say the panel is single-family BY DECLARATION, not pass silently")


def test_a_single_family_majority_carries_under_the_waiver() -> None:
    from review_panel import Panel, PanelOutcome, Vote

    panel = Panel(
        slug="b042-demo", phase="plan", artifact="abc123", author="daedalus-tech-lead",
        votes=[Vote("vera-technical-arbiter", "claude-opus-5", "approve",
                    "the evidence supports the conclusion drawn from it, and each pointer in the brief resolves on disk"),
               Vote("nemesis-claim-auditor", "claude-sonnet-5", "approve",
                    "every claim resolves against the measurement it cites, and the two that did not were withdrawn"),
               Vote("argus-pattern-analyst", "claude-opus-5", "return",
                    "the shape repeats a defect this registry already recorded twice, under B-031 and again under B-077")],
        single_family_waived=True,
    )

    assert panel.tally() is PanelOutcome.APPROVED
    assert "single family" in panel.outcome_note.lower(), (
        "the outcome must carry the waiver: APPROVED by one family is a weaker claim "
        "than APPROVED across two, and a reader tells them apart or is misled")


def test_without_the_waiver_one_family_still_cannot_carry() -> None:
    """The kit keeps the rule. Only a project that declared the waiver escapes it."""
    from review_panel import Panel, PanelInvalid, PanelOutcome, Vote

    panel = Panel(
        slug="b042-demo", phase="plan", artifact="abc123", author="daedalus-tech-lead",
        votes=[Vote("vera-technical-arbiter", "claude-opus-5", "approve",
                    "the evidence supports the conclusion drawn from it, and each pointer in the brief resolves on disk"),
               Vote("nemesis-claim-auditor", "claude-sonnet-5", "approve",
                    "every claim resolves against the measurement it cites, and the two that did not were withdrawn"),
               Vote("argus-pattern-analyst", "claude-opus-5", "return",
                    "the shape repeats a defect this registry already recorded twice, under B-031 and again under B-077")],
        single_family_waived=False,
    )

    with pytest.raises(PanelInvalid, match="outside"):
        panel.tally()
