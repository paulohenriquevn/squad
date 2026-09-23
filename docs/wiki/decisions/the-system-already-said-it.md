---
type: concept
title: The system already said it
description: Three investigations in one day where the answer was already written down and the investigator looked somewhere else. Why this is not "measure the premise", and the one habit that separates them.
tags: [decision, investigation, honesty, method, adr]

generated:
  by: claude/opus-5
  at: 2026-09-23
status: stable
sources:
  - id: exemptions
    resource: ../../rules/write-exemptions.txt
  - id: steps
    resource: a-step-that-cannot-fail-loudly-did-not-run.md
  - id: refs
    resource: a-reference-is-checked-in-one-direction.md
---

# The system already said it

## Three measurements, two sessions, one day

Unlike the other classes recorded here, the subject of this one is not a mechanism. It is
the person — or agent — looking at it.

**1. A lock reported as an escape.** A consumer's post-install validation reported
`escaped: .BACKLOG.md.lock`. A test was written and an inheritance rule implemented so
that a sidecar lock would inherit its target's exemption. `rules/write-exemptions.txt`
already carried `.*.lock | tool | …` with its reason spelled out; the consumer's copy of
that file simply predated it. The fix was reverted whole.

**2. A workflow's announcement filtered out of its own log.** Two pull requests were
opened by hand and the behaviour reported as a defect. The workflow documented it in
fifteen lines and announced it with a `::notice` that appeared in both runs. The log had
been filtered by `error|failed|pull.request`; the announcement lived under `notice`.

**3. Four required formats discovered one gate refusal at a time.** A plan was written to
the shape of a previous plan, and each format the checkers demanded was learned by being
refused. The template documented all four. It had not been opened.

## Why this is not "measure the premise"

Measuring the premise means *verify the claim before building on it*. That is a good rule
and it is not this one. In all three cases there was no claim to verify — **the system had
already written the answer down**, in a file whose job is to hold exactly that answer.

The distinction matters because the remedies are different. Verifying a premise means
constructing a measurement. Reading what the system says means opening the file that owns
the question — which is cheaper, earlier, and the thing that was skipped.

## The shape

Each of the three has an authority that was not consulted:

    the escaped lock         rules/write-exemptions.txt, which decides what may sit outside
    the hand-opened PRs      the workflow, which decides what it opens and says so
    the refused formats      the template, which IS the contract the checkers enforce

And in each, the reader went somewhere adjacent instead: to the symptom, to a filtered
view of the output, to a neighbouring example of the artifact.

## Read the structure before the text

The sharpest version of the remedy came from the second case, and it generalises. A log
filtered by severity keywords answers *what went wrong*; it cannot answer *which branch
ran*. `gh run view --json jobs`, with the per-step conclusions, does — and a `skipped`
beside a `success` explains more than any grep over the text.

The same move applies to the other two. `grep` over a rules file answers *is this word
here*; opening the file answers *what does this file decide*. The structure — what kind of
artifact is this, and what question does it own — is what points at the authority. The
text is what you read once you are in front of it.

## The cheap question

Before investigating a surprising behaviour:

**Which file's job is it to answer this? Have I opened it?**

If the answer to the second is no, the investigation has not started. Everything built
before it is built on the symptom.

## What this does not say

It does not say the three findings were worthless. Each cost real time and each pointed at
something: a consumer's stale configuration, a procedure nobody had read, a plan written
from the wrong model. What it says is that the cost was avoidable, and by a step that takes
seconds rather than a measurement that takes minutes.
