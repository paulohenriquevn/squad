---
type: SOP
title: Run the critic for a phase nothing else reviews
description: Brief a critic against the phase's contract, record its round, and let the agent fix what was named — the chain keeps moving, and only an exhausted disagreement escalates.
tags: [procedure, governance, review]

# The OPERATOR's procedure. `SKILL.md` is the contract the agent executes; this is what a
# person needs to run a critic and read what comes back.
# Derived from the documents in `sources` — no step here was invented.
generated:
  by: claude/opus-5
  at: 2026-09-11
status: stable
sources:
  - id: contract
    resource: ./SKILL.md
  - id: population
    resource: ../../rules/critic-phases.txt
  - id: bands
    resource: ../../rules/verdict-bands.txt

sop: run-a-phase-critic
version: 1.0.0
owner: whoever is advancing a phase that nothing else reviews
standard: rules/critic-phases.txt
last_reviewed: 2026-09-11
---

# Run the critic for a phase nothing else reviews

## Purpose

Give acceptance, code-quality, backlog and release the reader they do not have — without
stopping the autonomous chain to get it.

## Prerequisites

- The phase emitted its verdict. A critic asked before that reviews a draft rather than
  the thing that will ship.
- The phase is in `rules/critic-phases.txt`. If it is not, it has a panel or a judge
  already, and a critic there is a fourth opinion over three.

## Steps

1. **Read what this critic is asked** —
   `critic_round.py --phase {phase} --slug {slug} --brief`.
   The brief carries the contract, the question, and **every prior round**.
2. **Invoke a critic with that brief, unchanged.** A critic that composes its own
   question judges the phase against whatever it framed.
3. **Record the round** — `--verdict accepted|returned --finding "…"`.
4. **Act on the exit code**, which is the whole point:

| Exit | Outcome | What you do |
|---|---|---|
| 0 | `CRITIC_ACCEPTED` | advance |
| 1 | `CRITIC_RETURNED` | **the agent fixes what was named and re-runs the phase.** Nothing waits for you |
| 3 | `CRITIC_EXHAUSTED` | hand to `halt_disposition.py` |
| 2 | refused | no critic for this phase, or the finding is too thin |

## Reading a returned round

**It is not a failure.** It is the phase working: something was named, and the agent can
fix it without anyone being paged. `CRITIC_RETURNED` sits in the `redo` band on
`FAIL_SOFT`'s argument — walling ordinary rework *"would wall every loop that is working
correctly"*.

**`CRITIC_EXHAUSTED` is a failure to CONVERGE, not a failure of the work.** The critic and
the agent did not agree inside the declared rounds. That is a different fact and takes a
different action: `halt_disposition.py` decides whether the item returns to the registry
or waits for a person, exactly as it does for every other stop in this kit.

## What a passing critic does not mean

It does not mean a model was called. The round is recorded by the session that was meant
to run the critic, so a fabricated round produces a file this accepts — the same limit
`check_panel_approval.py` states about the panel record.

It does not mean the finding was true. Ten words naming what to change is a floor on the
shape of a finding, not on its correctness.

## Escalation

- A critic returns the same finding twice → the agent is not addressing it, or the
  finding is not actionable. → read both rounds in the record before spending the third.
- `CRITIC_EXHAUSTED` on acceptance → the delivery is contested and the milestone
  checkbox has not flipped. → `halt_disposition.py`; do not flip it manually.
- You want to raise `max_rounds` to settle an argument → don't. The ceiling is what
  keeps a disagreement from becoming an invisible halt. → change the contract, or record
  the concern as accepted and file it.
- The phase you want criticised is not declared → it has a panel or a judge. → check
  `rules/review-panel.txt` before adding one.

## Competencies

- Reading `CRITIC_RETURNED` as the loop working rather than as a blocker.
- Telling "did not converge" from "the work is wrong".
- Resisting a fifth reviewer on a phase that already has three.

## Cadence

Once per phase run, on the four declared phases. Re-run only when the phase re-runs.
