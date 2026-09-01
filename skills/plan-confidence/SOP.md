---
type: SOP
title: Score the plan before it is built
description: Score a plan structurally, apply the caps other phases feed it, and refuse to let an INVALID plan reach /implement.
tags: [procedure, cycle-plan, gate]

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

sop: score-the-plan
version: 1.0.0
owner: whoever is running cycle-plan for this slug
standard: rules/cycle-plan.md
last_reviewed: 2026-08-31
---

# Score the plan before it is built

## Purpose

Decide whether a plan may enter `/implement`, deterministically, and record why when it may not.

## Prerequisites

- `/deps-audit` has run and left its report on disk — this is phase 4 and that is phase 3.
- The item is aligned, or the alignment gate will cap the score regardless of the plan's quality.

## Steps

1. Run `/plan-confidence {slug}`.
2. Read the verdict together with every cap that fired, and note which phase fed each one.
3. Route per Decisions below.
4. Re-score after `/plan-improve`, never instead of it.

## Decisions

| Verdict | Band | What follows |
|---|---|---|
| `SHIPPABLE` | ≥ 90 | Ready for `/implement` |
| `SHIPPABLE_WITH_CAVEATS` | ≥ 70 | Ready for `/implement`; caveats travel |
| `NEEDS_REVISION` | ≥ 50 | `/plan-improve`, then re-score |
| `NON_SHIPPABLE` | < 50 | Rewrite |
| `INVALID` | hard cap | Back to `/to-plan`. A missing alignment brief and an insecure dependency both land here |

```mermaid
flowchart TD
    A{Any hard cap fired?}
    B{Score at or above 70?}
    A -->|yes| C[INVALID — back to /to-plan]
    A -->|no| B
    B -->|yes| D[Ready for /implement]
    B -->|no| E[/plan-improve, then re-score]
```

## Escalation

- The alignment cap fired and no reviewer is available → the item waits. → there is no `--skip` on that gate by design.
- A dependency cap fired on a CVE with no fix → the sponsor decides. → allowlist with an ADR, or replace the dependency.

## Competencies

- Reading which phase fed each cap. A capped score is usually a message from `/deps-audit` or `/shared-understanding`, not a judgement about the prose.
- Knowing that no bypass flag exists here and that adding one is forbidden by the golden rule's constructor invariant.
