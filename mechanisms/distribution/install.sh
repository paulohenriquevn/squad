#!/usr/bin/env bash
# Installs the Squad maintenance ecosystem into a target project as a plugin install
# (target/.claude/ layout). Hooks auto-detect the layout, so target/.claude/* is
# picked up identically to the standalone repo.
#
# Usage:
#   bash mechanisms/distribution/install.sh <target-project-dir> [--force]
#
# What it does:
#   1. Validates target is a directory.
#   2. Refuses to overwrite an existing target/.claude/ unless --force.
#   3. Copies skills/, rules/, hooks/, commands/, mechanisms/, squad/, plugin.json,
#      HOW-TO-USE.md into target/.claude/.
#   4. Writes settings.plugin.json as target/.claude/settings.json.
#   5. Creates empty scaffold under target/.claude/records/
#      (plans, implementations, reviews, audits, discoveries/{plans,opportunities,snapshots},
#      adrs, grills, honesty-gate, judge-codex, backlog, maintenance-runs, tools).
#      agents/ receives ONLY README.md (the routing mechanism). Specialists are
#      derived per project — the kit ships none. agents/ is never deleted.
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
for arg in "${@:2}"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --merge) MERGE=1 ;;
    "") ;;
    *) echo "ERROR: unknown flag ${arg}. Expected --force or --merge." >&2; exit 2 ;;
  esac
done

if [ ! -d "$TARGET" ]; then
  echo "ERROR: target is not a directory: $TARGET" >&2
  exit 2
fi

TARGET="$(cd "$TARGET" && pwd)"
ECO="$TARGET/.claude"

if [ "$TARGET" = "$SRC_DIR" ]; then
  echo "ERROR: target is the source repo itself. install.sh is for installing the ecosystem INTO another project." >&2
  exit 2
fi

if [ -d "$ECO" ] && [ "$FORCE" -ne 1 ] && [ "$MERGE" -ne 1 ]; then
  echo "ERROR: $ECO already exists." >&2
  echo "  --merge  add the kit's files, delete nothing. Use this when the target has a .claude/ of" >&2
  echo "           its own (project skills, project agents) that must survive." >&2
  echo "  --force  replace skills/rules/hooks/commands/mechanisms/squad/agents wholesale. Snapshots first" >&2
  echo "           and names what it overwrote, but anything the source does not have is DELETED." >&2
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
if [ -d "$ECO" ]; then
  BACKUP_DIR="$ECO/.install-backups/$(date +%Y%m%dT%H%M%S)"
  mkdir -p "$BACKUP_DIR"
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

# --- tabela de roteamento: entregue VAZIA ------------------------------------
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
      SKILLS_KEEP="$(mktemp -d)"
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
      CONFIG_KEEP="$(mktemp -d)"
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
      OWN_KEEP="$(mktemp -d)"
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
      # this, the non-merge branch copied the kit's own configuration (Python
      # enabled,
      # alvo vivo do ecossistema de origem) e o consumidor nascia com ela.
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
  local target="$ECO/rules/domain-routing.txt"
  python3 - "${LEGACY_TABLE:-}" "$target" "$SRC_DIR" "$TARGET" <<'PYEOF'
import sys
from pathlib import Path

legacy_arg, target, kit, project = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
sys.path.insert(0, str(kit / "mechanisms" / "cycle"))
sys.path.insert(0, str(kit / "skills" / "backlog-init" / "scripts"))

