---
name: design
version: 0.1.0
requires: [brainstorm-pieces]
description: 'Draw the system before anyone writes a backlog item against it — five technical drawings that force the four decisions which cannot be retrofitted once code exists: what the central object''s lifecycle is, where untrusted code stops, what the real call order is including failures, and what survives a process death. Use this after /brainstorm-pieces and before /backlog-init, on any product where two people could read the TRD and picture different systems. Produces mermaid a machine can read plus an animated walkthrough a person can watch, and refuses to close while a declared PIECE-N has no place in the map.'
user-invocable: true
allowed-tools: Read Glob Grep Bash Write Edit AskUserQuestion
argument-hint: "[scope-name]"
---

# `/design` — draw it before anyone files work against it

Phase between BRAINSTORM and BACKLOG. Produces five drawings under
`.squad/wiki/design/` and emits the cycle's verdict.

## The gap it closes

`brainstorm-pieces` names PIECE-N as *"a responsibility with a boundary"*, and says
plainly what it does not do:

> *"A piece may map to a repo, several repos, or part of one. **The mapping is not
> decided here**; `/backlog-init` inventories repos from disk afterwards."*

So phase 4 declares responsibilities in prose, `backlog-init` inventories repos from
disk, and nothing joins them. Items get filed against a system nobody drew — and the
two decisions that cannot be retrofitted, **state ownership** and **trust boundary**,
are the two nobody is forced to make.

## Cycle contract

Companion to [`rules/cycle-design.md`](../../rules/cycle-design.md), which is the source
of truth for the gates and the verdicts. This file is what the agent executes.

## The five, and why four are mandatory

They are not a diagram set. They are four DECISIONS plus a summary, in the order that
removes ambiguity fastest.

| Id | File | The decision it forces |
|---|---|---|
| **D1** | `states.md` | What the central object's lifecycle IS. Which transitions exist, which are irreversible, who triggers each |
| **D2** | `trust.md` | Where third-party or user code runs, what crosses the boundary, with which credential |
| **D3** | `sequence.md` | The real call order **including failure paths** — which reveals the components prose invented |
| **D4** | `durability.md` | What survives a process death, a node restart, a platform deploy |
| **D5** | `system-map.md` | The components and their edges — **derived from D1–D4** |

**D5 is not an input.** A component map drawn FIRST is decoration: it looks like design
happened and forces no choice. Drawn last it is a summary, and the gate checks it
against the pieces rather than against taste.

## Why these four

Take a concrete brief — *"a PaaS like Vercel, on Docker, for long-running agents"* —
and each drawing earns its place by the error it prevents:

| Drawing | The question nobody asks without it | The error it prevents |
|---|---|---|
| D1 | Does an agent running for 3 days survive a deploy **of the platform**? Can it resume on another node? | Building everything stateless, then discovering in month three that "long-running" always meant checkpoints |
| D2 | Does the agent have unrestricted egress? How does it authenticate to our own API? Can one agent see another? | Retrofitted multi-tenancy — the most expensive thing to change and the only one that cannot be deferred |
| D3 | What happens when the build fails? When there is no capacity? | Finding out build and run need different isolation only when the first heavy build takes down a production agent |
| D4 | The container dies — what is lost? | *"The container died and we lost six hours of the agent's work"*, which for this product is the product failing |

## Process

### Step 1 — Interrogate before drawing

**A diagram of a misunderstanding is a confident misunderstanding** —
`/plan-alignment` puts it that way and the same holds here. Read `trd.md` and
`technical-pieces.md`, then ask the person, one question at a time, for each drawing
that has an unresolved decision in it. The questions above are the starting set; the
product supplies the rest.

Ask only what the documents cannot answer. A question whose answer is in the TRD is a
question that wastes the one session a person attends.

### Step 2 — Draw, one file per decision

