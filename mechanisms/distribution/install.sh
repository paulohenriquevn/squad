#!/usr/bin/env bash
# Installs the Squad maintenance ecosystem into a target project as a plugin install
# (target/.claude/ layout). Hooks auto-detect the layout, so target/.claude/* is
# picked up identically to the standalone repo.
#
# Usage:
#   bash mechanisms/distribution/install.sh <target-project-dir> [--force | --merge]
#   bash mechanisms/distribution/install.sh <target-project-dir> --apply-upstream <path> [--from <kit-dir>]
#
# What it does:
#   1. Validates target is a directory, and refuses the machine-wide roots — $HOME,
#      $CLAUDE_CONFIG_DIR and its parent, and /. Everything under <target>/.claude/ is
#      replaced, so a mistyped argument there rewrites the configuration of every
#      project on the machine.
#   2. Refuses to overwrite an existing target/.claude/ unless --force or --merge.
#      --force  replaces every name the kit ships, snapshotting what it overwrote into
#               .claude/.install-backups/<timestamp>/ first. Files the kit does NOT
#               ship are left alone.
#      --merge  adds the kit's files and deletes nothing. The header listed only
#               --force until 2026-09-17, while the parser had accepted --merge since
#               it was added — an operator reading the usage line could not discover
#               the one flag that does not clobber.
#      --apply-upstream <path>
#               takes the kit's version of ONE file and installs nothing else. It
#               refuses every file this install holds unique lines in — DIVERGED and
#               INSTALL_AHEAD alike — so it can only ever delete a line the kit still
#               ships. See the block guarding it below for why the refusal, not the
#               copy, is the point. --from names the kit to take the file FROM; the
#               classifier always comes from this script's own tree.
#   3. Copies skills/, rules/, hooks/, commands/, mechanisms/, squad/, plugin.json,
#      HOW-TO-USE.md into target/.claude/.
#   4. settings.json: MERGED by key ownership when the target already has one —
#      the kit owns its wiring (statusLine, env, defaultMode), `hooks` and
#      `permissions` are merged per ENTRY so a consumer's own survive, and the
#      kit's are unioned in as a floor with the
#      consumer's kept. Written whole from settings.plugin.json only when the
#      target has none. (This line said "writes settings.plugin.json as
#      target/.claude/settings.json" until 2026-09-04, describing the behaviour
#      issue #8 reported and this merge replaced in August. A reader who trusted
#      it avoided the installer to protect permissions the merge would have kept.)
#   5. Creates an empty scaffold under target/.squad/records/ — NOT under
#      target/.claude/, which holds the installed kit and nothing the kit writes.
#      The list is `KB_DIRS` below and is the only authority; this line names it
#      rather than restating it, because the previous restatement drifted three ways
#      at once: it gave the .claude path the code contradicts in its own comment,
#      promised `adrs/` (retired — decisions live in .squad/wiki/decisions/) and
#      promised `grills/` and `discoveries/opportunities/` that nothing created,
#      so the terminal artifact of DISCOVER had nowhere to land. Both now exist.
#      agents/ receives README.md (the routing mechanism) AND the kit's 14 generic
#      specialists — nemesis-claim-auditor, vera-technical-arbiter and the rest, which
#      the review panel and the judge stages name by id. agents/ is never deleted, so a
#      project's own specialists survive beside them.
#
#      This line said "the kit ships none" until 2026-09-15, which was true when it was
#      written and false for every install since the specialists landed. Measured while
#      installing a consumer: agents/ went from 1 file to 15, and the comment said that
#      could not happen. Same failure this file already records one paragraph above —
#      a reader trusting a stale line about what the installer does.
#   6. Skips the source repo's history: caches, artifact dirs, audit trails,
#      CHANGELOG.md, .git/, .compaction-snapshots/, .attestations/.
#   7. Prints next steps.
#
# What it does NOT do:
#   - Modify the consumer's CLAUDE.md (write your own pointer to .claude/).
#   - Add anything to .gitignore (consumer decides whether to track .claude/).
#   - Install dependencies (python3, jq, ast-grep, ralph-loop plugin) — see HOW-TO-USE.md.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The kit root is two levels up: this script lives in `mechanisms/distribution/`.
SRC_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# --- args ---
if [ $# -lt 1 ]; then
  echo "Usage: bash mechanisms/distribution/install.sh <target-project-dir> [--force|--merge]" >&2
  exit 2
fi

TARGET="$1"
FORCE=0
MERGE=0
REMOVE_WITHDRAWN=0
APPLY_UPSTREAM=""
APPLY_FROM=""
_expect=""
for arg in "${@:2}"; do
  if [ -n "$_expect" ]; then
    case "$_expect" in
      apply) APPLY_UPSTREAM="$arg" ;;
      from)  APPLY_FROM="$arg" ;;
    esac
    _expect=""
    continue
  fi
  case "$arg" in
    --force) FORCE=1 ;;
    --merge) MERGE=1 ;;
    --remove-withdrawn) REMOVE_WITHDRAWN=1 ;;
    --apply-upstream) _expect="apply" ;;
    --from) _expect="from" ;;
    "") ;;
    *) echo "ERROR: unknown flag ${arg}. Expected --force, --merge, --remove-withdrawn, --apply-upstream <path> or --from <kit-dir>." >&2; exit 2 ;;
  esac
done
if [ -n "$_expect" ]; then
  echo "ERROR: --${_expect/apply/apply-upstream} needs a value." >&2
  exit 2
fi

if [ ! -d "$TARGET" ]; then
  echo "ERROR: target is not a directory: $TARGET" >&2
  exit 2
fi

TARGET="$(cd "$TARGET" && pwd)"
ECO="$TARGET/.claude"

