"""A task id is not unique across items; a commit is attributed by the plan slug it names.

Task ids are per-plan and every plan starts at `T1.1`, so two items sharing a `T4.1` is the normal
case. Measured in a consumer on 2026-09-24: the last 500 commits carried 57 task-id references with
`T2.1` appearing twice. Matching the bare id over the whole repository therefore read another
item's commit as this item's, and it did so in both directions:

  - a false HIGH `task_committed_in_git_not_in_progress` for a task this item never committed —
    whose "fix" is to mark it committed against a commit that does not implement it;
  - a MASKED `plan_task_absent_from_progress`, because the inventory check defers to "a commit
    references it" and a foreign commit satisfied that.

`rules/cycle-implement.md` already asks each commit to reference "the plan slug and task ID"; the
gate now reads the slug from the `Plan: <slug>` line the halt-loop's commit template writes.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from check_checkpoint_consistency import check_checkpoint_consistency


def _git(repo: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *a],
                          capture_output=True, text=True, check=True).stdout


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    return repo


def _commit(repo: Path, rel: str, msg: str) -> str:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(rel, encoding="utf-8")
    _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD").strip()


def test_another_items_commit_is_not_attributed_to_a_pending_task(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _commit(repo, "other.py", "feat(other): x\n\nPlan: other-item\nT4.1: other item's task")
    progress = {"slug": "this-item", "tasks": [
        {"id": "T4.1", "phase": "4", "status": "pending"},
    ]}

    report = check_checkpoint_consistency(progress, repo, ["T4.1"])

    assert report.findings == ()


def test_this_items_commit_still_convicts_a_stale_checkpoint(tmp_path: Path) -> None:
    """The control: a filter that attributes nothing would pass the test above and measure nothing."""
    repo = _repo(tmp_path)
    _commit(repo, "mine.py", "feat(mine): x\n\nPlan: this-item\nT4.1: this item's task")
    progress = {"slug": "this-item", "tasks": [
        {"id": "T4.1", "phase": "4", "status": "pending"},
    ]}

    report = check_checkpoint_consistency(progress, repo, ["T4.1"])

    assert [f.code for f in report.findings] == ["task_committed_in_git_not_in_progress"]


def test_a_foreign_commit_does_not_mask_a_task_missing_from_the_checkpoint(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _commit(repo, "other.py", "feat(other): x\n\nPlan: other-item\nT4.1: other item's task")
    progress = {"slug": "this-item", "tasks": []}

    report = check_checkpoint_consistency(progress, repo, ["T4.1"])

    assert [f.code for f in report.findings] == ["plan_task_absent_from_progress"]


def test_a_slug_that_prefixes_another_does_not_attribute_its_commits(tmp_path: Path) -> None:
    """`auth` must not claim the commits of `auth-v2` — not through the `Plan:` line, and not
    through the conventional-commit scope, which is routinely the same word as a slug."""
    repo = _repo(tmp_path)
    _commit(repo, "other.py", "feat(auth): x\n\nPlan: auth-v2\nT1.1: v2's task")
    progress = {"slug": "auth", "tasks": [{"id": "T1.1", "phase": "1", "status": "pending"}]}

    report = check_checkpoint_consistency(progress, repo, ["T1.1"])

    assert report.findings == ()


def test_the_callers_slug_is_used_when_the_checkpoint_omits_it(tmp_path: Path) -> None:
    """`slug` is optional in the checkpoint schema; both callers know the slug they validate."""
    repo = _repo(tmp_path)
    _commit(repo, "mine.py", "feat(mine): x\n\nPlan: this-item\nT4.1: this item's task")
    progress = {"tasks": [{"id": "T4.1", "phase": "4", "status": "pending"}]}

    report = check_checkpoint_consistency(progress, repo, ["T4.1"], slug="this-item")

    assert [f.code for f in report.findings] == ["task_committed_in_git_not_in_progress"]


def test_without_any_slug_no_commit_is_attributed_and_the_gap_is_said(tmp_path: Path) -> None:
    """No slug from the checkpoint or the caller: the backward check cannot tell whose commit it is.

    Guessing is the defect; declining silently would read as "no commit references it". It declines
    and says so.
    """
    repo = _repo(tmp_path)
    _commit(repo, "x.py", "feat: x\n\nT4.1: somebody's task")
    progress = {"tasks": [{"id": "T4.1", "phase": "4", "status": "pending"}]}

    report = check_checkpoint_consistency(progress, repo, ["T4.1"])

    assert [f.code for f in report.findings] == ["commit_attribution_unavailable"]
    assert report.findings[0].severity == "WARN"
