"""Removing a Squad hook from `settings.json` is a decision, not drift to repair.

`settings.json` is Claude Code's own configuration file, and the kit writes its
hooks into it — the same shape `spec-kit` uses, where an integration's events go
into the agent's native config and are removable through it. That is the ONE
configuration surface, and a kit that invents a second one (a bespoke rules file,
an environment flag) gives the same system two behaviours and two sets of gates to
reason about.

Measured 2026-09-19, and it is why somebody reaches for a flag: the surface does
not hold. A project removed `UserPromptSubmit` from `settings.json`, reinstalled,
and the hook was back. `merge_hooks` places "the kit's groups first, verbatim", so
a removal is invisible to it and the file only looks like configuration.

The kit already holds the correct pattern one function down. `.kit-permissions.json`
records what the kit SHIPPED, and a rule present in the consumer and absent from
the kit is "either something the kit retired or something the project added, and
those must never share an outcome". `.kit-hooks.json` is the same record for hooks
and was read for only one of the two directions — retiring what the kit dropped,
never respecting what the project dropped.

With no baseline nothing is respected, so a first install wires everything. That
is the same "with no record nothing is removed" the permissions merge already
states, and it is what keeps this from silencing a fresh consumer.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "mechanisms" / "distribution"))

from merge_settings import hook_baseline, merge_hooks  # noqa: E402

_LADDER = "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/userpromptsubmit-inject.py"
_GUARD = "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/boundary-check.py"


def _kit() -> dict:
    return {"hooks": {
        "UserPromptSubmit": [{"hooks": [{"type": "command", "command": _LADDER}]}],
        "PreToolUse": [{"matcher": "Write", "hooks": [{"type": "command", "command": _GUARD}]}],
    }}


def _commands(merged: dict, event: str) -> list[str]:
    return [h.get("command") for g in merged.get(event, []) for h in g.get("hooks", [])]


def test_a_first_install_wires_everything() -> None:
    """No baseline means no record of a removal, so nothing is respected as one."""
    merged, _, _, _ = merge_hooks({}, _kit(), {})
    assert _commands(merged, "UserPromptSubmit") == [_LADDER]
    assert _commands(merged, "PreToolUse") == [_GUARD]


def test_a_hook_the_project_deleted_is_not_put_back() -> None:
    """The measured defect: reinstall resurrected what the project had removed."""
    previous = hook_baseline(_kit())
    mine = {"hooks": {
        "PreToolUse": [{"matcher": "Write", "hooks": [{"type": "command", "command": _GUARD}]}],
    }}
    merged, _, _, _ = merge_hooks(mine, _kit(), previous)
    assert _commands(merged, "UserPromptSubmit") == []
    assert _commands(merged, "PreToolUse") == [_GUARD], "an untouched hook must survive"


def test_removal_is_uniform_across_every_hook() -> None:
    """A guard removed is a guard removed.

    Exempting the guards would be the two-behaviours problem again, one layer
    down: the same file would mean different things depending on which line you
    edited, and nothing on the page would say which.
    """
    previous = hook_baseline(_kit())
    merged, _, _, _ = merge_hooks({"hooks": {}}, _kit(), previous)
    assert _commands(merged, "PreToolUse") == []
    assert _commands(merged, "UserPromptSubmit") == []


def test_a_removal_is_reported_rather_than_silent() -> None:
    """An install that quietly declines to wire a gate is one nobody can audit."""
    previous = hook_baseline(_kit())
    mine = {"hooks": {"PreToolUse": [
        {"matcher": "Write", "hooks": [{"type": "command", "command": _GUARD}]}]}}
    _, _, retired, respected = merge_hooks(mine, _kit(), previous)
    assert any(_LADDER in line for line in respected), respected
    # And never confused with the other reason a kit hook disappears. "The kit
    # stopped shipping it" and "this project removed it" are different facts and
    # a reader acts differently on each.
    assert retired == [], retired


def test_a_hook_the_kit_never_shipped_before_still_arrives() -> None:
    """A NEW kit hook is not a removal — there is no record of the project dropping it.

    Without this, every hook added after a consumer's last install would be read
    as something they had deleted, and the kit would stop shipping gates to the
    consumers furthest behind.
    """
    previous = {"PreToolUse": [_GUARD]}          # the ladder did not exist last time
    mine = {"hooks": {"PreToolUse": [
        {"matcher": "Write", "hooks": [{"type": "command", "command": _GUARD}]}]}}
    merged, _, _, _ = merge_hooks(mine, _kit(), previous)
    assert _commands(merged, "UserPromptSubmit") == [_LADDER]
