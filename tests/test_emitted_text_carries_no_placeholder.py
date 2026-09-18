"""A `{slug}` reaching a reader is an instruction with a hole in it.

Three of the five BLOCKER findings `check_upstream_gate` emits carried the literal
string `{slug}` in their remediation, because those three strings were never marked
as f-strings while their neighbours were. The findings go into the consolidated review
report, so the report told the reader to run `/code-quality {slug}`.

This kit already treats the shape as a defect elsewhere — `spawn_stages.py` refuses to
write a prompt with a surviving placeholder for exactly this reason — so the check is
applied to the emitters rather than to one file.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

#: A brace pair around a bare identifier, in a string that is NOT an f-string. The
#: JSON and format-spec cases (`{}`, `{{`, `{0}`) are excluded by requiring a name.
_UNSUBSTITUTED = re.compile(r'(?<![fr])(["\'])(?:(?!\1).)*\{[a-z_][a-z0-9_]*\}(?:(?!\1).)*\1')


def _emitters() -> list[Path]:
    return [_ROOT / "skills" / "review" / "scripts" / "check_upstream_gate.py"]


def test_no_remediation_ships_an_unfilled_placeholder() -> None:
    offenders: list[str] = []
    for path in _emitters():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or "{" not in stripped:
                continue
            if _UNSUBSTITUTED.search(stripped):
                offenders.append(f"{path.relative_to(_ROOT)}:{number}: {stripped}")

    assert offenders == [], "\n".join(offenders)
