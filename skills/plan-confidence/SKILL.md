---
name: plan-confidence
version: 0.1.0
requires: [deps-audit]
description: Score a plan produced by /plan-write for structural quality (M2 deterministic check). Sibling of /discover-confidence with a plan-shape rubric. Use after /plan-edge-cases, before /implement.
user-invocable: true
allowed-tools: Read Glob Grep Bash Write
argument-hint: "{plan-slug}"
---

# Plan-Confidence — M2 Structural Scoring

Scores a plan produced by `/plan-write` against the M2 structural rubric. Deterministic. Zero LLM calls. Latency < 5s. Cost $0.

**Rubric:** `templates/rubric-v1.md` (this skill's templates dir)
**Hard caps:** see `.claude/rules/plan-confidence-golden-rule.md`
**Thresholds (versioned):** `.claude/rules/plan-confidence-thresholds.txt`

## When to Trigger

- After running `/plan-edge-cases {slug}` and incorporating MUST FIX items, BEFORE implementation.
- User explicitly invokes `/plan-confidence {plan-slug}`.

## Cycle contract

This skill is **phase 4** of [`cycle-plan`](../../rules/cycle-plan.md), after `/deps-audit` (phase 3). The cycle rule is the source of truth for chain order, hard gates, soft gates, stop conditions, anti-patterns, and rollback. Read it before invoking this skill. This SKILL.md retains phase-specific detail (the scoring rubric, hard caps, output schema, exit codes).

## Architecture compliance check (always runs)

`/plan-confidence` ALWAYS reads `.claude/rules/` (or falls back to `.claude/skills/plan-confidence/defaults/`) and verifies the plan REFERENCES the rules. The sub-report `architecture_compliance` exposes:

- `project_rules_found_count` — how many `.md` rules were detected
- `fallback_to_defaults` — true if no project rules existed (and defaults were used)
- `rules_referenced_in_plan` — which rule filenames the plan cited
- `principles_cited` — which principles (SOLID/DRY/KISS/YAGNI/...) the plan mentions
- `has_dod_quality_signal` — Global DoD mentions lint/complexity/size
- `has_size_budget_signal` — plan mentions file-size budget
- `compliance_score` — 0.0 to 1.0

If `compliance_score < 0.4` AND the plan otherwise scores ≥ 90, a soft cap fires (`soft_floor_low_architecture_compliance`, score capped at 89). Plans that don't show awareness of project rules cannot be SHIPPABLE.

## Does Not Own
**Out of scope for M2:**

- **M3 (Evidence verification via SAFE adapted to `ripgrep + tree-sitter`)** — detects citation fabrication.
- **M4 (PoLL Jury cross-family)** — Sonnet + GPT-4o-mini + Gemini Flash as judges.
- **M5 (Calibration via Semantic Entropy + P(True))** — N-sample uncertainty.
- **M6 (Evolutionary Loop)** — adaptive thresholds with human-gate.

These dimensions return empty `reasons` in M2 output. The composite formula renormalizes to active dimensions (ADR D8): in M2, `final = 0.60·Completude + 0.40·Risco-estrutural`.

## Workflow

1. **Resolve plan path.** If argument is a slug like `plan-confidence-setup`, resolve to `.claude/records/plans/{slug}-plan.md`. If argument is a path (`.md` suffix), use directly.
2. **Invoke the structural runner.** Call `python3 "$([ -d .claude/skills ] && echo .claude || echo .)/scripts/run_structural.py" <plan-path>` from the skill directory. Pass rubric path and thresholds path as arguments.
3. **Parse the JSON output.** The runner emits a JSON object matching `templates/score-report-template.md`.
4. **Render the report.** Render the JSON to the user, highlighting the top 3 contributors and detractors per dimension, with the verdict band clearly marked. If `verdict == INVALID`, display in red. If `verdict == SHIPPABLE`, display in green.

## Hard Caps (mirror plan-confidence-golden-rule.md)

A plan is INVALID and CANNOT score above 49 when any of these fire:

- **Coverage Matrix < 100%** (gaps not mapped to tasks) — capped at 49 (M2 enforced). Stable identifier: `coverage_lt_100`.
- **Fabricated citation** (file/symbol in `Evidence:` doesn't exist in repo) — capped at 49 (M3 future). Stable identifier: `fabricated_citation`.

A plan caps at 70 (SHIPPABLE_WITH_CAVEATS at most) when:

- **ADR without alternatives** listed in Rationale. Stable identifier: `adr_without_alternatives`.
- **Bug-fix task without explicit TDD** (RED-GREEN-REFACTOR block). Stable identifier: `tdd_in_bugfix`.

These caps are UNBREAKABLE. See `.claude/rules/plan-confidence-golden-rule.md` for full enforcement contract. The stable identifiers above are what appears in the JSON output's `hard_caps_triggered` list.

## Conservative Bias (fail-closed)

The system **biases toward false positives** (over-flag) rather than false negatives
(under-flag). When signals indicate risk, the system caps the verdict at
SHIPPABLE_WITH_CAVEATS (89) instead of allowing SHIPPABLE (90+):

- **High smell density** (≥30 weak-imperative/loophole/vague hits in prose) → soft cap 89.
- **High deferred ratio** (>20% of Coverage Matrix entries marked out-of-scope) → soft cap 89.

This is a deliberate engineering choice: it is much easier to recover from a
plan that was marked WITH_CAVEATS but is actually clean (loses 1 minute of
human review time) than from a plan that was marked SHIPPABLE but had real
gaps (loses days/weeks of implementation rework). Asymmetry favors RESSALVAS.

Soft caps are listed in `hard_caps_triggered` with prefix `soft_floor_`
(e.g., `soft_floor_smell_density_high`) for auditability. They do NOT
trigger `verdict == INVALID`.

## Verdict Bands (versioned in thresholds allowlist)

| Score | Verdict | Action |
|---|---|---|
| 90-100 | SHIPPABLE | Implement with confidence |
| 70-89 | SHIPPABLE_WITH_CAVEATS | List caveats, review manually |
| 50-69 | NON_SHIPPABLE | Re-run `/plan-write` + `/plan-edge-cases` |
| 0-49 | INVALID | Structural defect — re-plan |

## Convene the panel — the phase does not advance without it

`rules/review-panel.txt` gates PLAN on **2 of 3 signed approvals**, and the
reviewers are **this project's own specialist agents**, not model strings. The scorer
applies that gate by default: a document scoring 100 with no panel record is
`AWAITING_REVIEW`, never `SHIPPABLE`.

The deterministic half is a mechanism; the judgement is yours to gather, because the
question a panel answers — does the evidence that resolves actually SUPPORT the
conclusion — is exactly the one no script can ask.

1. **Assign the seats.** From the project root:

   ```bash
   python3 "$([ -d .claude/skills ] && echo .claude || echo .)/mechanisms/cycle/convene_panel.py" \
       --slug <slug> --phase plan --author <who wrote it> --write
   ```

   Exit 3 means the panel cannot convene here — a missing agent or an absent binary.
   That is an `access` impediment, **not** a rejection: return the item to the
   registry and take the next one.

2. **Invoke every assigned agent as a sub-agent**, one per seat, each judging the
   document against its own speciality. Here: `vera-technical-arbiter` on the technical shape, `nemesis-claim-auditor` on the plan's claims, and `judge-codex:plan-judge` from outside the family.

3. **Write the votes** to `.squad/records/panels/<slug>-plan.json`:

   ```bash
   ARTIFACT=<path to the document the panel judged>
   SHA=$(python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$ARTIFACT")
   ```

   ```json
   {"slug": "...", "phase": "plan", "artifact": "<path>", "artifact_sha256": "<SHA>",
    "author": "...",
    "votes": [{"reviewer": "<the assigned agent>", "model": "<what it ran on>",
                "verdict": "approve | return | abstain",
                "reason": "what was checked, against which evidence"}]}
   ```

   **`artifact_sha256` binds the votes to the text.** Without it the approval survives a
   rewrite of the thing approved, and editing the artifact after the votes land is the
   cheapest way to launder a change past a panel. The gate reports the binding as
   unverified when the field is absent — it does not silently accept it.

   A reason under 15 words is refused: a verdict with no reasoning is a tick, and a
   tick is what a panel exists to be more than.

4. **Re-run the scorer.** It now reports the panel beside the score.

**What is refused, and why each one matters.** The author on their own panel; three
votes from one model family; one reviewer voting twice; an abstention read as
agreement; a voter the assignment never named. Each is a way a panel can look
convened and be a rubber stamp — counting to two is trivial and is not the point.

`--structural-only` measures structure without the gate. It records that it did, in
the report, so the choice cannot quietly become the norm.

## Output Format

The skill produces a JSON object with these top-level keys (see `templates/score-report-template.md` for full schema):

- `plan_slug`, `plan_path`, `plan_version`
- `completeness_score`, `structural_risk_score` (0-100 each)
- `active_dimensions` — list of dimensions scored in this milestone (M2: `["completeness", "structural_risk"]`)
- `weight_normalization_factor` — ADR D8 normalization factor applied
- `hard_caps_triggered` — list of triggered caps (e.g., `["coverage_lt_100"]`)
- `final_score_after_caps` — composite after applying caps
- `verdict` — one of SHIPPABLE / SHIPPABLE_WITH_CAVEATS / NON_SHIPPABLE / INVALID
- `reasons` — dict of dimension → list of top-3 contributors and detractors (with citations)
- `sub_reports` — raw output from each checker for auditability

## Exit Codes

- `0` — SHIPPABLE or SHIPPABLE_WITH_CAVEATS (green path).
- `1` — INVALID (hard cap triggered).
- `2` — Error (plan not found, malformed rubric).
- `3` — NON_SHIPPABLE (score < 50 without hard cap; over-penalization to investigate).

## How to Read Edge Case Outputs

If a previous `/plan-edge-cases {slug}` produced MUST FIX items, the current plan should have incorporated them BEFORE invoking `/plan-confidence`. The skill does NOT cross-reference edge-case reports automatically in M2 — that's an M4 feature (jury layer).

## Related

- Golden rule: `.claude/rules/plan-confidence-golden-rule.md`
- Thresholds: `.claude/rules/plan-confidence-thresholds.txt`
- Rubric: `templates/rubric-v1.md`
- Schema: `templates/score-report.schema.json`
- Defaults (fallback when project rules missing): `defaults/`
- Sibling skill: `/discover-confidence` (same architecture, scores opportunities instead of plans)
