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


def _roster_families() -> set[str]:
    """The model families the roster actually seats, read from the roster itself."""
    from review_panel import family_of, parse_roster

    return {family_of(seat.model) for seat in parse_roster(ROSTER.read_text(encoding="utf-8"))}


def test_the_waiver_is_present_exactly_when_the_roster_needs_it() -> None:
    """Both directions. A missing waiver hides a weaker panel; a stale one hides a stronger.

    This asserted the waiver UNCONDITIONALLY until 2026-09-21, which made it a test of
    one day's roster rather than of the rule. The roster changed that day — the codex
    CLI was upgraded, `codex exec` answered on gpt-5.5, and one seat per phase became
    `judge-codex:*` — and the test failed for a roster that had just got BETTER. A test
    that reddens on an improvement is a test people delete.

    The rule it was reaching for has two sides, and only one was written:

      one family  -> the waiver must be declared, with a reason
      two or more -> the waiver must be gone

    The second side is the defect that was actually found on disk: the keys outlived
    the fact they named, and nothing could tell.
    """
    text = ROSTER.read_text(encoding="utf-8")
    data = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    declared = [ln for ln in data if ln.startswith("single_family_panel")]
    reasons = [ln for ln in data if ln.startswith("single_family_reason")]

    if _roster_families() - {"anthropic"}:
        assert not declared and not reasons, (
            "the roster spans more than one family, so the waiver is obsolete — and an "
            "obsolete waiver makes a two-family APPROVED read as the weaker one-family "
            "claim, which is the guarantee this panel exists to give")
        return

    assert declared, (
        "every seat is Anthropic, so the cross-family rule is waived — and a waiver "
        "nobody declared is indistinguishable from a roster somebody got wrong")
    assert reasons, (
        "an exemption with no reason is an escape hatch, not a record")


@pytest.mark.usefixtures("reachable_review_panel")
def test_the_capability_gate_reports_the_family_span_it_found() -> None:
    """HOLDS either way — and the line saying so matches the roster on disk."""
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(REPO / "mechanisms" / "gates" / "check_panel_capability.py")],
        capture_output=True, text=True, cwd=REPO, check=False)

    assert proc.returncode == 0, proc.stdout + proc.stderr

    if _roster_families() - {"anthropic"}:
        assert "SINGLE FAMILY, BY DECLARATION" not in proc.stdout, (
            "the roster spans two families, so the gate must not warn about one — a "
            "warning that survives the condition it describes trains readers to skip it")
        return

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
    from review_panel import Panel, PanelInvalid, Vote

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


# ---------------------------------------------------------------------------
# A waiver that names a FACT must be refuted when the fact is false.
#
# The reason read "no non-Anthropic provider is configured for this project" until
# 2026-09-21, while `codex` sat on PATH, authenticated, with `judge-codex` installed.
# It had been false for as long as nobody re-read it — which is the whole failure mode
# of a claim nothing checks. `check_panel_capability.py` already refuses to let the
# waiver pass SILENTLY; what it could not do is notice the waiver was lying.
#
# Only the "no provider" CLASS of reason is checkable. A waiver naming a broken CLI, an
# expired key or a refused model is a fact about the provider's BEHAVIOUR, and probing
# that means spending a call on every gate run — so those stay a human claim, and this
# check says nothing about them rather than guessing.
# ---------------------------------------------------------------------------

def test_a_waiver_claiming_no_provider_is_refuted_by_a_provider_on_path() -> None:
    from check_panel_capability import waiver_contradicted

    on_path = {"codex": "/usr/bin/codex"}.get

    assert waiver_contradicted(
        "no non-Anthropic provider is configured for this project", which=on_path), (
        "the waiver claims no provider is configured while `codex` is on PATH — a "
        "reason nothing re-reads is a reason that outlives the fact it names")


def test_a_waiver_naming_a_broken_provider_is_not_refuted_by_the_binary() -> None:
    """The binary being present is the PREMISE of this reason, not a refutation."""
    from check_panel_capability import waiver_contradicted

    on_path = {"codex": "/usr/bin/codex"}.get

    assert not waiver_contradicted(
        "codex CLI 0.120.0 is installed and authenticated but refuses every model "
        "this account exposes (400: gpt-5.5 requires a newer CLI)", which=on_path)


def test_no_provider_on_path_leaves_the_no_provider_waiver_standing() -> None:
    from check_panel_capability import waiver_contradicted

    assert not waiver_contradicted(
        "no non-Anthropic provider is configured for this project",
        which=lambda _name: None)


def test_this_projects_declared_reason_is_not_self_contradictory() -> None:
    """The roster on disk, checked against this machine."""
    import shutil

    from check_panel_capability import waiver_contradicted
    from review_panel import single_family_waived

    waived, reason = single_family_waived(ROSTER.read_text(encoding="utf-8"))
    if not waived:
        pytest.skip("this project declares no waiver")
    assert not waiver_contradicted(reason, which=shutil.which), (
        f"the declared reason is refuted on this machine: {reason}")
