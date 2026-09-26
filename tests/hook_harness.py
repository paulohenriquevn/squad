"""Run a hook without knowing what language it is written in.

The hooks are migrating from shell to Python one at a time. A test that names
`boundary-check.py` fails the moment that hook becomes `.py` — not because the
behaviour changed, but because the filename did. So the contract is addressed by
NAME and the harness finds the implementation and its interpreter.

This also refuses to run when a name resolves to two files: during a migration
the old and new implementations can briefly coexist, and a test that silently
picked one of them would report on whichever sorted first.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: Exit codes Claude Code assigns meaning to.
ALLOW = 0
NON_BLOCK = 1
BLOCK = 2


def hook_path(name: str, root: Path | None = None) -> Path:
    hooks = (root or REPO) / "hooks"
    found = sorted(p for p in hooks.glob(f"{name}.*") if p.suffix in (".sh", ".py"))
    assert len(found) == 1, f"expected exactly one implementation of {name}, found {found}"
    return found[0]


def command_for(hook: Path) -> list[str]:
    return ["bash", str(hook)] if hook.suffix == ".sh" else [sys.executable, str(hook)]


def run_hook(name: str, payload: dict, *, cwd: Path | None = None,
             env: dict[str, str] | None = None,
             root: Path | None = None) -> subprocess.CompletedProcess:
    """Invoke the hook with `payload` on stdin.

    `hook_event_name` is required by `squad.create_context`, which blocks without
    it rather than guessing which event it is holding. Tests that omitted it were
    relying on a shell hook that never read the field.
    """
    assert "hook_event_name" in payload, (
        "the payload must name its event — the library refuses to guess, and a "
        "test omitting it measures the refusal instead of the hook")
    hook = hook_path(name, root)
    where = cwd or REPO
    base = {"PATH": os.environ["PATH"], "HOME": str(where), "CLAUDE_PROJECT_DIR": str(where)}
    return subprocess.run(
        command_for(hook), input=json.dumps(payload), capture_output=True,
        text=True, cwd=where, env={**base, **(env or {})}, check=False)


def pre_tool_use(tool_name: str, **tool_input) -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": tool_name,
            "tool_input": dict(tool_input)}


def post_tool_use(tool_name: str, **tool_input) -> dict:
    return {"hook_event_name": "PostToolUse", "tool_name": tool_name,
            "tool_input": dict(tool_input)}
