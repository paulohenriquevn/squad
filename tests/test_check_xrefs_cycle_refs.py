"""Uma regra pode citar uma regra que não existe, e o validador não olhava.

`rules/cycle-acceptance.md` e `rules/cycle-release.md` ancoravam o single-flip
invariant em *"cycle-roadmap § Hard gates"*. O `cycle-roadmap` foi substituído
por `cycle-maintenance` e o arquivo não existe mais — mas o `check_xrefs.py`
reportava PASS, porque o Check 7 varria `skills/**/SKILL.md`, `skills/**/*.py` e
`scripts/**/*.py`, e **nunca `rules/*.md`**; e porque nada checava referências a
um cycle por nome (`cycle-roadmap`), só a caminhos `rules/<arquivo>.md`.

Uma âncora normativa apontando para o vazio não quebra a execução hoje — quebra
a próxima manutenção, que vai procurar a seção citada para saber o que o gate
promete e não vai encontrá-la.
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
    result = subprocess.run(
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
    """Check 7 nunca varreu `rules/` — uma regra citando outra escapava."""
    eco = _make_ecosystem(tmp_path)
    (eco / "rules" / "cycle-implement.md").write_text(
        "# Cycle: IMPLEMENT\n\nSee `rules/nao-existe-em-lugar-nenhum.md`.\n"
        "\n## Cross-references\n\n- `skills/implement/SKILL.md`\n",
        encoding="utf-8",
    )
    rc, data = _run(eco)
    assert _checks(data, "rules_reference_resolves"), data
    assert rc == 1


def test_a_cycle_that_exists_as_a_skill_is_not_a_broken_reference(tmp_path: Path) -> None:
    """`cycle-goal` é uma skill, não um arquivo de regra — citá-la é legítimo."""
    eco = _make_ecosystem(tmp_path)
    (eco / "skills" / "cycle-goal").mkdir(parents=True)
    (eco / "skills" / "cycle-goal" / "SKILL.md").write_text("# cycle-goal\n", encoding="utf-8")
    (eco / "rules" / "cycle-implement.md").write_text(
        "# Cycle: IMPLEMENT\n\nThe `cycle-goal` Stop-hook reads the verdict.\n"
        "\n## Cross-references\n\n- `skills/implement/SKILL.md`\n",
        encoding="utf-8",
    )
    rc, data = _run(eco)
    assert _checks(data, "cycle_reference_resolves") == []


def test_clean_ecosystem_still_passes(tmp_path: Path) -> None:
    eco = _make_ecosystem(tmp_path)
    rc, data = _run(eco)
    assert _checks(data, "cycle_reference_resolves") == []
    assert _checks(data, "rules_reference_resolves") == []
