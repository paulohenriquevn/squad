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
