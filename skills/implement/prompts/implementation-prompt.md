# Implementation Halt-Loop Driver Prompt

You are mid-implementation, iteration {ITERATION}. The user invoked `/implement {PLAN_SLUG}` to drive a TDD halt-loop over the implementation plan.

**Plan:** `{PLAN_PATH}`
**Implementation working contract:** `{IMPLEMENTATION_PATH}`
**Progress file:** `.claude/records/implementations/.progress-{PLAN_SLUG}.json` (gitignored)
**Domain specialist:** `{SPECIALIST_PATH}` — the project's own, resolved at Step 2.5 by `mechanisms/cycle/route_domain.py`. Subagent type is `{SPECIALIST_DOMAIN}` (the `name:` in its frontmatter). **Nothing here generates it**; it was derived from the project's disk and carries the repos it covers, their verified build commands, their invariants and the false positives that domain produces.
**Consultation logs:** `.claude/records/implementations/{PLAN_SLUG}/specialist-consultations/iteration-{N}-{phase}.md`

## Specialist invocation discipline (READ BEFORE Step 1)

Claude Code's agent registry loads at SESSION START, so a project that derived its specialists mid-session will not have them registered yet. Two paths, in priority order:

1. **Primary:** `Agent(subagent_type='{SPECIALIST_DOMAIN}', prompt=<iteration question>, description='specialist {phase} — {T-ID}')`.

2. **Fallback:** `Agent(subagent_type='general-purpose', prompt='Read {SPECIALIST_PATH} for your role, the repos you cover, their invariants and their build commands. <iteration-specific question with MODE=TIGHT or MODE=VERBOSE>', description='specialist {phase} — {T-ID}')`.

If the Primary path returns "Agent type not found", switch to Fallback for the rest of the cycle. The file on disk is the source of truth either way.

**If Step 2.5 recorded a SKIP** (a plan with no `B-NNN`, so no `repo:` to route on), perform no consultation and say so in the iteration log rather than substituting a generic agent — with no declared domain, any specialist chosen is chosen by resemblance. Every other Step 2.5 outcome is a HALT, so a running loop has either a specialist or a recorded skip.

## Your contract for this iteration

1. **Read the progress file.** Find the next task whose status is `pending` AND whose dependencies are `committed` or `blocked` — the two terminal statuses. (This said `committed` or `done` until 2026-09-08. `done` is not a status: nothing in the loop treated it as terminal, so a dependency carrying it would never unblock its dependants.)

2. **For the picked task, run the complete TDD cycle in order:**

### Specialist consultation 1/3 — Before RED

Before writing any test, invoke the specialist via `Agent` tool:

- `description`: "specialist pre-RED — task {T-ID}"
- `subagent_type`: `{SPECIALIST_DOMAIN}` (Primary) OR `general-purpose` (Fallback — pass `{SPECIALIST_PATH}` in the prompt)
- `prompt`: advise on task {T-ID} — recap what the plan declares for it, then, from what you know about these repos: the gotchas this domain produces, the false positives to expect, ADR-link expectations, files-to-edit verification, and TDD shape concerns.

The response is markdown advice. Read it BEFORE writing the test. A `[CRITICAL]` flag is a HALT trigger unless you have explicit Unbreakable-Rule-1 (95% confidence) justification to proceed.

Append the response to `.claude/records/implementations/{PLAN_SLUG}/specialist-consultations/iteration-{ITERATION}-pre-red.md` for the audit trail. Logs go under `records/`; `agents/` holds definitions only.

### RED phase (mandatory first)

- Read the plan's TDD section for this task
- Apply any non-critical suggestions from the pre-RED consultation
- Write the failing test FIRST in the declared `.test.ts` file
- Run `npm test -- {test-file-path}` and CONFIRM it FAILS for the expected reason
- If the test passes BEFORE implementation, the test does not exercise the targeted behavior — HALT, revise the test
- Update progress file: task status → `red`, log iteration outcome

