#!/bin/bash
# StatusLine — emits a single line shown in Claude Code's status bar.
#
# Composition: <git-branch[*=dirty]> | <plan-slug> | <ralph-loop:iter or ->
#
# Outputs nothing if not in a git repo (Claude Code falls back to default).

set -eu

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$PROJECT_DIR" 2>/dev/null || exit 0

PARTS=""

# Git. `git rev-parse` rather than `[ -d .git ]`: inside a worktree, a submodule or any
# subdirectory, `.git` is a FILE or is not here at all — and the status line then showed
# no branch in exactly the trees the fleet works in, which are worktrees.
if command -v git >/dev/null 2>&1 && git rev-parse --git-dir >/dev/null 2>&1; then
  BRANCH=$(git branch --show-current 2>/dev/null || echo "?")
  DIRTY=""
  if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    DIRTY="*"
  fi
  PARTS="$BRANCH$DIRTY"
fi

# Plan. Resolved through `squad.paths`, which owns every data-root literal, with the
# pre-`.squad` names kept as FALLBACKS. Both paths here were the old ones only —
# `.active_plan` and `records/plans/` — so on a project that had migrated, the status
# line showed no plan at all while a plan was active. Same move `fleet_status.sh` made
# for the lead log.
PLAN=""
# Every candidate path comes from `squad.paths`, canonical and legacy alike. They used
# to be typed into this file as a fallback list, which is the second spelling of a data
# root that `check_write_containment.py` exists to refuse — and the gate caught it. The
# owner publishes the order now; this script only walks it.
_RESOLVER='
import sys
from pathlib import Path
here = Path.cwd().resolve()
for up in [here, *here.parents]:
    for base in (up, up / ".claude"):
        if (base / "squad" / "paths.py").is_file():
            sys.path.insert(0, str(base)); break
    else:
        continue
    break
try:
    from squad.paths import active_plan_candidates, plans_dir_candidates
    for p in active_plan_candidates("."):
        print(f"P\t{p}")
    for p in plans_dir_candidates("."):
        print(f"D\t{p}")
except Exception:
    pass
'
_PATHS=$(python3 -c "$_RESOLVER" 2>/dev/null)

while IFS=$'\t' read -r _kind _pointer; do
  [ "$_kind" = "P" ] || continue
  [ -n "$_pointer" ] && [ -f "$_pointer" ] || continue
  PLAN=$(tr -d '\r\n[:space:]' < "$_pointer" 2>/dev/null)
  [ -n "$PLAN" ] && break
done <<EOF
$_PATHS
EOF

if [ -z "$PLAN" ]; then
  while IFS=$'\t' read -r _kind _plans; do
    [ "$_kind" = "D" ] || continue
    [ -n "$_plans" ] && [ -d "$_plans" ] || continue
    NEWEST=$(ls -t "$_plans"/*-plan.md 2>/dev/null | head -1)
    [ -n "$NEWEST" ] && { PLAN=$(basename "$NEWEST" -plan.md); break; }
  done <<EOF
$_PATHS
EOF
fi
if [ -n "$PLAN" ]; then
  PARTS="${PARTS:+$PARTS | }plan:$PLAN"
fi

# Ralph-loop
if [ -f ralph-loop.local.md ]; then
  ACTIVE=$(grep '^active:' ralph-loop.local.md 2>/dev/null | sed 's/active: *//' | tr -d ' ')
  if [ "$ACTIVE" = "true" ]; then
    ITER=$(grep '^iteration:' ralph-loop.local.md 2>/dev/null | sed 's/iteration: *//' | tr -d ' ')
    PARTS="${PARTS:+$PARTS | }loop:iter$ITER"
  fi
fi

printf '%s' "$PARTS"
