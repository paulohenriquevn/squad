# Cycle: BRAINSTORM

Source of Truth for the product-alignment cycle. Skills consume this; do not duplicate content into SKILL.md.

## Purpose

Produce, with a person in the room, the four documents that say **what the product
is** — and reach measured agreement on them before anything downstream is allowed
to run.

This is phase −1 of the Squad chain: it sits above `cycle-backlog`, which registers
units of work, because a unit of work is only meaningful against something it serves.
It exists for two reasons the rest of the pipeline cannot address on its own.

**The first is autonomy.** Every phase after `cycle-backlog` runs unattended. That is
the design, and it is only defensible if somebody agreed, once, on what the system is
building — otherwise an autonomous chain executes hunches at speed and calls the
throughput progress. This cycle is where that agreement is made, and it is **the only
cycle in the kit where a human is required**.

**The second is traceability.** `rules/current-constraint.md` states plainly that this
kit cannot detect local optimisation, because it does not instrument flow and *"a hard
gate asking whether this touches the constraint, against data that does not exist, would
be answered by assertion."* That limit stands. What this cycle adds is cheaper and
checkable: every backlog item names the objective it serves, so **an objective nothing
serves** and **shipped work serving no objective** both become computable facts rather
than impressions.

The cycle produces four documents and one verdict. It produces **no backlog items** —
`/backlog-init` and `/backlog-item` read these documents as context and remain the only
writers of the registry.

### What "any product" means here

These documents describe **whatever product adopts this kit**. Nothing in this cycle
names a domain, a stack or a company, and nothing may: the kit ships the *questions*,
and the answers are the adopter's. A vision document carried in from another ecosystem
is the same defect as an inherited routing table — `agents/README.md` records what that
cost when it was measured, and the shape does not change because the artifact is prose.

## Who runs it

**`iris-product-designer`.** The role decides what the user will experience and makes
it visible before it is built, refuses a brief describing a system in place of an
experience — which is gate G-B1 — and already holds the item-level alignment gate at
the same 90% floor over the same 17-criteria rubric. This cycle is that instrument
one level up.

She runs the cascade and generates the sign-off unticked. **She never signs it**, and
neither does any judge: see § Why the judge may not sign this one.

`kairos-product-owner` inherits the output rather than the phase — the `OBJ-N` ids
that backlog items cite through `traces_to`. The queue is his; what the queue serves
is not.

## Pre-conditions

Invoke `/brainstorm-vision` when ALL of:

- A person is available and will stay for the session. This cycle has no unattended
  mode, and adding one would defeat it.
- The scope is decided — which repository, umbrella or product this describes.
- `CHANGELOG.md` exists at the scope root (Unbreakable Rule 6).

Do NOT trigger BRAINSTORM for:

- **A single feature.** The unit here is the product. One feature is a `B-NNN`, and
  `/backlog-item` takes it in four questions.
- **Re-litigating a decision already recorded.** The documents are living and may be
  revised; reopening one needs a reason that changed, the same standard gate G5 applies
  at intake.
- **Producing a plan.** This cycle says what and why. `cycle-plan` says how, per item,
  and reaching for implementation detail here is the anti-pattern below.
- **Filling the backlog.** The registry has two writers and this is neither.

## Chain

```
scripts/build_agenda.py                  ← what the machine already knows needs you
     ↓ (open halts, unroutable items, prose blockers, recent kills,
     ↓  never-swept domains, orphan objectives, purposeless shipped work)
     ↓
/brainstorm-vision                       ← phase 1 · WHAT and FOR WHOM
     ↓ (produces: wiki/product/product-vision.md)
/brainstorm-objectives                   ← phase 2 · WHAT WE WANT TO ACHIEVE
     ↓ (produces: wiki/product/objectives.md · OBJ-N, each with a metric)
/brainstorm-trd                          ← phase 3 · WHAT IT MUST DO
     ↓ (produces: wiki/product/trd.md · REQ-N, each citing an OBJ-N)
/brainstorm-pieces                       ← phase 4 · WHAT IT IS MADE OF
     ↓ (produces: wiki/product/technical-pieces.md · PIECE-N, each citing a REQ-N)
     ↓
score_product_alignment.py               ← 90% floor + a human signature
     ↓
     ├── PRODUCT_ALIGNED   → /backlog-init, then the chain runs unattended
     ├── AWAITING_REVIEW   → structure done, nobody signed. Ask for the review
     ├── NEEDS_REVISION    → below the floor; re-enter at the weakest phase
     └── INVALID           → a document is missing, or a citation resolves to nothing
```

