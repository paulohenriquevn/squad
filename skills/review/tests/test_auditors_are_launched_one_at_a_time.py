"""The auditor step states how N halt-loops are launched in one session.

Step 2b said "Run each command the assignment prints, exactly as printed" and nothing
about order. Each command is a halt-loop driven by its plugin's Stop hook, and every
active hook advances its own iteration counter on turns spent on the other loops —
so launching the setups back to back gives each auditor a share of one ceiling
(reported 2026-09-23: three state files `active: true` at once in a scratch repo).
No plugin guards against it, so the order is the skill's to state.

What is pinned is what an agent following the step would observe: that loops run
one at a time, that the next waits for the previous `final_report.md` and for no
`*-loop.local.md` still active, that a loop is never handed to a sub-agent (Stop
hooks do not fire there), and how the review resumes afterwards.
"""
from __future__ import annotations

from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "SKILL.md"


def _auditor_step(text: str) -> str:
    """Step 2b, with line wrapping collapsed so a reflow cannot break a phrase."""
    start = text.index("### Step 2b")
    return " ".join(text[start:text.index("### Step 3", start)].split())


def test_the_auditor_step_launches_one_loop_at_a_time() -> None:
    step = _auditor_step(SKILL.read_text(encoding="utf-8"))

    assert "One auditor at a time" in step


def test_the_next_loop_waits_for_the_previous_report_and_state_file() -> None:
    step = _auditor_step(SKILL.read_text(encoding="utf-8"))

    assert "<output_dir>/final_report.md" in step
    assert "`.claude/*-loop.local.md` still says `active: true`" in step


def test_a_loop_is_never_handed_to_a_sub_agent() -> None:
    step = _auditor_step(SKILL.read_text(encoding="utf-8"))

    assert "Never delegate a loop to a sub-agent" in step


def test_the_step_says_where_the_review_resumes() -> None:
    step = _auditor_step(SKILL.read_text(encoding="utf-8"))

    assert "continue with Step 3 in the same session" in step
