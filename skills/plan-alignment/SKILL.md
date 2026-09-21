---
name: plan-alignment
version: 0.3.0
requires: []
description: Bring one backlog item to ~90% shared understanding BEFORE any of it is built, by interrogating it and drawing it in the same pass. Produces an alignment brief (problem, functional and non-functional requirements with stable ids, four scenario classes, system design, interaction model, traceable acceptance criteria, out-of-scope, closed questions) plus an animated HTML walkthrough of every flow, then scores the result on seventeen criteria and hands an unticked review checklist to a reviewer who is not its author — a person, or `alignment_judge.py` when no person will. Below 90% machine score the item MUST NOT be implemented; without a sign-off it is not aligned either, and the signature records which kind it was. Use after DISCOVER has evidence and before /plan-write writes the plan, on any item where two people could read the description and picture different systems — which is most of them.
user-invocable: true
allowed-tools: Read Glob Grep Bash Write Edit AskUserQuestion
argument-hint: "{item-slug or B-NNN}"
---

# `/plan-alignment` — Grill it and draw it, until both sides see the same system

Two people read the same paragraph and picture different systems. The disagreement
is invisible in prose — everyone nods — and surfaces at review, after the work.
This skill exists to make it surface **before** the work, and to refuse the work
while it has not.

The method is one pass with two halves that feed each other:

| Half | What it does | Why it cannot be dropped |
|---|---|---|
| **Grill** | Interrogates the item, one question at a time, codebase-first | A diagram of a misunderstanding is a confident misunderstanding |
| **Draw** | Renders every flow as an animated walkthrough somebody can watch | A question nobody thought to ask is a gap prose never reveals |

Drawing generates the questions the interview would not have reached: to place an
arrow you must decide who calls whom, with what payload, and what happens when it
fails. Interviewing supplies the answers the drawing needs. Running them apart
produces a diagram of a vague brief, or a precise brief nobody can picture.

## Cycle contract

This skill is **phase 0** of [`cycle-plan`](../../rules/cycle-plan.md), and unlike
Phase 0 it is not optional for anything arriving from `BACKLOG.md`. It runs after
`/discover-plan` has evidence the item is real, and before `/plan-write` commits to how
it gets built. **Read `cycle-plan.md § Chain` before invoking.**

```
/discover-plan B-NNN        → evidence found, status: triaged
     ↓
/plan-alignment B-NNN → .squad/records/alignment/{slug}-alignment.md + {slug}-walkthrough.html
     ├── ALIGNED         → /plan-write
     ├── AWAITING_REVIEW → structure is done; nobody has signed off yet
     └── BLOCKED         → the item is NOT built; close the gaps and re-score
     ↓
/plan-write → /plan-confidence → /implement
```

The threshold, and the rule that the agent may never tick its OWN reviewer boxes,
are defined once in [`skills/_kit-rules/alignment-threshold.md`](../../skills/_kit-rules/alignment-threshold.md).
This file carries the protocol; that file carries the gate.

## Who may sign, and what each signature is worth

The rule is **not** that a human must sign. It is that **the author must not**.
Those are different rules, and reading the first for the second is what left this
skill's own judge unused for days while the autonomous loop halted at
`AWAITING_REVIEW` — the machinery existed, `score_alignment.py` already read its
signature, and nothing here said so.

| Signer | Marker | What it is worth |
|---|---|---|
| A person | `<!-- signed-by: human/{who} -->` | a review |
| `alignment_judge.py` | `<!-- signed-by: judge/alignment-judge -->` | a second agent that read the EVIDENCE, not only the brief, and could refuse |
| The author | — | nothing. Never |

`score_alignment.py` reports the **weakest** signer of a mixed set, so one
unattributed tick does not launder the rest, and `ALIGNED` by a judge and
`ALIGNED` by a person are visibly different claims to any reader.

**Invoke the judge when no reviewer is coming** — the unattended loop, a fleet
session, any run where waiting means the item never moves:

```bash
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/plan-alignment/scripts/alignment_judge.py" \
  .squad/records/alignment/{slug}-alignment.md \
  --model "<the model doing the judging>" \
  --verdict signed --reason "<what the evidence showed>"
```