from route_domain import count_candidate_rows, parse_routing_table  # noqa: E402
from detect_domains import (  # noqa: E402
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
        print("        --write .claude/rules/domain-routing.txt")
    raise SystemExit(0)

write_routing_table(target, rows)
print(f"    migrated: rules/domain-routing.txt — {len(rows)} domain(s) recovered from {origin}")
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
rm -rf "$ECO/hooks/quality"

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
for kit_agent in kairos-product-owner.md iris-product-designer.md daedalus-tech-lead.md hermes-scrum-master.md; do
  if [ -f "$SRC_DIR/agents/$kit_agent" ]; then
    cp "$SRC_DIR/agents/$kit_agent" "$ECO/agents/$kit_agent"
    echo "    agents/$kit_agent"
  fi
done
# Top-level docs and manifest
for f in HOW-TO-USE.md README.md .active_plan.example; do
  [ -f "$SRC_DIR/$f" ] && cp "$SRC_DIR/$f" "$ECO/$f"
done
# The manifest has ONE canonical place — `.claude-plugin/plugin.json`, where
# Claude Code looks for it. There used to be a second copy at the root, and two
# copies of a manifest diverge: the root one was what the README pointed at and
# what this script
# instalava, enquanto o mecanismo nativo lia a outra.
[ -f "$SRC_DIR/.claude-plugin/plugin.json" ] && cp "$SRC_DIR/.claude-plugin/plugin.json" "$ECO/plugin.json"

# --- settings.json (plugin install variant) ---
if [ ! -f "$SRC_DIR/settings.plugin.json" ]; then
  echo "ERROR: $SRC_DIR/settings.plugin.json missing — required for plugin install layout." >&2
  exit 1
fi
if [ -f "$ECO/settings.json" ]; then
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
  python3 - "$ECO/settings.json" "$SRC_DIR/settings.plugin.json" <<'PYEOF'
import json, os, sys

target, source = sys.argv[1], sys.argv[2]
mine = json.load(open(target, encoding="utf-8-sig"))
kit = json.load(open(source, encoding="utf-8"))

# Keys the KIT owns: they wire the kit's own scripts, and a stale copy is a gate
# that quietly stopped running.
for key in ("hooks", "statusLine", "env", "$schema", "_comment_",
            "skipDangerousModePermissionPrompt"):
    if key in kit:
        mine[key] = kit[key]

# `permissions` is the project's. The kit's are a floor, not a replacement:
# union, with the consumer's kept. `deny` goes first because an entry that
# forbids must be read before one that allows.
#
# The LIST keys work that way. The scalar ones do not, and the difference cost a
# defect: the loop below used to `continue` on anything that was not a list, so
# `defaultMode` — a string — was skipped in silence. A change to it in the
# template would have reached only consumers with no settings.json yet, and none
# of the seventeen that already had one: applied, shipped, inert.
#
# `defaultMode` is the kit's POSTURE, not the project's preference, so the kit
# owns it. A consumer that wants a different one sets it in
# `.claude/settings.local.json`, which the harness reads at higher precedence —
# the mechanism built for exactly this, rather than a merge rule nobody can see.
_KIT_OWNED_SCALARS = ("defaultMode",)

# A union cannot retire a rule. Additions propagated and removals did not, so
# every entry the kit ever shipped stayed in every consumer that already had a
# settings.json — a retirement that is applied, released and inert everywhere but
# a fresh install. Same shape `defaultMode` had, in the other direction.
#
# It is not fixable by comparing two lists: a rule in the consumer and not in the
# kit is EITHER something the kit retired OR something the project added, and
# those must not share an outcome. The missing term is the base — what the kit
# shipped last time — so the install records it.
#
# Measured on 2026-09-02: the credential globs were rewritten from
# `Read(**/*secret*)` to named credential forms, and without this the old glob
# would have stayed denied in all seventeen consumers alongside the new ones.
_PROVENANCE = os.path.join(os.path.dirname(target), ".kit-permissions.json")
try:
    with open(_PROVENANCE, encoding="utf-8") as _fh:
        _previous = json.load(_fh)
except (OSError, ValueError):
    _previous = {}

# The declared half. A rule the kit withdrew is named in `rules/retired-permissions.txt`
# and removed on every run, base or no base — which is what makes the FIRST
# install under this scheme able to migrate at all.
_declared_retired = set()
try:
    # `source` is `<kit>/settings.plugin.json`; the heredoc is quoted, so shell
    # variables do not reach here and the kit root is derived from what does.
    with open(os.path.join(os.path.dirname(source), "rules",
                           "retired-permissions.txt"), encoding="utf-8") as _fh:
        _declared_retired = {ln.strip() for ln in _fh
                             if ln.strip() and not ln.lstrip().startswith("#")}
except OSError:
    pass

merged = mine.setdefault("permissions", {})
_retired_total = 0
for _key, _list in merged.items():
    if isinstance(_list, list):
        for _rule in list(_list):
            if _rule in _declared_retired:
                _list.remove(_rule)
                _retired_total += 1
for key, items in kit.get("permissions", {}).items():
    if not isinstance(items, list):
        if key in _KIT_OWNED_SCALARS:
            merged[key] = items
        continue
    target_list = merged.setdefault(key, [])

    # Retire only what the kit itself shipped last time and ships no longer.
    # With no record (first install under this scheme) nothing is removed —
    # every existing entry is indistinguishable from a project's own, and
    # deleting a project's rule is the worse error by far.
    retired = [r for r in _previous.get(key, []) if r not in items]
    for rule in retired:
        if rule in target_list:
            target_list.remove(rule)
            _retired_total += 1

    for item in items:
        if item not in target_list:
            target_list.insert(0, item) if key == "deny" else target_list.append(item)

# The base for next time: what the kit shipped now, not what the consumer ended
# up with. Recording the merged result would make every project rule look like
# the kit's and hand the next install permission to delete it.
_kit_lists = {k: v for k, v in kit.get("permissions", {}).items() if isinstance(v, list)}
with open(_PROVENANCE, "w", encoding="utf-8") as _fh:
    json.dump(_kit_lists, _fh, indent=2)
    _fh.write("\n")
if _retired_total:
    print(f"    {_retired_total} permission rule(s) retired by the kit were removed")

json.dump(mine, open(target, "w", encoding="utf-8"), indent=2)
open(target, "a", encoding="utf-8").write("\n")
PYEOF
  echo "==> settings.json merged (kit wiring refreshed, your permissions kept)"
else
  cp "$SRC_DIR/settings.plugin.json" "$ECO/settings.json"
  echo "==> settings.json written (plugin install variant)"
fi

# --- records scaffold (empty, idempotent) ---
# Mirrors the SEMANTIC structure of the source's records/ — every
# category folder that a cycle writes to. Slug-keyed subdirs that exist in
# the source (e.g. implementations/slice-X/, tools/argo-cd/, discoveries/
# snapshots/slice-X/) are NOT mirrored — those are historical artefacts of
# the plan repo's own honesty-gate, not part of the template.
echo "==> Scaffolding records/ subdirs (semantic structure)"
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
  "discoveries/snapshots"       # hash-verified snapshots cited by opportunities
  "progress"                    # per-slug progress.md (read by hooks + session-catchup)
  "sop-runs"                    # run records: what one machine did following a procedure
  "brainstorms"                 # one record per product-alignment session, discards included
)

