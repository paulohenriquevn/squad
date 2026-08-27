#!/bin/bash
# PostToolUse hook for Edit/Write: language-agnostic quick feedback after a change.
#
# Behavior: detect the edited file's language by extension and surface output
# from the most universally-available linter for that language IF the toolchain
# is detected (project marker file present + tool on PATH). All steps are no-op
# when the toolchain isn't present.
#
# Supported:
#   .go   → go vet on the file's PACKAGE (requires go.mod) + gofmt diff
#   .py   → ruff check on the file (requires pyproject.toml or setup.py/setup.cfg)
#   .ts/.tsx/.js/.jsx → eslint on the file (requires tsconfig.json + local eslint)
#   .rs   → rustfmt --check on the file (requires Cargo.toml)
#
# Never blocks — output is advisory.
#
# EVERYTHING HERE IS SCOPED TO THE EDITED FILE, AND THAT IS THE DESIGN
# --------------------------------------------------------------------
# This hook runs SYNCHRONOUSLY on every edit: the agent waits for it, and there
# is no debounce — ten edits in a row are ten runs. Until 2026-08-26 three of
# the four paths checked the WHOLE PROJECT: `tsc --noEmit -p tsconfig.json`
# (even when editing a `.js`), `cargo check` (the entire crate) and
# `go vet <dir>/...` (the entire module whenever the edited file sits at the
# root). With a 60s timeout, the outcome on a mid-sized repository was one of
# the two worst: the turn stalled for tens of seconds, or the hook died halfway
# and the feedback it exists to give never arrived.
#
# What is lost is real and worth saying out loud: per-file `tsc` is not
# equivalent to project `tsc` — a type error crossing modules no longer shows up
# here. It is still caught by the suite and by CI, which is where a check of
# that scale belongs. For anyone who prefers to pay the cost per edit,
# POST_EDIT_FULL_TYPECHECK=1 restores `tsc -p` and `cargo check` — now scoped to
# the crate that owns the file, never to the whole workspace.

set -uo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.filePath // empty')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
cd "$PROJECT_DIR" || {
  echo "post-edit-check: cannot enter project directory: $PROJECT_DIR" >&2
  exit 1
}

ABS_FILE_PATH="$FILE_PATH"
case "$FILE_PATH" in
  /*) ABS_FILE_PATH="$FILE_PATH" ;;
  *) ABS_FILE_PATH="$PROJECT_DIR/$FILE_PATH" ;;
esac
PKG_DIR=$(dirname "$ABS_FILE_PATH")

# Opt-in for the project-scale checks (see the header).
FULL_TYPECHECK="${POST_EDIT_FULL_TYPECHECK:-0}"

# Manifest of the crate that owns the file — the nearest ancestor with a
# Cargo.toml. Only consulted on the Rust path; resolving it here keeps the
# `case` readable.
CRATE_MANIFEST="Cargo.toml"
_crate_dir="$PKG_DIR"
while [ "$_crate_dir" != "/" ] && [ "$_crate_dir" != "." ]; do
  if [ -f "$_crate_dir/Cargo.toml" ]; then
    CRATE_MANIFEST="$_crate_dir/Cargo.toml"
    break
  fi
  _crate_dir=$(dirname "$_crate_dir")
done

case "$FILE_PATH" in
  *.go)
    if [ -f go.mod ] && command -v go >/dev/null 2>&1; then
      # The file's PACKAGE, without `/...`: the recursive form becomes the whole
      # module whenever the edited file sits at the root, as `main.go` does.
      VET_OUTPUT=$(go vet "$PKG_DIR" 2>&1 || true)
      if [ -n "$VET_OUTPUT" ]; then
        echo "go vet warnings on $PKG_DIR — first 8 lines:"
        echo "$VET_OUTPUT" | head -8
        echo ""
      fi
      if command -v gofmt >/dev/null 2>&1 && [ -f "$ABS_FILE_PATH" ]; then
        FMT_DIFF=$(gofmt -d "$ABS_FILE_PATH" 2>/dev/null || true)
        if [ -n "$FMT_DIFF" ]; then
          echo "gofmt would reformat $FILE_PATH — first 12 diff lines:"
          echo "$FMT_DIFF" | head -12
          echo ""
          echo "Run 'gofmt -w $FILE_PATH' to apply."
        fi
      fi
    fi
    ;;
  *.py)
    if { [ -f pyproject.toml ] || [ -f setup.py ] || [ -f setup.cfg ]; } && command -v ruff >/dev/null 2>&1; then
      RUFF_OUTPUT=$(ruff check "$ABS_FILE_PATH" 2>&1 || true)
      if [ -n "$RUFF_OUTPUT" ]; then
        echo "ruff warnings on $FILE_PATH — first 8 lines:"
        echo "$RUFF_OUTPUT" | head -8
      fi
    fi
    ;;
  *.ts|*.tsx|*.js|*.jsx)
    if [ -f tsconfig.json ]; then
      if [ "$FULL_TYPECHECK" = "1" ] && [ -x node_modules/.bin/tsc ]; then
        TSC_OUTPUT=$(node_modules/.bin/tsc --noEmit -p tsconfig.json 2>&1 | head -12 || true)
        if [ -n "$TSC_OUTPUT" ]; then
          echo "tsc warnings (projeto inteiro, POST_EDIT_FULL_TYPECHECK=1) — first 12 lines:"
          echo "$TSC_OUTPUT"
        fi
      elif [ -x node_modules/.bin/eslint ]; then
        ESLINT_OUTPUT=$(node_modules/.bin/eslint "$ABS_FILE_PATH" 2>&1 | head -12 || true)
        if [ -n "$ESLINT_OUTPUT" ]; then
          echo "eslint warnings on $FILE_PATH — first 12 lines:"
          echo "$ESLINT_OUTPUT"
        fi
      fi
    fi
    ;;
  *.rs)
    if [ -f Cargo.toml ]; then
      if [ "$FULL_TYPECHECK" = "1" ] && command -v cargo >/dev/null 2>&1; then
        # The crate that OWNS the file, not the workspace: `--manifest-path` is
        # what bounds a `cargo check` in a workspace with dozens of members.
        CARGO_OUTPUT=$(cargo check --manifest-path "$CRATE_MANIFEST" --message-format=short 2>&1 | head -12 || true)
        if [ -n "$CARGO_OUTPUT" ]; then
          echo "cargo check (crate $CRATE_MANIFEST, POST_EDIT_FULL_TYPECHECK=1) — first 12 lines:"
          echo "$CARGO_OUTPUT"
        fi
      elif command -v rustfmt >/dev/null 2>&1 && [ -f "$ABS_FILE_PATH" ]; then
        FMT_OUTPUT=$(rustfmt --check "$ABS_FILE_PATH" 2>&1 | head -12 || true)
        if [ -n "$FMT_OUTPUT" ]; then
          echo "rustfmt would reformat $FILE_PATH — first 12 lines:"
          echo "$FMT_OUTPUT"
        fi
      fi
    fi
    ;;
esac

exit 0
