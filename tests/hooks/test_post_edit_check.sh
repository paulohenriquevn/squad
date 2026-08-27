#!/bin/bash
# Tests for hooks/post-edit-check.sh
#
# What these tests pin is the SCOPE of the commands, not their duration. This
# hook runs on EVERY edit, synchronously — the agent waits for it. A command that
# checks the whole project turns every Edit into a build: measured by code reading
# on 2026-08-26, the TypeScript path ran
# `tsc --noEmit -p tsconfig.json` (projeto inteiro, inclusive ao editar um
# `.js`), o Rust rodava `cargo check` (crate inteiro) e o Go rodava
# `go vet <dir>/...` (the whole module when the file sits at the root). With no
# debounce, ten edits in a row were ten full builds, with a 60s timeout lurking —
# either the turn stalls, or the hook dies halfway and the feedback it exists to
# give never arrives.
#
# The whole-project check did not vanish: it became opt-in via
# POST_EDIT_FULL_TYPECHECK=1, and there is a test for both sides.
#
# Method: PATH shims that record the argv they receive. No real toolchain is
# needed, and the assertion is about the command the hook BUILDS.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOK="$REPO_ROOT/hooks/post-edit-check.sh"

PASS_COUNT=0
FAIL_COUNT=0
TOTAL=0

setup() {
  TMPDIR_TEST="$(mktemp -d)"
  BIN_DIR="$TMPDIR_TEST/.bin"
  ARGV_LOG="$TMPDIR_TEST/.argv"
  mkdir -p "$BIN_DIR"
  : > "$ARGV_LOG"
  export CLAUDE_PROJECT_DIR="$TMPDIR_TEST"
  unset POST_EDIT_FULL_TYPECHECK 2>/dev/null || true
}

teardown() {
  rm -rf "$TMPDIR_TEST"
  unset CLAUDE_PROJECT_DIR
  unset POST_EDIT_FULL_TYPECHECK 2>/dev/null || true
}

# shim <nome> — registra "<nome> <args>" e sai 0.
shim() {
  cat > "$BIN_DIR/$1" <<SHIM
#!/bin/bash
echo "$1 \$*" >> "$ARGV_LOG"
exit 0
SHIM
  chmod +x "$BIN_DIR/$1"
}

run_hook() {
  local file_path="$1"
  printf '{"tool_input":{"file_path":"%s"}}' "$file_path" \
    | (cd "$TMPDIR_TEST" && PATH="$BIN_DIR:$PATH" bash "$HOOK") >/dev/null 2>&1 || true
}

assert_log() {
  local description="$1" mode="$2" pattern="$3"
  TOTAL=$((TOTAL + 1))
  local hit=no
  grep -qF -- "$pattern" "$ARGV_LOG" && hit=yes
  if { [ "$mode" = "contains" ] && [ "$hit" = yes ]; } || \
     { [ "$mode" = "absent" ] && [ "$hit" = no ]; }; then
    echo "  PASS  $description"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo "  FAIL  $description"
    echo "        argv registrado: $(tr '\n' '|' < "$ARGV_LOG")"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
}

echo ""
echo "=== post-edit-check.sh ==="
echo ""

# ---------------------------------------------------------------------------
# Go — the package, not the whole module
# ---------------------------------------------------------------------------
setup
shim go
shim gofmt
printf 'module x\n' > "$TMPDIR_TEST/go.mod"
mkdir -p "$TMPDIR_TEST/internal/auth"
printf 'package auth\n' > "$TMPDIR_TEST/internal/auth/a.go"
run_hook "internal/auth/a.go"
assert_log "go vet receives the edited file's package" contains "vet $TMPDIR_TEST/internal/auth"
assert_log "go vet does NOT recurse with /... (whole module)" absent "/..."
teardown

# ---------------------------------------------------------------------------
# TypeScript — file scope by default
# ---------------------------------------------------------------------------
setup
mkdir -p "$TMPDIR_TEST/node_modules/.bin" "$TMPDIR_TEST/src"
printf '{}' > "$TMPDIR_TEST/tsconfig.json"
printf 'export const a = 1\n' > "$TMPDIR_TEST/src/a.ts"
BIN_DIR_SAVE="$BIN_DIR"
BIN_DIR="$TMPDIR_TEST/node_modules/.bin"
shim tsc
shim eslint
BIN_DIR="$BIN_DIR_SAVE"
run_hook "src/a.ts"
assert_log "whole-project tsc does NOT run by default" absent "-p tsconfig.json"
assert_log "eslint runs scoped to the edited file" contains "eslint $TMPDIR_TEST/src/a.ts"
teardown