# ── --apply-upstream: ONE file, and only where nothing can be lost ────────────
#
# The kit had two modes and both replace everything, while `boundary-check` refuses
# editing a kit file inside an install — correctly, for a fix somebody WROTE there:
# it protects one machine and the next install erases it. Neither answers the other
# case: a file that differs because the KIT moved and this install did not.
#
# READ THIS FIRST IF YOU CAME HERE TO FIX A DRIFTED INSTALL. Six mechanisms were measured
# individually across two sessions on 2026-09-23 — score_alignment, promote_to_develop,
# check_spec_smells, stop-validation, validate-command, and the boundary guard's treatment
# of a read. All six classify DIVERGED. **This mode resolves none of them.** It is not the
# answer to the drift that motivated it; it is the answer to the cheap half beside it.
#
# Measured the same day across four consumers (stepguard, gitsafety, hodor, talkex — the
# same distribution in all four): 400 files differ, and they split into
#     diverged 349 · install_ahead 1 · stale 10 · kit_ahead 40
# This mode applies to the last two — 50 files — and refuses the other 350.
#
# Both halves of that measurement come from a peer session running the checker against its
# own install; the six-of-six count is theirs. Two of the six had already produced a wrong
# diagnosis before measurement caught them, and a third was about to become a filed item —
# a stale install does not merely lag, it ANSWERS, and a stale answer is indistinguishable
# from a current one until something contradicts it. Three in six producing false
# conclusions is the number worth putting in front of whoever decides that reading 138
# diffs by hand is worth the afternoon.
#
# THE REFUSAL IS THE DESIGN, and it costs real coverage: of the 349 diverged, 22 differ by
# four lines or fewer and 83 by ten or fewer, and this refuses every one of them. That is
# the intended price. *Is this my work or my lag* is precisely the judgement
# `check_install_drift` states, in its own output, that it cannot make: "yours, or work to
# harvest — this check cannot tell". A small diff is not evidence of which one it is; the
# 2-line diff in `skills/code-quality/scripts/detectors/_mutation.py` looks exactly like a
# 2-line local fix. A command that appears to settle that question would be used on the
# cases where it does not, and the cost of being wrong is somebody's fix deleted silently.
#
# An earlier draft of this comment claimed the mode covered "67 files differing by one or
# two lines". That number came from counting differing LINES and never resolving the
# CLASS — the same defect this kit records under "an identifier counted rather than
# resolved". Those files are diverged, and this refuses them.
#
# What it covers is the case with nothing to lose on either side: the install holds no line
# the kit lacks, so taking the kit's version deletes nothing. Everything else keeps the
# answer it has today — open an issue, or reinstall deliberately.
if [ -n "$APPLY_UPSTREAM" ]; then
  _src_root="${APPLY_FROM:-$SRC_DIR}"
  _rel="$APPLY_UPSTREAM"

  # `..` is how a per-file copy becomes a write anywhere. Asked of realpath rather than
  # matched as a string: `a/../../b` normalises to something no pattern for ".." catches.
  #
  # BOTH sides are resolved. Comparing a resolved destination against an unresolved $ECO
  # refuses every install whose .claude is a symlink — a legitimate layout — with a message
  # about escaping that names a path the operator never wrote. Fail-closed on the wrong
  # question is still the wrong answer.
  _eco_real="$(realpath -m "$ECO")"
  _dest="$(realpath -m "$ECO/$_rel")"
  case "$_dest" in
    "$_eco_real"/*) ;;
    *) echo "ERROR: $_rel resolves outside the install ($_dest). Nothing was written." >&2
       exit 2 ;;
  esac

  # `rules/*.txt`, `agents/`, `records/`, `settings.json` are the PROJECT's, and the kit's
  # copy of them is a template. Overwriting one is what `--merge` exists to avoid, so this
  # mode refuses rather than quietly doing what the other mode refuses on purpose.
  # IMPORTED, not copied. The first draft of this block restated `PROJECT_OWNED` inline,
  # which made it the fourth reader of "whose file is this" — the exact multiplication
  # `check_install_drift._is_project_owned` refuses to add to in its own comment, and the
  # thing `check_write_containment` refuses for data roots. One declaration or they drift.
  if SQ_REL="$_rel" SQ_KIT="$SCRIPT_DIR/../.." python3 -c '
import os, sys
sys.path.insert(0, os.environ["SQ_KIT"])
from squad.boundaries import PROJECT_OWNED
sys.exit(0 if any(p.search(os.environ["SQ_REL"]) for p in PROJECT_OWNED) else 1)
'
  then
    echo "REFUSED: $_rel is the project's, not the kit's. The kit ships a template for it" >&2
    echo "  and --merge preserves yours on purpose. Nothing was written." >&2
    exit 2
  fi

  if [ ! -f "$_src_root/$_rel" ]; then
    echo "ERROR: the kit does not ship $_rel (looked in $_src_root)." >&2
    echo "  There is no upstream version to take, and writing one would delete yours." >&2
    exit 2
  fi
  if [ ! -f "$ECO/$_rel" ]; then
    echo "ERROR: $_rel is not in this install. Use --merge to add what the kit ships." >&2
    exit 2
  fi

  # The classifier comes from THIS installer's own tree, never from --from. The source of
  # the content and the authority on what the difference means are two different things,
  # and an old --from tree may predate the classifier — or not ship it at all.
  # FOUR arguments, not two. `classify_file` promotes DIVERGED to STALE only when given
  # `kit_root` AND `rel` — `rel` also enables its ownership guard — so a two-argument call
  # can never return STALE and never consults ownership. The scan passes both and saw
  # `stale: 9`; this passed neither and refused the same nine as DIVERGED. One reader,
  # called with less context than it needs, which is the inverse of the duplication the
  # `PROJECT_OWNED` import above removes and just as capable of two answers.
  #
  # `kit_root` is the CONTENT source when that is a git checkout, because the history that
  # explains this install is the history of the kit it came from; it falls back to this
  # script's own tree, which is also where the classifier is imported from.
  _hist_root="$_src_root"
  git -C "$_hist_root" rev-parse --git-dir >/dev/null 2>&1 || _hist_root="$SRC_DIR"
  _verdict="$(SQ_A="$ECO/$_rel" SQ_B="$_src_root/$_rel" SQ_REL="$_rel" \
              SQ_HIST="$_hist_root" SQ_GATES="$SCRIPT_DIR/../gates" python3 -c '
import os, sys
from pathlib import Path
sys.path.insert(0, os.environ["SQ_GATES"])
from check_install_drift import classify_file
print(classify_file(Path(os.environ["SQ_A"]), Path(os.environ["SQ_B"]),
                    Path(os.environ["SQ_HIST"]), os.environ["SQ_REL"]).value)
')" || _verdict=""

  case "$_verdict" in
    identical)
      echo "IDENTICAL: $_rel already matches the kit. Nothing was written." ;;
    kit_ahead|stale)
      cp "$_src_root/$_rel" "$ECO/$_rel"
      echo "APPLIED: $_rel took the kit's version ($_verdict — this install held no line the kit lacks)." ;;
    diverged)
      echo "REFUSED: $_rel is DIVERGED — both sides hold unique lines, and this cannot tell" >&2
      echo "  your work from your lag. Copying would delete a fix without a trace." >&2
      echo "  Read the diff, and send anything of yours upstream as an issue." >&2
      exit 1 ;;
    yours)
      # Reachable only if `squad.boundaries` and `check_install_drift._is_project_owned`
      # disagree — they do, for `agents/`, and that disagreement is a contract question
      # the drift gate documents and declines to settle. The guard above catches the
      # boundaries answer first; this is the other reader saying the same thing, and it
      # refuses rather than falling into "could not classify".
      echo "REFUSED: $_rel is the project's by the drift gate's reading. Nothing was written." >&2
      exit 2 ;;
    install_ahead)
      echo "REFUSED: $_rel is INSTALL_AHEAD — it holds lines the kit does not, and those are" >&2
      echo "  the only ones an upgrade deletes. Harvest them upstream first." >&2
      exit 1 ;;
    *)
      echo "ERROR: could not classify $_rel (got '$_verdict'). Nothing was written." >&2
      exit 2 ;;
  esac
  exit 0
fi

# Placed AFTER the per-file mode on purpose. Printed before it, these eight lines led
# every single-file invocation — 176 lines of unrelated repetition in a loop of 22, which
# is how a report teaches people to skip it. A withdrawal is news about the whole install,
# so it belongs to the operation that touches the whole install.
# ── what this kit SHIPPED and later WITHDREW ─────────────────────────────────
#
# A withdrawal reaches nobody. The skills branch below preserves any directory the source
# kit does not ship — right for a project's own skill, and exactly wrong for one this kit
# RETIRED, which is indistinguishable from it on disk. So retiring a skill removed it here
# and removed nothing anywhere, and the next install copied the old copy aside and restored
# it. Measured on one consumer: 30 skills present and absent from the kit, 103 of the 111
# files `check_install_drift` calls "consumer-local" belonging to them, 0 of the 30 named in
# `.kit-manifest.txt` — whose header says "Anything not here is the project's", false for
# every one of them because the manifest is regenerated and the withdrawing install erased
# the only record that the kit ever shipped them.
#
# They are not inert. A stale `shared-understanding` cites `rules/alignment-threshold.md`,
# which moved to `skills/_kit-rules/`, and breaks `check_xrefs` for the WHOLE install; its
# `score_alignment.py` predates `--depth` and produced a BLOCKED verdict on an item the
# current copy scores ALIGNED at 92%.
#
# BY NAME, NEVER BY ABSENCE. Absence is how a project's own skill gets deleted, so only a
# name in `withdrawn.txt` is ever called a withdrawal. Reported always; removed only under
# `--remove-withdrawn`, because a consumer may have kept a retired skill deliberately.
_withdrawn_list="$SCRIPT_DIR/withdrawn.txt"
if [ -f "$_withdrawn_list" ] && [ -d "$ECO" ]; then
  _found=0
  while IFS='|' read -r _rel _when _successor _record; do
    _rel="$(echo "$_rel" | tr -d '[:space:]')"
    case "$_rel" in ""|\#*) continue ;; esac
    [ -e "$ECO/$_rel" ] || continue
    if [ "$_found" = 0 ]; then
      echo ""
      echo "==> WITHDRAWN by the kit, still present here:"
      _found=1
    fi
    printf '    %-28s withdrawn %s · successor %s · see %s\n' \
      "$_rel" "$(echo "$_when" | xargs)" "$(echo "$_successor" | xargs)" "$(echo "$_record" | xargs)"
    if [ "$REMOVE_WITHDRAWN" = 1 ]; then
      rm -rf "${ECO:?}/$_rel"
      echo "        removed (--remove-withdrawn)"
    fi
  done < "$_withdrawn_list"
  if [ "$_found" = 1 ] && [ "$REMOVE_WITHDRAWN" = 0 ]; then
    echo "    These are the kit's, not yours, and nothing else will tell you."
    echo "    Re-run with --remove-withdrawn to delete exactly the names listed above."
    echo ""
  fi
fi



if [ "$TARGET" = "$SRC_DIR" ]; then
  echo "ERROR: target is the source repo itself. install.sh is for installing the ecosystem INTO another project." >&2
  exit 2
fi

# Everything destructive below is rooted at $ECO: `rm -rf "${ECO:?}/$item"` for six
# directories, plus a settings.json merge. Until these three refusals existed, the only
# check was the source repo above, so `bash install.sh ~` resolved $ECO to the MACHINE-WIDE
# Claude configuration and rewrote the hook wiring and permission floor for every project
# on the machine. A mistyped or agent-supplied argument is the whole vector.
#
# A project marker is deliberately NOT required: the kit installs into bare directories
# legitimately. What is refused is the set of roots that are never a project.
CONFIG_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CONFIG_PARENT="$(dirname "$CONFIG_HOME")"
for forbidden in "/" "$HOME" "$CONFIG_HOME" "$CONFIG_PARENT"; do
  [ -n "$forbidden" ] || continue
  if [ "$TARGET" = "$forbidden" ]; then
    echo "ERROR: refusing to install into $TARGET." >&2
    echo "  Everything under $TARGET/.claude would be replaced, and that path is the" >&2
    echo "  machine-wide Claude configuration, not a project. Name the project directory." >&2
    exit 2
  fi
done

if [ -d "$ECO" ] && [ "$FORCE" -ne 1 ] && [ "$MERGE" -ne 1 ]; then
  echo "ERROR: $ECO already exists." >&2
  echo "  --merge  add the kit's files, delete nothing." >&2
  echo "  --force  refresh skills/rules/hooks/commands/mechanisms/squad/agents. Snapshots first and" >&2
  echo "           names what it overwrote. Files the kit does NOT ship are left alone: a name the" >&2
  echo "           kit ships is the kit's and is replaced; anything else is the project's and stays." >&2
  exit 2
fi

echo "==> Installing Squad ecosystem"
echo "    source: $SRC_DIR"
echo "    target: $ECO"

# --- snapshot what the project owns, before overwriting it ---
# `rules/` and `agents/` are exactly where a project's own configuration lives: the routing
# table, its domain specialists, and every gate the "Next steps" below tells you to edit
# (code-quality-languages.txt, live-target.txt, acceptance-target.txt, the allow-lists).
# `--force` overwrote all of it silently. Measured: a `typescript | ... | ENABLED` line and a
# live-target block added to a fresh install were both gone after one re-run, with no message.
#
# In a repo that versions `.claude/` that is recoverable with `git restore`. a TypeScript monorepo does not
# version it — the kit is a maintainer's tool, not product code — so silent was also permanent.
# The fix is not to merge (guessing which side of a config wins is how you get it wrong): it is
# to make the overwrite recoverable and loud. For an upgrade that must NOT clobber, use
# `patch_install.sh`, which copies a manifest and leaves agents/ and settings.json alone.
BACKUP_DIR=""
# ALWAYS under the target, never under /tmp, and never empty. The `:-/tmp` fallback that
# first replaced `mktemp -d` would have reintroduced the defect on any path where this
# block did not run — a default that restores the bug is not a default.
STAGING="$ECO/.install-backups/staging"
mkdir -p "$STAGING"
if [ -d "$ECO" ]; then
  BACKUP_DIR="$ECO/.install-backups/$(date +%Y%m%dT%H%M%S)"
  mkdir -p "$BACKUP_DIR"
  # Where project-authored files are held between the `rm -rf` and the restore loop.
  # This was `mktemp -d` — a directory under /tmp — and for that window it held the ONLY
  # copy of every file under skills/, rules/, hooks/, commands/, mechanisms/ and squad/
  # that the kit does not ship. An interrupt, a crash or a reboot in that window loses
  # them with nothing to recover from, and /tmp is the one directory a machine may clear
  # on its own. Beside the snapshot instead: same filesystem, same lifetime, and the
  # operator is already told where that directory is.
  for item in rules agents; do
    [ -d "$ECO/$item" ] && cp -r "$ECO/$item" "$BACKUP_DIR/$item"
  done
  echo "==> Snapshot of the previous rules/ and agents/: $BACKUP_DIR"
fi

# --- copy without tool caches ------------------------------------------------
# This script's header promises to skip caches. `cp -r` does not read
# `.gitignore`, and the caches live INSIDE `skills/` — so the promise was never
# kept: measured 2026-08-26, an install carried 342 `.pyc` files and 51 cache
# directories (3.9 MB) to the consumer, 887 files against 496 tracked. Almost
# half of what arrived was not the system, and the consumer's own auditors
# started measuring files that are not the project's.
#
# `tar` in a pipe, not `rsync`: rsync is not guaranteed on every machine; tar is.
# The exclusions are CACHE only — nothing here decides what counts as kit
# content, that remains the source tree.
KIT_EXCLUDES=(
  --exclude=__pycache__
  --exclude=.pytest_cache
  --exclude=.ruff_cache
  --exclude=.mypy_cache
  --exclude=.hypothesis
  --exclude=*.pyc
  --exclude=*.pyo
  --exclude=.DS_Store
)

# copy_tree <src> <dest> — copies the CONTENTS of src into dest.
copy_tree() {
  local src="$1" dest="$2"
  mkdir -p "$dest"
  tar -cf - -C "$src" "${KIT_EXCLUDES[@]}" . | tar -xf - -C "$dest"
}

# Removes cache generated AFTER the copy. The validation at the end of this
# script runs Python inside the target, and the interpreter writes `__pycache__`
# on import — without this cleanup the verification step reintroduces exactly the
# litter the copy just avoided.
prune_caches() {
  find "$1" -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache \
       -o -name .mypy_cache \) -prune -exec rm -rf {} + 2>/dev/null || true
  find "$1" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete 2>/dev/null || true
}

# --- routing table: shipped EMPTY ---------------------------------------------
# --- copy ecosystem code ---
# Two modes, because a target with a `.claude/` of its own has no correct answer in one of them.
# Measured on an adopter: 598 files under `skills/` — 5 of the kit's, 10 the project wrote
# (`architecture-debate-table`, `placement-algorithms`, `quota-isolation`, …) — plus 13 named
# architect agents and their memory. The `rm -rf` below would have deleted every one of them, and
# a snapshot in `.install-backups/` is a consolation prize, not a correct install.
# Which `rules/*.txt` belong to the KIT rather than to the project.
#
# The suffix was a fine proxy while every `.txt` under `rules/` was the
# consumer's — enabled languages, allowlists, thresholds. `cycle-phases.txt`
# broke it: it declares the pipeline's phase chain, the consumer never edits it,
# and `check_phase_drift.py` measures runs against it. Preserved by extension, a
# stale chain freezes in every consumer and the drift gate starts comparing
# against a contract the kit stopped shipping.
#
# Stated by name, because guessing ownership from a filename is what produced
# this defect.
kit_owns_txt() {
  case "$1" in
    cycle-phases.txt) return 0 ;;
    # Same shape as the phase chain: it names the verdicts that hold an item, the
    # consumer never edits it, and both `check_phase_drift.py` and the board read it
    # to answer one question. Preserved by extension, a consumer keeps whatever list
    # it first received while the kit ships a corrected one.
    blocking-verdicts.txt) return 0 ;;
    # The third of the same shape, and the one that made the pattern explicit: it
    # classifies every verdict into a band, the consumer never edits it, and
    # `check_phase_drift.py` reads it to tell legitimate rework from a step out of
    # sequence. Preserved by extension, a consumer keeps whatever classification it
    # first received — and an unclassified verdict silently disables the check, which
    # is the defect the registry was created to end.
    verdict-bands.txt) return 0 ;;
    # The kit's own record of the permission rules it has withdrawn. A consumer
    # never writes to it — only the kit knows what the kit used to ship — and it
    # is the half of retirement that works with no recorded base, so a frozen
    # copy is a consumer that keeps every rule the kit ever retired.
    #
    # Added the same day the file was, after `install.sh` announced
    # "kept (yours): rules/retired-permissions.txt" on its first update. It
    # arrived that time only because it was NEW; the second update would have
    # preserved a stale one. Exactly what the comment above this case block warns
    # about, introduced by the commit that wrote the comment's newest example.
    retired-permissions.txt) return 0 ;;
    *) return 1 ;;
  esac
}


mkdir -p "$ECO"
# Becomes 1 when the consumer's DERIVED table was preserved — in that case the
# empty template must not be applied on top of it.
# Capture the pre-move routing table before the copy loop replaces the file it
# lives in. Read after the loop and you read the kit's own fresh copy, which has
# no table — the migration would find nothing and say nothing.
LEGACY_TABLE=""
if [ -f "$ECO/rules/cycle-backlog.md" ]; then
  LEGACY_TABLE="$(mktemp)"
  cp "$ECO/rules/cycle-backlog.md" "$LEGACY_TABLE"
fi

# ── the rename: `scripts/` became `mechanisms/<family>/` ──────────────────────
# A consumer installed before this carries `.claude/scripts/`. Copying `mechanisms/`
# beside it leaves BOTH on disk, and the stale copy is not inert: `hooks/` resolves
# through a fallback chain that still lists `.claude/scripts/`, so a hook would keep
# firing the OLD gate and reporting its verdict as current. That is the drift
# `check_install_drift.py` exists to name, arriving through the installer itself.
#
# Only a directory the KIT wrote is removed. A file the project put in `scripts/`
# is its own — it is moved aside, never deleted, and the path is printed.
if [ -d "$ECO/scripts" ]; then
  echo "==> Migrating: scripts/ became mechanisms/<family>/"
  _kept="$ECO/scripts.project-files"
  _orphans=0
  while IFS= read -r _f; do
    _base="$(basename "$_f")"
    if [ -z "$(find "$SRC_DIR/mechanisms" -name "$_base" -print -quit 2>/dev/null)" ]; then
      mkdir -p "$_kept"; mv "$_f" "$_kept/"; _orphans=$((_orphans + 1))
    fi
  done < <(find "$ECO/scripts" -type f 2>/dev/null)
  if [ "$_orphans" -gt 0 ]; then
    echo "    $_orphans file(s) the kit does not ship moved to scripts.project-files/ — review and keep"
  fi
  rm -rf "$ECO/scripts"
  echo "    removed the stale .claude/scripts/ so no hook resolves to it"
fi

for item in skills rules hooks commands mechanisms squad; do
  if [ "$MERGE" -eq 1 ]; then
    echo "==> Merging $item/ (adding, deleting nothing)"
    mkdir -p "$ECO/$item"
    if [ "$item" = "rules" ]; then
      # The routing table is project configuration living inside a kit `.md`.
      # Save it before copying and re-inject it after: measured on `speculative`,
      # reinstalling restored the origin ecosystem's table over the derived one and
      # `route_domain <project>` went from exit 0 to exit 1 — the project stopped
      # being able to route items about itself. The rest of cycle-backlog.md is the
      # kit's contract.
      # `rules/*.txt` is the project's CONFIGURATION — enabled languages, live
      # target, allowlists, declared auxiliary skills. Copying the template over it
      # erases local tuning in silence: measured on `speculative`, where the
      # declaration of the project's 9 skills died on the next reinstall. The `.md`
      # files keep being updated — they are the normative contract, and the kit owns
      # them.
      for f in "$SRC_DIR/rules"/*; do
        [ -f "$f" ] || continue
        base="$(basename "$f")"
        case "$base" in
          *.txt)
            if [ -f "$ECO/rules/$base" ] && ! kit_owns_txt "$base"; then
              echo "    kept (yours): rules/$base"
              continue
            fi
            ;;
        esac
        # Project-specific config is born blank: the kit used to ship ITS OWN
        # (Python enabled, the origin ecosystem's live target) as if it were the
        # consumer's. The thresholds have NO template — they are universal defaults,
        # and emptying them would leave the gate with no band at all.
        if [ "$base" = "domain-routing.md" ]; then
          continue  # SECTION template, applied by apply_routing_template
        fi
        if [ "$base" = "domain-routing.txt" ]; then
          # The kit stopped carrying this file on 2026-09-21. `squad.paths` has written
          # the table to the project's write root since 2026-09-11, and copying a
          # placeholder under `rules/` shipped it to the one directory no writer fills —
          # then recreated it on every reinstall, which is the copy B-198's own comment
          # calls "silently correct" and therefore invisible.
          continue
        fi
        if [ -f "$SRC_DIR/rules/templates/$base" ]; then
          cp "$SRC_DIR/rules/templates/$base" "$ECO/rules/$base"
        else
          cp "$f" "$ECO/rules/$base"
        fi
      done
    else
      copy_tree "$SRC_DIR/$item" "$ECO/$item"
    fi
  else
    echo "==> Copying $item/"
    # `rules/*.txt` is the project's configuration, and this branch is about to
    # `rm -rf` the directory holding it. The merge branch guards it with a
    # `continue`; this one did not, so `--force` — the flag a reinstall uses —
    # erased what that guard exists to protect. Measured while reinstalling the
    # kit across 19 consumers: four npm projects lost `deny: Read(**/.env*)`
    # along with their enabled languages, and the loss was silent.
    # The PROJECT's own skills sit in the same directory as the kit's, and this
    # branch is about to `rm -rf` it. `.kit-manifest.txt` is what tells the two
    # apart — it exists precisely because guessing by name is the alternative.
    # The merge branch never deletes; this one did, and measured on 2026-08-28
    # it took six `an adopter-*` skills out of `appteste` and six more out of
    # `website`, every one a versioned file the project wrote.
    #
    # Same shape as rules/*.txt, settings.json and the routing table before it:
    # a rule stated once and implemented on one of the two paths.
    SKILLS_KEEP=""
    # `$MANIFEST` is only assigned much later in this script, so it is spelled
    # out here rather than referenced — reading it before assignment made the
    # guard silently false and deleted the skills it exists to keep.
    # The glob below is `*` and not `*/` on purpose. The first version matched
    # DIRECTORIES only, so a project keeping a `SKILLS.md` index beside its skill
    # folders lost it on every reinstall while the folders survived. Measured
    # 2026-08-29 in `speculative`: 207 versioned lines, gone. It came back with
    # `git restore` only because that repository versions `.claude/`; a project
    # following the policy of not versioning it would have lost the file.
    #
    # Sixth face of one defect. The rule has been stated once and implemented for
    # one shape at a time — the routing table, `rules/*.txt`, `settings.json` by
    # key, project skill directories, `an adopter.md`, and now loose
    # files. Each fix was right and none generalised. The rule is: whatever the
    # SOURCE kit does not ship is the project's, whatever its shape.
    if [ "$item" = "skills" ] && [ -d "$ECO/skills" ]; then
      SKILLS_KEEP="$(mktemp -d "$STAGING/skills_keep.XXXXXX")"
      for d in "$ECO/skills"/* "$ECO/skills"/.[!.]*; do
        [ -e "$d" ] || continue
        name="$(basename "$d")"
        # In the source kit => the kit ships it => the fresh copy replaces it.
        [ -e "$SRC_DIR/skills/$name" ] && continue
        cp -r "$d" "$SKILLS_KEEP/"
      done
    fi

    CONFIG_KEEP=""
    if [ "$item" = "rules" ] && [ -d "$ECO/rules" ]; then
      CONFIG_KEEP="$(mktemp -d "$STAGING/config_keep.XXXXXX")"
      for f in "$ECO/rules"/*; do
        [ -f "$f" ] || continue
        base="$(basename "$f")"
        case "$base" in
          *.txt) kit_owns_txt "$base" && continue ;;
          # A `rules/*.md` the manifest does not list was written by the project.
          # `boundary-check.py` calls `rules/*.md` the kit's, which is true of the
          # ones the kit ships — and two consumers keep a `an adopter.md`
          # of their own beside them. Measured 2026-08-28: `--force` deleted it in
          # both, a versioned file in each case.
          *) [ -f "$SRC_DIR/rules/$base" ] && continue ;;
        esac
        cp "$f" "$CONFIG_KEEP/"
      done
    fi
    # ── the project's files, in ANY copied directory ────────────────────────
    #
    # This runs for every `item`, not for a chosen few, because the rule is not
    # about skills: whatever the SOURCE kit does not ship is the project's,
    # wherever it sits. That rule has now been stated once and implemented one
    # shape at a time seven times over — the routing table, `rules/*.txt`,
    # `settings.json` by key, project skill directories, `an adopter.md`,
    # loose files in `skills/`, and finally `hooks/` and `scripts/`, which had no
    # preservation pass at all.
    #
    # Measured by a consumer session on 2026-08-29 in `platform`: the
    # installer removed `hooks/delivery-gate.sh`, `hooks/lib/detect-layout.sh`,
    # `scripts/check-allowlist-sunsets.py` and `scripts/test_e2e_smoke.py`, none
    # of which exist in the kit. Two were gates that repository's pre-push
    # depends on. Nothing warned, and the install reported success.
    #
    # Ownership is decided by the SOURCE kit and not by `.kit-manifest.txt`,
    # which covers only `agents/`, `rules/` and `skills/` — for `hooks/` and
    # `scripts/` it is blind, so consulting it would answer by omission.
    OWN_KEEP=""
    if [ -d "$ECO/$item" ]; then
      OWN_KEEP="$(mktemp -d "$STAGING/own_keep.XXXXXX")"
      # Descend only where the kit also has a directory. A subtree the kit does
      # not ship is copied WHOLE and not walked — which is both correct and the
      # difference between finishing and not: one consumer keeps a `.venv` inside
      # a project skill, and walking it file by file made the install hang past
      # every timeout. `-maxdepth 1` per level, recursing by hand.
      _keep_own() {  # $1 = path relative to $item, "" at the top
        local rel="$1" src dst entry base
        src="$ECO/$item${rel:+/$rel}"
        for entry in "$src"/* "$src"/.[!.]*; do
          [ -e "$entry" ] || continue
          base="$(basename "$entry")"
          dst="${rel:+$rel/}$base"
          if [ ! -e "$SRC_DIR/$item/$dst" ]; then
            mkdir -p "$OWN_KEEP/$(dirname "$dst")"
            cp -a "$entry" "$OWN_KEEP/$dst"     # whole subtree, links intact
          elif [ -d "$entry" ] && [ ! -L "$entry" ]; then
            _keep_own "$dst"                     # the kit has it too — look inside
          fi
        done
      }
      _keep_own ""
    fi

    rm -rf "${ECO:?}/$item"
    copy_tree "$SRC_DIR/$item" "$ECO/$item"

    # Put them back, preserving their sub-paths. `hooks/lib/detect-layout.sh` is
    # two levels down, and a flat restore would have dropped it while reporting
    # success — the same class of half-fix as the glob before it.
    if [ -n "${OWN_KEEP:-}" ]; then
      if [ -n "$(ls -A "$OWN_KEEP" 2>/dev/null)" ]; then
        # `cp -a` the top-level entries back: each is either a loose file or a
        # whole subtree the kit does not ship, and both restore as one unit.
        for entry in "$OWN_KEEP"/* "$OWN_KEEP"/.[!.]*; do
          [ -e "$entry" ] || continue
          cp -a "$entry" "$ECO/$item/"
          echo "    kept (yours): $item/$(basename "$entry")"
        done
      fi
      rm -rf "$OWN_KEEP"
      OWN_KEEP=""
    fi

    # Restored right after the copy, outside every per-item conditional: an
    # earlier version sat inside `if [ "$item" = "rules" ]`, so it ran on the
    # wrong iteration and the skills were saved and never put back.
    if [ -n "${SKILLS_KEEP:-}" ]; then
      # `*` and `.[!.]*`, not `*/` — the same glob that dropped loose files on
      # the way OUT would drop them on the way back IN. Both ends of one pass had
      # the same assumption, so fixing either alone still lost the file.
      for d in "$SKILLS_KEEP"/* "$SKILLS_KEEP"/.[!.]*; do
        [ -e "$d" ] || continue
        cp -r "$d" "$ECO/skills/"
        echo "    kept (yours): skills/$(basename "$d")"
      done
      rm -rf "$SKILLS_KEEP"
      SKILLS_KEEP=""
    fi
    if [ "$item" = "rules" ]; then
      # Even on a clean install: project-specific config is born blank. Without
      # this, the non-merge branch copied the kit's own configuration (Python enabled,
      # the source ecosystem's own live target) and the consumer was born with it.
      for tpl in "$SRC_DIR"/rules/templates/*; do
        [ -f "$tpl" ] || continue
        [ "$(basename "$tpl")" = "domain-routing.md" ] && continue
        cp "$tpl" "$ECO/rules/$(basename "$tpl")"
      done
      # Back on top of the template: the consumer's tuning outranks the blank.
      if [ -n "$CONFIG_KEEP" ]; then
        for f in "$CONFIG_KEEP"/*; do
          [ -f "$f" ] || continue
          cp "$f" "$ECO/rules/$(basename "$f")"
          echo "    kept (yours): rules/$(basename "$f")"
        done
        rm -rf "$CONFIG_KEEP"
      fi
    fi
  fi
done


# --- migrate a pre-move routing table -----------------------------------------
# The table used to be a `## Domain routing` section inside the kit's own
# `cycle-backlog.md`. Consumers installed before the move still have it there.
#
# This runs at install time because that is the only moment the kit is inside the
# consumer with permission to write: a migration that asks the consumer to act is
# one most consumers never perform, and the ones that skip it are exactly those
# whose table is oldest.
#
# Only a NON-empty section migrates. Carrying the empty placeholder over would
# fabricate a derived table the project never derived — and the emptiness is what
# makes `/backlog-item` refuse items, which is correct while nobody has said who
# owns what.
migrate_routing_table() {
  # B-198 — the destination is RESOLVED inside the heredoc, from `squad.paths`, never composed
  # here. It used to be `"$ECO/rules/domain-routing.txt"`, which `rules/records-location.md`
  # retired: a reinstall then recreated the legacy path in a project that had already migrated,
  # and while both files exist the routing is silently correct — `.squad/` is read first — so
  # nothing reports the copy that will be read the day the newer one is removed.
  python3 - "${LEGACY_TABLE:-}" "$SRC_DIR" "$TARGET" <<'PYEOF'
import sys
from pathlib import Path

legacy_arg, kit, project = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, str(kit / "mechanisms" / "cycle"))
sys.path.insert(0, str(kit / "skills" / "backlog-init" / "scripts"))

