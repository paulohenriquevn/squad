---
name: review
version: 0.1.0
requires: [code-quality]
description: Most rigorous gate of the ecosystem. Validates quality gates + line-by-line plan vs implementation + 100% integration + integration test depth + edge-case coverage. Before starting, generates specialized review agents for the plan's domain (architecture, tests, wiring, cross-validation, domain-specific) and spawns them in parallel. Single entry-point for cycle-review. Use after /implement passed on `workspace` and recent commits are ready to be audited (typically before a release cut).
user-invocable: true
allowed-tools: Read Glob Grep Bash Write Edit Agent Skill
argument-hint: "{plan-slug}"
---

# Review — The Most Rigorous Gate

Single entry-point for [`cycle-review`](../../rules/cycle-review.md). The most rigorous gate of the ecosystem. Before merge, this skill:

1. **Generates specialized review agents** tailored to the plan's domain
2. **Spawns them in parallel** to review architecture, tests, wiring, cross-validation, and domain-specific concerns
3. **Validates quality gates** (test/typecheck/lint/coverage) deterministically
4. **Cross-validates line-by-line** plan vs implementation via dedicated Agent task (semantic match, not regex)
5. **Analyzes edge-case coverage** of integration tests against scenarios declared in the plan
6. **Consolidates findings** into a severity-classified report (BLOCKER/HIGH/MEDIUM/LOW/INFO — aligned with `rules/cycle-review.md`)
7. **HALTS on any BLOCKER** — merge cannot proceed until resolved

## Cycle contract

This skill is **the only phase** of [`cycle-review`](../../rules/cycle-review.md). The cycle rule is the **source of truth** for: pre-conditions, hard gates (BLOCKER never merges; NEEDS_DEEPER returns to /plan-write for re-scoping), soft gates, stop conditions, anti-patterns (never approve unresolved BLOCKER, never fabricate findings, never merge — that belongs to `/release`), rollback (review-report only — never code).

**Read `cycle-review.md` before invoking this skill.** This SKILL.md retains phase-specific detail (domain detection, agent generation, consolidation rubric).

## When to Trigger

User explicitly invokes `/review {plan-slug}` when:

- Recent commits on `workspace` passed `/implement` validation. PASS is the canonical state; PARTIAL with documented SKIPs — a language absent from the repository, a coverage command that does not exist — is acceptable, and `PARTIAL` sits in the `caveats` band precisely because the caveat travels with the result. What is never acceptable is a SKIP that names a project phase it did not observe.
- All tests are green on the branch
- The implementation plan at `plans/{slug}-plan.md` is the canonical contract (un-revised since /implement)
- PR is drafted OR ready to be drafted

Refuse to start when:

- `workspace` has uncommitted changes
- `/implement` validation FAILed and was not addressed
- `/code-quality` audit is missing OR its verdict is `FAIL_SOFT` / `FAIL_HARD` / `INVALID` (per `rules/cycle-code-quality.md`)
- Tests are red
- Plan has been revised post-implementation (the plan must be the ground truth for review)

## The 5 specialized agents (generated dynamically)

Before review begins, `scripts/spawn_reviewers.py` generates N agent definition files at `.squad/records/reviews/review-{slug}-{date}/`. These are PERSISTENT (audit trail in git) and each contains a focused system prompt. The script reads templates `agent-{role}-reviewer.md` and writes them as `{role}.md` (without the `agent-` prefix or `-reviewer` suffix) into the run directory:

| Role key | Output filename | Always generated? | What it reviews |
|---|---|---|---|
| **architecture** | `architecture.md` | Yes (baseline) | SOLID compliance per task, DIP boundary violations, design pattern misuse, hierarchical coupling |
| **tests** | `tests.md` | Yes (baseline) | Integration test depth, AAA/Given-When-Then format, fixture quality, missing scenarios from plan's TDD section |
| **wiring** | `wiring.md` | Yes (baseline) | Triad re-validation (caller + integration test + runtime metric) in DEPTH; integration of new code with existing flows; dead exports |
| **cross-validation** | `cross-validation.md` | Yes (baseline) | Line-by-line plan vs commits: every plan task → which commits implement it → was Acceptance Criteria met → was DoD satisfied |
| **domain-{X}** | `domain-{X}.md` | 1-3 dynamic | Domain-specific: memory layer patterns (Project A-shape pipeline integrity), pgvector schema compliance, auth flows, frontend a11y, etc. — depends on `detect_domain.py` output |

