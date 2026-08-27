# Cycle: PLAN

Source of Truth for the planning cycle.

## Purpose

Produce an implementation plan — what to build, how, in what order, with which dependencies and risks. Output is a document, not code.

## Pre-conditions

- A feature has a defined goal and known prior art (otherwise, run DISCOVER first).
- A non-trivial bug fix that touches multiple modules.
- (Optional macro context) — when running inside the `cycle-maintenance` super-loop, `/to-plan` accepts `--milestone M<N>` to persist the milestone ID in the plan frontmatter; `cycle-release` reads this metadata to flip the checkbox post-merge. Plans without `--milestone` are valid (ad-hoc / hotfix work) but skip the post-release flip.

Do NOT trigger PLAN for:
- Single-line changes (write the code).
- Pure refactors with no behavior change (open a PR with the diff and a 1-line rationale).

## Chain

Phase 0 is OPTIONAL — invoke only when the topic is non-trivial AND requirements are not yet precise. Phases 1+ are unbreakable.

```
/grill-me {topic-slug}                     [Phase 0 — OPTIONAL]
     ↓ (interview-driven requirements resolution)
     ↓ (produces: knowledge-base/grills/{slug}-grill.md)
     ↓ verdict:
     ↓   READY_FOR_PLAN  → proceed to /to-plan
     ↓   NEEDS_SPLIT     → split topic, re-grill sub-topics
     ↓   NEEDS_DISCOVERY → return to /discover-plan first
/to-plan "{one-sentence feature description}"
     ↓ (Step 0 auto-discovers rules/ + skills/*-patterns/ + grill output if present)
     ↓ (produces: knowledge-base/plans/{slug}-plan.md)
/edge-case-plan {slug}
     ↓ (MUST-FIX absorbed into the plan)
/deps-audit {slug}
     ↓ (dependencies + CVE audit before any code)
/plan-confidence {slug}
     ↓ (score)
     ↓ if INVALID  → /to-plan (rewrite)
     ↓ if low      → /plan-improve {slug} → /plan-confidence (re-score)
     ↓ if ≥ SHIPPABLE_WITH_CAVEATS → ready for /implement
```

## Phase contracts

| Phase | Input | Output | Hard gate |
|---|---|---|---|
| grill-me (opt.) | topic slug | grill log + verdict in knowledge-base/grills/{slug}-grill.md | every recommended answer offered; ≤ 15 questions; verdict declared |
| to-plan | feature description (+ grill output if Phase 0 ran) | plan with Goal, Tasks, Risks, Test Plan, Open Questions | Coverage Matrix present (every Goal claim mapped to ≥ 1 task) |
| edge-case-plan | plan | annotated plan with MUST-FIX | every MUST-FIX has owner + acceptance criterion |
| deps-audit | plan | dependency report with CVE status | no critical CVE on a planned dependency — **human-enforced, see below** |
| plan-confidence | plan | score + verdict | INVALID returns to /to-plan |

**The `deps-audit` gate was, until 2026-08-26, the one gate in this cycle nothing mechanized.**
Every other hard gate above is checked by a script that can fail the phase; this one held only if a
human invoked `/deps-audit {slug}` and honoured the verdict by hand. It is now checked by
`check_deps_audit.py`, which `/plan-confidence` runs like any other check:

| Plan state | Effect |
|---|---|
| declares no new dependency | check does not apply |
| declares one, no audit report on disk | soft floor ≤ 89 (`soft_floor_deps_audit_missing`) |
| report says CRITICAL/HIGH CVE in a declared dep | hard cap ≤ 49 → `INVALID` (`deps_audit_insecure`) |

The check does NOT scan for CVEs — `/deps-audit` does that, with the scanners. It reads the verdict
that run left on disk, so the human step that remains is running the audit, and forgetting it now
costs the plan its band instead of passing silently. The extension of the gate is recorded in
`plan-confidence-golden-rule.md` § Rules that cannot be bent.

Stating it is the point. A gate listed beside four mechanized ones reads as mechanized, and a gate
believed to be automatic is one nobody runs.

## Halt-loop contract (/plan-improve only)

`/plan-improve` is the only phase of `cycle-plan` that drives an autonomous halt-loop via `ralph-loop:ralph-loop`. It follows the same rigorous template established for `/implement` (per `rules/cycle-implement.md`): pre-flight guard against concurrent ralph-loops, formal stop conditions, post-promise sanity check, anti-patterns enumerated, honest BLOCKED report over false PASS.

- **Completion promise:** `<promise>PLAN_IMPROVED</promise>` — asserts re-run of `run_structural.py` in the emitting iteration shows verdict ≥ `--target`. Step 6 post-promise sanity check re-verifies score-on-disk. The loop runs until the score on disk reaches the target; partial improvements do not justify emitting the promise.
- **Stop conditions:** see `skills/plan-improve/SKILL.md § Stop conditions` (6 enumerated cases). When the loop stops without reaching the target, emit a BLOCKED report (no completion promise) and surface the structural blocker to the human.
- **Hard caps are NOT auto-fixable.** Per § Verdicts, `INVALID` (49) returns to `/to-plan` rewrite — `/plan-improve` MUST NOT iterate trying to lift a hard cap.

A BLOCKED report blocks downstream: `/plan-confidence` MUST NOT honor the plan as SHIPPABLE until the human resolves the blocker.

## When to skip Phase 0 (grill-me)

- The user already wrote a detailed spec (e.g., a one-pager in `docs/specs/`).
- Trivial fix (single-line, obvious bug).
- Pure refactor with no behavior change.
- Decision tree has < 3 branches — just write the plan.
- A grill output already exists for the same slug and is < 7 days old.

## Verdicts

- `INVALID` — hard cap blew (e.g., Coverage Matrix incomplete, fabricated citation). Return to `/to-plan`. **`/plan-improve` does not fix hard caps.**
- `NEEDS_REVISION` — soft caps blew (risks under-addressed, test plan thin). Use `/plan-improve`.
- `SHIPPABLE_WITH_CAVEATS` — proceed to `/implement`; caveats are explicit, not hidden.
- `SHIPPABLE` — green light.

## Anti-patterns

- Plans that are essentially "implement X, test it, ship it" — no actual decomposition.
- Plans without a Test Plan section. If the plan can't say how to verify success, the plan is incomplete.
- Plans listing every possible task without prioritization. Tasks need an ordering.
- Skipping `/deps-audit` because "the lib is well-known". Well-known libs ship CVEs too.
- Pivoting the plan during `/implement` instead of returning to `/to-plan`. If the plan was wrong, the plan needs to change; the implementation log is not the place.

## Cross-references

- Schema for cycle rules: `rules/cycle-rule-schema.md`
- Skills: `skills/grill-me/SKILL.md`, `skills/to-plan/SKILL.md`, `skills/edge-case-plan/SKILL.md`, `skills/deps-audit/SKILL.md`, `skills/plan-confidence/SKILL.md`, `skills/plan-improve/SKILL.md`
- Macro super-loop: `rules/cycle-maintenance.md` — defines the `milestone_id` frontmatter contract that plans MAY carry
- Upstream: `rules/cycle-discover.md` (when prior art is unknown)
- Downstream: `rules/cycle-implement.md` (consumes the plan with verdict ≥ SHIPPABLE_WITH_CAVEATS)
- Conventions: `rules/architecture.md`, `rules/testing.md`
