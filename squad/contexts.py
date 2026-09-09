"""The typed view of what Claude Code put on stdin, one class per event.

Every context carries the three fields the runtime always sends —
`session_id`, `transcript_path`, `cwd` — plus whatever its own event adds.
Fields absent from the payload read as `None` rather than raising: a runtime
that adds a field must not break a hook that does not use it.

`raw` keeps the whole payload. A hook needing a field this module does not model
reads it there instead of waiting for the library to catch up.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import outputs


@dataclass
class HookContext:
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
    session_id: str | None = None
    transcript_path: str | None = None
    cwd: str | None = None

    #: Set by the subclass. Compared against the payload's `hook_event_name`,
    #: so a context built for the wrong event is a refusal, never a silent
    #: reading of fields that are not there.
    event_name: str = ""

    @property
    def output(self) -> outputs.Output:
        return outputs.Output()


@dataclass
class PreToolUseContext(HookContext):
    event_name: str = "PreToolUse"
    tool_name: str | None = None
    tool_input: dict[str, Any] = field(default_factory=dict)

    @property
    def output(self) -> outputs.PreToolUseOutput:
        return outputs.PreToolUseOutput()


@dataclass
class PostToolUseContext(HookContext):
    event_name: str = "PostToolUse"
    tool_name: str | None = None
    tool_input: dict[str, Any] = field(default_factory=dict)
    tool_response: Any = None

    @property
    def output(self) -> outputs.PostToolUseOutput:
        return outputs.PostToolUseOutput()


@dataclass
class UserPromptSubmitContext(HookContext):
    event_name: str = "UserPromptSubmit"
    prompt: str = ""

    @property
    def output(self) -> outputs.UserPromptSubmitOutput:
        return outputs.UserPromptSubmitOutput()


@dataclass
class StopContext(HookContext):
    event_name: str = "Stop"
    #: True when this stop was already interrupted by a Stop hook. A hook that
    #: calls `prevent()` without checking it makes the session unstoppable.
    stop_hook_active: bool = False

    @property
    def output(self) -> outputs.StopOutput:
        return outputs.StopOutput()


@dataclass
class SubagentStopContext(HookContext):
    """A subagent finished. Separate from `Stop` because refusing here keeps ONE
    subagent working, while refusing a `Stop` keeps the whole session going."""

    event_name: str = "SubagentStop"
    stop_hook_active: bool = False

    @property
    def output(self) -> outputs.SubagentStopOutput:
        return outputs.SubagentStopOutput()


@dataclass
class SessionStartContext(HookContext):
    event_name: str = "SessionStart"
    #: `startup` · `resume` · `clear` · `compact`
    source: str | None = None

    @property
    def output(self) -> outputs.SessionStartOutput:
        return outputs.SessionStartOutput()


@dataclass
class PreCompactContext(HookContext):
    event_name: str = "PreCompact"
    #: `manual` or `auto`
    trigger: str | None = None
    custom_instructions: str | None = None

    @property
    def output(self) -> outputs.PreCompactOutput:
        return outputs.PreCompactOutput()


#: The events this library models. Six of them have a hook in this kit today;
#: `SubagentStop` has none and is here because the API declares it. The runtime
#: has more still (`Notification`, `SessionEnd`), and `create_context` refuses an
#: unmodelled event BY NAME — the gap stays legible instead of being guessed at
#: by reading `raw` in the hook.
BY_EVENT: dict[str, type[HookContext]] = {
    "PreToolUse": PreToolUseContext,
    "PostToolUse": PostToolUseContext,
    "UserPromptSubmit": UserPromptSubmitContext,
    "Stop": StopContext,
    "SubagentStop": SubagentStopContext,
    "SessionStart": SessionStartContext,
    "PreCompact": PreCompactContext,
}
