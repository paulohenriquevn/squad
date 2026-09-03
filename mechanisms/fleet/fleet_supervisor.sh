#!/usr/bin/env bash
# Keep the fleet working: route what is startable, land what is verified, repeat.
#
# WHY
#
# Every part of the loop existed and none of them ran on their own. Measured
# 2026-09-03: three lanes idle for 10h33m with actionable work open, and five
# completed repairs sitting on branches that a person had to push and merge.
# Both ends were a human reading one output and typing the next input.
#
# WHAT IT DOES NOT DO
#
# It makes no decision either mechanism refuses to make. It cannot unblock a
# backlog item, cannot close an issue, cannot open the promotion PR to `develop`,
# and cannot land a branch whose suite it has not watched pass. If both
# mechanisms have nothing to do, the correct output is a line saying so — an
# idle fleet with a walled backlog is a fleet behaving correctly, and dressing
# that up as activity is the failure this kit keeps finding.
#
# Usage:
#   fleet_supervisor.sh --lanes squad1,squad2,squad3 --kit /home/paulo/dev/squad \
#                       --kit-repo owner/name --project /home/paulo/dev/theo
#   ... --once      run a single pass and exit
#   ... --dry-run   plan and assess without typing or pushing anything
#
# Exit codes:
#   0  the loop ended cleanly (only reachable with --once)
#   2  invocation error

set -uo pipefail
_here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

LANES=""; KIT=""; KIT_REPO=""; PROJECT=""; INTERVAL=300; ONCE=0; APPLY="--apply"
while [ $# -gt 0 ]; do
  case "$1" in
    --lanes)    LANES="$2"; shift 2 ;;
    --kit)      KIT="$2"; shift 2 ;;
    --kit-repo) KIT_REPO="$2"; shift 2 ;;
    --project)  PROJECT="$2"; shift 2 ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    --once)     ONCE=1; shift ;;
    --dry-run)  APPLY=""; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$LANES" ] && [ -n "$KIT" ] || {
  echo "usage: fleet_supervisor.sh --lanes a,b,c --kit /path/to/kit [--kit-repo owner/name] [--project /path] [--interval 300] [--once] [--dry-run]" >&2
  exit 2
}

_stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }

while :; do
  echo "── $(_stamp) ── route ──"
  # An empty APPLY must expand to no argument at all, so it is deliberately
  # unquoted.
  # shellcheck disable=SC2086
  python3 "$_here/fleet_router.py" --lanes "$LANES" --kit-path "$KIT" \
      ${KIT_REPO:+--kit-repo "$KIT_REPO"} ${PROJECT:+--project "$PROJECT"} $APPLY
  _route=$?

  echo "── $(_stamp) ── land ──"
  # The lander runs two full suites per branch. It is slow on purpose: what it is
  # protecting is the working branch every other lane cuts from.
  # shellcheck disable=SC2086
  python3 "$_here/fleet_lander.py" --repo "$KIT" $APPLY
  _land=$?

  echo "── $(_stamp) ── pass done (route=$_route land=$_land) ──"
  [ "$ONCE" -eq 1 ] && break
  sleep "$INTERVAL"
done