It must be able to REFUSE, and refusing must cost the same as signing. A judge
that has never refused is a judge nobody has tested — pass `--verdict refused`
and the reason is written into the brief, where the next run reads it.

## Step 0 — Classify the path, out loud

Say the classification before the first question, so the human can override it.
Taken from `obra/superpowers`' brainstorming skill, whose framing is the one that
resolves the tension between rigour and KISS: **the ceremony scales with the task;
the approval gate never does.**

| Path | What it is | What this skill produces |
|---|---|---|
| **Spike** | A feasibility question whose output is an answer, not code you keep | The question and the probe, in 2–3 sentences. No brief, no walkthrough |
| **Bounded** | A change to a flow that **already exists in this repo** and can be read | A short brief, one flow drawn, reviewer sign-off still required |
| **Architectural** | A new subsystem, a new interface others depend on, or anything restructuring how components fit | The full brief, every scenario class drawn, reviewer sign-off |

Two rules make the classification honest:

- **Bounded measures the repo, not your familiarity.** If there is no existing flow
  to open and read, the item is not bounded, however well you understand the domain.
- **The ratchet is one-way.** Hidden complexity found mid-pass upgrades the path —
  stop, say so, step up. Nothing ever downgrades, and reaching for a lighter label
  to skip work *is* the doubt that should have upgraded it.

**Decompose before refining.** If the item describes independent subsystems, say so
immediately rather than spending questions on the details of something that has to
be split first. Each piece gets its own alignment.

## Step 1 — Read the evidence, then the code

Read the `B-NNN` block and whatever `cycle-discover` attached to it. Then read the
code the item touches. Every question you can answer from the repository is a
question you must not spend on the human — the codebase-first rule the retired `/grill-me`
enforces, for the same reason.

## Step 2 — Draft the brief from what you already know

Write `.squad/records/alignment/{slug}-alignment.md` **before** asking anything, filling
in every section you can. A draft with honest holes is a better interview
instrument than a blank page: a human corrects a wrong guess faster than they
answer an open question.

**Never fabricate to fill a hole.** Do not invent plausible requirements from a
product category, and do not ship `{{PLACEHOLDER}}` tokens. A brief that reads
complete and was partly guessed is the worst artefact this skill can produce,
because the guess is now written down in the reader's voice. This is the same
failure a baseline run measured on 2026-08-28: refusing a bad justification and
then **manufacturing a local one** to replace it. If you do not know, mark it and
ask. `score_alignment.py` scores any placeholder as 0 outright.

Required sections — exactly what the scorer measures:

```markdown
# Alignment: B-NNN — {title}

## Problem                     # observed HERE, with a measurement and a date
## Functional Requirements     # `- FR-001: <actor> shall <verb> <object>.`
## Non-Functional Requirements # `- NFR-001: p95 under 800ms at 50 rps.`  numbers, always
## Flows                       # `### <name> [primary|alternate|exception|recovery]`
## System design               # mermaid flowchart: components and what connects them
## Interaction                 # mermaid sequenceDiagram / classDiagram: who calls whom
## Acceptance Criteria         # `- AC-001 (FR-002): \`pytest …\` exits 0.`
## Dependencies                # named, or the word "none"
## Out of scope                # the boundary everybody otherwise assumes differently
## Questions answered          # `### Session YYYY-MM-DD` then `- Q: … → A: …`
## Demonstration               # how the result gets shown to somebody
## Walkthrough                 # link to the .html
## Reviewer sign-off           # generated UNTICKED. See Step 6.
```

**Stable ids are not decoration.** Every reference implementation converged on
them independently (spec-kit's `FR-###`/`SC-###`, feature-forge's EARS ids,
FredAntB's sequential `REQ-xxx`). Without an id, an acceptance criterion cannot
cite the requirement it closes, a task cannot cite either, and nothing traces.
Ids are sequential from `001` and never reused.

