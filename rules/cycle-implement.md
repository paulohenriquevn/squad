# Cycle: IMPLEMENT

Source of Truth for the implementation cycle.

## Purpose

Execute a confidence-approved plan into code, tests, and commits. TDD-disciplined, halt-loop driven.

## Pre-conditions

- A plan exists at `records/plans/{slug}-plan.md` with verdict ≥ SHIPPABLE_WITH_CAVEATS.
- The item the plan implements scored `ALIGNED` — `records/alignment/{slug}-alignment.md` exists and `score_alignment.py` exits 0 on it, which needs BOTH a machine score >= 90% and a tick in every `## Reviewer sign-off` box by a reviewer **who is not the author** — a person, or `alignment_judge.py` when none is coming. `AWAITING_REVIEW` is not a pass, and the agent that wrote the brief may never tick a box. This line said *a human's tick* until 2026-09-01, contradicting the very file it cites: [`alignment-threshold.md § Amended 2026-09-01`](alignment-threshold.md) requires a reviewer who is not the author, which a judge can be, and `score_alignment.py` had already implemented it — the verdict turns on `reviewer_signed_off`, with `signed_by_is_human` reported beside it so a judge's `ALIGNED` reads as the weaker claim it is. Honoured literally, the stale wording re-froze every unattended run at `AWAITING_REVIEW`, which is the halt that amendment exists to end.
- The repository is on `workspace` (per Unbreakable Rule 4 — work is born on `workspace` and promoted to `develop` via PR; see `git-safety.md` § 1).
- The project bootstrapped its language toolchain (e.g., `go.mod`, `package.json`, `pyproject.toml`, `Cargo.toml`).

If any pre-condition fails, refuse and surface the missing item.

## Chain (per task in the plan)

Each task runs as a halt-loop iteration:

```
(once, before the loop)
ROUTE    — mechanisms/cycle/route_domain.py resolves the project's domain specialist

(per task)
RED      — write the failing test that captures the task's acceptance criterion
GREEN    — walk the parsimony ladder, then write the minimal code to pass the test
REFACTOR — improve structure; tests stay green
WIRING   — caller + integration test + runtime metric (the "wiring triad")
COMMIT   — atomic commit referencing the plan slug and task ID
```

## The domain specialist — consulted, never generated

**This cycle generates no agents.** It routes to the specialist the project derived
from its own disk (`agents/README.md`), and consults it three times per iteration:
before RED, after GREEN, before COMMIT.

| `route_domain.py` exit | Meaning | Action |
|---|---|---|
| `0` | resolves to a specialist on disk | consult it |
| `1` | the repo is in no domain | HALT — gate G1 should have refused this upstream |
| `2` | the routing table is unreadable | HALT — guessing is what the table prevents |
| `3` | `BROKEN ROUTE` — a specialist nobody wrote | **HALT, and do not stand in for them** |

A plan citing no `B-NNN` has no `repo:` to route on: the consultation is **skipped and
the skip recorded** under "Pre-condition audit". With no declared domain, any
specialist chosen would be chosen by resemblance.

**Authority.** Read-only; never writes code, never commits, never modifies the plan. A
`[CRITICAL]` finding recommends HALT and does not block on its own — Unbreakable Rule 1
puts the confidence burden on the actor. **Inside its domain the specialist is not
overruled**; believing it is wrong is a finding to record, not a verdict to substitute.

This section was written on 2026-09-01 and it closes a gap rather than adding a step.
The skill had a MANDATORY Step 2.5 that **generated** a per-plan agent, justified in
its own text as being "per `cycle-implement.md`" — and this file contained no mention
of it. A mandatory step resting on a contract that does not contain it is the defect
this kit exists to catch, pointed inward. What the step does is now prescribed here,
and what it used to do is recorded in
`skills/implement/reference/domain-specialist.md`.

## Parsimony gate (GREEN-phase deliberation — pre-write)

Before writing any production code in the GREEN phase, the halt-loop walks the
**parsimony ladder** (`rules/parsimony-ladder.md`) top-down and stops at the first
rung that resolves the need. The six rungs are defined once in that file — not
restated here, per DRY (`parsimony-ladder.md § How each rung is enforced`).

This is a **deliberation, not a detector** — it is the proactive counterpart to the
reactive dead-code / scope-creep gates downstream. The ladder NEVER justifies
skipping a test, input validation, error handling, security, or accessibility — see
`rules/parsimony-ladder.md § Never on the chopping block`. A parsimony argument that
weakens correctness is a Rule 3 (honesty) violation, not a win.

