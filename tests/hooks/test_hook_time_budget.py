"""A hook killed by the runtime is the one failure it cannot report.

Every other way these hooks fail to measure is recorded: `_GIT_UNREACHABLE`,
`_GATE_UNREACHABLE`, the broken-install warning. Being killed at the declared
timeout is different — the process is gone, so nothing writes the note, and a
`stop-validation` that dies takes the secrets blocker with it silently.

That is not fixable from inside once it happens; it is avoidable by arithmetic.
A hook whose own subprocess may run for as long as the hook is allowed to live
has no margin for the work around it: `stop-validation` calls git up to six times
besides the leakage scan, and `post-edit-check` runs two linters in sequence.

The budgets are read from the modules rather than from their text, so the check
measures what runs. Hooks name them `*_TIMEOUT`; a hook that spawns a subprocess
and declares none is the case this file refuses, because an undeclared budget is
one nobody balanced against the runtime's.
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _declared_timeouts() -> dict[str, int]:
    """What `hooks.json` gives each hook, keyed by script name."""
    wiring = json.loads((REPO / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    found = {}
    for groups in wiring["hooks"].values():
        for group in groups:
            for hook in group["hooks"]:
                name = re.search(r"([a-z-]+\.py)", hook["command"])
                if name:
                    found[name.group(1)] = hook["timeout"]
    return found


def _load(script: str):
    spec = importlib.util.spec_from_file_location(
        f"budget_{script.replace('-', '_').removesuffix('.py')}", REPO / "hooks" / script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _internal_budgets(module) -> dict[str, int]:
    return {name: value for name, value in vars(module).items()
            if name.endswith("_TIMEOUT") and isinstance(value, int)}


#: Hooks that shell out, and how many calls run one after another in the worst
#: path through them. `stop-validation`: the leakage scan plus six git calls.
#: `post-edit-check`: `check_go` runs `go vet` then `gofmt`.
SEQUENTIAL_CALLS = {"stop-validation.py": 7, "post-edit-check.py": 2,
                    "sessionstart-context.py": 5, "validate-command.py": 3}


@pytest.mark.parametrize("script", sorted(SEQUENTIAL_CALLS))
def test_a_hook_that_shells_out_declares_what_it_spends(script: str) -> None:
    """An undeclared budget is one nobody balanced against the runtime's."""
    budgets = _internal_budgets(_load(script))
    assert budgets, (
        f"{script} spawns subprocesses and declares no `*_TIMEOUT` constant, so "
        f"nothing relates what it spends to the {_declared_timeouts()[script]}s "
        f"hooks.json gives it")


@pytest.mark.parametrize("script", sorted(SEQUENTIAL_CALLS))
def test_no_subprocess_may_outlive_the_hook_that_spawned_it(script: str) -> None:
    budget = _declared_timeouts()[script]
    over = {n: v for n, v in _internal_budgets(_load(script)).items() if v >= budget}

    assert not over, (
        f"{script} is given {budget}s by hooks.json and grants a subprocess "
        f"{over} — at that point the runtime kills the hook mid-check and no "
        f"record of the check is written anywhere")


@pytest.mark.parametrize("script", sorted(SEQUENTIAL_CALLS))
def test_the_worst_sequential_path_fits_with_room_to_report(script: str) -> None:
    """Fitting one call is not the question; the calls run one after another."""
    budget = _declared_timeouts()[script]
    budgets = _internal_budgets(_load(script))
    worst = max(budgets.values()) + (SEQUENTIAL_CALLS[script] - 1) * min(budgets.values())

    assert worst < budget, (
        f"{script}: the worst path spends {worst}s of a {budget}s budget "
        f"({SEQUENTIAL_CALLS[script]} sequential calls, budgets {budgets})")
