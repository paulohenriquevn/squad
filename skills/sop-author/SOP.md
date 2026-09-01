---
type: SOP
title: Write or revise a procedure
description: Turn something this project does repeatedly into a SOP under the schema, so the steps stop living in a script header.
tags: [procedure, sop, authoring]

# The OPERATOR's procedure for a skill that is a phase of no cycle. `SKILL.md` is
# the contract; this is what a person needs to run it and act on what comes back.
# Derived from the documents in `sources` — no step here was invented.
generated:
  by: claude/opus-5
  at: 2026-08-31
status: stable
sources:
  - id: contract
    resource: ./SKILL.md
  - id: standard
    resource: ../../rules/sop-schema.md

sop: write-a-procedure
version: 1.0.0
owner: whoever performs the procedure
standard: _none_
last_reviewed: 2026-08-31
---

# Write or revise a procedure

## Purpose

Give a repeated act a written procedure with an owner, a review date, and the decisions it actually contains.

## Prerequisites

- The act is repeated. A one-off belongs in a record, not a procedure.
- Someone has performed it, or the source it is derived from is named honestly.

## Steps

1. Run `/sop-author {name}`.
2. Write the steps as imperatives, one action each.
3. Draw the decisions, giving every decision node at least two answers.
4. Name an owner a reader can reach, and route each escalation to someone.
5. Set `status: draft` when the procedure was derived from code rather than from a run somebody performed.

## Decisions

| State | What it means | What follows |
|---|---|---|
| Derived from a performed run | The strongest claim available | `status: stable`, with the run in `sources` |
| Derived from a script | The steps are read, not tested | `status: draft`, and say so |
| Nobody has performed it and no source exists | There is nothing to write yet | Do not invent it |

```mermaid
flowchart TD
    A{Has anyone performed this procedure?}
    B{Is there a script or contract to derive it from?}
    A -->|yes| C[Write it stable, citing the run record]
    A -->|no| B
    B -->|yes| D[Write it draft, citing the script]
    B -->|no| E[Write nothing — an invented procedure is followed without checking]
```

## Escalation

- The procedure would name a mechanism this project does not have → stop. → that is how a ported fix breaks the receiving side.

## Competencies

- Telling a procedure derived from a run apart from one derived from code, and marking the difference where a reader sees it.
- Writing steps someone can follow without the author present.
