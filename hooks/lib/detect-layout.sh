#!/bin/bash
# Layout resolution shared by the hooks.
#
# Usage, from any hook:
#   source "$(dirname "$0")/lib/detect-layout.sh"
#
# Once sourced, TWO paths are defined — and the distinction between them is the
# whole point of this file:
#
#   KIT_DIR  the kit's CODE (skills/, rules/, hooks/). Read-only for the
#            consumer. Under the native plugin layout it lives OUTSIDE the project.
#   ECO      the cycle's DATA (knowledge-base/, .active_plan, .attestations).
#            Always inside the project, always writable.
#
# $PROJECT_DIR is defined too (default: $CLAUDE_PROJECT_DIR or pwd).
# Exits 0 defining nothing when there is no kit — a project that does not use it
# should hear nothing.
#
# WHY TWO PATHS AND NOT ONE
# -------------------------
# Until 2026-08-26 there was only `ECO`, and it answered for both. That works
# only while the kit LIVES inside the project, which is what
# `scripts/install.sh` does by copying it into `<project>/.claude/`. The cost of
# that conflation is on record in `scripts/check_install_drift.py`: twenty-two
# kit fixes spent weeks inside one consumer's gitignored `.claude/` and nowhere
# else. As long as the kit's code is a writable directory inside the project,
# the consumer's agent edits it — and the divergence is not a bug to fix, it is
# the design's expected behaviour.
#
# Separating them is what makes the native layout possible, where the code sits
# under `$CLAUDE_PLUGIN_ROOT` and the project keeps only what is its own.

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$PROJECT_DIR" || exit 0

# A directory is the kit when it carries the three trees that define it.
_squad_has_kit() {
  [ -d "$1/skills" ] && [ -d "$1/rules" ] && [ -d "$1/hooks" ]
}

KIT_DIR=""
ECO=""

if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
  # --- 1. NATIVE PLUGIN -----------------------------------------------------
  # Claude Code exports CLAUDE_PLUGIN_ROOT to the hooks declared in
  # hooks/hooks.json. The kit's code lives outside the project.
  if _squad_has_kit "$CLAUDE_PLUGIN_ROOT"; then
    KIT_DIR="$CLAUDE_PLUGIN_ROOT"
    # The data stays in the project. `.claude/` when it exists, to match the
    # layout copy installs already use; the root otherwise.
    if [ -d ".claude" ]; then ECO=".claude"; else ECO="."; fi
  else
    # CLAUDE_PLUGIN_ROOT set without the kit is a corrupt install — not the same
    # as "nobody installed it". Before this the script exited 0 without a line,
    # and every gate was switched off while looking approved. Measured
    # 2026-08-26: stop-validation.sh and sessionstart-context.sh exited 0, mute.
    echo "[squad] CLAUDE_PLUGIN_ROOT=${CLAUDE_PLUGIN_ROOT} does not contain skills/, rules/ and hooks/." >&2
    echo "[squad] Incomplete install — the gates are NOT active in this session." >&2
    exit 0
  fi
elif _squad_has_kit ".claude"; then
  # --- 2. COPY INSTALL ------------------------------------------------------
  # The layout scripts/install.sh writes. Code and data coincide, as they always
  # did: nothing changes for anyone who already installed this way.
  KIT_DIR=".claude"
  ECO=".claude"
elif _squad_has_kit "."; then
  # --- 3. STANDALONE --------------------------------------------------------
  # The kit's own repository opened in Claude Code.
  KIT_DIR="."
  ECO="."
else
  exit 0
fi

# Diagnostics on demand. `settings.json` already exposes CLAUDE_DEBUG_HOOKS, and
# the question "where does this hook think the kit came from?" had no answer.
if [ "${CLAUDE_DEBUG_HOOKS:-0}" = "1" ]; then
  echo "[squad] KIT_DIR=${KIT_DIR} ECO=${ECO} PROJECT_DIR=${PROJECT_DIR}" >&2
fi