### GREEN phase

- **Walk the parsimony ladder FIRST** (`.claude/rules/parsimony-ladder.md`), top-down, stopping at the first rung that resolves the need — this is a deliberation step BEFORE you type code:
  1. Does this need to exist? → no: skip it (YAGNI) — if the RED test can pass without new code, do not write any.
  2. Does the stdlib do it? → use it.
  3. Native platform / framework feature? → use it.
  4. Dependency already installed? → reuse it; do NOT add a redundant dependency.
  5. One line? → one line.
  6. Only then: the minimum that makes the test pass.
- The ladder NEVER justifies skipping the failing test, input validation, error handling, security, or accessibility (`parsimony-ladder.md § Never on the chopping block`). A "fewer lines" argument that weakens correctness is a Rule 3 honesty violation — state the need explicitly and write the necessary code.
- Write the MINIMAL production code that makes the RED test pass
- Run `npm test -- {test-file-path}` and confirm PASS
- If still failing after a reasonable attempt, increment task retry counter (max 3 per task)
- After 3 GREEN failures, mark task BLOCKED with reason "implementation strategy not viable"
- Update progress file: task status → `green`, log iteration outcome

### Specialist consultation 2/3 — After GREEN / Before REFACTOR

Invoke the specialist via `Agent` tool with the diff:

- `description`: "specialist post-GREEN — task {T-ID}"
- `subagent_type`: `{SPECIALIST_DOMAIN}` (Primary) OR `general-purpose` (Fallback — pass `{SPECIALIST_PATH}` in the prompt)
- `prompt`: review the diff (`git diff` against last commit). Spot SOLID/Clean Code/DRY violations, missed cross-references, naming-convention drift, and test completeness against the ADR invariants — plus anything that violates an invariant of YOUR domain specifically.

Append response to `.claude/records/implementations/{PLAN_SLUG}/specialist-consultations/iteration-{ITERATION}-post-green.md`.

### REFACTOR phase

Review the new code against quality rules from `SKILL.md § Quality rules` PLUS the post-GREEN findings:

- **SOLID:** SRP (one reason to change), OCP (composition over inheritance), LSP (subtypes substitute), ISP (role-shaped interfaces), DIP (`src/core/` ↛ `src/local|cloud/`)
- **Clean Code:** naming conventions, function size, no dead code, no `any`, no `console.log`
- **DRY:** rule of three for extraction; don't merge code that looks similar but represents different concepts
- **Design Patterns:** apply established patterns when the problem matches; don't invent
- **Specialist-flagged items:** address each `[MAJOR]` or `[MINOR]` finding (or document explicit justification to skip)

If any violation found, fix it. Tests stay green throughout. If tests break, revert REFACTOR changes and continue (refactor was wrong shape).

Update progress file: task status → `refactor`, log iteration outcome.

### WIRING phase (HARD GATE — the main rule)

Identify the new public symbols introduced by this task (functions, classes, types exported from the changed files). For each symbol, run:

```bash
python3 .claude/skills/implement/scripts/check_wiring.py \
  --symbol {symbol-name} \
  --project-root .
```

The script emits JSON with three pillars:

- **(a) Static caller** — must find ≥1 production caller (non-test file under `src/`)
- **(b) Integration test** — must find ≥1 file under `tests/integration/` referencing the symbol OR an explicit `<!-- ADR-DEFER-WIRING-B: reason -->` marker in the implementation task contract
- **(c) Runtime metric** — if the plan's task or Global DoD declared a metric (`metric:name`), `.wiring-evidence.json` must show `name: count > 0`. If no metric declared, this pillar is `n/a`.

**Failure handling:**

