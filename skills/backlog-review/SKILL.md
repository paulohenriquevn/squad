---
name: backlog-review
version: 0.1.0
requires: []
description: Report what has rotted in BACKLOG.md — duplicate or renumbered ids, triaged items with no evidence, raw items that were measured and never advanced, killed items with no reason, repos that route to nobody, vague or missing DoD, stale items, probable duplicates. Use this whenever someone asks whether the backlog is trustworthy or messy, before running the maintenance loop, after a sweep registers a batch of findings, or periodically — a registry nobody reviews is a registry nobody trusts. Read-only.
user-invocable: true
allowed-tools: Read Glob Grep Bash
argument-hint: "[path to BACKLOG.md]"
---

# `/backlog-review` — structural review of the registry

Read `BACKLOG.md` and report what is wrong with it. Writes nothing.

A registry is not a document that decays visibly. Its failure mode is quiet: statuses that stopped tracking reality, items nobody can act on, duplicates that split attention. By the time it looks wrong, people have already stopped consulting it. This skill makes that state observable while it is still cheap to fix.

## Cycle contract

Companion to [`rules/cycle-backlog.md`](../../rules/cycle-backlog.md) (the registry and its intake) and [`rules/cycle-maintenance.md`](../../rules/cycle-maintenance.md) (the loop that consumes it). Both are the source of truth for the schema, the status transitions and the gates. This skill only reports divergence from them.

## When NOT to invoke

- Before a `cycle-maintenance` run, so the loop does not select a broken item.
- After a `--sweep` registers a batch of findings — bulk writes are where duplicates and missing fields arrive.
- Periodically. A registry nobody reviews is a registry nobody trusts.
- Before handing the backlog to someone else.

Do NOT invoke to add or change items — that is `/backlog-item`. This skill is read-only, deliberately: a reviewer that also edits cannot be trusted to report what it found.

### The one exception, named rather than left to be discovered

`scripts/backlog_index.py --write` **rewrites `BACKLOG.md`**, and it lives in this
skill's directory. That is not a hole in the read-only rule; it is a different act,
and the distinction is worth stating because `allowed-tools` cannot enforce it —
`Bash` is granted, so nothing mechanical stops a write.

The index is **generated, never edited**: `backlog_index.py` derives the `## Index`
section from the item blocks and replaces only that block. It adds no judgement,
changes no field, and cannot alter what an item says. Running it twice changes
nothing the first run did.

It lives here because it shares the item parser with `check_backlog_structure.py`,
and a second parser would disagree with the first about what the registry contains —
the exact defect the index exists to expose.

**The review path never calls it.** `/backlog-review` reports `index_stale` and stops
there; regenerating is `/backlog-item`'s business, whose contract
(`rules/cycle-backlog.md § The index that opens the registry`) is where the write is
prescribed.

## What lives in `scripts/`, and who runs it

Eight files, and only three used to be named anywhere in this skill. A tool nobody
names is a tool nobody finds — `skills/map.md` records what that cost twice over.

| Script | Runs it | What it does |
|---|---|---|
| `check_backlog_structure.py` | `/backlog-review` | the review itself — every finding class below |
| `backlog_index.py` | `/backlog-item`, `backlog_status.py` | derives the `## Index` block. **The only writer here** |
| `select_backlog_item.py` | `cycle-maintenance` SELECT, `/pipeline`, Kairos, Hermes | ranks the queue and answers *may this item start* |
| `squad_boss.py` | Kairos, `squad_lead.py` | reads BLOCKED reports and names the halts a queue can attack |
| `board_state.py` | `board_server.py`, `squad_boss.py` | builds the board's view of every item and its phase |
| `board_server.py` | `/backlog-review --board` | serves that view on `127.0.0.1:8765` |
| `board.html` | `board_server.py` | the page itself — no build step, no CDN |
| `phase_coverage.py` | on demand | reconstructs which phases left a record, per item |

**`select_backlog_item.py` and `squad_boss.py` are called from outside this skill, by
command line and never by import.** `rules/cycle-maintenance.md` names their paths
because they emit that cycle's verdicts. They sit here because the registry is what
they read, and moving them would separate them from the parser they share.

## What it checks

### Deterministic — the machine is sure

| Check | Severity | Why it matters |
|---|---|---|
| `duplicate_id` | blocker | Two blocks sharing a `B-NNN` destroy the audit trail |
| `renumbered` | blocker | Ids are never reused or reordered; a reused id makes every earlier reference ambiguous |
| `illegal_status` | blocker | A status outside the declared set means the loop cannot route the item |
| `triaged_without_evidence` | blocker | Triaged means measured. Without evidence the status is a claim nobody made |
| `unroutable_repo` | blocker | A repo in no domain routes to nobody (gate G1). **Open items only** — G1 is about work that cannot proceed |
| `unroutable_repo_closed` | minor | The same on a `shipped` or `killed` item. History, not an impediment: the contract forbids renumbering it and forbids an impediment on closed work, so a blocker there is permanent and unfixable |
| `raw_with_evidence` | major | Measurement happened and the status was never advanced — the rot the loop exists to prevent |
| `killed_without_reason` | major | Indistinguishable from an abandoned run (gate G-K) |
| `missing_field` | major | A required field absent |
| `invalid_mode` | major | `suggested_mode` outside the four |

### Heuristic — a human decides

| Check | Severity | Honest limitation |
|---|---|---|
| `thin_dod` | major | Zero DoD bullets. Nothing states when the item is done, so it never closes |
| `vague_dod` | minor | Word-list matching. A bullet carrying a number or a backticked artifact is treated as falsifiable even when it also reads as vague — "p95 below 800ms" is a criterion, and flagging it would train people to ignore the check |
| `stale_raw` | minor | 90 days is a convention, not a measurement. It asks a question rather than asserting a defect |
| `possible_duplicate` | minor | Title-word overlap ≥ 0.6 between OPEN items. Closed items are excluded — a shipped item and a new one in the same area is a follow-up, not a duplicate |

