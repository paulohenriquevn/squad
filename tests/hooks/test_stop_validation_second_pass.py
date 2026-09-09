"""A Stop hook that answers the same way forever makes the session unstoppable.

`stop_hook_active` is true when this stop attempt was already interrupted by a
Stop hook. The kit's own library says what happens if it is ignored, in two
places — `squad/contexts.py`: *"A hook that calls `prevent()` without checking it
makes the session unstoppable"*, and `squad/outputs.py`: *"Guard
`stop_hook_active` before calling this or the session cannot end"*.

The hook never read the field. Every payload in the suite sent `false`, so the
second pass had no test and the first one always passed. A blocker the model
cannot clear — a `.env` that is deliberately there, a CHANGELOG entry it will not
invent — was a session with no exit but the environment variable, which the model
cannot set for the hook's own process.

The gate still fires. It fires ONCE: the second time it degrades to a warning,
having already been heard and having no new information to add.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _repo_with_unrecorded_change(tmp_path: Path) -> Path:
    git = ["git", "-C", str(tmp_path)]
    subprocess.run([*git, "init", "-b", "workspace", "--quiet"], check=True)
    subprocess.run([*git, "config", "user.email", "t@t.invalid"], check=True)
    subprocess.run([*git, "config", "user.name", "T"], check=True)
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n",
                                           encoding="utf-8")
    (tmp_path / "seed.txt").write_text("x\n", encoding="utf-8")
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-m", "init", "--quiet"], check=True)
    # Production source changed, nothing recorded it: the CHANGELOG blocker.
    (tmp_path / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    return tmp_path


def _stop(root: Path, *, active: bool) -> subprocess.CompletedProcess:
    payload = {"hook_event_name": "Stop", "stop_hook_active": active}
    import os
    return subprocess.run(  # noqa: PLW1510 — returncode is the assertion
        [sys.executable, str(REPO / "hooks" / "stop-validation.py")],
        input=json.dumps(payload), capture_output=True, text=True, cwd=root,
        env={"PATH": os.environ["PATH"], "HOME": str(root),
             "CLAUDE_PROJECT_DIR": str(root)})


def test_the_first_stop_attempt_blocks(tmp_path: Path) -> None:
    root = _repo_with_unrecorded_change(tmp_path)
    assert _stop(root, active=False).returncode == 2


def test_the_second_attempt_states_the_same_gate_and_lets_the_session_end(
        tmp_path: Path) -> None:
    """Not a softer verdict — the same one, delivered once.

    The gate was already shown to the model and the model stopped anyway. Saying
    it again in a loop it cannot leave does not add a reader; it removes the only
    one there was.
    """
    root = _repo_with_unrecorded_change(tmp_path)
    done = _stop(root, active=True)

    assert done.returncode == 0, "the session could not be ended"
    assert "CHANGELOG" in (done.stdout + done.stderr), \
        "the gate went quiet instead of reporting what is still owed"


def test_the_second_pass_says_why_it_is_not_blocking(tmp_path: Path) -> None:
    root = _repo_with_unrecorded_change(tmp_path)
    out = _stop(root, active=True).stdout + _stop(root, active=True).stderr

    assert "stop_hook_active" in out, \
        "a gate that stopped blocking must name the reason it stopped"
