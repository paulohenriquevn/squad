"""The measurability detector missed the comparison sign the kit's own documents use.

`MEASURABLE_PATTERNS` matched `[<>]=?\\s*\\d` — so `<= 500` counted and `≤ 500` did not, while
`plan-template.md` and every golden rule in this kit write `≤ 60 lines`, `≤ 500 LoC`,
`complexity ≤ 10`. Two more misses of the same kind: the exit-code pattern required `exit ` and
a criterion saying `exits 0` was not matched, and `LoC` was absent from the unit list.

Found on 2026-09-23 by widening `SECTION_HEADER_RE` so that a plan's `#### DoD` was finally
seen (#175's sibling). The kit's own `good-plan.md` fixture then fired
`vague_acceptance_criteria` with `vague_ratio 0.00` and `acceptable_ratio 0.69`, and the four
bullets below the bar were:

    verb=True obj=False   Unit test exits 0 asserting both branches
    verb=True obj=False   cargo clippy passes (lint, complexity ≤ 10)
    verb=True obj=False   All files ≤ 500 LoC
    verb=True obj=False   Merged with commit subject referencing the task ID

Three of the four are the detector's, and only the last is the fixture's. The first response was
to stop grading DoD bullets, then to rewrite the fixture; measuring which side was wrong settled
it a third way, and that is why this file exists rather than a fixture edit.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_ROOT / "skills" / "plan-confidence" / "scripts"))

from check_criterion_executability import _has_measurable_object  # noqa: E402


@pytest.mark.parametrize("text", [
    "All files ≤ 500 LoC",
    "complexity ≤ 10",
    "latency ≥ 2 requests",
    "p95 ≤ 800 ms",
])
def test_a_unicode_comparison_is_measurable(text: str) -> None:
    assert _has_measurable_object(text), (
        f"`{text}` carries a comparison the kit's own documents write, and the detector reads "
        f"only the ASCII form")


@pytest.mark.parametrize("text", ["the command exits 0", "it exits code 1", "exit 0"])
def test_an_exit_code_is_measurable_however_the_verb_is_inflected(text: str) -> None:
    assert _has_measurable_object(text), f"`{text}` names an exit code and was not matched"


@pytest.mark.parametrize("text", ["file is ≤ 500 LoC", "module under 300 loc", "diff of 40 lines"])
def test_a_line_count_is_a_unit(text: str) -> None:
    assert _has_measurable_object(text), f"`{text}` states a line count and was not matched"


@pytest.mark.parametrize("text", [
    "Improve testing",
    "Merged with commit subject referencing the task ID",
    "make the code better",
])
def test_prose_with_no_number_is_still_not_measurable(text: str) -> None:
    """The control. Widening a detector that then accepts everything measures nothing."""
    assert not _has_measurable_object(text), f"`{text}` has nothing to measure and was accepted"
