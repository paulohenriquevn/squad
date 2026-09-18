---
name: idea-to-release
version: 0.1.0
requires: [discover-plan, discover-edge-cases, discover-plan-confidence, discover-execute, discover-confidence, discover-improve, plan-write, plan-edge-cases, deps-audit, plan-confidence, plan-improve, implement, code-quality, review, release, acceptance]
description: End-to-end autonomous orchestrator for cycle-discover + cycle-plan + cycle-implement + cycle-code-quality + cycle-review + cycle-release + cycle-acceptance. Single entry-point chains the whole pipeline from idea to a released, accepted milestone, merge included — pausing only where a gate did not pass or branch protection requires a reviewer. Default is full-pipeline; --plan-only retains the legacy discover+plan behavior. Depth (none/light/full) is derived deterministically from a confidence score against repo state — no interactive prompts. MUST-FIX items from /plan-edge-cases are auto-injected into the plan before /plan-confidence re-scores. Inspired by planning-with-files v2.43.0 autonomy + composes Claude Code primitives (/plan-goal, /plan-loop) absorbed 2026-05-26.
user-invocable: true
allowed-tools: Read Write Edit Bash Glob Grep Skill
argument-hint: "[M<N> | B-NNN | {topic-slug}] [--plan-only] [--depth=none|light|full] [--no-release] [--bump=patch|minor|major]"
---

# `/idea-to-release` — Autonomous cycle orchestrator (full pipeline)

End-to-end autonomous orchestration of the 6-cycle pipeline: `cycle-discover` → `cycle-plan` → `cycle-implement` → `cycle-code-quality` → `cycle-review` → `cycle-release`. Replaces the 9+ slash manual sequence with a single invocation that:

1. **Assesses confidence** deterministically against repo state — signals about OUR system: patterns skills, ADRs, ROADMAP/CLAUDE.md, completed plans, tool study-material, user context. Peer projects under `study-material/` are **reported and score zero**: prior art cannot buy past the measurement, because a peer project cannot tell you what is true of your system (`README.md` § Prior art can never be evidence).
2. **Derives depth** from the confidence band (no interactive prompts — overridable via CLI flag).
3. **Chains skills autonomously** through every cycle, gating each transition on the downstream cycle's pre-conditions.
4. **Auto-injects MUST-FIX items** from `/plan-edge-cases` into the plan before `/plan-confidence` re-scores — eliminating the manual "human absorbs MUST FIX" step.
5. **Pauses only where a person is genuinely required** — a gate that did not pass, or branch protection demanding a reviewer the system cannot be (`rules/autonomy-envelope.md` floor 2).

## When to invoke

- User wants to take a feature from idea to release PR without invoking the pipeline cycles manually.
- User wants a confidence-checked plan-only mode for incremental work (`--plan-only`).
- User wants the discover phase auto-triggered when prior art is thin.

Do NOT invoke when:

- Plan already exists and just needs `/implement` — invoke `/implement` directly.
- Current branch is not `workspace` — switch to `workspace` first (`git switch workspace`). `develop` integrates and `main` is release-only per Unbreakable Rule 4.
- Context is < 50 chars AND no related artifacts exist in repo — orchestrator will refuse (LOW confidence).

## Argument parsing

```
/idea-to-release                                   # ROADMAP-DRIVEN: read ROADMAP.md, pick next eligible milestone
/idea-to-release M<N>                              # ROADMAP-DRIVEN: target specific milestone (M0..M8)
/idea-to-release {topic-slug}                      # AD-HOC: full pipeline with a free-form slug (no roadmap link)
/idea-to-release {topic-slug} --plan-only          # legacy: stop after plan; user runs /implement manually
/idea-to-release {topic-slug} --depth=none         # skip discover; depth is auto-derived from confidence band otherwise
/idea-to-release {topic-slug} --depth=light
/idea-to-release {topic-slug} --depth=full
/idea-to-release {topic-slug} --no-release         # full pipeline but stop after /review; do not open release PR
/idea-to-release {topic-slug} --bump=patch|minor|major  # forwarded to /release (otherwise auto-derived from CHANGELOG)
/idea-to-release {topic-slug} --force-override     # bypass refusal even at LOW confidence
```

**Slug resolution order:**

1. If no arg AND `ROADMAP.md` exists → roadmap-driven mode: select next eligible milestone (see Step 0).
2. If arg matches `^M[0-8]$` AND `ROADMAP.md` exists → roadmap-driven mode targeting that milestone.
3. If arg matches `^B-\d{3,}$` → backlog-driven mode: read that item from `BACKLOG.md` and use its statement + Definition of Done as the topic. This is the form `cycle-maintenance` delegates.
4. Otherwise → ad-hoc mode with the arg as free-form slug. Emit `INFO ad-hoc: no milestone_id will be persisted; the chain ends at RELEASED with no acceptance phase`.

