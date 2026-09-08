# Cycle Rule Schema

Canonical schema for every `rules/cycle-*.md` file. Defines required vs optional sections, the canonical vocabulary for verdicts and completion promises, and the rationale for why each cycle has a vocabulary of its own.

## Purpose

Without a shared schema, cycle rules drift: one rule calls section X "Trigger conditions", another calls it "Pre-conditions", a third "When to use". Verdict tokens proliferate (`SHIPPABLE` vs `PASS` vs `READY_TO_MERGE`) without anyone explaining why. The schema makes the contract explicit so reviewers can detect divergence and `mechanisms/gates/check_xrefs.py` can enforce it mechanically.

## Required sections

Every `cycle-*.md` MUST have these top-level sections, in this order:

| # | Section | Purpose |
|---|---|---|
| 1 | `# Cycle: <NAME>` | Title + one-line tagline below it |
| 2 | `## Purpose` | What problem this cycle solves; what it produces |
| 3 | `## Pre-conditions` | When to invoke; when NOT to invoke (negative cases included) |
| 4 | `## Chain` | The ordered phases as a fenced code block — skills/scripts invoked in sequence |
| 5 | `## Anti-patterns` | Concrete failure modes a reviewer should flag |
| 6 | `## Cross-references` | Skills, sibling cycles, conventions, allowlists — every related file |

## Optional sections

A cycle MAY include any of the following, when it adds clarity. They fall in two
positional bands relative to the required sections.

**Body band — between `## Chain` and `## Anti-patterns`:**

| Section | When to include |
|---|---|
| `## Phase contracts` | Multi-phase cycles where each phase has its own input/output/hard-gate |
| `## Wiring triad` | Cycles producing code that touches production (currently: implement) |
| `## Verdicts` | Cycles that emit a tripartite verdict, listed with definition + downstream action |
| `## Hard gates` | When at least one finding is severe enough to block the chain |
| `## Severity rubric` | Cycles that classify findings (code-quality, review) |
| `## Stop conditions` | Loop-style cycles (halt-loop, ralph-loop) where a stop signal must be defined |
| `## Confidence gates between phases` | Orchestrators (idea-to-release) that gate transitions |

**Footer band — after `## Anti-patterns`, before `## Cross-references`:**

| Section | When to include |
|---|---|
| `## Output` | When the artifacts produced live in non-obvious paths |
| `## Rollback` | Cycles whose output mutates the registered ecosystem (e.g., discover → registered skill) |

Within a band, sections SHOULD appear in the order listed. `## Verdicts` precedes
`## Hard gates` (the verdict vocabulary frames what the gates enforce). `## Output`
and `## Rollback` are terminal — they describe artifacts/recovery and belong at the
foot of the document, not interleaved with the analytic body. Reordering beyond
this is a smell unless the cycle has a structural reason for it.

## Canonical verdict vocabularies

Each cycle has its own verdict vocabulary because the **shape of the decision** differs. The schema documents them centrally so a reader does not have to spelunk to learn what `READY_TO_MERGE` means vs `SHIPPABLE`.

