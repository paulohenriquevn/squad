---
name: backlog-init
version: 0.1.0
requires: []
description: Create BACKLOG.md once, at the root of the governed scope — the umbrella when repos live below it, or the repository itself when it is autonomous — inventorying what is FROM DISK and deriving the domain routing table from THIS project. Use this the first time anyone tries to register maintenance work and no registry exists yet, when /backlog-item refuses because BACKLOG.md is missing, or when adopting Squad in a new workspace. Refuses if BACKLOG.md already exists.
user-invocable: true
allowed-tools: Read Glob Grep Bash Write Edit AskUserQuestion
argument-hint: "(no arguments)"
---

# `/backlog-init` — Create the ecosystem maintenance registry

Create `BACKLOG.md` at the umbrella root: the one place that answers *"what is pending anywhere in this ecosystem?"*

Run once, at adoption. Every item after that arrives through `/backlog-item` (human) or `/discover-execute --sweep` (measured finding).

## Cycle contract

**Two scopes, both valid.** `detect_scope` answers which one you are in: `umbrella` (the directory is not itself a repo and groups repos that are) or `single-repo` (the directory IS the repo). The previous pre-flight refused the second — *"no umbrella detected: run at the workspace root"* — which, in an autonomous project, means writing the registry into the parent directory, outside the project. Measured on an adopter: ten independent repos, each with its own cycle, and the kit pushed all ten registries into a directory that is nobody's repository.

The principle the rule defends ("one question, one place to look") never required an umbrella. It requires **one registry per governed scope**, and an autonomous repo is a scope.

This skill bootstraps the artifact that [`cycle-backlog`](../../rules/cycle-backlog.md) governs. The cycle rule is the **source of truth** for the item schema, status transitions, domain routing, verdicts and gates. This skill only creates the empty registry those rules operate on — it never registers an item.

## When NOT to invoke

DO NOT invoke when:

- `BACKLOG.md` exists. This skill refuses — use `/backlog-item` to add to it.
- You want to add an item. That is `/backlog-item`, always.
- You are inside a governed repo. A per-repo backlog is the fragmentation the single registry exists to prevent (`cycle-backlog.md § Output`).

## Process

### Step 0 — Pre-flight (MANDATORY, fail-fast)

```bash
# 0.1  BACKLOG.md must NOT exist (opposite of /backlog-item)
test -f BACKLOG.md && { echo "FATAL: BACKLOG.md already exists — use /backlog-item"; exit 1; }

# 0.2  determine the SCOPE of the registry — never refuse for lack of an umbrella
ECO=$([ -d .claude/skills ] && echo .claude || echo .)   # plugin vs standalone
SCOPE=$(python3 "$ECO/skills/backlog-init/scripts/detect_domains.py" --root . --json \
          | python3 -c 'import json,sys; print(json.load(sys.stdin)["scope"])')
echo "scope: $SCOPE"   # umbrella | single-repo — both are valid registry roots

# 0.3  CHANGELOG.md must exist (Unbreakable Rule 6)
test -f CHANGELOG.md || { echo "FATAL: CHANGELOG.md missing"; exit 1; }

# 0.4  the product documents, if the scope was aligned (advisory — see below)
python3 "$ECO/skills/brainstorm-pieces/scripts/score_product_alignment.py" --root . || true
```

### Step 0.5 — Read the brainstorm, if there is one

`cycle-brainstorm` runs before this skill and produces four documents under
`.squad/wiki/product/`. **Read all four before inventorying anything**, and hold them for
the whole run:

| Document | What it changes here |
|---|---|
| `product-vision.md` | What counts as in scope — the exclusions in Step 2 stop being arbitrary |
| `objectives.md` | The `OBJ-N` ids items will later trace to |
| `trd.md` | What the system must do, which is not the same as what its repos are |
| `technical-pieces.md` | The pieces the product is made of — compared against the repos on disk in Step 1 |

**The comparison in Step 1 is the point.** Pieces are what the product needs; repos
are what exists. A piece with no repo and a repo realising no piece are both real
findings, and this is the only moment both lists are in view at once. Report them;
do not resolve them, and above all do not invent a repo or drop a piece to make the
two agree.

