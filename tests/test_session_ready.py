"""A launcher that reports success without looking is worse than one that fails.

Measured on 2026-09-02, minutes after the CLI was upgraded to 2.1.258: four tmux
sessions were created, all four sat in a first-run dialog nobody had seen before
— "Try the new fullscreen renderer?" — and both launchers printed success. The
three lanes stayed there for forty minutes while `fleet_status.sh` reported them
idle and `claude agents --json` listed them alive, so the lead would have read
three free lanes and dispatched work into sessions that could not take it.

The lead itself was worse. Its brief was typed into the dialog after a blind
four-second sleep, and the first newline confirmed the pre-selected option, which
on the trust dialog is `No, exit`. The session died and the launcher said it was
looping every ten minutes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mechanisms" / "fleet"))

import session_ready

_RENDERER_DIALOG = """\
  Try the new fullscreen renderer?
  · Flicker-free output — fixes the flashing you see during long responses
  ❯ 1. Yes, try it
    2. Not now
  Enter to confirm · Esc to cancel
"""

_TRUST_DIALOG = """\
 Do you trust the files in this folder?
 ❯ No, exit
   Yes, I trust this folder
 Enter to confirm · Esc to cancel
"""

_AT_PROMPT = """\
─────────────────────────────────────────────── lead ─
 ❯
──────────────────────────────────────────────────────
  ⏵⏵ bypass permissions on (shift+tab to cycle) · ← for agents
"""


def _screen(monkeypatch, text: str | None) -> None:
    """Stub the pane AND the turn state.

    Before 2026-09-03 the screen alone decided `ready`, and that was the defect:
    the status bar these fixtures carry is drawn mid-turn too, so `ready` meant
    only "the CLI is up". These tests always meant "at a prompt AND free"; the
    second half was an unstated premise the code did not check. Stubbing the CLI
    as idle states it, rather than weakening what they assert.
    """
    monkeypatch.setattr(session_ready, "screen", lambda _session: text)
    monkeypatch.setattr(session_ready, "pane_pid", lambda _session: 4242)
    monkeypatch.setattr(session_ready, "_agent_status", lambda: {4242: "idle"})


def test_a_session_at_a_prompt_is_ready(monkeypatch) -> None:
    _screen(monkeypatch, _AT_PROMPT)

    verdict, _ = session_ready.state("lead")

    assert verdict == "ready"


@pytest.mark.parametrize("dialog", [_RENDERER_DIALOG, _TRUST_DIALOG],
                         ids=["renderer-2.1.258", "trust"])
def test_any_modal_is_a_dialog_including_ones_this_kit_has_never_seen(
        monkeypatch, dialog: str) -> None:
    """The check does not enumerate dialogs, and must not start.

    2.1.144 asked about trust, 2.1.258 asked about a renderer, and the next
    version will ask about something else. What they share is the line telling
    the operator a keystroke is expected — so an unknown dialog is named as
    usefully as a known one.
    """
    _screen(monkeypatch, dialog)

    verdict, evidence = session_ready.state("squad1")

    assert verdict == "dialog"
    assert "Enter to confirm" in evidence, "the operator is shown what is blocking"


def test_a_dialog_is_not_reported_as_a_slow_start(monkeypatch) -> None:
    """They need different advice: a dialog waits for the operator and never
    clears on its own, while a slow start clears by waiting. Telling someone to
    wait for something that is waiting for them is the worse of the two."""
    _screen(monkeypatch, _RENDERER_DIALOG)
    assert session_ready.state("squad1")[0] == "dialog"

    _screen(monkeypatch, "loading…")
    assert session_ready.state("squad1")[0] == "starting"


def test_a_missing_session_is_gone_not_merely_unready(monkeypatch) -> None:
    """A session that was created and did not survive is the lead's failure mode
    — the brief's first newline confirmed `No, exit`."""
    _screen(monkeypatch, None)

    verdict, evidence = session_ready.state("lead")

    assert verdict == "gone"
    assert "no tmux session" in evidence


