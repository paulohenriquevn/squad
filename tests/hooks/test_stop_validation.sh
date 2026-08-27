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
  mkdir -p "$TMPDIR_TEST/hooks/environment"
  cp "$REPO_ROOT/hooks/environment/detect-layout.sh" "$TMPDIR_TEST/hooks/environment/detect-layout.sh"

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

# ---- Comment-only change to source => exit 0 (colhido do theokit-tui) ----
# A comment-only change has NOTHING to announce to a consumer, and Rule 6 says to write
# for the consumer. Demanding an entry for it invites the two worst outcomes: a fabricated
# line polluting the public contract, or the override — and reaching for the override to
# satisfy a question the gate should not have asked is how a gate stops being read.
setup
printf 'print("hello")\n' > "$TMPDIR_TEST/app.py"
printf '# Changelog\n\n## [Unreleased]\n### Added\n- app.py\n' > "$TMPDIR_TEST/CHANGELOG.md"
git -C "$TMPDIR_TEST" add app.py CHANGELOG.md
git -C "$TMPDIR_TEST" commit -m "base" --quiet
printf '# explains the why\nprint("hello")\n' > "$TMPDIR_TEST/app.py"
git -C "$TMPDIR_TEST" add app.py
git -C "$TMPDIR_TEST" commit -m "comment only" --quiet
rc=$(run_hook)
assert_exit "comment-only change without CHANGELOG => exit 0" 0 "$rc"
teardown

# ---- Code change disguised among comments => exit 2 (conservative by construction) ----
# The check removes only unambiguously comment or blank lines, so ANY changed line carrying
# code leaves the file in CODE_CHANGED. A false negative about a real change is impossible;
# a false positive is merely inconvenient. The asymmetry is deliberate.
setup
printf 'print("hello")\n' > "$TMPDIR_TEST/app.py"
printf '# Changelog\n\n## [Unreleased]\n### Added\n- app.py\n' > "$TMPDIR_TEST/CHANGELOG.md"
git -C "$TMPDIR_TEST" add app.py CHANGELOG.md
git -C "$TMPDIR_TEST" commit -m "base" --quiet
printf '# um comentario\nprint("tchau")\n' > "$TMPDIR_TEST/app.py"
git -C "$TMPDIR_TEST" add app.py
git -C "$TMPDIR_TEST" commit -m "code plus comment" --quiet
rc=$(run_hook)
assert_exit "code change among comments still demands CHANGELOG => exit 2" 2 "$rc"
teardown

# ---- Test-only change => exit 0 ----
setup
printf 'print("hello")\n' > "$TMPDIR_TEST/app.py"
printf '# Changelog\n\n## [Unreleased]\n### Added\n- app.py\n' > "$TMPDIR_TEST/CHANGELOG.md"
git -C "$TMPDIR_TEST" add app.py CHANGELOG.md
git -C "$TMPDIR_TEST" commit -m "base" --quiet
mkdir -p "$TMPDIR_TEST/tests"
printf 'def test_x():\n    assert True\n' > "$TMPDIR_TEST/tests/test_x.py"
git -C "$TMPDIR_TEST" add tests/test_x.py
git -C "$TMPDIR_TEST" commit -m "add test" --quiet
rc=$(run_hook)
assert_exit "test-only change => exit 0" 0 "$rc"
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
# Project WITHOUT CHANGELOG.md — the gate must not vanish silently
# ---------------------------------------------------------------------------
# `if [ -f "CHANGELOG.md" ]` disabled all of Rule 6 when the file did not exist.
# An adopting project that never created one never discovered the kit expected
# it: discipline promised in the documentation, absent in practice.
#
# ADVISORY and not BLOCKER — creating the file is the consumer's decision, and
# locking every session of a freshly adopted repo would make the install a wall.
# What the test demands is that the silence ends, not that the session stops.

run_hook_capture() {
  (cd "$TMPDIR_TEST" && bash "$HOOK") 2>&1 || true
}

# ---- code changes, no CHANGELOG.md => warns, but does not block ----
setup
rm -f "$TMPDIR_TEST/CHANGELOG.md"
git -C "$TMPDIR_TEST" rm -q --cached CHANGELOG.md >/dev/null 2>&1 || true
echo "package main" > "$TMPDIR_TEST/app.go"
git -C "$TMPDIR_TEST" add app.go >/dev/null 2>&1
rc=$(run_hook)
assert_exit "no CHANGELOG.md: a code change does NOT block" 0 "$rc"
out=$(run_hook_capture)
TOTAL=$((TOTAL + 1))
if echo "$out" | grep -q "No CHANGELOG.md in this project"; then
  echo "  PASS  no CHANGELOG.md: emits an advisory naming the gap"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  FAIL  no CHANGELOG.md: advisory missing (the gate vanished silently)"
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi
teardown

