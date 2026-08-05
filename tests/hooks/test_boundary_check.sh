#!/bin/bash
# Tests for hooks/boundary-check.sh
# Verifies that writes to knowledge-base/references/ and knowledge-base/tools/
# are blocked, while writes to other paths are allowed.
#
# The hook reads JSON from stdin with a file_path field (Edit/Write tool schema).
# Exit 0 = allow, Exit 2 = block.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOK="$REPO_ROOT/hooks/boundary-check.sh"

PASS_COUNT=0
FAIL_COUNT=0
TOTAL=0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
setup() {
  TMPDIR_TEST="$(mktemp -d)"
  mkdir -p "$TMPDIR_TEST/skills" "$TMPDIR_TEST/rules" "$TMPDIR_TEST/hooks"
  export CLAUDE_PROJECT_DIR="$TMPDIR_TEST"
}

teardown() {
  rm -rf "$TMPDIR_TEST"
  unset CLAUDE_PROJECT_DIR
}

make_input() {
  local path="$1"
  printf '{"tool_name":"Write","tool_input":{"file_path":"%s"}}' "$path"
}

assert_exit() {
  local description="$1"
  local expected="$2"
  local actual="$3"
  TOTAL=$((TOTAL + 1))

  if [ "$actual" -eq "$expected" ]; then
    echo "  PASS  $description"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo "  FAIL  $description  (expected exit $expected, got $actual)"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
}

run_hook() {
  local path="$1"
  local rc=0
  make_input "$path" | bash "$HOOK" >/dev/null 2>&1 || rc=$?
  echo "$rc"
}

# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

echo ""
echo "=== boundary-check.sh ==="
echo ""

# ---- Write to knowledge-base/references/ (blocked) ----
setup
rc=$(run_hook "knowledge-base/references/project-x/README.md")
assert_exit "write to knowledge-base/references/ is blocked" 2 "$rc"
teardown

# ---- Write to knowledge-base/tools/ (blocked) ----
setup
rc=$(run_hook "knowledge-base/tools/sometool/config.yaml")
assert_exit "write to knowledge-base/tools/ is blocked" 2 "$rc"
teardown

# ---- Write to .claude/knowledge-base/references/ (blocked) ----
setup
rc=$(run_hook ".claude/knowledge-base/references/lib/file.py")
assert_exit "write to .claude/knowledge-base/references/ is blocked" 2 "$rc"
teardown

# ---- Write to .claude/knowledge-base/tools/ (blocked) ----
setup
rc=$(run_hook ".claude/knowledge-base/tools/tool/main.go")
assert_exit "write to .claude/knowledge-base/tools/ is blocked" 2 "$rc"
teardown

# ---- Write to knowledge-base/discoveries/ (allowed) ----
setup
rc=$(run_hook "knowledge-base/discoveries/blueprints/finding.md")
assert_exit "write to knowledge-base/discoveries/ is allowed" 0 "$rc"
teardown

# ---- Write to src/ (allowed) ----
setup
rc=$(run_hook "src/main.py")
assert_exit "write to src/main.py is allowed" 0 "$rc"
teardown

# ---- Write to rules/ (allowed) ----
setup
rc=$(run_hook "rules/testing.md")
assert_exit "write to rules/ is allowed" 0 "$rc"
teardown

# ---- Write to hooks/ (allowed) ----
setup
rc=$(run_hook "hooks/new-hook.sh")
assert_exit "write to hooks/ is allowed" 0 "$rc"
teardown

# ---- Empty file_path (allowed — no path to check) ----
setup
rc=0
echo '{"tool_name":"Write","tool_input":{}}' | bash "$HOOK" >/dev/null 2>&1 || rc=$?
assert_exit "empty file_path is allowed" 0 "$rc"
teardown

# ---- Absolute path containing knowledge-base/references/ (blocked) ----
setup
rc=$(run_hook "/home/user/project/knowledge-base/references/file.txt")
assert_exit "absolute path to knowledge-base/references/ is blocked" 2 "$rc"
teardown

# ---- File with 'references' in name but not in knowledge-base (allowed) ----
setup
rc=$(run_hook "docs/references-guide.md")
assert_exit "file named references outside knowledge-base is allowed" 0 "$rc"
teardown

# ---- filePath variant (camelCase) ----
setup
rc=0
printf '{"tool_name":"Edit","tool_input":{"filePath":"knowledge-base/references/x.md"}}' \
  | bash "$HOOK" >/dev/null 2>&1 || rc=$?
assert_exit "filePath (camelCase) to references/ is blocked" 2 "$rc"
teardown

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "--- Results: $PASS_COUNT/$TOTAL passed ---"
if [ "$FAIL_COUNT" -gt 0 ]; then
  echo "$FAIL_COUNT FAILED"
  exit 1
fi
echo "All tests passed."
exit 0
