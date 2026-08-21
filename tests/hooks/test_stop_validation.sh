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

# ---- Comment-only change to source => exit 0 (colhido do theokit-tui) ----
# Uma mudança só de comentário não tem NADA a anunciar a um consumidor, e a Regra 6 manda
# escrever para o consumidor. Exigir entrada por ela convida aos dois piores desfechos: uma
# linha fabricada poluindo o contrato público, ou o override — e recorrer ao override para
# satisfazer uma pergunta que o gate não devia ter feito é como um gate deixa de ser lido.
setup
printf 'print("hello")\n' > "$TMPDIR_TEST/app.py"
printf '# Changelog\n\n## [Unreleased]\n### Added\n- app.py\n' > "$TMPDIR_TEST/CHANGELOG.md"
git -C "$TMPDIR_TEST" add app.py CHANGELOG.md
git -C "$TMPDIR_TEST" commit -m "base" --quiet
printf '# explica o porque\nprint("hello")\n' > "$TMPDIR_TEST/app.py"
git -C "$TMPDIR_TEST" add app.py
git -C "$TMPDIR_TEST" commit -m "comment only" --quiet
rc=$(run_hook)
assert_exit "comment-only change without CHANGELOG => exit 0" 0 "$rc"
teardown

# ---- Code change disguised among comments => exit 2 (conservador por construção) ----
# O teste tira apenas linhas inequivocamente comentário ou branco, então QUALQUER linha
# alterada carregando código deixa o arquivo em CODE_CHANGED. Falso negativo sobre mudança
# real é impossível; falso positivo é apenas inconveniente. A assimetria é deliberada.
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
# Projeto SEM CHANGELOG.md — o gate não pode sumir em silêncio
# ---------------------------------------------------------------------------
# `if [ -f "CHANGELOG.md" ]` desativava a Regra 6 inteira quando o arquivo não
# existia. Um projeto adotante que nunca o criou nunca descobria que o kit
# esperava um: disciplina prometida na documentação, ausente na prática.
#
# ADVISORY e não BLOCKER — criar o arquivo é decisão do consumidor, e travar
# toda sessão de um repo recém-adotado faria da instalação uma parede. O que o
# teste exige é que o silêncio acabe, não que a sessão pare.

run_hook_capture() {
  (cd "$TMPDIR_TEST" && bash "$HOOK") 2>&1 || true
}

# ---- código muda, sem CHANGELOG.md => avisa, mas não bloqueia ----
setup
rm -f "$TMPDIR_TEST/CHANGELOG.md"
git -C "$TMPDIR_TEST" rm -q --cached CHANGELOG.md >/dev/null 2>&1 || true
echo "package main" > "$TMPDIR_TEST/app.go"
git -C "$TMPDIR_TEST" add app.go >/dev/null 2>&1
rc=$(run_hook)
assert_exit "sem CHANGELOG.md: mudança de código NÃO bloqueia" 0 "$rc"
out=$(run_hook_capture)
TOTAL=$((TOTAL + 1))
if echo "$out" | grep -q "No CHANGELOG.md in this project"; then
  echo "  PASS  sem CHANGELOG.md: emite advisory nomeando o gap"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  FAIL  sem CHANGELOG.md: advisory ausente (o gate sumiu em silêncio)"
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi
teardown

# ---- sem CHANGELOG.md e sem mudança de código => silêncio é correto ----
setup
rm -f "$TMPDIR_TEST/CHANGELOG.md"
git -C "$TMPDIR_TEST" rm -q --cached CHANGELOG.md >/dev/null 2>&1 || true
echo "# doc" > "$TMPDIR_TEST/NOTES.md"
git -C "$TMPDIR_TEST" add NOTES.md >/dev/null 2>&1
out=$(run_hook_capture)
TOTAL=$((TOTAL + 1))
if echo "$out" | grep -q "No CHANGELOG.md in this project"; then
  echo "  FAIL  sem código mudado: advisory não deveria disparar (ruído)"
  FAIL_COUNT=$((FAIL_COUNT + 1))
else
  echo "  PASS  sem código mudado: nenhum advisory (silêncio correto)"
  PASS_COUNT=$((PASS_COUNT + 1))
fi
teardown

# ---------------------------------------------------------------------------
# O kit instalado sob .claude/ é dependência, não fonte do consumidor
# ---------------------------------------------------------------------------
# Medido num projeto adotante recém-instalado: a primeira sessão emitia 107
# linhas de aviso sobre arquivos DO KIT (`.claude/skills/**/*.py`) contra UM
# achado real no código do usuário. Auditar a própria dependência é o jeito
# canônico de ensinar alguém a ignorar o gate.
#
# O filtro é `^\.claude/`, e vale nos dois layouts sem precisar detectar qual:
# em plugin-install o kit mora em `.claude/` e é excluído; em standalone o
# repositório do kit tem os arquivos em `skills/`, que seguem auditados.

# ---- arquivo do kit sob .claude/ não gera aviso ----
setup
rm -f "$TMPDIR_TEST/CHANGELOG.md"
git -C "$TMPDIR_TEST" rm -q --cached CHANGELOG.md >/dev/null 2>&1 || true
mkdir -p "$TMPDIR_TEST/.claude/skills/foo/scripts"
echo "def f(): pass" > "$TMPDIR_TEST/.claude/skills/foo/scripts/thing.py"
git -C "$TMPDIR_TEST" add -A >/dev/null 2>&1
out=$(run_hook_capture)
TOTAL=$((TOTAL + 1))
if echo "$out" | grep -q '\.claude/'; then
  echo "  FAIL  arquivo do kit sob .claude/ apareceu num aviso (audita a dependência)"
  FAIL_COUNT=$((FAIL_COUNT + 1))
else
  echo "  PASS  arquivo do kit sob .claude/ não gera aviso"
  PASS_COUNT=$((PASS_COUNT + 1))
fi
teardown

# ---- regressão: código do usuário FORA de .claude/ segue auditado ----
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
  echo "  PASS  regressão: código do usuário fora de .claude/ segue auditado"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  FAIL  regressão: o filtro cegou o gate para o código do usuário"
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