**This is advisory, not a gate.** A scope with no brainstorm still initialises —
the kit is adopted into repositories that predate this cycle, and refusing them
would mean a consumer cannot create a registry until they hold a product session
they did not ask for. Say plainly that the documents were absent, so the reader
knows the inventory had nothing to check itself against rather than assuming it did.

**It still seeds ZERO items.** The objectives are not a backlog: an item needs a
`why_now` drawn from something that changed, a DoD, and an owner, and deriving one
from an objective would manufacture work nobody filed. `cycle-backlog.md § Purpose`
is unchanged by any of this.

### Step 1 — Inventory the repos FROM DISK

Never write the inventory from memory or from an existing `CLAUDE.md` table. Both drift, and a routing table that names a repo which is not checked out sends items to a specialist that cannot open the code.

```bash
for d in */; do
  [ -d "$d/.git" ] && printf '%-24s %s\n' "${d%/}" "$(git -C "$d" rev-list --count HEAD 2>/dev/null || echo 0) commits"
done
```

Then derive the routing table FROM THIS PROJECT:

```bash
ECO=$([ -d .claude/skills ] && echo .claude || echo .)   # plugin vs standalone
python3 "$ECO/skills/backlog-init/scripts/detect_domains.py" --root . --json
```

The rule is the repository as the unit of ownership: an umbrella of checked-out repos gets one domain per repo; a single repo gets ONE domain named after it, with each monorepo package listed as a path-addressed entry (`packages/sdk`) — the form the routing table already supports.

Do NOT classify the target's repos into a domain set borrowed from anywhere — not from another project, not from a set the kit once shipped. `cycle-backlog.md` ships the section EMPTY precisely so there is nothing to borrow. Measured on an adopter (2026-08-18), back when eight foreign domains did ship: 88 items carrying measured `file:line` evidence, every one of them `BLOCKER/unroutable_repo`, because `packages/sdk` cannot exist in another ecosystem's map.

Two classes get **excluded from routing**, and the registry says so out loud rather than omitting them silently:

- **Zero-commit repos** — nothing to maintain yet.
- **Nested clones of the umbrella itself** — not a product; working in one duplicates the same repository into two checkouts that diverge in silence.

A repo on disk that the detector did not reach is a finding, not a rounding error: surface it with `AskUserQuestion` and let the human either fold it into a derived domain or declare it out of scope. Never quietly drop it — a repo absent from the routing table can never receive an item.

The specialist file is **scaffolded from disk, then completed by someone who knows the domain.**

```bash
python3 "$ECO/skills/backlog-init/scripts/scaffold_specialists.py" --root . --write
```

It writes one file per domain the table names, carrying what it measured — the repos found by walking for `.git`, each one's commit count, the manifests present, and the commands those manifests imply, marked IMPLIED because nothing was run. The invariants, the shape of a real finding and the blast radius are written as OPEN, because they need someone who knows the domain and an invariant asserted by nobody is worse than an absent one: it gets believed.

This used to be human work at the first step, and `route_domain.py` exits 3 for a domain whose specialist is not on disk — so a project with a derived table and no specialists could not route a single item until a person sat down and wrote them. A file with the measured half and the rest marked open routes correctly today and improves later; a missing file routes nothing, ever.

A specialist that already exists is never overwritten. It carries knowledge the scaffold cannot reproduce.

### Step 2 — Confirm the routing table, then WRITE it

Print the derived table and ask for confirmation. The routing table decides which specialist owns which code for the life of the registry; a wrong mapping here is a wrong mapping in every item that follows.

Once confirmed, write it — this step is not optional and not cosmetic:

```bash
python3 "$ECO/skills/backlog-init/scripts/detect_domains.py" --root . \
  --write
```

**Skipping this leaves routing FATAL, and the failure does not look like a missing step.** `route_domain.py` reads the table `squad.paths.routing_table` resolves — `.squad/domain-routing.txt`, then the pre-2026-09-11 locations under `rules/` — falling back to `rules/cycle-backlog.md`, and nothing else. A table written anywhere else — including into `BACKLOG.md`, which earlier versions of this skill prescribed — is a table nothing reads.

