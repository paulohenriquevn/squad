"""A summary row that names the gate by id is covered by it.

THE DEFECT THIS CLOSES
----------------------
`check_gate_mechanisms.py` sweeps two things: the `## Hard gates` section of each cycle
rule, and the `Hard gate` column of each phase-contract table. The second sweep landed
on 2026-09-17 and reported **42 rows naming no enforcer**, which read as 42 gates
nobody computes.

Most of them are not. A phase-contract table is a SUMMARY — one line per phase, saying
what it takes and what holds it — and the gate itself is declared below, with an id and
a mechanism. `cycle-brainstorm.md` is the clearest case: G-B1 to G-B5 each name
`score_product_alignment.py` in the `## Hard gates` table, and the five summary rows
above say `(G-B1)`, `(G-B2)`, `(G-B3)`, `(G-B4, G-B5)`. The executor is named, once,
where the gate is defined — and the auditor did not follow the reference.

Reporting those as unenforced does two kinds of damage. It buries the rows that really
have no mechanism among rows that do, and it makes `--strict-phase-rows` unusable: a
flag that would fail the build on 42 findings, most of them false, is a flag nobody
turns on.

WHAT THIS DOES NOT LOOSEN
-------------------------
The id must be DECLARED in the same rule, and the gate it names must itself carry a
mechanism or a justified exemption. A row citing `(G-Z9)`, which nothing declares, is
still a row with no enforcer — and so is a row citing a gate that is itself unmechanized.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "mechanisms" / "gates"))
sys.path.insert(0, str(REPO))

from check_gate_mechanisms import check_gate_mechanisms  # noqa: E402


def _rule(tmp_path: Path, body: str) -> Path:
    rules = tmp_path / "rules"
    rules.mkdir(exist_ok=True)
    (rules / "cycle-demo.md").write_text(body, encoding="utf-8")
    mechanisms = tmp_path / "mechanisms" / "gates"
    mechanisms.mkdir(parents=True, exist_ok=True)
    (mechanisms / "check_demo.py").write_text(
        'if __name__ == "__main__":\n    pass\n', encoding="utf-8")
    return tmp_path


DECLARED = """# Cycle: DEMO

## Phase contracts

| Phase | Input | Output | Hard gate |
|---|---|---|---|
| one | a | b | the thing holds (G-X1) |

## Hard gates

| # | Gate | Blocks on |
|---|---|---|
| G-X1 | **The thing holds** (`check_demo.py`) | it does not hold |
"""


def _rows(root: Path) -> list:
    return check_gate_mechanisms(root).phase_rows_without_mechanism


def test_a_row_citing_a_declared_mechanised_gate_is_covered(tmp_path: Path) -> None:
    root = _rule(tmp_path, DECLARED)

    assert _rows(root) == [], (
        "the row names G-X1, which is declared below and names its script — the "
        "executor is named once, where the gate is defined")


def test_a_row_citing_an_id_nobody_declares_is_still_reported(tmp_path: Path) -> None:
    root = _rule(tmp_path, DECLARED.replace("(G-X1)", "(G-Z9)"))

    assert len(_rows(root)) == 1


def test_a_row_citing_a_gate_that_is_itself_unmechanised_is_reported(tmp_path: Path) -> None:
    body = DECLARED.replace("| G-X1 | **The thing holds** (`check_demo.py`) | it does not hold |",
                            "| G-X1 | **The thing holds** | it does not hold |")
    root = _rule(tmp_path, body)

    assert len(_rows(root)) >= 1, (
        "following the reference must not launder a gate that names no mechanism "
        "of its own")


def test_a_row_naming_nothing_at_all_is_reported(tmp_path: Path) -> None:
    root = _rule(tmp_path, DECLARED.replace("the thing holds (G-X1)", "the thing holds"))

    assert len(_rows(root)) == 1