sys.path.insert(0, str(kit))
from squad.paths import write_routing_table as _owner_destination  # noqa: E402
from route_domain import count_candidate_rows, parse_routing_table  # noqa: E402 — post-bootstrap
from detect_domains import (  # noqa: E402 — post-bootstrap
    Domain,
    domains_from_backlog,
    write_routing_table,
)

PARTIAL = []   # files whose table parsed only in part; reported, never written


def rows_from(path):
    """Domains from `path`, or [] — and [] also when the parse was PARTIAL.

    All or nothing per file. Measured on `website`: four domains — one
    repository, so the second column lists paths rather than checkouts — parsed
    to one, and writing that one out would have handed the consumer a third of
    their map in a file that reads as authoritative. Losing three rows silently
    is worse than migrating nothing, because nothing is visibly nothing.
    """
    if not path or not Path(path).is_file():
        return []
    content = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    try:
        table = parse_routing_table(Path(path))
    except (ValueError, OSError):
        if count_candidate_rows(content):
            PARTIAL.append(Path(path).name)
        return []
    rows = [
        Domain(name=name, repos=entry["repos"], agent=entry["agent"] or f"agents/{name}.md")
        for name, entry in table.items()
        if entry["repos"]
    ]
    candidates = count_candidate_rows(content)
    if candidates and len(rows) < candidates:
        PARTIAL.append(Path(path).name)
        return []
    return rows


