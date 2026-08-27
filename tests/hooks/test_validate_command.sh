#!/bin/bash
# Tests for hooks/validate-command.sh
# Verifies that dangerous git commands are blocked and safe ones are allowed.
#
# Each test pipes JSON (matching the PreToolUse Bash schema) to the hook via
# stdin and asserts the exit code: 0 = allow, 2 = block.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOK="$REPO_ROOT/hooks/validate-command.sh"

PASS_COUNT=0
FAIL_COUNT=0
TOTAL=0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
setup() {
  TMPDIR_TEST="$(mktemp -d)"
  # Create the minimal ecosystem layout so detect-layout.sh won't bail
  mkdir -p "$TMPDIR_TEST/skills" "$TMPDIR_TEST/rules" "$TMPDIR_TEST/hooks"
  export CLAUDE_PROJECT_DIR="$TMPDIR_TEST"

  # Initialise a git repo on `workspace` — the branch where work is allowed to
  # happen under the workspace → develop → main model. Both `main` and `develop`
  # are protected, so an unrelated test must not start on either of them.
  git -C "$TMPDIR_TEST" init -b workspace --quiet
  git -C "$TMPDIR_TEST" config user.email "test@test.com"
  git -C "$TMPDIR_TEST" config user.name "Test"
  # Need at least one commit so HEAD exists
  touch "$TMPDIR_TEST/dummy"
  git -C "$TMPDIR_TEST" add dummy
  git -C "$TMPDIR_TEST" commit -m "init" --quiet
}

teardown() {
  rm -rf "$TMPDIR_TEST"
  unset CLAUDE_PROJECT_DIR
}

# Build the JSON payload that PreToolUse sends for a Bash tool call.
make_input() {
  local cmd="$1"
  printf '{"tool_name":"Bash","tool_input":{"command":"%s"}}' "$cmd"
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
  local cmd="$1"
  local rc=0
  make_input "$cmd" | (cd "$TMPDIR_TEST" && bash "$HOOK") >/dev/null 2>&1 || rc=$?
  echo "$rc"
}

# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

echo ""
echo "=== validate-command.sh ==="
echo ""

# ---- git checkout (blocked) ----
setup
rc=$(run_hook "git checkout feature-x")
assert_exit "git checkout is blocked" 2 "$rc"
teardown

# ---- git switch (allowed) ----
setup
rc=$(run_hook "git switch develop")
assert_exit "git switch is allowed" 0 "$rc"
teardown

# ---- git revert (blocked) ----
setup
rc=$(run_hook "git revert abc123")
assert_exit "git revert is blocked" 2 "$rc"
teardown

# ---- git push --force (blocked) ----
setup
rc=$(run_hook "git push --force origin develop")
assert_exit "git push --force is blocked" 2 "$rc"
teardown

# ---- git push -f (blocked) ----
setup
rc=$(run_hook "git push -f origin develop")
assert_exit "git push -f is blocked" 2 "$rc"
teardown

# ---- git push --force-with-lease (allowed) ----
setup
rc=$(run_hook "git push --force-with-lease origin develop")
assert_exit "git push --force-with-lease is allowed" 0 "$rc"
teardown

# ---- git reset --hard (blocked) ----
setup
rc=$(run_hook "git reset --hard HEAD~1")
assert_exit "git reset --hard is blocked" 2 "$rc"
teardown

# ---- git reset --soft (allowed) ----
setup
rc=$(run_hook "git reset --soft HEAD~1")
assert_exit "git reset --soft is allowed" 0 "$rc"
teardown

# ---- git stash (allowed) ----
setup
rc=$(run_hook "git stash")
assert_exit "git stash is allowed" 0 "$rc"
teardown

# ---- commit on main (blocked) ----
setup
# Switch the temp repo to main branch
git -C "$TMPDIR_TEST" checkout -b main --quiet
rc=$(run_hook "git commit -m 'bad commit'")
assert_exit "git commit on main is blocked" 2 "$rc"
teardown

# ---- commit on workspace (allowed: this is where work happens) ----
setup
rc=$(run_hook "git commit -m 'good commit'")
assert_exit "git commit on workspace is allowed" 0 "$rc"
teardown

# ---- merge on main (blocked) ----
setup
git -C "$TMPDIR_TEST" checkout -b main --quiet
rc=$(run_hook "git merge develop")
assert_exit "git merge on main is blocked" 2 "$rc"
teardown