**Every requirement gets a criterion, and every criterion names its requirement.**
The scorer checks both directions, because both fail: a criterion citing nothing
proves nothing in particular, and a requirement no criterion cites ships unverified.

## Step 3 — Grill the holes, five questions, one per turn

The old budget was fifteen. spec-kit's `/clarify` caps at **five**, and the cap is
what forces the selection: a question that does not change the architecture, the
data model, the task breakdown, the test design or the operational posture is a
question you do not get to ask. Rank candidates by **Impact × Uncertainty** and
spend the budget from the top.

Scan for holes across these categories, marking each Clear / Partial / Missing —
they are the categories briefs are actually missing, not the ones they visibly lack:

| Category | What goes wrong when it is missing |
|---|---|
| Functional scope & roles | Two readers with different pictures of who does what |
| Domain & data model | Entities, identity, **state transitions**, volume assumptions |
| Interaction & UX flow | Error, empty and loading states nobody drew |
| Non-functional attributes | Latency, throughput, availability, observability, security |
| Integrations | External services and **their failure modes** |
| Edge cases | Negative paths, throttling, concurrent-edit conflicts |
| Constraints & tradeoffs | Rejected alternatives nobody wrote down |
| Terminology | The same concept under two names in two sections |
| Completion signals | Acceptance criteria that cannot fail |

Question form is part of the contract:

- A full interrogative ending in `?`, readable on its own. **A topic label is not
  a question** — `Acceptance device matrix (FR-023)` is invalid.
- One plain-language **"Why it matters"** sentence immediately after it, naming the
  stake for shipping.
- Your **recommended answer** with reasoning, so the human can nod instead of compose.
- One question per turn. Never a numbered list — that reads as a form, and a person
  facing three bullets answers the first.

**Two classes earn their turn above all others.** *Failure*: what happens when this
step does not succeed — most briefs describe only the happy path and most defects
live in the other one. *Boundary*: what is deliberately not covered — two people can
agree completely on what a thing does and disagree completely on what it does not.

**Stop early** when the remaining questions would not change the work, and say which
categories you are **deferring** and why. A quota reached with high-impact categories
unresolved must be flagged, not quietly dropped.

## Step 4 — Integrate each answer immediately

Write to disk after **every** accepted answer, not at the end. Two reasons, both
observed: context is lost between turns, and an answer held in memory is an answer
that gets paraphrased.

For each answer:

1. Append `- Q: <question> → A: <answer>` under `### Session YYYY-MM-DD` in
   `## Questions answered`. That section is the audit trail of the interview.
2. **Then apply it to the section it changes.** A functional answer edits the FR; a
   number edits the NFR; an edge case adds a flow.
3. **Replace the ambiguous statement — never leave it beside the answer.** A brief
   holding both the vague original and its clarification has two readings again,
   which is the state this whole skill exists to leave.

## Step 5 — Draw every flow, all four classes

**Write a spec. Do not place anything.**

```bash
# .squad/records/alignment/{slug}-walkthrough.yaml
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/plan-alignment/scripts/build_walkthrough.py" \
    .squad/records/alignment/{slug}-walkthrough.yaml \
    -o .squad/records/alignment/{slug}-walkthrough.html
```

```yaml
title: ...
subtitle: ...              # what to WATCH for, not what the diagram contains
direction: LR
nodes:
  api: { label: API gateway, kind: service }   # actor | service | store | external
flows:
  "Happy path [primary]":
    - { from: ui, to: api, label: POST /orders, payload: "...", note: "..." }
```

Read [`references/spec-format.md`](references/spec-format.md) before writing one.

**Never hand-place a node and never hand-draw a curve.** The first version of this
artefact asked its author for `x`/`y` percentages and shipped five layout defects
in one afternoon — nodes in a corner, three steps sharing one arc, labels stacked
16px apart, a lane fix that cancelled itself out, an edge crossing a node with its
label on that node's title. None of them were testable while a person chose the
coordinates: there is no invariant to violate, only an appearance to dislike in
the one case you happened to open. Graphviz owns the geometry now and the
invariants are asserted in `tests/`.
[`references/layout-engines.md`](references/layout-engines.md) has the reasoning
and the two-pass method; [`references/animation.md`](references/animation.md) has
what the page animates and why those three layers together.