# ---- opt-in restores the whole-project check ----
setup
mkdir -p "$TMPDIR_TEST/node_modules/.bin" "$TMPDIR_TEST/src"
printf '{}' > "$TMPDIR_TEST/tsconfig.json"
printf 'export const a = 1\n' > "$TMPDIR_TEST/src/a.ts"
BIN_DIR_SAVE="$BIN_DIR"
BIN_DIR="$TMPDIR_TEST/node_modules/.bin"
shim tsc
BIN_DIR="$BIN_DIR_SAVE"
POST_EDIT_FULL_TYPECHECK=1 run_hook "src/a.ts"
assert_log "POST_EDIT_FULL_TYPECHECK=1 restaura o tsc de projeto" contains "-p tsconfig.json"
teardown

# ---------------------------------------------------------------------------
# Rust — file formatting by default, crate build only under opt-in
# ---------------------------------------------------------------------------
setup
shim cargo
shim rustfmt
printf '[package]\nname="x"\n' > "$TMPDIR_TEST/Cargo.toml"
mkdir -p "$TMPDIR_TEST/src"
printf 'fn main() {}\n' > "$TMPDIR_TEST/src/main.rs"
run_hook "src/main.rs"
assert_log "cargo check does NOT run by default" absent "cargo check"
assert_log "rustfmt runs scoped to the edited file" contains "rustfmt --check $TMPDIR_TEST/src/main.rs"
teardown

setup
shim cargo
shim rustfmt
printf '[package]\nname="x"\n' > "$TMPDIR_TEST/Cargo.toml"
mkdir -p "$TMPDIR_TEST/src"
printf 'fn main() {}\n' > "$TMPDIR_TEST/src/main.rs"
POST_EDIT_FULL_TYPECHECK=1 run_hook "src/main.rs"
assert_log "POST_EDIT_FULL_TYPECHECK=1 restaura o cargo check da crate dona" contains "--manifest-path $TMPDIR_TEST/Cargo.toml"
teardown

# ---------------------------------------------------------------------------
# Python — was already file-scoped; regression
# ---------------------------------------------------------------------------
setup
shim ruff
printf '[project]\nname="x"\n' > "$TMPDIR_TEST/pyproject.toml"
mkdir -p "$TMPDIR_TEST/src"
printf 'x = 1\n' > "$TMPDIR_TEST/src/a.py"
run_hook "src/a.py"
assert_log "ruff stays scoped to the edited file" contains "ruff check $TMPDIR_TEST/src/a.py"
teardown

# ---------------------------------------------------------------------------
# With no project marker, nothing runs and the hook exits clean
# ---------------------------------------------------------------------------
# The promise in the hook's header is to be a no-op when the toolchain is not the
# project's. Without `go.mod` no command should be built, even with `go` on PATH.
setup
shim go
shim gofmt
mkdir -p "$TMPDIR_TEST/internal"
printf 'package internal\n' > "$TMPDIR_TEST/internal/a.go"
rc=0
printf '{"tool_input":{"file_path":"internal/a.go"}}' \
  | (cd "$TMPDIR_TEST" && PATH="$BIN_DIR:$PATH" bash "$HOOK") >/dev/null 2>&1 || rc=$?
TOTAL=$((TOTAL + 1))
if [ "$rc" -eq 0 ] && [ ! -s "$ARGV_LOG" ]; then
  echo "  PASS  without go.mod nothing runs and the hook exits 0 (advisory, never blocks)"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  FAIL  without go.mod the hook exited $rc and built: $(tr '\n' '|' < "$ARGV_LOG")"
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi
teardown

echo ""
echo "--- Results: $PASS_COUNT/$TOTAL passed ---"
if [ "$FAIL_COUNT" -gt 0 ]; then
  echo "$FAIL_COUNT FAILED"
  exit 1
fi
echo "All tests passed."
exit 0
