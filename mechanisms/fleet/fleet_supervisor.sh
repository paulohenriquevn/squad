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
    # The ${VAR:+--flag "$VAR"} forms must word-split to vanish when unset.
    # shellcheck disable=SC2086
    python3 "$_here/fleet_router.py" --lanes "$LANES" --kit-path "$KIT" \
        ${KIT_REPO:+--kit-repo "$KIT_REPO"} ${PROJECT:+--project "$PROJECT"} $APPLY
    _rc=$?
    _say_step_result route "$_rc"
    echo "── $(_stamp) ── route done (next in ${ROUTE_INTERVAL}s) ──"
    [ "$ONCE" -eq 1 ] && break
    sleep "$ROUTE_INTERVAL"
  done
}

_say_step_result() {
  # Every step's exit code, said out loud. None of the three was read: a supervisor
  # that cannot tell a finished step from a failed one reports the same thing either
  # way, and this kit's most-found defect is an inability to work published as work.
  #
  # NOT fatal. The loop repeats every interval and one failed pass is a pass to retry,
  # not a reason to stop supervising — so the code is reported and the loop continues.
  # What changes is that a reader of the log can see which passes did nothing.
  if [ "${2:-0}" -ne 0 ]; then
    echo "   !! $1 exited $2 — this pass did NOT do its work; the loop continues" >&2
  fi
}

_land_loop() {
  while :; do
    echo "── $(_stamp) ── land ──"
    # The ${VAR:+--flag "$VAR"} forms must word-split to vanish when unset.
    # shellcheck disable=SC2086
    python3 "$_here/fleet_lander.py" --repo "$KIT" $APPLY
    _say_step_result land $?

    # The third step, and it was missing entirely until 2026-09-08. The loop's own
    # docstring said "route -> land -> label/close" and the suite asserted the
    # order by checking the file had "3+ steps" — so `issue_lifecycle.py` was
    # executed by nothing, and the rule it enforces (label on develop, close only
    # on release) stayed a manual chore while the automation reported nothing to
    # do. See #39.
    #
    # It writes to the tracker, which is outside this machine, so a dry run says
    # what it would do rather than doing it.
    echo "── $(_stamp) ── issues ──"
    if [ -n "$APPLY" ]; then
      # `|| true` kept the loop alive, which is right — one failed tracker write must
      # not stop the fleet — and it also threw the answer away. A gh auth expiry, a
      # rate limit and a crash all left the same trace as success.
      python3 "$_here/issue_lifecycle.py" --repo "$KIT"
      _say_step_result issues $?
    else
      echo "   (dry run: the tracker is not touched)"
    fi
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
#
# The comment said that and the code did the opposite: `wait "$_route_pid" "$_land_pid"`
# blocks until BOTH children have exited and returns the status of the LAST one. If the
# route loop is killed — OOM, a stray signal, a `kill` aimed at a child pid — the
# supervisor waits on the land loop as if nothing happened, and the land loop keeps
# printing. `wait -n` returns when the FIRST one goes, which is the event that matters.
trap 'kill "$_route_pid" "$_land_pid" 2>/dev/null' EXIT INT TERM
wait -n "$_route_pid" "$_land_pid"
_first_status=$?

if kill -0 "$_route_pid" 2>/dev/null; then
  _dead="the LAND loop"
else
  _dead="the ROUTE loop"
fi
echo "── $(_stamp) ── $_dead exited ($_first_status) ──" >&2
echo "   A supervisor with one loop left is half a supervisor, and the half that keeps" >&2
echo "   printing reads as a supervisor that works. Stopping the other and exiting." >&2
kill "$_route_pid" "$_land_pid" 2>/dev/null
wait "$_route_pid" "$_land_pid" 2>/dev/null
exit "${_first_status:-1}"
