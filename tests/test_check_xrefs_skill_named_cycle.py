"""Uma skill chamada `cycle-algo` era indistinguível de uma referência a um cycle.

`skills/cycle-goal/` é uma skill, não uma fase de cycle — não existe (nem deve
existir) `rules/cycle-goal.md`. Mas o Check 2 extraía o primeiro token `cycle-X`
do SKILL.md inteiro quando não havia seção `## Cycle contract`, e concluía que a
skill declarava pertencer a um cycle inexistente.

O efeito prático: o `plan-help`, cuja função é justamente LISTAR os comandos,
não podia mencionar `/cycle-goal` sem derrubar o validador para FAIL. O bug ficou
latente enquanto a documentação omitia o comando — a omissão escondia o defeito,
e corrigir a omissão o revelou.

Um `cycle-X` cujo X nomeia uma skill existente é a skill, nunca uma regra. Quem
de fato pertence a um cycle diz isso numa seção `## Cycle contract`, que é casada
primeiro e não é ambígua.
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


def _write_aux(eco: Path, *names: str) -> None:
    (eco / "rules" / "auxiliary-skills.txt").write_text(
        "\n".join(names) + "\n", encoding="utf-8"
    )


def test_skill_named_cycle_something_is_not_a_cycle_reference(tmp_path: Path) -> None:
    eco = _make_ecosystem(tmp_path)
    (eco / "skills" / "cycle-goal").mkdir(parents=True)
    (eco / "skills" / "cycle-goal" / "SKILL.md").write_text(
        "# `/cycle-goal`\n\nBinds a session to a milestone.\n", encoding="utf-8"
    )
    _write_aux(eco, "cycle-goal")

    rc, data = _run(eco)

    assert not _checks(data, "skill_cycle_contract_resolves"), data
    assert rc == 0, data


def test_another_skill_may_mention_the_cycle_named_skill(tmp_path: Path) -> None:
    """O caso que quebrou de verdade: o `plan-help` listando `/cycle-goal`."""
    eco = _make_ecosystem(tmp_path)
    (eco / "skills" / "cycle-goal").mkdir(parents=True)
    (eco / "skills" / "cycle-goal" / "SKILL.md").write_text(
        "# `/cycle-goal`\n\nBinds a session to a milestone.\n", encoding="utf-8"
    )
    (eco / "skills" / "plan-help").mkdir(parents=True)
    (eco / "skills" / "plan-help" / "SKILL.md").write_text(
        "# `/plan-help`\n\n| `/cycle-goal M<N>` | Bind the session |\n", encoding="utf-8"
    )
    _write_aux(eco, "cycle-goal", "plan-help")

    rc, data = _run(eco)

    assert not _checks(data, "skill_cycle_contract_resolves"), data
    assert rc == 0, data


def test_a_genuinely_missing_cycle_is_still_caught(tmp_path: Path) -> None:
    """A correção não pode cegar o check: só nomes de SKILL existentes são isentos."""
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