# ---- rebase on main (blocked) ----
setup
git -C "$TMPDIR_TEST" checkout -b main --quiet
rc=$(run_hook "git rebase develop")
assert_exit "git rebase on main is blocked" 2 "$rc"
teardown

# ---- reset --soft on main (blocked: mutates main ref) ----
setup
git -C "$TMPDIR_TEST" checkout -b main --quiet
rc=$(run_hook "git reset --soft HEAD~1")
assert_exit "git reset on main is blocked" 2 "$rc"
teardown

# ---- cherry-pick on main (blocked) ----
setup
git -C "$TMPDIR_TEST" checkout -b main --quiet
rc=$(run_hook "git cherry-pick abc123")
assert_exit "git cherry-pick on main is blocked" 2 "$rc"
teardown

# ---------------------------------------------------------------------------
# G1 — develop protection (workspace → develop → main)
# develop integrates work; it never originates it. Only the promotion merge from
# workspace and plain push stay open, mirroring how main is treated.
# ---------------------------------------------------------------------------

# ---- commit on develop (blocked: work is born on workspace) ----
setup
git -C "$TMPDIR_TEST" checkout -b develop --quiet
rc=$(run_hook "git commit -m 'straight to develop'")
assert_exit "G1: git commit on develop is blocked" 2 "$rc"
teardown

# ---- promotion merge from workspace (allowed) ----
setup
git -C "$TMPDIR_TEST" checkout -b develop --quiet
rc=$(run_hook "git merge workspace")
assert_exit "G1: 'git merge workspace' on develop is allowed" 0 "$rc"
teardown

setup
git -C "$TMPDIR_TEST" checkout -b develop --quiet
rc=$(run_hook "git merge --no-ff origin/workspace")
assert_exit "G1: 'git merge origin/workspace' on develop is allowed" 0 "$rc"
teardown

# ---- merge from anything else into develop (blocked) ----
setup
git -C "$TMPDIR_TEST" checkout -b develop --quiet
rc=$(run_hook "git merge feature-x")
assert_exit "G1: merging a non-workspace branch into develop is blocked" 2 "$rc"
teardown

# ---- rebase / reset / cherry-pick on develop (blocked) ----
setup
git -C "$TMPDIR_TEST" checkout -b develop --quiet
rc=$(run_hook "git rebase workspace")
assert_exit "G1: git rebase on develop is blocked" 2 "$rc"
teardown

setup
git -C "$TMPDIR_TEST" checkout -b develop --quiet
rc=$(run_hook "git reset --soft HEAD~1")
assert_exit "G1: git reset on develop is blocked" 2 "$rc"
teardown

setup
git -C "$TMPDIR_TEST" checkout -b develop --quiet
rc=$(run_hook "git cherry-pick abc123")
assert_exit "G1: git cherry-pick on develop is blocked" 2 "$rc"
teardown

# ---- push on develop (allowed: the promotion has to reach origin) ----
setup
git -C "$TMPDIR_TEST" checkout -b develop --quiet
rc=$(run_hook "git push origin develop")
assert_exit "G1: git push on develop is allowed" 0 "$rc"
teardown

# ---- inline switch to develop then mutate (blocked — mirrors F4) ----
setup
rc=$(run_hook "git switch develop && git commit -m x")
assert_exit "G1: 'git switch develop && git commit' is blocked" 2 "$rc"
teardown

# ---- rebase on workspace (allowed: workspace is the working branch) ----
setup
rc=$(run_hook "git rebase develop")
assert_exit "G1: git rebase on workspace is allowed" 0 "$rc"
teardown

# ---- rm -rf / (blocked) ----
setup
rc=$(run_hook "rm -rf /")
assert_exit "rm -rf / is blocked" 2 "$rc"
teardown

# ---- rm -rf /etc (blocked) ----
setup
rc=$(run_hook "rm -rf /etc")
assert_exit "rm -rf /etc is blocked" 2 "$rc"
teardown

# ---- rm -rf /home (blocked) ----
setup
rc=$(run_hook "rm -rf /home")
assert_exit "rm -rf /home is blocked" 2 "$rc"
teardown

# ---- rm -rf project-relative path (allowed) ----
setup
rc=$(run_hook "rm -rf ./build")
assert_exit "rm -rf ./build (project-relative) is allowed" 0 "$rc"
teardown

