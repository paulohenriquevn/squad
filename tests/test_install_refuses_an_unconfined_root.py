"""The installer's destructive half is rooted at `$TARGET/.claude`, and `$TARGET` is argv[1].

Until this file existed the only refusal was "target is the source repo itself". Every
other path was accepted, so `bash install.sh ~` resolved ECO to the machine-wide Claude
configuration directory and `rm -rf "${ECO:?}/$item"` ran over it — settings.json rewritten
with this kit's hook wiring for every project on the machine, `scripts/` removed, and the
backup snapshot covering only `rules/` and `agents/`.

The vector is a mistyped or agent-supplied argument, not a remote attacker. These tests
pin the refusal, not the message.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

INSTALL = Path(__file__).resolve().parents[1] / "mechanisms" / "distribution" / "install.sh"


def _run(target: Path, home: Path, *flags: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, HOME=str(home))
    env.pop("CLAUDE_CONFIG_DIR", None)
    return subprocess.run(["bash", str(INSTALL), str(target), *flags],
                          capture_output=True, text=True, timeout=300, env=env, check=False)


def test_the_home_directory_is_not_an_install_target(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text('{"kept": true}', encoding="utf-8")

    done = _run(home, home, "--force")

    assert done.returncode != 0, "the installer accepted the machine-wide config root"
    assert (home / ".claude" / "settings.json").read_text(encoding="utf-8") == '{"kept": true}'


# A project marker (.git, package.json) was the other half of the proposed remedy and is
# deliberately NOT required: the kit's own suite installs into bare temporary directories
# more than thirty times, and a marker rule would refuse the job the installer exists to
# do. What the vector actually needs is a refusal of the roots that are never a project.


def test_the_config_directory_named_by_the_environment_is_not_a_target(tmp_path: Path) -> None:
    """`CLAUDE_CONFIG_DIR` moves the machine-wide root; the refusal must move with it."""
    home = tmp_path / "home"
    home.mkdir()
    config = tmp_path / "elsewhere" / "claude"
    config.mkdir(parents=True)
    (config / "settings.json").write_text('{"kept": true}', encoding="utf-8")

    env = dict(os.environ, HOME=str(home), CLAUDE_CONFIG_DIR=str(config))
    done = subprocess.run(["bash", str(INSTALL), str(config.parent), "--force"],
                          capture_output=True, text=True, timeout=300, env=env, check=False)

    assert done.returncode != 0, "the installer accepted the configured machine-wide root"
    assert (config / "settings.json").read_text(encoding="utf-8") == '{"kept": true}'


def test_the_filesystem_root_is_not_an_install_target(tmp_path: Path) -> None:
    done = _run(Path("/"), tmp_path / "home")
    assert done.returncode != 0, "the installer accepted / as a target"


def test_an_ordinary_directory_is_still_accepted(tmp_path: Path) -> None:
    """The guard must refuse the machine, not the job the installer exists to do."""
    target = tmp_path / "project"
    target.mkdir()

    done = _run(target, tmp_path / "home")

    assert done.returncode == 0, f"an ordinary target was refused:\n{done.stderr[-2000:]}"
    assert (target / ".claude" / "skills").is_dir()
