---
type: concept
title: Merging is inside the autonomy envelope
description: The release PR is merged by the system when every gate passed, rather than waiting for a person. The decision, what it costs, and the three things that had to become true first.
tags: [decision, autonomy, release, adr]

generated:
  by: claude/opus-5
  at: 2026-09-01
status: stable
sources:
  - id: envelope
    resource: ../../rules/autonomy-envelope.md
  - id: release
    resource: ../../rules/cycle-release.md
  - id: brainstorm
    resource: ../../rules/cycle-brainstorm.md
---

# Merging is inside the autonomy envelope

**Status:** accepted · **Date:** 2026-09-01 · **Decided by:** Paulo Henrique (owner)
· **Drafted by:** the agent, from that decision · **Owner review:** not performed

**Read that last field before relying on the reasoning below.** The DECISION is the
owner's: auto-merge was chosen deliberately, with the cost stated in front of the
choice. The *argument* for it — the load-bearing clause, the three preconditions, the
rejected alternatives — is the agent's reconstruction of why that decision is sound,
and the owner has not confirmed that it is his reasoning.

The envelope says changing it is a human act, and it is the one document where an
agent validating its own draft would be the exact failure the kit refuses elsewhere.
So this field stays until a person edits the file, and a reader who finds an argument
here they disagree with should treat it as the agent's, not as settled.

## Context

`rules/autonomy-envelope.md` has five floors the system never crosses. The second
read:

> **A change is proposed, never merged.** The system opens the pull request and stops
> there. This is the one stop that costs nothing: the work is delivered, the PR is its
> record, and the queue continues to the next item. Merging is the single act that
> reaches shared history, and it stays outside the envelope.

The argument has one load-bearing clause — *"the one stop that costs nothing"* — and it
holds only while somebody is coming. It was written for a queue with a person watching,
where a pause is a pause. With nobody watching, the same pause is a stop: every item
that passes review parks at an open PR, and the queue drains into a pile of branches
nobody merges. The work is done, gated and unreachable.

This is the same discovery `skills/_kit-rules/alignment-threshold.md § Amended
2026-09-01` made one level up, and the shape is identical: a rule that said *a human
must do X* was really two claims wearing one sentence, and only one of them was the
argument.

## Decision

**The system merges the release PR when every gate has passed.** Floor 2 is replaced
by a floor about gates rather than about merging:

> **No change reaches shared history except through the gates.** Every merge is of a
> pull request whose full chain passed — review returned `READY_TO_MERGE`, code-quality
> did not return `FAIL_HARD`, and no BLOCKED report stands against the item. The system
> may merge such a PR. It may never merge one that has not passed, and it may never
> merge by moving a gate.

The branching topology is unchanged: work is born on `workspace`, promotes to `develop`
by PR, and reaches the trunk by a `develop → main` PR carrying a semver tag. Nothing
commits to the trunk directly, and `hooks/validate-command.py` still enforces that.

## What made this defensible, and what it is not

It rests on three things that had to become true first, and it would be wrong without
any of them.

1. **Somebody agreed what is being built.** `cycle-brainstorm` did not exist when the
   floor was written. Autonomy over merging is only defensible downstream of a product
   a person signed for, which is why that cycle is the one place a human is required
   and why `alignment_judge.py` may not sign it.

2. **The gates are mechanised, not narrated.** Review, code-quality, plan-confidence
   and the acceptance-criteria check are scripts with derived verdicts. Merging behind
   an asserted verdict would be merging behind nothing.

3. **The floor that actually mattered is intact.** Floor 3 — *no mechanical gate is
   switched off, and no threshold is moved to pass one* — is what stops this from
   becoming "the system merges what it wants". Under the old floor, disabling a gate
   still needed a human to merge afterwards; now that second look is gone, so floor 3
   carries the whole weight it used to share.

**This is not a claim that the merges will be right.** It is the trade named in the
envelope's own closing section: *"deciding by doctrine means some decisions will be
wrong in ways a person present would have caught."* What makes it recoverable is that
every merge is a PR with a diff, a verdict trail and a revertible commit.

## Alternatives rejected

**Keep the floor and let the queue park.** Rejected because it is not neutral. It
discards work already measured, planned, implemented, reviewed and gated — the
failure the envelope names in its own opening, applied at the last step instead of
the first.

**Auto-merge only `workspace → develop`, human on the release.** Genuinely close, and
the reason it lost is that it moves the pile rather than removing it: `develop`
accumulates merged work and no version ever cuts. It also splits one rule into two
that must be kept consistent by hand.

**Merge when gates pass AND a person has not objected within N hours.** Rejected as
a gate that cannot fail: nobody objects to what nobody reads, so it approves
everything while looking like review.

## Consequences

- `cycle-release`'s `PR_OPEN_AWAITING_APPROVAL` becomes the **exception** rather than
  the terminal state: emitted when a gate did not pass or branch protection requires a
  reviewer the system cannot be.
- **`ADVANCE`'s safety argument changed and had to be rewritten.**
  `rules/cycle-maintenance.md` justified mechanising ADVANCE with *"by the time it
  acts, every judgement it might have needed has been made by a person."* That is no
  longer true. ADVANCE is now safe for a different reason — it moves an item only on
  an explicit `cycle:phase:end` with `verdict=RELEASED`, which only exists downstream
  of the gates — and the section says so rather than keeping an argument that expired.
- **Branch protection outranks this decision.** Where the remote requires a human
  reviewer, the system cannot merge and must not try; it emits
  `PR_OPEN_AWAITING_APPROVAL` and moves on. The kit cannot configure another project's
  remote, and a project that wants the old behaviour gets it by turning that on — which
  is the honest place for the switch, since it is enforced rather than promised.
- Every merge the system performs is recorded as a phase event, per floor 5.

## Cross-references

- The envelope this amends: [`rules/autonomy-envelope.md`](../../rules/autonomy-envelope.md)
- The cycle it governs: [`rules/cycle-release.md`](../../rules/cycle-release.md)
- The human gate this rests on: [`rules/cycle-brainstorm.md`](../../rules/cycle-brainstorm.md)
- The parallel amendment one level up: [`skills/_kit-rules/alignment-threshold.md`](../../skills/_kit-rules/alignment-threshold.md)
- The bookkeeping whose argument this changed: [`rules/cycle-maintenance.md`](../../rules/cycle-maintenance.md)
