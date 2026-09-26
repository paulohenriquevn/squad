"""The 90% floor is stated once and read, never restated.

`cycle-brainstorm.md` G-B4 claims it already works this way:

    The figure and its reasoning are `skills/_kit-rules/alignment-threshold.md`;
    this cycle reuses them rather than choosing a second number for the same
    purpose.

Measured 2026-09-19, there were three statements of it and no reuse:

    skills/_kit-rules/alignment-threshold.md        prose, the reasoning
    plan-alignment/scripts/score_alignment.py:80    THRESHOLD = 0.90
    brainstorm-pieces/.../score_product_alignment.py:67   FLOOR_PCT = 90.0

Not even the same type — a fraction against a percentage — so a change to one
could not be made mechanically in the other, and nothing would report the
disagreement. They agree today by coincidence, which is the condition a
coincidence is in right before it ends.

`squad/rubric.py` already carries this argument for the parse that reads a rubric,
in its own words: "Three copies of one parse is three places for the convention to
drift, and the drift would be silent... The skills already import `squad.paths`
for the same reason, so this is the place they can all reach." The number the
rubric is graded against belongs beside it.

The prose file keeps the REASONING — why 90 and why a score at all — because that
is what a person needs and what no constant can hold. What moves is the figure.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from squad.rubric import ALIGNMENT_FLOOR_PCT, ALIGNMENT_FLOOR_RATIO  # noqa: E402

_SCORERS = (
    "skills/plan-alignment/scripts/score_alignment.py",
    "skills/brainstorm-pieces/scripts/score_product_alignment.py",
)


def test_the_owner_states_it_once_in_both_shapes() -> None:
    """Two spellings of one number, derived, so they cannot drift apart."""
    assert ALIGNMENT_FLOOR_PCT == 90.0
    assert ALIGNMENT_FLOOR_RATIO == pytest.approx(0.90)
    assert ALIGNMENT_FLOOR_RATIO == ALIGNMENT_FLOOR_PCT / 100


@pytest.mark.parametrize("rel", _SCORERS)
def test_a_scorer_reads_the_floor_rather_than_restating_it(rel: str) -> None:
    text = (_REPO / rel).read_text(encoding="utf-8")
    assert "from squad.rubric import" in text, f"{rel} does not ask who owns the floor"
    # The literal, in code. Prose that explains "90% of the maximum" is the
    # documentation working; a second assignment is a second definition.
    assignments = re.findall(r"^\s*[A-Z_]+\s*=\s*(?:0\.90|90\.0|90)\s*$", text, re.MULTILINE)
    assert not assignments, f"{rel} restates the floor: {assignments}"


def test_the_reasoning_stays_where_a_person_reads_it() -> None:
    """Moving the figure must not move the argument for it.

    A constant cannot hold "90% is the figure the Definition-of-Ready literature
    uses"; a rule file cannot be imported. Each keeps the half it can carry.
    """
    prose = (_REPO / "skills" / "_kit-rules" / "alignment-threshold.md").read_text(
        encoding="utf-8")
    assert "Why 90%" in prose, "the reasoning left with the number"


def test_both_scorers_agree_on_the_bar_they_apply() -> None:
    """Asserted through the modules, not through the files that define them."""
    sys.path.insert(0, str(_REPO / "skills" / "plan-alignment" / "scripts"))
    sys.path.insert(0, str(_REPO / "skills" / "brainstorm-pieces" / "scripts"))
    import score_alignment
    import score_product_alignment

    assert score_alignment.THRESHOLD == ALIGNMENT_FLOOR_RATIO
    assert score_product_alignment.FLOOR_PCT == ALIGNMENT_FLOOR_PCT
    assert score_alignment.THRESHOLD * 100 == score_product_alignment.FLOOR_PCT
