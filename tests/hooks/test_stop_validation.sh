#!/bin/bash
# Tests for hooks/stop-validation.sh
# Verifies CHANGELOG discipline, secret leak detection, and clean run behaviour.
#
# The Stop hook reads git diff state (unstaged, staged, last commit) to decide.
# We simulate changes by committing files into a temp git repo.
#
# Exit codes: 0 = clean/advisory-only, 2 = hard-gate violation.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOK="$REPO_ROOT/hooks/stop-validation.sh"

PASS_COUNT=0
FAIL_COUNT=0
TOTAL=0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
setup() {
  TMPDIR_TEST="$(mktemp -d)"
  mkdir -p "$TMPDIR_TEST/skills" "$TMPDIR_TEST/rules" "$TMPDIR_TEST/hooks"
  # Copy detect-layout.sh so the hook can source it
  mkdir -p "$TMPDIR_TEST/hooks/lib"
  cp "$REPO_ROOT/hooks/lib/detect-layout.sh" "$TMPDIR_TEST/hooks/lib/detect-layout.sh"

  export CLAUDE_PROJECT_DIR="$TMPDIR_TEST"
  unset STOP_VALIDATION_WARN_ONLY 2>/dev/null || true

  # Initialise repo with a baseline commit
  git -C "$TMPDIR_TEST" init -b develop --quiet
  git -C "$TMPDIR_TEST" config user.email "test@test.com"
  git -C "$TMPDIR_TEST" config user.name "Test"

  # Create CHANGELOG.md so the discipline check activates
  echo "# Changelog" > "$TMPDIR_TEST/CHANGELOG.md"
  touch "$TMPDIR_TEST/dummy"
  git -C "$TMPDIR_TEST" add .
  git -C "$TMPDIR_TEST" commit -m "init" --quiet
}

teardown() {
  rm -rf "$TMPDIR_TEST"
  unset CLAUDE_PROJECT_DIR
  unset STOP_VALIDATION_WARN_ONLY 2>/dev/null || true
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
  local rc=0
  (cd "$TMPDIR_TEST" && bash "$HOOK") >/dev/null 2>&1 || rc=$?
  echo "$rc"
}

# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

echo ""
echo "=== stop-validation.sh ==="
echo ""

# ---- Clean run: no file changes => exit 0 ----
setup
rc=$(run_hook)
assert_exit "no changes => clean exit 0" 0 "$rc"
teardown

# ---- Source changed, CHANGELOG NOT updated => exit 2 (blocked) ----
setup
echo 'print("hello")' > "$TMPDIR_TEST/app.py"
git -C "$TMPDIR_TEST" add app.py
git -C "$TMPDIR_TEST" commit -m "add source" --quiet
rc=$(run_hook)
assert_exit "source changed without CHANGELOG update => exit 2" 2 "$rc"
teardown

# ---- Source changed, CHANGELOG IS updated => exit 0 ----
setup
echo 'print("hello")' > "$TMPDIR_TEST/app.py"
echo -e "# Changelog\n\n## [Unreleased]\n### Added\n- app.py" > "$TMPDIR_TEST/CHANGELOG.md"
git -C "$TMPDIR_TEST" add app.py CHANGELOG.md
git -C "$TMPDIR_TEST" commit -m "add source with changelog" --quiet
rc=$(run_hook)
assert_exit "source changed with CHANGELOG update => exit 0" 0 "$rc"
teardown

# ---- Secret file .env committed => exit 2 (blocked) ----
setup
echo "SECRET=foo" > "$TMPDIR_TEST/.env"
git -C "$TMPDIR_TEST" add .env
git -C "$TMPDIR_TEST" commit -m "add env" --quiet
# Also update CHANGELOG to avoid that blocker interfering
echo -e "# Changelog\n\n## [Unreleased]\n### Added\n- env" > "$TMPDIR_TEST/CHANGELOG.md"
git -C "$TMPDIR_TEST" add CHANGELOG.md
git -C "$TMPDIR_TEST" commit --amend -m "add env with changelog" --quiet
rc=$(run_hook)
assert_exit ".env committed => exit 2" 2 "$rc"
teardown

