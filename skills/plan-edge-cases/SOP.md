---
type: SOP
title: Find the edge cases a plan does not handle
description: Annotate a plan with the edge cases that matter, classified MUST-FIX, SHOULD-TEST or DOCUMENT — without complicating the design.
tags: [procedure, cycle-plan, risk]

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
    resource: ../../rules/cycle-plan.md

sop: find-edge-cases-in-the-plan
version: 1.0.0
owner: whoever is running cycle-plan for this slug
standard: rules/cycle-plan.md
last_reviewed: 2026-08-31
---

# Find the edge cases a plan does not handle

## Purpose

Surface real risks inside the plan as written, and get the MUST-FIX ones absorbed before it is scored.

## Prerequisites

- A plan exists at `records/plans/{slug}-plan.md`.
- `/plan-write` has finished — this is phase 2 and that is phase 1.

## Steps

1. Run `/plan-edge-cases {slug}`.
2. Analyse the plan AS IT IS. A future API change is not an edge case of this plan.
3. Classify each finding MUST-FIX, SHOULD-TEST or DOCUMENT.
4. Give every MUST-FIX an owner and an acceptance criterion.
5. Absorb the MUST-FIX items into the plan before `/deps-audit`.

## Decisions

| Class | What it means | What follows |
|---|---|---|
| MUST-FIX | The plan is wrong without it | Absorbed into the plan, with an acceptance criterion |
| SHOULD-TEST | A real risk worth a test | Added to the test plan |
| DOCUMENT | A known limit | Recorded, not built around |

```mermaid
flowchart TD
    A{Does the plan break without handling this?}
    B{Does a one-line guard resolve it?}
    A -->|no| C[SHOULD-TEST or DOCUMENT]
    A -->|yes| B
    B -->|yes| D[MUST-FIX — the one-line guard, not a subsystem]
    B -->|no| E[MUST-FIX — with an owner and an acceptance criterion]
```

## Escalation

- The fix wants a new abstraction → refuse. → `if input.is_empty()` solves it; an `ErrorRecoveryManager` is the anti-pattern this phase names.
- The edge case implies the plan is wrong at the goal level → back to `/plan-write`. → this phase annotates plans, it does not rewrite them.

## Competencies

- Telling an edge case from a wider investigation. The first lives inside what was planned.
- Preferring the smallest guard that closes the case over the most general one.
