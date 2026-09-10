---
name: discover-confidence
version: 0.2.0
requires: [discover-execute]
description: Score an opportunity for structural quality (deterministic, zero LLM calls, under 5s). Use this after /discover-execute and before feeding anything to /plan-write, and whenever someone asks whether a finding is solid enough to act on. Verifies that every code pointer resolves AND that the cited line exists, counts runtime observations separately since they are not re-verifiable, and requires an ADR only when the change reaches beyond its own repo.
user-invocable: true
allowed-tools: Read Glob Grep Bash Write
argument-hint: "{opportunity-slug}"
---

# Discover-Confidence — M2 Structural Scoring for Opportunities

Scores an opportunity produced by `/discover-execute` against the M2 structural rubric. Deterministic. Zero LLM calls. Latency < 5s. Cost $0.

Sibling of `/plan-confidence` — same architecture (Python deterministic + soft caps + hard caps), different rubric. Plan-confidence scores **implementation plans**; discover-confidence scores **measured opportunities**.

**Rubric:** `templates/rubric-opportunity.md`
**Hard caps:** `rules/discover-opportunity-golden-rule.md`
**Thresholds (versioned):** `rules/discover-opportunity-thresholds.txt`

## When NOT to invoke

- After `/discover-execute {slug}` emitted `OPPORTUNITY_COMPLETE` (or exhausted its loop).
- After incorporating fixes from `/discover-improve`, BEFORE the opportunity feeds `/plan-write`.
- User explicitly invokes `/discover-confidence {opportunity-slug}`.

Do NOT invoke on a run that ended in `ITEM_KILLED`. A killed item produces no opportunity, and there is nothing to score — the outcome is recorded on the `B-NNN` block with its `kill_reason`.

## Cycle contract

This skill is **phase 5** of [`cycle-discover`](../../rules/cycle-discover.md). The cycle rule is the source of truth for chain order, the four modes and their evidence contracts, hard gates, stop conditions, anti-patterns and rollback. Read it before invoking this skill. This SKILL.md retains phase-specific detail (the rubric, caps, output schema, exit codes).

## What this skill checks (M2 active dimensions)

Four deterministic checkers, four dimensions:

| Dimension | Checker script | Hard cap | Weight |
|---|---|---|---|
| **corner_coverage** | `check_corner_coverage.py` | ≤49 if any of the 4 corners is empty | 0.30 |
| **evidence_pointers** | `check_evidence_pointers.py` | ≤49 if ANY code pointer fails to resolve | 0.30 |
| **opportunity_completeness** | `check_opportunity_completeness.py` | ≤70 if a mandatory section is missing | 0.25 |
| **structural_risk** (smells) | `check_spec_smells.py` | penalty only (no hard cap) | 0.15 |

Weights sum to 1.0: `final = 0.30·corner_coverage + 0.30·evidence_pointers + 0.25·opportunity_completeness + 0.15·structural_risk`. When a hard cap fires, `final_score_after_caps = min(weighted_avg, smallest_active_cap)`.

### The four corners

| Corner | Required H2 |
|---|---|
| Evidence | `## Corner 1 — Evidence` |
| Constraint Relation | `## Corner 2 — Constraint Relation` |
| Blast Radius | `## Corner 3 — Blast Radius` |
| Verification | `## Corner 4 — Verification` |

**`<!-- UNKNOWN: reason -->` populates Constraint Relation and ONLY Constraint Relation.** The constraint is a lens rather than a gate (`rules/current-constraint.md`), so `unknown` with a stated reason is a complete answer there. The marker is not honoured in the other three: an opportunity whose Evidence corner is `unknown` measured nothing, and a global escape hatch would become the cheapest way to pass every other gate.

The ancestor's `<!-- DEFERRED: ... -->` marker is **no longer honoured anywhere**. Deferring prior-art research was reasonable; deferring the measurement, the blast radius or the verification of a change to a running system is not.

### Evidence pointers — two classes, deliberately

- **Code pointers** `path/to/file.ext:LINE` — resolved against the project root. Verified only when the file exists **and** the line is within it. A pointer at line 400 of a 30-line file is evidence that moved, and it fails.
- **Runtime observations** `METHOD URL -> STATUS` — counted, never "verified". Re-running a request against a dev environment can legitimately differ; a checker claiming otherwise would assert rather than measure.

An opportunity with zero code pointers is not automatically penalised — a `live-test` finding is carried by observations. The empty-corner and mode-contract gates are what catch a genuinely evidence-free opportunity.

## Hard Caps

INVALID, cannot score above 49:

- **Empty corner** — any of the four corners missing or containing only a placeholder.
- **Fabricated evidence** — any code pointer that does not resolve (missing file, line out of range, unreadable).

Capped at 70 (SHIPPABLE_WITH_CAVEATS at most):

- **Mandatory section missing** — Header, Item, Repo, Mode, Context, Corner 1–4, Recommendation.
- **No ADR on a cross-repo change** — fires **only** when the Blast Radius corner names an ecosystem repo other than the opportunity's own. A repo-local fix carries no ADR requirement; the ancestor demanded one from every blueprint, which for maintenance work is ceremony. A change that reaches other repos decides something for their maintainers, and shipping it unrecorded is how a breaking change arrives unannounced.