If no arg AND `ROADMAP.md` is MISSING → refuse with `BLOCKED roadmap-required: ROADMAP.md is hand-authored — no skill generates it (see rules/cycle-acceptance.md § The ROADMAP.md contract). Invoke /idea-to-release B-NNN for backlog work, or /idea-to-release {topic-slug} for ad-hoc work`.

## Process

### Step 0 — Select milestone (roadmap-driven mode only)

Skip this step in ad-hoc mode.

```bash
# 0.1  Pick target milestone
if [ -z "$ARG" ] || [[ "$ARG" =~ ^M[0-8]$ ]]; then
  TARGET_MILESTONE=$(python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/idea-to-release/scripts/select_next_milestone.py" \
    --roadmap ROADMAP.md \
    ${ARG:+--prefer "$ARG"} \
    --json)
fi
```

`select_next_milestone.py` returns one of:

- `{"milestone_id": "M<N>", "name": "...", "objective": "...", "dod": [...], "depends_on": ["M<K>", ...]}` — picked eligible milestone (lowest ID with all dependencies `[x]`).
- `{"verdict": "ROADMAP_COMPLETE"}` — every milestone is `[x]`. Refuse to start a new cycle; surface to human: "ROADMAP delivered. Declare V2 or stop."
- `{"verdict": "ROADMAP_BLOCKED", "wall": [...]}` — `[ ]` milestones remain but each one's dependencies are still `[ ]`. Surface the dependency wall.
- `{"verdict": "PREFER_NOT_ELIGIBLE", "reason": "..."}` — user passed `M<N>` but `M<N>` is not eligible (already `[x]` OR dependencies not satisfied). Refuse with the reason.

Outputs from this step feed Step 2 (derive depth) and Step 3 (chain execution): `slug` is derived from the milestone name (kebab-case), and the milestone metadata is written into the plan frontmatter in Phase P.

### Step 1 — Assess confidence (deterministic, ~0 LLM tokens)

Run:

```bash
python3 .claude/skills/idea-to-release/scripts/assess_confidence.py {topic-slug} \
  --context-length={len(user_provided_context_in_chars)} --json
```

Parse JSON output. Note `score`, `verdict`, `recommended_depth`, `signals`.

### Step 2 — Derive depth deterministically (no interactive prompts)

Depth is now derived from the confidence band, NOT asked. Eliminates one `AskUserQuestion` per invocation and makes `/idea-to-release` resumable from any context.

| Confidence band | Auto-derived depth | Note |
|---|---|---|
| `HIGH` (≥ 95) | `none` | Skip discover; user context is already 95% confident. |
| `MED-HIGH` (70-94) | `light` | 2-3 discover questions; ≤ 60min budget. |
| `MED-LOW` (30-69) | `full` | Standard discover-plan defaults (5-10 questions). Soft warning that cap may land at SHIPPABLE_WITH_CAVEATS. |
| `LOW` (< 30) | (refused) | **Refuse** with suggested next actions, UNLESS `--force-override` flag present. If forced, proceed with `full` + log "OVERRIDE: user proceeded against low-confidence recommendation" in the eventual plan's `## Accepted Risks` section. |

CLI `--depth=` flag overrides the auto-derivation. CLI `--plan-only` clamps mode to plan-only regardless of confidence.

The deterministic derivation removes the legacy `AskUserQuestion` step. If the user disagrees with the auto-derived depth, they re-invoke with `--depth=...`.

### Step 3 — Chain execution

Based on chosen depth + mode (full-pipeline OR `--plan-only`):

#### Phase D — Discover (only if `depth != none`)

```
Skill(/discover-plan {topic-slug})
Skill(/discover-edge-cases {topic-slug})
Skill(/discover-plan-confidence {topic-slug})   # plan-gate — INVALID returns to /discover-plan
Skill(/discover-execute {topic-slug})       # ralph-loop halt-loop
Skill(/discover-confidence {topic-slug})
# If verdict < SHIPPABLE_WITH_CAVEATS:
Skill(/discover-improve {topic-slug})       # ralph-loop halt-loop
Skill(/discover-confidence {topic-slug})    # re-score
```

`/discover-plan-confidence` is **not optional**. It is phase 3 of `cycle-discover` and the gate that
refuses a fabricated target or an empty falsification criterion *before* a measurement runs on it —
`/discover-execute` declares it as its `requires` for exactly that reason. Skipping it lets the
chain measure against a plan nothing validated, and the result arrives looking clean.

