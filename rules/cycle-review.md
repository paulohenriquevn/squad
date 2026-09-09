# Cycle: REVIEW

Source of Truth for the pre-merge review cycle.

## Purpose

Re-validate quality gates with stricter thresholds before merge. Catches issues that slipped past `/implement`.

## Pre-conditions

- Implementation output exists at `records/implementations/{slug}-implementation.md`.
- Code-quality audit exists at `records/audits/{slug}-code-quality-*.md` with verdict ∈ {`PASS`, `PASS_WITH_CAVEATS`} — or `FAIL_SOFT` accompanied by an ADR dismissing each soft cap (per `code-quality-golden-rule.md` § 1). `FAIL_HARD` and `INVALID` block this cycle.

  **Enforced, not remembered.** `skills/review/scripts/check_upstream_gate.py` reads the newest audit for the slug and emits a BLOCKER when it is missing, unreadable, `FAIL_HARD`/`INVALID`, or `FAIL_SOFT` with any soft cap that no ADR names. `consolidate_findings.py` folds those findings into the same verdict computation as every other finding, so a `/review` verdict cannot be produced without the check having run. Until 2026-08-26 this was prose plus a `test -f` in `SKILL.md`, and the ADR — the artefact that makes a soft cap dismissible — was never looked for: asserting it existed was enough. "Each soft cap" is the strict reading: with two caps and one ADR, the loose reading approves the cap nobody examined as a passenger of the one that was.
- Working branch has commits ahead of the base branch.
- No uncommitted changes (review reads a stable state).

## Chain

```
/review {slug}
     ↓ detect domain (web/CLI/infra/data) from changed files
     ↓ spawn 5-7 specialist agents in parallel
     ↓ consolidate findings by severity (BLOCKER / HIGH / MEDIUM / LOW / INFO)
     ↓ verdict
```

## Specialist agents (typical set)

| Agent | Focus |
|---|---|
| architecture-reviewer | DIP, layering, SRP at module level |
| test-auditor | Test pyramid balance, missing edge cases, flakiness signals |
| wiring-validator | Wiring triad present for every new feature |
| cross-validation | Plan claims ↔ implementation ↔ tests consistency |
| domain-specific (1-3) | Per-domain checks (e.g., SQL injection for web, IAM misconfig for infra) |

## Independent auditors — the review consumes an audit it did not produce

The specialists above are Claude sub-agents with ad-hoc prompts. Nothing behind them
refuses a finding that was never grounded: no versioned catalog to cite, no tool
measuring what the prose estimates, no store that rejects an invented id. The `loop-*`
plugins audit the same domains with instruments that refuse their own theatre — a
finding whose catalog id is not registered is rejected at the database boundary,
complexity comes from radon / lizard / gocyclo rather than from reading, and a run that
found nothing is a hard block instead of a success.

So REVIEW runs both: opinions it produces, and an audit it consumes.
[`cycle-judge-codex.md`](cycle-judge-codex.md) already made this argument for cycle
ARTIFACTS; this extends it to the CODE.

| | |
|---|---|
| Who audits what | [`rules/review-auditors.txt`](review-auditors.txt) — **the project's**, because which plugins it has and what they cost it are not the kit's business |
| Selects | [`mechanisms/cycle/select_auditors.py`](../mechanisms/cycle/select_auditors.py), from the domain [`detect_domain.py`](../skills/review/scripts/detect_domain.py) already derives |
| **Blocks** | [`mechanisms/gates/check_auditor_coverage.py`](../mechanisms/gates/check_auditor_coverage.py), entering `consolidate_findings.py` as BLOCKER findings |
| Where plugins are found | [`mechanisms/conventions/installed_plugins.py`](../mechanisms/conventions/installed_plugins.py) |

**The selection is derived, not chosen.** The reviewing agent does not pick its own
auditor — the same rule the review panel enforces when it refuses to seat an author,
because the CHOICE is already a judgement. Point a concurrency change at a docs auditor
and the report comes back clean, honestly, having examined nothing that mattered: an
independent report about the wrong thing is worse than no report, because it reads as
coverage. The agent may **widen** the selection and never narrow it, which is the
fail-safe direction [`touched_slices.py`](../mechanisms/conventions/touched_slices.py)
already takes.

**Scope is passed, and the mode is recorded.** REVIEW audits a change, so each auditor
is given the change: `--diff-base <ref>`, `--pr <n>`, or `--commits <a>..<b>` — the same
three forms the plugins accept. Naming two at once is refused, because which one wins is
undefined there and an undefined scope silently audits the wrong thing. What that does depends on the domain and the plugin declares
it: `analysis-scoped` reads only the changed files, `report-filtered` reads the whole
tree and reports only what the change touched — because reachability, duplication and
dependency cycles are properties of the whole graph, and analysing the diff alone would
make every new function look orphaned. The mode is recorded so a scoped review is never
read as a full audit. **A run with no base says, in writing, that it covered the whole
tree**; the base is never guessed.

**The report contract is the plugins', not a copy.** The coverage gate runs each
plugin's own report checker against that plugin's own schema config, from its install
path. A second copy of that contract would diverge on the day it changes, and the kit
would accept a report shape the plugin itself rejects.

**Two sections travel out of every report on purpose**: `## Verdict`, quoted rather
than re-graded, and `## What Was NOT Analyzed`, which the contract never omits and
which is the single thing stopping partial coverage from reading as complete. The seam
between two honest halves is exactly where that caveat gets dropped.

