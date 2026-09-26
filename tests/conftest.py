"""Shared fixtures for Cycle ecosystem tests."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure scripts/ is importable
REPO_ROOT = Path(__file__).resolve().parent.parent
MECHANISMS = REPO_ROOT / "mechanisms"
#: The import namespace stayed flat when `scripts/` became `mechanisms/<family>/`,
#: so every family goes on the path — a test importing `check_xrefs` must not have
#: to know which drawer it was filed in.
for _family in ("gates", "conventions", "cycle", "fleet", "distribution"):
    _d = str(MECHANISMS / _family)
    if _d not in sys.path:
        sys.path.insert(0, _d)


@pytest.fixture()
def ecosystem_dir() -> Path:
    """Return the real Cycle ecosystem directory (repo root)."""
    from ecosystem_utils import find_ecosystem_dir

    return find_ecosystem_dir(start=REPO_ROOT)


@pytest.fixture(scope="session")
def versioned_kit(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The kit holding ONLY what git carries, with the working tree's content.

    It exists because installing from disk measures the machine running the test:
    `.gitignore` hides files present on one machine and on no other, and that is
    how a broken installation stayed green for months. The list comes from
    `git ls-files`; the content comes from disk, so the test keeps guiding the work
    instead of only seeing the last commit.
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
        if not source.is_file():  # tracked, but deleted in the working tree
            continue
        dest = src / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(source.read_bytes())
        dest.chmod(source.stat().st_mode & 0o777)
    return src


@pytest.fixture()
def reachable_review_panel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A machine on which every seat of `rules/review-panel.txt` resolves.

    The capability gate reads Claude Code's plugin manifest and `PATH`, so a test that
    runs it against the REAL roster measures whatever this machine has installed. On a
    workstation with `judge-codex` and `codex` that is green; on a CI runner it is
    `UNREACHABLE`, and nine tests failed on the first CI run in eleven days
    (2026-09-25) while passing locally. The seats are derived from the roster, so a
    seat added tomorrow is stubbed tomorrow.
    """
    from review_panel import parse_roster

    roster = parse_roster((REPO_ROOT / "rules" / "review-panel.txt").read_text(encoding="utf-8"))
    config_dir, bin_dir = tmp_path / "claude-config", tmp_path / "bin"
    bin_dir.mkdir()
    manifest: dict[str, list[dict[str, str]]] = {}
    for seat in roster:
        if ":" in seat.agent:
            plugin, _, agent = seat.agent.partition(":")
            install = config_dir / "plugins" / "cache" / plugin
            (install / "agents").mkdir(parents=True, exist_ok=True)
            (install / "agents" / f"{agent}.md").write_text(
                f"---\nname: {agent}\n---\nStub reviewer for the capability gate.\n",
                encoding="utf-8")
            manifest.setdefault(f"{plugin}@stub", [{"installPath": str(install),
                                                    "version": "0.0.0-stub"}])
        if not seat.is_builtin:
            stub = bin_dir / seat.invocation
            stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            stub.chmod(0o755)
    (config_dir / "plugins").mkdir(parents=True, exist_ok=True)
    (config_dir / "plugins" / "installed_plugins.json").write_text(
        json.dumps({"plugins": manifest}), encoding="utf-8")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    return config_dir
