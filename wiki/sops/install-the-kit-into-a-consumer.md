---
type: SOP
title: Install the kit into a consumer
description: The steps for putting the Squad ecosystem into a project that does not have it, and the two states that look like success and are not.
tags: [procedure, kit-maintenance, install]

# OKF provenance and trust (spec §5). `verified` is deliberately ABSENT, and so is
# any `sources` entry pointing at a run: this procedure was DERIVED FROM THE SCRIPT,
# not written from a run somebody performed and recorded. That is a weaker claim than
# `port-fix-between-kits` makes, and saying so is the point — a procedure presented as
# tested when nobody tested it is worse than an absent one, because it will be
# followed without checking.
generated:
  by: claude/opus-5
  at: 2026-08-31
status: draft
stale_after: 2027-02-28
sources:
  - id: script
    resource: ../../mechanisms/dist/install.sh

# Kit-specific keys, kept so `check_sop_structure.py` keeps reading this file.
sop: install-the-kit-into-a-consumer
version: 0.1.0
owner: kit maintainer (whoever holds the branch)
standard: _none_
last_reviewed: 2026-08-31
---

# Install the kit into a consumer

## Purpose

Put the ecosystem into a project that does not have it, as a plugin install at
`<target>/.claude/`, and leave the target in a state where the first cycle can
run. The script does the copying; this procedure is about the parts it cannot
decide and the two ways an install reports success while being broken.

## Prerequisites

- The target exists and is a directory. The script refuses anything else.
- The target has no `.claude/` — or you intend `--force`, which **overwrites**.
- `python3` on the path, because the install validates itself by running
  `check_xrefs.py --strict` from the target.
- A clean working tree in the kit. The installer copies what is on disk, not what
  is committed, so an uncommitted experiment ships with it.

## Steps

1. Run `bash mechanisms/dist/install.sh <target-project-dir>`. Add `--force` only when
   replacing an existing install, and only after reading what it overwrites.
2. Read the validation the installer runs at the end. It executes
   `check_xrefs.py --strict` **from the target**, not from the kit, because a
   validator started from the kit audits the kit — measured on 2026-08-03, three
   consumers reported PASS while carrying 3, 0 and 11 findings.
3. Confirm `.claude/agents/` contains `README.md` and nothing else. The kit ships
   no specialists on purpose: a specialist describes one ecosystem's repositories,
   and installing a stranger's makes the routing gate refuse every item.
4. Derive this project's specialists before routing anything —
   `skills/backlog-init/scripts/scaffold_specialists.py --root <target> --write`.
   Until they exist, `route_domain.py` exits 3 (BROKEN ROUTE) for every domain the
   table names.
5. Point the consumer's own `CLAUDE.md` at `.claude/`. The installer does not
   touch it, by design — it is the consumer's file.
6. Decide whether `.claude/` is tracked. The installer adds nothing to
   `.gitignore`; that is the consumer's call and it has consequences, because a
   fix written inside an untracked `.claude/` protects exactly one machine.
7. Read `.claude/.kit-manifest.txt`. It lists every path the kit brought, so
   anything not in it belongs to the project — the boundary a later patch relies
   on.

## Decisions

```mermaid
flowchart TD
    A{Target already has .claude/?}
    C{Replacing it wholesale?}
    F{check_xrefs --strict from the target passed?}
    G{agents/ holds README.md only?}
    A -->|no| B[install.sh]
    A -->|yes| C
    C -->|yes| D[install.sh --force]
    C -->|no, keep local state| E[patch_install.sh instead]
    B --> F
    D --> F
    F -->|yes| G
    F -->|no| H[Stop: the install is broken, not merely noisy]
    G -->|yes| I[Scaffold this project's specialists]
    G -->|no| J[Stop: a stranger's specialists were installed]
```

## Escalation

- `check_xrefs.py --strict` exits non-zero → stop and read the findings. A clean
  clone once produced an empty `.claude/agents/` and a dangling reference, green
  on the maintainer's machine. → the kit maintainer, not the consumer's owner.
- The target has local improvements under `.claude/` → do not `--force`. → use
  `patch_install.sh`, or the sync classifier, which refuses to overwrite a
  divergence.
- A domain in the routing table has no specialist and the scaffold cannot derive
  one → the topology is wrong, not the install. → whoever owns the repository
  layout.

## Competencies

- Reading a validator's exit code as a claim about a specific target, not about
  wherever the command was typed.
- Telling a scaffold apart from knowledge: an empty directory the installer made
  is not a project that has migrated.
- Knowing which files belong to the consumer — `CLAUDE.md`, `settings.local.json`,
  `records/`, `agents/` beyond the README — and leaving them alone.
