#!/bin/bash
# Attest a plan file — compute SHA256, write to .attestations/{slug}.sha256
#
# Adapted from planning-with-files v2.43.0 attest_plan.sh. Provides tamper
# detection for plan files: the next UserPromptSubmit hook reads the stored
# hash and compares against the live file. Mismatch → injection blocked +
# tamper warning to the agent.
#
# WHERE IT WRITES, AND WHY IT NO LONGER DECIDES THAT ITSELF
#
# The ecosystem is resolved by `squad.layout`, the same module the three hooks
# that CONSUME the attestation resolve through (`squad/plan.py`). One definition,
# because the writer and the reader must agree or the guarantee is not there.
#
# It used to probe for `skills/+rules/+hooks/` under `.`, `.claude/` and
# `.claude/plugins/cycle/` — a path named after the ancestor project — and fall
# back to `.`. In the plugin-native layout the kit lives OUTSIDE the project, so
# none of the three matched, the fallback fired, and this script operated on
# `<project>/records/plans/` and `<project>/.attestations/` while the hooks read
# `<project>/.claude/`. Measured 2026-09-08 (#36): with the plan where
# `rules/records-location.md` mandates it, `/plan-attest` exited 1 with "plan file
# not found"; with the plan at the root, an attestation was written that no hook
# would ever open, and `Attestation.tampered` is False when there is nothing to
# compare against — so an edited plan was injected every turn, silently.
#
# A layout that does not resolve is now an error. The old fallback wrote into a
# directory no reader consults, and `--verify` then reported OK about it.
#
# Workflow:
#   1. After editing a plan file, run: bash mechanisms/cycle/attest_plan.sh {slug}
#   2. This writes .attestations/{slug}.sha256 atomically (temp + rename).
#   3. Subsequent prompts validate against this stored hash.
#   4. If the plan is edited again without re-attesting, hooks block injection.
#
# Usage:
#   bash mechanisms/cycle/attest_plan.sh {slug}             # attest plan file by slug
#   bash mechanisms/cycle/attest_plan.sh --all              # attest all plans in plans/
#   bash mechanisms/cycle/attest_plan.sh --verify {slug}    # verify (read-only) without re-writing
#   bash mechanisms/cycle/attest_plan.sh --verify-all       # verify EVERY plan; exits non-zero
#                                                          # if any attestation is stale

set -eu

# The kit's own root, resolved BEFORE the `cd` below. `BASH_SOURCE[0]` is RELATIVE when
# the script is invoked by a relative path, so resolving it after changing directory
# makes the subshell `cd` fail and leaves KIT_ROOT EMPTY — measured 2026-09-16 with
# `CLAUDE_PROJECT_DIR` pointing elsewhere, which is the hook environment.
#
# Only used to put `squad` on the import path — never to decide where DATA goes.
KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$PROJECT_DIR" || exit 1

# One resolver, shared with the hooks that read what this writes.
ECOSYSTEM_DIR="$(PYTHONPATH="$KIT_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
from squad.layout import resolve
layout = resolve()
print(layout.eco if layout else "")
' || true)"

if [ -z "$ECOSYSTEM_DIR" ]; then
  echo "ERROR: no Squad layout resolves from $PROJECT_DIR." >&2
  echo "  The attestation has to land where the hooks read it, and that is" >&2
  echo "  decided by squad/layout.py. Refusing rather than writing somewhere" >&2
  echo "  nothing will look — an attestation nobody reads verifies nothing." >&2
  exit 1
