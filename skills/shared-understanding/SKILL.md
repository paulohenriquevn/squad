---
name: shared-understanding
version: 0.1.0
requires: []
description: Bring one backlog item to ~90% shared understanding BEFORE any of it is built, by interrogating it and drawing it in the same pass. Produces an alignment brief (problem, functional and non-functional requirements, flows, system design, interaction model, acceptance criteria, out-of-scope, closed questions) plus an animated HTML walkthrough of every flow, then scores the result against a 12-criterion rubric. Below 90% the item MUST NOT be implemented. Use after DISCOVER has evidence and before /to-plan writes the plan, on any item where two people could read the description and picture different systems — which is most of them.
user-invocable: true
allowed-tools: Read Glob Grep Bash Write Edit AskUserQuestion
argument-hint: "{item-slug or B-NNN}"
---

# `/shared-understanding` — Grill it and draw it, until both sides see the same system

Two people read the same paragraph and picture different systems. The disagreement
is invisible in prose — everyone nods — and surfaces at review, after the work.
This skill exists to make it surface **before** the work, and to refuse the work
while it has not.

The method is one pass with two halves that feed each other:

| Half | What it does | Why it cannot be dropped |
|---|---|---|
| **Grill** | Interrogates the item one question at a time, codebase-first | A diagram of a misunderstanding is a confident misunderstanding |
| **Draw** | Renders every flow as an animated walkthrough somebody can watch | A question nobody thought to ask is a gap prose never reveals |

Drawing generates the questions the interview would not have reached: to place an
arrow you must decide who calls whom, with what payload, and what happens when it
fails. Interviewing supplies the answers the drawing needs. Running them apart
produces a diagram of a vague brief, or a precise brief nobody can picture.

## Cycle contract

This skill is **Phase 0.5** of [`cycle-plan`](../../rules/cycle-plan.md), and unlike
Phase 0 it is not optional for anything arriving from `BACKLOG.md`. It runs after
`/discover-plan` has evidence the item is real, and before `/to-plan` commits to how
it gets built. **Read `cycle-plan.md § Chain` before invoking.**

```
/discover-plan B-NNN        → evidence found, status: triaged
     ↓
/shared-understanding B-NNN → records/alignment/{slug}-alignment.md + {slug}-walkthrough.html
     ├── score ≥ 90% → ALIGNED  → /to-plan
     └── score <  90% → BLOCKED → the item is NOT built; close the gaps and re-score
     ↓
/to-plan → /plan-confidence → /implement
```

The threshold and what it blocks are defined once, in
[`rules/alignment-threshold.md`](../../rules/alignment-threshold.md). Read it before
invoking. This file carries the protocol; that file carries the gate.

### When to skip

Skip when the item is genuinely small enough that no two readers could differ: a
single-line fix, a typo, a dependency bump, a revert. Everything else runs it. If
you are arguing about whether an item is small enough, it is not.

## Process

### Step 1 — Read the evidence, then the code

Read the `B-NNN` block and whatever `cycle-discover` attached to it. Then read the
code the item touches. Every question you can answer from the repository is a
question you must not spend on the human — the same codebase-first rule
`/grill-me` enforces, for the same reason.

### Step 2 — Draft the brief from what you already know

Write `records/alignment/{slug}-alignment.md` **before** asking anything, filling
in every section you can and marking the rest `UNKNOWN`. A draft with honest holes
is a better interview instrument than a blank page: the human corrects a wrong
guess faster than they answer an open question.

Required sections, which are exactly what the scorer measures:

```markdown
# Alignment: B-NNN — {title}

## Problem              # observed here, with a measurement and a date
## Functional Requirements    # >= 2, what the system must do
## Non-Functional Requirements # every one carries a NUMBER and a unit
## Flows                # `### {name}` each, broken into numbered steps
## System design        # mermaid flowchart: the components and what connects them
## Interaction          # mermaid sequenceDiagram or classDiagram: who calls whom
## Acceptance Criteria  # each names a command that can FAIL
## Dependencies         # named, or the words "none"
## Out of scope         # the boundary everybody otherwise assumes differently
## Questions answered   # every question raised, with its answer — no UNKNOWN left
## Demonstration        # how the result gets shown to somebody
## Walkthrough          # link to the .html
```

### Step 3 — Grill the holes, one question per turn

For each `UNKNOWN`, ask one question, with your recommended answer and its
reasoning. Wait. Never batch questions. Prefer the questions whose answers change
the drawing — an unanswered "what happens when the vendor times out?" is a missing
flow, not a missing sentence.

Two question classes earn their turn above all others:

- **Failure**: what happens when this step does not succeed? Most briefs describe
  only the happy path, and most defects live in the other one.
- **Boundary**: what is deliberately NOT covered? Two people can agree completely
  on what a thing does and disagree completely on what it does not.

### Step 4 — Draw every flow

Copy `templates/alignment-walkthrough.html` to
`records/alignment/{slug}-walkthrough.html` and fill in **only** `NODES` and
`FLOWS` at the top — the file is self-contained, has no build step and no
dependencies, and everything below the marked line is machinery.

```javascript
NODES  id -> { label, kind: actor|service|store|external, x, y }   // x/y in % of the stage
FLOWS  name -> [ { from, to, label, payload, note } ]
```

Draw the failure flows as their own entries, not as footnotes on the happy path.
A reader clicks between "Happy path" and "Vendor timeout" and sees the difference;
in prose that difference is a subordinate clause.

`note` is where the thing a reader would get wrong goes. That sentence is the
point of the artefact — the animation shows what happens, the note says what
people assume instead. A walkthrough whose notes only restate the arrows has
drawn the system without surfacing a single disagreement, and has not earned its
place.

### Step 5 — Score, and obey the score

```bash
python3 skills/shared-understanding/scripts/score_alignment.py \
    records/alignment/{slug}-alignment.md
```

Exit 0 is ALIGNED and the item may be planned. Exit 1 is BLOCKED: the report lists
every criterion below 2 and why. Close them and re-run. Do not argue with the
score by rewording — a criterion scores on what is checkable, so "responsive"
becomes "p95 under 800ms at 50 rps" or it stays at 0.

The scorer also prints what it did **not** measure — whether the stated problem is
the real one, whether the flows drawn are the flows that matter, whether the
numbers are the right numbers. Those are yours to judge, and a passing score never
claims them.

### Step 6 — Walk it with the human

Open the walkthrough and step through each flow together. This is the falsifiable
moment the whole skill exists for: the instant a packet takes an edge the reader
did not expect, the gap is on screen and nobody has to be persuaded it exists.

Record every correction back into `## Questions answered`, then re-score.

## Verdicts

| Verdict | Meaning | Downstream action |
|---|---|---|
| `ALIGNED` | Score ≥ 90%, walkthrough exists, every question closed | `/to-plan {slug}` |
| `BLOCKED` | Score < 90% | The item is **not** built. Close the listed gaps and re-run |
| `NEEDS_SPLIT` | Three or more flows, or the brief cannot converge in 15 questions | Split into items that each align on their own |

There is no "aligned with caveats". A caveat is an open question, and an open
question is what this skill exists to close.

## Anti-patterns

1. **Drawing before grilling.** A diagram of a vague brief looks rigorous and is
   the most expensive kind of wrong: it makes the misunderstanding legible and
   therefore convincing.
2. **Grilling without drawing.** The interview stops at the questions somebody
   thought to ask. The drawing asks the ones nobody did, by refusing to place an
   arrow with no destination.
3. **Wording around the scorer.** Adding the word "measurable" to a requirement
   with no number. The rubric is a proxy for whether somebody can fail the work;
   defeating the proxy defeats only yourself.
4. **Happy path only.** The flow list that contains exactly one flow has not been
   thought about. Ask what happens when each step fails.
5. **`UNKNOWN` left in the brief.** An open question wearing a closed coat. It
   costs the point precisely because it will otherwise be resolved by a guess
   during implementation.
6. **Skipping the walkthrough because "the mermaid diagram is enough".** A static
   diagram is read; an animated one is watched, and disagreement surfaces on a
   step, not on a picture.
7. **Treating the 90% as a target to reach rather than a floor to clear.** The
   score exists to refuse work, not to decorate it.

## What this skill does NOT do

- It does NOT write the plan — that is `/to-plan`, which reads this brief.
- It does NOT decide whether the item is worth doing — that is `cycle-discover`,
  upstream, and an item arriving here already has evidence.
- It does NOT judge whether the content is right. It measures whether the content
  is *checkable*, and says so.

## Related

- Gate: [`rules/alignment-threshold.md`](../../rules/alignment-threshold.md)
- Upstream: `/discover-plan` — supplies the evidence the brief opens with
- Downstream: `/to-plan` — the plan's `## Context` cites this brief
- Sibling interview skill: `/grill-me` — used alone when no drawing is warranted
- 95%-confidence principle: `~/.claude/CLAUDE.md § 1`
