"""`<!-- BLOCKED: … -->` means one thing, and one module decides what.

THE DEFECT THIS CLOSES
----------------------
The marker excuses a pointer or a target that could not be resolved — a documented gap
rather than a fabrication. Its proximity rule was "within ~80 characters after the
match", and that window crosses newlines, so a marker on one list item absolved the item
ABOVE it. A Corner 1 is written as a list, so it fired on the ordinary shape.

Measured 2026-09-21, before and after, in `check_evidence_pointers`:

    src/real/thing.ts:3  alone                        -> verified=1
    the same, with a BLOCKED item on the next line    -> verified=0, blocked=2

That was fixed in one file. The same rule lived in two more — `check_measurement_targets`
carried a character-for-character copy of `_is_explicitly_blocked`, and `apply_opportunity_fixes`
inlined the same window — so the fix did not travel and the gate for measurement targets
kept absolving the target above a declared gap:

    `src/real/thing.ts` alone                         -> verified=1
    the same, with a BLOCKED item on the next line    -> verified=0, blocked=2

Three readers of one convention is three places for it to drift. `squad/blocked_marker.py`
owns it; this test refuses a second.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

READERS = (
    "skills/discover-confidence/scripts/check_evidence_pointers.py",
    "skills/discover-plan-confidence/scripts/check_measurement_targets.py",
    "skills/discover-improve/scripts/apply_opportunity_fixes.py",
)

#: A local BLOCKED pattern, or a local proximity window. The shared module defines both.
_LOCAL_MARKER = re.compile(r"re\.compile\([^)]*BLOCKED")
_LOCAL_WINDOW = re.compile(r"match(?:\.end\(\)|_end)\s*[:+]\s*match(?:\.end\(\)|_end)?\s*\+\s*\d+")


@pytest.mark.parametrize("rel", READERS)
def test_a_reader_does_not_define_the_marker_itself(rel: str) -> None:
    source = (REPO / rel).read_text(encoding="utf-8")

    assert not _LOCAL_MARKER.search(source), (
        f"{rel} compiles its own BLOCKED pattern — import squad.blocked_marker")


@pytest.mark.parametrize("rel", READERS)
def test_a_reader_does_not_invent_its_own_proximity_window(rel: str) -> None:
    source = (REPO / rel).read_text(encoding="utf-8")

    assert not _LOCAL_WINDOW.search(source), (
        f"{rel} carries a character-count window. It crossed newlines and absolved the "
        f"item above the marked one; the rule is the pointer's own line")


def test_the_marker_excuses_only_its_own_line() -> None:
    from squad.blocked_marker import is_blocked_at

    same_line = "- src/ghost.ts:9 <!-- BLOCKED: gone -->\n"
    next_line = "- src/real.ts:3\n- src/ghost.ts:9 <!-- BLOCKED: gone -->\n"

    assert is_blocked_at(same_line, same_line.index(":9") + 2)
    assert not is_blocked_at(next_line, next_line.index("real.ts:3") + len("real.ts:3"))


def test_a_marker_at_the_end_of_the_file_still_counts() -> None:
    """No trailing newline is the shape a generator leaves behind."""
    from squad.blocked_marker import is_blocked_at

    text = "src/ghost.ts:9 <!-- BLOCKED: gone -->"

    assert is_blocked_at(text, text.index(":9") + 2)
