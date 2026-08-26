#!/bin/bash
# Stop hook: end-of-session sanity checks (agnostic).
#
# Behavior:
#   1. TDD gate (warn-first): for every changed production source file, warn
#      if no test is detected beside it OR in the owning package's test tree
#      (heuristic; supports common *_test.* / *.test.* / *.spec.* / test_*.*).
#   2. CHANGELOG discipline (HARD GATE — Inquebrável Rule 6 + cycle-review BLOCKER):
#      if production source changed and neither a CHANGELOG.md (root or package)
#      nor a .changeset/*.md entry did, BLOCK.
#   3. Secret leak (HARD GATE — cycle-review BLOCKER): if newly tracked files
#      match secret patterns (.env / credentials* / *.pem / *.key), BLOCK.
#   4. Pre-release honesty (warn-first): if README.md was modified, scan for
#      unverified production-ready / SLA claims.
#
# Hard gates align with rules/cycle-review.md § Hard gates (BLOCKER-level).
# Warn-first items are advisory — output is fed to Claude as context.
#
# Exit codes:
#   0 — clean OR only advisory warnings emitted
#   2 — hard-gate violation (CHANGELOG missing or secrets committed)
#
# Override: setting STOP_VALIDATION_WARN_ONLY=1 reverts every gate to warn-first
# (escape hatch for legitimate bulk reorgs; document the rationale in CHANGELOG).

set -uo pipefail

# shellcheck source=lib/detect-layout.sh
source "$(dirname "$0")/lib/detect-layout.sh"

# ----------------------------------------------------------------------------
# Collect ALL modified files
# (unstaged + staged + untracked-but-not-ignored + the last commit when unpushed)
# ----------------------------------------------------------------------------
UNSTAGED=$(git diff --name-only 2>/dev/null || true)
STAGED=$(git diff --cached --name-only 2>/dev/null || true)

# New files nobody staged yet. `git diff` reports tracked modifications only, so
# without this a brand-new file is invisible to every gate below — and the two
# artifacts these gates most want to see are always new: a .changeset entry, and
# a test file for source that never had one. --exclude-standard honours
# .gitignore, so build output and local scratch stay out.
UNTRACKED=$(git ls-files --others --exclude-standard 2>/dev/null || true)

# --- Defect 1: an already-published commit is not this session's work ---------
# The last commit counts only when it has NOT reached the upstream yet.
#
# It is in the set at all because a session that commits and then stops leaves
# nothing in the working tree — dropping it entirely would let exactly that
# session skip the gate. But a commit already on the remote was graded when it
# was made, and re-grading it means a session that changed nothing inherits its
# verdict: a read-only session then cannot end without either fabricating a
# CHANGELOG entry or reaching for STOP_VALIDATION_WARN_ONLY=1, and an override
# used to answer a question the gate should not have asked is how a gate stops
# being read. Measured on `theokit` 2026-08-26: a session that wrote nothing
# blocked nine times on the previous commit's `.ts` file.
#
# No upstream means no way to tell published from local, so stay strict.
LAST_COMMIT=""
if git rev-parse --abbrev-ref '@{upstream}' >/dev/null 2>&1; then
  AHEAD=$(git rev-list --count '@{upstream}..HEAD' 2>/dev/null || echo 0)
  if [ "${AHEAD:-0}" -gt 0 ]; then
    LAST_COMMIT=$(git diff --name-only HEAD~1..HEAD 2>/dev/null || true)
  fi
else
  LAST_COMMIT=$(git diff --name-only HEAD~1..HEAD 2>/dev/null || true)
fi

# `.claude/` é o kit INSTALADO — dependência do projeto, não fonte dele.
# Medido num adotante recém-instalado: a primeira sessão emitia 107 linhas de
# aviso sobre `.claude/skills/**/*.py` contra UM achado real no código do
# usuário. Auditar a própria dependência é o jeito canônico de ensinar alguém a
# ignorar o gate — e um gate ignorado não protege nada.
#
# O filtro serve os dois layouts sem precisar distinguir qual: em plugin-install
# o kit vive sob `.claude/` e sai; em standalone o repositório do kit tem seus
# arquivos em `skills/`, `hooks/`, `scripts/`, que seguem auditados normalmente.
ALL_FILES=$(echo -e "${UNSTAGED}\n${STAGED}\n${UNTRACKED}\n${LAST_COMMIT}" \
  | sort -u \
  | grep -v '^$' \
  | grep -v '^\.claude/' \
  || true)

