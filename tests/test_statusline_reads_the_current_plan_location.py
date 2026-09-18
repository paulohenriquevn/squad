"""The status line looked only at the pre-`.squad` plan locations.

`squad/paths.py` — the module that owns every data-root literal — puts the pointer at
`.squad/active-plan` and the plans under `.squad/records/plans/`. This script read
`.active_plan` and `records/plans/`, so on any project that had migrated it showed no
plan at all while a plan was active.

It also decided it was in a repository by testing `[ -d .git ]`. Inside a worktree, a
submodule or any subdirectory, `.git` is a FILE or is not there — and the fleet works in
worktrees, which is exactly where the branch went missing.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "mechanisms" / "fleet" / "statusline.sh"


def _consumer(root: Path) -> Path:
    """A tree shaped like a real consumer: the kit installed under `.claude/`.

    The candidate paths come from `squad.paths`, so the script needs that module to be
    importable — which in a consumer it is, from `.claude/squad/`. A bare temp
    directory is not a consumer, and testing against one would measure a layout nobody
    runs.
    """
    installed = root / ".claude" / "squad"
    installed.parent.mkdir(parents=True, exist_ok=True)
    installed.symlink_to(_SCRIPT.resolve().parents[2] / "squad")
    return root


def _line(cwd: Path) -> str:
    return subprocess.run(["bash", str(_SCRIPT)], cwd=cwd, capture_output=True,
                          text=True, timeout=120, check=False).stdout.strip()


def test_the_current_plan_location_is_read(tmp_path: Path) -> None:
    _consumer(tmp_path)
    (tmp_path / ".squad").mkdir()
    (tmp_path / ".squad" / "active-plan").write_text("a-migrated-slug\n", encoding="utf-8")

    assert "plan:a-migrated-slug" in _line(tmp_path)


def test_the_legacy_plan_location_still_works(tmp_path: Path) -> None:
    """A consumer that has not migrated must not lose its status line."""
    _consumer(tmp_path)
    (tmp_path / ".active_plan").write_text("a-legacy-slug\n", encoding="utf-8")

    assert "plan:a-legacy-slug" in _line(tmp_path)


def test_the_current_plans_directory_is_read(tmp_path: Path) -> None:
    _consumer(tmp_path)
    plans = tmp_path / ".squad" / "records" / "plans"
    plans.mkdir(parents=True)
    (plans / "newest-plan.md").write_text("# a plan\n", encoding="utf-8")

    assert "plan:newest" in _line(tmp_path)


def test_a_worktree_still_shows_its_branch(tmp_path: Path) -> None:
    """`[ -d .git ]` is false in a worktree, where `.git` is a file."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "a.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                    "-c", "commit.gpgsign=false", "commit", "-qm", "init"], check=True)
    tree = tmp_path / "tree"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", str(tree)], check=True)

    line = _line(tree)

    assert line, "the status line is empty inside a worktree"
