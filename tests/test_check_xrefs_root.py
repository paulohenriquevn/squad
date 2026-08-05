"""O validador audita o ecossistema a que PERTENCE, não o do diretório atual.

Antes, sem `--ecosystem-dir`, a raiz saía de `Path.cwd()`. O efeito era um
validador que mente por omissão: rodar

    python3 <outro-projeto>/.claude/scripts/check_xrefs.py

de um cwd qualquer auditava silenciosamente o ecossistema DO CWD e imprimia o
veredito dele — com o nome do outro projeto na linha de comando. Medido em
2026-08-03: três consumidores reportados `PASS` estavam com 3, 0 e 11 findings;
o `PASS` era o repo do kit se auto-validando três vezes.

Um validador que audita o alvo errado é pior que nenhum: nenhum não produz
confiança, este produz confiança infundada — e a decisão tomada em cima dela
(“os três estão limpos, pode seguir”) já foi tomada.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO / "scripts" / "check_xrefs.py"


def _make_ecosystem(root: Path, *, skill: str, missing_rule: bool) -> Path:
    """Cria um .claude/ mínimo, opcionalmente com uma referência de regra quebrada."""
    eco = root / ".claude"
    (eco / "skills" / skill).mkdir(parents=True)
    (eco / "rules").mkdir(parents=True)
    (eco / "scripts").mkdir(parents=True)
    (eco / "hooks").mkdir(parents=True)  # find_ecosystem_dir exige os três

    body = "# Skill\n\n## Cycle contract\n\nSee `rules/cycle-implement.md`.\n"
    if missing_rule:
        body += "\nAlso reads `rules/nao-existe-em-lugar-nenhum.md`.\n"
    (eco / "skills" / skill / "SKILL.md").write_text(body, encoding="utf-8")
    (eco / "rules" / "cycle-implement.md").write_text(
        f"# cycle-implement\n\nChain: `implement`\n\nUses skills/{skill}/.\n", encoding="utf-8"
    )
    return eco


def _findings(script: Path, cwd: Path) -> list[dict]:
    proc = subprocess.run(
        [sys.executable, str(script), "--json"],
        cwd=str(cwd), capture_output=True, text=True, check=False,
    )
    return json.loads(proc.stdout)["findings"]


def test_raiz_vem_do_script_e_nao_do_cwd(tmp_path: Path) -> None:
    """A regressão exata: script do projeto sujo, chamado de um cwd limpo."""
    sujo = tmp_path / "sujo"
    limpo = tmp_path / "limpo"
    eco_sujo = _make_ecosystem(sujo, skill="implement", missing_rule=True)
    _make_ecosystem(limpo, skill="implement", missing_rule=False)

    copia = eco_sujo / "scripts" / "check_xrefs.py"
    copia.write_bytes(_SCRIPT.read_bytes())
    for shared in (_REPO / "scripts").glob("*.py"):
        if shared.name != "check_xrefs.py":
            (eco_sujo / "scripts" / shared.name).write_bytes(shared.read_bytes())

    quebradas = [
        f for f in _findings(copia, cwd=limpo)
        if f.get("check") == "rules_reference_resolves"
    ]
    assert quebradas, (
        "o script do projeto sujo, chamado de um cwd limpo, não viu a referência "
        "quebrada que existe no projeto ao qual ele pertence — está auditando o cwd"
    )
    assert quebradas[0]["missing_rule"] == "nao-existe-em-lugar-nenhum.md"


def test_ecosystem_dir_explicito_continua_mandando(tmp_path: Path) -> None:
    """`--ecosystem-dir` é a única forma de apontar para outro alvo, e ela vence."""
    outro = tmp_path / "outro"
    eco_outro = _make_ecosystem(outro, skill="implement", missing_rule=True)

    proc = subprocess.run(
        [sys.executable, str(_SCRIPT), "--json", "--ecosystem-dir", str(eco_outro)],
        cwd=str(_REPO), capture_output=True, text=True, check=False,
    )
    findings = json.loads(proc.stdout)["findings"]
    assert any(f.get("check") == "rules_reference_resolves" for f in findings)
