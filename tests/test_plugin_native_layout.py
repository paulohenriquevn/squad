"""O kit instalado como plugin nativo, sem se copiar para dentro do projeto.

O DEFEITO QUE ISTO FIXA
-----------------------
`plugin.json` anunciava um plugin instalável, mas o único caminho de instalação
que funcionava era `scripts/install.sh`, que faz `cp -r` do kit para dentro de
`<projeto>/.claude/`. Três consequências, medidas em 2026-08-26:

1. **Instalado pelo mecanismo nativo, nenhum gate rodava.** O manifesto estava
   na raiz, e o Claude Code lê `.claude-plugin/plugin.json`; não havia
   `hooks/hooks.json`; e os hooks de `settings.plugin.json` apontavam para
   `$CLAUDE_PROJECT_DIR/.claude/hooks/…`, caminho que só existe no modo cópia.
   `detect-layout.sh` então encerrava com `exit 0` sem imprimir nada:
   `stop-validation.sh` e `sessionstart-context.sh` saíam 0, mudos.
   Um gate silenciosamente desligado é indistinguível de um gate que aprovou.

2. **O agente do consumidor editava o kit.** Vivendo em `.claude/`, com
   `Edit`/`Write`/`Bash(*)` liberados e nenhum hook protegendo o caminho, o kit
   era território gravável. O próprio `scripts/check_install_drift.py` registra
   o resultado: "Twenty-two fixes to this kit lived for weeks inside one
   consumer's gitignored `.claude/` install and nowhere else."

3. **Não havia "o sistema", havia N cópias divergentes.**

A CORREÇÃO, E O QUE ELA SEPARA
------------------------------
`detect-layout.sh` passa a resolver DOIS caminhos onde antes havia um:

    KIT_DIR  — o CÓDIGO do kit (skills/, rules/, hooks/). Read-only.
    ECO      — os DADOS do ciclo (knowledge-base/, .active_plan). Gravável.

No modo nativo os dois divergem — o código fica fora do projeto, sob
`$CLAUDE_PLUGIN_ROOT` — e é essa divergência que torna o kit não-editável pelo
consumidor. Nos modos cópia e standalone eles coincidem, como sempre
coincidiram, e nada muda para quem já instalou.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / ".claude-plugin" / "plugin.json"
HOOKS_JSON = REPO / "hooks" / "hooks.json"
LEGACY_SETTINGS = REPO / "settings.plugin.json"
DETECT = REPO / "hooks" / "lib" / "detect-layout.sh"


# --------------------------------------------------------------------------
# manifesto
# --------------------------------------------------------------------------
def test_manifest_sits_where_claude_code_looks_for_it():
    """O Claude Code lê `.claude-plugin/plugin.json`. Na raiz, o arquivo é decorativo."""
    assert MANIFEST.is_file(), (
        "sem .claude-plugin/plugin.json o plugin não é reconhecido pelo "
        "mecanismo nativo, e a única instalação possível é a por cópia"
    )
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data.get("name"), "manifesto sem `name`"
    assert data.get("version"), "manifesto sem `version`"


def test_manifest_is_the_single_source_of_the_plugin_identity():
    """Dois manifestos divergentes é pior que um só no lugar errado."""
    root = REPO / "plugin.json"
    if not root.is_file():
        return  # removido — nada a conciliar
    a = json.loads(root.read_text(encoding="utf-8"))
    b = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for field in ("name", "version"):
        assert a.get(field) == b.get(field), (
            f"plugin.json e .claude-plugin/plugin.json divergem em `{field}`: "
            f"{a.get(field)!r} != {b.get(field)!r}"
        )


# --------------------------------------------------------------------------
# hooks.json
# --------------------------------------------------------------------------
def _hook_commands(doc: dict) -> list[str]:
    out: list[str] = []
    for entries in doc.get("hooks", {}).values():
        for entry in entries:
            for hook in entry.get("hooks", []) or []:
                if hook.get("command"):
                    out.append(hook["command"])
    return out


def test_hooks_json_exists_and_is_valid():
    assert HOOKS_JSON.is_file(), (
        "sem hooks/hooks.json o plugin nativo não registra hook nenhum — "
        "todo gate fica desligado e silencioso"
    )
    json.loads(HOOKS_JSON.read_text(encoding="utf-8"))


def test_every_hook_resolves_through_plugin_root():
    """Nenhum comando pode resolver por `$CLAUDE_PROJECT_DIR/.claude/`.

    Esse caminho é o do modo cópia. Um plugin nativo que o use aponta para um
    diretório que não existe, e o hook falha em silêncio.
    """
    doc = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    commands = _hook_commands(doc)
    assert commands, "hooks.json não declara comando nenhum"
    for cmd in commands:
        assert "CLAUDE_PLUGIN_ROOT" in cmd, f"hook não usa CLAUDE_PLUGIN_ROOT: {cmd}"
        assert ".claude/hooks" not in cmd, (
            f"hook resolve pelo layout de cópia em vez do plugin root: {cmd}"
        )


def test_every_declared_hook_script_exists():
    """Um caminho de hook que não resolve é um gate que nunca roda."""
    doc = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    missing = []
    for cmd in _hook_commands(doc):
        for rel in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+)", cmd):
            if not (REPO / rel).is_file():
                missing.append(rel)
    assert not missing, f"hooks declarados sem script no disco: {sorted(set(missing))}"


def test_native_and_copy_layouts_wire_the_same_events():
    """Instalar por um caminho ou por outro não pode mudar QUAIS gates existem.

    Se o modo cópia protege `Stop` e o nativo não, a mesma versão do kit dá
    duas garantias diferentes conforme o instalador — e ninguém é avisado.
    """
    native = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))["hooks"]
    legacy = json.loads(LEGACY_SETTINGS.read_text(encoding="utf-8"))["hooks"]
    assert set(native) == set(legacy), (
        "eventos divergentes entre hooks.json (nativo) e settings.plugin.json "
        f"(cópia): só no nativo={set(native) - set(legacy)}, "
        f"só na cópia={set(legacy) - set(native)}"
    )


# --------------------------------------------------------------------------
# detect-layout.sh
# --------------------------------------------------------------------------
def _resolve(project_dir: Path, env: dict | None = None) -> tuple[str, str, str]:
    """Executa detect-layout.sh e devolve (KIT_DIR, ECO, stderr)."""
    script = f'source "{DETECT}"; echo "KIT=${{KIT_DIR:-}}"; echo "ECO=${{ECO:-}}"'
    full_env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)}
    full_env.pop("CLAUDE_PLUGIN_ROOT", None)
    if env:
        full_env.update(env)
    proc = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, env=full_env
    )
    kit = eco = ""
    for line in proc.stdout.splitlines():
        if line.startswith("KIT="):
            kit = line[4:]
        elif line.startswith("ECO="):
            eco = line[4:]
    return kit, eco, proc.stderr


def _fake_kit(root: Path) -> Path:
    for d in ("skills", "rules", "hooks"):
        (root / d).mkdir(parents=True, exist_ok=True)
    return root


def test_plugin_root_supplies_the_kit_and_the_project_supplies_the_data(tmp_path):
    """O caso que não existia: código fora do projeto, dados dentro."""
    kit = _fake_kit(tmp_path / "plugin-root")
    project = tmp_path / "consumer"
    (project / ".claude").mkdir(parents=True)

    kit_dir, eco, _ = _resolve(project, {"CLAUDE_PLUGIN_ROOT": str(kit)})
    assert kit_dir == str(kit), "KIT_DIR deveria vir de CLAUDE_PLUGIN_ROOT"
    assert eco not in ("", str(kit)), "os DADOS do ciclo não podem cair dentro do kit"


def test_a_corrupt_plugin_root_is_loud(tmp_path):
    """`CLAUDE_PLUGIN_ROOT` apontando para uma árvore sem o kit precisa AVISAR.

    Era exatamente aqui que o silêncio doía: sem estrutura reconhecível, o
    script saía 0 sem uma linha, e todo gate ficava desligado parecendo aprovado.
    """
    empty = tmp_path / "not-a-kit"
    empty.mkdir()
    project = tmp_path / "consumer"
    project.mkdir()

    _, _, stderr = _resolve(project, {"CLAUDE_PLUGIN_ROOT": str(empty)})
    assert stderr.strip(), (
        "instalação de plugin corrompida não emitiu aviso — os gates ficam "
        "desligados e indistinguíveis de aprovados"
    )


def test_copy_layout_still_resolves(tmp_path):
    """Regressão: quem já instalou por cópia não pode quebrar."""
    project = tmp_path / "consumer"
    _fake_kit(project / ".claude")
    kit_dir, eco, _ = _resolve(project)
    assert kit_dir.endswith(".claude") and eco.endswith(".claude")


def test_standalone_layout_still_resolves(tmp_path):
    """Regressão: o próprio repositório do kit aberto no Claude Code."""
    project = _fake_kit(tmp_path / "kit-repo")
    kit_dir, eco, _ = _resolve(project)
    assert kit_dir in (".", str(project))
    assert eco in (".", str(project))


def test_absent_kit_stays_quiet(tmp_path):
    """Um projeto que simplesmente não usa o kit não deve ser avisado de nada.

    A contrapartida de `test_a_corrupt_plugin_root_is_loud`: o aviso vale
    quando o kit deveria estar e não está, não quando ninguém o instalou.
    """
    project = tmp_path / "plain-project"
    project.mkdir()
    kit_dir, eco, stderr = _resolve(project)
    assert kit_dir == "" and eco == ""
    assert stderr.strip() == "", f"ruído em projeto sem o kit: {stderr!r}"