The four scenario classes are each their own flow, tagged in the heading:

| Class | The question it answers |
|---|---|
| `[primary]` | What happens when everything works |
| `[alternate]` | The legitimate other route — empty result, cached hit, second tier |
| `[exception]` | A step fails: timeout, rejection, malformed input |
| `[recovery]` | The system comes back: retry, resume, rollback, reconciliation |

Tag them in the flow name — the generator and `score_alignment.py` both read the
tag. A reader clicks between them and sees the difference; in prose that
difference is a subordinate clause. A brief with one flow has not been thought
about, and the scorer says so rather than leaving it to the anti-pattern list.

`--check` validates the spec and lays it out without writing, and names every
problem at once. A worked example lives in
[`examples/alignment-gate.yaml`](examples/alignment-gate.yaml): the gate drawn by
the skill about itself, in all four classes.

`note` is where the thing a reader would get wrong goes. That sentence is the point
of the artefact — the animation shows what happens, the note says what people assume
instead. A walkthrough whose notes only restate the arrows has drawn the system
without surfacing a single disagreement.

## Step 6 — Score, then hand the judgement to a human

```bash
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/plan-alignment/scripts/score_alignment.py" \
    .squad/records/alignment/{slug}-alignment.md
```

Two independent conditions, and the verdict needs both:

| Condition | Who satisfies it |
|---|---|
| Machine score ≥ 90% over seventeen structural criteria | **You.** Iterate with `--machine-only` until it clears |
| Reviewer sign-off — every box in `## Reviewer sign-off` ticked | **A person, or `alignment_judge.py`. Never you.** |

Generate the checklist **unticked**, one item per thing a script cannot decide:

```markdown
## Reviewer sign-off
- [ ] CHK001 The stated problem is the one we actually have. [Judgement]
- [ ] CHK002 The flows drawn are the flows that matter. [Judgement]
- [ ] CHK003 The numbers in the NFRs are the right numbers. [Judgement]
```

**You must never tick a box.** The mechanism exists because the first version of
this skill had the agent writing the brief and running the scorer that approved it
— a gate grading its own homework. Ticking your own checklist restores exactly
that, with a checkbox drawn over it. Handing the brief to `alignment_judge.py`
does not: that judge did not write it, reads the evidence rather than the prose,
and signs under its own name. Add items when the item warrants them; never
remove one, and never mark one.

Do not argue with the machine score by rewording. A criterion scores on what is
checkable, so "responsive" becomes "p95 under 800ms at 50 rps" or it stays at 0.

## Step 7 — Walk it with the human

Open the walkthrough and step through each flow together. This is the falsifiable
moment the whole skill exists for: the instant a packet takes an edge the reader
did not expect, the gap is on screen and nobody has to be persuaded it exists.

Record every correction back into `## Questions answered`, apply it to the section
it changes, and re-score. On the re-score, **report regressions explicitly** — a
criterion that was at 2 and is now lower is a fact about the last edit, and a
before/after that only counts improvements hides it.

## Verdicts

| Verdict | Meaning | Downstream action |
|---|---|---|
| `ALIGNED` | Machine score ≥ 90% **and** every reviewer box ticked by someone who is not the author | `/plan-write {slug}` |
| `AWAITING_REVIEW` | Structure is complete; nobody has signed off | Ask for the review, or run `alignment_judge.py` when none is coming. Do not proceed unsigned |
| `BLOCKED` | Machine score < 90% | The item is **not** built. Close the listed gaps and re-run |
| `NEEDS_SPLIT` | The item describes independent subsystems, or cannot converge in five questions | Split; each piece aligns on its own |

`NEEDS_SPLIT` is **declared by the reviewer, never inferred**. Mark the brief:

```markdown
<!-- verdict: NEEDS_SPLIT: ingest and query are independent subsystems -->
```