# Already migrated? The consumer's file wins; never overwrite a derived table.
target = _owner_destination(project)
if rows_from(target):
    raise SystemExit(0)

# Source 1: the `## Domain routing` section as it stood before this install.
rows, origin = rows_from(legacy_arg), "cycle-backlog.md"

# Source 2: BACKLOG.md. Measured across five consumers: four had the rule's
# section at the `_(empty)_` placeholder and their REAL table — human-written,
# one of them 14 path-addressed entries — in BACKLOG.md, because
# `backlog-init`'s Step 3 told them to put it there while `route_domain.py`
# reads only the rule. `route_domain` exited 2 FATAL in four of four, over 165
# registered items.
#
# Migrating only from the rule would find nothing in exactly those four and hand
# them a fresh empty `domain-routing.txt` that READS as authoritative: broken by
# one mechanism becomes broken by two.
backlog = project / "BACKLOG.md"

# Source 2: the routing TABLE written into BACKLOG.md. Measured across five
# consumers: four had the rule at its empty placeholder and their real,
# human-checked table here — one with fourteen path-addressed entries — because
# `backlog-init`'s Step 3 said to put it here while `route_domain.py` reads only
# the rule. Four of four exited 2 FATAL, over 165 registered items.
if not rows and backlog.is_file():
    rows, origin = rows_from(backlog), "BACKLOG.md"

