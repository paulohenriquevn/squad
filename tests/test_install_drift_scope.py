"""Drift must not pull what belongs to the project, nor compare the incomparable.

Two false positives measured 2026-08-20 against `speculative`'s installation:

1. `agents/speculative.md` e os 4 validadores do projeto apareceram como
   `INSTALL_AHEAD` — "work the kit does not have". They are domain specialists:
   they must never travel into the kit (grill, decision 5).
2. `settings.json` showed up as `DIVERGED`. The two files are identical as JSON —
   what diverges is the PAIR being compared: the kit has `settings.json` (dev, hooks
   in `$CLAUDE_PROJECT_DIR/hooks/`) and `settings.plugin.json` (install, hooks in
   `.claude/hooks/`). The installed one is a correct copy of the second, and drift
   compared it against the first. It would have reported that on all 41 consumers,
   forever.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO / "mechanisms" / "gates" / "check_install_drift.py"


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
    """The README describes the routing mechanism: it belongs to the kit."""
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
# Lag is not modification — the lesson that stayed in sync_consumers and not here.
# Measured on an adopter: the detector reported 11 files "needing a human"; 5
# were real work and 4 were OLDER versions of the kit itself (`install.sh`,
# `check_xrefs.py`, `code-quality-golden-rule.md`, `code-quality-allowlist.txt`). A
# detector that reports 11 when there are 5 teaches people to ignore it, which is
# the declared reason it exists.
# ---------------------------------------------------------------------------

_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin"}


def _kit_repo_with_history(tmp_path: Path) -> tuple[Path, str, str]:
    """A git kit with two versions of the same file."""
    kit = tmp_path / "kit"
    (kit / "rules").mkdir(parents=True)
    env = {**_ENV, "HOME": str(kit)}
    def run(*a):
        return subprocess.run(["git", "-C", str(kit), *a], check=True,
                                        capture_output=True, text=True, env=env)
    run("init", "-q")
    older = "line A\nline OLD\n"
    (kit / "rules" / "x.md").write_text(older, encoding="utf-8")
    run("add", "-A"); run("-c", "commit.gpgsign=false", "commit", "-q", "-m", "v1")  # noqa: E702
    newer = "line A\nline NEW\n"
    (kit / "rules" / "x.md").write_text(newer, encoding="utf-8")
    run("add", "-A"); run("-c", "commit.gpgsign=false", "commit", "-q", "-m", "v2")  # noqa: E702
    return kit, older, newer


def test_an_old_kit_version_is_reported_as_stale_not_as_local_work(tmp_path: Path) -> None:
    kit, older, _newer = _kit_repo_with_history(tmp_path)
    install = tmp_path / "install"
    (install / "rules").mkdir(parents=True)
    (install / "rules" / "x.md").write_text(older, encoding="utf-8")

    out = _run(install, kit)
    assert "stale" in out.lower(), out
    assert "diverged: 1" not in out, "lag is not divergence that needs a human"


def test_genuinely_local_work_is_still_flagged(tmp_path: Path) -> None:
    """What was never the kit's still requires a human — that is the detector's point."""
    kit, _older, newer = _kit_repo_with_history(tmp_path)
    install = tmp_path / "install"
    (install / "rules").mkdir(parents=True)
    (install / "rules" / "x.md").write_text(newer + "a fix that exists only here\n", encoding="utf-8")

    out = _run(install, kit)
    assert "install_ahead: 1" in out or "diverged: 1" in out, out


def test_the_comparison_covers_every_tree_the_installer_carries(tmp_path: Path) -> None:
    """Four of the six trees were invisible, and the default is why.

    `--kit` defaulted to the kit's `skills/`, which is where the noise is lowest
    and also where two thirds of what an install carries stops being looked at.
    Measured on 2026-09-02: `mechanisms/kit_issues.py` and
    `mechanisms/session_ready.py` existed in the kit and not in a consumer, and
    nothing reported it — the same afternoon a syncer was found to have dropped
    that whole tree from distribution after a rename.

    Widening to the entire root is the opposite failure: 5994 files only-in-kit,
    because the kit also holds tests, wiki, images and study material that no
    consumer ever receives. The scope is what `install.sh` carries, no more.
    """
    kit, install = _trees(tmp_path)
    for tree in ("skills", "hooks", "commands", "mechanisms", "squad"):
        (kit / tree).mkdir(exist_ok=True)
        (kit / tree / "m.py").write_text("kit only\n", encoding="utf-8")
    (kit / "tests").mkdir()
    (kit / "tests" / "t.py").write_text("never installed\n", encoding="utf-8")

    out = _run(install, kit)

    # One `m.py` per installed tree is seen; `tests/t.py` is not. The count is the
    # assertion because the summary does not name files when there are few, and a
    # test that reads a rendering rather than a result breaks on formatting.
    assert "only_in_kit: 5" in out, (
        f"expected the five installed trees to be compared and tests/ to be "
        f"excluded; got: {out}")
    assert "tests/t.py" not in out, "tests/ is not carried into a consumer"


def test_a_single_tree_can_still_be_compared_on_its_own(tmp_path: Path) -> None:
    """`--kit ./rules` against a consumer's `rules/`. Restricting the scope there
    would match nothing and report a clean sweep over an empty comparison — the
    exact shape of defect this file exists to catch, arriving through its fix."""
    kit, install = _trees(tmp_path)

    out = _run(install / "rules", kit / "rules")

    assert "identical: 1" in out, out