`score_alignment.py` transports the marker and `check_alignment_gate.py` caps the
plan on it. Deciding that a description spans independent subsystems is judgement —
the same judgement left unmechanized at intake (gate G3) for the same reason: a
regex over a brief produces verdicts about language, not about the work.

The marker is checked **before** the score, because a split item scores low as a
consequence of being two items. Reporting `BLOCKED` would send the reviewer to close
gaps that no rewrite can close.

There is no "aligned with caveats". A caveat is an open question, and an open
question is what this skill exists to close.

## Anti-patterns

1. **Ticking your own review boxes.** The single failure the sign-off exists to
   prevent. A gate you can satisfy alone is not a gate.
2. **Drawing before grilling.** A diagram of a vague brief looks rigorous and is
   the most expensive kind of wrong: it makes the misunderstanding legible and
   therefore convincing.
3. **Grilling without drawing.** The interview stops at the questions somebody
   thought to ask. The drawing asks the ones nobody did, by refusing to place an
   arrow with no destination.
4. **Filling a hole with a plausible guess.** Inventing requirements from a product
   category, or a local problem to replace a rejected justification. Mark it and ask.
5. **Wording around the scorer.** Adding "measurable" to a requirement with no
   number. The rubric is a proxy for whether somebody can fail the work; defeating
   the proxy defeats only yourself.
6. **One flow.** Four classes exist because the defects live in three of them.
7. **Leaving the clarification beside the ambiguity.** The brief now has two
   readings, which is where it started.
8. **Batching questions, or asking one as a topic label.** Both turn an interview
   into a form, and a form gets the first answer only.
9. **Calling it bounded to skip the work.** Reaching for the lighter label is the
   doubt that should have upgraded the path.
10. **Treating 90% as a target rather than a floor.** The score exists to refuse
    work, not to decorate it.

## Does Not Own
- It does NOT write the plan — that is `/plan-write`, which reads this brief.
- It does NOT decide whether the item is worth doing — that is `cycle-discover`,
  upstream; an item arriving here already has evidence.
- It does NOT judge whether the content is right. It measures whether the content
  is *checkable*, says so, and hands the rest to a named human.

## Where the mechanisms came from

Read in full on 2026-08-28, and adopted rather than paraphrased:

