# Cycle: AUTO-PLAN (sub-cycle of cycle-maintenance)

Source of Truth for the end-to-end autonomous orchestrator. Sits **below** `cycle-maintenance` in the cycle hierarchy: `cycle-maintenance` selects the next milestone and delegates one full `cycle-idea-to-release` run per milestone.

## Purpose

Chain DISCOVER → PLAN → IMPLEMENT → CODE-QUALITY → REVIEW → RELEASE autonomously for **one milestone** (or one ad-hoc topic), taking it from idea to a release PR awaiting human approval — without the user having to invoke 9+ slash commands manually. Default mode is `full-pipeline`; the `--plan-only` flag retains the legacy "discover + plan" behavior.

Two invocation modes coexist:

- **Backlog-driven** (`/idea-to-release B-NNN`): the form `cycle-maintenance` delegates. Takes the item's statement + Definition of Done as the input topic. When the item is bound to a milestone, the plan carries `milestone_id` so `cycle-acceptance` can find it after release.
- **Roadmap-driven** (`/idea-to-release M<N>` OR `/idea-to-release` without arg): reads `ROADMAP.md`, takes the milestone objective + DoD as the input topic, persists `milestone_id` in the resulting plan frontmatter so `cycle-acceptance` knows which checkbox its verdict governs.
- **Ad-hoc** (`/idea-to-release {topic-slug}`): work outside both registries (hotfixes, exploratory). The plan carries no `milestone_id` — the chain ends at `RELEASED`, with no acceptance phase to run.

## Pre-conditions

- The topic is large enough that running cycles manually would be tedious.
- The user explicitly authorizes autonomous execution.
- **Roadmap-driven mode only:** `ROADMAP.md` exists at the repo root AND at least one milestone is `[ ]` (unchecked) AND has all its declared dependencies satisfied (all `[x]`).