# Source 3: the (domain, repo) pairs the ITEMS declare. Weaker than a written
# table — it reports what has been FILED, not what exists — so it runs last.
#
# And never when a table was found and could not be fully read. Measured on
# `website`: four declared domains, five filed items, and deriving from the
# items produced ONE. Substituting the weaker source there presents a quarter of
# a declared map as the whole of it, which is the same failure as the partial
# parse, arriving through a different door.
if not rows and not PARTIAL and backlog.is_file():
    try:
        rows = domains_from_backlog(backlog, project)
        origin = "the items in BACKLOG.md"
    except (ValueError, OSError):
        rows = []

if not rows:
    # Nothing recognisable — but a table the parser cannot read is NOT the same
    # as no table, and treating them alike is how a consumer ends up with a fresh
    # empty file that reads as authoritative. Measured on `website`: a real,
    # human-written table in a shape the kit does not define (one repository, so
    # domains are areas of responsibility; two columns, no specialist). Inferring
    # a repo and a specialist from it would fabricate routing nobody wrote.
    if PARTIAL:
        print(f"    NOT migrated: {', '.join(sorted(set(PARTIAL)))} carries a routing table "
              "the kit can only read in part, and a partial map is worse than none")
        print("      derive it instead: python3 "
              ".claude/skills/backlog-init/scripts/detect_domains.py --root . \\")
        print("        --write")
    raise SystemExit(0)

write_routing_table(target, rows)
# The destination is PRINTED from the same value it was written to, never spelled again
# here. B-198 moved the write to whatever `squad.paths` resolves and left this line
# naming the old path, so the migration reported `rules/domain-routing.txt` while
# writing `.squad/domain-routing.txt`. A reader who went to check found the legacy
# placeholder the install had just recreated, read "(no domain yet)", and concluded the
# migration had lost their table — which is also exactly what
# `tests/test_clean_install.py` concluded, for the same reason.
print(f"    migrated: {target.relative_to(project)} — {len(rows)} domain(s) recovered from {origin}")
# A derived table routes to `agents/<domain>.md`, and route_domain exits 3 while
# that file is absent. "The migration found data" and "routing works" are
# different questions; say which one this answered.
missing = [d.agent for d in rows
           if not (project / ".claude" / d.agent).is_file() and not (project / d.agent).is_file()]
if missing:
    print("    routing is NOT yet resolvable — write these specialists (route_domain exits 3):")
    for agent in missing:
        print(f"      - {agent}")
PYEOF
  [ -n "${LEGACY_TABLE:-}" ] && rm -f "$LEGACY_TABLE"
  return 0
}

migrate_routing_table

# `rules/templates/` is installer input, not a rule. Leaving it in the consumer
# would make check_xrefs sweep files that govern nothing.
rm -rf "$ECO/rules/templates"

# `hooks/quality/` is THIS repository's smell gate, generated by `/quality-init`
# with thresholds calibrated on the p90 of the code here (max_file_lines = 367,
# and so on). Shipping it would repeat the defect the kit spent months fixing in
# `rules/*.txt` and in the routing table: distributing the author's configuration
# as if it were the installer's. The consumer generates its own with the same
# command, against its own numbers — step 3 of the closing instructions names it.
#
# GUARDED on the source. `hooks/quality/` is not in this repository's tree — `ls hooks/`
# has none and `tests/test_kit_manifest.py` asserts it is never listed — so this line
# deleted a consumer-owned directory the kit does not ship, which is the exact ownership
# rule stated twenty lines above. The guard makes the line refresh only what the
# installer actually carries.
if [ -e "$SRC_DIR/hooks/quality" ]; then
  rm -rf "$ECO/hooks/quality"
fi