| Source | What was taken |
|---|---|
| [`github/spec-kit`](https://github.com/github/spec-kit) | The five-question cap ranked by Impact × Uncertainty; the ambiguity taxonomy; dated clarification sessions written incrementally; "test the requirements, not the implementation"; the four scenario classes; and the **reviewer-owned checklist the agent may not mark** |
| [`obra/superpowers`](https://github.com/obra/superpowers) | Spike / bounded / architectural with a one-way ratchet; "the ceremony scales with the task, the approval gate never does"; the whole-document placeholder scan |
| [`jeffallan/claude-skills`](https://github.com/jeffallan/claude-skills) (`feature-forge`) | EARS-shaped requirements; the PM/Dev dual pass over the same brief |
| [`FredAntB/Spec-Driven-Development`](https://github.com/FredAntB/Spec-Driven-Development) | Sequential ids; the generation gate that lists the exact phrasings that do **not** license skipping it; the ban on fabricating requirements from a product category |
| [`melodic-software/claude-code-plugins`](https://github.com/melodic-software/claude-code-plugins) (`discovery/blindspot`) | Output calibrated to the human's disclosed starting point, not to a fixed depth |

## Files

| Path | What it is |
|---|---|
| `scripts/build_walkthrough.py` | Spec → self-contained animated HTML. Two Graphviz passes, no hand-placed coordinates |
| `scripts/score_alignment.py` | The 17-criterion machine score and the reviewer sign-off |
| `templates/walkthrough-shell.html` | The page the generator fills in. Animation and reading order only |
| `references/spec-format.md` | The YAML grammar — read before writing a spec |
| `references/layout-engines.md` | Why Graphviz, the two passes, and the traps in each |
| `references/animation.md` | Draw-on, motion path, arrival pulse, reduced motion |
| `examples/alignment-gate.yaml` | The skill drawn by itself, four scenario classes |

Requires Graphviz (`apt install graphviz` / `brew install graphviz`). The
generated page requires nothing.

## Related

- Gate: [`skills/_kit-rules/alignment-threshold.md`](../../skills/_kit-rules/alignment-threshold.md)
- Upstream: `/discover-plan` — supplies the evidence the brief opens with
- Downstream: `/plan-write` — the plan's `## Context` cites this brief
- 95%-confidence principle: `~/.claude/CLAUDE.md § 1`


## Scripts

| Script | Runs it | What it does |
|---|---|---|
| `check_criteria_discriminate.py` | on demand, before implementing | runs each acceptance criterion against the tree as it is and refuses the ones that already pass |


## Not every item needs the whole document

**Measured on a consumer over three days:** 93 items, 501 artefacts, 4 implementations,
**0 shipped**, and 78 hours of cycle time per item. The alignment briefs came to
**2,740 KB, signed by a person zero times** — 40-50 KB each, longer than the code they
describe, which measured 40 to 250 lines across the four items that reached a branch.
The walkthrough HTML added 1,032 KB across 38 files, an artefact made for a person to
look at, and none was opened.

`cycle-brainstorm` and `cycle-design` were already conditional. This phase was not, so
deleting an unreferenced package crossed the same phases as redesigning the data plane.

```bash
ECO=$([ -d .claude/skills ] && echo .claude || echo .)

python3 "$ECO/skills/plan-alignment/scripts/classify_alignment_depth.py" . B-NNN
```

| Depth | Produces | Exit |
|---|---|---|
| `LOCAL` | requirements with ids, acceptance criteria that execute, out-of-scope, closed questions, signature | 0 |
| `FULL` | all of that plus the prose sections, the four scenario classes, the system design, the interaction model and the walkthrough | 1 |

**Nothing a later phase consumes is dropped.** A criterion still has to discriminate,
`traces_to` still has to resolve, the 90% score still applies to what is there, and the
signature is still required. What LOCAL removes is the prose and the walkthrough.

**The classification is derived, never chosen.** An item needs the full document when
two readers could picture different systems from it — not directly measurable, so the
signals are:

| Signal | Forces FULL because |
|---|---|
| evidence spans modules | the change crosses a boundary two readers draw differently |
| the item is blocked | its shape depends on what lands first, so aligning it now aligns a guess |
| no DoD bullet names a command | the work is not concrete yet |
| mode is `evolve` | `cycle-backlog` defines it as changing what the system IS |

Any one means FULL, and **FULL is the default**: shallower is the irreversible
direction. A brief nobody wrote cannot be consulted later; one nobody needed only cost
time. Measured on that registry: 34 of 93 items (37%) are LOCAL.

## A criterion that passes before the work is not a criterion

The 17 machine criteria grade the brief's SHAPE. One of them — `acceptance_executable` —
asks whether a criterion names something that runs, from a text match over the bullet. It
never asks whether that command could run, or whether its answer distinguishes anything.

Measured on a consumer: a brief scored 14/14 executable where two criteria could not pass
at all, and `go test -run <pattern-that-matches-nothing>` exits 0 with `[no tests to
run]` — eight criteria in one brief were satisfied by writing no test.

`check_criteria_discriminate.py` runs them:

```bash
python3 "$ECO/skills/plan-alignment/scripts/check_criteria_discriminate.py" \
  .squad/records/alignment/B-001-alignment.md --repo-root .
```

A criterion that already passes cannot tell a finished item from an unstarted one. The
run refuses those, names the ones it could not run, and marks as **undecidable** — never
as sound — the ones whose bullet does not state what it expects.

**It checks one of three states, and says so.** The full method needs the intended state
and a deliberately wrong implementation the criterion must reject; the third is what
catches a criterion measuring a NAME rather than a behaviour. A reviewer's formulation is
worth keeping: *the minimal artefact that satisfies a criterion says exactly what it is
sensitive to.* If an empty function body with the right name turns it green, it measures
the name.

**It runs commands out of a document.** With a timeout, in the repository root, opt-in,
never from a hook or a scorer. Read what you are about to run if the brief did not come
from your own session.
