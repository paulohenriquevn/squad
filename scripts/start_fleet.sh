#!/usr/bin/env bash
# Start a fleet of executing sessions and one watchdog over all of them.
#
#     scripts/start_fleet.sh ~/dev/theo 3
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
# Derived, not chosen, and from the constraint that actually binds. Memory does not:
# a session is ~240 MB against tens of gigabytes. CPU does — a session spends its time
# in bursts (test suites, builds, greps) rather than steadily, so the ceiling is how
# many bursts a machine absorbs without queueing.
#
# One third of the cores, floored at 2 and capped at 6. Two because a fleet of one is
# a lead and the whole point is more than one; six because beyond that the shared
# account rate limit binds before the machine does, and a session waiting on a rate
# limit looks exactly like a session working.
#
# This is a defensible estimate, not a measurement of steady-state load per session —
# that number does not exist yet, and when it does this formula should be replaced by
# it rather than argued with.
set -euo pipefail

PROJECT="${1:?usage: start_fleet.sh <project-dir> [size]}"
PROJECT="$(cd "$PROJECT" && pwd)"

cores="$(nproc 2>/dev/null || echo 4)"
default=$(( cores / 3 ))
[ "$default" -lt 2 ] && default=2
[ "$default" -gt 6 ] && default=6
SIZE="${2:-$default}"

MARKERS="${MARKERS:-/tmp/squad-markers}"
LOG="${LOG:-/tmp/squad-lead.jsonl}"
mkdir -p "$MARKERS"

echo "==> Fleet of $SIZE over $PROJECT (cores: $cores)"

names=()
for i in $(seq 1 "$SIZE"); do
  name="squad$i"
  names+=("$name")
  if tmux has-session -t "$name" 2>/dev/null; then
    echo "    $name already running — left alone"
    continue
  fi
  # `claude` with permissions already granted: this session answers to the watchdog,
  # not to a person, and a permission prompt is a stop nobody is there to clear.
  tmux new-session -d -s "$name" -c "$PROJECT" \
    "claude --dangerously-skip-permissions"
  # The activity marker: the pane's own output, appended. The watchdog reads its mtime
  # to tell a session that is thinking from one that has handed the turn back.
  tmux pipe-pane -t "$name" -o "cat >> $MARKERS/$name.log"
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
  "python3 $PROJECT/.claude/scripts/squad_lead.py \
     --session $joined --project $PROJECT \
     --marker-dir $MARKERS --log $LOG \
     --idle 120 --poll 20 --agents-when-stuck 2>&1 | tee -a /tmp/squad-lead-run.log"

sleep 2
echo "==> Watching: $joined"
tmux ls
