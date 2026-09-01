"""Every eval battery this kit ships can actually be loaded by its runner.

THE DEFECT THIS CLOSES
----------------------
All four batteries — `backlog-item`, `discover-plan`, `discover-edge-cases`,
`discover-execute` — are a dict of `{skill_name, notes, evals:[...]}`. `run_eval.py`
came from upstream expecting a LIST of `{query, should_trigger}`, so every one of
them died on `TypeError: string indices must be integers`, iterating the dict's keys
as if they were cases.

They had never been executed by anything. Meanwhile `check_intake_gates.py`
justified leaving gates G3/G4/G5 conversational because *"the eval battery covers
exactly that"* — a coverage claim resting on a file nothing could run.

Nothing detected it because loading a battery was never something a test did. This
is that test. It does not run the model: it asserts the batteries and the runner
agree about shape, which is the part that silently stopped being true.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BATTERIES = sorted(REPO.glob("skills/*/evals/evals.json"))


def _normalise():
    sys.path.insert(0, str(REPO / "skills" / "skill-creator" / "scripts"))
    from run_eval import _normalise_eval_set

    return _normalise_eval_set


def test_the_kit_ships_batteries_at_all() -> None:
    """Guards the guard: a glob that matches nothing would pass every test below."""
    assert BATTERIES, "no evals.json found — this test would silently check nothing"


@pytest.mark.parametrize("battery", BATTERIES, ids=lambda p: p.parents[1].name)
def test_a_battery_loads_into_runnable_cases(battery: Path) -> None:
    cases = _normalise()(json.loads(battery.read_text(encoding="utf-8")))

    assert cases, f"{battery.relative_to(REPO)} produced zero runnable cases"
    for case in cases:
        assert case["query"].strip(), "a case with an empty query runs nothing"
        assert isinstance(case["should_trigger"], bool)


@pytest.mark.parametrize("battery", BATTERIES, ids=lambda p: p.parents[1].name)
def test_no_case_is_dropped_in_translation(battery: Path) -> None:
    """The normaliser must not quietly discard cases it does not understand.

    Losing one would shrink the battery without failing anything — the same quiet
    shape as the battery that could not run at all.
    """
    raw = json.loads(battery.read_text(encoding="utf-8"))
    declared = raw["evals"] if isinstance(raw, dict) else raw
    assert len(_normalise()(raw)) == len(declared), (
        f"{battery.relative_to(REPO)}: cases were dropped while normalising"
    )
