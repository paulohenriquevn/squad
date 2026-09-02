#!/usr/bin/env bash
# See every Squad session at once, from the shell.
#
#     mechanisms/fleet/fleet_status.sh            what each session is doing now
#     mechanisms/fleet/fleet_status.sh -f         follow: redraw every 10s
#     mechanisms/fleet/fleet_status.sh -l 20      20 lines per session, not 6
#     mechanisms/fleet/fleet_status.sh squad2     one session, in full
#
# `/squad-status` answers "why is the queue in this state" from inside a Claude
# session. This answers "what are the sessions doing", from outside, and never
# attaches to one — reading a pane does not steal it from whoever is watching.
set -uo pipefail

LOG="${LOG:-/tmp/squad-lead.jsonl}"
MARKERS="${MARKERS:-/tmp/squad-markers}"
# The project the fleet runs over. Derived from this script's own location —
# `mechanisms/fleet/` sits inside the ecosystem — so it is right in the kit's own
# repository and in a `.claude/` install without either being named here.
_here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="${PROJECT:-$(cd "$_here/../.." && pwd)}"
LINES=6
FOLLOW=0
ONLY=""

while [ $# -gt 0 ]; do
  case "$1" in
    -f|--follow) FOLLOW=1; shift ;;
    -l|--lines)  LINES="${2:-6}"; shift 2 ;;
    -h|--help)   sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)           ONLY="$1"; LINES=40; shift ;;
  esac
done

# The width the output is cut to. Fixed at 140 until 2026-09-02, which is wider
# than a pane in a 2x2 wall — every line wrapped and the report became unreadable
# exactly where it is most useful. `tput` needs a terminal; inside a pipe there is
# none, so COLUMNS answers and 100 is the last resort.
# Inside a tmux pane, ASK TMUX. `tput` needs a terminal and `COLUMNS` is not
# exported through `watch`, so both answer for the wrong thing — measured in the
# wall's status pane, where a 110-column pane was formatted for 100 and every
# other line wrapped. `$TMUX_PANE` is set by tmux for the process it runs.
if [ -n "${TMUX_PANE:-}" ] && command -v tmux >/dev/null 2>&1; then
  WIDTH="$(tmux display -p -t "$TMUX_PANE" '#{pane_width}' 2>/dev/null)"
fi
WIDTH="${WIDTH:-${COLUMNS:-$(tput cols 2>/dev/null || echo 100)}}"
[ "$WIDTH" -lt 40 ] 2>/dev/null && WIDTH=40
BODY=$((WIDTH - 8))

if [ -t 1 ]; then
  B=$'\e[1m'; D=$'\e[2m'; G=$'\e[32m'; Y=$'\e[33m'; R=$'\e[31m'; C=$'\e[36m'; Z=$'\e[0m'
else
  B=""; D=""; G=""; Y=""; R=""; C=""; Z=""
fi

# tmux paints panes with escape sequences; without stripping them the output is
# unreadable and, worse, the terminal keeps whatever mode the last one set.
strip_ansi() { sed -E $'s/\e\\[[0-9;?]*[a-zA-Z]//g; s/\e\\][^\a]*\a//g; s/\r//g'; }

# The last event the lead recorded for a session: which item, when, and what kind.
session_item() {
  local name="$1"
  [ -f "$LOG" ] || { echo "—|—|—"; return; }
  python3 - "$LOG" "$name" <<'PY' 2>/dev/null || echo "—|—|—"
import json, sys
log, want = sys.argv[1], sys.argv[2]
last = None
for line in open(log, encoding="utf-8", errors="replace"):
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if e.get("session") == want or (not e.get("session") and e.get("item")):
        if e.get("session") == want:
            last = e
print("|".join((last.get("item") or "—", last.get("event") or "—",
                (last.get("at") or "—")[11:19])) if last else "—|—|—")
PY
}