Total: 4 baseline + 1-3 domain-specific = 5-7 agents per `/review` invocation.

## Workflow

### Step 1 — Pre-condition validation (refuse if any fails)

```bash
# Plan exists and was not revised post-implementation
test -f .claude/records/plans/{slug}-plan.md
# Branch state clean (no uncommitted changes)
[ -z "$(git status --porcelain)" ]
# On workspace (NEVER on develop/main — review audits work before promotion)
[ "$(git branch --show-current)" = "workspace" ]
# /implement validation passed (or PARTIAL with acceptable SKIPs)
test -f .claude/records/reviews/{slug}-implement-validate-*.md
# /code-quality audit exists AND admits /review. Do not trust `test -f`: it does
# not read the verdict, and the per-soft-cap ADR requirement is not verifiable by
# eye. The script below is the same one `consolidate_findings.py` injects into the
# verdict — running it here only anticipates the answer, never replaces it.
python3 .claude/skills/review/scripts/check_upstream_gate.py {slug} --project-root .
grep -qE '"verdict":[[:space:]]*"(PASS|PASS_WITH_CAVEATS)"' .claude/records/audits/{slug}-code-quality-*.md \
  || (echo "Refuse: /code-quality verdict is not PASS/PASS_WITH_CAVEATS. Loop back to /implement." && exit 1)
# Tests green on the branch
# Whatever this project runs — `go test ./...`, `pytest`, `cargo test`, `npm test`.
# The validation gate runs every language whose manifest is at the root; naming
# only npm here read a Go workspace as having no tests to run.
npm test  # or the project's equivalent
```

If any check fails, refuse with the specific missing piece surfaced honestly. The `/code-quality` gate is mandatory — `/review` refuses to start when the audit is missing or its verdict is below `PASS_WITH_CAVEATS`.

### Step 2 — Domain detection

```bash
python3 .claude/skills/review/scripts/detect_domain.py \
  --plan .claude/records/plans/{slug}-plan.md \
  --diff-base main
```

Output: JSON with detected domains + confidence per domain.

```json
{
  "primary_domain": "memory-layer",
  "secondary_domains": ["pgvector-schema", "llm-extraction"],
  "confidence": {"memory-layer": 0.92, "pgvector-schema": 0.78, "llm-extraction": 0.65},
  "domain_keywords_matched": ["memory store", "embedding", "Postgres", "pgvector", "remember"]
}
```

### Step 2b — Independent auditors (selected from Step 2, never chosen here)

The agents in Step 3 are yours, with ad-hoc prompts. These are not: the `loop-*`
plugins audit the same domains against versioned catalogs that reject an unregistered
finding id at the database boundary, measure complexity with real tools, and treat a
run that found nothing as a hard block rather than a success.

**You do not pick which ones run.** The domains Step 2 derived select them, and you may
only WIDEN that — the same rule that forbids an author sitting on the panel judging
their own document. Choosing a docs auditor for a concurrency change returns a clean
report that honestly examined nothing that mattered, and an independent report about
the wrong thing reads as coverage.

```bash
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/mechanisms/cycle/select_auditors.py" \
  --slug {slug} --domains "<primary,secondary from Step 2>" --diff-base main --write
```

Name the change the way it is actually named: `--diff-base <ref>`, `--pr <n>` or
`--commits <a>..<b>`. Exactly one — naming two is refused, because which would win is
undefined in the plugins. Omit all three only when you mean a whole-tree audit, and the
assignment will say so in writing.

- **Exit 3** — a required plugin is not installed here. That is a coverage gap and an
  `access` impediment, not a defect in the code and not a clean review. It becomes a
  BLOCKER finding in Step 4 with its own remediation; do not work around it.
- **`none_declared`** — this project requires no independent audit. Nothing to run.

Run each command the assignment prints, exactly as printed. The `--output-dir` is where
Step 4 looks, and the `--diff-base` is what keeps the audit about this change; each
plugin applies its own declared `diff_mode` to that base.

**Do not paraphrase an auditor's findings into your own.** They travel as that
plugin's report, with its `## Verdict` quoted and its `## What Was NOT Analyzed`
carried — that section is the only thing stopping partial coverage from reading as
complete, and the seam between two honest halves is exactly where it gets dropped.

`consolidate_findings.py` verifies in Step 4 that every required audit produced a
report its own plugin accepts. A required audit that left no report did not pass — it
did not run.