# ---- no CHANGELOG.md and no code change => silence is correct ----
setup
rm -f "$TMPDIR_TEST/CHANGELOG.md"
git -C "$TMPDIR_TEST" rm -q --cached CHANGELOG.md >/dev/null 2>&1 || true
echo "# doc" > "$TMPDIR_TEST/NOTES.md"
git -C "$TMPDIR_TEST" add NOTES.md >/dev/null 2>&1
out=$(run_hook_capture)
TOTAL=$((TOTAL + 1))
if echo "$out" | grep -q "No CHANGELOG.md in this project"; then
  echo "  FAIL  no code changed: the advisory should not fire (noise)"
  FAIL_COUNT=$((FAIL_COUNT + 1))
else
  echo "  PASS  no code changed: no advisory (correct silence)"
  PASS_COUNT=$((PASS_COUNT + 1))
fi
teardown

# ---------------------------------------------------------------------------
# The kit installed under .claude/ is a dependency, not the consumer's source
# ---------------------------------------------------------------------------
# Measured on a freshly installed adopting project: the first session emitted 107
# warning lines about KIT files (`.claude/skills/**/*.py`) against ONE real
# finding in the user's code. Auditing your own dependency is the canonical way
# to teach someone to ignore the gate.
#
# The filter is `^\.claude/`, and it holds in both layouts without detecting
# which: under a plugin install the kit lives in `.claude/` and is excluded; in
# standalone the kit's repository keeps its files in `skills/`, still audited.

# ---- a kit file under .claude/ produces no warning ----
setup
rm -f "$TMPDIR_TEST/CHANGELOG.md"
git -C "$TMPDIR_TEST" rm -q --cached CHANGELOG.md >/dev/null 2>&1 || true
mkdir -p "$TMPDIR_TEST/.claude/skills/foo/scripts"
echo "def f(): pass" > "$TMPDIR_TEST/.claude/skills/foo/scripts/thing.py"
git -C "$TMPDIR_TEST" add -A >/dev/null 2>&1
out=$(run_hook_capture)
TOTAL=$((TOTAL + 1))
if echo "$out" | grep -q '\.claude/'; then
  echo "  FAIL  a kit file under .claude/ appeared in a warning (audits the dependency)"
  FAIL_COUNT=$((FAIL_COUNT + 1))
else
  echo "  PASS  a kit file under .claude/ produces no warning"
  PASS_COUNT=$((PASS_COUNT + 1))
fi
teardown

# ---- regression: user code OUTSIDE .claude/ stays audited ----
setup
rm -f "$TMPDIR_TEST/CHANGELOG.md"
git -C "$TMPDIR_TEST" rm -q --cached CHANGELOG.md >/dev/null 2>&1 || true
mkdir -p "$TMPDIR_TEST/.claude/skills/foo/scripts" "$TMPDIR_TEST/src"
echo "def f(): pass" > "$TMPDIR_TEST/.claude/skills/foo/scripts/thing.py"
echo "def g(): pass" > "$TMPDIR_TEST/src/mine.py"
git -C "$TMPDIR_TEST" add -A >/dev/null 2>&1
out=$(run_hook_capture)
TOTAL=$((TOTAL + 1))
if echo "$out" | grep -q 'src/mine.py'; then
  echo "  PASS  regression: user code outside .claude/ stays audited"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  FAIL  regression: the filter blinded the gate to the user's code"
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi
teardown

# ---------------------------------------------------------------------------
# knowledge-base/{references,tools}/ is THIRD-PARTY study material
# ---------------------------------------------------------------------------
# The same failure the `.claude/` filter above already fixed, in the zone the kit
# declares read-only in writing. Measured 2026-08-26 on an adopter: 500 files from
# a peer project cloned into `knowledge-base/references/` produced 517 output
# lines and 16,944 ms — 500 TDD warnings about code that is not the project's.
# Extrapolated linearly, ~3,000 files reach the 120s timeout declared for this
# hook, and a hook killed by timeout blocks nothing.

# ---- a study-zone file produces no warning ----
setup
rm -f "$TMPDIR_TEST/CHANGELOG.md"
git -C "$TMPDIR_TEST" rm -q --cached CHANGELOG.md >/dev/null 2>&1 || true
mkdir -p "$TMPDIR_TEST/knowledge-base/references/peer/mod"
echo "def f(): pass" > "$TMPDIR_TEST/knowledge-base/references/peer/mod/s.py"
git -C "$TMPDIR_TEST" add -A >/dev/null 2>&1
out=$(run_hook_capture)
TOTAL=$((TOTAL + 1))
if echo "$out" | grep -q 'knowledge-base/references/'; then
  echo "  FAIL  a knowledge-base/references/ file appeared in a warning (audits third parties)"
  FAIL_COUNT=$((FAIL_COUNT + 1))
else
  echo "  PASS  a knowledge-base/references/ file produces no warning"
  PASS_COUNT=$((PASS_COUNT + 1))
fi
teardown

