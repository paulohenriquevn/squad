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
_READY = ("shift+tab to cycle", "bypass permissions on")


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
        return "dialog", tail
    if any(marker in text for marker in _READY):
        return "ready", tail
    return "starting", tail


def wait(session: str, timeout: float = 45.0, interval: float = 1.5) -> tuple[str, str]:
    """Poll until ready, or until the answer stops being able to change.

    Returns as soon as the verdict is `ready`, `gone` or `dialog`: none of the
    three becomes something else by waiting, and a launcher that sleeps out its
    full timeout on a dialog delays the message the operator needs.
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
