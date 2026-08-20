"""Skills do projeto declaradas numa REGRA, não editadas dentro do validador.

`AUXILIARY_SKILLS` é uma constante no corpo do `check_xrefs.py`. Um consumidor
com skills próprias só tinha uma saída: editar o Python do kit. O `theo` fez
exatamente isso (`cnpg-audit`, `cnpg-design`, `multi-cluster-fleet-specialist`),
e essa edição é o que uma sincronização futura sobrescreve — nesta sessão ela só
sobreviveu porque a comparação foi feita arquivo a arquivo.

Medido no `speculative` (2026-08-20): 9 skills de domínio próprias, 18 WARN, que
eram **100% dos avisos do checker** — e com `--strict`, que é como o instalador
o invoca, isso reprova a instalação inteira. Um validador que sempre avisa
ensina a ser ignorado; um que reprova por design do consumidor ensina a rodar
sem `--strict`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO / "scripts" / "check_xrefs.py"


def _eco(root: Path, *, skills: list[str], declared: list[str] | None) -> Path:
    eco = root / ".claude"
    (eco / "rules").mkdir(parents=True)
    (eco / "scripts").mkdir(parents=True)
    (eco / "hooks").mkdir(parents=True)
    (eco / "rules" / "cycle-implement.md").write_text(
        "# Cycle: IMPLEMENT\n\n## Cross-references\n\n- `skills/implement/SKILL.md`\n",
        encoding="utf-8")
    (eco / "skills" / "implement").mkdir(parents=True)
    (eco / "skills" / "implement" / "SKILL.md").write_text(
        "# Skill\n\n## Cycle contract\n\nSee `rules/cycle-implement.md`.\n", encoding="utf-8")
    for name in skills:
        (eco / "skills" / name).mkdir(parents=True)
        (eco / "skills" / name / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    if declared is not None:
        (eco / "rules" / "auxiliary-skills.txt").write_text(
            "# skills deste projeto\n" + "\n".join(declared) + "\n", encoding="utf-8")
    return eco


def _warns_about(eco: Path, skill: str) -> bool:
    """Há algum aviso sobre ESTA skill? (o fixture mínimo gera outros, irrelevantes aqui)"""
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--ecosystem-dir", str(eco), "--json"],
        capture_output=True, text=True,
    )
    import json
    findings = json.loads(result.stdout).get("findings", [])
    return any(skill in json.dumps(f) for f in findings)


def test_undeclared_project_skill_is_warned_about(tmp_path: Path) -> None:
    eco = _eco(tmp_path, skills=["collapse-detection-specialist"], declared=None)
    assert _warns_about(eco, "collapse-detection-specialist"), "é o estado de hoje: 2 WARN por skill"


def test_declaring_it_in_the_rule_clears_both_warnings(tmp_path: Path) -> None:
    """Os DOIS checks — `no_orphan_skills` e `skill_has_cycle_contract`. Isentar só
    um é a meia isenção que o próprio código documenta como falso conserto."""
    eco = _eco(tmp_path, skills=["collapse-detection-specialist"],
               declared=["collapse-detection-specialist"])
    assert not _warns_about(eco, "collapse-detection-specialist")


def test_a_declared_skill_that_does_not_exist_is_not_an_error(tmp_path: Path) -> None:
    """A lista é declaração de intenção, não inventário: uma skill removida do
    projeto não deve quebrar o validador."""
    eco = _eco(tmp_path, skills=["collapse-detection-specialist"],
               declared=["collapse-detection-specialist", "ja-removida"])
    assert not _warns_about(eco, "ja-removida")
    assert not _warns_about(eco, "collapse-detection-specialist")
