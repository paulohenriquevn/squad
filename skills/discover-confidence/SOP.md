---
type: SOP
title: Score the opportunity
description: Score a completed opportunity for structural quality before anything downstream acts on it.
tags: [procedure, cycle-discover, gate]

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
    resource: ../../rules/cycle-discover.md

sop: score-the-opportunity
version: 1.0.0
owner: whoever is running cycle-discover for this item
standard: rules/cycle-discover.md
last_reviewed: 2026-08-31
---

# Score the opportunity

## Purpose

Decide whether a finding is argued solidly enough to feed `/plan-write`, deterministically and without an LLM call.

## Prerequisites

- `/discover-execute` produced an opportunity with all four corners populated.
- Every evidence pointer in it resolves on disk or in a recorded observation.

## Steps

1. Run `/discover-confidence {slug}`.
2. Read the verdict together with the caps that fired.
3. Route per Decisions below.
4. Send a low score to `/discover-improve`, never to a rewrite of the Evidence corner.

## Decisions

| Verdict | Band | What follows |
|---|---|---|
| `SHIPPABLE` | ≥ 90 | Feed `/plan-write` |
| `SHIPPABLE_WITH_CAVEATS` | ≥ 70 | Feed `/plan-write`; caveats travel |
| `NEEDS_REVISION` | ≥ 50 | `/discover-improve` |
| `NON_SHIPPABLE` | < 50 | The finding is not argued; re-measure or drop |
| `INVALID` | hard cap | A fabricated pointer or an empty corner |

```mermaid
flowchart TD
    A{Every pointer resolves?}
    B{Verdict at or above the caveat band?}
    A -->|no| C[INVALID — fabricated evidence]
    A -->|yes| B
    B -->|yes| D[Proceed to /plan-write]
    B -->|no| E[/discover-improve, argument only]
```

## Escalation

- The score is low and the finding is obviously important → the score is about the ARGUMENT, not the importance. → improve the argument; the importance survives it.
- A pointer resolved when written and does not now → the code moved. → re-measure rather than editing the pointer.

## Competencies

- Separating the strength of a finding from the strength of its case. This gate scores the second.
- Knowing that a low score is never fixed by editing what the measurement recorded.