| Cycle | OK | OK with caveats | Not OK — recoverable | Not OK — structural |
|---|---|---|---|---|
| `cycle-brainstorm` (phase −1 · product alignment) | `PRODUCT_ALIGNED` | — | `NEEDS_REVISION` | `INVALID` (+ `AWAITING_REVIEW`, orthogonal) |
| `cycle-maintenance` (macro super-loop) | `ITEM_SHIPPED` / `ITEM_KILLED` / `ITEM_VERIFIED_LOCAL` | `ITEM_IN_FLIGHT` (paused where only a person can act) | `ITEM_BLOCKED` (recoverable per item) | `ITEM_UNROUTABLE` (repo in no domain) |
| `cycle-backlog` (phase 0 · intake) | `ITEM_REGISTERED` | — | `ITEM_MERGED` (folded into an open item) | `ITEM_REJECTED` (out of ecosystem, or gate G5) |
| `cycle-discover` | `SHIPPABLE` (+ `ITEM_KILLED`, orthogonal) | `SHIPPABLE_WITH_CAVEATS` | `NEEDS_REVISION` | `INVALID` |
| `cycle-plan` | `SHIPPABLE` | `SHIPPABLE_WITH_CAVEATS` | `NEEDS_REVISION` | `INVALID` |
| `cycle-implement` | `IMPLEMENTATION_COMPLETE` (completion promise) | — | (halt-loop pauses for human) | — |
| `cycle-code-quality` | `PASS` | `PASS_WITH_CAVEATS` | `FAIL_SOFT` | `FAIL_HARD` / `INVALID` |
| `cycle-review` | `READY_TO_MERGE` | `READY_TO_MERGE_WITH_FOLLOWUPS` | `NEEDS_FIXES` | `NEEDS_DEEPER` |
| `cycle-release` | `RELEASED` (final cut) | `PRE_RELEASED` (an `-rc.N` batch: installable, scope unfinished) | `PR_OPEN_AWAITING_APPROVAL` (a gate did not pass — a remote needing a reviewer is a violated premise, not a state) | `BLOCKED` |
| `cycle-acceptance` | `ACCEPTED` | `ACCEPTED_WITH_CAVEATS` | `REJECTED` | `NOT_VALIDATED` |
| `cycle-idea-to-release` | (delegates to each chained cycle's verdict) | — | (pause + ask human at any gate failure) | — |
| `cycle-judge-codex` (optional, external plugin) | `SHIPPABLE` / `READY_TO_MERGE` (`:final` only) | `SHIPPABLE_WITH_CAVEATS` | `NEEDS_REVISION` / `NEEDS_FIXES` / `NEEDS_DEEPER` (`:final` only) | `FAIL_HARD` / `INVALID` / `META_DEFECT_FOUND` (`:final` only) / `AGGREGATOR_BUG_SUSPECTED` (`:final` only) |
| `honesty-gate` (utility) | `EVIDENCE_SUFFICIENT` | `EVIDENCE_WITH_CAVEATS` | — | `EVIDENCE_INSUFFICIENT` |

### Why each vocabulary differs

- **brainstorm** grades a **cascade of four documents plus the agreement over them**, so its bands split on a distinction no other cycle needs. `NEEDS_REVISION` means the rubric scored below the floor and editing the documents can lift it; `INVALID` means a document is absent or an id cites a referent that does not exist, which no editing of the citing document can fix. **`AWAITING_REVIEW` is orthogonal to all three** — the same shape as `cycle-discover`'s `ITEM_KILLED`: it grades nothing. The structure is complete and the judgement has not been made, and it is the only cycle where that judgement may not be delegated to a judge (`cycle-brainstorm.md § Why the judge may not sign this one`). Reused rather than renamed because `cycle-plan` already emits it for the identical state and `rules/blocking-verdicts.txt` already holds it.
- **maintenance** emits **macro-loop progression verdicts** per item: `ITEM_SHIPPED` when the item reached RELEASED, `ITEM_KILLED` when measurement refuted the hypothesis (an OK outcome — the loop protected the plan cycle from a hunch), `ITEM_BLOCKED` when a sub-cycle blocked recoverably, and `ITEM_UNROUTABLE` when the item's repo belongs to no domain, and `ITEM_VERIFIED_LOCAL` when every file the fix changed is untracked — the work is real and verified, and no tag can point at it. That last one is in the OK column on purpose: reporting it as blocked would file finished work as outstanding. Deliberately absent: a `*_COMPLETE` token. A roadmap is a finite declared scope and can be exhausted; a backlog is not a scope, and an empty one means nobody has looked recently rather than that the work is done. The empty state is `BACKLOG_EMPTY`, a prompt to sweep, and it is reported outside the OK/not-OK bands because it grades nothing.
- **discover/plan** emit a **structural fitness verdict** on a document. `INVALID` means the document violates a hard cap (fabricated evidence pointer, empty corner); `NEEDS_REVISION` means the score is recoverable via `*-improve`. **`discover` carries a fifth token that is orthogonal to the other four**: `ITEM_KILLED` reports an *outcome* rather than grading an *artifact* — the measurement ran, the hypothesis did not hold, and there is no document to score. It sits in the OK column because a run that kills an item succeeded: it stopped work that would have been justified by a hunch. Collapsing it into `INVALID` would file the cycle's most valuable result as a failure and create a standing incentive to ship weak findings rather than kill them.
- **implement** does not emit a verdict — it emits a **completion promise** (`IMPLEMENTATION_COMPLETE`) consumed by downstream cycles. Halt-loop pauses on hard-gate failure rather than emitting a verdict.
- **code-quality** emits a **graded quality verdict** keyed to a score cap (per `code-quality-golden-rule.md` § 1): `PASS`/`PASS_WITH_CAVEATS` proceed to `/review`; `FAIL_SOFT` may proceed only with an ADR dismissing each soft cap; `FAIL_HARD` blocks `/review` and loops back to `/implement`; `INVALID` means structural integrity is broken (golden rule missing/corrupt). The golden rule is the Source of Truth for the rubric — this matrix only lists the tokens.
- **review** emits **merge-readiness**: `READY_TO_MERGE` is the only green; `NEEDS_FIXES` returns to `/implement`; `NEEDS_DEEPER` returns to `/plan-write` for re-scoping.
- **release** emits two OK tokens because it cuts twice, and they are not degrees of the same thing. `PRE_RELEASED` says a batch is installable and the scope is unfinished; `RELEASED` says a milestone closed and was accepted. It sits in the caveats column because the caveat is real and permanent for that tag — an rc never becomes a release, it is superseded by one. **Only `RELEASED` moves an item to `shipped`**: `advance_items.py` reads that token and nothing else, so a pre-release cannot close work it did not finish.
- **acceptance** emits an **end-user validation verdict** on the *released* delivery, so its "not OK" band splits on a distinction no other cycle needs: `REJECTED` means the delivery was exercised and a Definition-of-done criterion did not hold; `NOT_VALIDATED` means the run could not establish either outcome (target unreachable, criterion never exercised, evidence missing, milestone declared no DoD). Collapsing them into one token would let untested work be reported as tested — the exact failure the cycle exists to prevent. Both block the `ROADMAP.md` checkbox flip identically. `ACCEPTED_WITH_CAVEATS` requires every caveat to be a filed issue.
- **honesty-gate** emits **evidence-readiness** because its decision is "is the v1.0 claim supported by recorded usage?"
- **judge-codex** mirrors the **upstream cycle's vocabulary** intentionally — `:discover`/`:plan` reuse the SHIPPABLE band; `:implementation` mirrors `cycle-implement` exit states adapted to a verdict; `:final` mirrors `cycle-review`'s merge-readiness plus two **meta-verdicts** (`META_DEFECT_FOUND`, `AGGREGATOR_BUG_SUSPECTED`) that exist only at the review-of-review stage. The plugin is **delivered externally** (`usetheodev/judge-codex-plugin-cc`) and consumes `plan`'s golden-rule files by path convention.

### Tokens that belong to no single cycle

The matrix above is organised per cycle, and four verdicts do not fit a column because
they are emitted from more than one. They were absent from this document until
2026-09-07 while being live in `blocking-verdicts.txt` — so a reader learning the
vocabulary here did not know they existed, and a reader meeting one in a contract did
not know it blocks. `tests/test_blocking_verdicts_are_in_the_schema.py` now fails when
a blocking verdict is missing from this file.

| Token | Emitted by | Meaning |
|---|---|---|
| `AWAITING_HUMAN` | any phase — declared in `cycle-plan`, `cycle-release`, `cycle-review`, `cycle-discover`, `cycle-acceptance`, `cycle-maintenance` | The phase ran and stopped at a gate only a person opens. **Emit it** — the work happened, and without the event the board, the drift checker, the selector and the watchdog all see an item nobody touched. Measured 2026-08-31: B-058 and B-059 halted at such a gate, emitted nothing, and the watchdog restarted B-059 because no event had appeared |
| `INVALID_AWAITING_HUMAN` | scoring phases | Structurally invalid **and** waiting on a person. Distinct from `INVALID` because the two take different next actions: one is edited, the other is escalated |
| `NEEDS_SPLIT` | `cycle-plan` (`plan-alignment`) | The item describes two subsystems, and no rewrite of the brief closes that. Kept distinct from `NEEDS_REVISION`, which is recoverable by editing |
| `FAIL` | `cycle-implement` validation checks | A check inside a phase failed. Not a cycle verdict — it is a check outcome that `blocking-verdicts.txt` treats as a wall, which is why it is documented here rather than in a cycle's row |

`FAIL_SOFT` is deliberately NOT on this list and deliberately not in
`blocking-verdicts.txt`: it sends work back to be redone without forbidding the chain
from advancing once it is, and treating it as a wall would report every ordinary rework
loop as a violation.

Do NOT introduce a new verdict token without adding it to this matrix and explaining why an existing token does not fit.

## Section conventions

- Use sentence-case headers (`## Pre-conditions`, not `## PRE-CONDITIONS`).
- The `## Chain` block MUST be a fenced code block. Phases inside use `↓` arrows for flow.
- `## Cross-references` MUST link to real files. `mechanisms/gates/check_xrefs.py` validates that every backtick-referenced path resolves.
- Verdict tokens MUST be in the matrix above.
- Hard gates MUST cite the rule they enforce (e.g., "Unbreakable Rule 4" for the no-`main`-commit gate).

## Golden Rule Change Protocol

The authoritative protocol for changing any LOCKED golden rule (`rules/*-golden-rule.md`).
Each golden rule references this section instead of restating it (per ADR-0010), and
keeps only its own deviations.

A golden rule is LOCKED. Changing it requires ALL of:

1. An ADR in `docs/ADR/` proposing the change — **versioned, because the record has to
   reach whoever clones**. This step named `records/adrs/` until 2026-09-07, and
   `.gitignore` excludes `records/` wholesale, so the justification for changing the
   kit's most locked contracts went to a directory that travels nowhere. The
   contradiction was already load-bearing: `plan-confidence-golden-rule.md` extended a
   gate on 2026-08-26 and had to write its reasoning into the golden rule instead,
   saying so in the file — somebody following the protocol had to break it to be
   useful. A **consumer's** run-local ADRs stay under `records/adrs/`; that is their
   repository and their trail, and it is what `code-quality-allowlist.txt` and
   `deps-audit-allowlist.txt` mean when they require one for an exemption.
2. A CHANGELOG entry under `[Unreleased] § Changed`.
3. `python3 "$([ -d .claude/skills ] && echo .claude || echo .)/mechanisms/gates/check_xrefs.py"` and `python3 "$([ -d .claude/skills ] && echo .claude || echo .)/mechanisms/gates/verify_ecosystem.py"` both PASS.

A change that **softens** a gate (loosening a cap, removing a check) carries the full
burden above. A change that **extends** the contract (adding a new hard cap) follows the
same process with lower burden — it tightens, it does not weaken. Per-rule deviations
(e.g., owner sign-off, operator anchor-evidence sign-off, threshold-file reference bumps,
documenting the change in a rule-local "Rules that cannot be bent" section) are listed in
each golden rule's own change section.

## Enforcement

- `mechanisms/gates/check_xrefs.py` validates the `## Cross-references` section against the filesystem on every run.
- `mechanisms/gates/verify_ecosystem.py` validates that every cycle has the required sections (`## Purpose`, `## Chain`, `## Anti-patterns`).
- A new cycle without entries in the verdict matrix above is a review BLOCKER.

## Adding a new cycle

1. Copy this schema's required sections into the new rule.
2. Add the new cycle's verdict vocabulary row to the matrix above.
3. Wire the cycle in `README.md` (Project structure + the cycle diagram) and `HOW-TO-USE.md` (Which cycle, when).
4. Add the new SKILL.md `Cycle contract` section pointing back at the rule.
5. Run `python3 "$([ -d .claude/skills ] && echo .claude || echo .)/mechanisms/gates/check_xrefs.py"` and `python3 "$([ -d .claude/skills ] && echo .claude || echo .)/mechanisms/gates/verify_ecosystem.py"` — both MUST be PASS before the cycle is merged.
