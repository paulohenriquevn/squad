#!/usr/bin/env bash
# Run heavy work on the runner instead of the workstation.
#
# WHY THIS IS A SCRIPT AND NOT A HABIT
#
# Measured on 2026-09-02, mid-session: 15 heavy processes on the workstation at
# load 18.9 across 12 cores, and ZERO on the runner at load 8.0 across 8. Four
# Claude sessions idle there. Four pipeline runs, a 23-agent audit, a 7-way
# parallel repair and several full suites had all been run locally, while the
# machine bought for it answered `ssh` and took `rsync`.
#
# The operator had already corrected this once and it recurred within hours.
# Something that recurs after a correction is not an intention problem.
#
# Usage:
#   run_remote.sh --in <remote-dir> -- <command...>
#   run_remote.sh --in ~/dev/theo --capture /tmp/out.txt -- task quality:gates
#
# It streams output back and exits with the remote command's status, so a caller
# cannot tell it apart from a local run except by where the load went.

set -uo pipefail

HOST="${SQUAD_RUNNER:-paulo@165.227.121.20}"
DIR=""; CAPTURE=""; TIMEOUT="${SQUAD_REMOTE_TIMEOUT:-3600}"
while [ $# -gt 0 ]; do
  case "$1" in
    --in)      DIR="$2"; shift 2 ;;
    --host)    HOST="$2"; shift 2 ;;
    --capture) CAPTURE="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --)        shift; break ;;
    *) echo "unknown argument: $1" >&2; exit 64 ;;
  esac
done
[ -n "$DIR" ] || { echo "usage: run_remote.sh --in <remote-dir> [--capture FILE] -- <command...>" >&2; exit 64; }
[ $# -gt 0 ] || { echo "FATAL: no command after --" >&2; exit 64; }

# Reachability is checked BEFORE the command, and a failure here is loud. A
# runner script that silently falls back to local is how the work comes home
# again without anybody deciding that it should.
if ! timeout 30 ssh -o BatchMode=yes -o ConnectTimeout=15 "$HOST" true 2>/dev/null; then
  echo "FATAL: $HOST is not reachable. NOT falling back to local — that is the" >&2
  echo "       decision this script exists to stop being made by accident." >&2
  exit 69
fi

_cmd="$*"
echo "==> $HOST:$DIR \$ $_cmd" >&2
_start=$(date +%s)
if [ -n "$CAPTURE" ]; then
  timeout "$TIMEOUT" ssh -o BatchMode=yes "$HOST" "cd $DIR && $_cmd" 2>&1 | tee "$CAPTURE"
  _rc=${PIPESTATUS[0]}
else
  timeout "$TIMEOUT" ssh -o BatchMode=yes "$HOST" "cd $DIR && $_cmd"
  _rc=$?
fi
echo "==> remote exit $_rc after $(( $(date +%s) - _start ))s" >&2
exit "$_rc"
