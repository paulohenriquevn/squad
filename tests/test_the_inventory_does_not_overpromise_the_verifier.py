"""`mechanisms/README.md` said the verifier "runs the checks above".

"The checks above" is the 31 gate rows of the same table. `verify_ecosystem`'s roster
wires 24 of them, and the other 21 files are reached by CI, by hooks, or by a skill —
never by the verifier. A reader who ran `verify_ecosystem.py` and saw one green verdict
was told, by the row next to it, that every gate in the directory had just passed.

The row now states the subset and says where the rest run. This test compares the claim
against the roster, so the row cannot quietly go back to promising the whole table.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_GATES = _ROOT / "mechanisms" / "gates"


def _wired() -> set[str]:
    source = (_GATES / "verify_ecosystem.py").read_text(encoding="utf-8")
    return (set(re.findall(r'_gate_payload\([^,]+,\s*"(check_\w+)"', source))
            | set(re.findall(r'"(check_\w+)\.py"', source)))


def test_the_row_does_not_claim_to_run_every_gate() -> None:
    row = next(line for line in (_ROOT / "mechanisms" / "README.md")
               .read_text(encoding="utf-8").splitlines()
               if "`verify_ecosystem.py`" in line and line.startswith("|"))

    assert "runs the checks above" not in row, (  # prose-test: the claim IS the defect
        f"it runs {len(_wired())} of {len(list(_GATES.glob('check_*.py')))} gates: {row}")


def test_the_row_names_how_many_it_runs() -> None:
    row = next(line for line in (_ROOT / "mechanisms" / "README.md")
               .read_text(encoding="utf-8").splitlines()
               if "`verify_ecosystem.py`" in line and line.startswith("|"))

    assert "subset" in row.lower() or re.search(r"\b\d+\b", row), (
        "a reader cannot tell how much of the table one green verdict covers")
