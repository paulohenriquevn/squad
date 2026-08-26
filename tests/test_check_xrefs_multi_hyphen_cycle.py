"""Um cycle com dois hífens era truncado, e o validador acusava o arquivo errado.

`CYCLE_REF_RE` era `` `?cycle-([a-z]+)`? `` — `[a-z]+` não casa hífen. Então
`cycle-code-quality` era lido como `cycle-code`, `cycle-auto-plan` como
`cycle-auto` e `cycle-judge-codex` como `cycle-judge`. Nenhum dos três existe em
`rules/`, e o Check 2 (`skill_cycle_contract_resolves`) reportava FAIL contra um
nome que ninguém escreveu.

Três dos doze cycle rules do kit são multi-hífen, então o defeito cobria um
quarto do inventário. Ficou escondido porque as duas skills que citavam esses
cycles no `## Cycle contract` mencionavam antes um cycle de nome simples — e
`_extract_cycle_contract_ref` retorna no PRIMEIRO match. `auto-plan` cita
`cycle-discover` antes de `cycle-auto-plan`; a primeira skill a citar um
multi-hífen sozinha foi a que fez o bug aparecer.

O modo de falha é o pior para um validador: ele acusa um arquivo inexistente
enquanto o arquivo real está lá, e a leitura natural — "o validador está
quebrado" — é a que ensina a ignorá-lo.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO / "scripts" / "check_xrefs.py"

# Todo cycle rule multi-hífen do kit. Um nome novo aqui é um caso novo de graça.
MULTI_HYPHEN_CYCLES = ["cycle-code-quality", "cycle-auto-plan", "cycle-judge-codex"]


def _make_ecosystem(root: Path, cycle: str) -> Path:
    """Ecossistema mínimo: uma skill cujo contrato cita `cycle`, e o rule que existe."""
    eco = root / ".claude"
    skill = cycle.removeprefix("cycle-")
    (eco / "skills" / skill).mkdir(parents=True)
    (eco / "rules").mkdir(parents=True)
    (eco / "scripts").mkdir(parents=True)
    (eco / "hooks").mkdir(parents=True)
    (eco / "skills" / skill / "SKILL.md").write_text(
        f"# Skill\n\n## Cycle contract\n\nSee `rules/{cycle}.md`.\n", encoding="utf-8"
    )
    (eco / "rules" / f"{cycle}.md").write_text(
        f"# Cycle\n\n## Cross-references\n\n- `skills/{skill}/SKILL.md`\n",
        encoding="utf-8",
    )
    return eco


def _run(eco: Path) -> dict:
    proc = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(_SCRIPT), "--ecosystem-dir", str(eco), "--json"],
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


@pytest.mark.parametrize("cycle", MULTI_HYPHEN_CYCLES)
def test_multi_hyphen_cycle_contract_resolves(tmp_path: Path, cycle: str) -> None:
    # Arrange — a skill cita um cycle multi-hífen que EXISTE em disco.
    eco = _make_ecosystem(tmp_path, cycle)

    # Act
    report = _run(eco)

    # Assert — nenhum finding pode acusar o contrato de não resolver.
    unresolved = [
        f for f in report["findings"] if f["check"] == "skill_cycle_contract_resolves"
    ]
    assert unresolved == [], (
        f"{cycle} existe em rules/ mas o validador o acusou como ausente: {unresolved}"
    )


@pytest.mark.parametrize("cycle", MULTI_HYPHEN_CYCLES)
def test_multi_hyphen_cycle_is_not_truncated(tmp_path: Path, cycle: str) -> None:
    # Arrange — mesmo ecossistema, mas agora o rule real é REMOVIDO.
    eco = _make_ecosystem(tmp_path, cycle)
    (eco / "rules" / f"{cycle}.md").unlink()

    # Act
    report = _run(eco)

    # Assert — o validador deve reclamar do nome COMPLETO, não do prefixo truncado.
    msgs = [
        f["message"]
        for f in report["findings"]
        if f["check"] == "skill_cycle_contract_resolves"
    ]
    assert msgs, f"remover rules/{cycle}.md deveria produzir um finding"
    truncated = cycle.rsplit("-", 1)[0]
    assert any(f"{cycle}.md" in m for m in msgs), (
        f"esperava o nome completo {cycle}.md na mensagem, veio: {msgs}"
    )
    assert not any(f"{truncated}.md" in m for m in msgs), (
        f"nome truncado {truncated}.md vazou para a mensagem: {msgs}"
    )