- Pillar (a) FAIL: do NOT commit. Add a caller in production code (the caller must be functionally necessary — never a no-op call gaming the metric). If no real caller justifies this symbol, the symbol is dead code; remove it.
- Pillar (b) FAIL: add an integration test that exercises the symbol via a real boundary scenario, OR add `<!-- ADR-DEFER-WIRING-B: <rationale> -->` with reason (prototype phase, third-party API not yet stable, etc.).
- Pillar (c) FAIL: run the integration test that should fire the metric; if it doesn't fire, the wiring is wrong (metric is declared but not exercised). Fix and re-check.

After triad passes, update progress file: task status → `wired`, log iteration outcome.

### COMMIT phase

**Model routing (teacher/student split — experimental):**

Before composing the commit message, check `.claude/rules/implement-model-routing.txt`. If a `commit:` entry exists (e.g., `commit: haiku ...`), delegate the commit-message composition to a nested `Agent` tool invocation with `model: <resolved>` and a phase-focused sub-prompt (stage facts + plan task ref + wiring summary as input; let the student model author only the one-line description + body). Main session retains the stage + commit execution (so git operations stay observable in the halt-loop transcript).

If the rule file is **missing** OR the `commit:` entry is **absent**, fall back to inline composition on the session model (status quo, no Agent nesting). **There is no `§ Model routing` contract in `cycle-implement.md`** — this split is experimental and the fallback above is its only specified behaviour.

### Specialist consultation 3/3 — Before COMMIT

Stage the files first (`git add` with specific paths), then invoke the specialist:

- `description`: "specialist pre-COMMIT — task {T-ID}"
- `subagent_type`: `{SPECIALIST_DOMAIN}` (Primary) OR `general-purpose` (Fallback — pass `{SPECIALIST_PATH}` in the prompt)
- `prompt`: audit the staged diff (`git diff --cached`) + draft commit message against the task's DoD checkboxes from the plan. Verify: conventional-commit format, T-id reference, Wiring summary completeness, wiring triad sanity (pillar (a) callers are FUNCTIONAL not no-op stubs). Then judge the change against your domain's blast-radius heuristics.

Append response to `.claude/records/implementations/{PLAN_SLUG}/specialist-consultations/iteration-{ITERATION}-pre-commit.md`.

On a `[CRITICAL]` finding here, do NOT commit. Unstage (`git restore --staged`), address it, re-consult. Up to 2 retries; on a third `[CRITICAL]` mark the task BLOCKED.

**Inside its domain the specialist is not overruled.** Believing it is wrong is a finding to record in the log, not a verdict to substitute.

Standard commit instructions (apply whether routed or inline):

- Stage ONLY the files modified by this task (`git add` with specific file paths — NEVER `git add -A` or `git add .`)
- Commit with conventional-commit format:
  ```
  {type}({scope}): {one-line description}

  T{N.M}: {plan task reference}
  Wiring: a={pass/defer} b={pass/defer} c={pass/n/a}
  Closes: {issue-ref if applicable}
  ```
  Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
- NEVER `git commit --no-verify` — if pre-commit hook fails, fix the underlying issue (Unbreakable Rule)
- Capture the commit SHA from `git rev-parse HEAD`

Update progress file: task status → `committed`, log SHA + iteration outcome.

### PROGRESS update

Update `.claude/records/implementations/.progress-{PLAN_SLUG}.json`. The file
is a SINGLE JSON object with a top-level `tasks` ARRAY — find the entry for this task
and set its fields (do NOT append a bare object; the gates read `data["tasks"]`).
Canonical shape: `.claude/skills/implement/templates/progress-schema.json`.

```json
{
  "slug": "{PLAN_SLUG}",
  "tasks": [
    {
      "id": "T1.1",
      "phase": "1",
      "status": "committed",
      "files": ["src/foo.ts", "src/foo.test.ts"],
      "commit_sha": "abc123...",
      "wiring": {"a": "pass", "b": "pass", "c": "n/a"},
      "iterations_used": 7,
      "phases_completed": ["red", "green", "refactor", "wiring", "commit"]
    }
  ]
}
```