If `/discover-plan-confidence` returns `INVALID` → return to `/discover-plan` for a rewrite; do NOT
proceed to `/discover-execute`.

For `light` depth: instruct `/discover-plan` to target 2-3 questions per project (narrower scope), so the discovery loop converges on fewer questions.

For `full` depth: standard `/discover-plan` defaults (5-10 questions per `cycle-discover.md v1.1`).

If `/discover-confidence` after improve still < SHIPPABLE_WITH_CAVEATS → halt with honest report; do NOT proceed to plan phase.

#### Phase P — Plan (always)

**Phase 0 of `cycle-plan` runs FIRST, and it is not optional for a backlog item.**
This chain used to go straight from discover to `/plan-write`, which could not
work: `check_alignment_gate.py` hard-caps a plan citing a `B-NNN` with no
alignment brief at 49, so `/plan-confidence` returned `INVALID` for every backlog
item and `/plan-improve` was handed a defect it cannot fix — the missing artifact
is not in the plan. The chain did not halt at the gate, it died past it with a
reason that pointed at the wrong file.

```
Skill(/plan-alignment {topic-slug})          # cycle-plan phase 0 — UNBREAKABLE for a B-NNN
     ↓ ALIGNED          → continue
     ↓ AWAITING_REVIEW  → see below; unattended runs sign with the judge
     ↓ BLOCKED          → the item is NOT built; close the gaps and re-score
     ↓ NEEDS_SPLIT      → split into items that each align on their own; halt this run
```

**`AWAITING_REVIEW` is where an unattended chain used to stop forever.** The brief
is complete and nobody signed it, and for a fleet session nobody is coming. The
answer is not to let the author sign — that is the one thing
`skills/_kit-rules/alignment-threshold.md` forbids — it is to hand the brief to a reviewer
that is not the author:

```
Bash(python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/plan-alignment/scripts/alignment_judge.py" \
       .squad/records/alignment/{slug}-alignment.md \
       --model "<the model doing the judging>" \
       --verdict signed --reason "<what was checked, against which evidence>")
```

Exit 0 signs and the chain continues; exit 1 is a REFUSAL, and a refusal halts
this item with the reason written into the brief. **Do not retry a refusal** — the
judge reading the same evidence twice is not a second opinion. Invoke it only when
no reviewer is coming; where a person reviews, wait for the person, because a
human signature is worth more and the record says which one it got.

```
Skill(/plan-write {topic-slug} [--milestone M<N>])   # --milestone forwarded only in roadmap-driven mode
Skill(/plan-edge-cases {topic-slug})
# AUTO-INJECT MUST-FIX items into the plan (no AskUserQuestion):
Bash(python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/idea-to-release/scripts/inject_must_fix.py" \
       --plan .squad/records/plans/{slug}-plan.md \
       --edge-cases .squad/records/reviews/{slug}-edge-cases-*.md)
# INJECT milestone_id into plan frontmatter (roadmap-driven mode only):
Bash(python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/idea-to-release/scripts/inject_milestone_id.py" \
       --plan .squad/records/plans/{slug}-plan.md \
       --milestone-id M<N>)
Skill(/deps-audit {topic-slug})
Skill(/plan-confidence {topic-slug})
# If verdict < SHIPPABLE:
Skill(/plan-improve {topic-slug})           # ralph-loop, max 10 iterations
Skill(/plan-confidence {topic-slug})         # re-score
```

`inject_must_fix.py` parses the `## MUST FIX` section of the edge-case report and appends each item as a sub-task (or ADR-deferred note) into the plan. The user does NOT have to absorb them manually. `/plan-confidence` is re-run after injection to validate the augmented plan.

`inject_milestone_id.py` writes the `milestone_id: M<N>` field into the plan's YAML frontmatter (the field `cycle-acceptance`'s flip phase reads — consumed by `skills/release/scripts/flip_milestone_checkbox.py`, which is housed in the release slice but invoked only from acceptance). In ad-hoc mode this script is skipped — the plan frontmatter carries no `milestone_id`, so the chain ends at `RELEASED` and no acceptance phase runs.

#### Phase A — Attest (always, post-plan)

```
Bash(mechanisms/cycle/attest_plan.sh {topic-slug})
```

Locks the SHA256 so UserPromptSubmit hook can validate.

#### Phase I — Implement (full-pipeline only; SKIPPED when `--plan-only`)

```
Skill(/implement {topic-slug})              # ralph-loop halt-loop until IMPLEMENTATION_COMPLETE
```