Measured across five consumers on 2026-08-27: four had the routing file at its empty placeholder and a real, human-checked table in `BACKLOG.md` (one of them with fourteen path-addressed entries). `route_domain` exited 2 FATAL in four of four, over **165 registered items**. Every one of those registries was built by following this skill exactly.

Then write the specialist file the table names, under `$ECO/agents/`. A derived table routes to `agents/<domain>.md`, and `route_domain.py` exits 3 while that file is absent: the table existing and the routing resolving are different facts, and the run is not done until both hold. Verify:

```bash
python3 "$ECO/mechanisms/cycle/route_domain.py" <a-repo-from-the-table>; echo "exit $?"
```

Exit 0 is the only acceptable outcome of this step.

### Step 3 — Write `BACKLOG.md`

Structure, in this order:

1. **Header** — what the registry is, and the one-line rule that governs it: *ids are monotonic and never renumbered*.
2. **How an item gets here** — the two producers (`/backlog-item` human, `/discover-execute --sweep` measured), pointing at `cycle-backlog.md` for the schema rather than restating it. The registry is data; the contract lives in the rule.
3. **Where routing lives** — one line pointing at `.squad/domain-routing.txt`, plus the exclusions and their reasons. Do **not** copy the table itself here. `mechanisms/cycle/route_domain.py`'s own header states why — *"One table, one truth: a copy in code drifts from the rule the moment…"* — and a copy in the registry drifts the same way. Measured: the consumers that followed the older wording ended up with the real table in `BACKLOG.md`, where nothing reads it, and FATAL routing; the one consumer that refused to duplicate ended up with neither table, and FATAL routing. Obeying and disobeying reached the same place, which is the signal that the instruction was the defect.
4. **`## Index`** — the three-bucket summary (`cycle-backlog.md § The index that opens the
   registry`). Do **not** hand-write it; run it, even on an empty registry:

   ```bash
   python3 $([ -d .claude/skills ] && echo .claude || echo .)/skills/backlog-review/scripts/backlog_index.py BACKLOG.md --write
   ```

   Generating it now, over zero items, is what makes the section exist before anyone has a reason
   to skip it. `check_backlog_structure.py` treats an absent index as stale, so a registry created
   without one is born non-conformant.
5. **`## Items`** — empty, with the next free id declared as `B-001`.

Seed **no items**. An item nobody filed has no `why_now`, no DoD and no owner — it is a placeholder that will be inherited as though it were a decision.

### Step 4 — CHANGELOG + report

One line under `[Unreleased] § Added`. Then report the table, the exclusions, and the next step:

```
BACKLOG.md created — 8 domains, {n} repos routed, {m} excluded.
Next step:  /backlog-item {slug}   or   /discover-execute --sweep {domain}
```

## Out of scope (deliberately)

**Migrating existing findings.** The `records/` of an adopting workspace often holds review reports with real, still-open findings. Importing them here is a **separate, evidence-preserving migration** — each imported item needs its original evidence pointer and its original date, or it arrives as a hunch and loses exactly what made it worth keeping. This skill does not attempt it, and a registry created by it is honestly empty rather than dishonestly populated.

## Anti-patterns

- **Writing the inventory from `CLAUDE.md`.** It is documentation and it drifts. `find`/`git -C` is the source of truth.
- **Seeding "obvious" items.** Every item needs a human `why_now` and a DoD. Pre-filled items have neither and get inherited as decisions nobody made.
- **Silently dropping an unclassifiable repo.** It disappears from routing and becomes unmaintainable through the system. Ask.
- **Creating a per-repo `BACKLOG.md`.** Directly re-creates the orphaned-findings problem the single registry solves.
- **Re-running to "refresh" the routing table.** The skill refuses when the file exists, on purpose. Edit the table in place; the items must survive.

## Cross-references

- Cycle rule (source of truth): [`rules/cycle-backlog.md`](../../rules/cycle-backlog.md)
- Sister skill, opposite pre-condition: [`skills/backlog-item/SKILL.md`](../backlog-item/SKILL.md)
- Live environment declaration used by `/discover-execute (live-test mode)`: [`rules/live-target.txt`](../../rules/live-target.txt)
- Branching contract for the registry commit: [`rules/git-safety.md`](../../rules/git-safety.md)
