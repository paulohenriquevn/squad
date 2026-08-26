"""O kit instalado não é território gravável do consumidor.

O DEFEITO QUE ISTO FIXA
-----------------------
Instalado por cópia, o kit vive em `<projeto>/.claude/`, e `settings.plugin.json`
libera `Edit`, `Write` e `Bash(*)`. Nenhum hook cobria esse caminho:
`boundary-check.sh` protegia apenas `knowledge-base/references/` e
`knowledge-base/tools/`, e `validate-command.sh` não mencionava
`.claude/skills`, `.claude/rules` nem `.claude/hooks`. O `.kit-manifest.txt`,
escrito pelo instalador justamente para dizer o que veio do kit, não era lido
por hook nenhum.

O resultado está registrado pelo próprio repositório, em
`scripts/check_install_drift.py`:

    "Twenty-two fixes to this kit lived for weeks inside one consumer's
     gitignored `.claude/` install and nowhere else. Nobody hid them.
     Nothing looked."

Uma correção escrita dentro do kit instalado protege exatamente uma máquina, e
some no próximo `install.sh --force`.

O QUE CONTINUA GRAVÁVEL, E POR QUÊ
----------------------------------
A fronteira não é `.claude/` inteiro — isso quebraria o uso normal. O que é do
PROJETO permanece gravável e está enumerado abaixo em
`test_project_owned_paths_stay_writable`: a configuração (`rules/*.txt`), os
especialistas de domínio (`agents/`), tudo sob `knowledge-base/`, e o
`settings.json`. O que é CONTRATO do kit — skills, regras normativas, hooks,
scripts — é read-only.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "hooks" / "boundary-check.sh"

BLOCK = 2
ALLOW = 0


def _run(file_path: str, project: Path, plugin_root: Path | None = None) -> int:
    payload = json.dumps({"tool_input": {"file_path": file_path}})
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project)}
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    if plugin_root is not None:
        env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    proc = subprocess.run(
        ["bash", str(HOOK)], input=payload, capture_output=True, text=True, env=env
    )
    return proc.returncode


@pytest.fixture()
def copy_install(tmp_path: Path) -> Path:
    """Um projeto com o kit instalado por cópia, como `install.sh` o escreve."""
    project = tmp_path / "consumer"
    eco = project / ".claude"
    for d in ("skills/review", "rules", "hooks/lib", "scripts", "commands",
              "agents", "knowledge-base/plans"):
        (eco / d).mkdir(parents=True, exist_ok=True)
    (eco / "skills/review/SKILL.md").write_text("kit\n", encoding="utf-8")
    (eco / "rules/cycle-review.md").write_text("kit\n", encoding="utf-8")
    (eco / "rules/code-quality-languages.txt").write_text("# projeto\n", encoding="utf-8")
    (eco / ".kit-manifest.txt").write_text(
        "# escrito por install.sh\nskills/review\nrules/cycle-review.md\n"
        "rules/code-quality-languages.txt\n",
        encoding="utf-8",
    )
    return project


# --------------------------------------------------------------------------
# o que o kit possui — read-only
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "rel",
    [
        ".claude/skills/review/SKILL.md",
        ".claude/rules/cycle-review.md",
        ".claude/hooks/stop-validation.sh",
        ".claude/hooks/lib/detect-layout.sh",
        ".claude/scripts/check_xrefs.py",
        ".claude/commands/plan-goal.md",
    ],
)
def test_kit_owned_paths_are_blocked(copy_install: Path, rel: str):
    """Editar o kit instalado precisa ser recusado, não aceito em silêncio."""
    assert _run(str(copy_install / rel), copy_install) == BLOCK, (
        f"{rel} aceitou escrita — uma correção feita aqui protege uma máquina "
        "e some no próximo install --force"
    )


def test_relative_paths_are_blocked_too(copy_install: Path):
    """O agente cita caminho relativo com a mesma frequência que absoluto."""
    assert _run(".claude/skills/review/SKILL.md", copy_install) == BLOCK


# --------------------------------------------------------------------------
# o que o projeto possui — gravável
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "rel",
    [
        ".claude/rules/code-quality-languages.txt",  # configuração do projeto
        ".claude/agents/meu-dominio.md",             # especialista do projeto
        ".claude/knowledge-base/plans/x-plan.md",    # saída do ciclo
        ".claude/settings.json",                     # fiação do projeto
        "src/app.py",                                # o código do consumidor
        "README.md",
    ],
)
def test_project_owned_paths_stay_writable(copy_install: Path, rel: str):
    """A fronteira é o CONTRATO do kit, não o diretório `.claude/` inteiro."""
    assert _run(str(copy_install / rel), copy_install) == ALLOW, (
        f"{rel} foi bloqueado, mas pertence ao projeto"
    )


def test_a_project_skill_is_not_the_kits(copy_install: Path):
    """Uma skill que o PROJETO escreveu continua sendo dele.

    É para isso que o `.kit-manifest.txt` existe: sem ele, a única forma de
    separar seria adivinhar por nome.
    """
    own = copy_install / ".claude/skills/placement-algorithms/SKILL.md"
    own.parent.mkdir(parents=True, exist_ok=True)
    own.write_text("do projeto\n", encoding="utf-8")
    assert _run(str(own), copy_install) == ALLOW, (
        "uma skill do projeto foi tratada como do kit — o manifesto não foi lido"
    )


# --------------------------------------------------------------------------
# modo nativo
# --------------------------------------------------------------------------
def test_native_plugin_root_is_read_only(tmp_path: Path):
    """No modo nativo o kit está fora do projeto — e segue read-only."""
    kit = tmp_path / "plugin-root"
    for d in ("skills", "rules", "hooks"):
        (kit / d).mkdir(parents=True)
    project = tmp_path / "consumer"
    project.mkdir()
    assert _run(str(kit / "skills" / "review" / "SKILL.md"), project, plugin_root=kit) == BLOCK


# --------------------------------------------------------------------------
# regressão: a fronteira que já existia
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "rel",
    ["knowledge-base/references/outro-projeto.md", "knowledge-base/tools/argo-cd.md"],
)
def test_study_zone_stays_read_only(copy_install: Path, rel: str):
    assert _run(str(copy_install / ".claude" / rel), copy_install) == BLOCK


def test_a_project_without_the_kit_allows_everything(tmp_path: Path):
    """Sem kit instalado, este hook não tem fronteira nenhuma a defender."""
    plain = tmp_path / "plain"
    plain.mkdir()
    assert _run(str(plain / "src" / "app.py"), plain) == ALLOW
