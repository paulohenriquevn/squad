#!/usr/bin/env bash
# Start a fleet of executing sessions and one watchdog over all of them.
#
#     mechanisms/fleet/start_fleet.sh ~/dev/theo 3
#
# WHY A FLEET
# -----------
# One session works one item at a time — that is what a session is. Every attempt to
# get parallelism out of a single session produced the opposite: items started minutes
# apart, none of them finishing, and the session ending up on work none of them had
# asked for. Concurrency lives in the sessions or nowhere.
#
# SIZE
# ----
# Derived from the constraint that binds, and the constraint was measured rather than
# assumed. Memory does not bind: three sessions held 1.3 GB with 15 GB free. CPU does.
#
# Measured on an 8-core machine running the board and the watchdog alongside:
#
#   1 session   load 4.85
#   3 sessions  load 7.3 – 8.2      (saturated: 8 runnable on 8 cores)
#
# So the fixed cost of the surrounding processes is roughly 3.4, and each session adds
# about 1.4 — a session spends its time in bursts, test suites and builds and greps,
# not steadily, and a load average counts a burst the same as steady work.
#
#   sessions = (cores - 2) / 2
#
# Two cores reserved for everything that is not a session, and two cores per session
# from the 1.4 measured plus headroom, because a machine at exactly 1.0 per core has
# no room for the burst that arrives next. On the machine above this gives 3, which is
# where the measurement puts the ceiling.
#
# Floored at 2, because a fleet of one is a lead. Capped at 6, because past that the
# shared account rate limit binds before the machine does — and a session waiting on a
# rate limit looks exactly like a session working, which makes the wrong number hard
# to notice.
#
# Replace this formula when a better measurement exists. Do not argue with it.
set -euo pipefail

PROJECT="${1:?usage: start_fleet.sh <project-dir> [size]}"
PROJECT="$(cd "$PROJECT" && pwd)"

cores="$(nproc 2>/dev/null || echo 4)"
default=$(( (cores - 2) / 2 ))
[ "$default" -lt 2 ] && default=2
[ "$default" -gt 6 ] && default=6
SIZE="${2:-$default}"

MARKERS="${MARKERS:-/tmp/squad-markers}"
LOG="${LOG:-/tmp/squad-lead.jsonl}"
# The per-consultation ceiling the lead passes to `--max-budget-usd`. The default
# lives in `squad_lead.py` and its comment says 6.00 was measured "with room for a
# larger project" — a real one exceeded it on 2026-08-31 and the lead exited 1,
# stopping the whole fleet over a ceiling, not over the work. The knob is here
# because raising it must not mean editing the script that carries it.
AGENT_BUDGET_USD="${AGENT_BUDGET_USD:-}"
mkdir -p "$MARKERS"

echo "==> Fleet of $SIZE over $PROJECT (cores: $cores)"

names=()
for i in $(seq 1 "$SIZE"); do
  name="squad$i"
  names+=("$name")
  if tmux has-session -t "$name" 2>/dev/null; then
    # Left alone, but NOT left unwatched. A preserved session keeps whatever pipe it
    # had — a different file, or none — and the watchdog reads the marker by name. A
    # preserved session with its pipe pointing elsewhere has no marker at all, and the
    # fleet's lead cannot act on it.
    #
    # Closed first, then opened WITHOUT `-o`: that flag only opens a pipe when none
    # exists, so against a live pipe it toggles the pipe off instead of re-pointing it.
    # Measured — the marker stayed missing and the session went from mis-piped to
    # un-piped.
    tmux pipe-pane -t "$name" 2>/dev/null || true
    tmux pipe-pane -t "$name" "cat >> $MARKERS/$name.log"
    echo "    $name already running — left alone, marker re-pointed"
    continue
  fi
  # `claude` with permissions already granted: this session answers to the watchdog,
  # not to a person, and a permission prompt is a stop nobody is there to clear.
  tmux new-session -d -s "$name" -c "$PROJECT" \
    "claude --dangerously-skip-permissions"
  # The activity marker: the pane's own output, appended. The watchdog reads its mtime
  # to tell a session that is thinking from one that has handed the turn back.
  tmux pipe-pane -t "$name" "cat >> $MARKERS/$name.log"
  echo "    $name started"
done

sleep 3

# One watchdog over all of them. Its `--session` list is what makes it a fleet: the
# leads share a claim so no two sessions are handed the same item.
if tmux has-session -t lead 2>/dev/null; then
  tmux kill-session -t lead
fi
joined="$(IFS=,; echo "${names[*]}")"
tmux new-session -d -s lead -c "$PROJECT" \
  "python3 $PROJECT/.claude/mechanisms/fleet/squad_lead.py \
     --session $joined --project $PROJECT \
     --marker-dir $MARKERS --log $LOG \
     --idle 120 --poll 20 --agents-when-stuck \
     ${AGENT_BUDGET_USD:+--agent-budget-usd $AGENT_BUDGET_USD} \
     2>&1 | tee -a /tmp/squad-lead-run.log"

sleep 2
echo "==> Watching: $joined"
tmux ls