## Wiring triad

A task is **not** complete until all three are present:

1. **Caller** — production code path that exercises the new behavior end-to-end.
2. **Integration test** — covers the boundary the unit test mocked.
3. **Runtime metric** — counter, histogram, or log line that lets ops see the new behavior in production. Without observability, the feature is invisible when it breaks.

## Hard gates (pre-loop, at Step 2)

- **Every plan task has an executable RED-test shape** — verified by `skills/implement/scripts/check_tdd_shape.py`. Tasks whose `#### TDD` body contains only prose (no assertion / GWT / `test_<behavior>` literal) BLOCK the halt-loop from starting. Defense in depth against vague plans that slipped past `/plan-confidence`'s `check_criterion_executability`. Failure path: loop back to `cycle-plan` `/plan-improve`.

## Hard gates (per iteration)

- Parsimony ladder walked before GREEN-phase code is written (`rules/parsimony-ladder.md`) — guardrail items (tests/validation/error-handling/security/accessibility) never sacrificed. `userpromptsubmit-inject.py` re-injects the ladder every turn — _(not mechanized: injecting a deliberation prompt is not checking that the deliberation happened; nothing reads the resulting code and decides which rung it stopped at)_
- Test suite green before commit — `suite_runners.py`, via `run_validation.py` after the halt-loop, and `ci.yml` on every push. _(not mechanized at the point of action: no hook runs the suite before a commit lands, so "before commit" is honoured by discipline and caught afterwards)_
- Linter clean (project-specific — see `rules/code-quality-languages.txt`) — `post-edit-check.py` on every edit, scoped to the edited file, and `run_code_quality.py` over the tree at Step 5.
- No new symbols left dangling (every new function/class has a caller or a test exercising it) — `check_wiring.py`, whose pillar (a) is the non-negotiable one.
- CHANGELOG `[Unreleased]` updated (Unbreakable Rule 6) — `stop-validation.py`.

## Hard gates (per phase boundary — Step 4.7 mini review)

When a commit closes a `## Phase N` of the plan, `skills/implement/scripts/mini_review.py` MUST run BEFORE the halt-loop accepts the next task. Verdict drives:

| Verdict | Trigger | Action |
|---|---|---|
| `PHASE_REVIEW_PASS` | No HIGH or BLOCKER findings | Proceed to next phase |
| `PHASE_REVIEW_NEEDS_FIX` | ≥ 1 HIGH/BLOCKER finding | Halt-loop emits BLOCKED with report path; surface to human; resume via § Step 4 "Resume after recovered blocker" only after fix |

Aggregated checks: phase completeness, diff cohesion (declared scope vs modified files), wiring summary (pillar a non-negotiable across all phase symbols), delta audit coverage — whether Step 5's audit will look at the phase's files at all (a language not `ENABLED` in `rules/code-quality-languages.txt` is audited by nobody). It replaced an unconditional SKIP: `cq_invoke` scores a whole plan, not a file subset, so no delta-scoped audit was ever running behind that line.

Skipping mini review on phase boundary is a documented anti-pattern: design problems compound across phases, and each skipped boundary lets defects propagate into the next phase where they become harder to localize. Plans without `## Phase N` headers cause Step 4.7 to SKIP gracefully (no phases → no boundaries).

## Hard gates (post-halt-loop, before `IMPLEMENTATION_COMPLETE` is honored)

`scripts/run_validation.py` runs after the promise marker and BEFORE the handoff. It consolidates (per ADR 0002 — `cq-gate-in-validate`) every post-implementation gate into one report:

- **Progress-checkpoint schema — validated fail-fast, before any gate that reads it.** `check_progress_schema.py` confirms `.progress-{slug}.json` matches the canonical shape (`skills/implement/templates/progress-schema.json`): a `tasks` array of objects keyed by `id` (not `task_id`), each with `phase`/`status` and, once committed, `commit_sha`/`files`. A malformed checkpoint FAILs loudly instead of letting phase-scoped gates degrade silently.
- **Checkpoint-vs-git consistency.** `check_checkpoint_consistency.py` cross-checks the checkpoint against the real git history both ways: every `committed` task points at a SHA that exists, and every plan task referenced by a real commit (`T{N.M}` convention in the message) is recorded `committed`. Nothing forces the halt-loop to update `.progress` at write time, but a task finished + committed without a matching checkpoint entry FAILs here (and on each phase boundary), so the omission cannot reach handoff. Heuristic limit: relies on the commit-message task-id convention.
- **Coverage gate — a number that was read, or an honest WARN.** `coverage_gate.py` parses the project's coverage report (istanbul `json-summary`, Cobertura XML, coverage.py JSON) and compares TOTAL line coverage against a floor resolved from `rules/code-quality-thresholds.txt:coverage.min_percent` (unset = 80), reporting which source the number came from. No parseable report means `WARN` — *the threshold was not verified* — never `PASS`. The per-changed-file and critical-path thresholds remain unenforced and are documented as such; claiming them from a total would be the laundering this gate was fixed to stop.

