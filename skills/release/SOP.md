---
type: SOP
title: Cut a release
description: Derive the version from the CHANGELOG, tag it, open the develop-to-main PR — and stop there, because the merge is the one act that stays with a person.
tags: [procedure, cycle-release, release]

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
    resource: ../../rules/cycle-release.md

sop: cut-the-release
version: 1.0.0
owner: whoever is cutting this release
standard: rules/cycle-release.md
last_reviewed: 2026-08-31
---

# Cut a release

## Purpose

Turn reviewed work into a tagged release proposal, with notes rendered from the CHANGELOG rather than from git log.

## Prerequisites

- `/review` returned `READY_TO_MERGE`.
- `[Unreleased]` in the CHANGELOG describes the change for a consumer, not for a developer.
- The branch flow is respected: the release is cut from `develop`, never from `workspace` or `main`.

## Steps

1. Run `/release {bump}`.
2. Confirm the version derived from the CHANGELOG sections matches what the change actually is.
3. Review the rendered notes before the PR opens.
4. Open the `develop → main` PR and stop.
5. Wait for a person to merge. Create the annotated tag and the GitHub release only after the merge.

## Decisions

| State | What it means | What follows |
|---|---|---|
| `PR_OPEN_AWAITING_APPROVAL` | The proposal is complete | Wait. This is the correct end state for the phase |
| Version ambiguous | `[Unreleased]` has only `Changed` under 0.x | Pause and carry the question; do not guess minor versus patch |
| `[Unreleased]` empty | Nothing to announce | There is no release to cut |

```mermaid
flowchart TD
    A{Did /review return READY_TO_MERGE?}
    B{Do the CHANGELOG sections determine the bump?}
    A -->|no| C[Stop — every release traces to a READY_TO_MERGE audit]
    A -->|yes| B
    B -->|no| D[Pause and ask; a guessed bump is a wrong contract]
    B -->|yes| E[Tag, open the PR, and wait for a human merge]
```

## Escalation

- The PR is open and nobody merges → that is the design, not a stall. → the queue moves to the next item; the PR is the record.
- The bump cannot be derived → carry the question to a person. → guessing minor versus patch under 0.x misstates compatibility.

## Competencies

- Never auto-merging. It is the single act that reaches shared history and it stays outside the envelope.
- Writing CHANGELOG entries for the consumer rather than the developer, because the release notes are rendered from them.
