---
name: brainstorm-vision
version: 0.1.0
requires: []
description: 'Run the product-vision session with a person: what the product is, who it is for, the problem it solves, and — the half that is always omitted — what it is explicitly NOT. Use this at the start of a product, when adopting the kit into a new scope, or when the answer to "what are we actually building?" differs depending on who you ask. This is phase 1 of cycle-brainstorm, the ONLY cycle in the kit where a human participates; everything after the backlog runs unattended. It writes .squad/wiki/product/product-vision.md and never a backlog item.'
user-invocable: true
allowed-tools: Read Glob Grep Bash Write Edit AskUserQuestion
argument-hint: "[scope-name]"
---

# `/brainstorm-vision` — What the product is, and what it is not

Phase 1 of four. Produces `.squad/wiki/product/product-vision.md`: the document every
objective, requirement and piece downstream is measured against.

## Cycle contract

This skill is **phase 1** of [`cycle-brainstorm`](../../rules/cycle-brainstorm.md).
The cycle rule is the **source of truth** for the chain, the four documents, the
verdict vocabulary, gates G-B1 to G-B5, and why a judge may not sign this one.

**Read `cycle-brainstorm.md` before invoking.** This file retains only the session
protocol below.

## Why this one has a human in it

Every phase after `cycle-backlog` runs unattended, and that is only defensible if
somebody agreed once on what is being built. Otherwise the chain executes hunches
at speed and the throughput reads as progress.

So this session is not a formality before the real work. It is the input the
autonomy rests on, and `rules/autonomy-envelope.md` already says as much: *"What
the human owns: the backlog… that is where a person's judgement is irreplaceable,
because it is the only judgement that is about the product rather than about the
work."* This phase is where that judgement is written down.

## When NOT to invoke

- **`.squad/wiki/product/product-vision.md` already exists and still holds.** Revise it
  directly and re-score; the cascade is the order things are first decided, not a
  ritual to repeat.
- **For one feature.** That is a `B-NNN`. `/backlog-item` takes it in four questions.
- **With nobody in the room.** There is no unattended mode and adding one would
  defeat the phase — a vision agreed with its own author agrees with everything.

## Process

### Step 0 — Pre-flight (MANDATORY, fail-fast)

```bash
ECO=$([ -d .claude/skills ] && echo .claude || echo .)

test -f CHANGELOG.md || { echo "FATAL: CHANGELOG.md missing (Unbreakable Rule 6)"; exit 1; }
mkdir -p .squad/wiki/product .squad/records/brainstorms 2>/dev/null
test -w .squad/wiki/product || { echo "FATAL: .squad/wiki/product not writable"; exit 1; }
```

### Step 1 — Build the agenda BEFORE asking anything

```bash
python3 "$ECO/skills/brainstorm-vision/scripts/build_agenda.py" --root .
```

This is the half of the session the machine owns. It collects what already stalled
for want of a person: halted items, unroutable repos, `blocked_by` lines naming a
decision rather than an id, objectives nothing serves, shipped work serving no
objective, domains nobody ever swept.

**Read it aloud to the user before the first question.** They are the only human
touchpoint in the pipeline, so anything waiting on a human is waiting on this
session — and a person who is not shown the queue cannot clear it.

It reports and never decides. Nothing in it is a priority order, and no item's
status changes because it appeared here.

### Step 2 — Emit the phase start

```bash
python3 "$ECO/mechanisms/cycle/cycle_events.py" start --cycle brainstorm --slug {scope}
```

Without it the board can only draw what FINISHED, and a session under way is
indistinguishable from one nobody began.

### Step 3 — The session (4 questions, ONE per turn)

Same protocol as every grill in the kit: one question per turn, each with a
recommended answer and its reasoning, persisted after every answer.

| # | Question | Why it must be answered |
|---|---|---|
| 1 | Who is this for? Name them concretely — a role, a situation, a person you can picture. | A vision with no named user describes a system rather than a product, and every later trade-off gets settled by whoever is loudest instead of by whoever it is for. |
| 2 | What is true today that should not be? What does that person do now, and what does it cost them? | This is the problem, stated as an observation rather than as a wish. It is also the sentence the objectives are derived from. |
| 3 | What is the product, in one paragraph a stranger could repeat back? | If it cannot be repeated back, it cannot be agreed with — only nodded at. |
| 4 | What is this explicitly NOT? Name at least two. | **The uncomfortable one, and the one that pays for itself.** Everything is in scope until someone writes down what is not, and the argument you avoid today is the re-scope you pay for after the code exists. |

**Persist after every answer** to `.squad/records/brainstorms/{date}-session.md`, with
`status: in_progress`. Flip to `completed` at Step 4, or `aborted` if the person
stops early. An abandoned session leaves a record, never a half-written vision.

**Record what was discarded, and why.** The session record is the only place that
can answer *"did we consider X?"* a year from now with something other than
somebody's memory. The four documents carry the current answer; this carries the
reasoning that produced it.

### Step 4 — Write

Write `.squad/wiki/product/product-vision.md` with exactly these sections — the scorer
reads them by name:

```markdown
# Product vision — {scope}

## Who it is for
## The problem
## What it is
## What it is NOT
- ...
- ...
```

Then `CHANGELOG.md`, one line under `[Unreleased] § Added`.

**Do not emit a phase end here.** `brainstorm` is ONE declared phase in
`rules/cycle-phases.txt`, opened by `/brainstorm-vision` and closed by
`/brainstorm-pieces` with the gate's verdict. A step that closes it mid-cascade
reports the phase finished three times before it did, and a stream holding four
closes against one open tells nobody how long the session took or whether one is
running right now. Until phase 4 emits its end, this scope is correctly WIP.

The phase start from Step 2 stays open across phases 2 and 3 — that is what makes
an abandoned cascade visible as WIP rather than as a phase nobody began.

### Step 5 — Report and hand off

```
WRITTEN  .squad/wiki/product/product-vision.md   (phase 1 of 4 — brainstorm still open)
  for:       {the named user}
  problem:   {one line}
  non-goals: {n} recorded

Next step:  /brainstorm-objectives
```

## Anti-patterns

Cycle-level anti-patterns live in `cycle-brainstorm.md § Anti-patterns`. Specific
to this skill:

- **Accepting "developers" or "users" as the named user.** Both are categories, not
  someone whose situation you can picture, and neither settles a single trade-off.
- **Writing the problem as the absence of your solution.** "We have no dashboard" is
  not a problem; it is the solution, negated. The problem is what the person does
  instead, and what that costs.
- **Skipping question 4 because the session is going well.** It is going well
  *because* nothing has been ruled out yet.
- **Letting the agenda become the session.** It is context, not the agenda's own
  meeting. A halted item that needs a decision gets the decision; it does not get
  to redirect the product vision.
- **Writing objectives here.** They are phase 2 and they need the vision to exist
  first. An objective written before the problem is agreed measures the wrong thing
  precisely.

## Cross-references

- Cycle rule (source of truth): [`rules/cycle-brainstorm.md`](../../rules/cycle-brainstorm.md)
- Next phase: [`skills/brainstorm-objectives/SKILL.md`](../brainstorm-objectives/SKILL.md)
- The gate this cascade ends at: [`skills/brainstorm-pieces/SKILL.md`](../brainstorm-pieces/SKILL.md)
- The threshold and why the author may not sign: [`skills/_kit-rules/alignment-threshold.md`](../_kit-rules/alignment-threshold.md)
- What the system decides once alignment exists: [`rules/autonomy-envelope.md`](../../rules/autonomy-envelope.md)
- Where the two output kinds live: [`rules/records-location.md`](../../rules/records-location.md)