Every finding carries `kind: deterministic | heuristic`. A reader must be able to tell "this is certainly wrong" from "someone should look" without knowing the implementation.

## Verdict

Derived from the findings, never asserted — the same discipline the confidence scorers follow.

| Verdict | Condition | Exit |
|---|---|---|
| `SHIPPABLE` | no findings | 0 |
| `SHIPPABLE_WITH_CAVEATS` | minors only | 0 |
| `NEEDS_REVISION` | at least one major | 3 |
| `INVALID` | at least one blocker | 1 |

## Usage

```bash
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/backlog-review/scripts/check_backlog_structure.py" BACKLOG.md
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/backlog-review/scripts/check_backlog_structure.py" --json
```

Read the output and report it. Do not edit `BACKLOG.md`.

## Selecting the next item

```bash
# which item may start now?
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/backlog-review/scripts/select_backlog_item.py" BACKLOG.md

# may THIS one start? — the form the gate takes when a human already picked
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/backlog-review/scripts/select_backlog_item.py" BACKLOG.md --check B-014

# the head of the order, for a caller filling more than one lane
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/backlog-review/scripts/select_backlog_item.py" BACKLOG.md --queue 5
```

Implements `rules/cycle-maintenance.md § Chain` — the filter, the ranking (triaged
before raw, then oldest first) and the verdicts SELECT can reach. All three forms run
the same computation, so the gate and the selector cannot disagree.

Two things it does that the written chain did not say, because the chain predates them:
**blocked items are dropped** (an item waiting on another reads `triaged` on disk and
cannot be worked on, so eligibility uses the derived state), and **`BACKLOG_BLOCKED` is
not `BACKLOG_EMPTY`** — when items remain and every one is blocked, the sweep the
latter prescribes would add items beside a wall instead of clearing it.

An item that is `approved` comes back `ITEM_AWAITING_PLAN` — the decision was taken and the plan does not exist yet, which is not a wall and not work in flight; the next step is `/plan-write`. An item that is `planned`, `shipped` or `killed` comes back `ITEM_IN_FLIGHT`,
`ITEM_SHIPPED` or `ITEM_KILLED` — not blocked. It is past the point where SELECT hands
out work, which is a different fact from being held back, and reporting both as one
verdict told a reader the opposite of the truth.

## The live board

```bash
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/backlog-review/scripts/board_server.py" . --port 8765
```

Serves `http://127.0.0.1:8765` — every item, the phase it sits in, and what holds it,
re-rendering by itself whenever `BACKLOG.md` or `.squad/records/cycle-events.jsonl` changes on
disk. Standard library only; nothing to install.

It reads two sources that answer different questions, and says which one it used:

| Source | Answers | Shown as |
|---|---|---|
| `BACKLOG.md` | where each item stands | `derived` — inferred from `status` |
| `.squad/records/cycle-events.jsonl` | which phase actually ran | measured; no qualifier |

**The distinction is on the screen, not in a footnote.** The stream is per-machine and
starts empty in every clone, so the inferred case is what most viewers see first — and
a board that renders an inference and a measurement in the same typeface asserts
knowledge it does not have. With no stream at all, the board says so above the columns
rather than letting the layout imply something was observed.

**Impediment is a marker on the card, never a column.** `blocked` is derived from
`status` + `blocked_by`, so an item stalled at `planned` still sits in the Plan column,
which is where it resumes. A Blocked column would relocate the item and lose that.

**`killed` is not styled as a failure.** The contract calls it a successful outcome, so
it takes a muted neutral. Colouring it red would misreport eleven honest measurements
as eleven failures.

**Read-only, bound to `127.0.0.1`.** A board that could advance an item would be a
second writer racing `backlog_status.py`, which is the shape this kit removed when it
gave the status line one owner. And `BACKLOG.md` carries unreleased plans, kill reasons
and sponsor decisions, so binding the wrong address publishes someone's roadmap.

## When routing cannot be checked

The report carries `routing_table_read`. When it is `false`, the routing table was unreachable and **`unroutable_repo` did not run** — no repo was judged.

Say so in the report. Reporting every repo as unroutable from missing data would assert a violation the evidence does not support, and a clean report that silently skipped a check is worse than a report that says which check it could not run.

## Anti-patterns

- **Editing the backlog.** Read-only. A reviewer that edits cannot be trusted to report what it found. The one write in this directory — `backlog_index.py`, which *generates* the index rather than editing any item — belongs to `/backlog-item`'s contract and is never called from the review path (§ The one exception, named rather than left to be discovered).
- **Treating a heuristic finding as certain.** `possible_duplicate` and `vague_dod` ask questions. The human answers.
- **Ignoring `raw_with_evidence`.** It is the most informative finding here: someone measured and nobody advanced the status, which means the loop is being bypassed.
- **Silencing `stale_raw` by killing items in bulk.** A kill needs a `kill_reason` naming what was measured. Killing to clear a count produces exactly the unexplained kills gate G-K exists to prevent.
- **Reporting a clean verdict without saying `routing_table_read` was false.**

## Related

- The registry and its intake: [`rules/cycle-backlog.md`](../../rules/cycle-backlog.md)
- The loop that consumes it: [`rules/cycle-maintenance.md`](../../rules/cycle-maintenance.md)
- Routing: `mechanisms/cycle/route_domain.py`
- Bootstrap: [`skills/backlog-init/SKILL.md`](../backlog-init/SKILL.md)
- Intake: [`skills/backlog-item/SKILL.md`](../backlog-item/SKILL.md)
