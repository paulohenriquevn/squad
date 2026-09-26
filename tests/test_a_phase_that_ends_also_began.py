"""Thirty-seven ends, one start, and nothing measurable about flow.

`cycle_events.emit_phase_start` has existed since the stream did. Nothing calls it: the
four programmatic emitters — code-quality, review, implement, acceptance — each call
`emit_phase_end` and none calls its sibling.

Measured on one consumer, 2026-09-18:

    38 events
     1 cycle:phase:start   (brainstorm, never closed)
    37 cycle:phase:end

An `end` says something finished. It does not say when it began, or that it was ever
running. Everything a person opens a board to ask is derived from the pair:

    a column marked `working`      needs a start with no end
    WIP right now                  needs open starts
    WIP over time                  needs start–end pairs placed on a clock
    lead time per phase            needs end minus start
    the minimum WIP that keeps
      the system from idling       needs the WIP series

`code-quality` emitted 29 ends against one slug. Without starts there is no way to know
whether that was 29 runs or 29 reports of the same one — and the difference is exactly
what WIP measures.

This test holds the pair. It does not check that the numbers are right; it checks that
the fact needed to compute them is recorded at all.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]

#: The scripts that record a phase transition on the system's behalf. A skill that
#: instructs the CLI is a different mechanism and is covered by its own prose test.
_EMITTERS = (
    "skills/code-quality/scripts/run_code_quality.py",
    "skills/review/scripts/consolidate_findings.py",
    "skills/implement/scripts/run_validation.py",
    "skills/acceptance/scripts/compute_acceptance_verdict.py",
)


@pytest.mark.parametrize("rel", _EMITTERS)
def test_an_emitter_that_records_an_end_records_a_start(rel: str) -> None:
    """Both halves, in the same file. One without the other is a duration nobody can
    compute."""
    source = (_ROOT / rel).read_text(encoding="utf-8")

    ends = len(re.findall(r"\bemit_phase_end\b", source))
    starts = len(re.findall(r"\bemit_phase_start\b", source))

    assert ends, f"{rel} no longer emits an end; this test needs re-pointing"
    assert starts, (
        f"{rel} records {ends} reference(s) to `emit_phase_end` and none to "
        f"`emit_phase_start`. An end with no start is a phase that finished and was "
        f"never running — the board cannot draw it, and WIP cannot be computed from it")


def test_the_emitter_helper_exists_for_both() -> None:
    """The function has been there all along; this is the check that it stays."""
    source = (_ROOT / "mechanisms" / "cycle" / "cycle_events.py").read_text(encoding="utf-8")

    assert "def emit_phase_start" in source
    assert "def emit_phase_end" in source