# ---- knowledge-base/tools/ idem ----
setup
rm -f "$TMPDIR_TEST/CHANGELOG.md"
git -C "$TMPDIR_TEST" rm -q --cached CHANGELOG.md >/dev/null 2>&1 || true
mkdir -p "$TMPDIR_TEST/knowledge-base/tools/dep"
echo "def f(): pass" > "$TMPDIR_TEST/knowledge-base/tools/dep/s.py"
git -C "$TMPDIR_TEST" add -A >/dev/null 2>&1
out=$(run_hook_capture)
TOTAL=$((TOTAL + 1))
if echo "$out" | grep -q 'knowledge-base/tools/'; then
  echo "  FAIL  a knowledge-base/tools/ file appeared in a warning (audits third parties)"
  FAIL_COUNT=$((FAIL_COUNT + 1))
else
  echo "  PASS  a knowledge-base/tools/ file produces no warning"
  PASS_COUNT=$((PASS_COUNT + 1))
fi
teardown

# ---- the zone does not silence the CHANGELOG gate about project code ----
setup
mkdir -p "$TMPDIR_TEST/knowledge-base/references/peer" "$TMPDIR_TEST/src"
echo "def f(): pass" > "$TMPDIR_TEST/knowledge-base/references/peer/s.py"
echo "def g(): pass" > "$TMPDIR_TEST/src/mine.py"
git -C "$TMPDIR_TEST" add -A >/dev/null 2>&1
rc=$(run_hook)
assert_exit "regression: project code beside the zone still requires a CHANGELOG" 2 "$rc"
teardown

# ---------------------------------------------------------------------------
# The TDD gate walks the tree ONCE per unit, not once per file
# ---------------------------------------------------------------------------
# It pins the SHAPE the speed comes from, not a duration — a timing assertion is
# a flaky test on a loaded machine. The measured cost of one `find -maxdepth 6`
# with no match was 39 ms on a 13,000-file repo; one per changed file is what
# drove the hook to its timeout.
setup
mkdir -p "$TMPDIR_TEST/src"
printf '[project]\nname="x"\n' > "$TMPDIR_TEST/pyproject.toml"
for i in 1 2 3 4 5 6 7 8; do
  echo "def f$i(): pass" > "$TMPDIR_TEST/src/mod$i.py"
done
git -C "$TMPDIR_TEST" add -A >/dev/null 2>&1

FIND_SHIM_DIR="$TMPDIR_TEST/.shim"
mkdir -p "$FIND_SHIM_DIR"
REAL_FIND="$(command -v find)"
cat > "$FIND_SHIM_DIR/find" <<SHIM
#!/bin/bash
echo "call" >> "$TMPDIR_TEST/.find-calls"
exec "$REAL_FIND" "\$@"
SHIM
chmod +x "$FIND_SHIM_DIR/find"
: > "$TMPDIR_TEST/.find-calls"
(cd "$TMPDIR_TEST" && PATH="$FIND_SHIM_DIR:$PATH" bash "$HOOK") >/dev/null 2>&1 || true
FIND_CALLS=$(wc -l < "$TMPDIR_TEST/.find-calls" | tr -d ' ')
TOTAL=$((TOTAL + 1))
if [ "$FIND_CALLS" -le 2 ]; then
  echo "  PASS  TDD gate walks per unit ($FIND_CALLS find calls for 8 files)"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  FAIL  TDD gate walks per file ($FIND_CALLS find calls for 8 files)"
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi
teardown

# ---- regression: the paired test is still found in the unit's tree ----
setup
mkdir -p "$TMPDIR_TEST/src" "$TMPDIR_TEST/tests/unit"
printf '[project]\nname="x"\n' > "$TMPDIR_TEST/pyproject.toml"
printf '# Changelog\n\n## [Unreleased]\n- x\n' > "$TMPDIR_TEST/CHANGELOG.md"
echo "def g(): pass" > "$TMPDIR_TEST/src/pagamento.py"
echo "def test_g(): pass" > "$TMPDIR_TEST/tests/unit/test_pagamento.py"
git -C "$TMPDIR_TEST" add -A >/dev/null 2>&1
out=$(run_hook_capture)
TOTAL=$((TOTAL + 1))
if echo "$out" | grep -q 'src/pagamento.py'; then
  echo "  FAIL  a test in tests/unit/ was not found (false TDD warning)"
  FAIL_COUNT=$((FAIL_COUNT + 1))
else
  echo "  PASS  a test in tests/unit/ is found by the unit index"
  PASS_COUNT=$((PASS_COUNT + 1))
fi
teardown

# ---- regression: a file REALLY without a test is still flagged ----
setup
mkdir -p "$TMPDIR_TEST/src"
printf '[project]\nname="x"\n' > "$TMPDIR_TEST/pyproject.toml"
printf '# Changelog\n\n## [Unreleased]\n- x\n' > "$TMPDIR_TEST/CHANGELOG.md"
echo "def g(): pass" > "$TMPDIR_TEST/src/orfao.py"
git -C "$TMPDIR_TEST" add -A >/dev/null 2>&1
out=$(run_hook_capture)
TOTAL=$((TOTAL + 1))
if echo "$out" | grep -q 'src/orfao.py'; then
  echo "  PASS  a file without a test is still flagged by the gate"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  FAIL  the index blinded the gate to a file without a test"
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi
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