WARNINGS=()
BLOCKERS=()

# ----------------------------------------------------------------------------
# Reference leakage (third layer of the provenance guard) — evaluated BEFORE the
# no-diff early exit on purpose. Layers 1 and 2 live in validate-command.sh and
# block copying content OUT of the study zone and citing its paths in commit
# messages; neither sees a manual paste. This checks the RESULT: a block of
# consecutive lines shared between the project and the zone.
# It must run even when the session produced only UNTRACKED files — `git diff`
# does not list those, so the early exit below would skip the check exactly in
# the "pasted a brand-new file" case, which is the likeliest way a copy lands.
# Advisory by design: exact-shingle matching is strong evidence, not proof, and a
# false BLOCK would be worse than a WARN. SKIPs when the zone is absent.
# ----------------------------------------------------------------------------
LEAK_SCRIPT="$PROJECT_DIR/scripts/check_reference_leakage.py"
if [ -f "$LEAK_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
  LEAK_OUT=$(python3 "$LEAK_SCRIPT" --repo "$PROJECT_DIR" --strict 2>&1 || true)
  if echo "$LEAK_OUT" | grep -q "SUSPECTED COPY"; then
    msg="Suspected literal copy of third-party study material (provenance risk). Review each match; if legitimate, record source + licence in CHANGELOG.md:"
    while IFS= read -r line; do
      case "$line" in
        *"shares"*"consecutive lines with"*) msg+="\n    -${line}" ;;
      esac
    done <<< "$LEAK_OUT"
    WARNINGS+=("$msg")
  fi
fi

