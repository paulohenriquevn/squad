---
name: brainstorm-pieces
version: 0.1.0
requires: [brainstorm-trd]
description: 'Name the technical pieces the product is made of — PIECE-N components, each citing the REQ-N requirements it realises — then run the product-alignment gate that decides whether the whole cascade is agreed. Use this after /brainstorm-trd to close the brainstorm cycle. This is phase 4 of cycle-brainstorm and the gate the autonomous pipeline rests on: it scores the four documents against a 90% floor and REFUSES to sign them itself, because a judge grading a product vision would be grading it against nothing.'
user-invocable: true
allowed-tools: Read Glob Grep Bash Write Edit AskUserQuestion
argument-hint: "[scope-name]"
---

# `/brainstorm-pieces` — What it is made of, and whether we agree

Phase 4 of four. Produces `wiki/product/technical-pieces.md` and
`wiki/product/alignment.md`, then runs the gate that emits the cycle's verdict.

## Cycle contract

This skill is **phase 4** of [`cycle-brainstorm`](../../rules/cycle-brainstorm.md),
the source of truth for the chain, gates G-B1 to G-B5, and the verdicts.

**Read `cycle-brainstorm.md` before invoking.**

## Pre-conditions

- `wiki/product/trd.md` exists and every `serves:` citation resolves.
- The same person from phases 1 to 3 is present. **This phase cannot complete
  without them** — see the gate below.

## What a piece is

A **responsibility with a boundary**, not a file and not a service. The question it
answers is *"what part of the system owns this?"*, and the useful granularity is the
one where responsibilities differ — the same cut `agents/README.md` prescribes for
domain specialists: *"one agent per repo rots once per copy, one agent per role is
too coarse."*

A piece may map to a repo, several repos, or part of one. The mapping is not decided
here; `/backlog-init` inventories repos from disk afterwards, and a piece that turns
out to have no repo is a finding worth having.

## Process

### Step 1 — The session (2 questions per piece, ONE per turn)

| # | Question | Feeds | Refused when |
|---|---|---|---|
| 1 | What part of the system owns this, and what is it responsible for? | `responsibility` | Two pieces claim the same responsibility, or one piece claims all of them |
| 2 | Which requirements does it realise? | `realises` | It realises none. **G-B3 refuses it** — a piece serving no requirement is architecture nobody asked for |

After the last piece, run the reverse check out loud: **is every `REQ-N` realised by
some piece?** A requirement no piece realises is agreed work with nobody to do it,
and it is far easier to see now than after the backlog exists.

### Step 2 — Write

```markdown
# Technical pieces — {scope}

## PIECE-1 — {title}
realises: REQ-1, REQ-2
responsibility: {what this part owns}
```

### Step 3 — Generate the sign-off, unticked

Write `wiki/product/alignment.md` with the checklist **always unticked**:

```markdown
# Product alignment — {scope}

## Reviewer sign-off

- [ ] The problem stated in the vision is the real one
- [ ] These are the right objectives, and the metrics are the right metrics
- [ ] The requirements follow from the objectives
- [ ] The pieces cover every requirement

<!-- signed-by: -->
```

**The agent generates this section and may never tick a box, remove one, or delete
the section.** That rule is `skills/_kit-rules/alignment-threshold.md`, and it is
the half a script cannot enforce. Ticking a reviewer's box fabricates a judgement
nobody made — a Rule 3 violation, not a shortcut.

The four boxes are exactly the three things the scorer reports as **not scored**,
plus coverage. That is deliberate: the checklist covers what the number cannot, so
the two together mean something the score alone does not.

### Step 4 — Run the gate

```bash
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/brainstorm-pieces/scripts/score_product_alignment.py" --root .
```

| Verdict | Exit | What it means | Do |
|---|---|---|---|
| `PRODUCT_ALIGNED` | 0 | ≥ 90%, every citation resolves, signed by a person | `/backlog-init` — the chain below may run unattended |
| `AWAITING_REVIEW` | 1 | Structure complete, nobody signed | **Ask for the review.** Not a failure, not a pass |
| `NEEDS_REVISION` | 1 | Below the floor, or a floor cap fired | Re-enter at the phase the report names |
| `INVALID` | 2 | A document is missing, or a citation has no referent | Re-run that phase; editing cannot fix it |

### Step 5 — The signature is a person's, and only a person's

`alignment-threshold.md § Amended 2026-09-01` lets `alignment_judge.py` sign an
**item's** brief, because the judge reads the item's evidence — something that
exists independently of the brief and can contradict it.

**That amendment does not reach here, and the scorer enforces it**: a
`signed-by: judge/…` returns `AWAITING_REVIEW`. At product level there is no
independent evidence — the vision is what everything else is measured against, so a
judge scoring it grades the document against itself.

The two rules point at opposite signers for the same reason. At item level the judge
signs *because nobody is coming*. Here the person signs *because this is the one
place they come*. Remove this signature and the kit has no human input at all.

### Step 6 — Emit and hand off

```bash
python3 "$([ -d .claude/scripts ] && echo .claude || echo .)/mechanisms/cycle/cycle_events.py" end \
    --cycle brainstorm --slug {scope} --verdict {PRODUCT_ALIGNED|AWAITING_REVIEW|NEEDS_REVISION|INVALID}
```

Emit `AWAITING_REVIEW` too. `rules/cycle-maintenance.md` is explicit that stopping
at a human gate is a phase **ending**, not a phase skipping: an item worked and left
silent is indistinguishable from one nobody touched, and a watchdog seeing no event
concludes the command never landed and starts it again.

```
PRODUCT_ALIGNED  94.1% (32/34, floor 90%)
  signed by: {person}
  4 objectives · 9 requirements · 6 pieces

Next step:  /backlog-init      (reads these four documents as context)
```

## Anti-patterns

- **Ticking your own boxes.** The one anti-pattern that defeats the whole gate, and
  the only one that is dishonest rather than merely lazy.
- **Reaching 90% by rewording.** The rubric is a proxy for whether somebody could
  disagree with you. Beating the proxy beats nobody.
- **One piece per repo you already have.** That describes the current system, which
  is what the requirements were supposed to be free to contradict.
- **Treating `AWAITING_REVIEW` as a pass** because the number looked good. It is the
  state where the machine finished and the person has not started.
- **Filing backlog items from here.** This cycle writes no items. `/backlog-init`
  and `/backlog-item` are the registry's only two writers.

## Cross-references

- Cycle rule (source of truth): [`rules/cycle-brainstorm.md`](../../rules/cycle-brainstorm.md)
- Previous phase: [`skills/brainstorm-trd/SKILL.md`](../brainstorm-trd/SKILL.md)
- The threshold, the unscored three, and the author rule: [`skills/_kit-rules/alignment-threshold.md`](../_kit-rules/alignment-threshold.md)
- Downstream bootstrap: [`skills/backlog-init/SKILL.md`](../backlog-init/SKILL.md)
- Why a human gate still emits an event: [`rules/cycle-maintenance.md`](../../rules/cycle-maintenance.md)