When NOT to use:
- A plan already exists AND only implementation remains → call `/implement` directly.
- The feature is trivial (< 1 hour by hand).
- You're not 95% sure about requirements (Unbreakable Rule 1).
- **Roadmap-driven mode:** all milestones already `[x]` (project's V1 scope is complete — declare V2 or stop) OR every `[ ]` milestone is blocked by another `[ ]` (dependency wall — `cycle-maintenance` emits `ROADMAP_BLOCKED`).

## Chain

```
/pipeline B-014 B-022 …             [OPTIONAL — schedules many items through
     ↓                               everything below, one stage each, a git
     ↓                               worktree per lane. Every gate still applies
     ↓                               per item; the alignment halt stops ONE item
     ↓                               while the others advance.]

/idea-to-release M<N>
     ↓ READ ROADMAP — extract milestone objective + DoD; derive slug; record milestone_id
     ↓ DISCOVER     (full chain, if no prior opportunity)
     ↓ PLAN         (full chain — auto-injects MUST-FIX from plan-edge-cases into the plan)
     ↓                — plan frontmatter carries milestone_id: M<N> (contract with cycle-acceptance)
     ↓ gate:         only proceed if /plan-confidence ≥ SHIPPABLE_WITH_CAVEATS
     ↓ IMPLEMENT    (halt-loop until IMPLEMENTATION_COMPLETE)
     ↓ CODE-QUALITY (audit; gate proceeds only when PASS / PASS_WITH_CAVEATS)
     ↓ REVIEW       (5-7 specialist agents)
     ↓ gate:         only proceed if /review ∈ {READY_TO_MERGE, READY_TO_MERGE_WITH_FOLLOWUPS}
     ↓ RELEASE      (opens develop→main PR with semver tag; PAUSES for human approval)
     ↓                — cycle-release does NOT flip the checkbox
     ↓ ACCEPTANCE   (/acceptance M<N> — exercises the RELEASED delivery against the DoD)
     ↓                — ACCEPTED | ACCEPTED_WITH_CAVEATS → flips ROADMAP.md M<N> [ ] → [x]
     ↓ verdict:      ACCEPTED OR ACCEPTED_WITH_CAVEATS OR REJECTED
     ↓                OR PR_OPEN_AWAITING_APPROVAL (chain paused at the human gate)
```

Ad-hoc (`/idea-to-release {topic-slug}` with arbitrary slug):

```
/idea-to-release {topic-slug}
     ↓ (same chain as above)
     ↓ plan frontmatter carries NO milestone_id (this work is off-roadmap)
     ↓ no milestone_id → no acceptance phase; the chain ends at the release
     ↓ verdict:      RELEASED OR PR_OPEN_AWAITING_APPROVAL
```

`--plan-only` mode:

```
/idea-to-release {topic-slug} --plan-only
     ↓ DISCOVER
     ↓ PLAN
     ↓ stops at the locked plan; user invokes /implement manually later
```

## Confidence gates between phases

- Before PLAN starts: a discovery opportunity exists OR the user explicitly confirms no measurement is needed (deterministic; pre-recorded via `--no-discover`).
- **Before PLAN starts, for anything from `BACKLOG.md`: the item is `ALIGNED`.** `check_alignment_gate.py` hard-caps an unaligned plan at 49, so an item that skipped `/plan-alignment` cannot clear the next gate anyway. This gate is satisfied by a reviewer who is **not the author** — a person, or `alignment_judge.py` when no person is coming. The agent that wrote the brief may never tick a box, and that rule is unchanged; what changed on 2026-09-01 is that it was being read as *a human must sign*, which does not follow from it and left every unattended run halted at `AWAITING_REVIEW` permanently. An autonomous chain that could align an item **with itself** would still be the failure this gate exists to prevent, which is why the judge reads the item's evidence rather than the brief, signs under its own name, and can refuse. `score_alignment.py` reports the weakest signer, so a judge's `ALIGNED` never reads as a person's.
- Before IMPLEMENT starts: plan-confidence verdict ≥ SHIPPABLE_WITH_CAVEATS.
- Before CODE-QUALITY starts: implementation emitted `IMPLEMENTATION_COMPLETE`.
- Before REVIEW starts: code-quality verdict ∈ {`PASS`, `PASS_WITH_CAVEATS`}.
- Before RELEASE starts: review verdict ∈ {`READY_TO_MERGE`, `READY_TO_MERGE_WITH_FOLLOWUPS`}. The second is not a softening: it is only reachable when zero BLOCKER remain and every HIGH is a *registered* followup, which `consolidate_findings.py` verifies against the plan's `## Followups` before emitting it.
- Final manual gate: human approves the release PR. Auto-merge is forbidden (Unbreakable Rule 4).
- Before ACCEPTANCE starts: `cycle-release` emitted `RELEASED` AND the plan carries a `milestone_id`. No `milestone_id` → the chain ends at `RELEASED`; there is no milestone to accept.

Any gate failure → pause + surface the blocking finding. The orchestrator does NOT loop indefinitely; after 1 fix-and-retry attempt at the same gate, it halts with `BLOCKED` and asks the human.

## Stop conditions

- Any cycle's stop condition fires.
- A hard gate failure that the orchestrator cannot resolve autonomously (e.g., merge conflict, missing credential).
- `cycle-acceptance` returns `ACCEPTED` or `ACCEPTED_WITH_CAVEATS` — the milestone is done and its checkbox flipped.
- `cycle-acceptance` returns `REJECTED` or `NOT_VALIDATED` — halt and surface. The release stands; the milestone does not.

## Scheduling many items at once

This cycle chains its phases for ONE item. `/pipeline` sits above it and schedules
several, one stage each, with a git worktree per lane —
[`skills/_kit-rules/parallelism-shapes.md`](parallelism-shapes.md) names the two shapes and
why this kit had only one of them.

Every gate here still applies per item, unchanged. `/pipeline` decides WHICH item
enters WHICH stage and WHEN; it never decides whether a stage passed, and a
scheduler that could overrule a verdict would be a way around this cycle rather
than a way to run more of it.

The alignment halt above is the clearest case. It stops everything today. Under
`/pipeline` it stops one item while the others advance, which turns the
operator's review from an interruption into a batch — and is the strongest
argument for the shape rather than an obstacle to it.

## Anti-patterns

- Running `/idea-to-release` on a topic with unclear requirements. Garbage in, garbage out.
- Ignoring the confidence gates ("just proceed anyway"). The gates exist to catch divergence early.
- Mixing manual and idea-to-release invocations on the same slug — they share state and will conflict.

## When manual cycles are preferred

For most features, running cycles manually with human review between them produces better output than autonomous chaining. Reserve `/idea-to-release` for topics where the orchestration overhead actually pays for itself.

## Cross-references

- Schema for cycle rules: `rules/cycle-rule-schema.md`
- Orchestrator skill: `skills/idea-to-release/SKILL.md`
- Upstream macro super-loop: `rules/cycle-maintenance.md` — selects the next `B-NNN` item and delegates one full `cycle-idea-to-release` run per item
- Chained cycles: `rules/cycle-discover.md`, `rules/cycle-plan.md`, `rules/cycle-implement.md`, `rules/cycle-code-quality.md`, `rules/cycle-review.md`, `rules/cycle-release.md`, `rules/cycle-acceptance.md`
- Conventions: `rules/loop-engine-convention.md`
