"""A convention check that grades history it cannot change is grading the wrong thing.

The gate's default `-40` window is right for a standalone audit — there, grading history
IS the question. As a PRE-PUSH gate it is a deadlock rather than a nuisance.

Measured on a consumer 2026-09-16: four violations in the window, THREE already on
`origin/workspace`. No amend reaches a pushed commit and only a force-push would; the two
nearest left the window in eleven and thirteen commits, which could not happen — because
the gate refused the commits that would have moved it. Nine verified commits sat behind
that wall, and RELEASE could not run end to end because the push could not happen.

Every part was individually right. The gate reported a true fact, the hook correctly
refused, and the floor forbids switching either off. What was wrong is that two callers
shared one range.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_GATE = (Path(__file__).resolve().parents[1] / "mechanisms" / "gates"
         / "check_contribution_conventions.py")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True,
                          check=True, timeout=120).stdout.strip()


def _repo_with_a_pushed_violation(tmp_path: Path) -> Path:
    """A bad commit on the upstream, and a good one only here."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "workspace")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    _git(repo, "add", "-A")
    # No type, no scope: a header_shape violation by any convention.
    _git(repo, "commit", "-qm", "this commit has no conventional header at all")

    bare = tmp_path / "origin.git"
    _git(repo, "init", "-q", "--bare", str(bare))
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "push", "-q", "-u", "origin", "workspace")

    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "feat(thing): a clean local commit\n\nWith a body.")
    return repo


def _run(repo: Path, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(_GATE), "--repo", str(repo), *flags],
                          capture_output=True, text=True, timeout=180, check=False)


def test_the_introduced_range_grades_only_what_the_push_adds(tmp_path: Path) -> None:
    repo = _repo_with_a_pushed_violation(tmp_path)
    result = _run(repo, "--introduced")
    assert "origin/workspace..HEAD" in result.stdout, \
        "the report does not name the range it actually graded"
    assert result.returncode == 0, (
        "the only violation is on a commit already pushed, which this push does not "
        f"introduce:\n{result.stdout}")


def test_the_default_window_still_grades_history(tmp_path: Path) -> None:
    """The audit caller must keep its reach — the fix separates two callers, it does
    not weaken one."""
    result = _run(_repo_with_a_pushed_violation(tmp_path))
    assert result.returncode == 1
    assert "over -40" in result.stdout


def test_a_finding_on_a_pushed_commit_says_it_cannot_be_amended(tmp_path: Path) -> None:
    """Printing fixable and unfixable findings identically is what made a deadlock look
    like a to-do list."""
    out = _run(_repo_with_a_pushed_violation(tmp_path)).stdout
    assert "[already pushed]" in out
    assert "An amend cannot reach them" in out
    assert "--introduced" in out, "the report names no way out"


def test_a_branch_with_no_upstream_grades_everything_it_has(tmp_path: Path) -> None:
    """Nothing is pushed, so everything is fixable; grading it all is honest and safe."""
    repo = tmp_path / "solo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "workspace")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "no conventional header here either")
    result = _run(repo, "--introduced")
    assert "over HEAD" in result.stdout
    assert result.returncode == 1
    assert "[already pushed]" not in result.stdout
