"""Write a Claude Code hook in Python without parsing the wire format by hand.

    from squad import create_context, PreToolUseContext

    c = create_context(PreToolUseContext)
    if c.tool_name == "Bash" and "rm -rf" in c.tool_input.get("command", ""):
        c.output.deny(reason="rm -rf is blocked", system_message="⚠️ destructive")
    c.output.allow()

WHEN THE CONTEXT CANNOT BE BUILT, THE HOOK BLOCKS
-------------------------------------------------
Unreadable stdin, malformed JSON, a missing or unknown `hook_event_name`: each
exits 2, which Claude Code reads as a block, with a stderr line saying which.
This is the one decision in the library that is not negotiable per call, and it
is deliberate.

`hooks/validate-command.py` states the reason in its own header — *"F5: fail
CLOSED if jq is unavailable"* — and the kit's doctrine is the same everywhere
else: an inability to measure never becomes a passing measurement. A hook that
exits 0 because it could not parse its input is a gate that approves everything
while its log looks clean, and nothing downstream can tell that apart from a
gate that ran and found nothing.

The cost is stated rather than hidden: on an observer event (`PostToolUse`,
`SessionStart`, `PreCompact`) a parse failure is noisy and protects nothing in
particular. It is still a block, because when the payload cannot be read the
library does not know WHICH event it is holding, so it cannot choose a
per-event answer without guessing — and guessing is the failure this rule
exists to prevent.
"""
from __future__ import annotations

import json
import sys
from typing import Any, NoReturn, TypeVar

from .contexts import (
    BY_EVENT,
    HookContext,
    PostToolUseContext,
    PreCompactContext,
    PreToolUseContext,
    SessionStartContext,
    StopContext,
    SubagentStopContext,
    UserPromptSubmitContext,
)
from .outputs import BLOCK, NON_BLOCK, Output

__all__ = [
    "BLOCK", "BY_EVENT", "HookContext", "NON_BLOCK", "Output",
    "PostToolUseContext", "PreCompactContext", "PreToolUseContext",
    "SessionStartContext", "StopContext", "SubagentStopContext",
    "UserPromptSubmitContext",
    "create_context", "safe_create_context", "handle_context_error",
    "exit_block", "exit_non_block", "exit_success", "output_json",
]

C = TypeVar("C", bound=HookContext)


class ContextError(RuntimeError):
    """The payload could not be turned into a context. Always ends in a block."""


def _read_payload(stream: Any) -> dict[str, Any]:
    try:
        text = stream.read()
    except OSError as error:
        raise ContextError(f"stdin could not be read: {error}") from error
    if not text or not text.strip():
        raise ContextError("stdin was empty — a hook with no payload cannot judge anything")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise ContextError(f"stdin is not valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ContextError(f"the payload is {type(payload).__name__}, not an object")
    return payload


def build_context(payload: dict[str, Any], expected: type[C] | None = None) -> C:
    """Turn a payload into its context. Raises `ContextError`; never exits.

    Separated from `create_context` so tests can exercise the mapping without a
    process boundary — a library whose only entry point calls `sys.exit` can
    only be tested through a subprocess, and the cases worth pinning here are
    the malformed ones.
    """
    event = payload.get("hook_event_name")
    if not event:
        raise ContextError("the payload names no `hook_event_name`")
    cls = BY_EVENT.get(event)
    if cls is None:
        raise ContextError(
            f"`{event}` has no context in this library. It handles: "
            f"{', '.join(sorted(BY_EVENT))}. Add one rather than reading `raw` "
            f"in the hook, so the next hook for that event inherits it")
    if expected is not None and cls is not expected:
        raise ContextError(
            f"this hook expects {expected.__name__} but the runtime sent `{event}`. "
            f"Check the event it is registered under in hooks.json")

    known = {f for f in cls.__dataclass_fields__ if f not in ("raw", "event_name")}
    kwargs = {k: v for k, v in payload.items() if k in known}
    return cls(raw=payload, **kwargs)  # type: ignore[return-value]


def create_context(expected: type[C] | None = None, *, stream: Any = None) -> C:
    """Build the context for this invocation, or block saying why.

    Pass `expected` to get a narrowed type without `assert isinstance(...)`:
    an assert vanishes under `python -O`, and when it does fire it raises
    `AssertionError`, which exits 1 — a NON-blocking code. A security hook whose
    type check fails would therefore let the action through, which is the exact
    inversion this argument avoids.
    """
    try:
        return build_context(_read_payload(stream or sys.stdin), expected)
    except ContextError as error:
        handle_context_error(error)


def safe_create_context(expected: type[C] | None = None) -> C:
    """`create_context` under its older name. Identical, including the block.

    It was once described as exiting *gracefully*, which did not say in which
    direction — and the only graceful-looking direction, exit 0, turns a broken
    hook into one that approves everything.
    """
    return create_context(expected)


def handle_context_error(error: BaseException) -> NoReturn:
    """The single place the fail-closed decision is spelled out."""
    print(f"squad: cannot build the hook context, so nothing was checked — {error}",
          file=sys.stderr)
    sys.exit(BLOCK)


def exit_success(message: str | None = None) -> NoReturn:
    if message:
        print(message)
    sys.exit(0)


def exit_non_block(message: str, exit_code: int = NON_BLOCK) -> NoReturn:
    if exit_code == BLOCK:
        raise ValueError("exit_non_block cannot use exit code 2 — that is a block")
    print(message, file=sys.stderr)
    sys.exit(exit_code)


def exit_block(reason: str) -> NoReturn:
    print(reason, file=sys.stderr)
    sys.exit(BLOCK)


def output_json(data: dict[str, Any], exit_code: int = 0) -> NoReturn:
    print(json.dumps(data))
    sys.exit(exit_code)
