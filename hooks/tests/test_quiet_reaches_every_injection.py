"""Quiet mode is measured at the hooks, not at the function that decides it.

`is_quiet` returning True proves nothing about a session. What a reader notices is
the bytes, so these run the three hooks as Claude Code runs them — one JSON event
on stdin — and count what comes back.

The fourth test is the one that matters most: the guards do not read this setting
at all, and a change that silenced them would pass every test above while removing
the only thing standing between an agent and a write into the installed kit.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_HOOKS = _REPO / "hooks"


def _consumer(tmp_path: Path) -> Path:
    """A plugin install: the kit under `.claude/`, as `install.sh` writes it."""
    project = tmp_path / "consumer"
    eco = project / ".claude"
    for d in ("rules", "skills", "hooks", "mechanisms", "agents", "commands"):
        (eco / d).mkdir(parents=True, exist_ok=True)
    for name in ("parsimony-ladder", "testing", "architecture"):
        (eco / "rules" / f"{name}.md").write_text(f"# {name}\n", encoding="utf-8")
    return project


def _run(hook: str, project: Path, event: dict, *, quiet: bool) -> str:
    env = dict(os.environ)
    env.pop("SQUAD_QUIET", None)
    if quiet:
        env["SQUAD_QUIET"] = "1"
    payload = {"session_id": "t", "transcript_path": "/dev/null",
               "cwd": str(project), **event}
    proc = subprocess.run(
        [sys.executable, str(_HOOKS / hook)],
        input=json.dumps(payload), capture_output=True, text=True, env=env, cwd=project,
    )
    return proc.stdout + proc.stderr


@pytest.mark.parametrize(("hook", "event"), [
    ("userpromptsubmit-inject.py",
     {"hook_event_name": "UserPromptSubmit", "prompt": "what time is it"}),
    ("sessionstart-context.py",
     {"hook_event_name": "SessionStart", "source": "startup"}),
])
def test_an_injection_that_speaks_by_default_says_nothing_when_quiet(
        tmp_path: Path, hook: str, event: dict) -> None:
    project = _consumer(tmp_path)

    loud = _run(hook, project, event, quiet=False)
    assert "PARSIMONY" in loud or len(loud) > 200, (
        f"{hook} said nothing even when loud — this test would pass examining nothing")

    quiet = _run(hook, project, event, quiet=True)
    assert "PARSIMONY" not in quiet
    assert "additionalContext" not in quiet, quiet[:300]


def test_the_guards_do_not_read_this_setting_at_all() -> None:
    """Asserted on the source: being quiet is not being unprotected.

    A guard a config can silence is a guard that gets silenced on the day it would
    have mattered, by somebody who only wanted less text.
    """
    for guard in ("boundary-check.py", "validate-command.py"):
        text = (_HOOKS / guard).read_text(encoding="utf-8")
        assert "is_quiet" not in text and "SQUAD_QUIET" not in text, (
            f"{guard} is a guard and must not be reachable by the volume control")


def _stop_tree(tmp_path: Path) -> Path:
    """A consumer with a change that produces a WARN and a BLOCK at once."""
    project = _consumer(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=project, check=True)
    (project / "README.md").write_text("# r\n", encoding="utf-8")
    # The Rule 6 gate only runs where there IS a changelog; without one it degrades
    # to a warning and this test would be measuring the advisory half twice.
    (project / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=project, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=project, check=True)
    # Production source, no test beside it and no CHANGELOG entry: one WARN, one BLOCK.
    src = project / "src"
    src.mkdir()
    (src / "worker.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=project, check=True)
    return project


def test_quiet_drops_the_advisory_half_and_keeps_the_blocking_half(tmp_path: Path) -> None:
    """The cut is surgical: a secret or a missing changelog still stops the turn.

    Silencing a blocker would turn a volume control into a way past a gate, which
    is the one thing this setting must never become.
    """
    project = _stop_tree(tmp_path)
    event = {"hook_event_name": "Stop", "stop_hook_active": False}

    loud = _run("stop-validation.py", project, event, quiet=False)
    assert "[WARN]" in loud, "no warning even when loud — this test would prove nothing"
    assert "[BLOCK]" in loud, "no blocker even when loud — this test would prove nothing"

    quiet = _run("stop-validation.py", project, event, quiet=True)
    assert "ADVISORY WARNINGS" not in quiet
    assert "[WARN]" not in quiet
    assert "[BLOCK]" in quiet, "quiet reached the blocking half — that is a gate, not noise"
    assert "HARD-GATE VIOLATION" in quiet