Each file carries at least one ```mermaid block of the kind its slot expects — the gate
refuses a sequence diagram filed as the state machine, because a drawing in the wrong
slot answers a different question than the slot exists for.

Write the decision in prose beneath the diagram. **The diagram shows the shape; the
prose says what was decided and what was rejected.** A drawing with no rejected
alternative recorded is a drawing nobody can argue with later.

### Step 3 — Derive the map

`system-map.md` last, from D1–D4. Every `PIECE-N` in `technical-pieces.md` must appear.
A piece with no place in the map is a finding worth having **before** an item is filed
against it: either it has no place in the system as drawn, or the map is missing a
component.

### Step 4 — Render, when a person has to look at it

The mermaid IS the drawing. It is what the gate reads, what git versions, and what an
agent reads back later — so it is never regenerated from a rendered file. Rendering is
for the review session, where a person reads a picture faster than a fenced block.

```bash
/diagram-design:import-mermaid .squad/wiki/design/states.md --format=html
/diagram-design:import-mermaid .squad/wiki/design/system-map.md --format=html+png --audience=mixed
```

The `diagram-design` plugin accepts Markdown carrying fenced `mermaid` blocks, which is
exactly the shape of these files. Nothing has to be exported or converted first.

**It is optional, and the phase does not depend on it.** The plugin is a separate
install; `check_design_completeness.py` never asks for a rendered file, because a
drawing that exists only as a picture is a drawing no gate can check and no agent can
read.

**Not `build_walkthrough.py`.** That generator belongs to `/plan-alignment` and takes a
declarative YAML spec of one item's flows — a different input and a different artifact.
Pointing this step at it was wrong in the first version of this file and would have
failed on the first run.

### Step 5 — Score, then hand the checklist to a person

```bash
python3 "$ECO/skills/design/scripts/check_design_completeness.py" --project .
```

Then `/sign` the checklist. The machine counts drawings and cross-references pieces; it
cannot say a state machine has the RIGHT states, and does not pretend to — the verdict
stays `AWAITING_REVIEW` until a person signs.

### Step 6 — Emit and hand off

```bash
python3 "$([ -d .claude/scripts ] && echo .claude || echo .)/mechanisms/cycle/cycle_events.py" end \
    --cycle design --slug {scope} --verdict {DESIGN_AGREED|AWAITING_REVIEW|NEEDS_REVISION|INVALID}
```

Emit `AWAITING_REVIEW` too. Stopping at a human gate is a phase **ending**, not a phase
skipping: an item worked and left silent is indistinguishable from one nobody touched.

## Verdicts

| Verdict | Condition | Exit |
|---|---|---|
| `DESIGN_AGREED` | five drawings, every piece covered, signed by a person | 0 |
| `AWAITING_REVIEW` | complete and covered, nobody signed | 1 |
| `NEEDS_REVISION` | a drawing is a stub, in the wrong kind, or a piece has no place | 1 |
| `INVALID` | a mandatory drawing is absent entirely | 2 |

## What the gate does NOT check

- **Whether any drawing is CORRECT.** A state machine with the wrong states passes. A
  trust boundary in the wrong place passes.
- **Whether a covered piece is covered WELL,** or merely mentioned.
- **Whether the sequence matches what will be built.**

That judgement is what the signature is for, and why it must be a person's.

## Anti-patterns

- **Drawing D5 first.** It is the one that looks like progress and decides nothing.
- **A happy-path-only sequence.** The failure paths are where the components hide.
- **Padding a diagram to clear the stub check.** The floor is three lines because two
  labelled edges answer a question; a check people pad for is worse than no check.
- **Signing to unblock the backlog.** A signed design with an uncovered piece still
  returns `NEEDS_REVISION`, and correctly.
- **Using this for one item.** That is `/plan-alignment`, which draws one item's flows
  after DISCOVER has evidence. This draws the system, once, before any item exists.

## Related

- The pieces it draws: [`skills/brainstorm-pieces/SKILL.md`](../brainstorm-pieces/SKILL.md)
- What opens after it: [`skills/backlog-init/SKILL.md`](../backlog-init/SKILL.md)
- The per-item equivalent: [`skills/plan-alignment/SKILL.md`](../plan-alignment/SKILL.md)
- Signing the checklist: [`skills/sign/SKILL.md`](../sign/SKILL.md)
