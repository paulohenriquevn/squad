---
type: SOP
title: Calibrate the quality-gate hooks for a project
description: Read a codebase and emit PostToolUse hooks whose thresholds come from that project's real p90, so the gate does not start out rejecting the code already there.
tags: [procedure, bootstrap, quality]

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

sop: calibrate-quality-hooks
version: 1.0.0
owner: whoever is setting this project up
standard: _none_
last_reviewed: 2026-08-31
---

# Calibrate the quality-gate hooks for a project

## Purpose

Give a project quality gates it can actually pass on day one, and know how much of the existing code they would block.

## Prerequisites

- The project has code to measure. Calibration on an empty tree measures nothing.
- The languages and their test directories are discoverable.

## Steps

1. Run `/quality-init {target}`.
2. Read the calibration stage: how much of the existing code the generated gate would block.
3. Confirm no threshold sits below its floor — a gate that blocks every write makes the assistant unusable.
4. Install the hooks and verify one edit passes.

## Decisions

| Verdict | What it means | What follows |
|---|---|---|
| `READY` | The gate blocks a small, deliberate fraction | Install |
| `REVIEW` | It would block enough to be worth a decision | Decide with the number in front of you |
| `TOO_STRICT` | It would block most of the tree | Recalibrate before installing |

```mermaid
flowchart TD
    A{What fraction of existing files would the gate block?}
    B{Is every threshold at or above its floor?}
    A -->|most| C[TOO_STRICT — recalibrate]
    A -->|a deliberate fraction| B
    B -->|no| D[Raise it — a gate that blocks everything gets disabled]
    B -->|yes| E[Install and verify with one edit]
```

## Escalation

- The calibrated gate would block half the tree → that is a decision, not a default. → whoever owns the codebase decides between fixing and relaxing.

## Competencies

- Reading a per-metric p90 as a per-file risk: thirty functions in a file are thirty chances of holding one of the worst ten percent.
- Knowing hooks are gates, never fixers.