# ---- rm -rf /tmp/something (allowed) ----
setup
rc=$(run_hook "rm -rf /tmp/something")
assert_exit "rm -rf /tmp/something is allowed" 0 "$rc"
teardown

# ---- normal ls command (allowed) ----
setup
rc=$(run_hook "ls -la")
assert_exit "ls -la is allowed" 0 "$rc"
teardown

# ---- empty command / no command field (allowed) ----
setup
rc=0
echo '{"tool_name":"Bash","tool_input":{}}' | (cd "$TMPDIR_TEST" && bash "$HOOK") >/dev/null 2>&1 || rc=$?
assert_exit "empty input (no command) is allowed" 0 "$rc"
teardown

# ---- knowledge-base/references/ write via Bash (blocked) ----
setup
rc=$(run_hook "rm knowledge-base/references/foo.md")
assert_exit "rm inside knowledge-base/references/ is blocked" 2 "$rc"
teardown

# ---- knowledge-base/references/ write via Bash with .claude prefix (blocked) ----
setup
rc=$(run_hook "cp file.txt .claude/knowledge-base/references/dest.txt")
assert_exit "cp into .claude/knowledge-base/references/ is blocked" 2 "$rc"
teardown

# ---- Co-Authored-By in commit message (blocked) ----
setup
rc=$(run_hook "git commit -m 'feat: add thing\n\nCo-Authored-By: Someone <s@e.com>'")
assert_exit "commit with Co-Authored-By trailer is blocked" 2 "$rc"
teardown

# ---- git commit without Co-Authored-By (allowed on develop) ----
setup
rc=$(run_hook "git commit -m 'feat: add thing'")
assert_exit "commit without Co-Authored-By on develop is allowed" 0 "$rc"
teardown

# ===========================================================================
# Regression: issue #1 — git-safety guard bypasses (must all block)
# ===========================================================================

# ---- F1: rm recursive-intent in any flag order/spelling (blocked) ----
for c in "rm -fr /etc" "rm -Rf /usr" "rm -f -r /var" "rm --recursive --force /etc"; do
  setup; rc=$(run_hook "$c"); assert_exit "F1: '$c' is blocked" 2 "$rc"; teardown
done

# ---- F1/F8: recursive delete of a DEEP project path under /home (allowed) ----
setup; rc=$(run_hook "rm -rf /home/dev/Projetos/cycle/build"); assert_exit "F8: deep project path is allowed" 0 "$rc"; teardown

# ---- F2: force-push with the flag not right after 'push' (blocked) ----
setup; rc=$(run_hook "git push origin main --force"); assert_exit "F2: 'git push origin main --force' is blocked" 2 "$rc"; teardown
setup; rc=$(run_hook "git push origin +main"); assert_exit "F2: '+refspec' force push is blocked" 2 "$rc"; teardown
setup; rc=$(run_hook "git push origin main --force-with-lease"); assert_exit "F2: --force-with-lease is allowed" 0 "$rc"; teardown

# ---- F3: git global options smuggling a forbidden subcommand (blocked) ----
setup; rc=$(run_hook "git -C /tmp checkout main"); assert_exit "F3: 'git -C DIR checkout' is blocked" 2 "$rc"; teardown
setup; rc=$(run_hook "git -c x=y reset --hard"); assert_exit "F3: 'git -c K=V reset --hard' is blocked" 2 "$rc"; teardown

# ---- F11 (#6): the force token must belong to the PUSH, not to a neighbour ----
# The guard confirmed "a push exists" and "a force token exists" independently over
# the whole command, so any -f from another program in the compound was read as a
# force push.
setup; rc=$(run_hook "rm -f tmp.txt && git push origin workspace"); assert_exit "F11: 'rm -f' next to a plain push is allowed" 0 "$rc"; teardown
setup; rc=$(run_hook "tar -xf pkg.tar && git push origin workspace"); assert_exit "F11: 'tar -xf' next to a plain push is allowed" 0 "$rc"; teardown
setup; rc=$(run_hook "cp -f a b; git push origin workspace"); assert_exit "F11: 'cp -f' before a plain push is allowed" 0 "$rc"; teardown
# F2 regressions: a force token that DOES belong to the push stays blocked.
setup; rc=$(run_hook "git push -u -f origin workspace"); assert_exit "F11: '-f' among the push's own flags stays blocked" 2 "$rc"; teardown
setup; rc=$(run_hook "rm -f tmp.txt && git push --force origin workspace"); assert_exit "F11: real force push next to 'rm -f' stays blocked" 2 "$rc"; teardown
# Two pushes in one compound: the force on the FIRST must not be lost.
setup; rc=$(run_hook "git push --force origin a && git push origin b"); assert_exit "F11: force on the first of two pushes stays blocked" 2 "$rc"; teardown

