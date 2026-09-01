"""A rule may cite a rule that does not exist, and the validator did not look.

`rules/cycle-acceptance.md` e `rules/cycle-release.md` ancoravam o single-flip
invariant at *"cycle-roadmap § Hard gates"*. `cycle-roadmap` was replaced by
`cycle-maintenance` and the file no longer exists — but `check_xrefs.py` reported
PASS, because Check 7 swept `skills/**/SKILL.md`, `skills/**/*.py` and
`scripts/**/*.py`, and **never `rules/*.md`**; and because nothing checked
references to a cycle by name (`cycle-roadmap`), only paths like
`rules/<file>.md`.

A normative anchor pointing at nothing does not break execution today — it breaks
the next maintenance, which will look for the cited section to learn what the gate
promises and will not find it.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO / "scripts" / "check_xrefs.py"


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
    result = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(_SCRIPT), "--ecosystem-dir", str(eco), "--json"],
        capture_output=True, text=True,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        data = {"raw": result.stdout, "stderr": result.stderr}
    return result.returncode, data


def _checks(data: dict, name: str) -> list[dict]:
    return [f for f in data.get("findings", []) if f.get("check") == name]


def test_rule_citing_a_nonexistent_cycle_is_caught(tmp_path: Path) -> None:
    eco = _make_ecosystem(tmp_path)
    (eco / "rules" / "cycle-implement.md").write_text(
        "# Cycle: IMPLEMENT\n\nPer `cycle-roadmap § Hard gates`, one checkbox flips.\n"
        "\n## Cross-references\n\n- `skills/implement/SKILL.md`\n",
        encoding="utf-8",
    )
    rc, data = _run(eco)
    findings = _checks(data, "cycle_reference_resolves")
    assert findings, data
    assert any("cycle-roadmap" in f.get("message", "") for f in findings)
    assert rc == 1


def test_rule_citing_a_nonexistent_rules_file_is_caught(tmp_path: Path) -> None:
    """Check 7 never swept `rules/` — a rule citing another one escaped."""
    eco = _make_ecosystem(tmp_path)
    (eco / "rules" / "cycle-implement.md").write_text(
        "# Cycle: IMPLEMENT\n\nSee `rules/does-not-exist-anywhere.md`.\n"
        "\n## Cross-references\n\n- `skills/implement/SKILL.md`\n",
        encoding="utf-8",
    )
    rc, data = _run(eco)
    assert _checks(data, "rules_reference_resolves"), data
    assert rc == 1


def test_a_cycle_that_exists_as_a_skill_is_not_a_broken_reference(tmp_path: Path) -> None:
    """`session-goal` is a skill, not a rule file — citing it is legitimate."""
    eco = _make_ecosystem(tmp_path)
    (eco / "skills" / "session-goal").mkdir(parents=True)
    (eco / "skills" / "session-goal" / "SKILL.md").write_text("# session-goal\n", encoding="utf-8")
    (eco / "rules" / "cycle-implement.md").write_text(
        "# Cycle: IMPLEMENT\n\nThe `session-goal` Stop-hook reads the verdict.\n"
        "\n## Cross-references\n\n- `skills/implement/SKILL.md`\n",
        encoding="utf-8",
    )
    _rc, data = _run(eco)
    assert _checks(data, "cycle_reference_resolves") == []


def test_clean_ecosystem_still_passes(tmp_path: Path) -> None:
    eco = _make_ecosystem(tmp_path)
    _rc, data = _run(eco)
    assert _checks(data, "cycle_reference_resolves") == []
    assert _checks(data, "rules_reference_resolves") == []
