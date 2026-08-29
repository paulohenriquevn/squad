"""`generate_plugin_settings.py --check` is a CI gate and had no test.

It exists to eliminate the duplication between settings.json and
settings.plugin.json. If the prefix rewrite stops happening, the plugin file points at
paths that do not exist in the installation — and `--check` keeps saying OK.

PORTED FROM THE SIBLING KIT, 2026-08-29
---------------------------------------
Both kits ship `scripts/generate_plugin_settings.py`; only one guarded it. Editing
`settings.json` and `settings.plugin.json` by hand desynchronised them here, the
sibling's suite failed within seconds, and this one stayed green over the same
drift — a generator with no drift check is a generator nobody runs.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "generate_plugin_settings.py"

_spec = importlib.util.spec_from_file_location("generate_plugin_settings", SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def test_reescreve_prefixo_de_hooks():
    assert (
        _mod.rewrite_value("$CLAUDE_PROJECT_DIR/hooks/validate-command.sh")
        == "$CLAUDE_PROJECT_DIR/.claude/hooks/validate-command.sh"
    )


def test_reescreve_prefixo_de_scripts_e_knowledge_base():
    assert _mod.rewrite_value("$CLAUDE_PROJECT_DIR/scripts/x.py").startswith(
        "$CLAUDE_PROJECT_DIR/.claude/scripts/"
    )
    assert _mod.rewrite_value("$CLAUDE_PROJECT_DIR/records/y.md").startswith(
        "$CLAUDE_PROJECT_DIR/.claude/records/"
    )


def test_nao_reescreve_caminho_fora_da_lista():
    value = "$CLAUDE_PROJECT_DIR/rules/thing.txt"

    assert _mod.rewrite_value(value) == value


def test_transform_desce_em_listas_e_dicionarios():
    src = {"hooks": [{"command": "$CLAUDE_PROJECT_DIR/hooks/a.sh", "n": 1}]}

    out = _mod.transform(src)

    assert out["hooks"][0]["command"] == "$CLAUDE_PROJECT_DIR/.claude/hooks/a.sh"
    assert out["hooks"][0]["n"] == 1


def test_transform_preserva_tipos_nao_string():
    assert _mod.transform({"a": [1, True, None]}) == {"a": [1, True, None]}


def test_check_reporta_sincronizado_no_repo():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True, cwd=REPO_ROOT
    )

    assert result.returncode == 0, result.stderr


def test_arquivo_gerado_nao_contem_prefixo_standalone_nos_diretorios_reescritos():
    """The proof that the rewrite really happened in the versioned file."""
    data = json.loads((REPO_ROOT / "settings.plugin.json").read_text(encoding="utf-8"))

    blob = json.dumps(data)
    for d in _mod.REWRITE_DIRS:
        assert f"$CLAUDE_PROJECT_DIR/{d}" not in blob, f"prefixo standalone sobrou em {d}"
