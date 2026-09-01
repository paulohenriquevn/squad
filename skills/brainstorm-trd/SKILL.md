---
name: brainstorm-trd
version: 0.1.0
requires: [brainstorm-objectives]
description: 'Write the technical requirements document: numbered REQ-N statements of what must be true, each citing the OBJ-N objective it serves and each carrying an acceptance criterion. Use this after /brainstorm-objectives, or when the team is arguing about implementation before agreeing what the system must do. This is phase 3 of cycle-brainstorm, a cycle a human attends. A requirement naming a library has skipped cycle-plan, where that decision has a gate; a requirement serving no objective is refused by gate G-B3.'
user-invocable: true
allowed-tools: Read Glob Grep Bash Write Edit AskUserQuestion
argument-hint: "[scope-name]"
---

# `/brainstorm-trd` — What the system must do

Phase 3 of four. Produces `wiki/product/trd.md`: `REQ-N` statements, each tied to
the objective that justifies it.

## Cycle contract

This skill is **phase 3** of [`cycle-brainstorm`](../../rules/cycle-brainstorm.md),
the source of truth for the chain, the gates and the verdicts.

**Read `cycle-brainstorm.md` before invoking.**

## Pre-conditions

- `wiki/product/objectives.md` exists and its objectives carry metrics. A
  requirement citing an objective with no number inherits the un-measurability.
- The same person from phases 1 and 2 is present.

## The line this phase must not cross

**What must be true — not how it is made true.** A requirement naming a framework,
a library or a schema has made a design decision, and design decisions belong to
`cycle-plan`, where they get an edge-case pass, a dependency audit with CVE
checking, and a confidence score. Made here, the same decision gets none of those
and arrives downstream carrying the authority of an agreed document.

The test is mechanical: **could two competent teams satisfy this requirement with
different technology?** If not, it is a design, and it belongs one cycle later.

| Requirement | Design wearing its clothes |
|---|---|
| A service added today has a usable baseline within 24h | Baselines are computed by a Postgres window function |
| Discovery reads the registry rather than a config file | Discovery polls Consul every 30s |
| An answer arrives before the person switches context | The API responds in under 200ms using Redis |

The third pair is the subtle one: the number is fine, the mechanism is not.

## Process

### Step 1 — Read the objectives back

State each `OBJ-N` and its metric before asking anything. A requirement written
without its objective in view serves whichever one it happens to resemble.

### Step 2 — The session (3 questions per requirement, ONE per turn)

Work objective by objective, not requirement by requirement. Finishing `OBJ-1`
before starting `OBJ-2` is what makes it visible when an objective has no
requirements at all — which means either the objective is unreachable or nobody
knows how to reach it, and both are worth finding here.

| # | Question | Feeds | Refused when |
|---|---|---|---|
| 1 | What must be true for `OBJ-N` to be met? | `statement` | It names a technology; ask what that technology would achieve |
| 2 | Which objective does this serve? | `serves` | It serves none. **G-B3 refuses it** — a requirement with no objective is a preference wearing the document's authority |
| 3 | How would someone check it holds? | `acceptance` | It restates the requirement. "The baseline works" is the statement again, not a check |

A requirement serving two objectives is fine and is written as `serves: OBJ-1, OBJ-2`.
A requirement serving *every* objective is usually a principle, not a requirement —
move it to the vision.

### Step 3 — Write

```markdown
# Technical requirements — {scope}

## REQ-1 — {title}
serves: OBJ-1
statement: {what must be true}
acceptance: {how someone checks it holds}
```

Every `OBJ-N` cited must exist in `objectives.md`. `score_product_alignment.py`
resolves each citation and a dangling one caps the cascade at `INVALID` — the same
rule the kit applies to a `file:line`, for the same reason: **no edit to the citing
document fixes a referent that does not exist.**

### Step 4 — Check the citations before moving on

```bash
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/brainstorm-pieces/scripts/score_product_alignment.py" --root . --json \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['dangling_citations'] or 'all citations resolve')"
```

Then emit the event:

```bash
python3 "$([ -d .claude/scripts ] && echo .claude || echo .)/scripts/cycle_events.py" end \
    --cycle brainstorm --slug {scope} --verdict TRD_WRITTEN
```

## Anti-patterns

- **Choosing the stack.** The most common way this phase fails, and the one that
  looks most like progress.
- **A requirement per feature idea.** The list grows until it is a backlog with no
  ids, and the actual backlog then has two sources of truth.
- **`serves:` filled in afterwards to pass the gate.** Reverse-justifying a
  requirement against whichever objective is nearest produces citations that resolve
  and mean nothing. If it genuinely serves none, the honest move is to drop it or to
  add the objective it implies — in phase 2, where objectives get a metric.
- **Acceptance criteria that only a person can judge.** "The interface feels fast"
  cannot be checked by anyone twice.
- **Naming pieces here.** They are phase 4 and they cite these ids.

## Cross-references

- Cycle rule (source of truth): [`rules/cycle-brainstorm.md`](../../rules/cycle-brainstorm.md)
- Previous phase: [`skills/brainstorm-objectives/SKILL.md`](../brainstorm-objectives/SKILL.md)
- Next phase: [`skills/brainstorm-pieces/SKILL.md`](../brainstorm-pieces/SKILL.md)
- Where design decisions get their gates instead: [`rules/cycle-plan.md`](../../rules/cycle-plan.md)