def test_waiting_returns_the_moment_the_answer_can_no_longer_change(monkeypatch) -> None:
    """`ready`, `gone` and `dialog` are all final. Sleeping out a 45s timeout on a
    dialog delays exactly the message the operator is waiting to read."""
    calls = {"n": 0}

    def counted(_session: str) -> str:
        calls["n"] += 1
        return _RENDERER_DIALOG

    monkeypatch.setattr(session_ready, "screen", counted)
    monkeypatch.setattr(session_ready.time, "sleep",
                        lambda _s: pytest.fail("a dialog must not be waited out"))

    verdict, _ = session_ready.wait("squad1", timeout=45.0)

    assert verdict == "dialog"
    assert calls["n"] == 1


def test_a_slow_start_is_polled_until_it_becomes_ready(monkeypatch) -> None:
    screens = ["loading…", "loading…", _AT_PROMPT]
    monkeypatch.setattr(session_ready, "screen", lambda _s: screens.pop(0) if screens else _AT_PROMPT)
    monkeypatch.setattr(session_ready, "pane_pid", lambda _s: 4242)
    monkeypatch.setattr(session_ready, "_agent_status", lambda: {4242: "idle"})
    monkeypatch.setattr(session_ready.time, "sleep", lambda _s: None)

    verdict, _ = session_ready.wait("squad1", timeout=45.0, interval=0.0)

    assert verdict == "ready"
    assert not screens, "it kept looking rather than deciding on the first frame"


def test_the_exit_code_separates_absent_from_unready(monkeypatch, capsys) -> None:
    """A launcher chaining on this needs to tell "it died" from "answer the
    dialog": one is a bug to report, the other is an action to take."""
    _screen(monkeypatch, None)
    assert session_ready.main(["lead"]) == 2

    _screen(monkeypatch, _RENDERER_DIALOG)
    assert session_ready.main(["squad1"]) == 1

    _screen(monkeypatch, _AT_PROMPT)
    assert session_ready.main(["lead"]) == 0

    assert "tmux attach -t squad1" in capsys.readouterr().err, \
        "and it says how to clear it, naming the session"


def test_a_gone_session_is_not_given_a_last_screen_it_never_had(monkeypatch, capsys) -> None:
    """Printing "last on its screen" above an explanation would be this kit's own
    defect in miniature: an absence presented as an observation."""
    _screen(monkeypatch, None)

    session_ready.main(["lead"])

    err = capsys.readouterr().err
    assert "last on its screen" not in err
    assert "it is not there" in err


# ── the composer, told apart from the transcript ──────────────────────────────
# Measured 2026-09-03: `dispatch_to_lane.sh` reported `it was NOT submitted` on
# three dispatches that had all succeeded — the lanes were already building their
# worktrees. It grepped the WHOLE pane for the sent text, and Claude Code echoes a
# submitted prompt into the transcript, so the predicate was true whether the send
# worked or not. The success branch had never executed. A guard that fires
# unconditionally cannot distinguish the failure it was written for.

_RULE = "─" * 78
#: The composer draws U+276F then a NON-BREAKING space. Splitting on ASCII
#: whitespace alone leaves that character behind and every empty composer reads
#: as occupied — which is the bug, restored.
_EMPTY_COMPOSER = f"{_RULE}\n❯ \n{_RULE}\n  ⏵⏵ bypass permissions on (shift+tab to cycle)"


def test_an_empty_composer_reports_nothing_waiting() -> None:
    assert session_ready.composer_text(_EMPTY_COMPOSER) == ""


def test_text_left_in_the_composer_is_reported() -> None:
    screen = _EMPTY_COMPOSER.replace("❯ ", "❯ Read /tmp/lane-work/kit19.md")
    assert session_ready.composer_text(screen) == "Read /tmp/lane-work/kit19.md"