The `/implement` skill itself runs the consolidated validation gate at Step 5 — `run_validation.py` invokes `/code-quality` internally via `cq_invoke` (per ADR 0002) — and, when Step 5 returns `FAIL`, drives a mandatory fix-loop at Step 5.5 with promise `VALIDATION_GATE_PASSED` (see `skills/implement/SKILL.md`). A separate orchestrator call is not needed. After `/implement` returns, branch on the final reported state:

- Step 4 promise = `IMPLEMENTATION_COMPLETE` (no BLOCKED) AND Step 5/5.5 promise = `VALIDATION_GATE_PASSED` (no BLOCKED) AND final code-quality verdict ∈ {`PASS`, `PASS_WITH_CAVEATS`} → proceed to Phase R.
- Either loop emitted a BLOCKED report OR final code-quality verdict ∈ {`FAIL_SOFT`, `FAIL_HARD`, `INVALID`} → halt with `BLOCKED` and surface findings. `/review` and `/release` MUST NOT run.

#### Phase R — Review (full-pipeline only; SKIPPED when `--plan-only`)

```
Skill(/review {topic-slug})
```

- review verdict = `READY_TO_MERGE` → proceed to Phase Rel (unless `--no-release`).
- review verdict = `READY_TO_MERGE_WITH_FOLLOWUPS` → proceed to Phase Rel, and carry the registered followups into the release PR description. The verdict already proves every HIGH is owned (`consolidate_findings.py` fails closed otherwise), so re-litigating it here would only re-open a question the gate answered.
- review verdict = `NEEDS_FIXES` → loop once back to `/implement` for targeted fixes, then re-run `/review`. After 1 loop attempt, halt with `BLOCKED`.
- review verdict = `NEEDS_DEEPER` → halt; the item returns to the registry and re-enters at `/plan-write`.

#### Phase Rel — Release (full-pipeline only; SKIPPED when `--plan-only` OR `--no-release`)

```
Skill(/release [--bump={forwarded}])
```

`/release` opens a develop→main PR and merges it once the chain verifies. The orchestrator emits final verdict:

- `RELEASED` — PR was already merged when this chain ran (`/release` resumed after merge).
- `PR_OPEN_AWAITING_APPROVAL` — PR is open and the system declined to merge it because a gate did not pass. A remote that requires a human reviewer is a violated premise caught at intake by `check_merge_autonomy.py`, not a state reached here (`autonomy-envelope.md` floor 2).

### Step 4 — Deliver

Print summary:

```
=== /idea-to-release complete ===
Topic: {slug}
Mode: {full-pipeline | plan-only}
Depth chosen: {none|light|full}
Confidence at start: {score}/100 ({verdict})

Discover phase:     {SKIP | SHIPPABLE_WITH_CAVEATS {score} | SHIPPABLE {score}}
Plan phase:         {SHIPPABLE_WITH_CAVEATS {score} | SHIPPABLE {score} | NEEDS_HUMAN}
Implement phase:    {SKIP | IMPLEMENTATION_COMPLETE | BLOCKED}
Code-quality:       {SKIP | PASS | PASS_WITH_CAVEATS | FAIL_SOFT | FAIL_HARD | INVALID}
Review phase:       {SKIP | READY_TO_MERGE | NEEDS_FIXES | NEEDS_DEEPER}
Release phase:      {SKIP | RELEASED | PR_OPEN_AWAITING_APPROVAL}
Acceptance phase:   {SKIP (no milestone_id) | ACCEPTED | ACCEPTED_WITH_CAVEATS | REJECTED | NOT_VALIDATED}

Final plan: .squad/records/plans/{slug}-plan.md
Implementation: .squad/records/implementations/{slug}-implementation.md
Code-quality audit: .squad/records/audits/{slug}-code-quality-*.md
Review: .squad/records/reviews/{slug}-review-*.md
Release: .squad/records/releases/v{version}-release.md (if released)
Acceptance: .squad/records/acceptance/{milestone-id}-acceptance-*.md (if a milestone was accepted)
Attestation hash: {sha256}

Next step:
  - plan-only       → /implement {slug} when ready
  - full + no-release → manual /release when ready
  - PR_OPEN_AWAITING_APPROVAL → read which gate did not pass; the PR merges once it does
  - RELEASED + milestone_id   → /acceptance {milestone-id} (the checkbox flips there)
  - RELEASED, no milestone_id → start a new cycle
  - ACCEPTED*       → milestone closed; start a new cycle
  - REJECTED | NOT_VALIDATED  → the release stands, the milestone does not; fix and re-accept
```

