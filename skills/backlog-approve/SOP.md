---
type: SOP
title: Decide which backlog items are the work you want done
description: Render the registry as one readable page, check what each item claims against the files it cites and what the objectives leave uncovered, tick what you commit to, sign, and record the decision as `approved`.
tags: [procedure, cycle-backlog, sign-off, governance]

# The OPERATOR's procedure. `SKILL.md` is the contract the agent executes; this is
# what a person needs in order to decide, and to know what their signature claims.
# Derived from the documents in `sources` — no step here was invented.
generated:
  by: claude/opus-5
  at: 2026-09-11
status: stable
sources:
  - id: contract
    resource: ./SKILL.md
  - id: cycle
    resource: ../../rules/cycle-backlog.md
  - id: signature
    resource: ../sign/SKILL.md

sop: approve-the-backlog
version: 1.0.0
owner: whoever is accountable for what the team builds next
standard: rules/cycle-backlog.md
last_reviewed: 2026-09-11
---

# Decide which backlog items are the work you want done

## Purpose

Close the gap between work that was written down and work somebody chose. Structure is
checked elsewhere; this is the only step that asks whether the right work was written
down at all.

## Prerequisites

- `BACKLOG.md` exists and holds items at `triaged`.
- You can spare the reading time. Roughly 20 minutes for 28 items — signing without that
  produces the formality this procedure exists to replace.
- Optional but load-bearing: `.squad/wiki/product/objectives.md`. Without it the brief
  cannot tell you what the backlog leaves **uncovered**, and says so rather than
  implying the coverage is fine.

## Steps

1. **Render.** `build_approval_brief.py <project>` writes one page under the records
   root and prints where. It reads the registry and writes nothing to it.
2. **Read the coverage section first**, before the items. It is the only part that can
   raise "something I want is missing" — an objective with no item is work you asked for
   that nobody wrote down, and ticking every box below would still leave it undone.
3. **Read the evidence column.** Anything marked *does not check out* cites a file that
   is not on disk. That does not make the item wrong — the file may have moved — but the
   reason you are being asked to trust cannot currently be followed.
4. **Tick what you want done.** Leave the rest. An unticked item stays exactly where it
   was; nothing is rejected and nothing is killed.
5. **Sign.** `/sign <brief>`. The signature covers what you ticked.
6. **Record.** `apply_approval.py <project> <brief>` moves the ticked items to
   `approved`. Add `--dry-run` first to see the moves before they happen.

## Decisions

| Outcome | Means | Obliges |
|---|---|---|
| `moved N item(s) to approved` | the decision is recorded and those items may now be planned | nothing — the cycle can proceed |
| `REFUSED: the brief is not signed` | ticks exist, a signature does not | sign, or discard the ticks |
| `REFUSED: signed and nothing is ticked` | almost certainly a slip | tick, or accept the backlog unchanged |
| `refused by backlog_status.py` | the item was not at a status this move is legal from | read the reason; the item may already be past this gate |
| `NOT MEASURED` on coverage | no objectives document | run `/brainstorm-objectives`, or accept that coverage is unanswerable here |
| `NOT MEASURED` on the brief | no brief, no registry, or no writer found | fix the path — nothing was examined |

## Escalation

**An objective with no item, and you did not know it.** Stop approving. The set in front
of you is not the set you need, and committing to it spends attention on the wrong
question. File the missing item first.

**An item you do not recognise at all.** It was written by an agent from a measurement,
and `source: human` records only that someone ran the intake command. Ask for the
evidence pointer before ticking; if it does not check out, leave it unticked and say so.

**Evidence that does not check out on more than a few items.** That is a signal about
the registry rather than about any item — the tree moved under it. Leave them and
re-measure before approving anything, or you are approving descriptions of a codebase
that no longer exists.

**You are the person who wrote the items.** `/sign` will require
`--despite-authorship` and will record it in the document. That is not a blocker, and it
is deliberately visible to the next reader: an author approving their own backlog is a
weaker signal than a second reader doing it, and the document says which one happened.

## Competencies

- Reading a Definition of Done and judging whether it could fail.
- Telling a measurement from an inference — and knowing this registry does not record
  which is which.
- Willingness to leave boxes unticked. The procedure only works if not approving is a
  real option.
