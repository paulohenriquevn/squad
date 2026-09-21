---
type: Architecture Decision
title: The CLI navigates; the mechanisms compute
description: A single entry point exists to make the kit findable, not to run it. It resolves names, scopes test runs to what changed, and states what it did not check — and it never becomes a second list of gates.
tags: [decision, cli, discoverability, adr, tooling]

generated:
  by: claude/opus-5
  at: 2026-09-09
status: stable
sources:
  - id: ownership
    resource: ../../rules/README.md
  - id: families
    resource: ../../mechanisms/README.md
  - id: map
    resource: ../../rules/squad-map.md
  - id: reachability
    resource: ../../tests/test_every_gate_is_reachable.py
  - id: aggregator
    resource: ../../mechanisms/gates/verify_ecosystem.py
  - id: ci
    resource: ../../.github/workflows/ci.yml
---

# The CLI navigates; the mechanisms compute

**Status:** accepted · **Date:** 2026-09-09 · **Requested by:** Paulo Henrique (owner)
· **Drafted by:** the agent · **Owner review:** not performed

The owner asked for a CLI and accepted the shape recommended below. Everything after
`## Context` — the friction measurements, the boundary that keeps this out of
`mechanisms/`, the rejected alternatives — is the agent's argument for why that shape
is the right one, and has not been confirmed as the owner's reasoning. A reader who
disagrees with an argument here should treat it as the agent's, not as settled.

The measurements are not opinion. They were taken from one working session on
2026-09-09 and are reproducible from that session's git history.

## Context

### What already works, and must not be rebuilt

The first proposal for this CLI was "every check, in one place". That part of the
problem is already solved, and solved better than a new entry point would solve it:

- [`verify_ecosystem.py`](../../../mechanisms/gates/verify_ecosystem.py) aggregates. Of
  the 23 gates on disk, the CI invokes 10 directly and roughly 11 more are reached
  through it.
- [`test_every_gate_is_reachable.py`](../../../tests/test_every_gate_is_reachable.py)
  proves no gate is orphaned — and it is not naive about it. It strips Python
  comments, triple-quoted literals and shell comments before matching, because nine
  prose mentions once looked exactly like call sites and hid an unrun gate for ten
  hours.

A CLI holding **its own list of gates** would therefore be a second source of truth
for a question that already has one, and the two would diverge on the next gate
added. That is the defect class this repository exists to catch, arriving through the
tool built to prevent it.

### What is actually missing

The kit has no execution problem. It has a **navigation** problem, and the cause is
structural rather than accidental.

[`rules/README.md`](../../../rules/README.md) states that the question which places a
file is *not who reads it — it is who owns it*. That rule is correct for the disk: it
is what lets an installer preserve a consumer's configuration and overwrite the kit's
contracts. It is also what makes the tree unsearchable by task, because ownership and
task are different axes.

**The CLI is the projection of an ownership-organised tree onto a task-organised
surface.** That is its whole job, and it is a job nothing else in the kit does.

### The friction, measured

From one session, working inside this repository:

| What happened | Cost |
|---|---|
| Guessed the wrong directory twice (`select_backlog_item`, `backlog_status`) | ~4 wasted calls |
| Guessed the wrong argument form twice; the usage text arrives only after `exit 2` | ~2 wasted calls |
| Diagnosing a red CI down to the billing annotation | ~8 calls |
| Cross-referencing issue to commit to test to label | 3 hand-written shell loops |
| **Read 80 of 240 lines of `ci.yml`** and reported jobs as missing that were present | **stated something false** |
| **Did not know the root suite excludes `skills/*/tests`** | **almost reported 1894 passing as full coverage** |
| **Truncated a run with `tail -25`** and published a count from the truncation | **published an unmeasured number** |

The last three are the ones that matter. They cost no time at all; they produced false
statements. A CLI that saves minutes is a convenience. A CLI that makes those three
impossible is a correctness measure, and that is the justification for building one.

## Decision

A single entry point, `sq`, is added at the repository root. It resolves names, scopes
work to what changed, and reports what it did **not** examine. It does not compute
verdicts and it does not run the cycle.

### The load-bearing property

**Every command states what it did not check.** This is first, not last. The kit's
governing sentence is that an inability to measure must never become a passing
measurement — and the tooling used to measure did not have that property. `sq test`
prints

```
1894 passed (root)  ·  3402 across 23 slices NOT RUN — sq test --slices
```

rather than `1894 passed`. The session that produced this ADR made that exact mistake,
and no amount of care would have prevented it, because nothing on screen said the
other half existed.

### The commands, in the order the measured friction justifies them

| Command | Answers | Friction it closes |
|---|---|---|
| `sq test [--touched] [--slices]` | did the code survive, and what was not run | the false-coverage report, and the 6–9 minute loop |
| `sq check` | do the contracts hold — a façade over `verify_ecosystem`, plus what was skipped and why | the hand-written gate loop |
| `sq where` / `sq run <name>` | where does this live and how is it invoked | the wrong-directory and wrong-argument guesses |
| `sq ci` | why is the pipeline red — last run **plus its annotations** | the eight-call billing diagnosis |

`--touched` maps a diff to the slices it affects. The mapping is mechanical and the
information is already on disk; it converts a nine-minute feedback loop into seconds,
which changes how work is done rather than only how long it takes.

`sq explain <token>` is accepted in principle and deferred: it must **project** the
existing machine-readable registers (`rules/verdict-bands.txt`,
`rules/cycle-phases.txt`, `rules/blocking-verdicts.txt`) and never restate them. An
`explain` carrying prose of its own would rot, and
[`check_prose_tests.py`](../../../mechanisms/gates/check_prose_tests.py) exists because
this repository has already paid for that lesson.