# The OKF bundle: durable knowledge, separate from the dated trail above.
# `rules/sop-schema.md` and wiki/decisions/where-knowledge-lives.md say why.
for d in sops decisions references opportunities product; do
  mkdir -p "$ECO/wiki/$d"
done
for d in "${KB_DIRS[@]}"; do
  mkdir -p "$ECO/records/$d"
done

# agents/ holds only the README above. The routing table ships empty alongside it,
# so route_domain.py has nothing to resolve until the project derives both — a table
# with rows and no specialist on disk is what exit 3 (BROKEN ROUTE) exists to catch.


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
    echo "    rules/*.txt, the routing table in rules/cycle-backlog.md, and agents/*.md."
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
} > "$MANIFEST"
echo "==> Manifest written: $(grep -vc '^#' "$MANIFEST") paths from the kit"

echo "==> Validating install (from the target, not from here)"
if (cd "$TARGET" && python3 .claude/mechanisms/gates/check_xrefs.py --strict > /dev/null 2>&1); then
  echo "    check_xrefs.py: OK"
else
  echo "    check_xrefs.py: FAIL (re-run manually)"
fi

if (cd "$TARGET" && python3 .claude/mechanisms/gates/verify_ecosystem.py > /dev/null 2>&1); then
  echo "    verify_ecosystem.py: OK"
else
  echo "    verify_ecosystem.py: FAIL (re-run manually)"
fi

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
         --write .claude/rules/domain-routing.txt
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

  The 360º view — every phase, who owns it, and what it reads:
    .claude/rules/squad-map.md
  A compact form of it is injected at every SessionStart, so an agent starting
  work already knows the chain and the four roles.
EOF
