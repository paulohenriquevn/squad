---
type: concept
title: A reference is checked in one direction
description: Four cross-reference checks found in one day, each careful in the direction its author was thinking about and silent in the other. Why the missing half is invisible, and the two questions that find it before shipping.
tags: [decision, gates, references, honesty, adr]

generated:
  by: claude/opus-5
  at: 2026-09-22
status: stable
sources:
  - id: matrix
    resource: ../../skills/plan-confidence/scripts/check_coverage_matrix.py
  - id: design
    resource: ../../skills/design/scripts/check_design_completeness.py
  - id: product
    resource: ../../skills/brainstorm-pieces/scripts/score_product_alignment.py
  - id: steps
    resource: a-step-that-cannot-fail-loudly-did-not-run.md
---

# A reference is checked in one direction

## Four measurements, one shape

On 2026-09-22 a sweep of this kit's identifier vocabularies found four cross-reference
checks with the same defect. None was careless — each is the work of somebody who thought
hard about the direction they were facing.

**1. The Coverage Matrix counted a row without opening the task it named.** A row reading
`| G1 | something | T1.1 | AC-999 |` counted as mapped with `AC-999` declared nowhere. The
TASK relation was checked BOTH ways — a row naming no task is unmapped, a task no row names
is an orphan — and the rest of the row in neither.

**2. A review finding carried a path nobody opened.** `consolidate_findings` rendered the
`file`, deduped on it and computed the verdict from the set. One BLOCKER at a path that
exists nowhere produced `NEEDS_FIXES` with nothing saying so.

**3. The system map could draw a piece nobody declared.** Coverage ran pieces → map, and
the map was never read back. `_mentions` even carries a careful comment about matching the
WHOLE id, because `PIECE-1` is a substring of `PIECE-10` — the author was rigorous about
that once, and never asked it the other way round.

**4. A goal nothing serves reached DESIGN.** Both citations pointing UP the product chain
resolve — `serves:`, `realises:` — and whether every objective is SERVED was asked nowhere
in the phase that writes all four documents.

## Why the missing half is invisible

A cross-reference has two sides and one author. The author writes the check while holding
one side in mind — *does this row point at a real task?* — and the code that answers it is
complete, correct, and tested. The other question is not wrong; **it is absent**, and
absence has no failing test, no red line, no symptom.

It stays absent because the two questions are not symmetric in consequence, so nothing
makes the reader ask for the second:

    a piece missing from the map    work the drawing forgot
    a piece in the map nobody declared    the map drawing something no one decided

    a row citing a task that does not exist    the plan lost a task
    a row citing a criterion nobody declares    the row is hollow and the ratio says 1.0

Each pair reads as one topic and resolves to two findings. The half that is checked is
usually the one that sounds like the check's name.

## What makes it worse than a missing check

A gate that does not exist is honestly absent. A gate that checks one direction **reports a
verdict** — and that verdict is read as covering the topic, because its name says so.
`is_complete: True` over a matrix whose rows point at nothing is not silence; it is an
assertion, and it is the assertion somebody acts on.

That is the difference from
[a step that cannot fail loudly did not run](a-step-that-cannot-fail-loudly-did-not-run.md).
There, a step did nothing and said nothing. Here, half a check says everything is fine.

## The two questions

Before shipping a check over a reference between two documents:

1. **If the target did not exist, would anything say so?**
2. **If the target existed and nothing pointed at it, would anything say so?**

If either answer is no, the missing half is either work or a recorded decision that it is
out of scope — and the decision belongs in the code, where the next reader is.

## Keep the findings apart

In every one of the four, the two directions turned out to be different findings that a
reader acts on differently. `criteria_not_declared` caps; `criteria_not_cited` reports.
`piece_not_in_map` says the drawing forgot; `piece_not_declared` says the drawing invented.
Folding them into one count would make a single number out of two questions, which is the
defect in
[a claim about now is not a fact that survives](a-claim-about-now-is-not-a-fact-that-survives.md),
arrived at from the other side.

## And guard the unmeasurable case

Three of the four fixes needed the same guard: when the target DOCUMENT is missing or
unreadable, report nothing rather than reporting everything as unresolved. A TRD that is
not there does not mean every objective is unserved — it means coverage was not checked,
and turning that into a measurement is the thing this kit is organised to refuse.
