"""In a SKILL.md, the start comes before the end.

THE DEFECT THIS CLOSES
----------------------
A SKILL.md is read top to bottom and executed in that order. `plan-write` carried the
`end` block on line 145 and the `start` block on line 161, under the instruction *"Emit
the START of this phase before doing the work"* — by which point the reader had already
been told to close the phase.

Two outcomes, both bad: the stream gets an `end` before its `start`, which is disorder
`check_phase_drift` reads by slug; or the start is never emitted at all, because the
reader followed the document and the moment it describes had passed.

Measured 2026-09-21 across every SKILL.md: one file had them in that order, and seven
had them the right way round. This keeps it that way.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SKILLS = sorted(REPO.glob("skills/*/SKILL.md"))

_TRANSITION_RE = re.compile(r'cycle_events\.py"?\s+(start|end)')


def _first_lines(text: str) -> dict[str, int]:
    seen: dict[str, int] = {}
    for match in _TRANSITION_RE.finditer(text):
        seen.setdefault(match.group(1), text[: match.start()].count("\n") + 1)
    return seen


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.parent.name)
def test_the_start_block_precedes_the_end_block(skill: Path) -> None:
    lines = _first_lines(skill.read_text(encoding="utf-8"))
    if "start" not in lines or "end" not in lines:
        pytest.skip("this skill emits only one half of the pair")

    assert lines["start"] < lines["end"], (
        f"{skill.relative_to(REPO)} tells the reader to close the phase on line "
        f"{lines['end']} and to open it on line {lines['start']}. The document is "
        f"executed in the order it is read")
