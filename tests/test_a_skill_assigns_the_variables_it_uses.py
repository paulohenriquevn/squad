"""A shell variable a SKILL.md uses is one it assigned.

THE DEFECT THIS CLOSES, TWICE
-----------------------------
`$ECO` resolves the kit — `.claude/` in a consumer, `.` in this repository — and a
SKILL.md that uses it without assigning it expands to an absolute path from the
filesystem root:

    python3 "$ECO/skills/plan-alignment/scripts/classify_alignment_depth.py" . B-001
    python3: can't open file '/skills/plan-alignment/scripts/classify_alignment_depth.py'

Found in `skills/design/SKILL.md` on 2026-09-20, where the two commands that did not run
were "score the drawings" and "convene the panel". A test was written for it — and it
lived in `skills/design/tests/`, reading `skills/design/SKILL.md` and nothing else.

On 2026-09-21 the same defect was measured in `skills/plan-alignment/SKILL.md`, whose
unrunnable command is `classify_alignment_depth.py`: the script `cycle-plan.md` describes
as **"Derived, never chosen"**. With it not running, the depth is chosen — and the
document's own default is FULL, the outcome the script exists to avoid after a consumer
produced 2,740 KB of alignment briefs signed zero times.

A test scoped to one slice catches the defect in one slice. This one reads every
SKILL.md, which is the only scope that could have caught the second instance.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SKILLS = sorted(REPO.glob("skills/*/SKILL.md"))

#: `"$NAME/…"` — a variable used as a path prefix, which is the shape that expands to
#: `/…` when the variable is empty.
_USED_RE = re.compile(r'"\$(\w+)/')
#: `NAME=…`, and `for NAME in …` — a loop variable is assigned by the loop, and reading
#: only the first form reported `$d` in a `for d in */` as unassigned.
_ASSIGNED_RE = re.compile(r"^\s*(\w+)=|\bfor\s+(\w+)\s+in\b", re.MULTILINE)


def _assigned(text: str) -> set[str]:
    return {name for pair in _ASSIGNED_RE.findall(text) for name in pair if name}

#: Variables the shell or the harness provides. Assigning them would be the error.
_AMBIENT = frozenset({"HOME", "PWD", "TMPDIR", "PATH", "CLAUDE_PLUGIN_ROOT"})


def test_the_glob_found_skills() -> None:
    """A glob matching nothing would make every assertion below vacuous."""
    assert len(SKILLS) > 10


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.parent.name)
def test_every_variable_used_as_a_path_is_assigned(skill: Path) -> None:
    text = skill.read_text(encoding="utf-8")

    missing = sorted(set(_USED_RE.findall(text)) - _assigned(text) - _AMBIENT)

    assert not missing, (
        f"{skill.relative_to(REPO)} uses {missing} as a path prefix and assigns "
        f"none of them. An empty expansion makes the command an absolute path from "
        f"the filesystem root, and the step silently does not run")
