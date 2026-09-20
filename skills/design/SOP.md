---
type: SOP
title: Draw the system before a backlog exists
description: Produce the five technical drawings that force the decisions a product cannot retrofit — lifecycle, trust boundary, real call order, durability — and the map derived from them.
tags: [procedure, cycle-design, architecture]

# The OPERATOR's procedure. `SKILL.md` is the contract the agent executes; this is
# what a person needs to attend the session and act on what comes back.
# Derived from the documents in `sources` — no step here was invented.
generated:
  by: claude/opus-5
  at: 2026-09-10
status: stable
sources:
  - id: contract
    resource: ./SKILL.md
  - id: cycle
    resource: ../../rules/cycle-design.md
  - id: pieces
    resource: ../brainstorm-pieces/SKILL.md

sop: draw-the-system
version: 1.0.0
owner: whoever will answer for the system's shape
standard: rules/cycle-design.md
last_reviewed: 2026-09-10
---

# Draw the system before a backlog exists

## Purpose

Force the four decisions that cannot be retrofitted, while they are still cheap.

## Prerequisites

- `cycle-brainstorm` closed: `technical-pieces.md` exists with PIECE-N declared.
- **A person is present.** This phase interrogates before it draws, and the gate ends
  at a signature only a person may give.

## Steps

1. **Run** `/design {scope}`.
2. **Answer the questions.** They come one at a time and only where the TRD cannot
   answer. A question already answered in the documents is a question that wastes the
   session.
3. **Read each drawing as it lands**, and say what is wrong immediately. A drawing
   corrected in the session costs a sentence; corrected after the backlog opens it
   costs every item filed against it.
4. **Render, if you would rather look at a picture** — optional, and nothing depends
   on it:
   ```bash
   /diagram-design:import-mermaid .squad/wiki/design/sequence.md --format=html
   ```
   The plugin reads these files directly; they are Markdown carrying fenced mermaid.
   `--format=html+png` when the review is not at a terminal. The mermaid stays the
   drawing — the render is never edited back into it.
5. **Score** —
   `python3 skills/design/scripts/check_design_completeness.py --project .`
6. **Convene the panel and read its verdict** — `/panel design {scope}`, then
   `python3 mechanisms/gates/check_panel_approval.py --slug {scope} --phase design --project .`
   Gate G-D8. A missing record is not an approval, and the completeness score does not
   ask for it: both gates have to pass.
7. **Sign** the checklist — `/sign .squad/wiki/design/sign-off.md --as human/<you>`.
   `/design` wrote it unticked at Step 3b; the `human/` prefix is what the gate accepts.
8. **Emit** the verdict, then `/backlog-init`.

## What each drawing must let you answer

Ask these of the drawings before ticking anything. If a drawing cannot answer its row,
it is not done.

| Drawing | You must be able to say |
|---|---|
| D1 states | which transitions are irreversible, and who can trigger each |
| D2 trust | where untrusted code stops, and with which credential it reaches us |
| D3 sequence | what happens when each step fails, not only when it succeeds |
| D4 durability | what is lost when the process dies, the node restarts, the platform deploys |
| D5 map | which component owns each PIECE-N, and which components own none |

## The commands, in one place

| | |
|---|---|
| Produce the drawings | `/design {scope}` |
| Score them | `python3 skills/design/scripts/check_design_completeness.py --project .` |
| Sign the checklist | `python3 skills/sign/scripts/sign_document.py .squad/wiki/design/sign-off.md --as {you}` |
| Render one, optional | `/diagram-design:import-mermaid <file.md> [--format=html\|svg\|png\|html+png]` |
| Export an existing render | `/diagram-design:export-diagram` |

The `diagram-design` plugin is a **separate install**. Nothing in this phase depends on
it, and the gate never asks for a rendered file: a drawing that exists only as a picture
is one no gate can check and no agent can read back.

## Escalation

- A drawing cannot be finished because a product decision is open → that is the phase
  working. → the decision's owner; do not draw a placeholder, which reads as settled.
- `NEEDS_REVISION` names an uncovered piece → either the map is missing a component or
  the piece is not real. → back to `/brainstorm-pieces` if the piece is wrong.
- `AWAITING_REVIEW` and nobody will sign → the phase is complete and unattested.
  → whoever will answer for the system's shape. There is no judge for this gate.
- A drawing is correct today and the system changed → nothing here detects that.
  → re-run the phase; staleness is not mechanised, and this is a known gap.

## Competencies

- Reading D5 as a summary rather than as the design.
- Recognising a happy-path-only sequence as incomplete, not as concise.
- Telling "the machine says complete" from "the design is right" — the first is
  countable and the second is what you are signing.

## Cadence

Once per scope, before the backlog opens. Re-run when the system's shape changes —
which nothing detects for you.
