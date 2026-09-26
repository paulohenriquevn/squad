#!/usr/bin/env bash
# Watch a running workflow's agents from OUTSIDE the session that spawned them.
#
# WHY THIS EXISTS
#
# The single-instance architecture replaced three tmux lanes with subagents that
# run inside the coordinating session's process. That fixed the coordination
# defects the lanes had — but it took the observation surface with it. An
# operator typed `tmux attach -t squad1`, got `no sessions`, and the only answer
# on offer was `/workflows`, which is reachable from inside that session and
# nowhere else.
#
# The agents write JSONL transcripts to disk as they work. This reads them. It is
# the outside view: a person on any shell can see what each agent is doing,
# without the session's cooperation and without being able to disturb it.
#
# WHAT IT REFUSES TO DO
#
# It reports what the transcripts contain and does not infer past them. An agent
# whose file has not been written to in a while is reported as exactly that —
# "no output for Nm" — never as "stuck" or "done", because from the file alone
# those are the same observation.
#
# Usage:
#   workflow_watch.sh                 # the most recent workflow
#   workflow_watch.sh <run-id>        # a specific one
#   workflow_watch.sh --follow        # refresh every 10s
#   workflow_watch.sh --list          # what runs exist

set -uo pipefail

# The CLI's transcript store, which is where `wf_*` run directories live. This was
# `${CLAUDE_PROJECT_DIR:-$HOME/.claude/projects}` — two roots that are never the same
# tree, one the project and one the store. Inside a Claude Code session the variable
# IS set, which is the documented use, so every such invocation searched the project
# and exited 1 with "no workflow run found" while the runs sat in the other tree.
_root="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects"
_runs="$(find "$_root" -maxdepth 6 -type d -name 'wf_*' 2>/dev/null | sort)"

RUN=""; FOLLOW=0
while [ $# -gt 0 ]; do
  case "$1" in
    --follow|-f) FOLLOW=1; shift ;;
    --list|-l)
      echo "$_runs" | while read -r d; do
        [ -z "$d" ] && continue
        printf '%s  %s  %s agent(s)\n' \
          "$(date -r "$d" '+%Y-%m-%d %H:%M' 2>/dev/null || echo '?')" \
          "$(basename "$d")" \
          "$(find "$d" -name 'agent-*.jsonl' 2>/dev/null | wc -l)"
      done
      exit 0 ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    *) RUN="$1"; shift ;;
  esac
done

_dir=""
if [ -n "$RUN" ]; then
  _dir="$(echo "$_runs" | grep -F "$RUN" | head -1)"
else
  _dir="$(echo "$_runs" | while read -r d; do
    [ -z "$d" ] && continue
    printf '%s\t%s\n' "$(stat -c %Y "$d" 2>/dev/null || echo 0)" "$d"
  done | sort -rn | head -1 | cut -f2)"
fi

[ -n "$_dir" ] && [ -d "$_dir" ] || { echo "no workflow run found (try --list)" >&2; exit 1; }

_render() {
  echo "╭─ WORKFLOW $(basename "$_dir") ─ $(date '+%H:%M:%S')"
  echo "│"

  # The journal carries one line per completed agent. It is the only place a
  # RESULT appears; the transcripts carry the work, not the verdict.
  local journal="$_dir/journal.jsonl"
  local finished=0
  [ -f "$journal" ] && finished="$(grep -c '"type":"result"' "$journal" 2>/dev/null | tr -d "\n" || true)"
  [ -z "$finished" ] && finished=0

  local total
  total="$(find "$_dir" -name 'agent-*.jsonl' 2>/dev/null | wc -l)"
  echo "├─ $finished of $total agent(s) have returned a result"
  echo "│"

  local now
  now="$(date +%s)"
  for f in "$_dir"/agent-*.jsonl; do
    [ -f "$f" ] || continue
    local id age line label
    id="$(basename "$f" .jsonl | sed 's/^agent-//' | cut -c1-8)"
    age=$(( now - $(stat -c %Y "$f" 2>/dev/null || echo "$now") ))

    # Last tool the agent reached for — the closest thing to "what it is doing".
    line="$(grep -o '"name":"[A-Za-z_]*"' "$f" 2>/dev/null | tail -1 | cut -d'"' -f4)"
    [ -z "$line" ] && line="(no tool call yet)"

    # The label the workflow gave it, if the prompt carried one.
    # The item the agent was handed, stated once in its prompt as `ITEM: B-NNN`.
    # Matching a bare word like "verify" finds it in every prompt that mentions
    # the verify phase, which reported all eight agents under one name.
    label="$(grep -o 'ITEM: B-[0-9]\{3\}' "$f" 2>/dev/null | head -1 | sed 's/ITEM: //')"
    if [ -z "$label" ]; then
      label="$(grep -o '"label":"[^"]*"' "$f" 2>/dev/null | head -1 | cut -d'"' -f4)"
    fi
    [ -z "$label" ] && label="$id"

    printf '├─ %-18s last tool: %-14s  no output for %dm%02ds\n' \
      "$label" "$line" $(( age / 60 )) $(( age % 60 ))
  done

  echo "│"
  echo "├─ transcripts: $_dir"
  echo "│  A file that has not been written to recently may be thinking, waiting on a"
  echo "│  slow command, or finished. From the file alone those look the same — this"
  echo "│  reports the silence and does not guess which."
  echo "╰─"
}

if [ "$FOLLOW" -eq 1 ]; then
  while :; do clear; _render; sleep 10; done
else
  _render
fi
