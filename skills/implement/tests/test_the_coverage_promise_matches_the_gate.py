"""The contract promised two thresholds the gate does not enforce.

`SKILL.md` Step 5 listed "Coverage gate — >= 90% on changed files; 100% on critical
paths declared in plan". `coverage_gate.evaluate` compares ONE total against one
threshold, and `resolve_threshold`'s fallback is `DEFAULT_MIN_PERCENT = 80` — ten
points under the number the contract named.

`coverage_gate.py`'s own docstring said so ("this reads TOTAL line coverage. The
per-changed-file and critical-path thresholds in SKILL.md remain unenforced here"), so
the tool and the contract contradicted each other in writing, and the contract is the
one people read.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "skills" / "implement" / "scripts"))

import coverage_gate  # noqa: E402 — post-bootstrap import

_SKILL = (_ROOT / "skills" / "implement" / "SKILL.md").read_text(encoding="utf-8")


def test_the_contract_no_longer_promises_a_per_file_threshold() -> None:
    assert "≥ 90% on changed files; 100% on critical paths declared in plan" not in _SKILL


def test_the_contract_names_the_floor_the_gate_actually_applies() -> None:
    assert str(coverage_gate.DEFAULT_MIN_PERCENT) in _SKILL, (
        f"the gate's default floor is {coverage_gate.DEFAULT_MIN_PERCENT} and the "
        f"contract does not say so")


def test_the_unimplemented_half_is_declared_as_such() -> None:
    """A gap stated is a gap nobody reads the total as covering."""
    assert "not implemented" in _SKILL.lower()


def test_the_default_floor_is_what_the_resolver_returns(tmp_path: Path) -> None:
    percent, source = coverage_gate.resolve_threshold(tmp_path)

    assert percent == coverage_gate.DEFAULT_MIN_PERCENT
    assert source == "default", "a configured value must be distinguishable from a default"
