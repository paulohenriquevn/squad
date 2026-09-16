"""A claim of singleness is a claim nothing checks.

`halt_reports` called itself "the single reader of these files", which was true of the
two callers it named and false of a third. `mechanisms/fleet/squad_lead.py` carried its
own glob — `*{item[2:]}*-BLOCKED.md` — anchoring BLOCKED to the end of the name, which
is the exact form `halt_reports`' own comment records as wrong: a lane writing a second
report for one item adds a descriptive suffix, and the end-anchor misses it. Measured
2026-09-04: B-079 had two halt reports on disk and that glob returned neither.

So the lead told a lane "not blocked" for an item the board and the selector both showed
as blocked — one registry answering two ways depending on which mechanism asked.

This test is what turns the docstring's claim into something checked.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]

#: A directory listing for halt reports: `*BLOCKED*` in any form. Anything matching this
#: outside `squad_boss.py` is a second reader of those files.
_HALT_GLOB = re.compile(r"glob\(\s*f?[\"'][^\"']*BLOCKED[^\"']*[\"']")


def _sources() -> list[Path]:
    out: list[Path] = []
    for base in ("skills", "mechanisms", "hooks", "squad"):
        directory = _ROOT / base
        if directory.is_dir():
            out.extend(p for p in directory.rglob("*.py")
                       if "__pycache__" not in p.parts and "/tests/" not in str(p))
    return out


def test_only_squad_boss_lists_halt_reports() -> None:
    offenders = []
    for path in _sources():
        if path.name == "squad_boss.py":
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _HALT_GLOB.search(line):
                offenders.append(f"{path.relative_to(_ROOT)}:{line_no}")
    assert not offenders, (
        "these list halt reports themselves instead of calling `halt_reports`, and a "
        f"second scan drifts from the first: {offenders}")


def test_the_docstring_still_claims_it() -> None:
    """If the claim is ever dropped, this test should be dropped with it — a guard for a
    promise nobody makes any more is a guard nobody can interpret."""
    source = (_ROOT / "skills" / "backlog-review" / "scripts"
              / "squad_boss.py").read_text(encoding="utf-8")
    assert "The single reader of these files" in source
