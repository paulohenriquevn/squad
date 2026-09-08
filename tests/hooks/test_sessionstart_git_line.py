"""The opening context goes quiet in exactly the environment the kit works in.

`git_line()` asked `Path(".git").is_dir()`. Inside a git worktree `.git` is a
FILE holding a pointer to the common git dir, so the test was false and the
session started with no branch, no dirty count and no "ahead of upstream" — with
nothing saying why.

The kit uses worktrees deliberately: `/review` runs its agents in isolated ones,
and `validate-command` carries a whole guard about the stash they share. So the
line that tells an agent which branch it is on disappeared precisely where the
git discipline is hardest to keep by memory.

Second defect in the same function: it read the CWD, while every other hook here
resolves `layout.project_dir` first. A hook does not choose its working
directory.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def hook():
    spec = importlib.util.spec_from_file_location(
        "sessionstart_under_test", REPO / "hooks" / "sessionstart-context.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _repo(root: Path) -> Path:
    git = ["git", "-C", str(root)]
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run([*git, "init", "-b", "workspace", "--quiet"], check=True)
    subprocess.run([*git, "config", "user.email", "t@t.invalid"], check=True)
    subprocess.run([*git, "config", "user.name", "T"], check=True)
    (root / "seed.txt").write_text("x\n", encoding="utf-8")
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-m", "init", "--quiet"], check=True)
    return root


def test_a_plain_repository_reports_its_branch(hook, tmp_path: Path) -> None:
    line = hook.git_line(_repo(tmp_path / "repo"))
    assert line and "branch=workspace" in line


def test_a_worktree_reports_its_branch_too(hook, tmp_path: Path) -> None:
    """`.git` is a file here, and that is the whole difference."""
    root = _repo(tmp_path / "repo")
    lane = tmp_path / "lane"
    subprocess.run(["git", "-C", str(root), "worktree", "add", "-b", "lane",
                    str(lane), "HEAD"], check=True, capture_output=True)
    assert (lane / ".git").is_file() and not (lane / ".git").is_dir()

    line = hook.git_line(lane)
    assert line, "a worktree got no git line at all"
    assert "branch=lane" in line


def test_outside_a_repository_there_is_nothing_to_say(hook, tmp_path: Path) -> None:
    assert hook.git_line(tmp_path) is None


def test_the_line_follows_the_project_not_the_working_directory(
        hook, tmp_path: Path, monkeypatch) -> None:
    """A hook does not choose its CWD, and every other hook here resolves the
    project first."""
    root = _repo(tmp_path / "repo")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    line = hook.git_line(root)
    assert line and "branch=workspace" in line


def test_the_injected_context_carries_the_git_line_in_a_worktree(tmp_path: Path) -> None:
    """End to end: the payload the session actually receives."""
    kit = tmp_path / "kit"
    for tree in ("skills", "rules", "hooks"):
        (kit / tree).mkdir(parents=True, exist_ok=True)
    root = _repo(tmp_path / "repo")
    lane = tmp_path / "lane"
    subprocess.run(["git", "-C", str(root), "worktree", "add", "-b", "lane",
                    str(lane), "HEAD"], check=True, capture_output=True)

    import os
    done = subprocess.run(  # noqa: PLW1510 — stdout is the assertion
        [sys.executable, str(REPO / "hooks" / "sessionstart-context.py")],
        input=json.dumps({"hook_event_name": "SessionStart", "source": "startup"}),
        capture_output=True, text=True, cwd=lane,
        env={"PATH": os.environ["PATH"], "HOME": str(tmp_path),
             "CLAUDE_PROJECT_DIR": str(lane), "CLAUDE_PLUGIN_ROOT": str(kit)})

    context = json.loads(done.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "branch=lane" in context
