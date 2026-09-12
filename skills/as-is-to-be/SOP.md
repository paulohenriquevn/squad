---
type: SOP
title: See what the open backlog adds up to
description: Project the registry into current state versus future state — what this system is today, and what it becomes if the open items are done — and read the three limits before reading the content.
tags: [procedure, cycle-backlog, gap-analysis]

# The OPERATOR's procedure. `SKILL.md` is the contract the agent executes; this is what
# a person needs to read the page and know what it does not say.
# Derived from the documents in `sources` — no step here was invented.
generated:
  by: claude/opus-5
  at: 2026-09-12
status: stable
sources:
  - id: contract
    resource: ./SKILL.md
  - id: cycle
    resource: ../../rules/cycle-backlog.md
  - id: decision
    resource: ../backlog-approve/SKILL.md

sop: see-what-the-backlog-adds-up-to
version: 1.0.0
owner: whoever has to explain what the next quarter buys
standard: rules/cycle-backlog.md
last_reviewed: 2026-09-12
---

# See what the open backlog adds up to

## Purpose

Answer the question a list of tickets cannot: what will this system be when these items
are done. Read-only — it writes one document and never touches the registry.

## Prerequisites

- `BACKLOG.md` exists with items at `triaged`.
- Nothing else. Objectives and evidence improve the page; their absence is reported
  rather than hidden.

## Steps

1. **Render.** `build_gap_analysis.py <project>`. Add `--status any` to include work
   already shipped or killed, which is how you show what changed rather than what will.
2. **Read the header first.** Three counts decide how much weight the rest carries:
   verified, unverifiable, and broken-pointer current states.
3. **Read by domain.** Each section is one module's story: what it is, why it matters,
   what closes it.
4. **Check the blocked items.** A future state built on work that cannot begin is a
   different promise from one that can.
5. **Take it to `/backlog-approve`.** This page says what you would get; the brief is
   where you decide whether you want it.

## Decisions

| What you see | Means | Obliges |
|---|---|---|
| most current states `measured` | the as-is rests on files that exist | read on |
| several `pointer does not resolve` | the tree moved under the registry | re-measure before committing; you are reading descriptions of a codebase that changed |
| many `not verifiable` | evidence is prose rather than pointers | ask for pointers before treating the as-is as fact |
| an objective with no item | the future state does not reach a stated goal | file the missing item before approving anything |
| `no closing criterion` on an item | nothing says when it is done | send it back; it cannot close |

## Escalation

**The page reads complete and you know something is missing.** It is not complete, by
construction — the current state is only what these items measured. The page says so;
believe the page over the impression. File the missing item.

**Two items promise opposite things.** Nothing here detects that. Reconciling them is
design work — take it to `/design`, which has the drawings that force the decision.

**A stakeholder wants this as a commitment.** It is not one. Every item is a hypothesis
until DISCOVER measures it, and `approved` is the only status that records a decision.
Point at `/backlog-approve` rather than letting this page stand in for it.

## Competencies

- Reading a `dod` bullet and judging whether it could fail.
- Distinguishing "nobody measured this" from "this is fine" — the page marks the first
  and never asserts the second.