# ---- Secret file credentials.json committed => exit 2 (blocked) ----
setup
echo '{}' > "$TMPDIR_TEST/credentials.json"
git -C "$TMPDIR_TEST" add credentials.json
echo -e "# Changelog\n\n## [Unreleased]\n### Added\n- creds" > "$TMPDIR_TEST/CHANGELOG.md"
git -C "$TMPDIR_TEST" add CHANGELOG.md
git -C "$TMPDIR_TEST" commit -m "add creds" --quiet
rc=$(run_hook)
assert_exit "credentials.json committed => exit 2" 2 "$rc"
teardown

# ---- Secret file server.pem committed => exit 2 (blocked) ----
setup
echo "-----BEGIN CERT-----" > "$TMPDIR_TEST/server.pem"
git -C "$TMPDIR_TEST" add server.pem
echo -e "# Changelog\n\n## [Unreleased]\n### Added\n- cert" > "$TMPDIR_TEST/CHANGELOG.md"
git -C "$TMPDIR_TEST" add CHANGELOG.md
git -C "$TMPDIR_TEST" commit -m "add cert" --quiet
rc=$(run_hook)
assert_exit "server.pem committed => exit 2" 2 "$rc"
teardown

# ---- Secret file private.key committed => exit 2 (blocked) ----
setup
echo "KEY" > "$TMPDIR_TEST/private.key"
git -C "$TMPDIR_TEST" add private.key
echo -e "# Changelog\n\n## [Unreleased]\n### Added\n- key" > "$TMPDIR_TEST/CHANGELOG.md"
git -C "$TMPDIR_TEST" add CHANGELOG.md
git -C "$TMPDIR_TEST" commit -m "add key" --quiet
rc=$(run_hook)
assert_exit "private.key committed => exit 2" 2 "$rc"
teardown

# ---- .env.production committed => exit 2 (blocked) ----
setup
echo "SECRET=bar" > "$TMPDIR_TEST/.env.production"
git -C "$TMPDIR_TEST" add .env.production
echo -e "# Changelog\n\n## [Unreleased]\n### Added\n- env prod" > "$TMPDIR_TEST/CHANGELOG.md"
git -C "$TMPDIR_TEST" add CHANGELOG.md
git -C "$TMPDIR_TEST" commit -m "add env prod" --quiet
rc=$(run_hook)
assert_exit ".env.production committed => exit 2" 2 "$rc"
teardown

# ---- WARN_ONLY override converts blockers to warnings => exit 0 ----
setup
echo 'print("hello")' > "$TMPDIR_TEST/app.py"
git -C "$TMPDIR_TEST" add app.py
git -C "$TMPDIR_TEST" commit -m "add source" --quiet
export STOP_VALIDATION_WARN_ONLY=1
rc=$(run_hook)
assert_exit "STOP_VALIDATION_WARN_ONLY=1 downgrades to exit 0" 0 "$rc"
teardown

# ---- Only test files changed (no production source) => exit 0 ----
setup
echo 'def test_foo(): pass' > "$TMPDIR_TEST/test_app.py"
echo -e "# Changelog\n\n## [Unreleased]\n### Added\n- tests" > "$TMPDIR_TEST/CHANGELOG.md"
git -C "$TMPDIR_TEST" add test_app.py CHANGELOG.md
git -C "$TMPDIR_TEST" commit -m "add test" --quiet
rc=$(run_hook)
assert_exit "only test file changed => exit 0" 0 "$rc"
teardown

# ---- Non-code file changed (e.g. .md) without CHANGELOG => exit 0 ----
# The CHANGELOG gate only triggers for recognized source extensions.
setup
echo "docs" > "$TMPDIR_TEST/notes.md"
git -C "$TMPDIR_TEST" add notes.md
git -C "$TMPDIR_TEST" commit -m "add docs" --quiet
rc=$(run_hook)
assert_exit "non-code file change without CHANGELOG => exit 0" 0 "$rc"
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