render() {
  printf '%s╭─ SQUAD SESSIONS ─%s %s%s%s\n' "$B" "$Z" "$D" "$(date '+%H:%M:%S')" "$Z"

  if ! tmux list-sessions >/dev/null 2>&1; then
    printf '%s│%s  %sno tmux server running — the fleet is down%s\n' "$B" "$Z" "$R" "$Z"
    printf '%s╰─%s  start it: %sAGENT_BUDGET_USD=15 bash %s/start_fleet.sh %s 3%s\n' \
      "$B" "$Z" "$C" "$_here" "$PROJECT" "$Z"
    return
  fi

  local names
  # The same pattern `fleet_wall.sh` uses, for the same reason and with one more:
  # run INSIDE the wall, a report that lists every session lists the wall itself,
  # and the wall's pane is this report — so the reader sees the report inside the
  # report. `lead` is excluded too; its pane is raw jsonl, and the block below
  # renders its decisions in a form a person can read.
  names="$(tmux list-sessions -F '#{session_name}' 2>/dev/null \
           | grep -E "${FLEET_PATTERN:-^squad[0-9]+$}" | sort)"
  [ -n "$ONLY" ] && names="$ONLY"

  for name in $names; do
    tmux has-session -t "$name" 2>/dev/null || { printf '  %s%s: gone%s\n' "$R" "$name" "$Z"; continue; }

    local created attached info item event when
    created="$(tmux display-message -p -t "$name" '#{session_created}' 2>/dev/null)"
    attached="$(tmux display-message -p -t "$name" '#{session_attached}' 2>/dev/null)"
    info="$(session_item "$name")"
    item="${info%%|*}"; event="$(echo "$info" | cut -d'|' -f2)"; when="${info##*|}"

    local age="?"
    [ -n "$created" ] && age="$(( ($(date +%s) - created) / 60 ))m"

    printf '%s│%s\n' "$B" "$Z"
    printf '%s├─ %s%-8s%s  up %-6s %s  %s%s%s\n' "$B" "$B" "$name" "$Z" "$age" \
      "$([ "$attached" = "1" ] && printf '%sattached%s' "$Y" "$Z" || printf '%sdetached%s' "$D" "$Z")" \
      "$C" "$([ "$item" != "—" ] && echo "$item ($event $when)" || echo "no item on record")" "$Z"

    tmux capture-pane -p -t "$name" 2>/dev/null | strip_ansi \
      | grep -vE '^\s*$|bypass permissions|^─+$|^\s*❯\s*$|tokens\s*$|ctrl\+o to expand' \
      | tail -"$LINES" | cut -c1-"$BODY" | sed "s/^/${B}│${Z}     /"
  done

  printf '%s│%s\n' "$B" "$Z"
  if [ -f "$LOG" ]; then
    local starts stalls
    starts="$(grep -c '"event": "start"' "$LOG" 2>/dev/null || echo 0)"
    stalls="$(grep -c '"event": "stalled"' "$LOG" 2>/dev/null || echo 0)"
    printf '%s├─ %slead%s      %s handed out · %s stalled · log %s\n' \
      "$B" "$B" "$Z" "$starts" "$stalls" "$LOG"
    BODY="$BODY" python3 - "$LOG" <<'PY' 2>/dev/null | sed "s/^/${B}│${Z}     /"
import json, os, sys
cut = max(20, int(os.environ.get("BODY", "92")) - 40)
rows = []
for line in open(sys.argv[1], encoding="utf-8", errors="replace"):
    try:
        rows.append(json.loads(line))
    except ValueError:
        pass
for e in rows[-4:]:
    who = e.get("session") or "-"
    print(f'{(e.get("at") or "")[11:19]}  {e.get("event","?"):8} {who:7} '
          f'{e.get("item") or "-":8} {str(e.get("reason","")).splitlines()[0][:cut]}')
PY
  else
    printf '%s├─ %slead%s      no log at %s\n' "$B" "$B" "$Z" "$LOG"
  fi

  local sel="$PROJECT/.claude/skills/backlog-review/scripts/select_backlog_item.py"
  if [ -f "$sel" ]; then
    printf '%s│%s\n' "$B" "$Z"
    printf '%s\u251c\u2500 %squeue%s     ' "$B" "$B" "$Z"
    # Through a FILE, not a pipe: a heredoc IS stdin, so `... | python3 - <<EOF`
    # hands the script to the interpreter and discards the selector's output.
    _q="$(mktemp)"
    python3 "$sel" "$PROJECT/BACKLOG.md" --json > "$_q" 2>/dev/null
    python3 "$_here/fleet_queue_line.py" "$_q" 2>/dev/null || echo "could not be read"
    rm -f "$_q"
  fi

  printf '%s╰─%s  attach: %stmux attach -t <name>%s   detach: %sctrl-b d%s   one session: %sfleet_status.sh squad2%s\n' \
    "$B" "$Z" "$C" "$Z" "$C" "$Z" "$C" "$Z"
}

if [ "$FOLLOW" = "1" ]; then
  trap 'printf "\n"; exit 0' INT
  while true; do clear; render; sleep 10; done
else
  render
fi