- **Test-execution gate — a suite ran, in whatever language this repo speaks.** `suite_runners.py` detects every language manifest at the repo root and runs its suite: `npm test`, `pytest` (falling back to `unittest`), `go test ./...`, `cargo test`. The consolidating `test_execution` check **FAILs when a manifest is present and no suite executed** — including "pytest collected no tests" and "the toolchain is unavailable". Only a repo with no language manifest at all (genuine pre-code phase) may SKIP it. This closes the hole where a Python/Go/Rust repo skipped all four npm checks, landed on `PARTIAL`, and `PARTIAL` exits `0` — making `VALIDATION_GATE_PASSED` emittable with no test having run.
- **Wiring summary — independently re-verified, never self-reported.** Symbols are derived from the committed diffs and `check_wiring.py` is re-run per symbol; a progress file claiming pillar (a) pass over an actually-uncalled symbol is caught as fabricated evidence (FAIL). Trusting the self-reported `wiring` field is the bypass this closes.
- **TDD-shape gate — the Step 2 pre-loop gate, re-asserted.** `check_tdd_shape.py` runs again after the loop. It was invoked from `SKILL.md` prose only and no downstream gate asked whether it had run, so a halt-loop driven from a prose-only plan was indistinguishable from one driven from an executable plan. A task without an executable RED-test shape FAILs the validation.

- **Phase-review gate — Step 4.7 actually ran.** `check_phase_review.py` requires the mini-review report (`{slug}-phase{N}-review-*.md`) for every `## Phase N` whose tasks are all `committed`. This section already called skipping the mini review a documented anti-pattern; until this gate existed, nothing could tell a skipped boundary from a reviewed one, which is the same self-report problem the wiring recheck solves by re-deriving the evidence.

- **Acceptance-criteria gate** — `check_acceptance_criteria.py` enforces the plan's mechanizable AC/DoD that the command gates miss (file-size budget per changed file, CHANGELOG-updated) and surfaces non-mechanizable criteria (backward-compat) for human evidence instead of accepting a self-ticked box.
- **Test-obligation gate** — `check_test_obligations.py`. Declared concurrency tests / failure scenarios must have at least one matching test in the tree; total absence when the plan promised them is a FAIL (a generic green suite never exercised them).
- **`/code-quality` verdict ∉ {FAIL_HARD, INVALID}** — `cq_invoke.py`, called internally by `run_validation.py`. FAIL_SOFT and PASS_WITH_CAVEATS surface as WARN in the report but do not block. Override only with `--no-code-quality` (pre-code phase or CQ not installed).

Exit codes: `0` = `PASS` or `PARTIAL` (proceed); `1` = `FAIL` (trigger validation halt-loop — see below); `2` = invocation error (escalate to human).

## Validation halt-loop (mandatory when `run_validation.py` exits 1)

When the post-halt-loop gate returns `FAIL`, the skill re-invokes `ralph-loop:ralph-loop` with the validation-fix driver (`skills/implement/prompts/validation-fix-prompt.md`). This is the **default behavior of `/implement`**, not opt-in — driving validation fixes manually outside ralph-loop is the same contract violation as bypassing the Step 4 TDD halt-loop.

Contract:

- **Completion promise:** `<promise>VALIDATION_GATE_PASSED</promise>` — asserts `run_validation.py {slug}` re-run in the same iteration exited `0`. The loop runs until validation actually passes; never emit this promise on a partial pass.
- **Pre-flight guard:** verify the Step 4 `ralph-loop.local.md` has `active: false` before invoking; concurrent loops on overlapping state are an anti-pattern.
- **Per-iteration objective:** fix one (or one root-cause-clustered group of) `check.status == FAIL` per iteration; commit atomically (`fix(validation): …`); re-run `run_validation.py`; emit promise on exit 0 or STOP turn for next iteration.
- **Forbidden:** disabling/weakening failing tests, lowering coverage thresholds, no-op callers to satisfy pillar (a), hand-edited `.wiring-evidence.json`, ADR-defer of `symbol_fabrication_*` / `dead_code_unallowlisted_*` hard caps, emitting the promise on a `BLOCKED` exit to satisfy a downstream gate.

