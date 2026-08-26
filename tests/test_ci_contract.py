"""O CI tem de reprovar o que os gates reprovam.

O DEFEITO QUE ISTO FIXA
-----------------------
`check_xrefs.py` tem dois modos. Sem `--strict`, um achado de severidade WARN
é impresso e o processo sai 0 — a saída literal traz a linha do WARN e, logo
abaixo, `Overall: PASS`. Com `--strict`, o mesmo achado sai 1.

`scripts/install.sh` sempre chamou com `--strict`. O workflow chamava sem. O
resultado, medido em 2026-08-26: uma instalação a partir de um clone limpo
nascia com `rules/cycle-maintenance.md` apontando para um `agents/README.md`
inexistente, o instalador dizia `check_xrefs.py: FAIL`, e o CI do mesmo commit
ficava verde. O gate olhou, viu e aprovou.

POR QUE O TESTE LÊ O COMANDO DO WORKFLOW EM VEZ DE PROCURAR A FLAG
------------------------------------------------------------------
Um teste que fizesse `assert "--strict" in ci_yml` casaria com a flag escrita
em qualquer lugar do arquivo — num comentário, num passo desativado, num job
que não roda. Ele afirmaria sobre o TEXTO do workflow, não sobre o que o
workflow faz.

Então este módulo extrai o comando exato de cada passo e o EXECUTA contra uma
árvore deliberadamente corrompida. O que se afirma é o comportamento: dado um
defeito real, o comando que o CI roda precisa sair diferente de zero. Isso
continua valendo se alguém trocar `--strict` por outro mecanismo — que é
exatamente o que um teste de comportamento deve permitir.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"


def _steps() -> list[dict]:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    out: list[dict] = []
    for job in doc.get("jobs", {}).values():
        out.extend(job.get("steps", []) or [])
    return out


def _step_running(fragment: str) -> dict:
    matches = [s for s in _steps() if fragment in (s.get("run") or "")]
    assert matches, f"nenhum passo do CI executa {fragment!r} — o gate saiu do workflow"
    assert len(matches) == 1, f"{fragment!r} aparece em {len(matches)} passos; esperado 1"
    return matches[0]


@pytest.fixture()
def broken_kit(versioned_kit: Path, tmp_path: Path) -> Path:
    """Uma cópia do kit com exatamente o defeito que passou verde.

    `agents/README.md` é citado por `rules/cycle-maintenance.md`. Removê-lo
    reproduz o estado em que todo clone limpo nascia antes da correção.
    """
    kit = tmp_path / "broken-kit"
    shutil.copytree(versioned_kit, kit)
    readme = kit / "agents" / "README.md"
    assert readme.is_file(), (
        "agents/README.md não está versionado — este teste não consegue "
        "reproduzir o defeito, e o kit já está quebrado por outro motivo."
    )
    readme.unlink()
    return kit


def test_ci_xref_step_rejects_a_broken_reference(broken_kit: Path):
    """O comando de cross-reference do CI, executado sobre uma árvore quebrada, precisa falhar."""
    run = _step_running("check_xrefs.py")["run"].strip()
    proc = subprocess.run(run, shell=True, cwd=broken_kit, capture_output=True, text=True)
    assert proc.returncode != 0, (
        "O passo de cross-reference do CI aprovou uma referência quebrada.\n"
        f"comando: {run}\n"
        f"saída:\n{proc.stdout}\n{proc.stderr}"
    )


def test_ci_xref_step_accepts_the_healthy_kit(versioned_kit: Path):
    """E precisa aprovar a árvore íntegra — senão o teste acima passaria por acidente."""
    run = _step_running("check_xrefs.py")["run"].strip()
    proc = subprocess.run(run, shell=True, cwd=versioned_kit, capture_output=True, text=True)
    assert proc.returncode == 0, (
        f"O CI reprova o kit íntegro:\n{proc.stdout}\n{proc.stderr}"
    )


def test_ci_runs_the_install_contract(_broken: None = None):
    """A regressão de instalação limpa precisa estar no workflow, não só no disco.

    `tests/test_clean_install.py` é o único teste que enxerga o que outra
    máquina receberia. Se ele não roda no CI, volta a ser um arquivo que passou
    uma vez.
    """
    runs = " ".join((s.get("run") or "") for s in _steps())
    assert "run_slice_tests.sh" in runs or "test_clean_install" in runs, (
        "nenhum passo do CI executa a suíte que contém o contrato de instalação"
    )
