---
type: SOP
title: Review what has rotted in the registry
description: Report duplicate ids, evidence-less triaged items, kills with no reason, unrouted repositories and stale statuses — read-only, and honest about which findings are heuristics.
tags: [procedure, cycle-backlog, audit]

# The OPERATOR's procedure. `SKILL.md` is the contract the agent executes; this is
# what a person or a lead needs to run the phase and act on what comes back.
# Derived from the documents in `sources` — no step here was invented.
generated:
  by: claude/opus-5
  at: 2026-08-31
status: stable
sources:
  - id: contract
    resource: ./SKILL.md
  - id: cycle
    resource: ../../rules/cycle-backlog.md

sop: review-the-registry
version: 1.0.0
owner: whoever is about to trust the registry to pick work
standard: rules/cycle-backlog.md
last_reviewed: 2026-08-31
---

# Review what has rotted in the registry

## Purpose

Produce a picture of the registry's health before anything selects work from it.

## Prerequisites

- `BACKLOG.md` exists.
- Nothing else. This procedure reads and never writes.

## Steps

1. **Run** the review — `/backlog-review`, or the checker directly:
   `python3 skills/backlog-review/scripts/check_backlog_structure.py BACKLOG.md --json`.
2. **Read** deterministic findings as facts and heuristic ones as questions.
3. **Answer** the heuristic questions yourself — `possible_duplicate` and `vague_dod` ask, they do not decide.
4. **Check the queue** when the question is what to work on next, not what has rotted —
   `python3 skills/backlog-review/scripts/select_backlog_item.py BACKLOG.md --json`.
   Add `--check B-NNN` for *may this one start*, `--queue N` for the head of the order.
5. **Read the halts** when an item is held and the report names a cause —
   `python3 skills/backlog-review/scripts/squad_boss.py . --json`. The causes it names
   are work for `/backlog-item`, not for this skill.
6. **Open the board** for the same registry as a page — `python3 skills/backlog-review/scripts/board_server.py`,
   then `127.0.0.1:8765`. It observes and never commands.
7. **File the corrections** through the skills that own them, never by editing `BACKLOG.md` from here.

**On `index_stale`:** report it and stop. Regenerating is
`python3 skills/backlog-review/scripts/backlog_index.py BACKLOG.md --write`, and it belongs to
`/backlog-item`'s contract — the one write that lives in this directory, and the reason
`SKILL.md` names the exception explicitly.

## Decisions

| Finding kind | Confidence | What follows |
|---|---|---|
| Deterministic — duplicate id, unresolved `blocked_by`, kill with no reason | Fact | Fix it through the owning skill |
| Heuristic — `possible_duplicate`, `vague_dod` | A question | A person answers it |
| Unrouted repository | Fact | The routing table is incomplete |

```mermaid
flowchart TD
    A{Is the finding deterministic or heuristic?}
    B{Does the fix belong to another skill?}
    A -->|deterministic| B
    A -->|heuristic| C[Answer the question; the report does not decide]
    B -->|yes| D[Route it — /backlog-item, /backlog-status, or the cycle that owns it]
    B -->|no| E[Record it; a reviewer that edits cannot be trusted to report]
```

## Escalation

- A finding needs a registry write → this skill will not make it. → the skill that owns the field does.
- Every selectable item is blocked → that is a wall, not an empty backlog. → clear the causes rather than filing new items beside them.

## Competencies

- Reading a heuristic as a question. Treating `possible_duplicate` as certain merges two real items.
- Holding read-only. A reviewer that fixes what it finds cannot be trusted to report what it found.
