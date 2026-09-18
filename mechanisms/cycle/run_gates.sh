#!/usr/bin/env bash
# Run a project's quality gates in PARALLEL, with a per-gate ceiling.
#
# WHY
#
# A consumer measured on 2026-09-02 ran 51 gates from one Taskfile `cmds:` list.
# `cmds:` is sequential by definition, so the wall-clock is the SUM of 51 gates
# and the pre-push hook inherits it: pushes there exceeded 20 minutes, and a
# 20-minute pre-push is a pre-push people learn to skip. The operator's rule is
# 10 minutes, and the arithmetic says the same thing from the other side — a
# ceiling nobody can meet is a ceiling that gets bypassed rather than met.
#
# Two things this changes and one it deliberately does not:
#
#   - gates run concurrently, so the wall-clock becomes the SLOWEST gate rather
#     than their sum
#   - each gate gets its own timeout, so one hang cannot consume the budget of
#     the other fifty
#   - NO gate is skipped, reordered by importance, or downgraded to a warning.
#     Making a suite fast by running less of it is the failure this exists to
#     avoid, and it is the easiest one to reach for.
#
# Usage:
#   run_gates.sh --list <file>          one gate command per line, `#` ignored
#                [--jobs N]             default: cores - 2, floor 2
#                [--timeout SECONDS]    per gate, default 600 (the 10-minute rule)
#                [--budget SECONDS]     whole run, default 600
#
# Exit codes:
#   0  every gate passed inside its timeout, and the run inside its budget
#   1  a gate failed
#   2  a gate hit its timeout — reported separately, because "slow" and "broken"
#      are different findings and a timeout hides which one it was
#   3  every gate passed but the run exceeded the budget

set -uo pipefail

LIST=""; JOBS=""; GATE_TIMEOUT=600; BUDGET=600
while [ $# -gt 0 ]; do
  case "$1" in
    --list)    LIST="$2"; shift 2 ;;
    --jobs)    JOBS="$2"; shift 2 ;;
    --timeout) GATE_TIMEOUT="$2"; shift 2 ;;
    --budget)  BUDGET="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 64 ;;
  esac
done
[ -n "$LIST" ] || { echo "usage: run_gates.sh --list <file> [--jobs N] [--timeout S] [--budget S]" >&2; exit 64; }
[ -f "$LIST" ] || { echo "FATAL: no such list: $LIST" >&2; exit 64; }

# Two cores held back for everything that is not a gate. Measured on the fleet:
# saturating every core made the machine unresponsive and the gates no faster.
if [ -z "$JOBS" ]; then
  _cores="$(nproc 2>/dev/null || echo 4)"
  JOBS=$(( _cores - 2 )); [ "$JOBS" -lt 2 ] && JOBS=2
fi

RUNDIR="$(mktemp -d)"
trap 'rm -rf "$RUNDIR"' EXIT

_total=0
while IFS= read -r line; do
  case "$line" in ''|'#'*) continue ;; esac
  printf '%s\n' "$line" >> "$RUNDIR/gates"
  _total=$(( _total + 1 ))
done < "$LIST"

# An empty list is not a pass. A gate runner that sweeps nothing and reports
# success is the exact defect this kit keeps finding in its own checks.
if [ "$_total" -eq 0 ]; then
  echo "FATAL: $LIST holds no gate commands — nothing was run, which is not the same as everything passing" >&2
  exit 64
fi

echo "==> $_total gate(s), $JOBS at a time, ${GATE_TIMEOUT}s each, ${BUDGET}s budget"

run_one() {
  local idx="$1" cmd="$2" dir="$3" t="$4"
  local start end
  start=$(date +%s%N)
  timeout --kill-after=10s "$t" bash -c "$cmd" > "$dir/$idx.out" 2>&1
  local rc=$?
  end=$(date +%s%N)
  printf '%s\t%s\t%s\n' "$rc" "$(( (end - start) / 1000000 ))" "$cmd" > "$dir/$idx.rc"
}
export -f run_one

