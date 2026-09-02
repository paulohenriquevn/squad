#!/usr/bin/env bash
# The lead as a Claude session, not a daemon that types into terminals.
#
#     mechanisms/fleet/start_lead_session.sh <project-dir> [interval]
#
# WHY THIS REPLACES squad_lead.py
# --------------------------------
# The daemon reached the sessions by `tmux send-keys` and read them by scraping
# panes. Three costs were measured on a real fleet, and all three are properties
# of that transport rather than of the logic on top of it:
#
#   - a race the code itself documents: "the session moved between the decision
#     and the keystrokes; not typing into a working session";
#   - an `asked` decision that consulted an agent, received a concrete next
#     action, and had nowhere to send it — `sent=None`, five times, ~$1.30 each;
#   - `busy`/`idle` reconstructed by timing how long a screen had not changed,
#     when `claude agents --json` reports it as a field.
#
# A Claude session addresses peers BY NAME over the runtime's own socket, with
# delivery confirmed and the trust model carried in the message. It can also do
# the one thing a daemon can never do: invoke the Workflow tool, which is what
# runs the pipeline — N items at different stages at once, instead of N sessions
# fanned out over whatever the queue offers.
#
# WHAT IT MUST NOT DO, AND WHY IT IS SAID IN THE PROMPT
# ------------------------------------------------------
# A daemon cannot decide a verdict because it cannot form one. A session can, so
# the refusal has to be written down rather than assumed: the lead schedules and
# reports, and every gate stays with the phase that owns it.
set -uo pipefail

_here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="${1:?usage: start_lead_session.sh <project-dir> [interval]}"
PROJECT="$(cd "$PROJECT" && pwd)"
INTERVAL="${2:-10m}"
NAME="${LEAD_NAME:-lead}"

command -v claude >/dev/null 2>&1 || { echo "claude CLI not found" >&2; exit 1; }
command -v tmux   >/dev/null 2>&1 || { echo "tmux not found" >&2; exit 1; }

read -r -d '' BRIEF <<'PROMPT'
You are the Squad lead for this repository. You SCHEDULE and REPORT. You never
decide a phase's verdict — every gate stays with the phase that owns it, and a
scheduler that could overrule one would be a way around it rather than through.

Each round, in this order:

1. `python3 .claude/skills/backlog-review/scripts/select_backlog_item.py BACKLOG.md --json`
   That is the queue. Never hand-write it: an item waiting on another reads
   `triaged` on disk, and only the selector knows the difference.

2. `claude agents --json` for who is alive: `name`, `sessionId`, `status`.
   `status` is a field here — do not infer it from a terminal.

3. If the queue names items AND lanes are free, run the pipeline:
   `/pipeline` — it materialises one agent file per stage per item, then runs
   them with no barrier between stages. Read what PARKED afterwards: a parked
   item is the gate working, not a failure to route around.

4. If a session is idle and the queue has work it can take, send it there with
   SendMessage, addressed by session name. Say which item and why that one.

5. If the queue is BACKLOG_BLOCKED, say so once, name the decision and the item
   that needs it, and stop. Do not re-ask an agent the same question — the
   answer will not have changed and each ask is paid for.

Refusals, absolute: no `--no-verify`, no `--force`, no `--allow-dirty-tree`, no
moving a threshold or a baseline to make something pass, no marking a verdict a
phase did not emit, no editing BACKLOG.md to unblock what a person must unblock.
If the only way forward is one of those, stop and report it.

Report each round in five lines or fewer: queue depth, lanes busy, what you
dispatched, what parked, what is waiting on a person.
PROMPT

if tmux has-session -t "$NAME" 2>/dev/null; then
  echo "==> '$NAME' already exists — killing it so the brief is the current one"
  tmux kill-session -t "$NAME"
fi

# `--name` is the ADDRESS: it is what `claude agents --json` reports and what
# `SendMessage` routes on. Without it the session is unreachable by peers.
tmux new-session -d -s "$NAME" -c "$PROJECT" -x 200 -y 50 \
  "claude --name '$NAME' --dangerously-skip-permissions"

sleep 4
tmux send-keys -t "$NAME" "$BRIEF" C-m
sleep 1
tmux send-keys -t "$NAME" "/loop $INTERVAL Run one lead round now, following the brief above." C-m

echo "==> lead is a Claude session named '$NAME', looping every $INTERVAL"
echo "    watch it:   tmux attach -t $NAME"
echo "    address it: SendMessage to '$NAME' from any Claude session"
echo "    the fleet:  $_here/fleet_status.sh"
