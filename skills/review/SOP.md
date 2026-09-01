---
type: SOP
title: Run the review gate
description: Spawn the specialist reviewers over the diff in isolated worktrees, consolidate their findings, and route the verdict — a gate that never merges.
tags: [procedure, cycle-review, gate]

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
    resource: ../../rules/cycle-review.md

sop: run-the-review
version: 1.0.0
owner: whoever is running cycle-review for this slug
standard: rules/cycle-review.md
last_reviewed: 2026-08-31
---

# Run the review gate

## Purpose

Compare the diff against the plan line by line, across the dimensions the domain needs, and produce a verdict the release phase can act on.

## Prerequisites

- `/implement` validation passed, or its PARTIAL is documented and permitted for this lifecycle stage.
- `/code-quality` has run.
- The plan is on disk — it is what the diff is compared against.

## Steps

1. Run `/review {slug}`.
2. Confirm the reviewers were spawned with `isolation="worktree"`. Six reviewers in one tree produced a false BLOCKER against a symbol that existed.
3. Read the consolidated report, not the individual agents' output.
4. Route the verdict per Decisions below.
5. Re-review after fixes. A verdict describes the diff that was read.

## Decisions

| Verdict | What it means | What follows |
|---|---|---|
| `READY_TO_MERGE` | No open BLOCKER or HIGH finding | `/release` |
| `NEEDS_FIXES` | Findings to close in this slice | Fix, then re-review |
| `NEEDS_DEEPER` | The slice is wrong at the scope level | Back to `/plan-write` for re-scoping |
| `BLOCKED` | The review could not be performed | Say why; never a PASS by default |

```mermaid
flowchart TD
    A{Were the reviewers isolated per worktree?}
    B{Any open BLOCKER or HIGH?}
    A -->|no| C[Stop — findings from a shared tree cannot be trusted]
    A -->|yes| B
    B -->|yes| D[NEEDS_FIXES, or NEEDS_DEEPER when the scope is wrong]
    B -->|no| E[READY_TO_MERGE — proceed to /release]
```

## Escalation

- Review depth needs domain expertise outside the model's reach → mark BLOCKED with that reason. → a human domain expert.
- A finding is disputed → the finding stays open until closed with evidence. → deleting a finding and lowering a BLOCKER to MEDIUM are the same act.

## Competencies

- Knowing that this gate reviews and never merges, and that `NEEDS_DEEPER` is a scope verdict rather than a harder `NEEDS_FIXES`.
- Recognising contamination: a finding about a symbol that plainly exists usually means the tree moved under the reviewer.
