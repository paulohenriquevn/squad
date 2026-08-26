"""O drift não deve puxar o que é do projeto, nem comparar o incomparável.

Dois falsos positivos medidos em 2026-08-20 contra a instalação do `speculative`:

1. `agents/speculative.md` e os 4 validadores do projeto apareceram como
   `INSTALL_AHEAD` — "trabalho que o kit não tem". São especialistas de domínio:
   nunca devem viajar para dentro do kit (grill, decisão 5).
2. `settings.json` apareceu como `DIVERGED`. Os dois arquivos são idênticos como
   JSON — o que diverge é o PAR comparado: o kit tem `settings.json` (dev, hooks em
   `$CLAUDE_PROJECT_DIR/hooks/`) e `settings.plugin.json` (instalação, hooks em
   `.claude/hooks/`). O instalado é cópia correta do segundo, e o drift o comparava
   com o primeiro. Ia acusar isso nos 41 consumidores, para sempre.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO / "scripts" / "check_install_drift.py"


def _trees(tmp_path: Path) -> tuple[Path, Path]:
    kit = tmp_path / "kit"
    install = tmp_path / "install"
    for base in (kit, install):
        (base / "rules").mkdir(parents=True)
        (base / "rules" / "x.md").write_text("igual\n", encoding="utf-8")
    (kit / "agents").mkdir()
    (install / "agents").mkdir()
    (kit / "agents" / "README.md").write_text("mecanismo\n", encoding="utf-8")
    (install / "agents" / "README.md").write_text("mecanismo\n", encoding="utf-8")
    return kit, install


def _run(install: Path, kit: Path) -> str:
    return subprocess.run(  # noqa: PLW1510
        [sys.executable, str(_SCRIPT), "--install", str(install), "--kit", str(kit)],
        capture_output=True, text=True,
    ).stdout


def test_a_project_specialist_is_not_reported_as_unharvested(tmp_path: Path) -> None:
    kit, install = _trees(tmp_path)
    (install / "agents" / "meu-dominio.md").write_text("do projeto\n", encoding="utf-8")
    assert "meu-dominio" not in _run(install, kit)


def test_the_agents_readme_stays_in_scope(tmp_path: Path) -> None:
    """O README descreve o mecanismo de roteamento: é do kit."""
    kit, install = _trees(tmp_path)
    (install / "agents" / "README.md").write_text("mecanismo + correcao local\n", encoding="utf-8")
    assert "agents/README.md" in _run(install, kit)


def test_settings_json_is_compared_against_the_plugin_variant(tmp_path: Path) -> None:
    kit, install = _trees(tmp_path)
    (kit / "settings.json").write_text('{"hooks": "dev"}\n', encoding="utf-8")
    (kit / "settings.plugin.json").write_text('{"hooks": "plugin"}\n', encoding="utf-8")
    (install / "settings.json").write_text('{"hooks": "plugin"}\n', encoding="utf-8")
    out = _run(install, kit)
    assert "settings.json" not in out.replace("settings.plugin.json", ""), out


# ---------------------------------------------------------------------------
# Defasagem não é alteração — a lição que ficou no sync_consumers e não aqui.
# Medido no `theokit-tui`: o detector reportou 11 arquivos "que precisam de um
# humano"; 5 eram trabalho real e 4 eram versões ANTIGAS do próprio kit
# (`install.sh`, `check_xrefs.py`, `code-quality-golden-rule.md`,
# `code-quality-allowlist.txt`). Um detector que acusa 11 quando são 5 ensina a
# ser ignorado, que é a razão declarada de ele existir.
# ---------------------------------------------------------------------------

_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin"}


def _kit_repo_with_history(tmp_path: Path) -> tuple[Path, str, str]:
    """Um kit git com duas versões do mesmo arquivo."""
    kit = tmp_path / "kit"
    (kit / "rules").mkdir(parents=True)
    env = {**_ENV, "HOME": str(kit)}
    def run(*a):
        return subprocess.run(["git", "-C", str(kit), *a], check=True,
                                        capture_output=True, text=True, env=env)
    run("init", "-q")
    velho = "linha A\nlinha ANTIGA\n"
    (kit / "rules" / "x.md").write_text(velho, encoding="utf-8")
    run("add", "-A"); run("-c", "commit.gpgsign=false", "commit", "-q", "-m", "v1")  # noqa: E702
    novo = "linha A\nlinha NOVA\n"
    (kit / "rules" / "x.md").write_text(novo, encoding="utf-8")
    run("add", "-A"); run("-c", "commit.gpgsign=false", "commit", "-q", "-m", "v2")  # noqa: E702
    return kit, velho, novo


def test_an_old_kit_version_is_reported_as_stale_not_as_local_work(tmp_path: Path) -> None:
    kit, velho, _novo = _kit_repo_with_history(tmp_path)
    install = tmp_path / "install"
    (install / "rules").mkdir(parents=True)
    (install / "rules" / "x.md").write_text(velho, encoding="utf-8")

    out = _run(install, kit)
    assert "stale" in out.lower(), out
    assert "diverged: 1" not in out, "defasagem não é divergência que precisa de humano"


def test_genuinely_local_work_is_still_flagged(tmp_path: Path) -> None:
    """O que nunca foi do kit continua exigindo um humano — é o ponto do detector."""
    kit, _velho, novo = _kit_repo_with_history(tmp_path)
    install = tmp_path / "install"
    (install / "rules").mkdir(parents=True)
    (install / "rules" / "x.md").write_text(novo + "correcao que so existe aqui\n", encoding="utf-8")

    out = _run(install, kit)
    assert "install_ahead: 1" in out or "diverged: 1" in out, out