def test_the_same_text_in_the_transcript_is_not_the_composer() -> None:
    """The false positive itself: a submitted prompt is echoed above the rule."""
    screen = ("> Read /tmp/lane-work/kit19.md and do exactly what it says.\n"
              "● Bash(git worktree add …)\n"
              "✻ Puzzling… (18s)\n" + _EMPTY_COMPOSER)
    assert session_ready.composer_text(screen) == "", (
        "the transcript echo was read as unsent text — this is the defect")


def test_a_pane_with_no_composer_answers_unknown_not_empty() -> None:
    """Absence must not be reported as a measurement. A pane the parser cannot
    find a composer in is exactly the case this kit keeps shipping as a clean
    result."""
    assert session_ready.composer_text("some unrelated screen\nwith no prompt") is None


# ── "the CLI is up" is not "this lane can take work" ──────────────────────────
# Measured 2026-09-03: three lanes mid-turn (reading files, running bash) and
# session_ready.state() answered `ready` for all three. _READY matches the
# persistent status bar, which is drawn working or not, so the verdict answered a
# weaker question than every caller asks. dispatch_to_lane.sh promises in its own
# header to refuse a lane that is not at a prompt; it could not detect one.
#
# The pane cannot settle it — a working lane and an idle one draw the same empty
# composer. `claude agents --json` can, and is matched to a tmux session by the
# pane's pid.

_LIVE_PANE = "some transcript\n────\n❯ \n────\n  ⏵⏵ bypass permissions on (shift+tab to cycle)"


def test_a_lane_the_cli_calls_busy_is_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session_ready, "screen", lambda _s: _LIVE_PANE)
    monkeypatch.setattr(session_ready, "pane_pid", lambda _s: 4242)
    monkeypatch.setattr(session_ready, "_agent_status", lambda: {4242: "busy"})
    assert session_ready.state("squad1")[0] == "busy"


def test_a_lane_the_cli_calls_idle_is_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session_ready, "screen", lambda _s: _LIVE_PANE)
    monkeypatch.setattr(session_ready, "pane_pid", lambda _s: 4242)
    monkeypatch.setattr(session_ready, "_agent_status", lambda: {4242: "idle"})
    assert session_ready.state("squad1")[0] == "ready"


def test_a_pid_the_cli_does_not_list_is_unknown_not_ready(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The permissive answer must never be the fallback. Defaulting to `ready`
    here means typing into a working session on the strength of a check that did
    not run."""
    monkeypatch.setattr(session_ready, "screen", lambda _s: _LIVE_PANE)
    monkeypatch.setattr(session_ready, "pane_pid", lambda _s: 4242)
    monkeypatch.setattr(session_ready, "_agent_status", lambda: {99: "idle"})
    assert session_ready.state("squad1")[0] == "unknown"


def test_a_cli_that_cannot_answer_is_unknown_not_ready(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session_ready, "screen", lambda _s: _LIVE_PANE)
    monkeypatch.setattr(session_ready, "pane_pid", lambda _s: 4242)
    def unsupported() -> dict[int, str]:
        raise session_ready.StatusUnavailable("`claude agents --json` is not in this CLI")
    monkeypatch.setattr(session_ready, "_agent_status", unsupported)
    verdict, evidence = session_ready.state("squad1")
    assert verdict == "unknown"
    assert "not in this CLI" in evidence


def test_a_dialog_still_outranks_the_cli_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """A modal is waiting for a keystroke whatever the CLI reports about turns."""
    monkeypatch.setattr(session_ready, "screen",
                        lambda _s: "Try the new renderer?\nEnter to confirm")
    monkeypatch.setattr(session_ready, "pane_pid", lambda _s: 4242)
    monkeypatch.setattr(session_ready, "_agent_status", lambda: {4242: "idle"})
    assert session_ready.state("squad1")[0] == "dialog"