If any phase blocked → honest report listing what blocked, and the disposition `halt_disposition.py` gave the item.

## Hard gates (cannot proceed)

1. **Branch != `workspace`** → refuse; require working on `workspace` (Unbreakable Rule 4 — `develop` integrates, `main` is release-only).
2. **Uncommitted changes from prior cycle** → refuse; require git status clean OR explicit `--allow-dirty-tree`.
3. **Confidence < 30 without `--force-override`** → refuse with suggested next actions.
4. **`/discover-confidence` final verdict INVALID after improve** → halt; surface blockers; do NOT proceed to plan.
5. **`/plan-confidence` final verdict INVALID after improve** → halt; surface gaps; do NOT deliver as "ready".
6. **`/code-quality` returns FAIL_HARD or INVALID** → halt; do NOT proceed to `/review`. Loop back to `/implement` once; if still failing, return the item to the registry with the gate named as its cause (`halt_disposition.py`).
7. **`/review` returns NEEDS_DEEPER** → halt; the item returns to the registry, and re-scoping is the next pass's work rather than a person's.
8. **Merging a PR whose chain did not pass** → forbidden. `/release` owns the merge and verifies the verdicts first; the orchestrator never merges on its own, and never with `--admin`.

## Soft gates (proceed with warning)

1. **Cap likely SHIPPABLE_WITH_CAVEATS** at depth=none with confidence < 70 → warn but proceed.
2. **Override of recommended depth via `--depth=`** (user picked `none` when system derived `full`) → proceed; add `## Accepted Risks` entry to plan.
3. **`/code-quality` returns PASS_WITH_CAVEATS** → proceed; surface caveats in the final summary.
4. **`/review` returns NEEDS_FIXES** → ONE retry: loop back to `/implement` for targeted fixes, re-run `/review`. If still NEEDS_FIXES, halt with `BLOCKED`.

## Anti-patterns

1. **NEVER fabricate confidence signals.** The script is deterministic; output is the truth.
2. **NEVER skip /plan-edge-cases, /deps-audit, or /code-quality even on HIGH confidence.** Those gates are cheap and catch issues unit tests miss.
3. **NEVER auto-commit produced plan.** Delivery is the file; user decides when to commit.
4. **NEVER claim SHIPPABLE if plan-confidence returned WITH_CAVEATS** — honesty per Unbreakable Rule 3.
5. **NEVER proceed past INVALID verdict** — that's an explicit fail-closed.
6. **NEVER ask the user between phases.** Depth is derived; MUST-FIX is injected; gates pause only on `BLOCKED`. Interactive prompts during the chain defeat the orchestrator's purpose.
7. **NEVER merge past a gate.** `/release` merges only a PR whose chain passed; re-running a gate until it goes green, or reaching for `--admin` when branch protection refuses, are the same violation of envelope floor 3.

## Cycle contract

This skill is `phase 0` of the super-cycle that orchestrates `cycle-discover` + `cycle-plan` + `cycle-implement` + `cycle-code-quality` + `cycle-review` + `cycle-release`. The cycle rule SoT is `rules/cycle-idea-to-release.md`. Hard gates + soft gates + anti-patterns live there.

## Related

- `rules/cycle-maintenance.md` — macro super-loop that delegates one `cycle-idea-to-release` run per milestone
- `rules/cycle-idea-to-release.md` — cycle SoT
- `rules/cycle-discover.md` — discover sub-cycle
- `rules/cycle-plan.md` — plan sub-cycle
- `rules/cycle-implement.md` — implement sub-cycle
- `rules/cycle-code-quality.md` — code-quality sub-cycle
- `rules/cycle-review.md` — review sub-cycle
- `rules/cycle-release.md` — release sub-cycle (cuts the tag; does NOT flip the ROADMAP.md checkbox)
- `rules/cycle-acceptance.md` — acceptance sub-cycle (exercises the RELEASED delivery and owns the checkbox flip)
- `commands/plan-goal.md` + `plan-loop.md` — Claude Code primitive composition (alternative autonomy mechanism)
- `mechanisms/cycle/attest_plan.sh` — attestation post-plan
- `skills/idea-to-release/scripts/select_next_milestone.py` — Step 0 milestone selector (roadmap-driven mode)
- `skills/idea-to-release/scripts/inject_milestone_id.py` — Phase P metadata injector
- `skills/idea-to-release/scripts/inject_must_fix.py` — auto-absorption of MUST-FIX items
- Inspired by `planning-with-files` v2.43.0 (MIT, OthmanAdi) — autonomous file-based planning pattern, absorbed 2026-05-26
