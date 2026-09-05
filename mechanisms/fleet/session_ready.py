#!/usr/bin/env python3
"""Did the session actually reach a prompt, or is it sitting in a dialog?

WHAT THIS COST BEFORE IT EXISTED
--------------------------------
`start_fleet.sh` created three tmux sessions, printed `==> Watching:
squad1,squad2,squad3`, and returned 0. `start_lead_session.sh` created one, slept
four seconds, typed a brief into it, and printed `lead is a Claude session named
'lead', looping every 10m`.

Measured on 2026-09-02, right after the CLI was upgraded to 2.1.258: all four
sessions were sitting in a first-run dialog — *"Try the new fullscreen renderer?"*
— which no version before that one asked. The three lanes stayed in it for forty
minutes while `fleet_status.sh` showed them idle and `claude agents --json`
listed them alive, so the lead would have read three free lanes and dispatched
work into sessions that could not take it. The lead itself did worse: the brief
was typed into the dialog, and its first newline confirmed the pre-selected
option, which on the trust dialog is `No, exit`. The session died and the script
said it was looping.

Neither launcher looked. That is the whole defect, and it is this kit's most
familiar one: an inability to observe published as an observation.

WHY THE CHECK IS SHAPED LIKE THIS
---------------------------------
The dialog is not a failure to detect once and be done with. `2.1.144` asked
about trust, `2.1.258` asks about a renderer, and the next version will ask about
something else. So this does not enumerate dialogs. It waits for the session to
look READY, and reports anything else as "still not ready, here is the last thing
on its screen" — which names an unknown dialog as usefully as a known one.

Exit codes:
    0 — the session reached a prompt
    1 — it is alive but still not ready (a dialog, or a slow start)
    2 — the session does not exist
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time

#: A modal is waiting for a keystroke. Every first-run dialog the CLI has shipped
#: ends with this line, and typing anything else while it is up answers IT.
_MODAL = "Enter to confirm"

#: The status line the CLI draws once the prompt is live. Matched loosely — the
#: wording around it changes between versions and the marker has not.
#:
#: It says the CLI is UP. It does not say the lane is free: the same bar is drawn
#: mid-turn, and a working lane draws the same empty composer as an idle one.
#: Measured 2026-09-03 — three lanes running tools, `ready` for all three. The
#: turn state comes from `claude agents --json` below, not from the screen.
_READY = ("shift+tab to cycle", "bypass permissions on")


class StatusUnavailable(RuntimeError):
    """The CLI could not say whether a session is mid-turn.

    Distinct from "the session is idle". Collapsing the two means typing into a
    working session on the strength of a check that never ran.
    """


def pane_pid(session: str) -> int | None:
    """The pid tmux runs in the session's first pane — which IS the `claude`
    process (verified on the fleet: `pane_pid` and the CLI's reported pid match).
    """
    done = subprocess.run(  # noqa: PLW1510
        ["tmux", "list-panes", "-t", session, "-F", "#{pane_pid}"],
        capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if done.returncode != 0:
        return None
    first = (done.stdout or "").strip().splitlines()
    try:
        return int(first[0]) if first else None
    except ValueError:
        return None


def _agent_status() -> dict[int, str]:
    """`{pid: status}` from `claude agents --json`, the only authoritative source.

    Raises rather than returning an empty map: an empty map and a failed call
    would be indistinguishable, and one of them means every lane looks idle.
    """
    import claude_stream  # local: keeps the import cost off callers that never ask
    try:
        rows = claude_stream.sessions()
    except claude_stream.Unsupported as exc:
        raise StatusUnavailable(str(exc)) from exc
    except RuntimeError as exc:
        raise StatusUnavailable(f"`claude agents --json` did not answer: {exc}") from exc
    return {int(row["pid"]): str(row.get("status", "")) for row in rows if row.get("pid")}


def screen(session: str) -> str | None:
    """What the session is showing, or None when there is no such session."""
    done = subprocess.run(  # noqa: PLW1510
        ["tmux", "capture-pane", "-p", "-t", session],
        capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return done.stdout if done.returncode == 0 else None


def state(session: str) -> tuple[str, str]:
    """`(verdict, evidence)` — `gone`, `dialog`, `ready` or `starting`.

    `dialog` and `starting` are kept apart on purpose. A dialog will never clear
    on its own and the operator must answer it; a slow start clears by waiting.
    Reporting both as "not ready" would tell the operator to wait for something
    that is waiting for them.
    """
    text = screen(session)
    if text is None:
        return "gone", f"no tmux session named {session!r}"
    lines = [ln for ln in text.splitlines() if ln.strip()]
    tail = "\n".join(lines[-4:])
    if _MODAL in text:
        # A modal outranks everything: it is waiting for a keystroke regardless of
        # what the CLI reports about turns.
        return "dialog", tail
    if not any(marker in text for marker in _READY):
        return "starting", tail

    # The prompt is live. Whether the lane is mid-turn is a question the screen
    # cannot answer, so it is asked of the CLI and never guessed.
    pid = pane_pid(session)
    if pid is None:
        return "unknown", f"no pane pid for {session!r}, so its turn state is unknown"
    try:
        statuses = _agent_status()
    except StatusUnavailable as exc:
        return "unknown", f"{exc}\n{tail}"
    status = statuses.get(pid)
    if status is None:
        return "unknown", (f"pid {pid} is not in `claude agents --json`, so whether "
                           f"{session!r} is mid-turn is unknown\n{tail}")
    if status != "idle":
        return "busy", f"the CLI reports {session!r} as {status}\n{tail}"
    return "ready", tail


#: The composer's own prompt glyph. The CLI draws it followed by U+00A0, not by an
#: ASCII space, so stripping only ASCII whitespace leaves a character behind and
#: every empty composer reads as occupied.
_CARET = "\u276f"


def composer_text(screen: str) -> str | None:
    """What is sitting UNSENT in the composer. `""` when empty, `None` when the
    pane holds no composer at all.

    `None` is not `""`. Measured 2026-09-03: `dispatch_to_lane.sh` decided
    "submitted or not" by grepping the WHOLE pane for the text it had sent, and
    the CLI echoes a submitted prompt into the transcript above the composer — so
    the predicate held whether the send worked or not, and the branch that
    reports a successful dispatch had never once run. Three lanes were told they
    had not received work while they were already building their worktrees.

    Only the last caret line counts. Everything above it is transcript: what the
    session has already been told, which is precisely the text a naive search
    finds after a send that WORKED.
    """
    caret_lines = [ln for ln in screen.splitlines() if ln.lstrip().startswith(_CARET)]
    if not caret_lines:
        # Not "the composer is empty" — "this pane has no composer I can read".
        # Collapsing the two is the defect this whole function exists to close.
        return None
    return caret_lines[-1].lstrip()[len(_CARET):].strip().strip("\u00a0").strip()


def wait(session: str, timeout: float = 45.0, interval: float = 1.5) -> tuple[str, str]:
    """Poll until ready, or until the answer stops being able to change.

    Returns as soon as the verdict is `ready`, `gone` or `dialog`: none of the
    three becomes something else by waiting, and a launcher that sleeps out its
    full timeout on a dialog delays the message the operator needs.

    `busy` is returned as-is even though it DOES clear by waiting. This function
    waits out a STARTUP, and a caller that blocks here until a lane finishes its
    turn would hold for as long as the work takes — which is a scheduling
    decision, not a launch one. Whoever wants a free lane should ask again later;
    `fleet_router` does exactly that.
    """
    deadline = time.monotonic() + timeout
    verdict, evidence = state(session)
    while verdict == "starting" and time.monotonic() < deadline:
        time.sleep(interval)
        verdict, evidence = state(session)
    return verdict, evidence


_ADVICE = {
    "dialog": ("it is waiting on a first-run dialog. Answer it once —\n"
               "  tmux attach -t {session}\n"
               "— then start it again. Anything typed before it is answered "
               "answers IT, and on the trust dialog the pre-selected option is "
               "`No, exit`."),
    "starting": ("it is alive but has not reached a prompt within the timeout. "
                 "Look at it before assuming it will:\n  tmux attach -t {session}"),
    "gone": ("it is not there. It was created and did not survive — check whether "
             "something was typed into it before it was ready."),
    # The two verdicts the #25 fix introduced. Without entries here, `main()`
    # raised KeyError on precisely the states that fix exists to report — it
    # failed closed, so nothing was ever typed into a busy lane, but the operator
    # got a traceback where the point was to get a sentence.
    "busy": ("it is mid-turn. This one clears by itself — wait and ask again "
             "rather than attaching, because anything typed now lands in the "
             "turn that is already running."),
    "unknown": ("its turn state could not be established — either its pane has "
                "no pid, or the pid is not one `claude agents --json` lists, or "
                "the CLI could not answer. Not the same as busy: busy passes, "
                "this does not until you look:\n  tmux attach -t {session}"),
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("session")
    ap.add_argument("--timeout", type=float, default=45.0)
    ap.add_argument("--quiet", action="store_true",
                    help="print nothing on success")
    args = ap.parse_args(argv)

    verdict, evidence = wait(args.session, args.timeout)
    if verdict == "ready":
        if not args.quiet:
            print(f"{args.session}: at a prompt")
        return 0

    print(f"{args.session}: NOT READY — {_ADVICE[verdict].format(session=args.session)}",
          file=sys.stderr)
    # Only where there IS a screen. A gone session has no last frame, and
    # labelling its explanation as one would be this kit's own defect in
    # miniature: presenting the absence of an observation as an observation.
    if verdict != "gone" and evidence:
        print("\n  last on its screen:", file=sys.stderr)
        for line in evidence.splitlines():
            print(f"    {line}", file=sys.stderr)
    return 2 if verdict == "gone" else 1


if __name__ == "__main__":
    sys.exit(main())
