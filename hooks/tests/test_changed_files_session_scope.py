"""`changed_files()` reports a commit the session never made.

`stop-validation.py` builds "this session's diff" from three session-scoped
sources -- unstaged, staged, untracked -- and then folds in a fourth that is
not session-scoped at all:

    git diff --name-only HEAD~1..HEAD

guarded only by "the branch has unpushed commits". On a long-lived branch that
guard is permanently true, so the newest commit is re-attributed to every
later session forever. Measured in `theo` on 2026-09-12: branch `workspace`,
9 commits ahead of `origin/workspace`, HEAD `6c22c4ecf` touching exactly one
file -- and that file appears in `changed_files()` while
`git status --porcelain` for it is empty.

WHY THIS TEST CANNOT SIMPLY BE MADE GREEN
-----------------------------------------
The git state of "this session committed and did not push" is BYTE-IDENTICAL
to "a previous session committed and did not push". The sibling suite already
depends on the first being graded
(`test_unpushed_commit_without_changelog_still_blocks`), so no change to the
git queries alone can satisfy both. Separating them needs a reference point
git does not carry: HEAD recorded at SessionStart, keyed by `session_id`.

That id is already on the context object (`squad/contexts.py`), and no hook
reads it -- so the discriminator is available and unused. This test is the
pin that forces that decision rather than a regex tweak.

WHY IT LIVES HERE NOW
---------------------
This pin was written into a consumer's gitignored `.claude/hooks/tests/` on 2026-09-12
and named after the card that raised it. Both facts cost it: a file under `.claude/`
reaches exactly one machine, and a name built from a ticket id stops explaining itself
the moment the tracker moves. Ported 2026-09-16, renamed for what it tests.

The defect bites this kit's own workflow hardest. `workspace` is a permanent branch that
is never deleted, so "the branch has unpushed commits" is true almost always, and the
fold runs on nearly every session. Reproduced in the kit's own repo the day it was
ported: two commits ahead of origin, three files folded in from `HEAD~1..HEAD`.

Marked xfail rather than deleted or made green. The condition it pins is real and the
fix it names — HEAD recorded at SessionStart, keyed by the `session_id` that
`squad/contexts.py` already carries and no hook reads — is a decision, not a regex
tweak. An xfail keeps the suite honest about a defect it has not fixed; deleting the
test would report health the code does not have.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "stop-validation.py"
TEMPLATE = "charts/thing/templates/configmap.yaml"


def _load_hook():
    spec = importlib.util.spec_from_file_location("stop_validation_under_test", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture()
def repo_with_pre_session_commit(tmp_path: Path) -> Path:
    """A repo whose only unpushed commit predates the session, tree clean."""
    repo = tmp_path / "repo"
    for sub in ("skills", "rules", "hooks"):
        (repo / sub).mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "workspace")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n")
    (repo / "rules" / "keep").write_text("")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "baseline")

    bare = tmp_path / "origin.git"
    _git(repo, "init", "-q", "--bare", str(bare))
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "push", "-q", "-u", "origin", "workspace")

    template = repo / TEMPLATE
    template.parent.mkdir(parents=True, exist_ok=True)
    template.write_text("apiVersion: v1\nkind: ConfigMap\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "chore(helm): translate the comments")
    return repo


def test_the_working_tree_is_genuinely_clean(repo_with_pre_session_commit):
    """Control. Without this, the RED test below could pass for a wrong reason."""
    repo = repo_with_pre_session_commit
    assert _git(repo, "status", "--porcelain") == ""
    assert _git(repo, "rev-list", "--count", "@{upstream}..HEAD") == "1"
    assert TEMPLATE in _git(repo, "diff", "--name-only", "HEAD~1..HEAD")


@pytest.mark.xfail(reason="the fold is not session-scoped; the fix needs HEAD recorded"
                          " at SessionStart, keyed by session_id", strict=True)
def test_a_path_touched_solely_by_the_previous_commit_is_not_session_work(
    repo_with_pre_session_commit, monkeypatch
):
    """The fold re-attributes a pre-session commit to this session."""
    repo = repo_with_pre_session_commit
    monkeypatch.chdir(repo)
    hook = _load_hook()

    reported = hook.changed_files()

    assert TEMPLATE not in reported, (
        "`changed_files()` re-attributed a commit this session never made; "
        f"reported={reported}"
    )
