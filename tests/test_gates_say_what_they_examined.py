"""A gate that examined nothing must not print a verdict about everything.

This kit's most-found defect, by a wide margin, is an inability to measure
published as a measurement: a glob that lost its reach, a matcher pointed at a
renamed directory, a launcher that never looked. Every instance had the same
tell — a clean report over an empty sweep.

Measured on 2026-09-02, running every root-taking gate against an empty tree:
five of six said what they had swept ("swept 0 cycle rule(s)", "0 declared
phase(s)", "study zone absent or empty — nothing to compare against"). One
printed *"Overall: PASS — every cycle's declared numbering is unique and in chain
order"* after examining zero cycles.

This holds all of them to the honest five's standard, and any gate added later
inherits it without anyone remembering to.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

_GATES = Path(__file__).resolve().parent.parent / "mechanisms" / "gates"

#: The flag each gate takes for the tree it should look at. A gate absent here
#: takes no root and is skipped — see `test_the_roster_covers_every_gate_that_takes_a_root`.
ROOT_FLAG = {
    "check_english_only": "--root",
    "check_install_drift": "--install",
    "check_gate_mechanisms": "--repo",
    "check_mechanisms_inventory": "--root",
    "check_orphan_verdicts": "--repo",
    "check_phase_emitters": "--repo",
    "check_phase_numbering": "--root",
    "check_reference_leakage": "--repo",
    "check_semantic_names": "--repo",
    "check_skill_map": "--root",
    "check_squad_map": "--root",
    "check_wiki_migration": "--root",
}

#: Ways a gate can say "there was nothing here". Deliberately generous: the point
#: is that SOMETHING in the output distinguishes an empty sweep from a clean one,
#: not that every gate phrases it alike.
_SAYS_NOTHING_SWEPT = re.compile(
    r"\b0\s+\w|\bnothing\b|\bempty\b|\babsent\b|\bskip\b|\bnot a directory\b|"
    r"\bno \w+ (found|declared|present)\b|\bunreadable\b|FATAL",
    re.IGNORECASE)


@pytest.mark.parametrize("gate,flag", sorted(ROOT_FLAG.items()))
def test_an_empty_tree_produces_a_report_that_says_it_was_empty(
        gate: str, flag: str, tmp_path: Path) -> None:
    """Whatever the verdict, the output must let a reader tell an empty sweep
    from a clean one. A gate silent about its own reach is a gate whose next
    broken glob nobody notices."""
    done = subprocess.run(
        [sys.executable, str(_GATES / f"{gate}.py"), flag, str(tmp_path)],
        capture_output=True, text=True, timeout=120, check=False)
    output = done.stdout + done.stderr

    assert _SAYS_NOTHING_SWEPT.search(output), (
        f"{gate} reported on an empty tree without saying it was empty:\n{output[:600]}")


@pytest.mark.parametrize("gate,flag", sorted(ROOT_FLAG.items()))
def test_no_gate_claims_a_universal_property_over_an_empty_sweep(
        gate: str, flag: str, tmp_path: Path) -> None:
    """"every X is Y" said of zero X is the sentence this test exists for."""
    done = subprocess.run(
        [sys.executable, str(_GATES / f"{gate}.py"), flag, str(tmp_path)],
        capture_output=True, text=True, timeout=120, check=False)
    output = done.stdout + done.stderr

    for line in output.splitlines():
        if re.search(r"\bPASS\b", line) and re.search(r"\bevery\b|\ball\b", line,
                                                      re.IGNORECASE):
            assert re.search(r"\b[1-9]\d*\s+\w", line), (
                f"{gate} claims a universal property with no count behind it "
                f"on an empty tree:\n  {line}")


def test_the_roster_covers_every_gate_that_takes_a_root() -> None:
    """A gate added later must not opt out of this by being forgotten."""
    missing = []
    for path in sorted(_GATES.glob("check_*.py")):
        helped = subprocess.run([sys.executable, str(path), "--help"],
                                capture_output=True, text=True, timeout=60, check=False)
        flags = set(re.findall(r"--(root|repo|install)\b", helped.stdout))
        if flags and path.stem not in ROOT_FLAG:
            missing.append(f"{path.stem} (takes --{sorted(flags)[0]})")

    assert not missing, f"gates taking a root but absent from the roster: {missing}"
