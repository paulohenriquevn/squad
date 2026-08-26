"""Shared fixtures for Cycle ecosystem tests."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# Ensure scripts/ is importable
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture()
def ecosystem_dir() -> Path:
    """Return the real Cycle ecosystem directory (repo root)."""
    from ecosystem_utils import find_ecosystem_dir

    return find_ecosystem_dir(start=REPO_ROOT)


@pytest.fixture(scope="session")
def versioned_kit(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """O kit contendo APENAS o que o git carrega, com o conteúdo da árvore atual.

    Existe porque instalar a partir do disco mede a máquina de quem roda o
    teste: `.gitignore` esconde arquivos que estão presentes em uma máquina e
    em nenhuma outra, e foi assim que uma instalação quebrada passou verde por
    meses. A lista vem de `git ls-files`; o conteúdo vem do disco, para o teste
    continuar guiando o trabalho em vez de só enxergar o último commit.
    """
    src = tmp_path_factory.mktemp("versioned-kit") / "kit"
    src.mkdir()
    listing = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    for rel in filter(None, listing.split("\0")):
        source = REPO_ROOT / rel
        if not source.is_file():  # rastreado, mas apagado na árvore de trabalho
            continue
        dest = src / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(source.read_bytes())
        dest.chmod(source.stat().st_mode & 0o777)
    return src
