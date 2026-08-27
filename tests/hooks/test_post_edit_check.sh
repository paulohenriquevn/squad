#!/bin/bash
# Tests for hooks/post-edit-check.sh
#
# O que estes testes fixam é o ESCOPO dos comandos, não a duração deles. Este
# hook roda em TODA edição, de forma síncrona — o agente espera por ele. Um
# comando que verifica o projeto inteiro transforma cada Edit numa build:
# medido por leitura de código em 2026-08-26, o caminho TypeScript rodava
# `tsc --noEmit -p tsconfig.json` (projeto inteiro, inclusive ao editar um
# `.js`), o Rust rodava `cargo check` (crate inteiro) e o Go rodava
# `go vet <dir>/...` (módulo inteiro quando o arquivo está na raiz). Sem
# debounce, dez edições seguidas eram dez builds completas, com timeout de 60 s
# à espreita — ou o turno trava, ou o hook morre no meio e o feedback que ele
# existe para dar nunca chega.
#
# A verificação de projeto inteiro não sumiu: virou opt-in por
# POST_EDIT_FULL_TYPECHECK=1, e há teste para os dois lados.
#
# Método: shims em PATH que registram o argv recebido. Nenhuma toolchain real é
# necessária, e a asserção é sobre o comando que o hook MONTA.

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
# Go — o pacote, não o módulo inteiro
# ---------------------------------------------------------------------------
setup
shim go
shim gofmt
printf 'module x\n' > "$TMPDIR_TEST/go.mod"
mkdir -p "$TMPDIR_TEST/internal/auth"
printf 'package auth\n' > "$TMPDIR_TEST/internal/auth/a.go"
run_hook "internal/auth/a.go"
assert_log "go vet recebe o pacote do arquivo editado" contains "vet $TMPDIR_TEST/internal/auth"
assert_log "go vet NÃO recorre com /... (módulo inteiro)" absent "/..."
teardown

# ---------------------------------------------------------------------------
# TypeScript — escopo de arquivo por padrão
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
assert_log "tsc de projeto inteiro NÃO roda por padrão" absent "-p tsconfig.json"
assert_log "eslint roda escopado ao arquivo editado" contains "eslint $TMPDIR_TEST/src/a.ts"
teardown

# ---- opt-in restaura a verificação de projeto inteiro ----
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
# Rust — formato do arquivo por padrão, build da crate só sob opt-in
# ---------------------------------------------------------------------------
setup
shim cargo
shim rustfmt
printf '[package]\nname="x"\n' > "$TMPDIR_TEST/Cargo.toml"
mkdir -p "$TMPDIR_TEST/src"
printf 'fn main() {}\n' > "$TMPDIR_TEST/src/main.rs"
run_hook "src/main.rs"
assert_log "cargo check NÃO roda por padrão" absent "cargo check"
assert_log "rustfmt roda escopado ao arquivo editado" contains "rustfmt --check $TMPDIR_TEST/src/main.rs"
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
# Python — já era escopado ao arquivo; regressão
# ---------------------------------------------------------------------------
setup
shim ruff
printf '[project]\nname="x"\n' > "$TMPDIR_TEST/pyproject.toml"
mkdir -p "$TMPDIR_TEST/src"
printf 'x = 1\n' > "$TMPDIR_TEST/src/a.py"
run_hook "src/a.py"
assert_log "ruff segue escopado ao arquivo editado" contains "ruff check $TMPDIR_TEST/src/a.py"
teardown

# ---------------------------------------------------------------------------
# Sem marcador de projeto, nada roda e o hook sai limpo
# ---------------------------------------------------------------------------
# A promessa do cabeçalho do hook é ser no-op quando a toolchain não é do
# projeto. Sem `go.mod` nenhum comando deve ser montado, mesmo com `go` no PATH.
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
  echo "  PASS  sem go.mod nada roda e o hook sai 0 (advisory, nunca bloqueia)"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  FAIL  sem go.mod o hook saiu $rc e montou: $(tr '\n' '|' < "$ARGV_LOG")"
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