# ---------------------------------------------------------------------------
# P1 — reference EXFILTRATION: content must not leave the read-only study zone
# The pre-existing guard only watched writes INTO knowledge-base/{references,tools}/.
# Copying content OUT of it is the provenance leak, and was fully open.
# ---------------------------------------------------------------------------
setup; rc=$(run_hook "cp knowledge-base/references/redis/src/dict.c src/mine.c"); assert_exit "P1: cp out of the reference zone is blocked" 2 "$rc"; teardown
setup; rc=$(run_hook "cat knowledge-base/references/redis/src/dict.c > src/mine.c"); assert_exit "P1: redirect out of the reference zone is blocked" 2 "$rc"; teardown
setup; rc=$(run_hook "rsync -a knowledge-base/tools/foo/ src/vendor/"); assert_exit "P1: rsync out of the tools zone is blocked" 2 "$rc"; teardown
setup; rc=$(run_hook "cat .claude/knowledge-base/references/x/y.py >> src/z.py"); assert_exit "P1: append out of the .claude-prefixed zone is blocked" 2 "$rc"; teardown
setup; rc=$(run_hook "cat knowledge-base/references/redis/src/dict.c | tee src/mine.c"); assert_exit "P1: pipe-to-tee out of the zone is blocked" 2 "$rc"; teardown
# Reading and searching the zone stays allowed — that is what it is FOR.
setup; rc=$(run_hook "cat knowledge-base/references/redis/src/dict.c"); assert_exit "P1: plain read of the zone is allowed" 0 "$rc"; teardown
setup; rc=$(run_hook "grep -rn dictExpand knowledge-base/references/"); assert_exit "P1: grep inside the zone is allowed" 0 "$rc"; teardown
setup; rc=$(run_hook "ls knowledge-base/references/"); assert_exit "P1: ls of the zone is allowed" 0 "$rc"; teardown
# Correlation: an unrelated cp in another segment must not be blamed on the zone.
setup; rc=$(run_hook "ls knowledge-base/references/ && cp a.txt b.txt"); assert_exit "P1: unrelated cp in another segment is allowed" 0 "$rc"; teardown

# ---------------------------------------------------------------------------
# P2 — commit messages must not carry reference-zone paths
# ---------------------------------------------------------------------------
setup; rc=$(run_hook "git commit -m 'port from knowledge-base/references/redis/src/dict.c'"); assert_exit "P2: commit message citing the zone is blocked" 2 "$rc"; teardown
setup; rc=$(run_hook "git commit -m 'adapted from .claude/knowledge-base/tools/foo'"); assert_exit "P2: commit message citing the tools zone is blocked" 2 "$rc"; teardown
# Precision: the word "references" on its own is NOT the zone.
setup; rc=$(run_hook "git commit -m 'fix cross-references in rules README'"); assert_exit "P2: 'cross-references' is not the zone" 0 "$rc"; teardown
setup; rc=$(run_hook "git commit -m 'chore: normal change'"); assert_exit "P2: ordinary commit message is allowed" 0 "$rc"; teardown

# ---- F4: switch-to-main inline then mutate main (blocked) ----
setup; rc=$(run_hook "git switch main && git commit -m x"); assert_exit "F4: 'git switch main && git commit' is blocked" 2 "$rc"; teardown

# ---- F9 (#2): a command that merely QUOTES a git invocation is not one ----
# The F4 guard matched 'git switch main' + 'git commit' anywhere in the command
# text, so an echo/gh/commit-message that CITES them was blocked (over-block).
setup; rc=$(run_hook "echo \\\"doc: use git switch main and then git commit \\\""); assert_exit "F9: echo quoting 'git switch main'+'git commit' is allowed" 0 "$rc"; teardown
setup; rc=$(run_hook "gh issue create --body 'repro: git switch main && git commit -m x'"); assert_exit "F9: gh issue body quoting the bypass is allowed" 0 "$rc"; teardown
# F4 regression: the real bypass must STAY blocked, quoted message included.
setup; rc=$(run_hook "git switch main && git commit -m \\\"real bypass\\\""); assert_exit "F9: real bypass with quoted -m stays blocked" 2 "$rc"; teardown
setup; rc=$(run_hook "git checkout -b main && git commit -m x"); assert_exit "F9: checkout -b main + commit stays blocked" 2 "$rc"; teardown

