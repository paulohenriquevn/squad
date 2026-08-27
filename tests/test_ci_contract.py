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
    proc = subprocess.run(run, shell=True, cwd=broken_kit, capture_output=True, text=True)  # noqa: PLW1510
    assert proc.returncode != 0, (
        "O passo de cross-reference do CI aprovou uma referência quebrada.\n"
        f"comando: {run}\n"
        f"saída:\n{proc.stdout}\n{proc.stderr}"
    )


def test_ci_xref_step_accepts_the_healthy_kit(versioned_kit: Path):
    """E precisa aprovar a árvore íntegra — senão o teste acima passaria por acidente."""
    run = _step_running("check_xrefs.py")["run"].strip()
    proc = subprocess.run(run, shell=True, cwd=versioned_kit, capture_output=True, text=True)  # noqa: PLW1510
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


def _jobs() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8")).get("jobs", {})


def test_the_root_suite_is_not_run_twice_in_the_same_job():
    """Rodar a mesma suíte duas vezes não mede nada a mais — só custa o dobro.

    O job principal executava `run_slice_tests.sh` (que já roda `tests`) e, no
    passo seguinte, `pytest tests` de novo com cobertura. Medido 2026-08-26: 45 s
    duplicados por execução. A cobertura passou a ser calculada na única
    execução, com o mesmo limiar cobrado.
    """
    for name, job in _jobs().items():
        runs = [(s.get("run") or "") for s in (job.get("steps") or [])]
        slice_runner = [r for r in runs if "run_slice_tests.sh" in r]
        if not slice_runner:
            continue
        standalone_root = [
            r for r in runs
            if "run_slice_tests.sh" not in r
            and "pytest" in r
            and " tests" in r
        ]
        assert not standalone_root, (
            f"job {name!r} roda a suíte raiz duas vezes: {standalone_root}"
        )


def test_coverage_threshold_survives_the_deduplication():
    """A desduplicação não pode ter levado o limiar de cobertura junto."""
    runs = " ".join((s.get("run") or "") for s in _steps())
    env = " ".join(
        f"{k}={v}"
        for job in _jobs().values()
        for step in (job.get("steps") or [])
        for k, v in (step.get("env") or {}).items()
    )
    assert "cov-fail-under" in runs or "ROOT_SUITE_COV" in runs + env, (
        "nenhum passo do CI cobra um limiar de cobertura"
    )


def test_python_setup_caches_dependencies():
    """Quatro jobs reinstalando as mesmas dependências a cada execução é custo puro."""
    missing = []
    for name, job in _jobs().items():
        for step in job.get("steps") or []:
            if str(step.get("uses", "")).startswith("actions/setup-python"):
                if not (step.get("with") or {}).get("cache"):
                    missing.append(name)
    assert not missing, f"setup-python sem cache de dependências nos jobs: {missing}"
