#!/bin/bash
# SessionStart hook — injects dynamic project context at session start.
#
# Triggered by Claude Code at: new session, resume, /clear, post-compaction.
# Emits canonical JSON with hookSpecificOutput.additionalContext per
# https://code.claude.com/docs/en/hooks.md (Claude Code 2026).
#
# Surfaces:
#   - Current git branch + working-tree status (clean / dirty)
#   - Active plan slug (from .active_plan or fallback to newest)
#   - Active ralph-loop state (if ralph-loop.local.md present and active)
#   - Reminder of unbreakable principles

set -eu

# shellcheck source=environment/detect-layout.sh
source "$(dirname "$0")/environment/detect-layout.sh"

CTX=""
add() { CTX="$CTX$1
"; }

# 1) Git state
if command -v git >/dev/null 2>&1 && [ -d .git ]; then
  BRANCH=$(git branch --show-current 2>/dev/null || echo "(detached)")
  STATUS=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  AHEAD=$(git rev-list --count "@{upstream}..HEAD" 2>/dev/null || echo "0")
  if [ "$STATUS" -eq 0 ]; then
    add "Git: branch=$BRANCH (clean, $AHEAD ahead of upstream)"
  else
    add "Git: branch=$BRANCH ($STATUS uncommitted files, $AHEAD ahead of upstream)"
  fi
fi

# 2) Active plan
PLAN_SLUG=""
if [ -f "$ECO/.active_plan" ]; then
  AP=$(tr -d '\r\n[:space:]' < "$ECO/.active_plan" 2>/dev/null)
  if [ -n "$AP" ] && [ -f "$ECO/records/plans/${AP}-plan.md" ]; then
    PLAN_SLUG="$AP"
    add "Active plan: $AP ($ECO/records/plans/${AP}-plan.md) — pinned via $ECO/.active_plan"
  fi
fi
if [ -z "$PLAN_SLUG" ] && [ -d "$ECO/records/plans" ]; then
  NEWEST=$(ls -t "$ECO"/records/plans/*-plan.md 2>/dev/null | head -1)
  if [ -n "$NEWEST" ]; then
    PLAN_SLUG=$(basename "$NEWEST" -plan.md)
    add "Active plan: $PLAN_SLUG (resolved by mtime — set $ECO/.active_plan to pin)"
  fi
fi

# 3) Ralph-loop state
if [ -f "$ECO/ralph-loop.local.md" ]; then
  ACTIVE=$(grep '^active:' "$ECO/ralph-loop.local.md" 2>/dev/null | sed 's/active: *//' | tr -d ' ')
  ITER=$(grep '^iteration:' "$ECO/ralph-loop.local.md" 2>/dev/null | sed 's/iteration: *//' | tr -d ' ')
  if [ "$ACTIVE" = "true" ]; then
    add "ralph-loop: ACTIVE (iter $ITER) — if stale (>24h, no progress), cancel via /ralph-loop:cancel-ralph or delete the file"
  fi
fi

# 4) The Squad map, in its compact form
#
# WHY INLINE, AND WHY ONLY HERE
# -----------------------------
# The full map is `rules/squad-map.md`. This is the part an agent needs BEFORE it
# can decide anything: which phase it is in, who owns the decision, and the one
# routing rule that has a refusal attached.
#
# It is injected at SessionStart and NOT on every prompt. `userpromptsubmit-inject.sh`
# records why that distinction matters: its additionalContext stays in the
# conversation history, so anything re-injected per turn accumulates linearly and
# drives compaction. Once per session is the right cadence for orientation — and
# unlike a per-turn hook, a pointer here IS walkable, because the agent has the
# whole session to open the file.
#
# THIS IS A SUMMARY, AND THE MAP IS THE SOURCE. Same discipline as the parsimony
# ladder in the sibling hook: edit `rules/squad-map.md` first, then bring this in
# line with it — never the reverse, and never only one. `scripts/check_squad_map.py`
# keeps the map honest against the directory; nothing checks this summary against
# the map, so the comment is the only thing standing between them.
add ""
add "SQUAD — the chain, and who decides (full map: $ECO/rules/squad-map.md)"
add "  BRAINSTORM -> BACKLOG -> DISCOVER -> PLAN -> IMPLEMENT -> CODE-QUALITY -> REVIEW -> RELEASE -> ACCEPTANCE"
add "  BRAINSTORM is the ONLY phase that requires a person; everything after it runs unattended, merge included."
add "  ITEM_KILLED ends the chain and is a SUCCESSFUL outcome."
add "  Roles: kairos=what work exists & in what order | iris=what the user experiences | daedalus=one item's technical path | hermes=flow & halts"
add "  Domain specialists are the PROJECT's, never the kit's. Reach them with scripts/route_domain.py <repo>;"
add "    exit 3 (BROKEN ROUTE) means the domain names a specialist nobody wrote — stop, do NOT stand in for them."
add "  No verdict is asserted in prose: a script computes it. Read the cycle rule before running a phase."

# 5) Reminder
add ""
add "Unbreakable principles apply (see ~/.claude/CLAUDE.md): 95% confidence, TDD-first, no commits to main, CHANGELOG discipline."

# Exit silently if nothing relevant
if [ -z "$CTX" ]; then
  exit 0
fi

CTX_JSON=$(printf '%s' "$CTX" | jq -Rs .)
printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":%s}}\n' "$CTX_JSON"
exit 0
