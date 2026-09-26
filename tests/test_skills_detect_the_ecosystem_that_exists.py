"""A skill resolves its own kit, or it runs the wrong file — or none.

Every SKILL.md that shells out to a kit script first has to answer one question:
is this project a CONSUMER, where the kit lives under `.claude/`, or the kit's own
repository, where it lives at the root? The idiom is a directory test:

    $([ -d .claude/skills ] && echo .claude || echo .)

Thirteen call sites across eight skills tested `.claude/scripts` instead — a
directory `mechanisms/distribution/install.sh` DELETES on every install:

    if [ -d "$ECO/scripts" ]; then ... rm -rf "$ECO/scripts"
        echo "    removed the stale .claude/scripts/ so no hook resolves to it"

So in any consumer installed after `scripts/` became `mechanisms/<family>/`, the
test is false by construction, the branch falls through to `.`, and the command
becomes `./mechanisms/cycle/cycle_events.py` — a path that exists only in the kit's
own repo. The phase event was never written, and nothing said so: `cycle_events`
is fail-open by design, and a missing event reads exactly like a phase that was
skipped.

Invisible in THIS repository, which is why it survived: here neither directory
exists, both branches resolve to `.`, and every affected command works.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]

#: The probe that is true in a consumer. `skills/` is copied by the installer and
#: is the directory the ecosystem is NAMED for; `scripts/` is the one it removes.
_PROBE = "[ -d .claude/skills ]"

_STALE_RE = re.compile(r"\[\s*-d\s+\.claude/(?!skills\b)([A-Za-z0-9_.-]+)\s*\]")

_SKILLS = sorted(_ROOT.glob("skills/*/SKILL.md"))


def test_the_repository_has_skills_to_check() -> None:
    """A glob that silently matched nothing would make every test below vacuous."""
    assert len(_SKILLS) > 10


@pytest.mark.parametrize("skill", _SKILLS, ids=lambda p: p.parent.name)
def test_a_skill_probes_a_directory_the_installer_writes(skill: Path) -> None:
    stale = _STALE_RE.findall(skill.read_text(encoding="utf-8"))
    assert not stale, (
        f"{skill.relative_to(_ROOT)} decides where the kit lives by testing "
        f"`.claude/{stale[0]}`, which the installer does not write (and, for "
        f"`scripts`, actively removes). Use `{_PROBE}`.")
