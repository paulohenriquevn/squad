---
type: Architecture Decision
title: The wiki holds knowledge; the records holds the trail
description: Durable knowledge moves to an OKF bundle, and dated execution records stay where they are, because they are different kinds of artifact.
tags: [decision, okf, records, layout]

generated:
  by: claude/opus-5
  at: 2026-08-27
status: stable
sources:
  - id: okf-spec
    resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
    author: "process:google-cloud"
  - id: kb-location
    resource: ../../rules/records-location.md
---

# Decision

Durable knowledge — procedures, decisions, absorbed external references,
measured opportunities — lives in `wiki/`, an OKF v0.2 bundle.

Dated execution records — audits, reviews, implementations, releases,
acceptance runs, SOP run records, progress checkpoints — stay in
`records/`, unchanged.

# Context

`records/` had grown to 15 directories under one convention, holding two
kinds of artifact that were never the same thing:

| Kind | Example | Property |
| --- | --- | --- |
| Knowledge | a procedure, an ADR | evolves, has an owner, goes stale |
| Record | an audit dated 2026-08-26 | immutable, evidence, never edited |

OKF is a format for *"the context an agent needs"*.[^okf-spec] Its fields say so:
`status`, `stale_after`, `verified`. None of those means anything for a record of
one execution on one day — a run record does not become `deprecated`, and
re-verifying it would falsify what it is.

# The rename that followed

Splitting the two left `knowledge-base/` naming exactly what is **not**
knowledge, which is worse than a vague name: it is an inverted one. Renamed to
`records/`, and two things came out of it at the same time because no single
name was honest about all four natures it held:

| Was | Is | Why it did not belong |
| --- | --- | --- |
| `knowledge-base/tools/` | `study-material/` | third-party docs, read-only, never produced by a run |
| `knowledge-base/progress/` | `session-state/` | ephemeral checkpoint, not evidence of anything |
| `knowledge-base/*` (the rest) | `records/` | dated, immutable, produced by a phase — the actual trail |

Readers fall back to `knowledge-base/` and writers do not, for the same reason
the bundle fallback exists: 42 consumers have the old directory on disk and this
kit cannot run a migration inside another project's repository.

# Consequences

- **Two roots, resolved with a fallback.** Readers try `wiki/` first and
  `records/` second; writers only ever write the new one. No installed
  consumer breaks, and each migrates as it runs.
- **The trust tier becomes computable.** A concept with no `verified` is
  unverified — written by an agent, checked by nobody. That distinction was
  already the kit's central discipline, mechanised gate by gate; OKF gives it a
  field and a validator instead of a convention.
- **`stale_after` replaces a bespoke pair.** The SOP schema had computed
  staleness from `last_reviewed + review_interval_days`. Both keys stay for the
  existing gate, and OKF's absolute date is now the portable form.
- **The connectivity gate is asleep until the second concept.** The validator
  only reports orphans when a bundle holds more than one concept, so a
  single-concept bundle passes `--strict` trivially. Adding this file is what
  woke it up.

# What was NOT decided

Whether `rules/` becomes part of the bundle. It is the largest body of
agent-facing knowledge in the kit — 24 normative documents — and by OKF's own
description it would qualify. It also carries `## Hard gates` sections that
`check_gate_mechanisms.py` parses, and moving it is a separate change with its
own blast radius.

See [the porting procedure](/sops/port-fix-between-kits.md) for how a change
like that would reach the sibling kit.

[^okf-spec]: OKF v0.2, published by Google Cloud.

## An instance of the split

[The judgement-gate finding](/references/judgement-gates-are-insurance.md) is the durable half of the 2026-08-28 baseline
experiment: the finding lives here because it stays true, and the run that produced
it — scenarios, verbatim outputs, the model tiers used — stays in
`records/experiments/`, because one execution on one day is not a concept that
evolves.
