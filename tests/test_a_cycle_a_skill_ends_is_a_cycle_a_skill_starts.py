"""A phase a skill closes is a phase some skill opened.

`tests/test_a_phase_that_ends_also_began.py` holds this for the four PROGRAMMATIC
emitters and says so in its own words: *"A skill that instructs the CLI is a
different mechanism and is covered by its own prose test."* That prose test did not
exist, and the gap was not theoretical — it is the exact stream that test quotes:

    38 events
     1 cycle:phase:start   (brainstorm, never closed)
    37 cycle:phase:end

`brainstorm` then acquired three MORE ends: four skills emitted
`end --cycle brainstorm --slug {scope}` against one start, for one cycle that
`rules/cycle-phases.txt` declares ONCE. Nothing derived from the pair — WIP, lead
time, whether a session is open right now — is computable from four closes of a
phase that opened once, and the cycle it happened to is the only one a person
attends.

`design` had the other half of the same defect: an end, and no start anywhere.

What this test does NOT check: that the pair is balanced at runtime. A session
abandoned mid-cascade SHOULD leave an open start — that is WIP, and the board is
supposed to show it.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]

#: `cycle_events.py <transition> … --cycle <name>`, across the line breaks a shell
#: snippet uses. Stops at the blank line or fence that ends the command.
_CALL_RE = re.compile(
    r"cycle_events\.py\"?\s+(start|end)\b((?:.|\n)*?)(?=\n\s*\n|```)")
_CYCLE_RE = re.compile(r"--cycle\s+(\S+)")


def _calls() -> dict[str, dict[str, list[str]]]:
    """{cycle: {"start": [skill, …], "end": [skill, …]}} over every SKILL.md."""
    found: dict[str, dict[str, list[str]]] = {}
    for skill in sorted(_ROOT.glob("skills/*/SKILL.md")):
        text = skill.read_text(encoding="utf-8")
        for match in _CALL_RE.finditer(text):
            cycle = _CYCLE_RE.search(match.group(2))
            if not cycle:
                continue
            found.setdefault(cycle.group(1), {}).setdefault(
                match.group(1), []).append(skill.parent.name)
    return found


_CALLS = _calls()


def test_the_scan_found_the_call_sites() -> None:
    """A regex that matched nothing would make every assertion below vacuous."""
    assert len(_CALLS) >= 5, _CALLS


@pytest.mark.parametrize("cycle", sorted(_CALLS))
def test_a_cycle_that_ends_in_a_skill_also_starts_in_one(cycle: str) -> None:
    transitions = _CALLS[cycle]
    if not transitions.get("end"):
        pytest.skip(f"`{cycle}` is started by a skill and ended elsewhere")
    assert transitions.get("start"), (
        f"`{cycle}` is ended by {transitions['end']} and started by no skill. An end "
        f"says something finished; without a start nothing can say when it began, "
        f"or that it was ever running.")


@pytest.mark.parametrize("cycle", sorted(_CALLS))
def test_one_cycle_closes_once_per_run(cycle: str) -> None:
    """One declared phase, one close.

    Four skills closing `brainstorm` are not four phases: `rules/cycle-phases.txt`
    declares it once, and `check_phase_drift.py` groups the stream by slug — so the
    four arrive as four closes of the same phase of the same scope. The cascade's
    intermediate steps hand off to each other; only the last one ends the phase.
    """
    ends = _CALLS[cycle].get("end", [])
    assert len(ends) <= 1, (
        f"`{cycle}` is closed by {len(ends)} skills ({', '.join(sorted(ends))}). "
        f"A phase declared once ends once — the steps before the last one hand off, "
        f"they do not close.")
