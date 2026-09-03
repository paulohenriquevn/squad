"""Idle lanes are not evidence of a healthy queue.

Measured on 2026-09-02: the remote fleet ran THIRTEEN autonomous rounds and
dispatched NOTHING. Zero items reached a lane. Every round was correct — the
consumer's queue was legitimately BACKLOG_BLOCKED, with 14 items waiting on human
decisions, and the kit's own registry was clean because its issues had all been
closed. The lead refused to schedule anything, which is exactly right.

And three lanes sat at a prompt for over two hours.

Governance without production is half a fleet. The brief now carries a sixth
branch for the case where both queues are empty: auditing the kit for the defects
it keeps shipping — the one source of work that does not run out and does not
wait on a person.
"""
from __future__ import annotations

import re
from pathlib import Path

_BRIEF = (Path(__file__).resolve().parent.parent / "mechanisms" / "fleet"
          / "start_lead_session.sh")


def _brief_text() -> str:
    """The prompt the lead is actually given, not the script around it."""
    text = _BRIEF.read_text(encoding="utf-8")
    match = re.search(r"read -r -d '' BRIEF <<'PROMPT'\n(.*?)\nPROMPT", text, re.S)
    assert match, "the brief heredoc has moved"
    return match.group(1)


def _prose() -> str:
    """The brief as one line. Its sentences wrap, and an assertion that reads a
    rendering rather than the text breaks on reflow — which has already cost this
    suite two false failures today."""
    return " ".join(_brief_text().split())


def test_an_idle_lane_has_somewhere_to_go() -> None:
    """Without this the lead's only honest move on an empty queue is to stop, and
    it stopped thirteen times."""
    brief = _brief_text()

    assert "kit_audit_workflow" in brief, \
        "the brief names no work for a lane when both queues are empty"


def test_the_consumers_backlog_still_wins() -> None:
    """A fleet that prefers auditing itself to shipping the product is worse than
    an idle one — it looks busy."""
    brief = _brief_text()

    assert "backlog wins whenever it has anything" in _prose()
    assert "Never let this crowd out" in _prose()


def test_an_audit_finding_does_not_authorise_touching_the_consumer() -> None:
    """The audit is about the kit. Finding something in the kit is not a reason to
    edit the project the fleet is deployed against."""
    assert "not a reason to touch the consumer" in _prose()


def test_a_finding_needs_evidence_and_refutation_before_it_becomes_an_issue() -> None:
    """Otherwise idle lanes produce a backlog of impressions, and the next reader
    learns to skim them."""
    brief = _brief_text()

    assert "refute" in brief
    assert "not an impression" in _prose()


def test_the_measurement_that_motivated_it_is_in_the_brief() -> None:
    """The lead reads this every time it starts. A rule with its reason attached
    survives a rewrite; one without it gets trimmed as boilerplate."""
    brief = _brief_text()

    assert "THIRTEEN rounds" in brief and "dispatched" in brief.upper() or "NOTHING" in brief
    assert "Idle lanes are not evidence of a healthy queue" in _prose()
