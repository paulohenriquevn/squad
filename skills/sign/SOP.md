---
type: SOP
title: Sign a document that is waiting on a person
description: Find what is waiting for a signature, read what is being signed, and record it — including the case where the signer is also the author, which is declared rather than hidden.
tags: [procedure, sign-off, governance]

# The OPERATOR's procedure. `SKILL.md` is the contract the agent executes; this is
# what a person needs to sign and to know what their signature claims.
# Derived from the documents in `sources` — no step here was invented.
generated:
  by: claude/opus-5
  at: 2026-09-10
status: stable
sources:
  - id: contract
    resource: ./SKILL.md
  - id: item-level
    resource: ../plan-alignment/SKILL.md
  - id: product-level
    resource: ../brainstorm-pieces/SKILL.md

sop: sign-a-document
version: 1.0.0
owner: the person a stopped cycle is waiting on
standard: skills/_kit-rules/alignment-threshold.md
last_reviewed: 2026-09-10
---

# Sign a document that is waiting on a person

## Purpose

Turn a stopped `AWAITING_REVIEW` into a decision, by the only party that can make it.

## Prerequisites

- A document with a `## Sign-off` or `## Reviewer sign-off` section.
- Nothing else. The score is not this procedure's business — see Escalation.

## Steps

1. **See what is waiting** — `/sign --list`, or
   `python3 skills/sign/scripts/sign_document.py --list`.
   An empty listing means nothing was FOUND waiting; it does not mean everything is
   signed.
2. **Read the preview** — `… <path> --as <you>`. It writes nothing. It shows the
   section verbatim, who git says wrote the file, and what your signature asserts.
3. **Read the document itself.** The preview shows the checklist, not the work. A
   signature over an unread document is the failure this whole gate exists to prevent.
4. **Sign** — add `--confirm`. If you also authored the document, add
   `--despite-authorship "<why>"`; the reason goes into the file.
5. **Run the gate.** This tool wrote a signature and computed nothing:
   - item brief → `python3 skills/plan-alignment/scripts/score_alignment.py <brief>`
   - product → `python3 skills/brainstorm-pieces/scripts/score_product_alignment.py`
6. **Read the new verdict.** `ALIGNED` / `PRODUCT_ALIGNED` means the chain may move.
   Anything else means the signature was not what was blocking it.

## What your signature claims, and what it does not

| Claims | Does not claim |
|---|---|
| You read this and are willing to say it holds | That a machine verified it |
| You are accountable for that judgement | That the score passed — a separate mechanism decides that |
| Which person, on which date | That no reviewer was available — unless you said so with `--despite-authorship` |

## Escalation

- The scorer still returns `NEEDS_REVISION` after you signed → the signature was not the
  blocker; the document is below the floor. → the document's author, to revise it.
- You are the author and no second reviewer exists → `--despite-authorship` with the
  reason. → nobody; you are recording a known weakness, not asking permission.
- The document has no sign-off section and you were told to sign it → the phase that
  produced it did not write one. → the skill that owns that phase.
- You signed and want it undone → untick a box. The gate reads the file, not the stamp,
  and the judge's own note says the same.
- A signature you did not make appears under your name → this tool takes `--as` at its
  word and cannot authenticate anyone. → treat it as a repository access question, not
  a tooling one.

## Competencies

- Telling "nothing is waiting" from "everything is signed".
- Reading `--despite-authorship` as a recorded weakness rather than a formality.
- Knowing that a signed document below the floor is still refused, and that this is
  correct.

## Cadence

On demand. There is no schedule: this exists because a cycle stopped and named a person.
