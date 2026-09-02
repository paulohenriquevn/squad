#!/usr/bin/env bash
# One tmux session showing every fleet session at once, side by side.
#
#     mechanisms/fleet/fleet_wall.sh          build the wall and attach to it
#     mechanisms/fleet/fleet_wall.sh -d       build it, do not attach
#     mechanisms/fleet/fleet_wall.sh -w       writable panes (see the warning below)
#     mechanisms/fleet/fleet_wall.sh -n board name it something else
#     FLEET_PATTERN='^(squad|worker)[0-9]+$' … which sessions count as fleet
#
# Each pane attaches to a real session, so what you see is that session live —
# not a copy, not a poll. `fleet_status.sh` reads panes and prints a report; this
# puts the panes themselves on one screen.
#
# READ-ONLY BY DEFAULT, AND THAT IS THE POINT
# -------------------------------------------
# `tmux attach -r` gives a view that cannot type. A fleet session is being driven
# by the watchdog, and a keystroke that lands in it while an agent holds the turn
# does not "help" — it answers a question the agent was asked, from someone the
# agent will treat as the operator. Watching must not be able to do that by
# accident. `-w` exists for when you mean to intervene, and then the pane is the
# session: what you type goes to the agent.
#
# The wall is disposable. Killing it never touches the sessions it shows.
set -uo pipefail

_here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAME="wall"
ATTACH=1
MODE="-r"

while [ $# -gt 0 ]; do
  case "$1" in
    -d|--detached)   ATTACH=0; shift ;;
    -w|--writable)   MODE=""; shift ;;
    -n|--name)       NAME="${2:?-n needs a name}"; shift 2 ;;
    -h|--help)       sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)               echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
  esac
done

if ! tmux list-sessions >/dev/null 2>&1; then
  echo "no tmux server running — there is no fleet to show." >&2
  echo "start one: AGENT_BUDGET_USD=15 bash $_here/start_fleet.sh <project> 3" >&2
  exit 1
fi

# Only the fleet's executing sessions. `start_fleet.sh` names them `squad1..N`, so
# that is the pattern — and it must be a pattern rather than "everything running",
# because a wall built from every tmux session shows whatever else the machine
# happens to be doing. Measured while testing this: a throwaway session created
# two commands earlier appeared as a fleet member.
#
# `lead` falls outside the pattern, and that is deliberate rather than incidental:
# its pane is the watchdog's own jsonl, and a grid cell of raw log is a cell nobody
# reads. The status pane below carries the same information in a usable form.
PATTERN="${FLEET_PATTERN:-^squad[0-9]+$}"
mapfile -t SESSIONS < <(tmux list-sessions -F '#{session_name}' 2>/dev/null \
                        | grep -vx "$NAME" | grep -E "$PATTERN" | sort)

if [ "${#SESSIONS[@]}" -eq 0 ]; then
  echo "tmux is running, but no session matches the fleet pattern ($PATTERN)." >&2
  echo "running now: $(tmux list-sessions -F '#{session_name}' 2>/dev/null | tr '\n' ' ')" >&2
  echo "set FLEET_PATTERN to widen it, or start a fleet:" >&2
  echo "  AGENT_BUDGET_USD=15 bash $_here/start_fleet.sh <project> 3" >&2
  exit 1
fi

# Rebuilt from scratch: a wall left over from a previous fleet shows panes whose
# sessions are gone, and a dead pane looks exactly like an idle one.
tmux kill-session -t "$NAME" 2>/dev/null

first="${SESSIONS[0]}"
tmux new-session -d -s "$NAME" "TMUX= tmux attach $MODE -t '$first'"
for s in "${SESSIONS[@]:1}"; do
  tmux split-window -t "$NAME" "TMUX= tmux attach $MODE -t '$s'"
  tmux select-layout -t "$NAME" tiled >/dev/null
done

# One cell is the report rather than a session: it says what the lead just decided
# and what the selector would pick, which is the half of the picture no pane shows.
tmux split-window -t "$NAME" "watch -t -n 10 -c '$_here/fleet_status.sh' 2>/dev/null \
                              || while true; do clear; '$_here/fleet_status.sh'; sleep 10; done"
tmux select-layout -t "$NAME" tiled >/dev/null

# The wall's own bar names what is on screen; each inner session draws its own
# below its pane, so the two together say which pane is which.
tmux set-option -t "$NAME" status-left "#[bold] WALL #[default] " >/dev/null 2>&1
tmux set-option -t "$NAME" status-right \
  " $([ -n "$MODE" ] && echo 'read-only' || echo 'WRITABLE') · ${#SESSIONS[@]} sessions " \
  >/dev/null 2>&1

echo "==> '$NAME' shows ${#SESSIONS[@]} session(s) + a status pane: ${SESSIONS[*]}"
echo "    $([ -n "$MODE" ] && echo 'read-only — panes cannot be typed into' \
                           || echo 'WRITABLE — what you type reaches the agent')"
echo "    detach with ctrl-b d · kill the wall with: tmux kill-session -t $NAME"

if [ "$ATTACH" = "1" ]; then
  if [ -n "${TMUX:-}" ]; then
    echo "    (already inside tmux — attach from outside with: tmux attach -t $NAME)"
  else
    exec tmux attach -t "$NAME"
  fi
fi
