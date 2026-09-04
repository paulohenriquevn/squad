#!/usr/bin/env bash
# Hand one unit of work to one fleet lane, and refuse to if it cannot take it.
#
# WHY
#
# The lead's brief tells it to dispatch, and it had no mechanism to dispatch WITH.
# Measured on 2026-09-02: thirteen autonomous rounds, zero items dispatched, three
# lanes at a prompt for over two hours. Part of that was a legitimately blocked
# queue. The rest was that "send it to a lane" existed only as a sentence.
#
# WHAT IT REFUSES
#
# A lane that is not at a prompt does not get work. Typing into a session that is
# mid-turn interrupts whatever it holds; typing into one sitting in a first-run
# dialog answers the DIALOG. Both happened on this fleet before `session_ready.py`
# existed, and the second one killed a lead by confirming `No, exit`.
#
# Usage:
#   dispatch_to_lane.sh --lane squad1 --prompt-file /tmp/work.md
#   dispatch_to_lane.sh --lane squad2 --prompt "one-line instruction"
#
# Exit codes:
#   0  delivered
#   1  the lane is not at a prompt, or the text stayed in the composer
#   2  no such lane
#   3  the composer could not be read — delivery is UNKNOWN, not confirmed

set -uo pipefail
_here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

LANE=""; PROMPT=""; PROMPT_FILE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --lane)        LANE="$2"; shift 2 ;;
    --prompt)      PROMPT="$2"; shift 2 ;;
    --prompt-file) PROMPT_FILE="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 64 ;;
  esac
done
[ -n "$LANE" ] || { echo "usage: dispatch_to_lane.sh --lane <name> (--prompt TEXT | --prompt-file FILE)" >&2; exit 64; }
if [ -n "$PROMPT_FILE" ]; then
  [ -f "$PROMPT_FILE" ] || { echo "FATAL: no such prompt file: $PROMPT_FILE" >&2; exit 64; }
  PROMPT="$(cat "$PROMPT_FILE")"
fi
[ -n "$PROMPT" ] || { echo "FATAL: nothing to send" >&2; exit 64; }

if ! tmux has-session -t "$LANE" 2>/dev/null; then
  echo "FATAL: no lane named '$LANE'" >&2
  exit 2
fi

# The check that makes this safe to run unattended. Not advisory.
if ! python3 "$_here/session_ready.py" "$LANE" --timeout 20 --quiet; then
  echo "==> $LANE is not at a prompt — NOTHING was typed into it." >&2
  echo "    Work handed to a busy lane interrupts its turn; work handed to a lane" >&2
  echo "    in a dialog answers the dialog." >&2
  exit 1
fi

# A multi-line prompt is delivered as a FILE REFERENCE, not as keystrokes.
#
# Measured on 2026-09-02, on the first real dispatch: sending 1806 characters
# with `send-keys ... C-m` put them in the prompt as "[Pasted text #1 +18 lines]"
# and the trailing C-m was consumed by the paste rather than submitting it. All
# three lanes sat holding an unsent instruction, and `tmux capture-pane` showed
# them at a prompt — indistinguishable from idle. The work looked dispatched and
# was not.
#
# One line always submits. And the file is a better artefact anyway: a wrong
# finding can be traced to the instruction that produced it, which is the same
# reason `spawn_stages.py` writes its prompts to disk instead of inlining them.
if printf '%s' "$PROMPT" | grep -q $'\n'; then
  _drop="/tmp/squad-dispatch/$LANE-$(date +%s).md"
  mkdir -p "$(dirname "$_drop")"
  printf '%s\n' "$PROMPT" > "$_drop"
  _line="Read $_drop and do exactly what it says. It is your instruction, written to disk before this run so a wrong finding can be traced to the prompt that produced it."
else
  _drop=""
  _line="$PROMPT"
fi

# The text and the Enter go as TWO calls, and this is not stylistic. Measured on
# 2026-09-02: `send-keys "$text" C-m` left the line sitting in the composer on all
# three lanes — the trailing C-m arrives inside the same input event as the text
# and the composer treats it as part of the paste. A separate `send-keys C-m`
# submits. `start_lead_session.sh` worked only because it sent its `/loop` line
# afterwards, which submitted the brief as a side effect nobody had noticed.
tmux send-keys -t "$LANE" "$_line"
sleep 1
tmux send-keys -t "$LANE" C-m

# Verify the COMPOSER emptied — not that the text vanished from the screen.
#
# The first version of this check grepped the whole pane for the text it had just
# sent. The CLI echoes a submitted prompt into the transcript, so that predicate
# was true whether the send worked or not: it reported `NOT submitted` on every
# dispatch, including the three on 2026-09-03 whose lanes were already building
# their worktrees, and the branch below never once ran. A guard that fires
# unconditionally cannot distinguish the failure it exists for.
#
# `composer_text` reads the last caret line only. Everything above it is what the
# session has already been told.
sleep 3
_left="$(tmux capture-pane -p -t "$LANE" 2>/dev/null \
         | python3 -c 'import sys;sys.path.insert(0,"'"$_here"'");import session_ready as s;t=s.composer_text(sys.stdin.read());print("\x00UNREADABLE" if t is None else t)')"
case "$_left" in
  "")
    echo "==> dispatched to $LANE${_drop:+ (instruction at $_drop)}"
    ;;
  *UNREADABLE)
    # Absent is not empty. Saying "delivered" here would be this kit's most-found
    # defect: an inability to measure published as a measurement.
    echo "==> $LANE: could not find a composer on the pane, so whether the text" >&2
    echo "    was submitted is UNKNOWN. This is not a delivery." >&2
    exit 3
    ;;
  *)
    echo "==> $LANE still holds the text in its composer — it was NOT submitted." >&2
    echo "    Nothing to retry automatically: a second C-m could submit whatever a" >&2
    echo "    person typed there in the meantime." >&2
    exit 1
    ;;
esac
