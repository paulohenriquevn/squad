---
name: as-is-to-be
version: 0.1.0
requires: []
description: Render the open backlog as current state versus future state — what this system is today, and what it becomes if the open items are done. Use when someone asks what the backlog adds up to, before committing to a quarter's work, or when a stakeholder needs the shape of the change rather than a list of tickets. Adds no field and asks no question — an item's `evidence` already IS the as-is and its `dod` already IS the to-be. States what it cannot tell you — coverage, coherence, and feasibility.
user-invocable: true
allowed-tools: Read Glob Grep Bash
argument-hint: "[project-path] [--status triaged|any] [--json]"
---

# `/as-is-to-be` — what we have, and what we will have

A backlog is a list of tickets. Nobody can hold twenty-three of them in their head and
answer *"so what will this system be when they are done?"* — which is the question
anyone funding the work actually has.

## It adds nothing to the schema

The two halves were already in every item, and no page had put them side by side:

```
evidence:  grep -ci 'cnpg' infra/helmfile/cell.helmfile.yaml.gotmpl  ->  0     ← AS-IS
dod:       one CNPG instance per cell, declared in the cell composition        ← TO-BE
           the operator is Ready before any `Cluster` is admitted
```

The first is a **measurement**, not an opinion — `cycle-discover` refuses an item
whose evidence is a hunch. The second is **falsifiable** — gate G4 refuses a bullet that
cannot fail. That is a stronger gap analysis than the technique usually gets, and it
came for free.

This is the shape business analysis has used for decades — BABOK §6.1 analyses the
current state, §6.2 defines the future state, §6.4 does the gap between them. The only
novelty here is that both columns are already written down and already gated.

## Use it

```bash
ECO="$([ -d .claude/skills ] && echo .claude || echo .)"
python3 "$ECO/skills/as-is-to-be/scripts/build_gap_analysis.py" .
```

`--status any` projects the whole registry rather than only `triaged`; `--json` for a
machine; `--stdout` to read it without writing a file.

## What it renders

Grouped by domain, so each module's future state reads as one story:

| Section | Answers |
|---|---|
| **Today** | what was measured, and whether the file it cites still exists |
| **Why it matters now** | the local trigger — gate G5 already refused prior-art envy |
| **After** | the `dod` bullets: what closes it |
| **Cannot start** | the item it waits on, when there is one |

## Three things it will not claim

This page is persuasive by construction — a list of promises reads like a plan. The
failure mode is not being wrong about an item; it is **being read as complete**. So it
says all three out loud, in the header, above the content:

| It does not claim | Because |
|---|---|
| the current state is **complete** | the as-is is the union of what these items happened to measure. A part of the system nobody filed an item against is absent from this page, and is not thereby fine |
| the future state is **coherent** | two items may promise contradictory things and nothing here can tell. Reconciling them is design work, and `cycle-design` is the phase with the drawings |
| the work is **feasible** | an item is a hypothesis until DISCOVER measures it. Evidence for the problem is not proof the solution works |

And when objectives are declared, an objective **no item serves** is named on this page
too: the future state below does not reach it, however many items are done.

## Where it sits

Read it before `/backlog-approve`, not instead of it. This page answers *what will we
have*; the brief answers *is this the work I want*. They are different questions and the
second one is the one that writes a status.

## Scripts

| Script | Runs it | What it does |
|---|---|---|
| `build_gap_analysis.py` | `/as-is-to-be` | projects the registry into current state vs future state |

It reuses `backlog-approve`'s parser and evidence verifier rather than carrying its own.
A second reader of the same registry is how two pages start disagreeing about what it
says.