fi
ATTEST_REL="$(python3 -c "import sys; sys.path.insert(0, '$KIT_ROOT'); from squad.paths import DATA_DIRNAME, ATTESTATIONS; print(f'{DATA_DIRNAME}/{ATTESTATIONS}')" 2>/dev/null)"
[ -n "$ATTEST_REL" ] || { echo "FATAL: cannot read the attestation root from squad/paths.py" >&2; exit 2; }
ATTEST_DIR="${PROJECT_DIR}/${ATTEST_REL}"
# The write root hangs off the PROJECT, never off the ecosystem directory: joining it
# to $ECOSYSTEM_DIR would produce `.claude/.squad/records/` and hide every plan from the
# hooks that read them. Shell cannot import the owner, so it asks it.
PROJECT_DIR="$ECOSYSTEM_DIR"
case "$ECOSYSTEM_DIR" in */.claude) PROJECT_DIR="$(dirname "$ECOSYSTEM_DIR")" ;; esac
# KIT_ROOT is already resolved at the top, before any `cd`. Re-deriving it here is what
# broke the slice runner's tree banner the same day: two correct expressions and a wrong
# order, with no line a reviewer could point at. A value a script already holds must not
# be computed again — that is a property a reader can check, unlike order.
DATA_REL="$(python3 -c "import sys; sys.path.insert(0, '$KIT_ROOT'); from squad.paths import DATA_DIRNAME, RECORDS; print(f'{DATA_DIRNAME}/{RECORDS}')" 2>/dev/null)"
[ -n "$DATA_REL" ] || { echo "FATAL: cannot read the write root from squad/paths.py" >&2; exit 2; }
PLANS_DIR="${PROJECT_DIR}/${DATA_REL}/plans"

mkdir -p "$ATTEST_DIR"

sha256_of() {
  local file="$1"
  (sha256sum "$file" 2>/dev/null || shasum -a 256 "$file" 2>/dev/null) | awk '{print $1}'
}

attest_one() {
  local slug="$1"
  local plan_file="${PLANS_DIR}/${slug}-plan.md"
  if [ ! -f "$plan_file" ]; then
    echo "ERROR: plan file not found: $plan_file" >&2
    return 1
  fi
  local hash
  hash=$(sha256_of "$plan_file")
  if [ -z "$hash" ]; then
    echo "ERROR: failed to compute sha256 for $plan_file" >&2
    return 1
  fi
  local out="${ATTEST_DIR}/${slug}.sha256"
  local tmp="${out}.tmp.$$"
  printf '%s' "$hash" > "$tmp"
  mv "$tmp" "$out"
  echo "attested: $slug -> $hash"
}

verify_one() {
  local slug="$1"
  local plan_file="${PLANS_DIR}/${slug}-plan.md"
  local attest_file="${ATTEST_DIR}/${slug}.sha256"
  if [ ! -f "$plan_file" ]; then
    echo "MISSING-PLAN: $plan_file"
    return 2
  fi
  if [ ! -f "$attest_file" ]; then
    echo "NO-ATTESTATION: $slug (run 'bash $0 $slug' to attest)"
    return 3
  fi
  local stored
  stored=$(tr -d '\r\n[:space:]' < "$attest_file")
  local actual
  actual=$(sha256_of "$plan_file")
  if [ "$stored" = "$actual" ]; then
    echo "OK: $slug ($actual)"
    return 0
  else
    echo "TAMPERED: $slug"
    echo "  expected: $stored"
    echo "  actual:   $actual"
    return 4
  fi
}

if [ $# -eq 0 ]; then
  echo "Usage: $0 {slug} | --all | --verify {slug} | --verify-all" >&2
  exit 1
fi

case "$1" in
  --all)
    for f in "${PLANS_DIR}"/*-plan.md; do
      [ -f "$f" ] || continue
      slug=$(basename "$f" -plan.md)
      attest_one "$slug"
    done
    ;;
  --verify)
    if [ -z "${2:-}" ]; then
      echo "Usage: $0 --verify {slug}" >&2
      exit 1
    fi
    verify_one "$2"
    ;;
  --verify-all)
    rc=0
    for f in "${PLANS_DIR}"/*-plan.md; do
      [ -f "$f" ] || continue
      slug=$(basename "$f" -plan.md)
      verify_one "$slug" || rc=$?
    done
    exit "$rc"
    ;;
  *)
    attest_one "$1"
    ;;
esac

exit 0
