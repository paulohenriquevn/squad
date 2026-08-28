# Alignment Threshold

An item nobody can draw is an item somebody is about to guess at. Below 90% shared understanding, it does not get built.

## The rule

**No backlog item may be implemented while its alignment score is below 90%.**

The score comes from `skills/shared-understanding/scripts/score_alignment.py`, run
against `records/alignment/{slug}-alignment.md`. Exit 0 permits the work; exit 1
forbids it. There is no band in between and no override for urgency — urgency is
the condition under which guessing is most expensive, not least.

## Why 90%, and why a score at all

"We understand each other" is the kind of claim this kit refuses everywhere else:
asserted, unfalsifiable, comfortable, and wrong at exactly the moments it matters.
Shared understanding cannot be measured directly. **Ambiguity can**, and ambiguity
is its inverse — so the rubric scores the artefact rather than the feeling.

90% is the figure the Definition-of-Ready literature uses for the same purpose:
score each criterion 0 (absent) / 1 (partial) / 2 (complete), require ≥90% of the
maximum to accept. It is deliberately high. At 70% an item passes with three of
its twelve criteria hollow, and the three hollow ones are never the harmless ones
— they are the boundary nobody wrote and the number nobody chose.

## What the rubric measures, and what it refuses to claim

Twelve criteria, scored on structure: a section exists, a requirement carries a
number, a flow has steps, an acceptance criterion names a command that can fail,
the boundary is written down, no question is left `UNKNOWN`, an animated
walkthrough exists.

Three things are **not** scored, and the report names them every time:

- whether the stated problem is the real one,
- whether the flows drawn are the flows that matter,
- whether the numbers in the requirements are the right numbers.

A script cannot decide those. Scoring them silently would make the number claim
more than it measured — the exact failure this kit calls evidence theatre. They
stay a human judgement, stated out loud rather than counted as passing.

## Where the gate sits in the chain

```
/backlog-item        → hypothesis, no evidence required, and no alignment required
/discover-plan       → evidence found or the item is killed
/shared-understanding → ALIGNED (≥90%) or BLOCKED
/to-plan             → refuses a slug with no ALIGNED brief
/implement           → refuses a plan whose item is not ALIGNED
```

The gate is deliberately **not** at intake. An item at intake is a hunch carrying
`evidence: none-yet` by design (`cycle-backlog.md § Hard gates`); demanding
requirements and diagrams from a hunch would collapse BACKLOG into PLAN and
silence exactly the mutter the registry exists to catch.

It is equally deliberately **not** at review. By review the code exists, and a
misunderstanding discovered there is paid for twice.

## What a BLOCKED item costs, and why it is cheaper

Blocking looks like delay and is not. The work of closing a gap is the same work
either way — deciding what the timeout does, choosing the latency number, naming
what is out of scope. The only variable is whether it happens before somebody
writes code against a guess or after. Before, it is a paragraph. After, it is a
paragraph plus a rewrite plus the review that found it.

## Anti-patterns

- **Reaching 90% by rewording.** Adding "measurable" to a requirement with no
  number. The rubric is a proxy for whether somebody can fail the work; beating
  the proxy beats nobody else.
- **Treating 90% as a target rather than a floor.** The score exists to refuse
  work. An item at 91% is barely permitted, not certified.
- **A single flow.** A brief describing only the happy path has not been thought
  about; every step that can fail is a flow that was not drawn.
- **Waiving the gate for a deadline.** The gate refuses the item, not the person.
  An item that must ship without alignment is an item shipping on a guess, and
  saying so is Rule 3, not obstruction.
- **`UNKNOWN` surviving into the plan.** It will be resolved during
  implementation, silently, by whoever hits it first.

## Cross-references

- Skill: [`skills/shared-understanding/SKILL.md`](../skills/shared-understanding/SKILL.md)
- Scorer: `skills/shared-understanding/scripts/score_alignment.py`
- Upstream gate on evidence: [`cycle-backlog.md`](cycle-backlog.md) § Hard gates
- Downstream gate on plans: [`plan-confidence-golden-rule.md`](plan-confidence-golden-rule.md)
- Honesty principle the unscored items serve: `~/.claude/CLAUDE.md § 3`
