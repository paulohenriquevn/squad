# Alignment Threshold

An item nobody can draw is an item somebody is about to guess at. Below 90% shared understanding, it does not get built.

## The rule

**No backlog item may be implemented until two independent conditions hold.**

| Condition | Who satisfies it | Verdict if missing |
|---|---|---|
| Machine score ≥ 90% over the structural rubric | The agent | `BLOCKED` |
| Every box in `## Reviewer sign-off` ticked | **A reviewer who is not the author** | `AWAITING_REVIEW` |

Both come from `skills/plan-alignment/scripts/score_alignment.py`, run against
`records/alignment/{slug}-alignment.md`. Exit 0 permits the work; exit 1 forbids it.
There is no band in between and no override for urgency — urgency is the condition
under which guessing is most expensive, not least.

## The AUTHOR may not tick the reviewer's boxes

This is the half of the rule that a script cannot enforce, and it is the more
important half.

The first version of this gate had one number, and the agent that wrote the brief
was the same agent that ran the scorer that approved it. That is a gate grading its
own homework. It looked rigorous — a rubric, a threshold, a report — and measured
only whether the author had filled in the author's own form.

Five reference implementations were read on 2026-08-28 looking for how anyone else
had solved it. Only one had: `github/spec-kit` makes its requirements checklist
**reviewer-owned** — generated unticked, ticked only by a human, and its
`/implement` reads the boxes as a gate and *may not modify the markers*.

So:

- The agent **generates** `## Reviewer sign-off`, always unticked, one item per
  thing the script cannot decide.
- The agent **may add** items when the work warrants them.
- The agent that wrote the brief **may never tick one, remove one, or delete the
  section.** Doing so is a Rule 3 (honesty) violation, not a shortcut — it
  fabricates a judgement nobody made.
- A brief with no checklist is not signed off either. An absent gate is not a
  passed one.

### Amended 2026-09-01 — the reviewer need not be a person

This rule said *"a human, never the agent"* for most of its life, and the sentence
did two jobs at once. Only one of them was the argument: **the author must not
grade the author's own form.** The other — that the reviewer must be human — never
followed from it, and it is what left the autonomous loop halted at
`AWAITING_REVIEW` with the machinery to clear it already on disk and unused.

`skills/plan-alignment/scripts/alignment_judge.py` may sign. It satisfies the
argument this rule actually makes:

- **it did not write the brief**, so it is not grading its own form;
- **it reads the item's EVIDENCE, not only the brief** — a brief that is internally
  tidy and describes work nobody measured is exactly what a self-approving author
  produces, and only the evidence exposes it;
- **it can refuse, and refusing costs what signing costs.** A judge that has never
  refused is a judge nobody has tested;
- **it signs under its own name** — `<!-- signed-by: judge/alignment-judge -->` —
  so `ALIGNED` by a judge and `ALIGNED` by a person are different claims that a
  reader tells apart without opening the file. `score_alignment.py` reports the
  **weakest** signer of a mixed set, so one unattributed tick cannot launder
  the rest.

**Who this affects.** Every consumer running the chain unattended: the halt at
`AWAITING_REVIEW` was permanent for them, because nobody was coming.

**What it does not change.** The 90% machine score, the ban on the author signing,
`NEEDS_SPLIT` staying a reviewer's declaration, and the absence of any `--skip`.
A judge's signature is a weaker claim than a person's and is recorded as one; it
is not a way past the gate, it is the gate answered by somebody else.

**What was rejected.** Leaving the rule as it stood and letting the loop halt —
which is not neutral: it discards work already measured and understood, and the
envelope names that failure explicitly. Also rejected: letting the author sign
when no reviewer is available, which would have kept the letter of the rule and
destroyed its reason.

`AWAITING_REVIEW` is a normal, expected state. It means the structure is done and
the judgement has not been made yet. It is not a failure and it is not an
invitation to proceed.

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

Seventeen criteria, scored on structure: a section exists, a requirement carries a
number and a stable id, every acceptance criterion cites the requirement it closes,
all four scenario classes are drawn, no unquantified quality adjective survives in a
requirement, no placeholder survives anywhere, the boundary is written down, and an
animated walkthrough exists.

Three things are **not** scored, and the report names them every time:

- whether the stated problem is the real one,
- whether the flows drawn are the flows that matter,
- whether the numbers in the requirements are the right numbers.

A script cannot decide those. Scoring them silently would make the number claim
more than it measured — the exact failure this kit calls evidence theatre. They
stay a human judgement, stated out loud rather than counted as passing.

## What enforces it

Two layers, and the rule was PROSE in three documents until they existed —
`alignment-threshold.md`, a pre-condition in `cycle-implement.md`, a phase
contract in `cycle-plan.md`. A grep for anything reading `records/alignment/`
returned nothing. Three documents said the item must not be built; no code
could stop it.

| Layer | Where | Effect |
|---|---|---|
| `skills/plan-confidence/scripts/check_alignment_gate.py` | inside `run_structural.py` | Hard cap 49 → `INVALID`. `cycle-plan` needs ≥ 70 to enter `/implement`, so an unaligned plan cannot get there |
| the same check, re-run in `skills/implement/scripts/run_validation.py` | end of `/implement` | `FAIL`. The last line, for the path that reached `/implement` without passing through `plan-confidence` |

There is **no `--skip` and no dismissing ADR** on this cap, unlike every other
one in `plan-confidence`. An escape hatch here is an escape hatch on the reason
the gate exists.

## The bypass that remains, stated rather than hidden

A plan citing no `B-NNN`, with no alignment brief for its slug, may be a
legitimate ad-hoc fix — or an item that skipped intake precisely to skip this
gate. **No check separates those.** Claiming otherwise would be the fabricated
precision this kit refuses elsewhere.

So that case takes a soft floor of 89 (`plan-confidence`) and a `WARN`
(`/implement`), both naming the reason. It stays out of `SHIPPABLE` and lands in
front of a human, which is where the same kind of judgement lives in
`cycle-backlog.md` § Hard gates. Closing it mechanically would mean refusing every
one-line hotfix, and a gate that fires on ordinary work is a gate somebody
disables.

## Where the gate sits in the chain

```
/backlog-item        → hypothesis, no evidence required, and no alignment required
/discover-plan       → evidence found or the item is killed
/plan-alignment → ALIGNED (≥90%) or BLOCKED
/plan-write             → refuses a slug with no ALIGNED brief
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

- **Ticking the reviewer's boxes.** The one anti-pattern that defeats the whole
  gate, and the only one that is dishonest rather than merely lazy.
- **Reaching 90% by rewording.** Adding "measurable" to a requirement with no
  number. The rubric is a proxy for whether somebody can fail the work; beating
  the proxy beats nobody else.
- **Treating `AWAITING_REVIEW` as a pass.** It is the state where the machine has
  finished and the human has not started.
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

- Skill: [`skills/plan-alignment/SKILL.md`](../skills/plan-alignment/SKILL.md)
- Scorer: `skills/plan-alignment/scripts/score_alignment.py`
- Upstream gate on evidence: [`cycle-backlog.md`](cycle-backlog.md) § Hard gates
- Downstream gate on plans: [`plan-confidence-golden-rule.md`](plan-confidence-golden-rule.md)
- Honesty principle the unscored items serve: `~/.claude/CLAUDE.md § 3`
