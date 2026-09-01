---
type: SOP
title: List the available commands
description: Show every command by cycle with the recommended flows — an index, never the contract.
tags: [procedure, orientation]

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

sop: list-the-commands
version: 1.0.0
owner: whoever is asking what the kit can do
standard: _none_
last_reviewed: 2026-08-31
---

# List the available commands

## Purpose

Orient someone who does not yet know which command answers their question.

## Prerequisites

- None. This reads and reports.

## Steps

1. Run `/commands-help`.
2. Find the cycle that owns the question, then the command inside it.
3. Open that skill's `SOP.md` for how to run it, and its `SKILL.md` for the contract.

## Decisions

| What you need | Where to go |
|---|---|
| Which command exists | This skill |
| How to operate one | That skill's `SOP.md` |
| What it guarantees | That skill's `SKILL.md` and its cycle rule |
| What every skill is for, and what not to use it for | `skills/map.md` |

```mermaid
flowchart TD
    A{Do you know which cycle owns the question?}
    B{Do you need the contract or the procedure?}
    A -->|no| C[Read skills/map.md — it groups by chain position]
    A -->|yes| B
    B -->|contract| D[SKILL.md and the cycle rule]
    B -->|procedure| E[That skill's SOP.md]
```

## Escalation

- The index and a skill disagree → the skill wins. → the disagreement is a defect worth reporting.

## Competencies

- Treating an index as a way in rather than as an authority.
