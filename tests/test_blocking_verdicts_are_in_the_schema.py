"""A verdict that stops an item, and no entry in the vocabulary that defines verdicts.

`cycle-rule-schema.md` closes its matrix with: *"Do NOT introduce a new verdict token
without adding it to this matrix."* `blocking-verdicts.txt` is the narrower list of
verdicts that hold an item where it is, read by `check_phase_drift.py` and
`board_state.py`. Every token on the second list is by definition a verdict, so it
must appear on the first.

Measured 2026-09-07: four did not. The one that matters is `AWAITING_HUMAN` — the
most widely used pause token in the kit, declared in the `## Verdicts` section of
`cycle-plan.md` and `cycle-release.md` with **"Emit it."** in bold, named in six of
the twelve contracts, carrying the B-058/B-059 measurement that put it in
`blocking-verdicts.txt` — and absent from the canonical matrix. A reader learning the
vocabulary from the schema would not know the token exists; a reader learning it from
the contracts would not know it blocks.

`FAIL`, `INVALID_AWAITING_HUMAN` and `NEEDS_SPLIT` were absent for the same reason,
and they are why the fix is a section rather than four table rows: none of them
belongs to one cycle's column. They are cross-cycle, and the matrix is organised per
cycle, so forcing them into a row would put a token in a cycle that does not own it.
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_BLOCKING = _ROOT / "rules" / "blocking-verdicts.txt"
_SCHEMA = _ROOT / "rules" / "cycle-rule-schema.md"


def _blocking_verdicts() -> list[str]:
    return [line.strip() for line in _BLOCKING.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def test_the_blocking_list_is_not_empty() -> None:
    """`blocking-verdicts.txt` says an absent file is an error, not an empty list."""
    assert len(_blocking_verdicts()) >= 10


def test_every_blocking_verdict_is_documented_in_the_schema() -> None:
    schema = _SCHEMA.read_text(encoding="utf-8-sig")
    missing = [v for v in _blocking_verdicts() if f"`{v}`" not in schema]
    assert missing == [], (
        f"{len(missing)} verdict(s) stop an item and are absent from the canonical "
        f"vocabulary in cycle-rule-schema.md: {missing}"
    )
