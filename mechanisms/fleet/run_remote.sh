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

# No default. The fallback was one person's account on one machine, versioned in a kit
# that ships to other repositories. Every consumer got the string and none of them get
# the host, so the failure was an ssh attempt against somebody else's server rather
# than a usage message.
#
# Refusing is right here for the same reason the script refuses to fall back to local:
# "the work comes home without anyone deciding it should" applies just as much to the
# work going to a machine nobody chose.
HOST="${SQUAD_RUNNER:-}"
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
if [ -z "$HOST" ]; then
  echo "run_remote.sh: no runner. Set SQUAD_RUNNER=<user>@<host>, or pass --host." >&2
  echo "    There is no default: a kit that ships to other repositories cannot name" >&2
  echo "    one person's machine as everybody's runner." >&2
  exit 64
fi

# Reachability is checked BEFORE the command, and a failure here is loud. A
# runner script that silently falls back to local is how the work comes home
# again without anybody deciding that it should.
if ! timeout 30 ssh -o BatchMode=yes -o ConnectTimeout=15 "$HOST" true 2>/dev/null; then
  echo "FATAL: $HOST is not reachable. NOT falling back to local — that is the" >&2
  echo "       decision this script exists to stop being made by accident." >&2
  exit 69
fi

# Each argument quoted for the REMOTE shell, one at a time. `"$*"` flattened them into
# one string that the login shell re-parsed, so quoting did not survive the trip:
# `run_remote.sh --in ~/dev/theo -- grep "foo bar" .` ran `grep foo bar .` on the
# runner, and any `;`, `|`, backtick or `$(...)` in an argument — or in `--in` — was
# executed there as shell syntax. This script is driven programmatically by the fleet,
# so the arguments are not always a human's.
_quote() {
  # POSIX single-quote escaping: wrap in single quotes and replace each
  # embedded quote with '\'' — the only form that is safe for every byte.
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"
}
_remote="cd $(_quote "$DIR") && "
for _arg in "$@"; do
  _remote="$_remote$(_quote "$_arg") "
done

echo "==> $HOST:$DIR \$ $*" >&2
_start=$(date +%s)
if [ -n "$CAPTURE" ]; then
  timeout "$TIMEOUT" ssh -o BatchMode=yes "$HOST" "$_remote" 2>&1 | tee "$CAPTURE"
  _rc=${PIPESTATUS[0]}
else
  timeout "$TIMEOUT" ssh -o BatchMode=yes "$HOST" "$_remote"
  _rc=$?
fi
echo "==> remote exit $_rc after $(( $(date +%s) - _start ))s" >&2
exit "$_rc"
