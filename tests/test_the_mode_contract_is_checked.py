"""A mode declares what counts as evidence. G-M is what holds it to that.

THE DEFECT THIS CLOSES
----------------------
`cycle-discover.md` is categorical: **"`bug` has a hard floor: no failing test, no
bug."** G-M promises to block *"The mode's mandatory evidence is incomplete — most often
`bug` without a failing test."*

`check_opportunity_completeness.py` verified that the line `**Mode:**` exists and carries
one of four tokens. Nothing verified the evidence the mode demands. Measured 2026-09-21
on an opportunity declaring `**Mode:** bug` whose Corner 1 says, in words, *"No test
written yet — the shape is obvious enough from the repro"*:

    opportunity_completeness: 100.0
    weighted_avg:             100.0
    hard_caps_triggered:      ['soft_floor_evidence_density_low']

WHAT IS CHECKED, AND WHY IT IS A MARKER RATHER THAN A GUESS
-----------------------------------------------------------
A mode's evidence is prose, and a regex hunting for "the test fails" would produce
verdicts about language — the thing this kit refuses in G3, G4 and G5. So `bug` declares
its floor STRUCTURALLY, the way the sign-off declares a signature:

    **Failing test:** path/to/test_file.py::test_name

The checker asks whether the line is there and whether the file resolves. Whether the
test genuinely fails is what `/discover-execute` runs and the panel judges; what this
gate refuses is the opportunity that never names one.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCORER = REPO / "skills" / "discover-confidence" / "scripts" / "run_opportunity_score.py"
FIXTURE = REPO / "skills" / "discover-confidence" / "fixtures" / "good-opportunity.md"


def _opportunity(tmp_path: Path, *, mode: str, extra_header: str = "",
                 corner_one: str | None = None) -> Path:
    src = FIXTURE.read_text(encoding="utf-8")
    src = src.replace("**Mode:** review", f"**Mode:** {mode}{extra_header}", 1)
    if corner_one is not None:
        start = src.index("## Corner 1 — Evidence")
        end = src.index("## Corner 2 — Constraint Relation")
        src = src[:start] + corner_one + src[end:]
    (tmp_path / ".git").mkdir(exist_ok=True)
    path = tmp_path / "opportunity.md"
    path.write_text(src, encoding="utf-8")
    return path


def _score(path: Path) -> dict:
    proc = subprocess.run([sys.executable, str(SCORER), str(path), "--no-warn"],
                          capture_output=True, text=True, cwd=path.parent)
    return json.loads(proc.stdout[proc.stdout.index("{"):])


def _failing_test(tmp_path: Path) -> str:
    target = tmp_path / "tests" / "test_runs.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("def test_list_survives_refresh():\n    assert False\n", encoding="utf-8")
    return "tests/test_runs.py::test_list_survives_refresh"


def test_a_bug_that_names_no_failing_test_is_capped(tmp_path: Path) -> None:
    report = _score(_opportunity(tmp_path, mode="bug"))

    assert "mode_contract_unmet" in report["hard_caps_triggered"], (
        "the contract says no failing test, no bug — and nothing asked for one")


def test_a_bug_naming_a_failing_test_that_resolves_passes(tmp_path: Path) -> None:
    header = f"\n**Failing test:** `{_failing_test(tmp_path)}`"

    report = _score(_opportunity(tmp_path, mode="bug", extra_header=header))

    assert "mode_contract_unmet" not in report["hard_caps_triggered"]


def test_a_bug_naming_a_test_file_that_does_not_exist_is_capped(tmp_path: Path) -> None:
    header = "\n**Failing test:** `tests/test_ghost.py::test_nothing`"

    report = _score(_opportunity(tmp_path, mode="bug", extra_header=header))

    assert "mode_contract_unmet" in report["hard_caps_triggered"], (
        "a test file nobody wrote is the fabricated-evidence shape, one field along")


@pytest.mark.parametrize("mode", ["review", "live-test", "evolve"])
def test_the_other_modes_are_not_asked_for_a_failing_test(tmp_path: Path, mode: str) -> None:
    """The floor belongs to `bug`. Demanding it elsewhere would invent a contract the
    cycle rule does not state."""
    report = _score(_opportunity(tmp_path, mode=mode))

    assert "mode_contract_unmet" not in report["hard_caps_triggered"]