Each phase is invoked separately and on purpose. A single sitting that produces all four
documents produces its best thinking in the first and its most tired in the last — and the
last is the one every later phase reads.

## Phase contracts

| Phase | Input | Output | Hard gate |
|---|---|---|---|
| agenda | the registry + the event stream | the session's pauta | none — it informs, it never blocks |
| 1 · vision | the agenda + the person | `product-vision.md` | names a user, a problem, and what the product is NOT (G-B1) |
| 2 · objectives | the vision | `objectives.md` | every `OBJ-N` carries a metric and a horizon (G-B2) |
| 3 · trd | the objectives | `trd.md` | every `REQ-N` cites an `OBJ-N` that exists (G-B3) |
| 4 · pieces | the TRD | `technical-pieces.md` | every `PIECE-N` cites a `REQ-N` that exists (G-B3) |
| gate | all four | verdict | ≥ 90% AND a human signature (G-B4, G-B5) |

## Verdicts

| Verdict | Meaning | Downstream action |
|---|---|---|
| `PRODUCT_ALIGNED` | Four documents complete, score ≥ 90%, signed by a person | `/backlog-init` may run; the chain below it may run unattended |
| `NEEDS_REVISION` | Below the 90% floor | Re-enter at the phase the report names as weakest |
| `INVALID` | A document of the cascade is absent, or an id cites something that does not exist | Re-run that phase. No editing fixes a citation with no referent |
| `AWAITING_REVIEW` | Structure complete, nobody has signed | **Orthogonal to the three above.** Not a failure and not a pass — the machine finished and the person has not started |

`AWAITING_REVIEW` is the token `cycle-plan` already uses for the same state, and it is
already in `rules/blocking-verdicts.txt`, so an artifact resting on it is held everywhere
by the same list. Introducing a synonym would have created a second name for one state
and a second thing to keep in step.

## Hard gates

| # | Gate | Blocks on |
|---|---|---|
| G-B1 | **The vision names a user, a problem and a non-goal** (`score_product_alignment.py`) | A vision with no named user describes a system; a vision with no non-goal has not been decided, only wished. The non-goal is the half that is always omitted and the half that settles arguments later |
| G-B2 | **Every objective carries a metric and a horizon** (`score_product_alignment.py`) | "Be faster" is not an objective, it is a mood. Without a number, nothing can ever report the objective as met, and nothing downstream can trace to it |
| G-B3 | **Every citation resolves** (`score_product_alignment.py`) | A `REQ-N` citing an `OBJ-N` that does not exist, or a `PIECE-N` citing a missing `REQ-N`. This is the same rule the kit applies to a `file:line` — a pointer that does not resolve caps the artifact at `INVALID` |
| G-B4 | **90% floor on the rubric** (`score_product_alignment.py`) | The figure and its reasoning are `skills/_kit-rules/alignment-threshold.md`; this cycle reuses them rather than choosing a second number for the same purpose |
| G-B5 | **A human signature** (`score_product_alignment.py`) | The `## Sign-off` section unticked. **`alignment_judge.py` may NOT sign here** — see below |

### Why the judge may not sign this one

`skills/_kit-rules/alignment-threshold.md § Amended 2026-09-01` lets a judge sign an
*item's* alignment brief, and the argument is sound: the reviewer must not be the author,
and a judge is not the author. It also names what makes the judge acceptable — it reads
the item's **evidence**, which exists independently of the brief.