**What the gate does NOT judge**, and says so: whether the audit had teeth — a plugin
whose tools were all absent still writes a well-formed report — and severity, which is
a parse of another tool's markdown, carried as a signal and never used to pass or fail.

## Verdicts

- `READY_TO_MERGE` — no BLOCKER, ≤ 2 HIGH findings with documented mitigation.
- `READY_TO_MERGE_WITH_FOLLOWUPS` — no BLOCKER, but MORE than 2 HIGH. The blocking work is closed and provable; the debt is real and named. **Hard gate:** every HIGH is a *registered* followup — an entry in the plan's `## Followups` (matched by finding id) or a filed issue reference (`#NNN`) on the finding — never a mention in prose. A caveat nobody owns is a defect with better manners. Enforced by `consolidate_findings.py --plan`, which fails closed to `NEEDS_FIXES` when the plan is absent.
- `AWAITING_HUMAN` — the phase ran and stopped at a gate only a person opens (a T3 boundary call, an alignment sign-off, an approval, a dependency in another repository). **Emit it.** The work happened; without the event it leaves no trace, and every reader — the board, the drift checker, the selector, the watchdog — sees an item that was never touched.

  The wording used to read *every HIGH **above the cap***. With 5 HIGH findings that names 3 of them and nothing says which 3 — any subset satisfies it, which is not a gate. `every HIGH` is the strict reading and the one implemented.

  Use it instead of stretching `READY_TO_MERGE` (which would call acknowledged debt a clean green) and instead of `NEEDS_FIXES` (which would claim the blocking work is unfinished when it is demonstrably closed). The milestone is still gated by `cycle-acceptance`, so this verdict never softens what a `[x]` claims — it only stops forcing a false binary at the review boundary.
- `NEEDS_FIXES` — BLOCKER or > 2 HIGH findings. Return to `/implement` (or open targeted fix tasks).

  **A BLOCKER that was fixed and re-verified is CLOSED, not deleted.** The re-review marks the finding `status: CLOSED` and leaves the severity as it was; `skills/review/scripts/consolidate_findings.py` scores the verdict from OPEN findings only, so the halt lifts while the finding stays in the report under its original severity, naming the agent that closed it. Lowering the severity or deleting the entry reaches the same verdict by destroying the record — both are anti-patterns below. Shape in `skills/review/SKILL.md` § *Closing a finding on a re-review*.

  The mechanism shipped and this contract never mentioned it, which cost a consumer a re-run of four review agents to work around a capability that already worked: it grepped the consolidator for `outcome` — the field name the harness's `ReportFindings` tool uses — found nothing, and concluded the field did not exist. A mechanism nobody can find is worth what an absent one is worth.
- `NEEDS_DEEPER` — review surfaced systemic issues that exceed targeted fixes. Return to `/plan-write` for a re-scoping pass.

## Hard gates (BLOCKER-level)

Four of the five run in hooks that fire whether or not `/review` is invoked, and
for a long time this list said so about none of them. A mechanized gate whose
rule names no mechanism reads exactly like a gate nobody enforces — so it gets
re-run by hand, or quietly ignored. The mechanism is now part of the line.

- Failing tests on the working branch — `suite_runners.py`, invoked upstream by
  `run_validation.py` at the end of `/implement`, and again by `ci.yml` on every
  push. **No hook executes the suite**, so a branch that never ran `/implement`
  reaches `/review` with this gate resting on CI alone.
- New secrets committed (any pattern matching `.env`, `credentials*`, `*.pem`,
  `*.key`) — `stop-validation.py`.
- Direct commit to `main` (Unbreakable Rule 4) — `validate-command.py`, which
  resolves the real trunk instead of matching the literal `main`.
- Co-Authored-By trailer in any commit on this branch (user policy) —
  `validate-command.py`.
- `CHANGELOG.md` not updated despite production source changes (Unbreakable
  Rule 6) — `stop-validation.py`, which accepts a package `CHANGELOG.md` or a
  `.changeset/` entry as the record.

- A required independent audit that did not happen — `check_auditor_coverage.py`, entering `consolidate_findings.py` as BLOCKER findings so the verdict cannot be computed while ignoring it, the shape `check_upstream_gate.py` established. It fires on a report that is missing, one the plugin's own checker rejects, or a plugin this machine does not have. A project that declares no auditor is **not** blocked: that opt-out is a visible edit to a file the installer preserves, never a silence.

## Output

- `records/reviews/{slug}-review-{YYYY-MM-DD}.md` — consolidated findings with severity matrix.
- `agents/review-{slug}-{YYYY-MM-DD}/` — per-agent audit trail.

## Anti-patterns

- Treating LOW/INFO findings as blockers. They are advisory by design.
- Re-running `/review` after every fix instead of fixing the batch and re-running once.
- Reviewing your own plan in isolation. Spawn independent agents — the goal is fresh eyes.
- Skipping `/review` for "small" PRs. The gate exists for everything that touches production.

## Cross-references

- Schema for cycle rules: `rules/cycle-rule-schema.md`
- Skill: `skills/review/SKILL.md`
- Public-copy lint: `rules/public-copy.md`
- Macro super-loop: `rules/cycle-maintenance.md` — `READY_TO_MERGE` here unblocks the release that flips the milestone checkbox
- Upstream: `rules/cycle-code-quality.md` (consumes the audit verdict)
- Conventions: `rules/architecture.md`, `rules/testing.md`, `rules/error-handling.md`, `rules/git-safety.md`
