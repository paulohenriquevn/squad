"""A rule that names a mechanism names one the reader can invoke.

`check_gate_mechanisms.py` asks one question per declared gate — does this line
say what enforces it — and is explicit about the question it refuses:

    It does NOT verify that the named script actually enforces the gate. Proving
    that a given `.py` implements a given English sentence is not something a text
    scan can do.

That refusal is right. Between it and what the gate does check, though, sits a
question that IS decidable by a text scan and was not asked: **can the named
thing be run at all?**

Measured 2026-09-19 across the nine cycle rules: 22 mechanisms named under
`## Hard gates`, **6 of them modules with no `__main__`**. They are libraries,
composed by runners, and they are genuinely enforced — every one is imported by a
script that does have an entry point. But a reader who follows the rule to the
mechanism and runs it gets this:

    $ python3 skills/discover-confidence/scripts/check_evidence_pointers.py --root .
    $                      (no output, exit 0)

Silence and zero are what a passing gate looks like. The gate's own stated
purpose is that "the reader of a rule can reach the mechanism", and reaching a
library that exits 0 is reaching something indistinguishable from a pass — the
failure this repository names most often, arriving through the document that
exists to prevent it.

THE FIX IS THE LINE, NOT THE MODULE. Giving six libraries a CLI would make each
one runnable and each one a second entry point to a score that is only meaningful
composed. What the reader needs is the invocable name, so the rule names both: the
module that implements the gate, and the runner that executes it.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "mechanisms" / "gates"))

_RULES = sorted((_REPO / "rules").glob("cycle-*.md"))


def _hard_gate_section(text: str) -> str:
    match = re.search(r"^## Hard gates(.*?)(?=^## )", text, re.S | re.M)
    return match.group(1) if match else ""


def _resolve(script: str) -> Path | None:
    hits = [h for h in _REPO.glob(f"**/{script}")
            if "/tests/" not in str(h) and "/.git/" not in str(h)]
    return hits[0] if hits else None


def _runnable(path: Path) -> bool:
    return "__main__" in path.read_text(encoding="utf-8", errors="replace")


@pytest.mark.parametrize("rule", _RULES, ids=lambda p: p.name)
def test_every_gate_line_names_something_the_reader_can_run(rule: Path) -> None:
    """Per LINE, not per rule: a gate is reached one row at a time."""
    section = _hard_gate_section(rule.read_text(encoding="utf-8"))
    unreachable: list[str] = []
    for line in section.splitlines():
        scripts = re.findall(r"`([a-z_]+\.py)`", line)
        if not scripts:
            continue
        resolved = [(s, _resolve(s)) for s in scripts]
        if any(path is not None and _runnable(path) for _, path in resolved):
            continue
        named = ", ".join(s for s, _ in resolved)
        unreachable.append(f"{named} — none of them has an entry point")
    assert not unreachable, (
        f"{rule.name} names mechanisms a reader cannot invoke; running one prints "
        f"nothing and exits 0, which is what a pass looks like: {unreachable}")


def test_the_probe_itself_is_not_vacuous() -> None:
    """A sweep that examined no gate line would pass in silence.

    The defect this file reports IS a check that examined nothing and said
    nothing, so this test refuses to become one.
    """
    total = sum(len(re.findall(r"`([a-z_]+\.py)`", _hard_gate_section(
        r.read_text(encoding="utf-8")))) for r in _RULES)
    assert total >= 20, total


def test_the_gate_reports_it_rather_than_leaving_it_to_this_test() -> None:
    """A finding only a test knows is a finding no consumer ever sees.

    `check_gate_mechanisms.py` ships to every consumer; this file does not.
    """
    gate = _REPO / "mechanisms" / "gates" / "check_gate_mechanisms.py"
    proc = subprocess.run([sys.executable, str(gate), "--help"],
                          capture_output=True, text=True, check=False)
    assert "not_runnable" in (gate.read_text(encoding="utf-8")), (
        "the gate does not look for this, so it is caught here and nowhere a "
        "consumer runs")
    assert proc.returncode == 0, proc.stderr