# Only an INDEX crosses into the worker. The gate text used to, through
# `line="{}"` inside a double-quoted assignment, so the shell re-parsed it and the
# quoting was lost: `grep -q "two words" file` became `grep -q two words file`, which
# printed `bash: words file: No such file or directory` — and the mangled worker never
# wrote its `.rc`, so the tally below counted only the gates that reported and printed
# "all N gate(s) passed". A gate that did not run, reported as a gate that passed.
# The worker reads its own line from the file by number; nothing re-parses a command.
_start=$(date +%s%N)
seq 1 "$_total" \
  | xargs -P "$JOBS" -I{} bash -c '
      idx="{}"
      cmd="$(sed -n "${idx}p" "'"$RUNDIR"'/gates")"
      run_one "$idx" "$cmd" "'"$RUNDIR"'" "'"$GATE_TIMEOUT"'"'
_wall=$(( ( $(date +%s%N) - _start ) / 1000000 ))

_failed=0; _timedout=0; _slowest=0; _slowest_cmd=""; _results=0
for f in "$RUNDIR"/*.rc; do
  [ -f "$f" ] || continue
  _results=$(( _results + 1 ))
  IFS=$'\t' read -r rc ms cmd < "$f"
  [ "$ms" -gt "$_slowest" ] && { _slowest="$ms"; _slowest_cmd="$cmd"; }
  if [ "$rc" = "124" ] || [ "$rc" = "137" ]; then
    _timedout=$(( _timedout + 1 ))
    printf '  TIMEOUT  %6ss  %s\n' "$(( ms / 1000 ))" "$cmd"
  elif [ "$rc" != "0" ]; then
    _failed=$(( _failed + 1 ))
    printf '  FAIL     %6ss  %s\n' "$(( ms / 1000 ))" "$cmd"
    sed 's/^/             /' "${f%.rc}.out" | tail -6
  fi
done

# Both numbers, always. The sum is what a sequential runner would have cost and
# is the argument for this file existing; the wall-clock is what it cost.
_sum=0
for f in "$RUNDIR"/*.rc; do
  [ -f "$f" ] || continue
  IFS=$'\t' read -r _ ms _ < "$f"
  _sum=$(( _sum + ms ))
done
printf '==> wall %ss · sequential would be %ss · slowest %ss (%s)\n' \
  "$(( _wall / 1000 ))" "$(( _sum / 1000 ))" "$(( _slowest / 1000 ))" "$_slowest_cmd"

# Dispatched against reported. Nothing compared them, so a worker that died before
# writing its `.rc` simply left the tally — and the summary spoke for the gates that
# DID report while claiming to speak for all of them. A gate with no result is not a
# gate that passed, and this is the line that refuses to treat it as one.
printf '==> %s result(s) for %s dispatched gate(s)\n' "$_results" "$_total"
if [ "$_results" -ne "$_total" ]; then
  echo "==> $(( _total - _results )) gate(s) left no result. They did not run, or died before" >&2
  echo "    recording one. Either way nothing here measured them, and a missing result" >&2
  echo "    must never read as a pass." >&2
  exit 65
fi

[ "$_timedout" -gt 0 ] && { echo "==> $_timedout gate(s) hit the ${GATE_TIMEOUT}s ceiling — slow is a finding, not a pass" >&2; exit 2; }
[ "$_failed" -gt 0 ] && { echo "==> $_failed gate(s) failed" >&2; exit 1; }
if [ "$(( _wall / 1000 ))" -gt "$BUDGET" ]; then
  echo "==> every gate passed and the run took $(( _wall / 1000 ))s against a ${BUDGET}s budget." >&2
  echo "    The slowest gate is ${_slowest_cmd}. Making this fit by running fewer gates is not a fix." >&2
  exit 3
fi
echo "==> all $_total gate(s) passed"
