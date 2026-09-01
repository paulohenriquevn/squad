---
type: SOP
title: Validate the trajectory with measurements
description: Run the trajectory modules against real tool output — benchmarks, complexity, fitness, scalability — and report what the numbers say rather than what was hoped.
tags: [procedure, trajectory, measurement]

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
    resource: ../../rules/cycle-trajectory-review.md

sop: validate-the-trajectory
version: 1.0.0
owner: whoever asked whether the direction still holds
standard: rules/cycle-trajectory-review.md
last_reviewed: 2026-08-31
---

# Validate the trajectory with measurements

## Purpose

Answer whether the project's direction survives measurement, with every number traceable to a tool run.

## Prerequisites

- The project opted in via `rules/trajectory-review-config.txt`. This cycle is opt-in and gates nothing.
- The tools the modules invoke are installed, because a module that could not run measured nothing.

## Steps

1. Run `/trajectory-review`.
2. Extract the hypotheses first. Benchmarks without hypotheses are benchmarking, not review.
3. Let each module produce numbers from an actual tool run with subprocess evidence.
4. Read the verdict as advisory — this cycle is independent and does not gate the chain.

## Decisions

| Verdict | What it means | What follows |
|---|---|---|
| Hypothesis confirmed | The direction survives the measurement | Continue |
| `AT_RISK` | Measurements trend against the hypothesis | Decide deliberately, with the numbers |
| `FALSIFIED` | The hypothesis does not hold | `COURSE_CORRECTION_NEEDED` or a fundamental rethink |
| A module could not run | Nothing was measured | Report that, never a pass |

```mermaid
flowchart TD
    A{Did every module actually run?}
    B{Do the numbers support the hypothesis?}
    A -->|no| C[Report the gap — an unrun module measured nothing]
    A -->|yes| B
    B -->|yes| D[Confirmed — continue]
    B -->|no| E[FALSIFIED — course correction or rethink]
```

## Escalation

- A verdict would change the roadmap → this cycle does not gate the chain. → the decision goes to whoever owns the direction, with the numbers attached.
- A tool is unavailable → the module did not run. → whoever owns the environment.

## Competencies

- Refusing to fabricate a measurement. Every number comes from a tool run with subprocess evidence.
- Extracting hypotheses before measuring, so the numbers can answer something.
