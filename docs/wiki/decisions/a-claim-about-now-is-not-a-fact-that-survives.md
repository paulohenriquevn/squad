---
type: concept
title: A claim about now is not a fact that survives
description: Three defects measured in one day, in three different systems, with one shape — run-scoped state and durable state kept in the same field. What the shape looks like, why each instance read as correct, and the two questions that separate them.
tags: [decision, state, gates, honesty, adr]

generated:
  by: claude/opus-5
  at: 2026-09-22
status: stable
sources:
  - id: board
    resource: ../../skills/backlog-review/scripts/board_state.py
  - id: coverage
    resource: ../../mechanisms/gates/check_auditor_coverage.py
  - id: testing
    resource: ../../rules/testing.md
---

# A claim about now is not a fact that survives

## Three measurements, one shape

Three defects turned up on 2026-09-22, in three systems maintained by three different
sessions. None was found by looking for this pattern; the pattern is what was left after
all three were fixed.

**1. A board headlined `WORKING B-184`** over an `implement` phase that had opened 20
hours and 26 events earlier and never closed. The same page, in its own notices panel,
said that start was *"not counted as work in flight"*. One event, two contradictory
claims, and the wrong one in the headline.

**2. `licence_finalize` exited 0 before the write that sets `status: blocked`.** A hard
block therefore left `status: running` on disk, and a resumed loop read a run that was
never blocked.

**3. `check_auditor_coverage` nearly collapsed `state` into the plugin's verdict.** The
first draft overwrote `covered` with `verdict_not_exposed` when a plugin exposed no
decidable verdict. Sixteen of seventeen plugins are in that state and every one of them
covers its audit.

## What they share

In each case a field that answers **"what is true now"** was asked to also carry **"what
happened"** — or the reverse.

    the event stream says a phase opened     is a fact about the STREAM
    an item is being worked on               is a claim about the WORK
    the message said blocked                 is a fact about the RUN
    the status file says running             is the state that SURVIVES it
    the audit ran and is well-formed         is a fact about the RUN
    the plugin exposes a decidable verdict   is a different fact about the same run

Each pair looks like one question until the two answers disagree. They only disagree
when something goes wrong — a lane dies, a guard fires, a plugin has not shipped a
feature — so the collapse is invisible in every healthy case and visible exactly when
somebody needs the truth.

## Why each one read as correct

None of the three was careless. Each had an argument:

- the start really had been recorded, so reporting it as running felt like reading the
  data rather than interpreting it;
- the block really had been decided, and the message really did say so;
- a plugin with no verdict really does give the gate less to work with.

The argument is the failure mode. A collapse of two facts survives review because the
reviewer checks whether the field is *right*, and it is — for the case in front of them.

## The two questions

Before a field is written, ask which of these it answers:

1. **Does this outlive the run that produced it?** A status on disk, a verdict, a
   checkbox, a registry line — these are read by someone who was not there.
2. **Is this a claim about the present?** Running, working, in flight, blocked — these
   are true only while they are true, and something has to make them false again.

A field that answers both is two fields. When one of the pair is missing, the honest
value is not the other one — it is the absence, named. `verdict_not_exposed` is not
`covered`; an abandoned start is not `running`; a printed refusal is not `blocked`.

## What this does not say

It does not say every field needs a sibling. Most answer one question and the answer is
obvious. The rule applies where a reader could act on the field — a gate, a headline, a
resumed loop — because that is where acting on the wrong half has a cost.

And it is not a new principle: `rules/records-location.md` already separates the durable
bundle from the dated trail, and `check_auditor_coverage` already split `not_installed`
from `no_report` for the same reason. What is new is that the shape now has three
measurements behind it instead of one instance and an intuition.
