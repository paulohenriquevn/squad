"""Shared pytest fixtures for implement tests."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = SKILL_ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


def _find_project_root(start: Path) -> Path:
    current = start.resolve()
    while current != current.parent:
        if (current / ".claude").is_dir() or (current / ".git").exists():
            return current
        current = current.parent
    return start.parent.parent.parent


PROJECT_ROOT = _find_project_root(SKILL_ROOT)


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def fake_project(tmp_path: Path) -> Path:
    """Create a fake mini-project with src/, tests/integration/, and .git/ marker."""
    root = tmp_path / "fake-project"
    root.mkdir()
    (root / ".git").mkdir()
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "tests" / "integration").mkdir()
    return root


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )


@pytest.fixture
def git_project(tmp_path: Path) -> Path:
    """A REAL git repository with one caller, so `git worktree add` works against it.

    `fake_project` only mkdir's a `.git`, which is enough for the path checks but not for any
    command that asks git a question. B-081 is about one such question — which checkouts are
    nested inside this one — so its tests need a repository git will actually answer for.
    """
    root = tmp_path / "git-project"
    (root / "src").mkdir(parents=True)
    (root / "tests" / "integration").mkdir(parents=True)
    (root / "src" / "uses-it.ts").write_text(
        "export function caller() { return targetSymbol(1); }\n", encoding="utf-8"
    )
    (root / "src" / "target.ts").write_text(
        "export function targetSymbol(n: number) { return n; }\n", encoding="utf-8"
    )
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "initial")
    return root
