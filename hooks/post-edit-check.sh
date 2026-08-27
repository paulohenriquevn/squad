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
# TUDO AQUI É ESCOPADO AO ARQUIVO EDITADO, E ISSO É O DESENHO
# -----------------------------------------------------------
# Este hook roda de forma SÍNCRONA em toda edição: o agente espera por ele, e
# não há debounce — dez edições seguidas são dez execuções. Até 2026-08-26 três
# dos quatro caminhos verificavam o PROJETO INTEIRO: `tsc --noEmit -p
# tsconfig.json` (inclusive ao editar um `.js`), `cargo check` (crate inteira) e
# `go vet <dir>/...` (o módulo inteiro quando o arquivo editado está na raiz).
# Com timeout de 60 s, o desfecho num repositório de porte médio era um dos dois
# piores: o turno travava por dezenas de segundos, ou o hook morria no meio e o
# feedback que ele existe para dar nunca chegava.
#
# O que se perde é real e vale dizer em voz alta: `tsc` por arquivo não é
# equivalente a `tsc` de projeto — um erro de tipo que atravessa módulos não
# aparece mais aqui. Ele continua sendo pego pela suíte e pelo CI, que é onde
# uma verificação dessa escala cabe. Para quem prefere pagar o custo por edição,
# POST_EDIT_FULL_TYPECHECK=1 restaura `tsc -p` e `cargo check` — agora escopado
# à crate dona do arquivo, nunca ao workspace inteiro.

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

# Opt-in para as verificações de escala de projeto (ver cabeçalho).
FULL_TYPECHECK="${POST_EDIT_FULL_TYPECHECK:-0}"

# Manifesto da crate dona do arquivo — o ancestral mais próximo com Cargo.toml.
# Só é consultado no caminho Rust; resolvê-lo aqui mantém o `case` legível.
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
      # O PACOTE do arquivo, sem `/...`: a forma recursiva vira o módulo inteiro
      # sempre que o arquivo editado está na raiz, que é o caso de `main.go`.
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
        # A crate DONA do arquivo, não o workspace: `--manifest-path` é o que
        # limita um `cargo check` num workspace com dezenas de membros.
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
