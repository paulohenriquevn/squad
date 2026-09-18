"""An item blocked by another item was sent to a person, and there was nothing to decide.

`rules/autonomy-envelope.md § What the human owns` reserves the backlog — what is worth
doing and why. It does not reserve the ORDER in which the system works through it. An
item whose wall is another item in the same registry has no decision in it at all: the
answer is "finish the blocker first", and that is work, not judgement.

`classify_wall` had no class for it, so the wall fell through to `UNCLASSIFIED`, and
`rules/decision-delegation.txt § on_no_match = retain` sent it behind a wall addressed to
a person. Measured on one consumer, 2026-09-18, with six items held:

    [PERSON] UNCLASSIFIED  B-007 — the composition root is implemented, tested, and its
                           review is down to one BLOCKER … B-007's scheduler is a
                           production caller by construction

Nobody was ever going to decide that. It resolves when B-007 ships, and until then the
queue's own answer is to work B-007. The fail-safe is right about free prose and was
wrong about this, because this is not a decision that went unmatched — it is not a
decision.

The fail-safe itself is untouched. What changes is that one shape stops reaching it.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mechanisms" / "cycle"))

from delegated_decision import DecisionClass, classify_wall  # after the bootstrap above


def test_a_wall_naming_another_item_is_the_queues_own_work() -> None:
    """The verbatim shape from the consumer registry."""
    verdict = classify_wall(
        "B-007 — the composition root is implemented, tested, and its review is down to "
        "one BLOCKER: pillar (a) of the wiring triad, no production caller")

    assert verdict.delegated, (
        "an item waiting on another item was sent to a person; there is no decision in it")
    assert verdict.klass is DecisionClass.DEPENDENCY


def test_the_blocking_item_is_named_in_the_evidence() -> None:
    """The disposition is only actionable if it says WHICH item to work."""
    verdict = classify_wall("blocked by B-042 until its migration lands")

    assert "B-042" in verdict.evidence, (
        f"the verdict does not name the blocker: {verdict.evidence!r}")


def test_an_access_wall_still_reaches_a_person() -> None:
    """The half that must not go quiet. A tenant nobody has is not work the queue can
    do, and widening delegation must not swallow it."""
    verdict = classify_wall(
        "a work tenant is needed before Teams can be exercised end to end — personal "
        "Teams has no app catalog, so a custom bot cannot be installed")

    assert not verdict.delegated, "an access impediment was handed to the system"


def test_free_prose_with_no_item_id_is_still_retained() -> None:
    """`on_no_match = retain` is untouched. One shape stops reaching it; the rule does not
    move."""
    verdict = classify_wall("waiting on something nobody wrote down")

    assert not verdict.delegated
    assert verdict.klass is DecisionClass.UNCLASSIFIED


def test_a_scope_decision_in_ordinary_prose_is_recognised() -> None:
    """`scope\\s+(decision|call)` demanded the words adjacent. A person writing a wall
    does not: "committed scope is a decision nobody has taken" is the same class and
    matched nothing, so the sponsor's own delegation never applied to it."""
    verdict = classify_wall(
        "how much terminal parity is committed scope is a decision nobody has taken")

    assert verdict.delegated, "a scope decision in natural prose was retained"
    assert verdict.klass is DecisionClass.SCOPE
