"""What a hook is allowed to say back, per event.

Claude Code gives a hook two channels and they do not mean the same thing:

  exit code   0 = proceed · 2 = BLOCK, with stderr shown to Claude · anything
              else = non-blocking error, stderr shown to the user only
  stdout JSON the decision fields the exit code cannot express — a permission
              verdict with a reason, context to inject, `continue: false`

THREE THINGS THE WIRE FORMAT SEPARATES AND THE NAMES MUST NOT BLUR
------------------------------------------------------------------
`deny`/`block`   refuses THIS action. Claude carries on and may try another way.
`halt`           sets `continue: false`, which stops the whole turn. It is not a
                 louder deny — it ends the run, so a hook reaching for it should
                 mean "nothing further should happen", not "not like that".
`system_message` is shown to the PERSON. `reason` is shown to CLAUDE. A warning
                 written into `reason` is read by the model and never seen by
                 the human it was meant to warn.

The verbs differ per event because the PROTOCOL differs per event, not for
variety: `PreToolUse` decides a permission, `UserPromptSubmit` blocks a prompt,
`Stop` refuses to stop.
"""
from __future__ import annotations

import json
import sys
from typing import Any, NoReturn

#: Claude Code reads this exit code as "block, and show stderr to Claude".
BLOCK = 2
#: Any non-zero code that is not BLOCK: the user sees stderr, the action proceeds.
NON_BLOCK = 1


def _emit(payload: dict[str, Any], system_message: str | None = None,
          code: int = 0) -> NoReturn:
    if system_message:
        payload = {**payload, "systemMessage": system_message}
    print(json.dumps(payload))
    sys.exit(code)


def _stop(code: int, message: str | None, stream: Any) -> NoReturn:
    if message:
        print(message, file=stream)
    sys.exit(code)


class Output:
    """Shared exits and `halt`. Every event has these; the verdicts are per-event."""

    event: str = ""

    # ── the exit-code channel ────────────────────────────────────────────────

    def exit_success(self, message: str | None = None) -> NoReturn:
        """Proceed. On the events that read stdout, `message` becomes context."""
        _stop(0, message, sys.stdout)

    def exit_non_block(self, message: str, exit_code: int = NON_BLOCK) -> NoReturn:
        """Something went wrong and the action still proceeds. The USER sees this.

        `exit_code` may not be `BLOCK`: a caller reaching for the non-blocking
        exit and passing 2 would get the opposite of what the name promises.
        """
        if exit_code == BLOCK:
            raise ValueError("exit_non_block cannot use exit code 2 — that is a block. "
                             "Call exit_block() if blocking is what you mean")
        _stop(exit_code, message, sys.stderr)

    def exit_block(self, reason: str) -> NoReturn:
        """Refuse. CLAUDE sees `reason`, so write it for the reader who must act.

        This channel carries no `system_message`: an exit code plus stderr is all
        it has. Use the JSON verb of your event when a person needs telling too.
        """
        _stop(BLOCK, reason, sys.stderr)

    # ── the JSON channel, shared by every event ──────────────────────────────

    def halt(self, reason: str, system_message: str | None = None) -> NoReturn:
        """End the turn: `continue: false`. Not a stronger deny — a different act.

        A denied action leaves Claude free to try another route, which is usually
        what a policy wants. `halt` ends the run, so the work in flight stops
        wherever it is.
        """
        _emit({"continue": False, "stopReason": reason}, system_message)