# ---- F10 (#4): rm glob in a DEEP path is not a root glob ----
# DANGEROUS_PATH_RE's '/\*' had no anchor, so 'dir/sub/*' matched like '/*' —
# blocking the very cleanup the hook's own message tells the operator to do.
setup; rc=$(run_hook "rm -rf /tmp/deep/dir/sub/*"); assert_exit "F10: 'rm -rf /tmp/deep/dir/sub/*' is allowed" 0 "$rc"; teardown
setup; rc=$(run_hook "rm -rf build/artifacts/*"); assert_exit "F10: 'rm -rf build/artifacts/*' is allowed" 0 "$rc"; teardown
# F10 regression: root glob and the bare roots must STAY blocked.
setup; rc=$(run_hook "rm -rf /*"); assert_exit "F10: 'rm -rf /*' stays blocked" 2 "$rc"; teardown
setup; rc=$(run_hook "rm -rf /home/dev"); assert_exit "F10: 'rm -rf /home/<user>' stays blocked" 2 "$rc"; teardown
setup; rc=$(run_hook "rm -rf /etc/foo"); assert_exit "F10: 'rm -rf /etc/foo' stays blocked" 2 "$rc"; teardown
setup; rc=$(run_hook "rm -rf \\\$HOME"); assert_exit "F10: 'rm -rf \$HOME' stays blocked" 2 "$rc"; teardown

# ---------------------------------------------------------------------------
# F12: trunk protection must follow the repo's trunk, not the literal name `main`
# ---------------------------------------------------------------------------
# An adopting project whose trunk is `master` installed the kit, read that Rule 4
# was protected, and it was not: the guard matched `[ "$BRANCH" = "main" ]` and
# nothing else. Measured on a throwaway project — on `master` the commit went
# through (exit 0), on `main` it blocked. The worst failure shape: promising
# without delivering, silently.
#
# `master` covers the majority; a trunk with a name of its own (`trunk`, `release`) is read
# from `origin/HEAD`. Over-protecting is the safe side of the error: blocking a
# commit that could have passed costs a branch switch, and the inverse costs the
# guarantee.

# ---- commit on master (blocked, like main) ----
setup
git -C "$TMPDIR_TEST" branch -m master --quiet 2>/dev/null || git -C "$TMPDIR_TEST" checkout -b master --quiet
rc=$(run_hook "git commit -m 'bad commit'")
assert_exit "F12: commit on 'master' is blocked" 2 "$rc"
teardown

# ---- mutations on master (blocked, like main) ----
setup
git -C "$TMPDIR_TEST" branch -m master --quiet 2>/dev/null || git -C "$TMPDIR_TEST" checkout -b master --quiet
rc=$(run_hook "git rebase HEAD~1")
assert_exit "F12: rebase on 'master' is blocked" 2 "$rc"
teardown

# ---- inline switch to master then commit (blocked) ----
setup
rc=$(run_hook "git switch master && git commit -m x")
assert_exit "F12: inline 'switch master && commit' is blocked" 2 "$rc"
teardown

# ---- the remote's default branch is protected even under a custom name ----
setup
git -C "$TMPDIR_TEST" checkout -b trunk --quiet
git -C "$TMPDIR_TEST" remote add origin "$TMPDIR_TEST" 2>/dev/null || true
git -C "$TMPDIR_TEST" symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/trunk 2>/dev/null || true
rc=$(run_hook "git commit -m 'bad commit'")
assert_exit "F12: commit on the remote's default branch ('trunk') is blocked" 2 "$rc"
teardown

# ---- regression: workspace stays writable ----
setup
rc=$(run_hook "git commit -m 'good commit'")
assert_exit "F12 regression: commit on 'workspace' still allowed" 0 "$rc"
teardown

# ---- regression: a feature branch is not a trunk ----
setup
git -C "$TMPDIR_TEST" checkout -b fix/some-bug --quiet
rc=$(run_hook "git commit -m 'fine'")
assert_exit "F12 regression: commit on a feature branch still allowed" 0 "$rc"
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