### Step 3 — Spawn specialized agents (parallel)

```bash
python3 .claude/skills/review/scripts/spawn_reviewers.py \
  --plan .claude/records/plans/{slug}-plan.md \
  --slug {slug} \
  --primary-domain memory-layer \
  --secondary-domains pgvector-schema,llm-extraction \
  --output-dir .squad/records/reviews/review-{slug}-{YYYY-MM-DD}/
```

Both `--slug` and `--primary-domain` are required. `--date` defaults to today UTC; `--diff-base` defaults to `main`.

The script:
1. Reads templates at `templates/agent-*.md`
2. Substitutes `{SLUG}`, `{DATE}`, `{PLAN_PATH}`, `{DIFF_BASE}`, `{DOMAIN}`, `{SECONDARY_DOMAINS}`
3. Writes 5-7 agent definition files (each is a valid Claude Code agent with frontmatter + system prompt)

After files are written, **invoke each agent in parallel via the Agent tool**. The output directory contains one `.md` file per role: `architecture.md`, `tests.md`, `wiring.md`, `cross-validation.md`, plus 1-3 `domain-{X}.md`. For each file:

```
Read the agent file content. Invoke:
Agent(
  subagent_type="general-purpose",
  description=f"Review-{role}",
  isolation="worktree",
  prompt=<full agent .md content as system prompt + "Run your review now. Output structured findings.">
)
```

**`isolation="worktree"` is not optional.** Without it every reviewer reads and
writes the same working tree, and each one's scratch files become the others'
evidence. Measured on the B-025 run, and recorded in the comment above
`capture_tree_state`: six agents against one tree, `usage-panel.tsx` found
carrying a mutation marker mid-review, probe files at the repo root, and the
architecture reviewer filing `reportGuardFailure has zero production call sites`
against a symbol called at `usage-panel.tsx:115` and `:147`. **Three of six
reviewers happened to notice the tree was dirty** and re-derived their citations —
that correctness depended on noticing is the defect, not the dirt.

The tree-state detector stays. It is not made redundant by the isolation: it is
what proves the isolation is still in force, and isolation that silently stops
working looks exactly like isolation that works.

Each agent runs its review independently and returns findings in a structured format (see "Findings format" below). Skill collects all findings.

### Step 4 — Consolidate findings

```bash
python3 .claude/skills/review/scripts/consolidate_findings.py \
  --findings-dir .squad/records/reviews/review-{slug}-{date}/findings/ \
  --output .claude/records/reviews/{slug}-review-{date}.md \
  --plan .claude/records/plans/{slug}-plan.md
```

The script:
1. Reads each agent's findings (saved during Step 3)
2. Deduplicates findings that multiple agents flagged
3. Classifies severity: BLOCKER / HIGH / MEDIUM / LOW / INFO (per `rules/cycle-review.md`)
4. Cross-references with plan's Acceptance Criteria and Global DoD
5. Emits consolidated report

### Step 5 — Re-validate quality gates

Run validation gates from `/implement`'s validation report, but with TIGHTER thresholds:

```bash
python3 .claude/skills/implement/scripts/run_validation.py {slug}  # already exists
```