if [ -z "$ALL_FILES" ] && [ ${#WARNINGS[@]} -eq 0 ]; then
  exit 0
fi

# Escape hatch
WARN_ONLY="${STOP_VALIDATION_WARN_ONLY:-0}"

# ----------------------------------------------------------------------------
# 1. TDD gate (warn-first) — heuristic test pairing
# ----------------------------------------------------------------------------
# Recognized source extensions: .go .py .ts .tsx .js .jsx .rs .java .kt .rb .cs
# Recognized test-name patterns in the same directory:
#   <name>_test.<ext>          (Go, Python, etc.)
#   <name>.test.<ext>          (TS/JS Jest convention)
#   <name>.spec.<ext>          (TS/JS Jasmine/RSpec)
#   test_<name>.<ext>          (Python pytest)
# Falls back to "ANY test file in the same directory" (idiomatic in some langs).
# Skips generated/doc files and obvious vendored/third-party trees.
SRC_CHANGED=$(echo "$ALL_FILES" \
  | grep -E '\.(go|py|ts|tsx|js|jsx|rs|java|kt|rb|cs)$' \
  | grep -vE '(^|/)(node_modules|vendor|dist|build|target|\.venv|__pycache__|\.next|\.nuxt)/' \
  | grep -vE '(_test|\.test|\.spec)\.[a-z]+$' \
  | grep -vE '(^|/)test_[^/]+\.[a-z]+$' \
  | grep -vE '(^|/)zz_generated[^/]*\.go$' \
  | grep -vE '(^|/)doc\.go$' \
  || true)

if [ -n "$SRC_CHANGED" ]; then
  MISSING_TESTS=()
  while IFS= read -r src_file; do
    [ -z "$src_file" ] && continue

    pkg_dir=$(dirname "$src_file")
    base_no_ext="${src_file##*/}"
    base_no_ext="${base_no_ext%.*}"
    ext="${src_file##*.}"

    # Candidate file names in same directory
    if [ -f "${pkg_dir}/${base_no_ext}_test.${ext}" ] || \
       [ -f "${pkg_dir}/${base_no_ext}.test.${ext}" ] || \
       [ -f "${pkg_dir}/${base_no_ext}.spec.${ext}" ] || \
       [ -f "${pkg_dir}/test_${base_no_ext}.${ext}" ]; then
      continue
    fi

    # Fallback: ANY test-named file in the same package directory
    found=$(find "$pkg_dir" -maxdepth 1 \( \
        -name "*_test.${ext}" -o -name "*.test.${ext}" -o -name "*.spec.${ext}" -o -name "test_*.${ext}" \
      \) -print -quit 2>/dev/null || true)
    if [ -n "$found" ]; then
      continue
    fi

    # Fallback: a test named after this file, anywhere in the OWNING unit's test
    # tree. Sibling-only lookup assumes tests sit next to the source, which is
    # idiomatic in Go and false for most of the JS/TS and Python world — the
    # adopters this kit serves keep them in packages/<p>/tests/unit/ and
    # tests/unit/. Reporting those files as untested is the noise that gets a
    # warn-first gate ignored, and a warn nobody reads protects nothing.
    #
    # The owning unit is the nearest ancestor holding a manifest, so the search
    # stays inside one package instead of scanning a whole monorepo. Bounded by
    # -maxdepth, and prunes the usual heavy trees, to keep the hook fast.
    #
    # LIMIT, stated rather than hidden: this matches on the SOURCE FILE'S NAME.
    # A test named for the behaviour it protects — which rules/testing.md § 3
    # actually asks for — will not be found, and the file is reported. Widening
    # this to grep for the module inside test bodies would trade a false warn for
    # a false silence, which is the worse of the two.
    unit_dir="$pkg_dir"
    while [ "$unit_dir" != "." ] && [ "$unit_dir" != "/" ]; do
      if [ -f "${unit_dir}/package.json" ] || [ -f "${unit_dir}/go.mod" ] || \
         [ -f "${unit_dir}/pyproject.toml" ] || [ -f "${unit_dir}/Cargo.toml" ]; then
        break
      fi
      unit_dir=$(dirname "$unit_dir")
    done

    if [ -d "$unit_dir" ]; then
      found=$(find "$unit_dir" -maxdepth 6 \
          \( -name node_modules -o -name dist -o -name build -o -name target \) -prune -o \
          \( -name "${base_no_ext}_test.${ext}" -o -name "${base_no_ext}.test.${ext}" \
             -o -name "${base_no_ext}.spec.${ext}" -o -name "test_${base_no_ext}.${ext}" \
             -o -name "${base_no_ext}.test.tsx" -o -name "${base_no_ext}.spec.tsx" \
          \) -print -quit 2>/dev/null || true)
      if [ -n "$found" ]; then
        continue
      fi
    fi

    MISSING_TESTS+=("$src_file")
  done <<< "$SRC_CHANGED"

  if [ ${#MISSING_TESTS[@]} -gt 0 ]; then
    msg="TDD gate (warn-first) — Inquebrável Rule 7: the following production source files have no sibling test file detected:"
    for f in "${MISSING_TESTS[@]}"; do
      msg+="\n    - $f"
    done
    msg+="\n  See $ECO/rules/testing.md for the project's test pairing convention."
    WARNINGS+=("$msg")
  fi
fi

# ----------------------------------------------------------------------------
# 2. CHANGELOG discipline (HARD GATE — Inquebrável Rule 6 + cycle-review BLOCKER)
# ----------------------------------------------------------------------------
if [ -f "CHANGELOG.md" ]; then
  CODE_CHANGED=$(echo "$ALL_FILES" \
    | grep -E '\.(go|py|ts|tsx|js|jsx|rs|java|kt|rb|cs)$' \
    | grep -vE '(_test|\.test|\.spec)\.[a-z]+$' \
    | grep -vE '(^|/)(tests?|spec|__tests__|testdata|fixtures)/' \
    | grep -vE '(^|/)[a-z0-9.-]+\.config\.[a-z]+$' \
    | grep -vE '(^|/)(node_modules|vendor|dist|build|target|\.venv|__pycache__)/' \
    || true)

  # Colhido do `theokit-tui`, onde esta correção viveu semanas dentro de um `.claude/`
  # gitignored (2026-08-20). Uma mudança SÓ de comentário não tem NADA a anunciar a um
  # consumidor, e a Regra 6 manda escrever para o consumidor. Exigir entrada por ela
  # convida aos dois piores desfechos: uma linha fabricada poluindo o contrato público,
  # ou o override — e recorrer ao override para satisfazer uma pergunta que o gate não
  # devia ter feito é como um gate deixa de ser lido.
  #
  # CONSERVADOR POR CONSTRUÇÃO, e esse é o desenho inteiro: só remove linhas que são
  # inequivocamente comentário ou branco, então QUALQUER linha alterada carregando código
  # deixa o arquivo em `CODE_CHANGED`. Falso negativo sobre mudança real é impossível
  # ENQUANTO o diff lido for o certo — corrigido 2026-08-26, quando não era;
  # falso positivo (um commit de docs ainda pedir entrada) é apenas inconveniente. A
  # assimetria é deliberada — a falha que este gate existe para impedir é uma mudança de
  # comportamento silenciosa, não um commit de documentação barulhento.
  #
  # `scripts/` NÃO entra na lista de exclusão acima, embora entre na do `theokit-tui`:
  # lá é ferramental de build, e aqui é produção — o kit é feito de scripts.
  if [ -n "$CODE_CHANGED" ]; then
    SUBSTANTIVE=""
    while IFS= read -r f; do
      [ -z "$f" ] && continue
      [ -f "$f" ] || { SUBSTANTIVE="$SUBSTANTIVE$f"$'\n'; continue; }
      # Which diff to read depends on how the file reached the set, and getting
      # this wrong inverts the filter's safety direction.
      #
      # `git diff HEAD~1 -- <path>` is empty for a file with no prior version —
      # a new module, an untracked file, a repo one commit deep — which reads
      # EXACTLY like "the diff carried only comments". Treating the two alike
      # let an entire new file skip the gate; measured 2026-08-26, a fresh
      # `src/payments.ts` with four lines of real code exited 0.
      #
      # So: prefer the working-tree diff against HEAD, fall back to the last
      # commit's, and when the file is new read its whole content — every line
      # of a new file IS the change. An unobtainable diff now counts as
      # substantive rather than as silence, which is the conservative direction
      # this filter was always documented to take.
      raw=$(git diff HEAD -- "$f" 2>/dev/null || true)
      [ -z "$raw" ] && raw=$(git diff HEAD~1 -- "$f" 2>/dev/null || true)
      if [ -z "$raw" ]; then
        raw=$(sed -E 's/^/+/' "$f" 2>/dev/null || true)
      fi
      body=$(echo "$raw" | grep -E '^[+-]' | grep -vE '^(\+\+\+|---)' \
        | sed -E 's/^[+-]//' | sed -E 's,^[[:space:]]*(//|\*|/\*|\*/|#).*$,,' \
        | grep -vE '^[[:space:]]*$' || true)
      [ -n "$body" ] && SUBSTANTIVE="$SUBSTANTIVE$f"$'\n'
    done <<< "$CODE_CHANGED"
    CODE_CHANGED=$(echo "$SUBSTANTIVE" | grep -v '^$' || true)
  fi

  # --- Defect 2: the root CHANGELOG.md is not the only form of the record ----
  # A monorepo publishing several packages records per-package changes in that
  # package's own CHANGELOG.md, or in a .changeset/*.md entry, which is what
  # BECOMES that changelog at version time. Accepting only the root file reports
  # "undocumented" over work that is documented — measured on `theokit`, whose
  # six packages all publish through .changeset/ and whose root file says so.
  #
  # .changeset/README.md and config.json ship with the tool and record nothing.
  CHANGELOG_TOUCHED=$(echo "$ALL_FILES" \
    | grep -E '(^|/)CHANGELOG\.md$|^\.changeset/[^/]+\.md$' \
    | grep -vE '^\.changeset/README\.md$' \
    || true)
  if [ -n "$CODE_CHANGED" ] && [ -z "$CHANGELOG_TOUCHED" ]; then
    msg="CHANGELOG.md not updated despite production source changes (Inquebrável Rule 6; cycle-review BLOCKER). Add an entry to [Unreleased] before stopping. Override with STOP_VALIDATION_WARN_ONLY=1 only when the change is a bulk reorg with the rationale documented separately."
    if [ "$WARN_ONLY" = "1" ]; then
      WARNINGS+=("$msg")
    else
      BLOCKERS+=("$msg")
    fi
  fi
else
  # Sem CHANGELOG.md o gate inteiro sumia em silêncio. Um projeto adotante que
  # nunca criou o arquivo nunca descobria que o kit esperava um — a disciplina
  # da Regra 6 era prometida na documentação e não existia na prática, que é o
  # mesmo formato de falha do trunk `master` (promete e não entrega, calado).
  #
  # ADVISORY, não BLOCKER, e a distinção é deliberada: criar o arquivo é decisão
  # do consumidor, e bloquear toda sessão de um repo recém-adotado até que ele
  # exista transformaria a primeira instalação numa parede. Avisar uma vez por
  # sessão em que código mudou é o suficiente para deixar de ser silêncio.
  CODE_CHANGED_NO_LOG=$(echo "$ALL_FILES" \
    | grep -E '\.(go|py|ts|tsx|js|jsx|rs|java|kt|rb|cs)$' \
    | grep -vE '(_test|\.test|\.spec)\.[a-z]+$' \
    | grep -vE '(^|/)(tests?|spec|__tests__|testdata|fixtures)/' \
    | grep -vE '(^|/)(node_modules|vendor|dist|build|target|\.venv|__pycache__)/' \
    || true)
  if [ -n "$CODE_CHANGED_NO_LOG" ]; then
    WARNINGS+=("No CHANGELOG.md in this project, so the Rule 6 gate cannot run — production source changed and nothing recorded it. Create CHANGELOG.md with an [Unreleased] section (Keep a Changelog format) to activate the gate, or leave it absent deliberately if this repo does not ship to consumers.")
  fi
fi

# ----------------------------------------------------------------------------
# 2b. Secret leak (HARD GATE — cycle-review BLOCKER)
# ----------------------------------------------------------------------------
SECRET_HITS=$(echo "$ALL_FILES" \
  | grep -E '(^|/)(\.env(\.[a-z0-9_-]+)?|credentials([._-][a-z0-9]+)?|[a-z0-9_-]*secret[s]?(\.[a-z0-9_-]+)?\.(ya?ml|json|env|txt))$|\.(pem|key|p12|pfx|jks)$' \
  || true)
if [ -n "$SECRET_HITS" ]; then
  msg="Secret-pattern files appear in this session's diff (cycle-review BLOCKER). Verify they are intentionally NOT secrets, or remove them before stopping:"
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    msg+="\n    - $f"
  done <<< "$SECRET_HITS"
  if [ "$WARN_ONLY" = "1" ]; then
    WARNINGS+=("$msg")
  else
    BLOCKERS+=("$msg")
  fi
fi

# ----------------------------------------------------------------------------
# 3. README.md production claims
# ----------------------------------------------------------------------------
if echo "$ALL_FILES" | grep -qE '(^|/)README\.md$'; then
  README_DIFF=$(git diff -- '*README.md' 2>/dev/null || true)
  if echo "$README_DIFF" | grep -qiE '^\+.*\bproduction[[:space:]]?-?[[:space:]]?(ready|grade)\b'; then
    WARNINGS+=("README.md introduces a 'production-ready' claim. Until v1.0 with measured evidence, prefer 'designed for' or 'targeted at' framings ($ECO/rules/public-copy.md).")
  fi
  if echo "$README_DIFF" | grep -qiE '^\+.*\b(99\.9|99\.95|99\.99)[[:space:]]?%[[:space:]]?(uptime|sla)'; then
    WARNINGS+=("README.md introduces a specific SLA/uptime number. Per the honesty rule, specific SLAs require sustained production measurement. Remove or qualify with 'target SLO' / 'designed to support'.")
  fi
fi

# ----------------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------------
if [ ${#BLOCKERS[@]} -gt 0 ]; then
  echo "============================================" >&2
  echo "  STOP VALIDATION — HARD-GATE VIOLATION" >&2
  echo "============================================" >&2
  echo "" >&2
  for b in "${BLOCKERS[@]}"; do
    echo -e "  [BLOCK] $b" >&2
    echo "" >&2
  done
  echo "--------------------------------------------" >&2
  echo "Resolve every BLOCK above before stopping. To override for a documented reason, re-run with STOP_VALIDATION_WARN_ONLY=1." >&2
fi

if [ ${#WARNINGS[@]} -gt 0 ]; then
  echo "============================================"
  echo "  STOP VALIDATION — ADVISORY WARNINGS"
  echo "============================================"
  echo ""
  for w in "${WARNINGS[@]}"; do
    echo -e "  [WARN] $w"
    echo ""
  done
  echo "--------------------------------------------"
  echo "These are advisory (warn-first). Address them or document why they are intentional before considering the session complete."
fi

if [ ${#BLOCKERS[@]} -gt 0 ]; then
  exit 2
fi

exit 0
