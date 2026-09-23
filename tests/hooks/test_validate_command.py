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
    return subprocess.run(cmd, input=json.dumps(payload), capture_output=True,
                          text=True, cwd=cwd or root,
                          env={"PATH": __import__("os").environ["PATH"],
                               "HOME": str(root),
                               "CLAUDE_PROJECT_DIR": str(root)}, check=False).returncode


#: (command, expected exit, branch HEAD is on). 2 = blocked, 0 = allowed.
CASES: list[tuple[str, int, str]] = [
    ("git checkout feature-x", 2, "workspace"),  # git checkout is blocked
    ("git switch develop", 0, "workspace"),  # git switch is allowed
    ("git revert abc123", 2, "workspace"),  # git revert is blocked
    ("git push --force origin develop", 2, "workspace"),  # git push --force is blocked
    ("git push -f origin develop", 2, "workspace"),  # git push -f is blocked
    # `--force-with-lease` on a PERMANENT branch is blocked. This row read `0` and
    # pinned the free pass: the hook's own refusal text said "--force-with-lease only
    # when explicitly authorized" while nothing asked about authorization, and the flag
    # matched none of FORCE_TOKEN_RE's alternatives. The lease guards against
    # clobbering a fetch you have not seen; it does not make rewriting develop's
    # published history safe. git-safety.md § 1: never on main, develop or workspace.
    ("git push --force-with-lease origin develop", 2, "workspace"),
    # On a disposable branch it stays allowed — the rule permits it there, and a guard
    # that refuses everything is a guard people route around.
    ("git push --force-with-lease origin an-experiment", 0, "workspace"),
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
    # A NEWLINE separates commands exactly as `;` does, and the Bash tool is given
    # multi-line blocks routinely. Splitting on `;`/`&&`/`||` alone leaves every
    # multi-line block as one segment, which is where this false positive survived
    # its first fix.
    ("rm -f x_test.go\ngrep -rn foo cmd | sed 's/^/  /'", 0, "workspace"),  # newline-separated
    ("ls /usr/lib > /dev/null\nrm -f BACKLOG.md.bak\ngrep -rn foo .", 0, "workspace"),  # three lines, three commands
    ("echo start\nrm -rf /etc", 2, "workspace"),  # still blocked when the line itself is dangerous
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


def test_the_branch_is_read_from_dash_c_not_only_from_the_cwd(tmp_path: Path) -> None:
    """`git -C <repo> commit` is judged by the branch of THAT repo.

    `strip_git_globals` removed `-C <path>` so the commit would still be seen,
    and then the branch was resolved in the cwd — so the guard read the right
    verb against the wrong repository. Both directions were wrong: a commit onto
    a trunk was allowed because the current directory happened to sit on
    `workspace`, and a legitimate commit was refused naming a branch the target
    repo was not on.

    `working_trees()` in the same file already honours `-C`, for the reason its
    docstring gives: the fleet's briefs drive git that way.
    """
    here = _repo_on(tmp_path / "here", "workspace")
    there = _repo_on(tmp_path / "there", "main")

    assert _run(here, f"git -C {there} commit -m x") == 2, \
        "a commit onto another repo's trunk walked through"
    assert _run(there, f"git -C {here} commit -m x") == 0, \
        "a commit onto workspace was refused because the CWD sat on a trunk"


def test_the_permanent_branch_cannot_be_deleted(tmp_path: Path) -> None:
    """`workspace` is a single permanent branch, never deleted, never recreated.

    Every rule about it assumed it exists. Deleting it discards whatever was not
    promoted, and the next `git switch workspace` creates a branch with the same
    name and none of the history the rules refer to.
    """
    root = _repo_on(tmp_path, "workspace")

    assert _run(root, "git branch -D workspace") == 2
    assert _run(root, "git branch -d develop") == 2
    assert _run(root, "git branch -D fix/some-bug") == 0, \
        "a disposable branch is the caller's business"


def test_a_cd_earlier_in_the_chain_is_part_of_the_deletion(tmp_path: Path) -> None:
    """`cd /etc && rm -rf *` is the same deletion as `rm -rf /etc/*`.

    Judging each segment alone fixed a false positive and opened its mirror: the
    dangerous path moved into a `cd` that the `rm` segment no longer carries.
    Both halves are needed — the segment rule stays, and a `cd` onto a system or
    home root travels with it.
    """
    root = _repo_on(tmp_path, "workspace")

    assert _run(root, "cd /etc && rm -rf *") == 2
    assert _run(root, "cd /home/someone\nrm -rf .") == 2
    assert _run(root, "cd build && rm -rf *") == 0, \
        "a project-relative cd is not a system root"
    assert _run(root, "cd /etc && ls -la") == 0, "reading there is not deleting there"


# ── B-264: a document that QUOTES the command is not an invocation of it ──────
# The guard already knows this for quoted text — `_QUOTED.sub("", cmd)` strips it,
# with the comment "nor one that merely mentions the stash". A heredoc body is not
# quoted, so the same sentence inside one still reads as a command.
#
# Measured 2026-09-23: writing the alignment brief FOR this very item was refused,
# because the prose describing the defect contains the command that causes it. The
# guard cannot see the hook that really runs it, and does see a sentence about it —
# both halves of one mismatch between what it inspects and what it means to catch.


def test_a_heredoc_body_that_mentions_the_stash_is_not_an_invocation(tmp_path):
    """Writing prose about the shared stack must not read as touching it."""
    root = _repo_on(tmp_path, "workspace")
    _second_worktree(root, tmp_path / "lane")

    command = (
        "cat > notes.md <<'DOC'\n"
        "The pre-commit hook runs git stash in a repository with three worktrees.\n"
        "DOC"
    )
    assert _run(root, command) == 0


def test_a_real_invocation_beside_a_heredoc_is_still_refused(tmp_path):
    """The guard that stops matching prose must not stop matching commands.

    Without this, the fix for the case above is indistinguishable from deleting the
    guard: a test that only asserts the false positive is gone passes just as well
    when the check was removed entirely.
    """
    root = _repo_on(tmp_path, "workspace")
    _second_worktree(root, tmp_path / "lane")

    command = (
        "cat > notes.md <<'DOC'\n"
        "harmless prose\n"
        "DOC\n"
        "git stash"
    )
    assert _run(root, command) == 2


def test_a_heredoc_fed_to_a_shell_is_still_inspected(tmp_path):
    """`bash <<EOF` EXECUTES its body, so that body is commands and not data.

    This is why the fix cannot simply strip every heredoc: the interpreter case is
    exactly where the text IS an invocation.
    """
    root = _repo_on(tmp_path, "workspace")
    _second_worktree(root, tmp_path / "lane")

    command = "bash <<'SH'\ngit stash\nSH"
    assert _run(root, command) == 2


# ── B-264: the hook that writes to the shared stack is invisible to this guard ─
# `working_trees()` refuses a PERSON typing the command under several worktrees.
# It cannot see `.githooks/pre-commit`, which invokes lint-staged, which pushes to
# `refs/stash` on EVERY commit — measured 2026-09-23: two orphaned backup entries
# sat on the stack, so the cleanup had already failed twice unnoticed.
#
# So the kit refuses the safe case and permits the dangerous one in silence. The
# commit itself IS a command this guard sees, which is where the asymmetry closes.
#
# A WARNING and never a refusal: refusing commits under several worktrees is the
# constant obstruction `.githooks/pre-commit` declined in its own docblock, and it
# would fire on every commit in a fleet that uses worktrees by design.


def test_committing_with_several_worktrees_warns_about_the_shared_stack(tmp_path):
    """The commit is allowed, and the stack it will touch is named."""
    root = _repo_on(tmp_path, "workspace")
    _second_worktree(root, tmp_path / "lane")

    hook = _hook()
    cmd = ["bash", str(hook)] if hook.suffix == ".sh" else [sys.executable, str(hook)]
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
               "tool_input": {"command": "git commit -m 'work'"}}
    done = subprocess.run(cmd, input=json.dumps(payload), capture_output=True,
                          text=True, cwd=root)

    assert done.returncode == 0, "a commit must not be refused over this"
    assert "stash" in (done.stdout + done.stderr).lower(), (
        "committing under several worktrees said nothing about the shared stack. "
        "lint-staged pushes to it on every commit and this guard is the only thing "
        "that sees the commit at all."
    )


def test_committing_with_one_worktree_stays_silent(tmp_path):
    """One tree, nobody to swap with — a warning there is noise that trains people to ignore it."""
    root = _repo_on(tmp_path, "workspace")

    hook = _hook()
    cmd = ["bash", str(hook)] if hook.suffix == ".sh" else [sys.executable, str(hook)]
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
               "tool_input": {"command": "git commit -m 'work'"}}
    done = subprocess.run(cmd, input=json.dumps(payload), capture_output=True,
                          text=True, cwd=root)

    assert done.returncode == 0
    assert "stash" not in (done.stdout + done.stderr).lower(), (
        "a single-worktree commit was warned about a stack nobody else touches"
    )
