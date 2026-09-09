"""Where an item goes when a phase stops, now that no phase may address a person.

`rules/autonomy-envelope.md § The autonomous span` (2026-09-08) removed every
*escalate to the human* between DISCOVER and ACCEPTANCE. Removing them is only half a
policy: a loop that cannot finish must still stop, and the item still has to go
somewhere. These tests pin where.

The two dispositions are deliberately NOT symmetric with `delegated_decision.py`, and
the asymmetry is the thing most likely to be "corrected" by a later reader:

  - a `blocked_by` line in the REGISTRY is prose a person wrote, so an unmatched one is
    RETAINED — no match is not consent;
  - a halt in a PHASE is emitted by the system with a known verdict, so an unmatched one
    is the queue's own work — a failing gate is a named cause, and the queue puts a named
    cause at the front precisely because something is blocked on it.

Reading a failing gate as an impediment would send every ordinary rework loop to a person
and rebuild the halt this policy exists to remove.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "mechanisms" / "cycle"))

from halt_disposition import (
    Disposition,
    disposition_for,
)

# --------------------------------------------------------------------------------------
# The default: a halt is work, and work goes back to the queue.
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("phase", "verdict"),
    [
        ("implement", "FAIL"),
        ("implement", "PHASE_REVIEW_NEEDS_FIX"),
        ("code-quality", "FAIL_HARD"),
        ("review", "NEEDS_FIXES"),
        ("plan-confidence", "INVALID"),
        ("discover", "NEEDS_DEEPER"),
        ("release", "BLOCKED"),
    ],
)
def test_a_failing_gate_returns_to_the_queue_not_to_a_person(phase: str, verdict: str) -> None:
    """Every one of these was written as *surface to human* before 2026-09-08."""
    result = disposition_for(phase=phase, verdict=verdict, cause="the gate reported a defect")

    assert result.disposition is Disposition.RETURN_TO_QUEUE
    assert not result.awaits_person
    assert result.reason


def test_an_exhausted_loop_is_still_work() -> None:
    """`autonomy-envelope.md § A loop ran out of attempts` — the diagnosis is the item's
    evidence, and a diagnosis parked in front of an absent person is worth nothing."""
    result = disposition_for(
        phase="implement",
        verdict="BLOCKED",
        cause="same check FAIL x3 with no observable progress: mypy rejects the new signature",
    )

    assert result.disposition is Disposition.RETURN_TO_QUEUE
    assert not result.awaits_person


# --------------------------------------------------------------------------------------
# The exception the sponsor named: a clear blockage that costs something to clear.
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("cause", "expected_class"),
    [
        ("the measurement needs a credential this process does not hold", "access"),
        ("target unreachable: no host is provisioned for the staging API", "access"),
        ("this needs another VM provisioned before it can run", "access"),
        ("requires a repository the session cannot reach", "access"),
        ("the series needs 30 days of accumulated data", "elapsed"),
        ("the live environment is down; nothing is standing to probe", "liveness"),
    ],
)
def test_a_material_impediment_is_retained(cause: str, expected_class: str) -> None:
    """Authority does not conjure a machine, a credential, or the passage of time."""
    result = disposition_for(phase="discover", verdict="BLOCKED", cause=cause)

    assert result.disposition is Disposition.RETAIN_FOR_PERSON
    assert result.awaits_person
    assert result.decision_class == expected_class
    assert result.reason


def test_governance_is_retained_and_says_it_is_not_about_resources() -> None:
    """The fourth retained class, kept on a different argument from the other three:
    delegation cannot authorise the thing it would be a bypass OF."""
    result = disposition_for(
        phase="implement",
        verdict="BLOCKED",
        cause="the item names autonomous execution as the bypass its governance prevents",
    )

    assert result.disposition is Disposition.RETAIN_FOR_PERSON
    assert result.decision_class == "governance"


def test_an_impediment_outranks_the_verdict() -> None:
    """A halt that is both a failing gate and a missing machine is a missing machine.

    Reading the delegable half first is exactly how the predecessor mechanism cleared an
    item that asks an operator to provision a host.
    """
    result = disposition_for(
        phase="implement",
        verdict="FAIL_HARD",
        cause="the integration test fails because no database credential is available",
    )

    assert result.disposition is Disposition.RETAIN_FOR_PERSON
    assert result.decision_class == "access"


# --------------------------------------------------------------------------------------
# The backstop: an impediment the regexes did not name, demonstrated instead of guessed.
# --------------------------------------------------------------------------------------

def test_an_item_the_queue_could_not_move_is_retained_on_evidence() -> None:
    """The honest answer to "what if the prose does not say it needs a machine?".

    Classifying free prose is guessing, and this kit has paid for a guessing classifier
    before. So the mechanism does not have to be right the first time: an item the queue
    returned to twice with no progress has DEMONSTRATED an impediment, which is a
    measurement rather than a match.
    """
    cause = "the build fails for a reason the slice cannot reach"

    first = disposition_for(phase="implement", verdict="FAIL", cause=cause, prior_returns=0)
    second = disposition_for(phase="implement", verdict="FAIL", cause=cause, prior_returns=1)
    third = disposition_for(phase="implement", verdict="FAIL", cause=cause, prior_returns=2)

    assert first.disposition is Disposition.RETURN_TO_QUEUE
    assert second.disposition is Disposition.RETURN_TO_QUEUE
    assert third.disposition is Disposition.RETAIN_FOR_PERSON
    assert third.decision_class == "unclassified"
    assert "twice" in third.reason or "2" in third.reason


def test_the_backstop_does_not_fire_on_a_fresh_cause() -> None:
    """The counter is per-cause, not per-item: an item that returns three times for three
    different reasons is a busy item, not a walled one."""
    result = disposition_for(
        phase="implement", verdict="FAIL", cause="a new and different failure", prior_returns=0
    )

    assert result.disposition is Disposition.RETURN_TO_QUEUE


# --------------------------------------------------------------------------------------
# What the mechanism must never produce.
# --------------------------------------------------------------------------------------

def test_no_input_produces_a_wait_in_place() -> None:
    """The span's whole promise: a phase may stop, but it may not hold the session.

    Both dispositions move the item OUT of the phase. `RETAIN_FOR_PERSON` puts it back in
    the registry behind a wall — the queue still advances to the next item.
    """
    for verdict in ("FAIL", "FAIL_HARD", "INVALID", "BLOCKED", "AWAITING_HUMAN", "NEEDS_FIXES"):
        # A blank cause is excluded on purpose: it raises, and
        # `test_an_empty_cause_is_a_caller_bug_not_a_disposition` owns that contract.
        for cause in ("a credential is missing", "the gate failed", "unclear"):
            result = disposition_for(phase="implement", verdict=verdict, cause=cause)
            assert result.disposition in tuple(Disposition)
            assert result.returns_item_to_registry, (verdict, cause)


def test_an_empty_cause_is_a_caller_bug_not_a_disposition() -> None:
    """A halt with nothing written on it cannot be classified and must not be guessed.

    This raises rather than returning a verdict: it is a bug at the call site — the phase
    knows why it stopped — and swallowing it would file items whose evidence is blank.
    """
    with pytest.raises(ValueError, match="cause"):
        disposition_for(phase="implement", verdict="FAIL", cause="   ")


def test_a_phase_outside_the_span_is_refused() -> None:
    """BRAINSTORM is the phase a person attends, and BACKLOG intake is the human's own.

    Handing either to this mechanism would be a category error: there is no autonomous
    disposition to compute, because waiting for a person is the correct behaviour there.
    """
    with pytest.raises(ValueError, match="span"):
        disposition_for(phase="brainstorm", verdict="AWAITING_REVIEW", cause="nobody signed")