**Required per task** (the gates depend on these exact keys): `id` (NOT `task_id`),
`phase` (gates filter by it), `status`, and — once committed — `commit_sha` + `files`.
A `blocked` task MUST also carry `blocked_reason`. Getting these wrong does not error
loudly on write, but `run_validation.py`'s `progress_schema` gate will FAIL the
validation, so write them right the first time.

## Re-evaluate halt conditions

After completing a task (or marking it BLOCKED), verify:

1. **Every task in the progress file has status `committed` OR `blocked` with reason.** Pending tasks remain → continue iterating.
2. **No task is `red`, `green`, `refactor`, or `wired` without `committed`.** A stuck mid-phase task → continue iterating to finish.
3. **All Acceptance Criteria checkboxes from the implementation task contract are TRUE.**

If ALL conditions hold, emit the promise marker AT THE VERY END of your response — **plain text, isolated on its own line, NO backticks, NO fenced code blocks, NO markdown wrapping**. Ralph-loop's regex matches the literal sequence `<promise>IMPLEMENTATION_COMPLETE</promise>` outside of inline code. Wrapping the marker in backticks (` `` `) or triple-fence code blocks BREAKS detection and forces another iteration.

Correct form (emit exactly this on its own line at end of response):

<promise>IMPLEMENTATION_COMPLETE</promise>

INCORRECT forms (will NOT terminate the loop):

- Wrapped in backticks: `<promise>IMPLEMENTATION_COMPLETE</promise>`
- Inside a fenced code block (triple backticks)
- Indented as part of a list item or quote
- Embedded mid-sentence

After emitting, you may follow with a one-paragraph summary, but the promise marker MUST be on its own isolated line before any trailing prose. Report: tasks completed / tasks blocked / iterations used / wiring triad summary / next step recommendation (run `scripts/run_validation.py`).

If conditions NOT met, do NOT emit the promise. STOP your current turn — the Stop hook will restart you in iteration {ITERATION + 1}.

## Inviolable rules (cycle-implement.md § Anti-patterns)

- NEVER write production code without a failing test first (TDD-first)
- NEVER mark a task `committed` with red/skipped tests
- NEVER edit the implementation plan (`{PLAN_PATH}`) mid-iteration — the plan is the contract
- NEVER commit directly to `main` (verify `git branch --show-current` != `main` before each commit)
- NEVER use `git checkout`, `git revert`, `git push --force`, `git reset --hard` — use `git switch`, `git restore --staged`, `git stash`
- NEVER `--no-verify` to skip hooks
- NEVER scope-creep mid-task — opportunistic improvements go to followups, not current commit
- NEVER fabricate wiring evidence — if pillar (c) needs a metric that the system doesn't emit, mark BLOCKED, not faked

## When the loop should give up

If the same task fails GREEN 3 times in a row with no observable progress OR an external dependency is missing (DB/service down, library not installed) OR the plan declares behavior contradicted by reality OR real-tree validation surfaces a HIGH/CRITICAL CVE:

- Mark the affected task as `blocked` with an explicit reason in `.progress-{PLAN_SLUG}.json`
- HALT this iteration. Do NOT emit `<promise>IMPLEMENTATION_COMPLETE</promise>` — the implementation gate has NOT passed
- Write an explicit BLOCKED report listing the blocked tasks, the blocker reason for each, and the recommended human action (typically: loop back to `cycle-plan` for revision OR fix the environment OR address the CVE)
- Surface the BLOCKED report to the user

The completion promise `<promise>IMPLEMENTATION_COMPLETE</promise>` is emitted EXCLUSIVELY when every task is `committed` OR honestly `blocked` with reason AND every DoD checkbox is true. There is no graceful-exit path that emits the promise on a partial state. The downstream validation gate (`run_validation.py`) would catch incomplete work regardless, but the gate exists so the LLM does not stage a partial implementation as complete. Honest BLOCKED over false completion (Unbreakable Rule 3).
