---
type: Architecture Decision
title: The wiki holds knowledge; the knowledge-base holds the trail
description: Durable knowledge moves to an OKF bundle, and dated execution records stay where they are, because they are different kinds of artifact.
tags: [decision, okf, knowledge-base, layout]

generated:
  by: claude/opus-5
  at: 2026-08-27
status: stable
sources:
  - id: okf-spec
    resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
    author: "process:google-cloud"
  - id: kb-location
    resource: ../../rules/knowledge-base-location.md
---

# Decision

Durable knowledge — procedures, decisions, absorbed external references,
measured opportunities — lives in `wiki/`, an OKF v0.2 bundle.

Dated execution records — audits, reviews, implementations, releases,
acceptance runs, SOP run records, progress checkpoints — stay in
`knowledge-base/`, unchanged.

# Context

`knowledge-base/` had grown to 15 directories under one convention, holding two
kinds of artifact that were never the same thing:

| Kind | Example | Property |
| --- | --- | --- |
| Knowledge | a procedure, an ADR | evolves, has an owner, goes stale |
| Record | an audit dated 2026-08-26 | immutable, evidence, never edited |

OKF is a format for *"the context an agent needs"*.[^okf-spec] Its fields say so:
`status`, `stale_after`, `verified`. None of those means anything for a record of
one execution on one day — a run record does not become `deprecated`, and
re-verifying it would falsify what it is.

# Consequences

- **Two roots, resolved with a fallback.** Readers try `wiki/` first and
  `knowledge-base/` second; writers only ever write the new one. No installed
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
