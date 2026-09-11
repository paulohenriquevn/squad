---
type: SOP
title: File an issue somebody who was not there can act on
description: Check the tracker, deduplicate, write the body in the order a fixer reads it, score it against what developers measurably use, and refuse anything carrying a secret.
tags: [procedure, tracker, defects]

# The OPERATOR's procedure. `SKILL.md` is the contract the agent executes; this is what
# a person needs to file a report and know when it is good enough.
# Derived from the documents in `sources` — no step here was invented.
generated:
  by: claude/opus-5
  at: 2026-09-11
status: stable
sources:
  - id: contract
    resource: ./SKILL.md
  - id: conventions
    resource: ../../rules/contribution-conventions.md

sop: score-and-file-an-issue
version: 1.0.0
owner: whoever found the defect
standard: rules/contribution-conventions.md
last_reviewed: 2026-09-11
---

# File an issue somebody who was not there can act on

## Purpose

Turn a finding into a report the fixer can act on without coming back to ask.

## Prerequisites

- A repro, or an honest statement that it is intermittent.
- Evidence — the output, not a description of it.
- Nothing else. Filing is the default; a finding held back is a finding nobody tracks.

## Steps

1. **Find the right tracker** — `gh repo view --json nameWithOwner,hasIssuesEnabled`.
   Where the team FIXES it, not where you were running.
2. **Search first** — `gh issue list --search "<distinctive term>" --state all`.
   A match means comment there, saying what is new. Duplication is the leading cause of
   a report nobody can reproduce (~29%).
3. **Write the body to a file**, in the order of the template: severity, build, expected
   vs actual, repro, evidence, probable cause, dedup.
4. **Score it** — `python3 skills/issue-confidence/scripts/score_issue.py draft.md`.
   `READY` files. `THIN` names what is missing, heaviest first. `REFUSED` means a secret
   was found; rewrite, do not file.
5. **File it** — `gh issue create --title "<area>: <what is wrong>" --body-file - < draft.md`.
6. **Label the state and keep it open** until the fix is installable, then close naming
   the version.

## How much is enough

The floor is 60% of weighted usefulness, and the weights are the FSE 2008 percentages —
steps to reproduce 83, stack traces 57, observed 33, expected 22, version 12, dedup 10,
environment 4.

**It cannot be reached by padding.** The repro alone is 38% of the total; environment
and severity together are 4%. An issue that is all metadata and no repro is the case the
same study ranks as causing the most delay — incomplete information, 74%.

## Escalation

- `hasIssuesEnabled` is false → the tracker is elsewhere. → `CONTRIBUTING.md`, or ask.
  Do not file in the wrong place.
- `gh auth status` fails → you cannot file. → write the draft to a file and hand it over
  with a note saying it is unfiled. An unfiled finding in a report is still better than a
  finding that is nowhere, but say plainly that it was not filed.
- The finding is intermittent → file it, mark `[NEEDS-REPRO]`, and say how many attempts
  out of how many reproduced it. → nobody; this is the phase working.
- You are unsure whether it is the product or the environment → say so in Probable
  cause. Honest uncertainty beats a confident wrong diagnosis, and the fixer can tell
  the difference.

## Competencies

- Reading severity as what it is: 0% useful to the fixer, and the field triage reads.
- Telling "I could not reproduce it" from "it is not reproducible" — the first is about
  you, the second is a claim about the defect.
- Pasting the failure rather than the log. A trace without context is, in the study's
  words, "often too large to be useful".

## Cadence

On every objective finding, immediately. There is no batch: a finding held to be filed
later is a finding filed never.
