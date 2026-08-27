#!/bin/bash
# PreToolUse hook for Edit/Write: write boundaries (stack-agnostic).
#
# Boundaries defended here:
#   1. knowledge-base/references/ (similar projects — inspiration) and
#      knowledge-base/tools/ (tools we depend on) are read-only study material.
#      Findings go to knowledge-base/discoveries/blueprints/.
#   2. THE INSTALLED KIT is read-only when it is a dependency of the project.
#
# The project's own architectural boundaries (e.g. DIP between domain and
# adapters) are project-specific: they belong to rules/architecture.md and are
# enforced in code review.
#
# Exit 0 = allow, Exit 2 = block.

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.filePath // empty')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# --- 1. knowledge-base/{references,tools}/ are read-only ---------------------
# Checked BEFORE the layout is resolved: `detect-layout.sh` exits 0 when it
# cannot find the kit, and this boundary does not depend on there being a kit at
# all. Matches both layouts (knowledge-base/ and .claude/knowledge-base/).
if echo "$FILE_PATH" | grep -qE '(^|/)(\.claude/)?knowledge-base/(references|tools)/'; then
  echo '{"decision":"block","reason":"BOUNDARY VIOLATION: knowledge-base/references/ (similar projects — inspiration) and knowledge-base/tools/ (tools we depend on) are read-only. Never edit/create files there. Capture findings in knowledge-base/discoveries/blueprints/."}' >&2
  exit 2
fi

# --- 2. the installed kit is read-only ---------------------------------------
# WHY THIS BOUNDARY EXISTS
# A copy-installed kit lives in `<project>/.claude/`, with Edit/Write/Bash(*)
# allowed, and until 2026-08-26 no hook covered that path. The result is on
# record in `scripts/check_install_drift.py`: twenty-two kit fixes spent weeks
# inside ONE consumer's gitignored `.claude/` and nowhere else. A fix written
# here protects exactly one machine and is erased by the next `install.sh
# --force`. Its destination is the kit's own repository.
source "$(dirname "$0")/environment/detect-layout.sh"

# STANDALONE IS NEVER PROTECTED. There `KIT_DIR` is the kit's own repository
# opened for development — blocking would prevent the very work this hook exists
# to preserve. The boundary applies when the kit is a DEPENDENCY.
[ "$KIT_DIR" = "." ] && exit 0

case "$KIT_DIR" in
  /*) KIT_ABS="$KIT_DIR" ;;
   *) KIT_ABS="$PROJECT_DIR/$KIT_DIR" ;;
esac
case "$FILE_PATH" in
  /*) TARGET_ABS="$FILE_PATH" ;;
   *) TARGET_ABS="$PROJECT_DIR/$FILE_PATH" ;;
esac

# Outside the kit's tree there is nothing to decide.
case "$TARGET_ABS" in
  "$KIT_ABS"/*) REL="${TARGET_ABS#"$KIT_ABS"/}" ;;
  *) exit 0 ;;
esac

# What belongs to the PROJECT inside the kit's tree, and why:
#
#   rules/*.txt          configuration — enabled languages, live target,
#                        allowlists. `install.sh` already preserves it across
#                        installs.
#   agents/**            the specialists the project wrote about its own
#                        repositories. They exist nowhere else.
#   knowledge-base/**    the cycle's output: plans, reviews, audits, ADRs.
#   settings.json        this project's wiring.
#   .kit-manifest.txt    rewritten by the installer on every install.
#
# Everything else under the tree is the kit's CONTRACT.
case "$REL" in
  rules/*.txt|agents/*|knowledge-base/*|settings.json|.kit-manifest.txt|.install-backups/*)
    exit 0
    ;;
esac

# A skill the PROJECT wrote stays the project's. That is what
# `.kit-manifest.txt` is for: without reading it, the only way to tell the kit's
# skills from the project's would be guessing by name — measured on an adopter
# carrying 10 skills of its own alongside the kit's.
case "$REL" in
  skills/*)
    SKILL_DIR="skills/$(echo "$REL" | cut -d/ -f2)"
    MANIFEST="$KIT_ABS/.kit-manifest.txt"
    if [ -f "$MANIFEST" ] && ! grep -qxF "$SKILL_DIR" "$MANIFEST"; then
      exit 0  # not from the kit — it is the project's
    fi
    ;;
esac

REASON="BOUNDARY VIOLATION: ${REL} belongs to the installed Squad kit, which is read-only here. A fix written inside an installed kit protects exactly one machine and is erased by the next install. Send it to the kit's own repository instead. Project-owned paths under the same tree stay writable: rules/*.txt (config), agents/ (your domain specialists), knowledge-base/ (cycle output) and settings.json."
printf '{"decision":"block","reason":%s}\n' "$(printf '%s' "$REASON" | jq -Rs .)" >&2
exit 2
