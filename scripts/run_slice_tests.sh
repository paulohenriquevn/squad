#!/usr/bin/env bash
# Run every skill slice's test suite in ISOLATION.
#
# WHY isolated (one pytest process per slice) instead of a single wide
# `pytest skills/` run:
#   The 31 slices are deliberately import-isolated (package-by-feature). Several
#   slices ship modules with the SAME top-level basename but DIFFERENT content
#   (e.g. check_research_coverage.py, apply_fixes.py, check_reference_citations.py).
#   In production each skill runs alone with only its own scripts/ on sys.path, so
#   these never collide. A single wide pytest process would put multiple slices'
#   scripts/ on one sys.path and `import check_research_coverage` would resolve to
#   whichever slice loaded first — a configuration that never happens in real use.
#   Running each slice in its own process mirrors production and keeps the suite
#   honest. See CHANGELOG (2026-06-20) for the full rationale.
#
# WHY parallel:
#   A isolação que o parágrafo acima defende é POR PROCESSO. Serialidade nunca
#   fez parte dela — era só como estava escrito. Medido 2026-08-26: 100,2 s de
#   relógio para 69,6 s de pytest somado, ou seja ~30 s gastos apenas subindo 18
#   interpretadores, um de cada vez. Cada slice roda no seu próprio processo
#   exatamente como antes; o que mudou é que vários processos existem ao mesmo
#   tempo. A saída é reordenada no fim para continuar determinística.
#
# SLICE_TEST_JOBS=1 volta ao comportamento serial (útil para depurar).
#
# Exit code: 0 only if every slice plus the root suite is green.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1

_detect_jobs() {
    local n
    n=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
    # Teto de 8: acima disso o ganho vira contenção de I/O nos testes que
    # instalam o kit em diretórios temporários.
    [ "$n" -gt 8 ] && n=8
    [ "$n" -lt 1 ] && n=1
    echo "$n"
}
JOBS="${SLICE_TEST_JOBS:-$(_detect_jobs)}"

LOG_DIR="$(mktemp -d)"
trap 'rm -rf "$LOG_DIR"' EXIT

# Ordem fixa: suíte raiz primeiro, depois as slices em ordem de diretório.
SUITES=()
[ -d tests ] && SUITES+=(tests)
for d in skills/*/tests; do
    [ -d "$d" ] && SUITES+=("$d")
done

# ROOT_SUITE_COV=1 mede cobertura NA execução que já existe, em vez de o CI
# rodar a suíte raiz uma segunda vez só para isso — 45 s duplicados por execução,
# medidos em 2026-08-26. O limiar continua sendo cobrado; muda o lugar.
#
# SOBRE O NÚMERO, E SOBRE O QUE ELE NÃO COBRE
# --------------------------------------------
# O kit impõe 80% de piso aos consumidores (`coverage_gate.py`, DEFAULT_MIN_PERCENT)
# e cobrava 40% de si mesmo. A divergência não estava declarada em lugar nenhum, o
# que é a parte ruim: um piso baixo escolhido e escrito é uma decisão; um piso baixo
# que ninguém comparou com o que se exige dos outros é um descuido que se acumula.
#
# Medido 2026-08-26: `scripts/` está em 58,39%. O piso passa a 55 — o valor medido
# com uma margem estreita, o suficiente para travar regressão sem exigir trabalho
# que este commit não fez. A meta continua sendo 80, o mesmo número cobrado do
# consumidor. O que falta para lá está concentrado em três arquivos sem teste
# nenhum: `session-catchup.py`, `validate_skill_frontmatter.py` e
# `test_check_install_drift.py` (0% cada).
#
# O ESCOPO também é estreito e vale dizer: `--cov=scripts` mede `scripts/`, não
# `skills/` nem `hooks/`. As slices de skill rodam com as suas próprias suítes, sem
# piso agregado. Subir o piso sem alargar o escopo mediria melhor um pedaço cada vez
# menor do sistema.
run_suite() {
    local path="$1" log_dir="$2" slot="$3"
    local out="$log_dir/$slot.out"
    local -a extra=()
    if [ "$path" = "tests" ] && [ "${ROOT_SUITE_COV:-0}" = "1" ]; then
        extra=(--cov=scripts --cov-report=term "--cov-fail-under=${ROOT_SUITE_COV_MIN:-55}")
    fi
    if python3 -m pytest -q -p no:cacheprovider --no-header "${extra[@]+"${extra[@]}"}" "$path" > "$out" 2>&1; then
        echo "0" > "$log_dir/$slot.rc"
    else
        echo "1" > "$log_dir/$slot.rc"
    fi
}
export -f run_suite

# `-P $JOBS` com um índice por suíte: o índice é o que permite reconstruir a
# ordem da saída depois, já que a de término é arbitrária.
for i in "${!SUITES[@]}"; do
    printf '%s\t%s\n' "$i" "${SUITES[$i]}"
done | xargs -P "$JOBS" -d '\n' -I{} bash -c '
    IFS=$'"'"'\t'"'"' read -r slot path <<< "{}"
    run_suite "$path" "'"$LOG_DIR"'" "$slot"
'

failures=()
for i in "${!SUITES[@]}"; do
    path="${SUITES[$i]}"
    echo "::group::pytest $path"
    cat "$LOG_DIR/$i.out" 2>/dev/null
    if [ "$(cat "$LOG_DIR/$i.rc" 2>/dev/null)" = "0" ]; then
        echo "PASS  $path"
    else
        echo "FAIL  $path"
        failures+=("$path")
    fi
    echo "::endgroup::"
done

echo
if [ "${#failures[@]}" -eq 0 ]; then
    echo "ALL SUITES GREEN"
    exit 0
fi
echo "FAILED SUITES (${#failures[@]}):"
printf '  - %s\n' "${failures[@]}"
exit 1