At product level there is no such independent evidence. The vision is not measured against
anything; it is the thing everything else is measured against. A judge scoring it would be
grading the document against itself, which is the exact failure the sign-off rule exists
to prevent, arriving through the door the amendment opened.

So the amendment does not extend here, and the two rules point at opposite signers for the
same reason. At item level the judge signs **because nobody is coming**. At product level
the person signs **because this is the one place they come**. Remove that signature and the
kit has no human input at all — every downstream gate would be measuring conformance to a
document nobody agreed to.

## Anti-patterns

- **Designing the solution.** The TRD says what must be true, not which library provides
  it. A requirement naming a framework has skipped `cycle-plan`, where that decision has a
  gate, an audit and a confidence score.
- **Objectives that cannot fail.** "Improve developer experience" closes never and is
  therefore never wrong. If no measurement could show the objective unmet, it is a value,
  not an objective — write it in the vision, where values belong.
- **A vision with no non-goal.** The section exists to be uncomfortable. Everything is in
  scope until someone writes down what is not.
- **Requirements with no objective.** They are somebody's preference wearing the document's
  authority. G-B3 refuses them, and the refusal is the point.
- **Filling the four documents to pass the scorer.** The rubric measures structure because
  structure is what a script can measure — it is a proxy for whether somebody could disagree
  with you, and beating the proxy beats nobody. `alignment-threshold.md` states the same
  limit for the item-level rubric and names the three things neither can score.
- **Running it unattended.** There is no flag for this and there must not be. A cycle whose
  entire purpose is human agreement, executed without a human, produces a document that
  agrees with its author.
- **Treating the documents as frozen.** They are `wiki/` content: durable knowledge with an
  owner and a review date, not a record of one execution. A product that never revises its
  objectives has stopped learning, and `rules/records-location.md` explains why that
  distinction has its own directory.
- **Re-running the whole cascade to change one objective.** Revise the document, re-score,
  re-sign. The cascade is the order things are *first* decided, not a ritual.

## Output

- `wiki/product/product-vision.md` — what the product is, who it is for, what it is not
- `wiki/product/objectives.md` — `OBJ-N`, each with a metric and a horizon
- `wiki/product/trd.md` — `REQ-N`, each citing the objective it serves
- `wiki/product/technical-pieces.md` — `PIECE-N`, each citing the requirements it realises
- `records/brainstorms/{date}-session.md` — the trail: what was discussed, what was
  discarded, and why

The split follows `rules/records-location.md`. The four documents are **knowledge**: they
evolve, they have an owner, they go stale, and the next reader wants the current version.
The session record is **a record**: one conversation on one day, immutable, and re-verifying
it would falsify what it is. A discarded idea lives only in the session record, which is
what makes it possible to answer "did we consider X?" a year later without the answer being
somebody's memory.

## Rollback

A document revised in error is corrected forward: edit it, re-score, re-sign, and note the
withdrawal in the session record of the day it happened. The four documents carry no history
of their own — `git` does — and a superseded objective keeps its `OBJ-N` id, never reused,
for the same reason a killed `B-007` stays `B-007`: items in the registry cite these ids, and
renumbering silently repoints every one of them.

## Cross-references

- Schema for cycle rules: [`rules/cycle-rule-schema.md`](cycle-rule-schema.md)
- The 90% floor, the rubric's limits, and why the author may not sign: [`skills/_kit-rules/alignment-threshold.md`](../skills/_kit-rules/alignment-threshold.md)
- Downstream bootstrap, which reads these documents as context: [`skills/backlog-init/SKILL.md`](../skills/backlog-init/SKILL.md)
- Downstream registry contract: [`rules/cycle-backlog.md`](cycle-backlog.md)
- Where the two output kinds live and why: [`rules/records-location.md`](records-location.md)
- What the system decides once alignment exists: [`rules/autonomy-envelope.md`](autonomy-envelope.md)
- The lens this cycle makes traceable: [`rules/current-constraint.md`](current-constraint.md)
- Phase declaration consumed by the drift checker: [`rules/cycle-phases.txt`](cycle-phases.txt)