Plus, `/review` adds:
- Coverage on critical paths MUST be 100% (not just 90% like /implement's permissive default)
- Lint warnings: 0 (not "fewer than before")
- Test runtime regression check (if previous run available)

### Step 6 — Edge-case coverage analysis

```bash
python3 .claude/skills/review/scripts/edge_case_coverage.py \
  --plan .claude/records/plans/{slug}-plan.md \
  --tests-dir tests/
```

The script:
1. Extracts every Edge Case mentioned in the plan (Deep Dives + Acceptance Criteria sections)
2. Searches tests/ for assertions exercising each edge case (keyword match + AST pattern via ast-grep)
3. Reports: covered / partial / missing edge cases

### Step 7 — HALT-if-BLOCKER decision

After all findings consolidate, decide (per `rules/cycle-review.md § Verdicts`):

- Any BLOCKER → **HALT**. Merge cannot proceed. Loop back to `/implement` to fix.
- More than 2 HIGH → `READY_TO_MERGE_WITH_FOLLOWUPS` **only when every HIGH is a registered followup** — named by id under the plan's `## Followups` section (that is what `--plan` is read for) or carrying an issue reference `#NNN` in `recommended_action`. Any unregistered HIGH → **HALT** with `NEEDS_FIXES`. A rationale written in the report's prose is not registration: a caveat nobody owns is a defect with better manners. Up to 2 HIGH with documented mitigation MAY emit `READY_TO_MERGE`.
- Any MEDIUM → surface to human; accept WITH_CAVEATS in PR description OR fix.
- LOW/INFO → log; merge can proceed.

### Step 8 — Final report

Write consolidated review report at:

```
.claude/records/reviews/{slug}-review-{date}.md
```

Report format (see `consolidate_findings.py`):

```markdown
# Review: {slug}

**Date:** {date}
**Reviewers (spawned agents):** 5-7 (list)
**Findings:** N total (BLOCKER: N, HIGH: N, MEDIUM: N, LOW: N, INFO: N)
**Verdict:** READY_TO_MERGE / READY_TO_MERGE_WITH_FOLLOWUPS / NEEDS_FIXES / NEEDS_DEEPER

## BLOCKER findings (must fix before merge)
### F1: {description}
- Severity: BLOCKER
- Found by: {agent role}
- File: src/path/to/file.ts:42
- Plan reference: T1.2 Acceptance Criteria item 3
- Recommended action: {specific}

## HIGH findings
...

## MEDIUM findings
...

## Edge-case coverage report
- Covered: N/M
- Missing: [{edge case 1}, {edge case 2}]

## Cross-validation summary
- Plan tasks: N
- Fully implemented: N
- Partially: N
- Missing: N
- Diverged: N

## Quality gates summary
- npm test: PASS
- npm run typecheck: PASS
- npm run lint: PASS (0 warnings)
- Coverage on critical paths: 100% / 92%
- Wiring triad: 12/12 symbols pillar (a) PASS; 11/12 pillar (b); 8/12 pillar (c) observed

## Spawned agents (audit trail)
- .squad/records/reviews/review-{slug}-{date}/architecture.md
- .squad/records/reviews/review-{slug}-{date}/tests.md
- .squad/records/reviews/review-{slug}-{date}/wiring.md
- .squad/records/reviews/review-{slug}-{date}/cross-validation.md
- .squad/records/reviews/review-{slug}-{date}/domain-memory-layer.md
- .squad/records/reviews/review-{slug}-{date}/domain-pgvector-schema.md

## Handoff decision
{READY_TO_MERGE or READY_TO_MERGE_WITH_FOLLOWUPS: open PR / NEEDS_FIXES: loop /implement / NEEDS_DEEPER: re-spawn with broader scope}
```

## Findings format (each agent emits)

Every spawned agent MUST return findings in this format:

```yaml
agent: architecture
review_target: commits on `workspace` for plan {slug}
findings:
  - id: F-arch-1
    severity: HIGH  # BLOCKER / HIGH / MEDIUM / LOW / INFO
    file: src/core/memory-store.ts
    line: 42
    plan_ref: T1.2 Acceptance Criteria item 3
    summary: src/core/ imports from src/local/ — violates DIP per architecture.md
    evidence: |
      ```ts
      import { PgvectorStore } from '../local/pgvector-store';
      ```
    recommended_action: Move PgvectorStore import to a factory module; inject via DIP boundary.
  - id: F-arch-2
    severity: INFO
    ...
```

### Closing a finding on a re-review

A re-review that verified a fix marks the finding `status: CLOSED` and **leaves
the severity alone**:

```yaml
  - id: F-dom-1
    severity: BLOCKER          # stays BLOCKER — it was one
    status: CLOSED             # what the re-review established
    file: .github/workflows/ci.yml
    summary: node -e trips SC2016 and fails workflow-lint
    evidence: |
      Re-verified against the same digest-pinned image: ACTIONLINT_EXIT=0,
      0 bytes of output. Appending a genuine SC2016 still fires, so the
      suppression is command-scoped rather than block-wide.
    recommended_action: none — fixed in <sha>
```

`consolidate_findings.py` scores the verdict from **open** findings only, so a
closed BLOCKER no longer forces `NEEDS_FIXES`. The finding stays in the report
under its own section, with its original severity and the agent that closed it:
the audit trail survives, and the verdict describes the code as it stands rather
than as it stood at the first read.

Only these three ways exist to move past a BLOCKER, and two of them are
forbidden:

| Action | Verdict | Allowed |
|---|---|---|
| Fix it, re-verify, mark `status: CLOSED` | passes | **yes** |
| Lower its severity | passes | no — demoting a failure to let it through, the first anti-pattern `rules/cycle-review.md` names |
| Delete the finding | passes | no — erases the audit trail of a real defect |

**Absence of the field keeps the old behaviour.** Every findings file written
before this omits `status`, and reinterpreting them would silently rescore every
past review.

**Why this section exists.** The mechanism shipped and the contract never
mentioned it. A consumer session hit a re-verified BLOCKER, grepped the
consolidator for `outcome` — the field name the harness's own `ReportFindings`
tool uses — found nothing, and concluded the capability was missing. It was
about to re-run four review agents at roughly 200k tokens each to work around
something that already worked. A mechanism nobody can find is worth what an
absent one is worth.

## Do not edit the tree between the spawn and the consolidation

The agents read the working tree while they run. Applying fixes during that
window means each agent reviewed a different tree, and the findings no longer
describe one state of the code.

`consolidate_findings.py` detects it — it records HEAD plus a digest of
`git status --porcelain` at spawn time, re-reads both at consolidation, and
emits `tree_contaminated` in the JSON plus a `## ⚠ Working tree contaminated
during this review` section in the report. So the run is not silently wrong.

But detection is the remedy, not the cure: the agents have already spent their
budget on a tree that moved. Measured on a real run — four reviewers, two of them
noticed independently, reported *"TREE MOVED MID-REVIEW"* and re-measured against
the new HEAD rather than inferring. That was their judgement, not the process's,
and the next set of agents may simply report against a tree nobody has any more.

Fix after the consolidation, then re-review. Marking the resulting findings
`status: CLOSED` is what makes the second pass cheap.

## Inviolable rules

- The skill NEVER modifies code on `workspace` — only writes review reports
- The skill NEVER approves a PR with unresolved BLOCKER findings — even on human override, requires explicit ADR-style dismissal IN THE REPORT
- The skill NEVER fabricates findings — if a file has no issues, the finding is "INFO: no issues found"
- The skill SHOULD cover every file in the diff (each baseline agent is briefed to enumerate touched files via the diff base). When a file is genuinely trivial — pure rename, single-line typo — the finding is "INFO: no issues found". Coverage is enforced by agent prompts today; a future `consolidate_findings.py` check may mechanically assert "every changed file appears in ≥1 finding"
- The skill NEVER reviews without the plan as ground truth — review without plan is vibes
- The skill NEVER merges. The merge belongs to `/release`, which verifies this review's verdict before performing it — a reviewer that could merge on its own verdict would be grading its own decision to proceed
- The skill NEVER reviews code modified between `/implement` validation and `/review` — if commits happened, re-run `/implement` validation
- The skill NEVER deletes the spawned agent files post-review — they are audit trail (per user decision: persist as audit)

## When to give up honestly

Per `cycle-review.md § Verdicts` — `BLOCKED` is the honest outcome here:

1. Review depth requires domain knowledge outside training (cryptography, hardware-specific, regulatory compliance) → mark BLOCKED with reason "requires human domain expert"
2. PR scope ambiguous (changes touch files unrelated to plan) → halt; surface to human
3. Agent task returns inconsistent findings 2× → escalate; consolidation cannot proceed reliably

## Related

- Cycle rule (SoT): [`cycle-review.md`](../../rules/cycle-review.md)
- Upstream cycle: [`cycle-implement.md`](../../rules/cycle-implement.md)
- Agent templates: `templates/agent-*.md`
- Orchestrator prompt: `prompts/orchestrator-prompt.md`
- Scripts: `scripts/detect_domain.py`, `scripts/spawn_reviewers.py`, `scripts/edge_case_coverage.py`, `scripts/consolidate_findings.py`
- Reuses: `.claude/skills/implement/scripts/run_validation.py` (quality gates), `.claude/skills/implement/scripts/check_wiring.py` (wiring re-validation)
- Generated audit trail: `.squad/records/reviews/review-{slug}-{date}/`
- Final reports: `.claude/records/reviews/{slug}-review-{date}.md`
- Project rules consumed: `architecture.md`, `testing.md`, `public-copy.md`, `discover-plan-golden-rule.md` and `discover-opportunity-golden-rule.md` (if the review touches discovery artifacts)

## Match to the work

This skill spawns 5-7 agents in parallel — it is the MOST RIGOROUS gate of all. Don't run `/review` for trivial changes; for small PRs, the built-in `/review` (Anthropic) is sufficient and far lighter.