class PreToolUseOutput(Output):
    event = "PreToolUse"

    def allow(self, reason: str | None = None, system_message: str | None = None) -> NoReturn:
        payload: dict[str, Any] = {"hookEventName": self.event, "permissionDecision": "allow"}
        if reason:
            payload["permissionDecisionReason"] = reason
        _emit({"hookSpecificOutput": payload}, system_message)

    def deny(self, reason: str, system_message: str | None = None) -> NoReturn:
        _emit({"hookSpecificOutput": {"hookEventName": self.event,
                                      "permissionDecision": "deny",
                                      "permissionDecisionReason": reason}}, system_message)

    def ask(self, reason: str | None = None, system_message: str | None = None) -> NoReturn:
        """Hand the decision to the person rather than deciding it.

        `reason` is optional because the honest answer is sometimes that the hook
        has no opinion — a pattern it did not match. Inventing a reason there
        would put words in the prompt the person reads.
        """
        payload: dict[str, Any] = {"hookEventName": self.event, "permissionDecision": "ask"}
        if reason:
            payload["permissionDecisionReason"] = reason
        _emit({"hookSpecificOutput": payload}, system_message)

    #: The exit-code spelling of `deny`, for a hook with nothing to add beyond "no".
    exit_deny = Output.exit_block


class PostToolUseOutput(Output):
    event = "PostToolUse"

    def accept(self, message: str | None = None,
               system_message: str | None = None) -> NoReturn:
        """The result is fine. Proceed."""
        if system_message:
            _emit({}, system_message)
        self.exit_success(message)

    def challenge(self, reason: str, system_message: str | None = None) -> NoReturn:
        """The tool already ran; this tells Claude the RESULT is unacceptable.

        It cannot un-run the call. What it can do is make Claude act on what came
        back instead of building on it.
        """
        _emit({"decision": "block", "reason": reason}, system_message)

    def ignore(self, system_message: str | None = None) -> NoReturn:
        """No opinion.

        On the wire this is `accept()` with nothing to say — the same exit 0. The
        separate name exists so a hook can distinguish "I looked and it is fine"
        from "this is not mine to judge", which matters when reading the hook,
        not to the runtime.
        """
        if system_message:
            _emit({}, system_message)
        sys.exit(0)

    def add_context(self, additional_context: str,
                    system_message: str | None = None) -> NoReturn:
        _emit({"hookSpecificOutput": {"hookEventName": self.event,
                                      "additionalContext": additional_context}},
              system_message)

    #: Kept as the name the earlier draft used for `challenge`.
    block = challenge
    allow = accept


class UserPromptSubmitOutput(Output):
    event = "UserPromptSubmit"

    def allow(self, additional_context: str | None = None,
              system_message: str | None = None) -> NoReturn:
        """Let the prompt through, optionally prepending context to it."""
        if additional_context is None:
            if system_message:
                _emit({}, system_message)
            sys.exit(0)
        _emit({"hookSpecificOutput": {"hookEventName": self.event,
                                      "additionalContext": additional_context}},
              system_message)

    def add_context(self, additional_context: str,
                    system_message: str | None = None) -> NoReturn:
        """`allow` with context, named for what it is doing."""
        self.allow(additional_context, system_message)

    def block(self, reason: str, system_message: str | None = None) -> NoReturn:
        _emit({"decision": "block", "reason": reason}, system_message)


class StopOutput(Output):
    event = "Stop"

    def allow(self, system_message: str | None = None) -> NoReturn:
        if system_message:
            _emit({}, system_message)
        sys.exit(0)

    def prevent(self, reason: str, system_message: str | None = None) -> NoReturn:
        """Refuse to stop, and tell Claude what is still owed.

        Guard `stop_hook_active` before calling this or the session cannot end:
        the hook fires again on the next stop attempt and answers the same way.
        """
        _emit({"decision": "block", "reason": reason}, system_message)


class SubagentStopOutput(StopOutput):
    event = "SubagentStop"


class SessionStartOutput(Output):
    event = "SessionStart"

    def add_context(self, additional_context: str,
                    system_message: str | None = None) -> NoReturn:
        _emit({"hookSpecificOutput": {"hookEventName": self.event,
                                      "additionalContext": additional_context}},
              system_message)

    def allow(self, additional_context: str | None = None,
              system_message: str | None = None) -> NoReturn:
        if additional_context is None:
            if system_message:
                _emit({}, system_message)
            sys.exit(0)
        self.add_context(additional_context, system_message)


class PreCompactOutput(Output):
    event = "PreCompact"

    def allow(self, message: str | None = None) -> NoReturn:
        self.exit_success(message)
