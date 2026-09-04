#!/bin/bash
# fleet_supervisor_with_autonomy.sh — extend fleet_supervisor with autonomous
# decision resolution. Adds autonomy phase after land phase.

set -uo pipefail
_here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

LANES=""; KIT=""; KIT_REPO=""; PROJECT=""; INTERVAL=300; ONCE=0; APPLY="--apply"
AUTONOMY_ENABLED="${AUTONOMY_ENABLED:-true}"  # New
AUTONOMY_INTERVAL="${AUTONOMY_INTERVAL:-600}"  # Run autonomy every Nth pass
AUTONOMY_PASS=0

while [ $# -gt 0 ]; do
  case "$1" in
    --lanes)    LANES="$2"; shift 2 ;;
    --kit)      KIT="$2"; shift 2 ;;
    --kit-repo) KIT_REPO="$2"; shift 2 ;;
    --project)  PROJECT="$2"; shift 2 ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    --once)     ONCE=1; shift ;;
    --dry-run)  APPLY=""; shift ;;
    --no-autonomy) AUTONOMY_ENABLED="false"; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$LANES" ] && [ -n "$KIT" ] || {
  echo "usage: fleet_supervisor.sh --lanes a,b,c --kit /path/to/kit [--kit-repo owner/name] [--project /path] [--interval 300] [--once] [--dry-run] [--no-autonomy]" >&2
  exit 2
}

_stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# Find autonomy loop
AUTONOMY_LOOP="${_here}/autonomy/autonomy-loop.sh"
if [ ! -f "$AUTONOMY_LOOP" ] && [ "$AUTONOMY_ENABLED" = "true" ]; then
    echo "WARNING: Autonomy enabled but $AUTONOMY_LOOP not found. Disabling." >&2
    AUTONOMY_ENABLED="false"
fi

while :; do
  echo "── $(_stamp) ── route ──"
  python3 "$_here/fleet_router.py" --lanes "$LANES" --kit-path "$KIT" \
      ${KIT_REPO:+--kit-repo "$KIT_REPO"} ${PROJECT:+--project "$PROJECT"} $APPLY
  _route=$?

  echo "── $(_stamp) ── land ──"
  python3 "$_here/fleet_lander.py" --repo "$KIT" $APPLY
  _land=$?

  # NEW: Autonomy phase
  if [ "$AUTONOMY_ENABLED" = "true" ]; then
    AUTONOMY_PASS=$((AUTONOMY_PASS + 1))
    if [ $((AUTONOMY_PASS % AUTONOMY_INTERVAL)) -eq 0 ]; then
      echo "── $(_stamp) ── autonomy ──"
      if bash "$AUTONOMY_LOOP" 2>&1 | sed 's/^/  [autonomy] /'; then
        echo "── $(_stamp) ── autonomy complete ──"
      else
        echo "── $(_stamp) ── autonomy had a non-fatal error (continuing) ──"
      fi
    fi
  fi

  echo "── $(_stamp) ── pass done (route=$_route land=$_land autonomy=$AUTONOMY_ENABLED) ──"
  [ "$ONCE" -eq 1 ] && break
  sleep "$INTERVAL"
done