## Stop conditions

**Emitting the milestone:** the event that records Step 4 finishing is emitted with
`cycle_events.py end --cycle implement --verdict IMPLEMENTATION_COMPLETE --once`. The
`--once` is not optional here: a phase that CONCLUDES may be recorded once, and
without the flag this milestone has been written twice for one item, seconds apart. A
gate that ITERATES is the opposite case — the same verdict several times in as many
seconds, each one a real run — which is why the emitter cannot tell the two apart and
the caller declares which it is.

**Step 4 — TDD halt-loop:**

- Hard gate fails twice on the same task → halt-loop pauses, escalate to human.
- Plan task list exhausted → emit completion promise (`IMPLEMENTATION_COMPLETE`).

**Step 5.5 — Validation halt-loop:**

- Same check FAIL × 3 consecutive iterations with **no observable progress** (identical diagnostic, identical failure shape, no new diff direction) → HALT; surface BLOCKED report to the human. **Do NOT emit `VALIDATION_GATE_PASSED`** — the gate did not pass.
- `code_quality INVALID` (contract itself broken) → HALT immediately; surface to human.
- Unremediatable `FAIL_HARD` (`symbol_fabrication_*` / `dead_code_unallowlisted_*` cannot be fixed without scope-creeping the plan) → HALT; surface BLOCKED report; recommend loop back to `cycle-plan`. **Do NOT emit the completion promise** — the validation gate has NOT passed.

The promise `VALIDATION_GATE_PASSED` is emitted EXCLUSIVELY when `run_validation.py` exits `0`. There is no graceful-exit path that emits the promise on a partial pass. Honest BLOCKED > false PASS (Unbreakable Rule 3).

**Either loop emitting a BLOCKED report blocks downstream:** `/review` and `/release` MUST NOT run until the human resolves the blocker.

## Anti-patterns

- Writing production code before the failing test (skipping RED).
- Skipping REFACTOR because "tests are green" — the cycle is RED → GREEN → REFACTOR, not RED → GREEN → ship.
- WIRING done in a separate PR ("I'll wire it later"). Later never comes.
- Commits that mix multiple tasks. Each commit references one task ID.
- Editing the plan during implementation. If the plan was wrong, return to `/plan-write`.

## Output

- Commits on the working branch.
- `records/implementations/.progress-{slug}.json` — the runtime checkpoint (gitignored) the halt-loop writes each iteration and every gate reads. Schema: `skills/implement/templates/progress-schema.json`.
- `records/implementations/{slug}/` — per-iteration logs.
- `records/implementations/{slug}-implementation.md` — final summary with wiring triad checklist per task.

## Cross-references

- Schema for cycle rules: `rules/cycle-rule-schema.md`
- Skill: `skills/implement/SKILL.md`
- Conventions: `rules/architecture.md`, `rules/testing.md`, `rules/error-handling.md`, `rules/git-safety.md`, `rules/loop-engine-convention.md`, `rules/parsimony-ladder.md`
- Macro super-loop: `rules/cycle-maintenance.md` — one cycle-implement run per milestone in the super-loop
- Upstream: `rules/cycle-plan.md` (plan must reach verdict ≥ SHIPPABLE_WITH_CAVEATS)
- Downstream: `rules/cycle-code-quality.md` (runs after `IMPLEMENTATION_COMPLETE`)
- Companion gates against plan vagueness:
  - Plan-side (heuristic, linguistic): `skills/plan-confidence/scripts/check_criterion_executability.py`
  - Implement-side (structural, shape detection): `skills/implement/scripts/check_tdd_shape.py`
- Phase-boundary mini review (Step 4.7):
  - Orchestrator: `skills/implement/scripts/mini_review.py`
  - Phase completeness: `skills/implement/scripts/check_phase_completeness.py`
  - Diff cohesion: `skills/implement/scripts/check_diff_cohesion.py`
  - Reports persisted at: `records/mini-reviews/{slug}-phase{N}-review-{date}.md`
  - Companion to `cycle-review.md` (final review): mini review runs per-phase; cycle-review runs once at the end. Both must pass for handoff.