These caps are UNBREAKABLE. See `rules/discover-opportunity-golden-rule.md`.

## Conservative Bias (fail-closed)

Biases toward over-flagging. When signals indicate risk, the verdict caps at 89 instead of allowing 90+:

- **High smell density** (≥20 weak-imperative / loophole / vague hits) → soft cap 89.
- **Low evidence density** (<1 pointer or observation per 200 words) → soft cap 89. An opportunity that is mostly prose is thin on measurement.

Soft caps appear in `hard_caps_triggered` with the `soft_floor_` prefix for auditability and do NOT produce `verdict == INVALID`.

## Verdict Bands

| Score | Verdict | Action |
|---|---|---|
| 90-100 | SHIPPABLE | Feed `/plan-write` |
| 70-89 | SHIPPABLE_WITH_CAVEATS | Caveats carried into the plan |
| 50-69 | NON_SHIPPABLE | Re-run `/discover-execute` with a revised measurement plan |
| 0-49 | INVALID | Structural defect — back to `/discover-plan` |

## Workflow

1. **Resolve the path.** A slug resolves to `.claude/records/discoveries/opportunities/{slug}-opportunity.md`; a `.md` path is used directly.
2. **Run the scorer.** `python3 "$([ -d .claude/skills ] && echo .claude || echo .)/scripts/run_opportunity_score.py" <opportunity-path>`.
3. **Parse the JSON**, matching `templates/score-report.schema.json`.
4. **Render the report.** Top 3 contributors and detractors per dimension, verdict band marked.

## Convene the panel — the phase does not advance without it

`rules/review-panel.txt` gates DISCOVER on **2 of 3 signed approvals**, and the
reviewers are **this project's own specialist agents**, not model strings. The scorer
applies that gate by default: a document scoring 100 with no panel record is
`AWAITING_REVIEW`, never `SHIPPABLE`.

The deterministic half is a mechanism; the judgement is yours to gather, because the
question a panel answers — does the evidence that resolves actually SUPPORT the
conclusion — is exactly the one no script can ask.

1. **Assign the seats.** From the project root:

   ```bash
   python3 "$([ -d .claude/skills ] && echo .claude || echo .)/mechanisms/cycle/convene_panel.py" \
       --slug <slug> --phase discover --author <who wrote it> --write
   ```

   Exit 3 means the panel cannot convene here — a missing agent or an absent binary.
   That is an `access` impediment, **not** a rejection: return the item to the
   registry and take the next one.

2. **Invoke every assigned agent as a sub-agent**, one per seat, each judging the
   document against its own speciality. Here: `nemesis-claim-auditor` on whether the claim is supported, `leonardo-researcher` on what the decision needed to know, and `judge-codex:discover-judge` from outside the family.

3. **Write the votes** to `records/panels/<slug>-discover.json`:

   ```bash
   ARTIFACT=<path to the document the panel judged>
   SHA=$(python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$ARTIFACT")
   ```

   ```json
   {"slug": "...", "phase": "discover", "artifact": "<path>", "artifact_sha256": "<SHA>",
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

- `opportunity_slug`, `opportunity_path`
- `corner_coverage_score`, `evidence_pointers_score`, `opportunity_completeness_score`, `structural_risk_score`
- `active_dimensions`, `weight_normalization_factor`, `weighted_avg`
- `hard_caps_triggered` — e.g. `["empty_corner_evidence"]`, `["fabricated_evidence"]`, `["no_adr_on_cross_repo_change"]`
- `final_score_after_caps`, `verdict`
- `reasons`, `sub_reports` — raw checker output for auditability

## Exit Codes

- `0` — SHIPPABLE or SHIPPABLE_WITH_CAVEATS
- `1` — INVALID (hard cap triggered)
- `2` — Error (opportunity not found, malformed rubric)
- `3` — NON_SHIPPABLE (score < 50 without a hard cap)

## Out of scope for M2

- **M3 (semantic evidence faithfulness)** — does the cited line actually contain the claimed behaviour? Today the checker proves the pointer resolves, not that it says what the opportunity claims.
- **M4 (jury cross-family)** — orthogonal LLM judges of opportunity quality.
- **M5 (calibration via semantic entropy)** — N-sample uncertainty.

The four active dimensions already sum to 1.0, so no renormalization applies. That machinery only engages once M3+ dimensions are added without rebalancing.

## Related

- Upstream: `/discover-execute` (produces the opportunity)
- Downstream: `/discover-improve` (refines low-scoring opportunities via halt-loop)
- Golden rule: `rules/discover-opportunity-golden-rule.md`
- Thresholds: `rules/discover-opportunity-thresholds.txt`
- Constraint lens: `rules/current-constraint.md`
- Rubric: `templates/rubric-opportunity.md`
- Schema: `templates/score-report.schema.json`
- Sibling: `/plan-confidence` (same architecture, scores implementation plans)
