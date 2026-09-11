---
type: SOP
title: Run a review panel for a gated phase
description: Convene the assigned reviewers, brief each against the phase contract, invoke them, record the votes as they come back, and tally — with the limit the record cannot escape stated plainly.
tags: [procedure, governance, review]

# The OPERATOR's procedure. `SKILL.md` is the contract the agent executes; this is what
# a person needs to run a panel and read what comes back.
# Derived from the documents in `sources` — no step here was invented.
generated:
  by: claude/opus-5
  at: 2026-09-11
status: stable
sources:
  - id: contract
    resource: ./SKILL.md
  - id: roster
    resource: ../../rules/review-panel.txt
  - id: threshold
    resource: ../_kit-rules/alignment-threshold.md

sop: run-a-review-panel
version: 1.0.0
owner: whoever is advancing an artifact through a gated phase
standard: rules/review-panel.txt
last_reviewed: 2026-09-11
---

# Run a review panel for a gated phase

## Purpose

Turn `NO_RECORD` into a tallied verdict, with three reviewers who did not write the
artifact.

## Prerequisites

- The artifact exists and its structural gate has run. A panel asked to review an
  incomplete artifact reviews a different thing than the one that will ship.
- `check_panel_capability.py` reports HOLDS. A panel that cannot be formed is a
  premise violated at intake, not a per-item halt.

## Steps

1. **Assign** — `convene_panel.py --slug {slug} --phase {phase} --author {who} --write`.
   Name the author honestly; it is what keeps them off their own panel.
2. **Look at the assignment** — `panel_brief.py --slug {slug} --phase {phase}`. Three
   reviewers, two model families, and the artifacts they will read.
3. **Invoke each one** with its brief, unchanged —
   `panel_brief.py … --reviewer {agent}`.
4. **Record each vote** — `cast_vote.py …`. It refuses what the tally would refuse
   later, three invocations earlier.
5. **Tally** — `review_panel.py --record .squad/records/panels/{slug}-{phase}.json`.
6. **Read the dissent**, not only the outcome. An `APPROVED` carrying a `return` is an
   approval over a stated objection, and the objection travels with the record.

## Reading the outcome

| Outcome | Means | Next |
|---|---|---|
| `APPROVED` | 2 of 3, spanning two model families | the phase may advance |
| `RETURNED` | fewer than 2, or a majority inside one family | the artifact goes back with the dissent |
| *(refused)* | the panel is invalid — author on it, duplicate seat, thin reason | fix the panel, not the artifact |

**Two reviewers from the same family agreeing is not a majority here.** Correlated models
share failure modes: a plausible fabrication that survives one tends to survive its
siblings, which is what the outside seat is bought to catch.

## What a passing panel does not mean

It does not mean a model was called. The record is written by the session that was meant
to collect the votes, so three fabricated votes produce a file the tally accepts. What is
checked is form and standing, never independence — and no step in this procedure changes
that.

It does not mean a reason is true. Fifteen words naming what was checked against which
evidence is a floor on the shape of a reason, not on its honesty.

Read a panel as *"three reviewers were asked and this is what they said"*. That is worth
having. It is not worth more than it is.

## Escalation

- `check_panel_capability` reports VIOLATED → the roster cannot form a panel for this
  phase at all. → whoever owns `rules/review-panel.txt`; this is a repository defect.
- It reports UNREACHABLE → a reviewer is missing on THIS machine. → whoever owns the
  environment; the declaration is correct.
- A reviewer returns and you disagree → that is the panel working. Fix the artifact or
  record why the objection does not hold. → do not re-run the assignment to get a
  different roster.
- The phase has no golden rule → `panel_brief.py` refuses, and it is right to. A panel
  with no contract grades against taste. → add the contract before the panel.

## Competencies

- Telling an abstention from an approval. It is counted as an incomplete panel.
- Reading `APPROVED` with a dissent as what it is: approved over a stated objection.
- Resisting the shortcut of writing the votes. The refusals are about form; form is all
  they can be about, which is why the invocation has to be real.

## Cadence

Once per artifact per gated phase. Re-run only when the artifact changed — a panel
approves a revision, not a name.