# agents/ is copied FILE BY FILE, not wholesale. This repo dogfoods its own cycles, and
# `/implement` and `/review` write their per-run agent definitions into subdirectories here
# (`implement-slice-*/`, `review-*/`). Those are THIS repo's audit trail, not template content —
# and `cp -r` shipped two of them, dated May 2026, into every consumer install. The header above
# already promises to skip audit trails; this is what keeping that promise looks like.
# The kit has NO specialists to copy. The eight it used to carry described the
# repos of a single ecosystem; in a consumer that is not that ecosystem, they were
# files about repositories that do not exist there. Measured 2026-08-20 across 41
# installs: 19 already lived without them and nothing broke, 11 write their own,
# and the routing table became DERIVED from the project — the coupling that
# justified them ceased to exist. They were removed from the source on 2026-08-26;
# they were never versioned (`.gitignore agents/**`), so the
# `--with-domain-agents` flag copied files that existed only on the machine of
# whoever wrote them.
#
# The README always ships: it describes the routing MECHANISM, not a domain.
# `agents/` is NEVER deleted, in any mode. This is where the specialists the
# project wrote live — and `rm -rf` in non-merge mode took every one of them.
# Nothing in the kit justifies destroying a consumer's domain specialist: it
# describes their repository, it is a copy of nothing of ours, and it exists
# nowhere else.
mkdir -p "$ECO/agents"
if [ -f "$ECO/agents/README.md" ]; then
  # Once someone adapts it, this README lists the PROJECT's agents.
  echo "    kept (yours): agents/README.md"
elif [ -f "$SRC_DIR/agents/README.md" ]; then
  echo "==> Copying agents/README.md (the routing mechanism)"
  cp "$SRC_DIR/agents/README.md" "$ECO/agents/README.md"
fi

# The kit's OWN agents, by name. They are not domain specialists — they describe no
# repository and make no claim about the consumer's topology, which is the whole
# reason specialists cannot ship. These two are mechanism, like the README: they say
# what to do when the maintenance queue stops, and that is identical everywhere.
#
# Named explicitly rather than copied wholesale, so a specialist the project wrote
# can never be overwritten by a glob that grew.
for kit_agent in kairos-product-owner.md iris-product-designer.md daedalus-tech-lead.md hermes-scrum-master.md vera-technical-arbiter.md clio-historian.md metis-oracle.md leonardo-researcher.md eureka-defect-hunter.md hecate-intake-triager.md vigil-sentinel.md aesculapius-healer.md argus-pattern-analyst.md nemesis-claim-auditor.md; do
  if [ -f "$SRC_DIR/agents/$kit_agent" ]; then
    cp "$SRC_DIR/agents/$kit_agent" "$ECO/agents/$kit_agent"
    echo "    agents/$kit_agent"
  fi
done
# Top-level docs and manifest.
#
# Declared ONCE, because two readers need the same answer: this loop, which
# copies them, and the manifest writer, which must name them. The manifest
# enumerated `skills/`, `rules/`, `agents/` and four directories and listed no
# loose file at all — so at the kit root it answered by omission, which its own
# header promises it never does. `squad/boundaries.py` reads that manifest to
# decide who owns a path; with the root omitted it had to fall back on "inside
# the kit directory, therefore the kit's", and claimed three files belonging to
# other plugins (`code-review-loop.local.md` and two siblings, measured on a
# consumer 2026-09-18). Separate lists in the two places would let the same gap
# reopen one file at a time.
KIT_LOOSE_FILES="HOW-TO-USE.md README.md .active_plan.example"
for f in $KIT_LOOSE_FILES; do
  [ -f "$SRC_DIR/$f" ] && cp "$SRC_DIR/$f" "$ECO/$f"
done
# The manifest has ONE canonical place — `.claude-plugin/plugin.json`, where
# Claude Code looks for it. There used to be a second copy at the root, and two
# copies of a manifest diverge: the root one was what the README pointed at and
# what this script installed, while the native mechanism read the other.
[ -f "$SRC_DIR/.claude-plugin/plugin.json" ] && cp "$SRC_DIR/.claude-plugin/plugin.json" "$ECO/plugin.json"

# --- settings.json (plugin install variant) ---
if [ ! -f "$SRC_DIR/settings.plugin.json" ]; then
  echo "ERROR: $SRC_DIR/settings.plugin.json missing — required for plugin install layout." >&2
  exit 1
fi
if [ ! -f "$SRC_DIR/mechanisms/distribution/merge_settings.py" ]; then
  echo "ERROR: $SRC_DIR/mechanisms/distribution/merge_settings.py missing — the settings" >&2
  echo "  merge cannot run, and copying over the consumer's file would delete their" >&2
  echo "  hooks and permissions. Refusing rather than overwriting." >&2
  exit 1
fi
# ONE path, not two. The fresh-install branch used to `cp settings.plugin.json` and
# skip the merge — which also skipped the two baselines the merge writes, because
# they are written by it. So a freshly installed consumer had no record of what the
# kit shipped, and the FIRST hook it removed from settings.json came back on the
# next install; the install after that respected the removal, once a merge had
# finally written the baseline. A rule that starts working on the second attempt is
# one nobody can rely on and nobody can explain.
#
# Seeding `{}` and merging produces the kit's settings exactly — measured: same 108
# deny rules, same hooks, differing only in the order of `deny`, and the merge is
# idempotent, so a fresh consumer now holds byte-for-byte what a reinstalled one
# holds. Before this they differed, and nothing said so.
[ -f "$ECO/settings.json" ] || printf '{}\n' > "$ECO/settings.json"
# One file, two owners — and replacing it wholesale was wrong in both
# directions. `boundary-check.py` allowlists `settings.json` as "this project's
# wiring", so the kit invites the consumer to edit it; then `--force` copied
# its own over the top. Measured across four npm consumers: `deny:
# Read(**/.env*)` gone, along with their `vitest`/`tsc` allowances. The kit
# widened what an agent may read in someone else's repository, silently.
#
# Keeping the consumer's file whole — what `--merge` did — has the opposite
# failure: `hooks` points at the kit's scripts, and a stale hook stops
# enforcing without ever saying so.
#
# So ownership is split by key. The kit owns its wiring; the project owns its
# permissions; a key the kit does not know is the consumer's and survives.
# The merge itself lives in `merge_settings.py`, not in a heredoc here. It was
# 100 lines inside this file, so nothing could run it and nothing did — and it
# shipped a wholesale `mine["hooks"] = kit["hooks"]` that deleted a consumer's
# own hook wiring on every run while carefully preserving the hook's FILE (#34).
# A gate present on disk and wired to nothing reads as installed to everyone.
python3 "$SRC_DIR/mechanisms/distribution/merge_settings.py" \
    "$ECO/settings.json" "$SRC_DIR/settings.plugin.json"
echo "==> settings.json merged (kit wiring refreshed; your hooks and permissions kept)"

# --- records scaffold (empty, idempotent) ---
# Mirrors the SEMANTIC structure of the source's records/ — every
# category folder that a cycle writes to. Slug-keyed subdirs that exist in
# the source (e.g. implementations/slice-X/, tools/argo-cd/, discoveries/
# snapshots/slice-X/) are NOT mirrored — those are historical artefacts of
# the plan repo's own honesty-gate, not part of the template.
echo "==> Naming the write-root subdirs (semantic structure)"
KB_DIRS=(
  "plans"                       # /plan-write outputs
  "implementations"             # /implement halt-loop logs
  "reviews"                     # /review reports
  # `cycle-release.md` § Output names `records/releases/{version}-release.md`,
  # and `squad_boss.HALT_DIRS` watches the directory for BLOCKED reports — it
  # was the only one of the eleven that nothing here created.
  "releases"                    # /release run records, one per cut version
  "audits"                      # /code-quality + /deps-audit reports
  "acceptance"                  # /acceptance records (end-user validation of a release)
  "acceptance/evidence"         # screenshots, console/network dumps, transcripts
  "maintenance-runs"            # per-item macro-loop audit trail
  "backlog"                     # /backlog-item intake logs
  "honesty-gate"                     # /honesty-gate anchor manifest
  "honesty-gate/evidence"            # /honesty-gate evidence files
  "judge-codex"                 # orthogonal LLM jury outputs (optional plugin)
  "tools"                       # read-only docs of tools the project depends on (consumer populates)
  "discoveries"                 # /discover-* root
  "discoveries/plans"           # /discover-plan outputs
  # The TERMINAL artifact of DISCOVER, documented by `HOW-TO-USE.md` and resolved by
  # `squad/paths.py` — and the one directory nothing here created, so the phase's own
  # output had nowhere to land on a fresh install.
  "discoveries/opportunities"   # /discover-execute outputs
  "discoveries/snapshots"       # hash-verified snapshots cited by opportunities
  # `skills/plan-write/SKILL.md` reads `records/grills/{slug}-grill.md` before writing a plan.
  "grills"                      # requirement-grilling transcripts a plan cites
  "progress"                    # per-slug progress.md (read by hooks + session-catchup)
  "sop-runs"                    # run records: what one machine did following a procedure
  "brainstorms"                 # one record per product-alignment session, discards included
)

