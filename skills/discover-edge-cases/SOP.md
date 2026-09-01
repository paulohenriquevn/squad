---
type: SOP
title: Find what would make the measurement lie
description: Audit a measurement plan for the ways it could produce a confident wrong answer — a stale target, a proxy read as the thing, an environment fault read as a product defect.
tags: [procedure, cycle-discover, measurement]

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

sop: find-what-would-make-the-measurement-lie
version: 1.0.0
owner: whoever is running cycle-discover for this item
standard: rules/cycle-discover.md
last_reviewed: 2026-08-31
---

# Find what would make the measurement lie

## Purpose

Surface the failure modes of the MEASUREMENT, not of the system: the ways this plan could return a clean number that means nothing.

## Prerequisites

- A measurement plan exists — this is phase 2 and `/discover-plan` is phase 1.
- The plan names its tools and targets, because those are what can lie.

## Steps

1. Run `/discover-edge-cases {slug}`.
2. Check each target for staleness: resolving is not the same as current.
3. Ask, for each question, whether the tool observes the thing or a proxy for it.
4. Separate an environment fault from a product defect for every failure the plan could see.
5. Fold the MUST-FIX findings back into the plan before scoring it.

## Decisions

| Finding class | What it means | What follows |
|---|---|---|
| MUST-FIX | The measurement would lie in a way that changes the conclusion | Fix the plan; do not run it |
| SHOULD-TEST | A real risk that does not invalidate the result | Fold in if cheap |
| DOCUMENT | A known limit of the method | Record it in the plan |

```mermaid
flowchart TD
    A{Does the tool observe the thing, or a proxy?}
    B{Would an environment fault be readable as a product defect?}
    A -->|proxy| C[MUST-FIX — name what the proxy hides]
    A -->|the thing| B
    B -->|yes| D[MUST-FIX — the plan must separate them]
    B -->|no| E[Fold findings in and proceed to scoring]
```

## Escalation

- The only available tool observes a proxy and no better one exists → record it as a stated limit rather than dropping it. → the plan carries the caveat into the opportunity.
- An edge case implies a wider investigation → refuse it. → an edge case lives inside what was planned; a wider question is a new item.

## Competencies

- Distinguishing a measurement that fails from one that lies. The first is visible; the second is the reason this phase exists.
- Refusing speculation about future states. The system that exists is the one being measured.
