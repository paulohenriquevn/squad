---
type: SOP
title: Take one item from idea to release
description: Chain the whole pipeline for a single item, deriving depth from a deterministic score, and stopping only where the contract says a person is required.
tags: [procedure, orchestration, pipeline]

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
    resource: ../../rules/cycle-idea-to-release.md

sop: run-one-item-end-to-end
version: 1.0.0
owner: whoever is running the chain for this item
standard: rules/cycle-idea-to-release.md
last_reviewed: 2026-08-31
---

# Take one item from idea to release

## Purpose

Run DISCOVER through ACCEPTANCE for one item without invoking nine commands by hand, and halt where the chain is designed to halt.

## Prerequisites

- The item exists in `BACKLOG.md`.
- The alignment gate can be satisfied — for a backlog item that means a reviewer will be available, because the chain cannot align an item with itself.

## Steps

1. Run `/idea-to-release {item}`.
2. Let the depth be derived from the confidence score. Never assert a confidence signal — the script is deterministic and its output is the truth.
3. Let every gate run. `/plan-edge-cases`, `/deps-audit` and `/code-quality` are cheap and catch what unit tests miss.
4. Expect the chain to stop at `AWAITING_REVIEW` for anything from the backlog. That halt is the design.
5. Read the final verdict and act on it per Decisions.

## Decisions

| Verdict | What it means | What follows |
|---|---|---|
| `PR_OPEN_AWAITING_APPROVAL` | The chain ran to the end | A person merges. The queue moves on |
| `AWAITING_REVIEW` | The alignment gate needs a human tick | Ask for the review; the chain cannot clear this itself |
| `BLOCKED` | A gate stopped on something the chain cannot pass | Read the report; register the causes as items |
| `ITEM_KILLED` | Discover refuted the hypothesis | A successful outcome. Nothing further |

```mermaid
flowchart TD
    A{Does the item come from BACKLOG.md?}
    B{Is a reviewer available for the alignment brief?}
    A -->|no| C[Ad-hoc path — the alignment gate soft-floors instead of capping]
    A -->|yes| B
    B -->|no| D[The chain halts at AWAITING_REVIEW by design]
    B -->|yes| E[Runs through to PR_OPEN_AWAITING_APPROVAL]
```

## Escalation

- The chain halts at a gate nobody can clear → register the cause as its own item and take the next one. → one item waiting is not the backlog waiting.
- A gate fails on something this slice did not cause → register each cause and mark this item blocked on them. → `rules/autonomy-envelope.md`.

## Competencies

- Recognising `AWAITING_REVIEW` as a designed stop rather than a failure. A chain that could align an item with itself would be the failure the gate prevents.
- Never skipping a gate on "high confidence". Confidence sets depth, not whether the gates run.