### The CI calls the CLI

`ci.yml` becomes `run: sq check --all`. There is one definition of "verified", and the
CLI is a façade over it rather than a parallel copy of it. A CLI the CI does not use is
a CLI that diverges from the CI.

### Where it lives, and why not in `mechanisms/`

[`mechanisms/README.md`](../../../mechanisms/README.md) organises five families by the
**work they do** — gates, cycle, fleet, distribution, conventions. A sixth family named
`cli/` would be organised by **form**, which is precisely the error the `scripts/` →
`mechanisms/` rename corrected: that name described the shape of the files and said
nothing about the six different jobs they did.

So: `sq` is a thin router at the repository root, and it computes nothing. The only new
logic it needs — the file-to-slice map behind `--touched` — belongs in
`mechanisms/conventions/`, which is literally *where things live and what shape they
have*.

**Settled during implementation:** `sq` passes `check_semantic_names` — `"sq"` is not on
its bin list, and its docstring requirement applies only to `.py`/`.sh` suffixes. But the
same suffix filter means **no gate reads the shim at all**: `verify_ecosystem` compiles
`*.py` and `bash -n`s three `*.sh` globs, `ruff` is handed directories, and `shellcheck`
reads `git ls-files '*.sh'`. So the shim is six lines and
[`tests/test_sq_entry_point.py`](../../../tests/test_sq_entry_point.py) executes it — that
test is the other half of the trade between the short name and the syntax gate.

## What is deliberately not in it

- **No skill wrappers.** `sq discover-plan B-014` would make the CLI *look* like it
  runs the cycle when it only observes one. A skill is conversational judgement; a CLI
  computes. Merging the two dilutes the rule that no verdict in this kit is asserted in
  prose.
- **No `--fix --all`.** Automatically repairing what a gate reports hides the defect
  instead of resolving it. Mechanical repairs (reindexing the backlog) are fine
  individually; as a default they are not.
- **No daemon and no state between invocations.** State is a source of
  non-determinism, and non-determinism costs a reader an investigation.
- **No colour by default.** For the primary consumer — an agent — ANSI is context spent
  on decoration. Detect a TTY and stay plain otherwise.

## Alternatives rejected

**A CLI that owns the list of checks.** Rejected above: a second list diverges from the
first, and the repository already computes reachability.

**Doing nothing, on YAGNI grounds.** This was the strongest objection, because YAGNI is
the repository's own rule and "a complete CLI" is exactly the kind of speculative
surface it forbids. It is rejected on the three false statements in the friction table:
they are not hypothetical costs, they were paid, and two of them reached the owner as
assertions before being caught. The scope was cut to four verbs measured against that
session rather than twelve chosen for symmetry.

**A richer first release** — `status`, `issues`, `explain` shipped together. Deferred.
Each is defensible and none was the source of a measured failure, so each waits for its
own evidence.

## Consequences

**A second surface exists that can rot.** `sq check` must **discover** the gates rather
than list them, and a gate should confirm the CLI reaches everything the CI reaches.
Without that, the CLI lies by omission on the day a gate is added — the same failure
mode as the prose-mention hole that
[`test_every_gate_is_reachable.py`](../../../tests/test_every_gate_is_reachable.py) had to
close.

**The CI's step list moves into the CLI.** That is the point, and it means a bug in the
CLI is a bug in the pipeline. It also means the CLI is covered by the pipeline that
depends on it, which is the correct direction for that dependency.

**A consumer does NOT get the `sq` file, and this ADR said otherwise until 2026-09-09.**
The sentence here used to read *"Consumers gain an entry point that must keep working
across installs"*. That was false when written and was caught during implementation
planning: [`install.sh:235`](../../../mechanisms/distribution/install.sh) iterates
DIRECTORIES — `for item in skills rules hooks commands mechanisms squad` — and hands each
to `copy_tree`. A loose file at the repository root is copied by nothing, and the manifest
loop at `:820` does not list it either.

An ADR asserting a property the implementation does not have is the defect class this
repository exists to catch, so the correction is recorded rather than quietly edited.

**What actually travels is the package.** `squad/` IS on that list, so `squad/cli/`
reaches every consumer and `python3 .claude/squad/cli` works there. The root `sq` is a
convenience for this repository alone. Making the short name travel would mean
special-casing a file in the copy loop and in the manifest writer — a separate item,
deliberately not folded into this one.

Either way the entry point resolves its own location through
[`squad/layout.py`](../../../squad/layout.py), which already distinguishes plugin, copy and
standalone, rather than assuming a path.

**`--touched` can be wrong in a way that is silent.** A file-to-slice map that misses an
edge runs fewer tests and still reports success. It must therefore state the slices it
selected and, when the mapping is uncertain, widen rather than narrow — the same
fail-safe direction the delegation rules take.

## Cross-references

- [`rules/README.md`](../../../rules/README.md) — ownership places a file, which is why a
  task-oriented surface has to be a separate projection.
- [`mechanisms/README.md`](../../../mechanisms/README.md) — the five families, and why
  `cli/` is not a sixth.
- [`rules/squad-map.md`](../../../rules/squad-map.md) — the answer to *where am I and who
  decides this*; `sq` is its executable half.
- [`docs/wiki/decisions/where-knowledge-lives.md`](where-knowledge-lives.md) — the same
  question asked of documents rather than of commands.