# EVERYTHING this system writes goes under `<project>/.squad/`, never into `$ECO`.
# `$ECO` is the installed dependency; `.squad/` is what the system produces, and
# nothing executes from it. Keeping them apart is what lets a project un-version the
# dependency without un-versioning its own records — measured across 20 consumers, 17
# had the kit committed and every one carried 348-566 permanently dirty files, all of
# them inside the install directory. See `squad/paths.py`.
# Shell cannot import `squad/paths.py`, so it ASKS it rather than restating the root.
# One owner, two languages.
DATA_ROOT_NAME="$(python3 -c "import sys; sys.path.insert(0, '$SRC_DIR'); from squad.paths import DATA_DIRNAME; print(DATA_DIRNAME)" 2>/dev/null)"
if [ -z "$DATA_ROOT_NAME" ]; then
  echo "FATAL: cannot read the write root from squad/paths.py — refusing to guess it" >&2
  exit 2
fi
DATA_ROOT="$TARGET/$DATA_ROOT_NAME"
echo "==> Scaffolding the write root at $DATA_ROOT"

# The OKF bundle: durable knowledge, separate from the dated trail above.
# `rules/sop-schema.md` and docs/wiki/decisions/where-knowledge-lives.md say why.
for d in sops decisions references opportunities product; do
  mkdir -p "$DATA_ROOT/wiki/$d"
done
for d in "${KB_DIRS[@]}"; do
  mkdir -p "$DATA_ROOT/records/$d"
done

# agents/ holds only the README above. The routing table is born empty beside the rest
# of the write root, so route_domain.py has nothing to resolve until the project derives
# both — a table with rows and no specialist on disk is what exit 3 (BROKEN ROUTE)
# exists to catch.
#
# AT THE DESTINATION, not under `rules/`. `squad.paths` has written the table to the
# write root since 2026-09-11 while this script went on copying a placeholder to
# `rules/domain-routing.txt` — the one directory no writer fills — and recreating it on
# every reinstall. The path is RESOLVED from the owner rather than spelled here, for the
# reason B-198 gave when the migration made the same mistake: a literal here is a copy,
# and a copy is how the two answers drift apart.
if [ ! -f "$DATA_ROOT/domain-routing.txt" ]; then
  python3 - "$TARGET" <<'ROUTEEOF'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
project = Path(sys.argv[1])
for up in [project, *project.parents]:
    if (up / "squad" / "paths.py").is_file():
        sys.path.insert(0, str(up))
        break
else:
    sys.path.insert(0, str(Path.cwd()))
try:
    from squad.paths import write_routing_table
except ImportError:
    raise SystemExit(0)
target = write_routing_table(project)
target.parent.mkdir(parents=True, exist_ok=True)
if not target.exists():
    target.write_text(
        "# Domain routing — WHICH REPOSITORIES EXIST HERE, and who owns each.\n"
        "#\n"
        "# This file is the PROJECT'S, not the kit's: the installer never overwrites it.\n"
        "# Derive it with `detect_domains.py --write`, which resolves this destination\n"
        "# itself rather than being told where to put it.\n"
        "#\n"
        "# Format: domain | repos (comma-separated) | specialist agent file\n"
        "\n"
        "# (no domain yet — run detect_domains.py --write)\n",
        encoding="utf-8")
ROUTEEOF
fi


# --- What the overwrite actually took ---
# A snapshot nobody is told about is a snapshot nobody uses. Naming the files that CHANGED (not
# every file, which would be noise) is what turns a silent clobber into a diff someone can act on.
if [ -n "$BACKUP_DIR" ]; then
  CLOBBERED=$(
    cd "$BACKUP_DIR" && find . -type f | while read -r f; do
      cmp -s "$f" "$ECO/${f#./}" || echo "  ${f#./}"
    done
  )
  if [ -n "$CLOBBERED" ]; then
    echo ""
    # "or REMOVED" is not hedging: a specialist the source repo does not have — which is every
    # specialist a consumer writes for its own domains — is not overwritten, it is deleted by the
    # `rm -rf` above. Calling that "overwritten" would understate what just happened.
    echo "==> These files were OVERWRITTEN or REMOVED (they differed from the source):"
    echo "$CLOBBERED"
    echo ""
    echo "    Your previous copies: $BACKUP_DIR"
    echo "    Nothing was merged — diff them and re-apply what is yours. Project config lives in"
    echo "    rules/*.txt, the routing table in rules/domain-routing.txt (or"
    echo "    .squad/domain-routing.txt under this install), and agents/*.md."
    echo "    This line said cycle-backlog.md until 2026-09-17. The table moved, and"
    echo "    cycle-backlog.md is kit-owned — an operator recovering their routing into it"
    echo "    is refused by boundary-check and loses the file they were trying to restore."
    echo "    To upgrade WITHOUT clobbering next time, use patch_install.sh instead."
  fi
fi

