"""An empty file list is a verdict only when git was actually asked.

`git()` returned `""` for every failure: the binary missing, a timeout, a broken
repository, a subcommand exiting non-zero. All four are indistinguishable from
"nothing changed" — and "nothing changed" is exactly what makes every gate in
this hook pass.

The hook runs at the end of every session. Two of its gates are blockers and one
of those is for secrets. So the silent version of this failure is a secret gate
that did not run, inside a session that ended clean.

Outside a repository there genuinely is nothing to validate, and that stays
silent. Every other failure is a measurement that did not happen.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def hook():
    spec = importlib.util.spec_from_file_location(
        "stop_validation_under_test", _REPO / "hooks" / "stop-validation.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._GIT_UNREACHABLE.clear()
    return module


def _fails_with(monkeypatch, hook, *, returncode: int = 128, stderr: str = "",
                raises: Exception | None = None) -> None:
    def fake(*_a, **_kw):
        if raises is not None:
            raise raises
        return subprocess.CompletedProcess([], returncode, "", stderr)
    monkeypatch.setattr(hook.subprocess, "run", fake)


def test_a_missing_git_binary_is_recorded_not_swallowed(monkeypatch, hook) -> None:
    _fails_with(monkeypatch, hook, raises=FileNotFoundError("git"))

    assert hook.git("diff", "--name-only") == ""
    assert hook._GIT_UNREACHABLE, "the failure left no trace at all"
    assert "FileNotFoundError" in hook._GIT_UNREACHABLE[0]


def test_a_timeout_is_recorded(monkeypatch, hook) -> None:
    _fails_with(monkeypatch, hook,
                raises=subprocess.TimeoutExpired(cmd="git", timeout=15))

    hook.git("diff", "--name-only")

    assert hook._GIT_UNREACHABLE


def test_a_broken_repository_is_recorded_with_its_reason(monkeypatch, hook) -> None:
    _fails_with(monkeypatch, hook, returncode=128,
                stderr="fatal: bad object HEAD\n")

    hook.git("rev-list", "--count", "@{upstream}..HEAD")

    assert hook._GIT_UNREACHABLE
    assert "bad object" in hook._GIT_UNREACHABLE[0], "the reason must survive"


def test_being_outside_a_repository_stays_silent(monkeypatch, hook) -> None:
    """A scratch directory has nothing to validate, and saying so at every prompt
    is noise. This is the one failure that is genuinely not a failure."""
    _fails_with(monkeypatch, hook, returncode=128,
                stderr="fatal: not a git repository (or any of the parent directories)\n")

    hook.git("diff", "--name-only")

    assert not hook._GIT_UNREACHABLE


def test_a_clean_run_records_nothing(monkeypatch, hook) -> None:
    monkeypatch.setattr(hook.subprocess, "run",
                        lambda *_a, **_kw: subprocess.CompletedProcess([], 0, "a.py\n", ""))

    assert hook.git("diff", "--name-only") == "a.py\n"
    assert not hook._GIT_UNREACHABLE


def test_the_hook_says_the_gates_did_not_run(hook) -> None:
    """The wording carries the whole point, so it is pinned: an operator reading
    the output must not be able to mistake this for a pass."""
    source = (_REPO / "hooks" / "stop-validation.py").read_text(encoding="utf-8")

    assert "STOP GATES DID NOT RUN" in source
    assert "This is not a pass" in source
    assert "_GIT_UNREACHABLE" in source.split("def main")[1], \
        "main must consult the record before allowing"


# ── the states that are ANSWERS, not failures to measure ─────────────────────

def _repo(tmp_path: Path, *, commits: int = 1) -> Path:
    git = ["git", "-C", str(tmp_path)]
    subprocess.run([*git, "init", "-b", "workspace", "--quiet"], check=True)
    subprocess.run([*git, "config", "user.email", "t@t.invalid"], check=True)
    subprocess.run([*git, "config", "user.name", "T"], check=True)
    for n in range(commits):
        (tmp_path / f"f{n}.txt").write_text("x\n", encoding="utf-8")
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "commit", "-m", f"c{n}", "--quiet"], check=True)
    return tmp_path


def test_having_no_upstream_is_an_answer_not_a_broken_measurement(
        monkeypatch, hook, tmp_path: Path) -> None:
    """`has_upstream` exists BECAUSE a branch may not have one.

    The absent upstream is a case the code handles two lines later, and it still
    landed in `_GIT_UNREACHABLE` — so every local branch that was never pushed
    ended its session under *"STOP GATES DID NOT RUN … This is not a pass"*.
    An alarm that fires on the normal case is the alarm people learn to scroll
    past, which costs exactly what the alarm was built to buy.
    """
    monkeypatch.chdir(_repo(tmp_path, commits=2))
    hook.changed_files()

    assert not hook._GIT_UNREACHABLE, \
        f"a branch with no upstream was reported as unmeasurable: {hook._GIT_UNREACHABLE}"


def test_a_repository_with_one_commit_is_an_answer_too(
        monkeypatch, hook, tmp_path: Path) -> None:
    """`HEAD~1` does not resolve in a repository whose history is one commit.
    That is the repository saying so, not git failing to answer."""
    monkeypatch.chdir(_repo(tmp_path, commits=1))
    hook.changed_files()

    assert not hook._GIT_UNREACHABLE, \
        f"a single-commit repository was reported as unmeasurable: {hook._GIT_UNREACHABLE}"


def test_the_warning_does_not_claim_an_empty_list_it_did_not_check(hook) -> None:
    """The sentence said the gates *"graded an empty file list"* whether or not
    the list was empty. Reproduced with one changed file present and named in the
    TDD gate three paragraphs below the claim it was not there."""
    hook._GIT_UNREACHABLE.append("`git whatever` exited 128: boom")

    assert "empty file list" not in hook.unreachable_warning(["b.py"]), \
        "the warning asserts an empty list while holding a non-empty one"
    assert "empty file list" in hook.unreachable_warning([]), \
        "and still says so when the list really is empty"
