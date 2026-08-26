"""A instalação que qualquer OUTRA máquina recebe.

POR QUE A LISTA DE ARQUIVOS VEM DO GIT
--------------------------------------
Todo teste de instalação que este repositório tinha copiava a árvore de
trabalho — e a árvore de trabalho do mantenedor carrega arquivos que o
`.gitignore` esconde. `agents/*.md` é o caso: nove arquivos presentes em uma
máquina e em nenhuma outra. Enquanto o teste instalasse do disco, ele mediria
a máquina de quem o roda, não o que o kit entrega.

Medido em 2026-08-26: um clone limpo instalado num alvo vazio produzia
`.claude/agents/` VAZIO — nem o `README.md`, que o instalador copia
incondicionalmente — e `check_xrefs.py --strict` saía 1, porque
`rules/cycle-maintenance.md` cita `agents/README.md`. Na máquina do mantenedor,
verde. O mesmo `cp -r` levava 342 `.pyc` ao consumidor, contra uma promessa
explícita no cabeçalho do instalador de que caches seriam pulados.

`git ls-files` é a única fonte que responde "o que está versionado?" sem
consultar o disco — e é por isso que a fixture abaixo monta a árvore a partir
dela, arquivo a arquivo, em vez de fazer `shutil.copytree`.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: Diretórios que são cache de ferramenta — nunca conteúdo do kit.
CACHE_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}


@pytest.fixture(scope="module")
def installed(versioned_kit: Path, tmp_path_factory: pytest.TempPathFactory):
    """Instalação real, a partir do kit versionado, num alvo vazio."""
    target = tmp_path_factory.mktemp("consumer")
    proc = subprocess.run(
        ["bash", str(versioned_kit / "scripts" / "install.sh"), str(target)],
        capture_output=True,
        text=True,
    )
    return target, proc


def test_install_succeeds(installed):
    target, proc = installed
    assert proc.returncode == 0, f"install.sh falhou:\n{proc.stdout}\n{proc.stderr}"
    assert (target / ".claude").is_dir()


def test_strict_xrefs_passes_on_a_fresh_install(installed):
    """O validador que o próprio install.sh chama tem de aprovar o que ele acabou de escrever.

    `--strict` é deliberado: sem ele, uma referência quebrada sai como
    `Overall: PASS` com exit 0 (ver `test_ci_contract.py`).
    """
    target, _ = installed
    proc = subprocess.run(
        ["python3", str(target / ".claude" / "scripts" / "check_xrefs.py"), "--strict"],
        cwd=target,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        "Uma instalação recém-feita não passa no seu próprio validador:\n"
        f"{proc.stdout}\n{proc.stderr}"
    )


def test_routing_mechanism_reaches_the_consumer(installed):
    """`agents/README.md` descreve o MECANISMO de roteamento, não um domínio.

    O instalador o copia incondicionalmente e `rules/cycle-maintenance.md` o
    cita. Se ele não estiver versionado, chega vazio em todo consumidor.
    """
    target, _ = installed
    readme = target / ".claude" / "agents" / "README.md"
    assert readme.is_file(), (
        "agents/README.md não chegou ao consumidor — ou não está versionado, "
        "ou o instalador parou de copiá-lo."
    )
    assert readme.stat().st_size > 0


def test_domain_specialists_are_opt_in(installed):
    """Sem `--with-domain-agents`, nenhum especialista de domínio é instalado.

    Eles descrevem os repositórios de UM ecossistema; num consumidor que não é
    aquele, são arquivos sobre repositórios que não existem ali.
    """
    target, _ = installed
    agents = target / ".claude" / "agents"
    specialists = [p for p in agents.glob("*.md") if p.name != "README.md"]
    assert specialists == [], f"especialistas de domínio vazaram: {specialists}"


def test_no_tool_cache_reaches_the_consumer(versioned_kit, tmp_path):
    """O cabeçalho do install.sh promete pular caches. Este teste cobra a promessa.

    Instala a partir de uma árvore que TEM caches — como a do mantenedor — e
    exige que nenhum atravesse. Instalar do `versioned_kit` não provaria nada:
    o git nunca carregou um `.pyc`.
    """
    dirty = tmp_path / "dirty-kit"
    subprocess.run(["cp", "-r", str(versioned_kit), str(dirty)], check=True)
    # Planta exatamente o lixo que a árvore de trabalho real acumula.
    for rel in ("skills/__pycache__", "scripts/__pycache__", "skills/code-quality/.pytest_cache"):
        d = dirty / rel
        d.mkdir(parents=True, exist_ok=True)
        (d / "planted.pyc").write_bytes(b"\x00planted")

    target = tmp_path / "consumer"
    target.mkdir()
    proc = subprocess.run(
        ["bash", str(dirty / "scripts" / "install.sh"), str(target)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr

    eco = target / ".claude"
    leaked_dirs = [p for p in eco.rglob("*") if p.is_dir() and p.name in CACHE_DIRS]
    leaked_pyc = list(eco.rglob("*.pyc"))
    assert not leaked_dirs, f"cache propagado ao consumidor: {[str(p) for p in leaked_dirs]}"
    assert not leaked_pyc, f".pyc propagado ao consumidor: {[str(p) for p in leaked_pyc]}"


def test_installed_payload_is_not_dominated_by_noise(installed, versioned_kit):
    """Guarda-corpo de ordem de grandeza sobre o que o consumidor recebe.

    Não fixa um número — o kit cresce. Fixa a relação: o que é instalado não
    pode exceder muito o que o git carrega, porque tudo além disso é conteúdo
    que ninguém versionou.
    """
    target, _ = installed
    versioned = len(
        subprocess.run(
            ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
        ).stdout.split()
    )
    installed_files = sum(1 for p in (target / ".claude").rglob("*") if p.is_file())
    assert installed_files <= versioned * 1.25, (
        f"instalados {installed_files} arquivos contra {versioned} versionados — "
        "o excedente não é o sistema."
    )
