"""Two documents described the sweep's output, and they disagreed.

`rules/cycle-backlog.md` says an item the system found is approved when it is filed,
attributed to `system/autonomous-sweep`. `skills/discover-execute/SKILL.md`, the skill
that files them, said `status: triaged`. An agent following the skill produced items
the registry's own contract says should not exist, and neither document knew about the
other (#183).
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _sweep_section() -> str:
    text = (_ROOT / "skills" / "discover-execute" / "SKILL.md").read_text(encoding="utf-8")
    found = re.search(r"### Step \d+ — Sweep mode\n(.*?)(?=\n## |\n### )", text, re.DOTALL)
    assert found, "discover-execute no longer has a sweep section"
    return found.group(1)


def test_the_registry_contract_files_sweep_findings_as_approved() -> None:
    rule = (_ROOT / "rules" / "cycle-backlog.md").read_text(encoding="utf-8")

    assert "approved_by: system/autonomous-sweep" in rule


def test_the_skill_that_files_them_says_the_same() -> None:
    section = _sweep_section()

    assert "status: approved" in section
    assert "approved_by: system/autonomous-sweep" in section
    assert "status: triaged" not in section
