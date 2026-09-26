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
    "exit_non_block",
]

# `exit_success`, `exit_block` and `output_json` used to be exported here as module-level
# twins of the methods on `squad/outputs.py`. Every hook exits through the per-event
# `Output` methods — `c.output.exit_block(...)` — and none of the twins had a caller or a
# test. Two spellings of "how a hook ends" is how one of them drifts, and the one nobody
# calls is the one that drifts unnoticed. `exit_non_block` stays: `squad/tests/test_squad.py`
# exercises the module-level form deliberately, to pin that it matches the method.

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

    fields = {name: f for name, f in cls.__dataclass_fields__.items()
              if name not in ("raw", "event_name")}
    kwargs = {k: v for k, v in payload.items() if k in fields}
    # The payload was filtered by field NAME and assigned straight into a TYPED dataclass,
    # so a runtime sending `tool_input` as a string produced a context whose annotation
    # said dict and whose value was not. The first hook doing `tool_input["command"]`
    # then raised TypeError — a traceback, exit 1, and for a PreToolUse hook exit 1 means
    # THE ACTION PROCEEDS. A malformed payload opened the guard instead of closing it.
    for name, value in kwargs.items():
        _refuse_wrong_type(name, value, fields[name].type, cls)
    # `cls` is a TypeVar bound to the context base; mypy cannot see that the concrete
    # subclass constructor accepts the filtered kwargs built from its own fields.
    return cls(raw=payload, **kwargs)  # type: ignore[return-value]


#: The annotations this library uses, mapped to what a JSON payload may carry for them.
#: Deliberately small: a dataclass field whose annotation is not here is not checked,
#: because guessing at a type is how a guard starts refusing valid input.
_JSON_TYPES: dict[str, tuple[type, ...]] = {
    "str": (str,),
    "bool": (bool,),
    "int": (int,),
    "dict": (dict,),
    "list": (list,),
    "dict[str, Any]": (dict,),
    "list[Any]": (list,),
    "str | None": (str, type(None)),
    "bool | None": (bool, type(None)),
    "int | None": (int, type(None)),
    "dict[str, Any] | None": (dict, type(None)),
}


def _refuse_wrong_type(name: str, value: object, annotation: object, cls: type) -> None:
    """Raise when `value` cannot be what `annotation` says, and stay quiet otherwise."""
    allowed = _JSON_TYPES.get(str(annotation).strip())
    if allowed is None:
        return
    # `bool` is a subclass of `int`; a payload sending True for an int field is a
    # different value than it looks, so the two are not interchangeable here.
    if isinstance(value, bool) and bool not in allowed:
        raise ContextError(
            f"`{name}` is a bool and {cls.__name__} declares it {annotation}")
    if not isinstance(value, allowed):
        raise ContextError(
            f"`{name}` is {type(value).__name__} and {cls.__name__} declares it "
            f"{annotation}. A hook reading it would raise rather than judge, and a hook "
            f"that raises exits 1 — which lets the action through")


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




def exit_non_block(message: str, exit_code: int = NON_BLOCK) -> NoReturn:
    if exit_code == BLOCK:
        raise ValueError("exit_non_block cannot use exit code 2 — that is a block")
    print(message, file=sys.stderr)
    sys.exit(exit_code)




