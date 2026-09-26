"""The library hooks are written against, with the fail-closed rule pinned.

Most of what is checked here is the refusal path, because that is where a hook
library can hurt: a context that cannot be built and exits 0 turns a gate into
a rubber stamp, and the transcript of that failure is indistinguishable from a
gate that ran and found nothing.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from squad import (
    BLOCK,
    ContextError,
    PostToolUseContext,
    PreCompactContext,
    PreToolUseContext,
    SessionStartContext,
    StopContext,
    SubagentStopContext,
    UserPromptSubmitContext,
    build_context,
    create_context,
    exit_non_block,
    safe_create_context,
)

_BASE = {"session_id": "s-1", "transcript_path": "/tmp/t.jsonl", "cwd": "/repo"}


def _stdin(payload) -> io.StringIO:
    return io.StringIO(payload if isinstance(payload, str) else json.dumps(payload))


# ── every event this kit receives maps to its context ─────────────────────────


@pytest.mark.parametrize(("event", "cls", "extra", "check"), [
    ("PreToolUse", PreToolUseContext, {"tool_name": "Bash", "tool_input": {"command": "ls"}},
     lambda c: c.tool_name == "Bash" and c.tool_input["command"] == "ls"),
    ("PostToolUse", PostToolUseContext, {"tool_name": "Write", "tool_response": {"ok": True}},
     lambda c: c.tool_response == {"ok": True}),
    ("UserPromptSubmit", UserPromptSubmitContext, {"prompt": "hello"},
     lambda c: c.prompt == "hello"),
    ("Stop", StopContext, {"stop_hook_active": True}, lambda c: c.stop_hook_active is True),
    ("SessionStart", SessionStartContext, {"source": "resume"}, lambda c: c.source == "resume"),
    ("PreCompact", PreCompactContext, {"trigger": "manual", "custom_instructions": "keep X"},
     lambda c: c.trigger == "manual" and c.custom_instructions == "keep X"),
])
def test_each_event_builds_its_own_context(event, cls, extra, check) -> None:
    c = build_context({**_BASE, "hook_event_name": event, **extra})

    assert isinstance(c, cls)
    assert check(c), f"{event} lost a field"
    assert c.session_id == "s-1" and c.cwd == "/repo"


def test_an_unmodelled_field_is_kept_in_raw_and_does_not_raise() -> None:
    """A runtime that adds a field must not break a hook that ignores it."""
    c = build_context({**_BASE, "hook_event_name": "Stop", "something_new": 42})

    assert c.raw["something_new"] == 42
    assert not hasattr(c, "something_new")


# ── the fail-closed rule ──────────────────────────────────────────────────────


@pytest.mark.parametrize(("payload", "fragment"), [
    ("", "empty"),
    ("   \n", "empty"),
    ("{not json", "not valid JSON"),
    ("[1, 2]", "not an object"),
    ({"tool_name": "Bash"}, "names no `hook_event_name`"),
    ({"hook_event_name": "Notification"}, "has no context in this library"),
    ({"hook_event_name": ""}, "names no `hook_event_name`"),
])
def test_a_payload_that_cannot_be_read_blocks(payload, fragment, capsys) -> None:
    """Exit 2, every time. Exit 0 here would be a gate approving what it never saw."""
    with pytest.raises(SystemExit) as exc:
        create_context(stream=_stdin(payload))

    assert exc.value.code == BLOCK, "a context that could not be built must never proceed"
    err = capsys.readouterr().err
    assert "nothing was checked" in err, "the reason must say that no judgement happened"
    assert fragment in err


@pytest.mark.parametrize(("extra", "field"), [
    ({"tool_name": "Bash", "tool_input": "a string, not a dict"}, "tool_input"),
    ({"tool_name": 17, "tool_input": {"command": "ls"}}, "tool_name"),
])
def test_a_field_of_the_wrong_type_blocks(extra, field, capsys) -> None:
    """`build_context` filtered the payload by field NAME and assigned straight in.

    Every payload in this file is well-typed, so nothing here ever asked what happens
    when the runtime sends `tool_input` as a string. Measured: it is accepted, and the
    first hook doing `context.tool_input["command"]` raises TypeError — a traceback, exit
    1, and for a PreToolUse hook exit 1 means THE ACTION PROCEEDS. A malformed payload
    would have opened the guard rather than closing it.
    """
    payload = {**_BASE, "hook_event_name": "PreToolUse", **extra}

    with pytest.raises(SystemExit) as exc:
        create_context(PreToolUseContext, stream=_stdin(payload))

    assert exc.value.code == BLOCK, "a wrongly-typed field must never proceed"
    err = capsys.readouterr().err
    assert field in err, f"the reason does not name the field: {err!r}"
    assert "nothing was checked" in err


def test_the_wrong_event_for_this_hook_blocks(capsys) -> None:
    """Registering a hook under the wrong event is a wiring bug, not a pass."""
    with pytest.raises(SystemExit) as exc:
        create_context(PreToolUseContext, stream=_stdin({**_BASE, "hook_event_name": "Stop"}))

    assert exc.value.code == BLOCK
    assert "hooks.json" in capsys.readouterr().err, "the message must name where to look"


def test_safe_create_context_blocks_exactly_like_create_context(capsys) -> None:
    """It was once described as exiting *gracefully*, which did not say which way."""
    with pytest.raises(SystemExit) as exc:
        safe_create_context()

    assert exc.value.code == BLOCK
    _ = capsys.readouterr()


def test_the_unknown_event_message_lists_what_is_handled() -> None:
    with pytest.raises(ContextError) as exc:
        build_context({"hook_event_name": "SessionEnd"})

    for handled in ("PreToolUse", "Stop", "SessionStart"):
        assert handled in str(exc.value), "the reader must learn what IS available"


# ── the outputs ───────────────────────────────────────────────────────────────


def test_deny_emits_a_permission_decision_and_exits_zero(capsys) -> None:
    """`deny` speaks through JSON, so the exit code stays 0 — the decision is
    in the payload, and exiting 2 as well would state it twice, differently."""
    c = build_context({**_BASE, "hook_event_name": "PreToolUse"})

    with pytest.raises(SystemExit) as exc:
        c.output.deny(reason="no", system_message="⚠️")

    assert exc.value.code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert out["hookSpecificOutput"]["permissionDecisionReason"] == "no"
    assert out["systemMessage"] == "⚠️"


def test_exit_deny_is_the_exit_code_spelling(capsys) -> None:
    c = build_context({**_BASE, "hook_event_name": "PreToolUse"})

    with pytest.raises(SystemExit) as exc:
        c.output.exit_deny("protected")

    assert exc.value.code == BLOCK
    assert "protected" in capsys.readouterr().err


def test_additional_context_travels_on_the_events_that_accept_it(capsys) -> None:
    c = build_context({**_BASE, "hook_event_name": "SessionStart", "source": "startup"})

    with pytest.raises(SystemExit) as exc:
        c.output.allow(additional_context="loaded")

    assert exc.value.code == 0
    assert json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"] == "loaded"


def test_allow_with_no_context_writes_nothing(capsys) -> None:
    """An empty envelope is not the same as no envelope on these events."""
    c = build_context({**_BASE, "hook_event_name": "UserPromptSubmit", "prompt": "x"})

    with pytest.raises(SystemExit) as exc:
        c.output.allow()

    assert exc.value.code == 0
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("call", ["method", "function"])
def test_the_non_blocking_exit_refuses_to_be_a_block(call) -> None:
    """Passing 2 to the non-blocking exit would do the opposite of its name."""
    c = build_context({**_BASE, "hook_event_name": "PostToolUse"})
    fn = c.output.exit_non_block if call == "method" else exit_non_block

    with pytest.raises(ValueError, match="that is a block"):
        fn("oops", exit_code=BLOCK)


def test_prevent_carries_the_reason_claude_must_act_on(capsys) -> None:
    c = build_context({**_BASE, "hook_event_name": "Stop", "stop_hook_active": False})

    with pytest.raises(SystemExit) as exc:
        c.output.prevent(reason="tests still failing")

    assert exc.value.code == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"decision": "block", "reason": "tests still failing"}


# ── system_message: the channel the PERSON reads ──────────────────────────────


def _out(event: str):
    return build_context({**_BASE, "hook_event_name": event}).output


#: Every (event, verb) the API declares as carrying `system_message`.
_CARRIERS = [
    ("PreToolUse", "allow", ()), ("PreToolUse", "deny", ("no",)),
    ("PreToolUse", "ask", ()), ("PreToolUse", "halt", ("done",)),
    ("PostToolUse", "accept", ()), ("PostToolUse", "challenge", ("bad",)),
    ("PostToolUse", "ignore", ()), ("PostToolUse", "add_context", ("ctx",)),
    ("PostToolUse", "halt", ("done",)),
    ("Stop", "halt", ("done",)), ("Stop", "prevent", ("more",)), ("Stop", "allow", ()),
    ("SubagentStop", "halt", ("done",)), ("SubagentStop", "prevent", ("more",)),
    ("SubagentStop", "allow", ()),
    ("UserPromptSubmit", "allow", ()), ("UserPromptSubmit", "block", ("no",)),
    ("UserPromptSubmit", "add_context", ("ctx",)), ("UserPromptSubmit", "halt", ("done",)),
    ("SessionStart", "add_context", ("ctx",)),
]


@pytest.mark.parametrize(("event", "verb", "args"), _CARRIERS,
                         ids=[f"{e}.{v}" for e, v, _ in _CARRIERS])
def test_every_declared_verb_carries_system_message(event, verb, args, capsys) -> None:
    """A warning written into `reason` is read by Claude and never by the person
    it was for. The table of which verbs carry it is the contract; this walks it.
    """
    with pytest.raises(SystemExit) as exc:
        getattr(_out(event), verb)(*args, system_message="⚠️ for the human")

    assert exc.value.code == 0, f"{event}.{verb} must not change the exit code"
    emitted = json.loads(capsys.readouterr().out)
    assert emitted["systemMessage"] == "⚠️ for the human", f"{event}.{verb} dropped it"


@pytest.mark.parametrize(("event", "verb", "args"), _CARRIERS,
                         ids=[f"{e}.{v}" for e, v, _ in _CARRIERS])
def test_omitting_system_message_emits_no_such_key(event, verb, args, capsys) -> None:
    """An empty `systemMessage` is a warning with no text — worse than none."""
    with pytest.raises(SystemExit):
        getattr(_out(event), verb)(*args)

    out = capsys.readouterr().out
    if out.strip():
        assert "systemMessage" not in json.loads(out)


# ── halt is not a louder deny ─────────────────────────────────────────────────


def test_halt_ends_the_turn_rather_than_the_action(capsys) -> None:
    """`deny` refuses one action and Claude may try another route. `halt` sets
    `continue: false`, which stops the run wherever it is. Two different acts."""
    with pytest.raises(SystemExit) as exc:
        _out("PreToolUse").halt("policy exhausted")

    assert exc.value.code == 0
    emitted = json.loads(capsys.readouterr().out)
    assert emitted["continue"] is False
    assert emitted["stopReason"] == "policy exhausted"
    assert "permissionDecision" not in emitted, "halt is not a permission verdict"


def test_deny_does_not_end_the_turn(capsys) -> None:
    with pytest.raises(SystemExit):
        _out("PreToolUse").deny("not this way")

    assert "continue" not in json.loads(capsys.readouterr().out)


# ── the PostToolUse verbs ─────────────────────────────────────────────────────


def test_challenge_tells_claude_the_result_is_unacceptable(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        _out("PostToolUse").challenge("the write left the file unparseable")

    assert exc.value.code == 0
    assert json.loads(capsys.readouterr().out)["decision"] == "block"


def test_accept_and_ignore_are_the_same_on_the_wire(capsys) -> None:
    """DOCUMENTED, not a defect: the runtime cannot tell them apart, and the
    distinction is for whoever reads the hook. Pinned so the day one of them
    grows a different payload, it is a deliberate act."""
    codes = []
    for verb in ("accept", "ignore"):
        with pytest.raises(SystemExit) as exc:
            getattr(_out("PostToolUse"), verb)()
        codes.append(exc.value.code)
        assert capsys.readouterr().out == ""
    assert codes == [0, 0]


def test_subagent_stop_answers_like_stop_under_its_own_event_name() -> None:
    c = build_context({**_BASE, "hook_event_name": "SubagentStop", "stop_hook_active": True})

    assert isinstance(c, SubagentStopContext)
    assert c.stop_hook_active is True
    assert c.output.event == "SubagentStop"


def test_ask_with_no_reason_states_none(capsys) -> None:
    """A hook that matched no pattern has no reason. Inventing one puts words in
    the prompt the person reads."""
    with pytest.raises(SystemExit):
        _out("PreToolUse").ask()

    specific = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert specific["permissionDecision"] == "ask"
    assert "permissionDecisionReason" not in specific
