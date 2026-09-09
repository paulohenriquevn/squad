#!/usr/bin/env bash
# What the squad is doing, from any shell — the observation surface for the
# single-instance architecture.
#
# WHY THIS EXISTS
#
# `fleet_status.sh` showed three tmux sessions and `fleet_wall.sh` showed them
# side by side. Both went away with the sessions on 2026-09-04, and what replaced
# them — the coordinating session's own `/workflows` view — is reachable only from
# inside that session. An operator on the runner typed `tmux attach -t squad1`,
# got `no sessions`, and had nothing else to try.
#
# An architecture whose state can only be read by the thing running it is one
# nobody can check. This is the outside view.
#
# WHAT IT REFUSES TO DO
#
# It does not report the coordinating session's internal progress — that lives in
# the session and this script cannot see it. It says so rather than implying the
# absence means idle: "no coordinator seen from here" is a different fact from
# "nothing is running", and printing the first as the second is the defect this
# kit finds most often.
#
# Usage:
#   squad_status.sh [--project /path/to/consumer]

set -uo pipefail
_here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_kit="$(cd "$_here/../.." && pwd)"

PROJECT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

_rule() { printf '─%.0s' $(seq 1 "${1:-64}"); echo; }

echo "╭─ SQUAD ─ $(date -u '+%Y-%m-%dT%H:%M:%SZ') ─ $(hostname)"
echo "│"

# ── the kit's own tree ────────────────────────────────────────────────────────
echo "├─ kit  $_kit"
if git -C "$_kit" rev-parse --git-dir >/dev/null 2>&1; then
  _branch="$(git -C "$_kit" branch --show-current 2>/dev/null || echo '?')"
  _dirty="$(git -C "$_kit" status --porcelain 2>/dev/null | wc -l)"
  _head="$(git -C "$_kit" log --oneline -1 2>/dev/null | cut -c1-60)"
  echo "│     branch  $_branch    uncommitted: $_dirty"
  echo "│     head    $_head"
  _extra="$(git -C "$_kit" branch --format='%(refname:short)' | grep -vcE '^(workspace|develop|main)$' || true)"
  [ "$_extra" -gt 0 ] && echo "│     ${_extra} branch(es) besides workspace — the single-branch model expects 0"
else
  echo "│     not a git repository"
fi
echo "│"

# ── the consumer's queue ──────────────────────────────────────────────────────
if [ -n "$PROJECT" ] && [ -d "$PROJECT" ]; then
  echo "├─ consumer  $PROJECT"
  _sel="$PROJECT/.claude/skills/backlog-review/scripts/select_backlog_item.py"
  [ -f "$_sel" ] || _sel="$_kit/skills/backlog-review/scripts/select_backlog_item.py"
  if [ -f "$_sel" ]; then
    (cd "$PROJECT" && timeout 60 python3 "$_sel" 2>&1 | head -3 | sed 's/^/│     /')
  else
    echo "│     selector not found — cannot report the queue (this is not 'queue empty')"
  fi
  _cdirty="$(git -C "$PROJECT" status --porcelain 2>/dev/null | wc -l)"
  echo "│     uncommitted: $_cdirty"
  echo "│"
fi

# ── what is actually executing ────────────────────────────────────────────────
echo "├─ running here"
_found=0
for pat in fleet_supervisor fleet_lander fleet_router; do
  while read -r line; do
    [ -z "$line" ] && continue
    echo "│     $line" | cut -c1-92
    _found=1
  done < <(ps -eo pid,etime,cmd --no-headers 2>/dev/null | grep "$pat" | grep -v grep)
done
_claude="$(ps -eo cmd --no-headers 2>/dev/null | grep -c '[c]laude' || true)"
[ "$_claude" -gt 0 ] && { echo "│     $_claude claude process(es)"; _found=1; }
_tmux="$(tmux ls 2>/dev/null | wc -l)"
[ "$_tmux" -gt 0 ] && { echo "│     $_tmux tmux session(s)"; _found=1; }
[ "$_found" -eq 0 ] && echo "│     nothing"

echo "│"
echo "├─ the coordinator"
echo "│     A single Claude Code session coordinates and spawns subagents. Its"
echo "│     live progress is visible only from inside it (/workflows there)."
echo "│     THIS SCRIPT CANNOT SEE IT. Silence above is not proof of idleness."
echo "╰─"
