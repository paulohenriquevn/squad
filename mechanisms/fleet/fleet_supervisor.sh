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
#   fleet_supervisor.sh --lanes squad1,squad2,squad3 --kit /path/to/kit \
#                       --kit-repo owner/name --project /path/to/consumer
#   ... --once      run a single pass and exit
#   ... --dry-run   plan and assess without typing or pushing anything
#
# Exit codes:
#   0  the loop ended cleanly (only reachable with --once)
#   2  invocation error

set -uo pipefail
_here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

LANES=""; KIT=""; KIT_REPO=""; PROJECT=""; ONCE=0; APPLY="--apply"
#: A lane may not sit idle longer than this. Route is seconds of work, so
#: asking often costs almost nothing and idleness costs the whole point.
ROUTE_INTERVAL=${ROUTE_INTERVAL:-120}
#: Land runs two suites per branch. Asking more often than it can finish
#: just queues a second copy behind the first.
LAND_INTERVAL=${LAND_INTERVAL:-600}
while [ $# -gt 0 ]; do
  case "$1" in
    --lanes)    LANES="$2"; shift 2 ;;
    --kit)      KIT="$2"; shift 2 ;;
    --kit-repo) KIT_REPO="$2"; shift 2 ;;
    --project)  PROJECT="$2"; shift 2 ;;
    --interval) ROUTE_INTERVAL="$2"; shift 2 ;;
    --route-interval) ROUTE_INTERVAL="$2"; shift 2 ;;
    --land-interval) LAND_INTERVAL="$2"; shift 2 ;;
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

# Two jobs, two clocks. They were one loop until 2026-09-04, and the measurement
# that ended that arrangement: routes landed 51, 54 and 53 minutes apart against
# a configured interval of 10, because land runs two full suites per branch and
# route waited for it. A lane finishing at 14:35 sat idle until 15:22.
# `fleet_idle` put the window at 94% idle, 1528 minutes against 92 productive.
#
# Nothing was broken. Route is cheap and decides whether a free lane gets work,
# so it must be frequent. Land is expensive and protects the branch every lane
# cuts from, so it must be thorough. Letting the second set the first's period
# is what turned a 10-minute interval into a 50-minute one.
_route_loop() {
  while :; do
    echo "── $(_stamp) ── route ──"
    # shellcheck disable=SC2086
    python3 "$_here/fleet_router.py" --lanes "$LANES" --kit-path "$KIT" \
        ${KIT_REPO:+--kit-repo "$KIT_REPO"} ${PROJECT:+--project "$PROJECT"} $APPLY
    echo "── $(_stamp) ── route done (next in ${ROUTE_INTERVAL}s) ──"
    [ "$ONCE" -eq 1 ] && break
    sleep "$ROUTE_INTERVAL"
  done
}

_land_loop() {
  while :; do
    echo "── $(_stamp) ── land ──"
    # shellcheck disable=SC2086
    python3 "$_here/fleet_lander.py" --repo "$KIT" $APPLY
    echo "── $(_stamp) ── land done (next in ${LAND_INTERVAL}s) ──"
    [ "$ONCE" -eq 1 ] && break
    sleep "$LAND_INTERVAL"
  done
}

_route_loop &
_route_pid=$!
_land_loop &
_land_pid=$!

# Both, not either. A supervisor that keeps printing because one loop survived
# reads as working while half of it is dead — this kit's most-found defect
# wearing a new hat.
trap 'kill "$_route_pid" "$_land_pid" 2>/dev/null' EXIT INT TERM
wait "$_route_pid" "$_land_pid"
