"""`validate-command`, the PreToolUse gate over Bash — ported from a test nobody ran.

`tests/hooks/test_validate_command.sh` held these 40 assertions and NOTHING
executed it: not CI, not pytest (`testpaths` listed only `tests`), not
`run_slice_tests.sh`. When finally run it already failed. Same cases, in a file
the suite collects.

What they protect is the git discipline in `CLAUDE.md § 4`: `checkout` and
`revert` refused in favour of `switch` and `restore`, no force-push, no
`reset --hard`, and nothing originating on `main` or `develop` — plus the
recursive-delete guard over system paths. Each is a rule that costs little to
enforce and a lot to break once.

**The branch is part of the case.** Half of these decisions depend on where HEAD
is: `git commit` is fine on `workspace` and refused on `main`. A port that
dropped the branch would have turned six real blocks into passing allows, which
is how a test starts agreeing with whatever the code does.

The zone cases moved to `test_reference_zone.py`, where the retirement of
`records/references/` is explained.

The stash cases at the bottom are newer and answer a different question: not
"which command is forbidden" but "where is it being run". `git stash` is fine in
a repository with one working tree and a swap of two agents' uncommitted work in
a repository with two (kit#31).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _hook() -> Path:
    found = sorted(p for p in (REPO / "hooks").glob("validate-command.*")
                   if p.suffix in (".sh", ".py"))
    assert len(found) == 1, f"expected one implementation, found {found}"
    return found[0]


def _repo_on(tmp_path: Path, branch: str) -> Path:
    """The minimal shape the hook needs: a kit layout and a git repo with a HEAD."""
    for tree in ("skills", "rules", "hooks"):
        (tmp_path / tree).mkdir(parents=True, exist_ok=True)
    git = ["git", "-C", str(tmp_path)]
    subprocess.run([*git, "init", "-b", branch, "--quiet"], check=True)
    subprocess.run([*git, "config", "user.email", "test@test.invalid"], check=True)
    subprocess.run([*git, "config", "user.name", "Test"], check=True)
    (tmp_path / "dummy").write_text("x\n", encoding="utf-8")
    subprocess.run([*git, "add", "dummy"], check=True)
    subprocess.run([*git, "commit", "-m", "init", "--quiet"], check=True)
    return tmp_path


def _second_worktree(root: Path, at: Path) -> Path:
    """A second working tree of the same repository — one shared stash stack."""
    subprocess.run(["git", "-C", str(root), "worktree", "add", "-b", "lane",
                    str(at), "HEAD"], check=True, capture_output=True)
    return at


def _run(root: Path, command: str | None, cwd: Path | None = None) -> int:
    hook = _hook()
    cmd = ["bash", str(hook)] if hook.suffix == ".sh" else [sys.executable, str(hook)]
    tool_input = {} if command is None else {"command": command}
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": tool_input}
    return subprocess.run(cmd, input=json.dumps(payload), capture_output=True,  # noqa: PLW1510
                          text=True, cwd=cwd or root,
                          env={"PATH": __import__("os").environ["PATH"],
                               "HOME": str(root),
                               "CLAUDE_PROJECT_DIR": str(root)}).returncode


#: (command, expected exit, branch HEAD is on). 2 = blocked, 0 = allowed.
CASES: list[tuple[str, int, str]] = [
    ("git checkout feature-x", 2, "workspace"),  # git checkout is blocked
    ("git switch develop", 0, "workspace"),  # git switch is allowed
    ("git revert abc123", 2, "workspace"),  # git revert is blocked
    ("git push --force origin develop", 2, "workspace"),  # git push --force is blocked
    ("git push -f origin develop", 2, "workspace"),  # git push -f is blocked
    ("git push --force-with-lease origin develop", 0, "workspace"),  # git push --force-with-lease is allowed
    ("git reset --hard HEAD~1", 2, "workspace"),  # git reset --hard is blocked
    ("git reset --soft HEAD~1", 0, "workspace"),  # git reset --soft is allowed
    ("git stash", 0, "workspace"),  # git stash is allowed
    ("git commit -m 'bad commit'", 2, "main"),  # git commit on main is blocked
    ("git commit -m 'good commit'", 0, "workspace"),  # git commit on workspace is allowed
    ("git merge develop", 2, "main"),  # git merge on main is blocked
    ("git rebase develop", 2, "main"),  # git rebase on main is blocked
    ("git reset --soft HEAD~1", 2, "main"),  # git reset on main is blocked
    ("git cherry-pick abc123", 2, "main"),  # git cherry-pick on main is blocked
    ("git commit -m 'straight to develop'", 2, "develop"),  # G1: git commit on develop is blocked
    ("git merge workspace", 0, "develop"),  # G1: 'git merge workspace' on develop is allowed
    ("git merge --no-ff origin/workspace", 0, "develop"),  # G1: 'git merge origin/workspace' on develop is allowed
    ("git merge feature-x", 2, "develop"),  # G1: merging a non-workspace branch into develop is blocked
    ("git rebase workspace", 2, "develop"),  # G1: git rebase on develop is blocked
    ("git reset --soft HEAD~1", 2, "develop"),  # G1: git reset on develop is blocked
    ("git cherry-pick abc123", 2, "develop"),  # G1: git cherry-pick on develop is blocked
    ("git push origin develop", 0, "develop"),  # G1: git push on develop is allowed
    ("git switch develop && git commit -m x", 2, "workspace"),  # G1: 'git switch develop && git commit' is blocked
    ("git rebase develop", 0, "workspace"),  # G1: git rebase on workspace is allowed
    ("rm -rf /", 2, "workspace"),  # rm -rf / is blocked
    ("rm -rf /etc", 2, "workspace"),  # rm -rf /etc is blocked
    ("rm -rf /home", 2, "workspace"),  # rm -rf /home is blocked
    ("rm -rf ./build", 0, "workspace"),  # rm -rf ./build (project-relative) is allowed
    ("rm -rf /tmp/something", 0, "workspace"),  # rm -rf /tmp/something is allowed
    # The three conditions must hold IN THE SAME SEGMENT. Matching them
    # independently over the whole line assembles a deletion nobody typed: the
    # `rm` from one command, the `-r` from a `grep`, the root path from a third.
    # This regressed once already (B-160 in a consumer, fixed in bash and
    # reintroduced by the Python rewrite), and the consumer's own guard test
    # could not see it because its payload was incomplete.
    ("rm nota.txt && grep -rn padrao /etc/hosts", 0, "workspace"),  # rm without -r, -r from grep
    ("grep -rn foo /etc && rm nota.txt", 0, "workspace"),  # same, order reversed
    ("ls -R /etc && rm -f nota.txt", 0, "workspace"),  # recursive flag from ls, rm not recursive
    ("rm -rf build && echo done", 0, "workspace"),  # a real recursive delete, safely scoped
    ("echo start && rm -rf /etc", 2, "workspace"),  # all three in one segment: still blocked
    ("ls -la", 0, "workspace"),  # ls -la is allowed
    ("git commit -m 'feat: add thing\n\nCo-Authored-By: Someone <s@e.com>'", 2, "workspace"),  # commit with Co-Authored-By trailer is blocked
    ("git commit -m 'feat: add thing'", 0, "workspace"),  # commit without Co-Authored-By on develop is allowed
    ("git commit -m 'bad commit'", 2, "master"),  # F12: commit on 'master' is blocked
    ("git rebase HEAD~1", 2, "master"),  # F12: rebase on 'master' is blocked
    ("git switch master && git commit -m x", 2, "workspace"),  # F12: inline 'switch master && commit' is blocked
    ("git commit -m 'good commit'", 0, "workspace"),  # F12 regression: commit on 'workspace' still allowed
    ("git commit -m 'fine'", 0, "fix/some-bug"),  # F12 regression: commit on a feature branch still allowed
]


@pytest.mark.parametrize(("command", "expected", "branch"), CASES,
                         ids=[f"{b}:{'block' if e == 2 else 'allow'}:{c[:40]}"
                              for c, e, b in CASES])
def test_the_command_gate_decides_as_specified(tmp_path: Path, command: str,
                                               expected: int, branch: str) -> None:
    root = _repo_on(tmp_path, branch)

    assert _run(root, command) == expected, f"on {branch}: {command}"


def test_a_payload_with_no_command_is_allowed(tmp_path: Path) -> None:
    """Nothing to run is nothing to refuse."""
    assert _run(_repo_on(tmp_path, "workspace"), None) == 0


def test_both_outcomes_are_represented() -> None:
    """A parametrisation that drifted to all-allow would pass while checking nothing."""
    blocked = sum(1 for _, e, _ in CASES if e == 2)
    assert blocked >= 15, blocked
    assert len(CASES) - blocked >= 10, len(CASES) - blocked


def test_the_protected_branches_are_all_exercised() -> None:
    """`main` and `develop` are the two the model protects; a port that lost
    either would leave that half of the gate unmeasured."""
    branches = {b for _, _, b in CASES}
    assert {"main", "develop", "workspace"} <= branches, branches


def test_trunk_protection_follows_the_repo_not_the_literal_name_main(tmp_path: Path) -> None:
    """F12. An adopting project whose trunk is `trunk` or `release` gets the same
    protection as one using `main`, because the hook reads the remote's default
    branch rather than matching a name.

    Kept out of the table above because it needs a remote HEAD, and a case whose
    setup differs from its neighbours hides that difference when it sits among them.
    """
    root = _repo_on(tmp_path, "trunk")
    subprocess.run(["git", "-C", str(root), "remote", "add", "origin", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "symbolic-ref",
                    "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk"], check=True)

    assert _run(root, "git commit -m 'bad commit'") == 2


def test_a_feature_branch_is_not_a_trunk(tmp_path: Path) -> None:
    """The other half of F12: protecting every branch would block all work."""
    assert _run(_repo_on(tmp_path, "fix/some-bug"), "git commit -m 'ok'") == 0


# ── kit#31: the stash stack is not part of what a worktree isolates ───────────
# `git worktree` gives each tree its own index, HEAD and checkout. `refs/stash`
# is not among them — it lives in the common git dir, so every tree pushes and
# pops ONE stack and `git stash pop` takes the top entry whoever pushed it.
#
# Measured 2026-09-04: two agents in separate worktrees stashed concurrently and
# each popped the other's entry. Uncommitted work swapped trees, and was only
# recovered because one of them noticed. The table above keeps the single-tree
# case allowed: with one working tree there is nobody to swap with.


def test_stash_is_refused_from_a_worktree_that_shares_the_stack(tmp_path: Path) -> None:
    root = _repo_on(tmp_path / "repo", "workspace")
    lane = _second_worktree(root, tmp_path / "lane")

    assert _run(root, "git stash -u", cwd=lane) == 2


def test_the_tree_that_pushed_first_is_refused_too(tmp_path: Path) -> None:
    """The hazard is symmetric: the entry the main tree pushes is the entry the
    lane pops. Guarding only the linked trees leaves half the swap open."""
    root = _repo_on(tmp_path / "repo", "workspace")
    _second_worktree(root, tmp_path / "lane")

    assert _run(root, "git stash") == 2


def test_reading_the_stack_is_not_the_hazard(tmp_path: Path) -> None:
    """`list` and `show` mutate nothing. Refusing them would only teach the lane
    that the guard is noise."""
    root = _repo_on(tmp_path / "repo", "workspace")
    lane = _second_worktree(root, tmp_path / "lane")

    assert _run(root, "git stash list", cwd=lane) == 0
    assert _run(root, "git stash show -p", cwd=lane) == 0


def test_the_worktree_is_read_from_dash_c_not_only_from_the_cwd(tmp_path: Path) -> None:
    """The fleet's own briefs drive git as `git -C <repo> …`, so a guard that
    only ever asks the current directory misses the form the kit itself uses."""
    root = _repo_on(tmp_path / "repo", "workspace")
    lane = _second_worktree(root, tmp_path / "lane")
    outside = tmp_path / "outside"
    outside.mkdir()

    assert _run(root, f"git -C {lane} stash", cwd=outside) == 2
