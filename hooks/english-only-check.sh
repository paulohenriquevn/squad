#!/usr/bin/env bash
# PostToolUse hook for Edit/Write: surfaces Portuguese in the file just written.
#
# WHY THIS HOOK EXISTS
# --------------------
# `scripts/check_english_only.py` shipped to every consumer and NOTHING invoked
# it there. The kit runs it in its own CI; consumers do not have the kit's CI,
# and the installer does not carry `.github/`. So the gate reached 19 installs as
# a script nobody would ever run — the exact defect this kit spent a day fixing
# in the other direction, a mechanism with no contract, now a mechanism with no
# caller.
#
# WHY ADVISORY RATHER THAN BLOCKING
# ---------------------------------
# `boundary-check.sh` blocks in PreToolUse because writing to the wrong PATH is
# unambiguous — the path is either the kit's or the project's. Language is not
# unambiguous at write time: a verbatim quote, a fixture that must be Portuguese
# to exercise the rule it tests, an error message copied from a tool. Those are
# legitimate and take the `english-only:` marker.
#
# Blocking them would put the author in a fight with the hook at the moment they
# are least able to explain themselves. So this warns immediately, and
# `check_english_only.py` remains the verdict — the same warn-first split
# `public-copy-lint.sh` uses for the same reason.
#
# Exit 0 always.

set -uo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.filePath // empty')

[ -z "$FILE_PATH" ] && exit 0
[ -f "$FILE_PATH" ] || exit 0

# Skip what the checker itself skips: third-party material is not ours to
# rewrite, and binaries are not prose.
case "$FILE_PATH" in
  */node_modules/*|*/.git/*|*/__pycache__/*|*/study-material/*|*/tools/*) exit 0 ;;
  *.png|*.jpg|*.jpeg|*.gif|*.svg|*.pdf|*.ico|*.woff|*.woff2|*.pyc|*.lock) exit 0 ;;
esac

# Locate the checker in either layout — the kit may be a plugin or a copy.
CHECKER=""
for candidate in \
  "${CLAUDE_PLUGIN_ROOT:-}/scripts/check_english_only.py" \
  "$(dirname "$0")/../scripts/check_english_only.py" \
  ".claude/scripts/check_english_only.py" \
  "scripts/check_english_only.py"; do
  if [ -n "$candidate" ] && [ -f "$candidate" ]; then
    CHECKER="$candidate"
    break
  fi
done
[ -z "$CHECKER" ] && exit 0

# One file, not the repository: this runs after every edit, and scanning the
# whole tree here would make each keystroke pay for the whole history.
FINDINGS=$(python3 - "$CHECKER" "$FILE_PATH" <<'PYEOF'
import sys
from pathlib import Path

checker, target = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(checker.parent))
try:
    from check_english_only import scan_text
except ImportError:
    raise SystemExit(0)

try:
    text = target.read_text(encoding="utf-8", errors="replace")
except OSError:
    raise SystemExit(0)

findings = scan_text(text)
if not findings:
    raise SystemExit(0)

print(f"english-only: {len(findings)} line(s) in {target.name} are not in English")
for line_no, markers in findings[:5]:
    print(f"  :{line_no}  {', '.join(sorted(set(markers)))}")
if len(findings) > 5:
    print(f"  … and {len(findings) - 5} more")
print()
print("This repository is English-only (rules/english-only.md). Translate the line,")
print("or — when the Portuguese IS the point, as in a verbatim quote or a fixture")
print("that must be Portuguese — keep it and say why on the line itself:")
print("  <text>  # english-only: quoting the tool's own output")
PYEOF
)

[ -n "$FINDINGS" ] && echo "$FINDINGS"
exit 0
