"""A skill named `cycle-something` was indistinguishable from a cycle reference.

`skills/session-goal/` is a skill, not a cycle phase — there is no (and should be
no) `rules/session-goal.md`. But Check 2 extracted the first `cycle-X` token from
the whole SKILL.md when there was no `## Cycle contract` section, and concluded
the
skill declarava pertencer a um cycle inexistente.

The practical effect: `commands-help`, whose whole job is to LIST the commands, could
not mention `/session-goal` without driving the validator to FAIL. The bug stayed
latent while the documentation omitted the command — the omission hid the defect,
and fixing the omission revealed it.

A `cycle-X` whose X names an existing skill IS the skill, never a rule. Whatever
genuinely belongs to a cycle says so in a `## Cycle contract` section, which is
matched first and is not ambiguous.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO / "mechanisms" / "gates" / "check_xrefs.py"


def _make_ecosystem(root: Path) -> Path:
    eco = root / ".claude"
    (eco / "skills" / "implement").mkdir(parents=True)
    (eco / "rules").mkdir(parents=True)
    (eco / "scripts").mkdir(parents=True)
    (eco / "hooks").mkdir(parents=True)
    (eco / "skills" / "implement" / "SKILL.md").write_text(
        "# Skill\n\n## Cycle contract\n\nSee `rules/cycle-implement.md`.\n", encoding="utf-8"
    )
    (eco / "rules" / "cycle-implement.md").write_text(
        "# Cycle: IMPLEMENT\n\n## Cross-references\n\n- `skills/implement/SKILL.md`\n",
        encoding="utf-8",
    )
    return eco


def _run(eco: Path) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--ecosystem-dir", str(eco), "--json"],
        capture_output=True, text=True,
     check=False)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        data = {"raw": result.stdout, "stderr": result.stderr}
    return result.returncode, data


def _checks(data: dict, name: str) -> list[dict]:
    return [f for f in data.get("findings", []) if f.get("check") == name]


def _write_aux(eco: Path, *names: str) -> None:
    (eco / "rules" / "auxiliary-skills.txt").write_text(
        "\n".join(names) + "\n", encoding="utf-8"
    )


def test_skill_named_cycle_something_is_not_a_cycle_reference(tmp_path: Path) -> None:
    eco = _make_ecosystem(tmp_path)
    (eco / "skills" / "session-goal").mkdir(parents=True)
    (eco / "skills" / "session-goal" / "SKILL.md").write_text(
        "# `/session-goal`\n\nBinds a session to a milestone.\n", encoding="utf-8"
    )
    _write_aux(eco, "session-goal")

    rc, data = _run(eco)

    assert not _checks(data, "skill_cycle_contract_resolves"), data
    assert rc == 0, data


def test_another_skill_may_mention_the_cycle_named_skill(tmp_path: Path) -> None:
    """The case that actually broke: `commands-help` listing `/session-goal`."""
    eco = _make_ecosystem(tmp_path)
    (eco / "skills" / "session-goal").mkdir(parents=True)
    (eco / "skills" / "session-goal" / "SKILL.md").write_text(
        "# `/session-goal`\n\nBinds a session to a milestone.\n", encoding="utf-8"
    )
    (eco / "skills" / "commands-help").mkdir(parents=True)
    (eco / "skills" / "commands-help" / "SKILL.md").write_text(
        "# `/commands-help`\n\n| `/session-goal M<N>` | Bind the session |\n", encoding="utf-8"
    )
    _write_aux(eco, "session-goal", "commands-help")

    rc, data = _run(eco)

    assert not _checks(data, "skill_cycle_contract_resolves"), data
    assert rc == 0, data


def test_a_genuinely_missing_cycle_is_still_caught(tmp_path: Path) -> None:
    """The fix must not blind the check: only existing SKILL names are exempt."""
    eco = _make_ecosystem(tmp_path)
    (eco / "skills" / "orfa").mkdir(parents=True)
    (eco / "skills" / "orfa" / "SKILL.md").write_text(
        "# Skill\n\n## Cycle contract\n\nSee `rules/cycle-inexistente.md`.\n",
        encoding="utf-8",
    )

    rc, data = _run(eco)

    findings = _checks(data, "skill_cycle_contract_resolves")
    assert findings, data
    assert any("cycle-inexistente" in f.get("message", "") for f in findings)
    assert rc == 1