# --- Validation ---
# Run FROM THE TARGET. verify_ecosystem.py resolves the ecosystem from the CWD, and the normal way
# to invoke this script is `cd squad && bash mechanisms/distribution/install.sh <target>` — so it was validating
# the source repo and printing OK for the installation it never opened. Measured: with a routed
# specialist and a cycle rule deleted from a fresh install, it answered
# `ecosystem: <workspace>/squad` / `ALL CHECKS PASSED` / exit 0. A check that cannot
# fail is worse than no check: it puts a green line next to a broken install.
#
# check_xrefs.py resolves from its own path and caught the same corruption (exit 1). Two lines
# printed the same word for two different amounts of verification.
# --- manifest: what came from the kit ----------------------------------------
# A consumer with an auditor of its own needs to tell what it wrote from what
# was installed. Measured on `speculative`: its `scripts/audit.py` walks
# `.claude/skills/*/SKILL.md` against the Agent Skills spec; with the kit installed
# it went from PASS to FAIL, auditing 37 skills that are not the project's
# against the standard of the 9 that are. Without a manifest, the only way out
# would be guessing by name. The PROJECT's skills never enter here — the list
# comes from the kit's tree.
MANIFEST="$ECO/.kit-manifest.txt"
# The header used to promise "anything not here is the project's" while listing
# only `agents/`, `rules/` and `skills/` — 92 entries, none for `hooks/` or
# `scripts/`. For those two the manifest answered by OMISSION, which is worse
# than not answering: a reader concludes the project owns a kit file, or the kit
# owns a project file, and both readings look supported. A peer session reviewing
# this on 2026-08-29 reported doing exactly that.
#
# Now it lists every file of every copied directory, so the sentence is true.
{
  echo "# Written by mechanisms/distribution/install.sh — what THIS kit brought into .claude/."
  echo "# One path per line, relative to .claude/. Anything not here is the project's."
  echo "# Covers every directory the installer copies; nothing answers by omission."
  echo "# Regenerated on every install; do not edit by hand."
  # The source this copy came from, so `check_install_drift` can compare
  # without anyone exporting SQUAD_KIT_SOURCE. Before this, the drift gate
  # was wired and inert: a consumer had to read hooks/sessionstart-context.py
  # to learn a variable existed (#23). A `#`-prefixed line, so every existing
  # reader — which all skip comments — is unaffected.
  echo "# kit-source: $SRC_DIR"
  # WHICH version, not only which directory. The path answered "where did this
  # come from" and nothing answered "what is this" — so an installed kit could not
  # say which version it was, and `sync_consumers.py` needs exactly that as its
  # `--base`. Measured 2026-09-16 across 55 consumers: three distinct contents, and
  # NONE of them matched any commit in the kit's history. Every one was installed
  # from a dirty working tree, so the only classification the sync tool could reach
  # was LOCAL_CHANGE — it refused all 55, correctly and uselessly.
  #
  # The dirty flag is recorded rather than refused. An install from a working tree
  # is how this kit is developed, and forbidding it would stop the loop that finds
  # the defects; saying so lets the sync tool tell a fossil from a release.
  if command -v git >/dev/null 2>&1 && git -C "$SRC_DIR" rev-parse --git-dir >/dev/null 2>&1; then
    _sha="$(git -C "$SRC_DIR" rev-parse HEAD 2>/dev/null || echo unknown)"
    if [ -n "$(git -C "$SRC_DIR" status --porcelain --untracked-files=no 2>/dev/null)" ]; then
      echo "# kit-commit: $_sha (dirty — this install does not match that commit)"
    else
      echo "# kit-commit: $_sha"
    fi
  else
    echo "# kit-commit: unknown (source is not a git checkout)"
  fi
  # `skills/` stays one entry per SKILL and `rules/` one per file — that is the
  # granularity every existing reader expects, and changing it broke three tests
  # that had nothing to do with the gap being closed.
  for d in "$SRC_DIR"/skills/*/; do
    [ -f "$d/SKILL.md" ] && echo "skills/$(basename "$d")"
  done
  for f in "$SRC_DIR"/rules/*; do
    [ -f "$f" ] && echo "rules/$(basename "$f")"
  done
  [ -f "$SRC_DIR/agents/README.md" ] && echo "agents/README.md"
  # `hooks/`, `commands/` and `scripts/` had NO entries at all, so for those the
  # manifest answered by omission — the gap this closes. Listed per file, because
  # they have no unit above the file the way a skill does.
  # `agents/` carries BOTH: the kit's four roles and the project's domain
  # specialists, which the kit never writes. Only the four are listed, so a reader
  # of the manifest can tell them apart — before this the manifest held
  # `agents/README.md` alone, and `check_squad_map` could not tell a kit role from
  # a specialist, so it asked the map to name agents it has no business knowing.
  if [ -d "$SRC_DIR/agents" ]; then
    # README is listed elsewhere; emitting it here too would duplicate the row.
    ( cd "$SRC_DIR/agents" && find . -maxdepth 1 -name '*.md' \
        -not -name 'README.md' -print ) \
      | sed 's|^\./|agents/|' | sort
  fi

  for item in hooks commands mechanisms squad; do
    [ -d "$SRC_DIR/$item" ] || continue
    ( cd "$SRC_DIR/$item" && find . -mindepth 1 \( -type f -o -type l \) \
        -not -path "*/__pycache__/*" -print ) \
    | sed "s|^\./|$item/|" | sort
  done

  # The kit root. Everything above lives in a directory the kit owns outright, so
  # a reader could infer ownership from the first path segment; at the root there
  # is no segment to infer from, and the kit shares that directory with every
  # other plugin the project installs. These are the only loose files that are
  # the kit's, and naming them is what lets `is_project_owned` answer "not mine"
  # for the rest instead of claiming the whole directory.
  for f in $KIT_LOOSE_FILES; do
    [ -f "$ECO/$f" ] && echo "$f"
  done
  # Written from `.claude-plugin/plugin.json`, so it is not in the loose list.
  [ -f "$ECO/plugin.json" ] && echo "plugin.json"
  # Provenance the installer itself writes: what the kit SHIPPED last time, which
  # `merge_settings.py` needs to tell a retired rule from a project's own. Not
  # copied from the source, and not the project's to edit either.
  for f in .kit-hooks.json .kit-permissions.json; do
    [ -f "$ECO/$f" ] && echo "$f"
  done
} > "$MANIFEST"
echo "==> Manifest written: $(grep -vc '^#' "$MANIFEST") paths from the kit"

# The reason a validator failed is KEPT, and a failure decides the exit status. Both ran
# with `> /dev/null 2>&1` — so the one output that says what is wrong with the install was
# destroyed — and neither branch set a status, so the script printed
# "Installation complete." and exited 0 whether they passed or failed. An installer that
# reports success over a broken install is worse than one that does not check.
echo "==> Validating install (from the target, not from here)"
VALIDATION_LOG="$ECO/.install-backups/validation-$(date -u +%Y%m%dT%H%M%SZ).log"
mkdir -p "$(dirname "$VALIDATION_LOG")"
VALIDATION_FAILED=0

# `check_wired_hooks.py` joined on 2026-09-21, routed by a consumer whose install
# predated `260892f`: it still had `hooks/validate-command.sh` WIRED, and that retired
# shell hook diverges from the live Python one in 2 of 36 payloads — both permissively,
# allowing `git stash` and `--force-with-lease` on the workspace. `.kit-hooks.json` could
# not withdraw it because that baseline only exists from 2026-09-02; a missing FILE needs
# no baseline.
for _gate in "check_xrefs.py --strict" "verify_ecosystem.py" "check_wired_hooks.py --root .claude"; do
  # shellcheck disable=SC2086
  # Unquoted on purpose: `$_gate` carries the script name AND its flag.
  if (cd "$TARGET" && python3 .claude/mechanisms/gates/$_gate) >> "$VALIDATION_LOG" 2>&1; then
    echo "    ${_gate%% *}: OK"
  else
    VALIDATION_FAILED=1
    echo "    ${_gate%% *}: FAIL — last lines:"
    tail -n 12 "$VALIDATION_LOG" | sed 's/^/      /'
  fi
done
echo "    validation log: $VALIDATION_LOG"

# The two validators above import modules from the target, and the interpreter
# writes `__pycache__` while doing so. Without this, the step that confirms the
# install is the one that dirties it again.
prune_caches "$ECO"

cat <<EOF

==> Installation complete.

Next steps for the target project:

  1. (optional) Add a CLAUDE.md at the project root pointing to .claude/ and
     listing project-specific stack/conventions. Hooks read it on SessionStart.

  2. Derive the domain routing table FOR THIS PROJECT (it ships EMPTY, and gate
     G1 refuses every item until this runs):
       python3 .claude/skills/backlog-init/scripts/detect_domains.py --root . \
         --write
     Then write the specialist file(s) it names under .claude/agents/.

  3. Configure project-specific gates (defaults are no-op until set):
       .claude/rules/code-quality-languages.txt    # uncomment languages you ship
       .claude/rules/discover-web-allowlist.txt    # domains for /discover-execute
       .claude/rules/code-quality-thresholds.txt   # per-project overrides
       .claude/rules/deps-audit-allowlist.txt      # CVE exemptions (with sunset)

  4. Verify ralph-loop plugin is installed (required by /implement, /discover-execute,
     /plan-improve):
       jq '.enabledPlugins' ~/.claude/settings.json | grep ralph-loop

  5. Open the project in Claude Code. The settings.json wires hooks; skills/
     and commands/ are auto-discovered.

  6. Agree what the product IS — the one cycle that needs a person, and the reason
     every phase after it may run unattended:
       /brainstorm-vision  ->  /brainstorm-objectives
         ->  /brainstorm-trd  ->  /brainstorm-pieces
     Four documents land in wiki/product/ and the last one runs the gate: 90% on
     the rubric AND your signature. A judge cannot sign this one.

     Skippable for a repo that predates the cycle — /backlog-init still runs, and
     says out loud that it had no product documents to check the inventory against.

  7. Create the registry: /backlog-init  (reads those four as context, seeds zero
     items — an objective is not a why_now)

  8. First item: /backlog-item, or /plan-write "{one-sentence feature}"

  BEFORE you ever clean out .claude/ by hand — ask which files are YOURS:
       python3 .claude/mechanisms/gates/check_install_drift.py \
         --install .claude --kit <path-to-the-kit> --consumer-local
     It lists every file this install holds that the kit does not ship: a push gate
     the project wrote, a per-review directory /review generated. A cleanup that
     deletes "old kit leftovers" cannot tell those from the kit's own obsolete files
     — that is how one consumer's delivery-gate.sh was deleted three times (kit#33).

  The 360º view — every phase, who owns it, and what it reads:
    .claude/rules/squad-map.md
  A compact form of it is injected at every SessionStart, so an agent starting
  work already knows the chain and the four roles.
EOF

# The exit status carries the validation. Printing "Installation complete." and exiting 0
# over a failed check is the installer reporting success about a state it just measured
# as broken — the files ARE installed, which is why this is exit 1 and not exit 2, but a
# caller scripting the install must be able to see the difference.
if [ "${VALIDATION_FAILED:-0}" -ne 0 ]; then
  echo "" >&2
  echo "==> The files are installed AND the post-install validation reported a FAILURE." >&2
  echo "    See $VALIDATION_LOG. Nothing above is a claim that this install works." >&2
  # WHICH failures decide the status: the ones whose subject is what this script just
  # WROTE. Two gates grade content the installer neither authored nor can fix, and both
  # are reported above and in the log either way:
  #
  #   Contribution conventions   the CONSUMER's last 40 commits. A fresh `git init` fails
  #                              it on its first commit, and so does any project whose
  #                              history does not follow this kit's header shape.
  #   Skill map                  the consumer's OWN skills sitting beside the kit's. A
  #                              project-authored skill has no row in the kit's `map.md`
  #                              and never will — that file is the kit's inventory.
  #   Skill frontmatter          the same tree. A consumer's malformed SKILL.md is a real
  #                              defect and is REPORTED, but it is the project's file to
  #                              fix, not evidence that the copy failed.
  #
  # What this does NOT weaken: CI runs all three over the KIT itself, where a broken
  # frontmatter or a missing map row fails the build. The exclusion is scoped to
  # install time, where the same gates also see files the installer did not write.
  #
  # Letting either decide would mean every honest install into a real project exits
  # non-zero for a reason that has nothing to do with the install. Every OTHER failure is
  # about the ecosystem this script wrote, and does decide.
  #
  # `grep -c` PRINTS 0 and EXITS 1 when nothing matches, so `|| echo 0` used to append a
  # second zero and the arithmetic saw "0\n0". grep+wc has one behaviour for both cases.
  _all_failures=$(grep '^✗' "$VALIDATION_LOG" 2>/dev/null | wc -l | tr -d ' ')
  _consumer_subject=$(grep -E '^✗ (Contribution conventions|Skill map|Skill frontmatter)' \
    "$VALIDATION_LOG" 2>/dev/null | wc -l | tr -d ' ')
  if [ "$(( _all_failures - _consumer_subject ))" -gt 0 ]; then
    exit 1
  fi
  echo "    Every failure grades THIS PROJECT's own content — its commit history, or its" >&2
  echo "    own skills beside the kit's — rather than what the installer wrote. Reported," >&2
  echo "    not treated as an install failure. Everything the installer wrote validated." >&2
fi
