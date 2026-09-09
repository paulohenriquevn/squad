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
#   The isolation the paragraph above defends is PER PROCESS. Seriality was never
#   part of it — it was only how this was written. Measured 2026-08-26: 100.2s of
#   wall clock for 69.6s of summed pytest, i.e. ~30s spent merely starting 18
#   interpreters one at a time. Each slice runs in its own process exactly as
#   before; what changed is that several processes exist at the same time. The
#   output is reordered at the end so it stays deterministic.
#
# SLICE_TEST_JOBS=1 returns to serial behaviour (useful for debugging).
#
# Exit code: 0 only if every slice plus the root suite is green.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT" || exit 1

_detect_jobs() {
    local n
    n=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
    # Ceiling of 8: above that the gain turns into I/O contention in the tests
    # that install the kit into temporary directories.
    [ "$n" -gt 8 ] && n=8
    [ "$n" -lt 1 ] && n=1
    echo "$n"
}
JOBS="${SLICE_TEST_JOBS:-$(_detect_jobs)}"

LOG_DIR="$(mktemp -d)"
trap 'rm -rf "$LOG_DIR"' EXIT

# Fixed order: root suite first, then the slices in directory order.
#
# THE ROOT SUITE IS ALL THREE TESTPATHS, NOT `tests`
# ---------------------------------------------------
# `pyproject.toml` declares testpaths = tests, hooks/tests, squad/tests, and says why
# the last two are there: fourteen stop-validation tests and the whole hook library
# had sat outside the collected set. Passing `tests` alone here suppressed that
# declaration — an explicit path argument always does — so the two paths added to
# close the hole fell straight back out of it.
#
# Measured 2026-09-09: a bare `pytest` collects 1894, `pytest tests` collects 1742,
# and the 152 in between ran in NO CI job, because `ci.yml` runs this script and
# nothing else. The hole was reopened by an optimisation rather than by neglect —
# `ci.yml` records that a second root-suite step was removed on 2026-08-26 to save
# "45s duplicated per run", and that step was the pipeline's only bare `pytest`.
#
# All three go to ONE pytest process, which is what a bare `pytest` already does:
# none of them is under `skills/`, so `conftest.py`'s multi-slice guard does not
# fire, and the coverage extra below keys on one root slot rather than three.
ROOT_SUITE=()
for d in tests hooks/tests squad/tests; do
    [ -d "$d" ] && ROOT_SUITE+=("$d")
done

SUITES=()
[ ${#ROOT_SUITE[@]} -gt 0 ] && SUITES+=("${ROOT_SUITE[*]}")
for d in skills/*/tests; do
    [ -d "$d" ] && SUITES+=("$d")
done

# ROOT_SUITE_COV=1 measures coverage IN the run that already happens, instead of
# CI running the root suite a second time just for that — 45s duplicated per run,
# measured 2026-08-26. The threshold is still enforced; only its place changes.
#
# ABOUT THE NUMBER, AND ABOUT WHAT IT DOES NOT COVER
# ---------------------------------------------------
# The kit imposes an 80% floor on consumers (`coverage_gate.py`,
# DEFAULT_MIN_PERCENT) and demanded 40% of itself. The divergence was declared
# nowhere, which is the bad part: a low floor chosen and written down is a
# decision; a low floor nobody compared against what is demanded of others is an
# oversight that compounds.
#
# Measured 2026-08-26: `scripts/` sits at 58.39%. The floor moves to 55 — the
# measured value with a narrow margin, enough to lock regression without
# demanding work this commit did not do. The target is still 80, the same number
# charged to the consumer. What is missing to get there is concentrated in three
# files with no test at all: `session_catchup.py`,
# `validate_skill_frontmatter.py` and `test_check_install_drift.py` (0% each).
#
# THE SCOPE is narrow too and worth saying: coverage measures `mechanisms/` and
# not `skills/` nor `hooks/`. The skill slices run with their own suites, with no
# aggregate floor. Raising the floor without widening the scope would measure an
# ever smaller piece of the system ever better.
run_suite() {
    local path="$1" log_dir="$2" slot="$3"
    local out="$log_dir/$slot.out"
    local -a extra=()
    # The root slot carries every testpath, space-separated, so it is matched by its
    # FIRST word rather than by equality.
    if [ "${path%% *}" = "tests" ] && [ "${ROOT_SUITE_COV:-0}" = "1" ]; then
        # `--cov=scripts` measured a directory renamed away on 2026-09-02, so the
        # report was 0.00% and the floor failed on every CI run that enabled it —
        # which the CI does, unconditionally. A floor that always fails is worth
        # exactly as much as one that always passes.
        extra=(--cov=mechanisms --cov=squad --cov-report=term
               "--cov-fail-under=${ROOT_SUITE_COV_MIN:-55}")
    fi
    # Unquoted on purpose: the root slot is several paths in one string.
    # shellcheck disable=SC2086
    python3 -m pytest -q -p no:cacheprovider --no-header "${extra[@]+"${extra[@]}"}" $path > "$out" 2>&1
    # The REAL exit code, not a boolean. pytest 5 (nothing collected) and 1 (a real
    # failure) are different facts, and collapsing them left a slice whose tests all
    # vanished reporting FAIL with no hint that the cause was an empty set.
    echo "$?" > "$log_dir/$slot.rc"
}
export -f run_suite

# `-P $JOBS` with one index per suite: the index is what allows the output order
# to be reconstructed afterwards, since completion order is arbitrary.
for i in "${!SUITES[@]}"; do
    printf '%s\t%s\n' "$i" "${SUITES[$i]}"
done | xargs -P "$JOBS" -d '\n' -I{} bash -c '
    IFS=$'"'"'\t'"'"' read -r slot path <<< "{}"
    run_suite "$path" "'"$LOG_DIR"'" "$slot"
'

failures=()
# One machine-readable line per suite, collected while replaying the human output and
# printed together afterwards. `sq test` reads these instead of regexing the `-q`
# summaries, so the count it reports comes from the runner rather than from a guess
# about how pytest phrases things this release.
trailer=()
for i in "${!SUITES[@]}"; do
    path="${SUITES[$i]}"
    out="$LOG_DIR/$i.out"
    rc="$(cat "$LOG_DIR/$i.rc" 2>/dev/null || echo "2")"
    echo "::group::pytest $path"
    cat "$out" 2>/dev/null
    if [ "$rc" = "0" ]; then
        echo "PASS  $path"
    else
        echo "FAIL  $path"
        failures+=("$path")
    fi
    echo "::endgroup::"

    # Absent rather than zero when pytest did not say: a 0 that means "not reported"
    # and a 0 that means "none" are different facts, and summing them silently is how
    # a total becomes fiction.
    passed="$(grep -oE '[0-9]+ passed' "$out" 2>/dev/null | tail -1 | grep -oE '[0-9]+' || true)"
    failed="$(grep -oE '[0-9]+ failed' "$out" 2>/dev/null | tail -1 | grep -oE '[0-9]+' || true)"
    collected="$(grep -oE 'collected [0-9]+' "$out" 2>/dev/null | tail -1 | grep -oE '[0-9]+' || true)"
    trailer+=("$(printf 'SUITE\t%s\t%s\t%s\t%s\t%s' \
        "$path" "$rc" "${passed:--}" "${failed:--}" "${collected:--}")")
done

echo
printf '%s\n' "${trailer[@]}"
echo
if [ "${#failures[@]}" -eq 0 ]; then
    echo "ALL SUITES GREEN"
    exit 0
fi
echo "FAILED SUITES (${#failures[@]}):"
printf '  - %s\n' "${failures[@]}"
exit 1
