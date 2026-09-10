---
name: brainstorm-objectives
version: 0.1.0
requires: [brainstorm-vision]
description: 'Turn the product vision into numbered objectives (OBJ-N) that can fail: each one carries a metric containing a number and a horizon by which it is judged. Use this after /brainstorm-vision, when someone asks what we are trying to achieve, or when work is being justified by "it would be better" rather than by a target. This is phase 2 of cycle-brainstorm, a cycle a human attends. An objective with no number is refused by gate G-B2 because nothing can ever report it as met.'
user-invocable: true
allowed-tools: Read Glob Grep Bash Write Edit AskUserQuestion
argument-hint: "[scope-name]"
---

# `/brainstorm-objectives` — What we are trying to achieve, in numbers

Phase 2 of four. Produces `.squad/wiki/product/objectives.md`: the `OBJ-N` ids that every
requirement cites and every backlog item traces to.

## Cycle contract

This skill is **phase 2** of [`cycle-brainstorm`](../../rules/cycle-brainstorm.md),
the source of truth for the chain, the gates and the verdicts.

**Read `cycle-brainstorm.md` before invoking.**

## Pre-conditions

- `.squad/wiki/product/product-vision.md` exists. An objective written before the problem
  is agreed measures the wrong thing precisely.
- The same person from phase 1 is present.

## Why a number, and why a date

**The metric.** `rules/cycle-backlog.md` refuses a `dod` bullet that cannot fail —
"improve performance" never closes — and an objective is that rule one level up. If
no measurement could ever show the objective unmet, it is a value rather than an
objective, and values belong in the vision where nothing traces to them.

**The horizon.** An objective with no date cannot be late, so it is never reviewed,
so it outlives the reason it was written. `rules/current-constraint.md` requires a
`review_on` for a declared constraint for exactly this reason: *"constraints move; an
undated one is unfalsifiable."*

Both are gate G-B2, and both are **floor caps** rather than scored criteria — a
rubric of seventeen dilutes any single one, so an objective with no number would
cost a point of thirty-four and still score 97%. The gate would have read as
enforced while passing precisely what it names.

## Process

### Step 1 — Read the vision back, out loud

Before asking anything, restate the problem and the named user from
`product-vision.md`. Objectives drift from the vision within one session if nobody
re-reads it, and the drift is invisible because both documents look fine alone.

### Step 2 — The session (3 questions per objective, ONE per turn)

Aim for **three to five objectives**. More than five and none of them is a
priority; fewer than two and the product has one idea, which the vision already
carried.

| # | Question | Feeds | Refused when |
|---|---|---|---|
| 1 | What must be true for the problem in the vision to be solved? | the title | It restates the vision, or it names a solution ("build a dashboard") rather than an outcome |
| 2 | How would we know? Give the number and how it is observed. | `metric` | No number. **G-B2 refuses it**; ask what would be different, and by how much |
| 3 | By when is this judged? | `horizon` | "Eventually". A date can be missed; a mood cannot |

For each, also capture `why` — one line saying what makes this worth doing now,
drawn from something observed rather than from a peer product. This is gate G5's
standard applied here: prior art is fine to know and never the justification.

Persist to `.squad/records/brainstorms/{date}-session.md` after every answer.

### Step 3 — Write

```markdown
# Objectives — {scope}

## OBJ-1 — {title}
metric: {number + how it is observed}
horizon: {date or quarter}
why: {what makes this worth doing now, observed}
```

Ids are **monotonic and never reused**, for the same reason `B-NNN` ids are: backlog
items cite them, and renumbering silently repoints every citation. A dropped
objective keeps its number and is marked withdrawn in the session record.

### Step 4 — Score early, and expect to fail here

```bash
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/brainstorm-pieces/scripts/score_product_alignment.py" --root .
```

It will report `INVALID` — `trd.md` and `technical-pieces.md` do not exist yet.
**Run it anyway and read the objectives criteria**: fixing a missing metric now
costs a sentence, and fixing it after the TRD cites the objective costs the TRD too.

Then emit the event and hand off:

```bash
python3 "$([ -d .claude/scripts ] && echo .claude || echo .)/mechanisms/cycle/cycle_events.py" end \
    --cycle brainstorm --slug {scope} --verdict OBJECTIVES_WRITTEN
```

## Anti-patterns

- **An objective that is a feature.** "Ship the trace explorer" is work, not an
  outcome. What would the explorer make true?
- **A metric that measures activity.** "12 items shipped per quarter" is throughput,
  and `README.md` names shipping into a stage that was never the limit as one of the
  five failures this kit exists to address.
- **A number nobody can observe today.** If measuring it requires instrumentation
  that does not exist, the instrumentation is a `B-NNN` and the objective says so.
- **Ten objectives.** A list where everything is an objective has no objectives.
- **Writing requirements here.** They are phase 3 and they need the ids these
  produce.

## Cross-references

- Cycle rule (source of truth): [`rules/cycle-brainstorm.md`](../../rules/cycle-brainstorm.md)
- Previous phase: [`skills/brainstorm-vision/SKILL.md`](../brainstorm-vision/SKILL.md)
- Next phase: [`skills/brainstorm-trd/SKILL.md`](../brainstorm-trd/SKILL.md)
- The falsifiable-criterion rule this applies upward: [`rules/cycle-backlog.md`](../../rules/cycle-backlog.md)
- Why a declaration carries a review date: [`rules/current-constraint.md`](../../rules/current-constraint.md)
