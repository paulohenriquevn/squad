# Cycle: PLAN

Source of Truth for the planning cycle.

## Purpose

Produce an implementation plan — what to build, how, in what order, with which dependencies and risks. Output is a document, not code.

## Pre-conditions

- A feature has a defined goal and known prior art (otherwise, run DISCOVER first).
- A non-trivial bug fix that touches multiple modules.
- (Optional macro context) — when running inside the `cycle-maintenance` super-loop, `/plan-write` accepts `--milestone M<N>` to persist the milestone ID in the plan frontmatter; `cycle-release` reads this metadata to flip the checkbox post-merge. Plans without `--milestone` are valid (ad-hoc / hotfix work) but skip the post-release flip.

Do NOT trigger PLAN for:
- Single-line changes (write the code).
- Pure refactors with no behavior change (open a PR with the diff and a 1-line rationale).

## Chain

Phase 0 is UNBREAKABLE for any item coming from `BACKLOG.md`, and so is everything
after it.

**There was a Phase 0 before this one** — `/grill-me`, an optional interview that
made vague requirements precise. It was retired on 2026-08-31 after producing one
grill in a consumer's entire history: `/plan-alignment` interrogates the item as
its first act, and it is unbreakable where the optional phase was not, so the
interview already happened wherever the work actually is.

```
/plan-alignment {slug}                       [Phase 0 — grill + draw, scored]
     ↓ (produces: records/alignment/{slug}-alignment.md + {slug}-walkthrough.html)
     ↓ verdict:
     ↓   ALIGNED          → machine >= 90% AND a non-author reviewer signed → /plan-write
     ↓   AWAITING_REVIEW  → structure done, nobody signed off yet; ask for the review
     ↓   BLOCKED          → the item is NOT built; close the listed gaps and re-score
     ↓   NEEDS_SPLIT      → split into items that each align on their own
/plan-write "{one-sentence feature description}"
     ↓ (Step 0 auto-discovers rules/ + skills/*-patterns/ + grill output if present)
     ↓ (produces: records/plans/{slug}-plan.md)
/plan-edge-cases {slug}
     ↓ (MUST-FIX absorbed into the plan)
/deps-audit {slug}
     ↓ (dependencies + CVE audit before any code)
/plan-confidence {slug}
     ↓ (score)
     ↓ if INVALID  → /plan-write (rewrite)
     ↓ if low      → /plan-improve {slug} → /plan-confidence (re-score)
     ↓ if ≥ SHIPPABLE_WITH_CAVEATS → ready for /implement
```

## Phase contracts

| Phase | Input | Output | Hard gate |
|---|---|---|---|
| plan-alignment | item + discover evidence | alignment brief + animated walkthrough + an unticked reviewer checklist | `score_alignment.py` reports ALIGNED — machine score >= 90% AND every `## Reviewer sign-off` box ticked by a reviewer **who is not the author**: a person, or `alignment_judge.py` when none is coming. The agent that wrote the brief may never tick one (see [`alignment-threshold.md`](../skills/_kit-rules/alignment-threshold.md) § Amended 2026-09-01). This row said *a human ticked* until 2026-09-08, contradicting the rule it cites and re-freezing every unattended run at `AWAITING_REVIEW` |
| plan-write | feature description (+ grill output if Phase 0 ran) | plan with Goal, Tasks, Risks, Test Plan, Open Questions | Coverage Matrix present (every Goal claim mapped to ≥ 1 task) |
| plan-edge-cases | plan | annotated plan with MUST-FIX | every MUST-FIX has owner + acceptance criterion |
| deps-audit | plan | dependency report with CVE status | no critical CVE on a planned dependency — `check_deps_audit.py`, see below |
| plan-confidence | plan | score + verdict | INVALID returns to /plan-write |

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
that run left on disk, so forgetting the audit costs the plan its band instead of passing silently.

**Running `/deps-audit` is a step of this cycle, not a human errand** (2026-09-08). It was described
as *"the human step that remains"* while the chain below `cycle-backlog` was already meant to run
unattended, which left the strongest gate in the cycle depending on somebody remembering. A CRITICAL
or HIGH CVE hard-caps the plan at `INVALID`, and `INVALID` returns to `/plan-write` — the dependency
is replaced, pinned or dropped by the same chain that planned it. Nothing about that needs
authority: it is `option` in [`decision-delegation.txt`](decision-delegation.txt), and the plan
already enumerates what it would depend on. The extension of the gate is recorded in
`plan-confidence-golden-rule.md` § Rules that cannot be bent.

Stating it is the point. A gate listed beside four mechanized ones reads as mechanized, and a gate
believed to be automatic is one nobody runs.

## Halt-loop contract (/plan-improve only)

`/plan-improve` is the only phase of `cycle-plan` that drives an autonomous halt-loop via `ralph-loop:ralph-loop`. It follows the same rigorous template established for `/implement` (per `rules/cycle-implement.md`): pre-flight guard against concurrent ralph-loops, formal stop conditions, post-promise sanity check, anti-patterns enumerated, honest BLOCKED report over false PASS.

- **Completion promise:** `<promise>PLAN_IMPROVED</promise>` — asserts re-run of `run_structural.py` in the emitting iteration shows verdict ≥ `--target`. Step 6 post-promise sanity check re-verifies score-on-disk. The loop runs until the score on disk reaches the target; partial improvements do not justify emitting the promise.
- **Stop conditions:** see `skills/plan-improve/SKILL.md § Stop conditions` (6 enumerated cases). When the loop stops without reaching the target, emit a BLOCKED report (no completion promise) and surface the structural blocker to the human.
- **Hard caps are NOT auto-fixable.** Per § Verdicts, `INVALID` (49) returns to `/plan-write` rewrite — `/plan-improve` MUST NOT iterate trying to lift a hard cap.

A BLOCKED report blocks downstream: `/plan-confidence` MUST NOT honor the plan as SHIPPABLE while it stands. **It does not stop at a person** — the item returns to the registry carrying the report, and the queue works the named cause (`autonomy-envelope.md § A loop ran out of attempts`). What is forbidden is honouring the plan anyway, not proceeding to the next item.


## Pre-flight: task interfaces

Before any task is implemented, `skills/plan-confidence/scripts/check_task_interfaces.py`
cross-checks what each task DECLARES it produces against what later tasks call, reading only
the `#### Pseudo-code / Signatures` blocks. It reports three things:

| Finding | Why it matters |
|---|---|
| produced and never consumed | a helper with no caller — D1 flags it one phase later, after it was written |
| consumed and never produced | a call to something no task declares; this one breaks at runtime |
| consumed before produced | the symbol resolves, but the plan cannot run in its own order |

**Why here and not in `check_wiring.py`.** That checker asks the same question after
`/implement`, when the mismatched calls already exist. Two tasks disagreeing about a
signature are cheapest to reconcile while both are still prose.

**Advisory, not a cap** _(not mechanized: judgement — the signature block is
optional by template, so an absent one is unknown rather than wrong, and capping on silence
would push authors to write blocks that satisfy a parser)_. Tasks with no block are counted
and reported as **unchecked**, never as clean.

The method comes from an observed run of `obra/superpowers`' `subagent-driven-development`
(2026-08-28): its pre-flight pass cross-checked 14 producer/consumer pairs before any code
and found six defects in the plan — including `assert.throws` returning `undefined` at eight
call sites, which would have failed every test in two files.

## The review panel

**Decided 2026-09-08.** The plan this cycle produces is judged by **three reviewers**, and
**2 of 3 approvals** advance it. Below the majority it returns as `NEEDS_REVISION` — a
verdict that already exists and already holds an item, so no new token was invented for a
state the vocabulary already had.

| | |
|---|---|
| Who sits | [`rules/review-panel.txt`](review-panel.txt) — **the project's**, because which models a project can reach is not the kit's business |
| What the kit imposes | Three reviewers; at least one from a recognised family **outside** the one the kit runs on; the author never sits |
| Computes | [`mechanisms/cycle/review_panel.py`](../mechanisms/cycle/review_panel.py) |
| Premise | [`mechanisms/gates/check_panel_capability.py`](../mechanisms/gates/check_panel_capability.py), at intake |

**Why a script cannot do this job.** `/plan-confidence` is deterministic and scores
STRUCTURE — the coverage matrix, citations that resolve, criteria that are executable.
What it cannot ask is whether the plan actually does what the item asked for, and whether
the evidence behind it supports the approach chosen. That is what the panel is for.

**Why the panel must not be one family.** Three Claudes asked three times are three
correlated opinions: a plausible fabrication that survives one tends to survive its
siblings, which is the single thing an orthogonal reviewer catches. An **unrecognised**
model supplies neither side — otherwise `--model anything` would prove orthogonality by
typing.

**An incomplete panel is not a rejection.** Two approvals out of two is not 2-of-3: the
threshold is over a FULL panel, so a missing reviewer is an abstention, and an abstention
approves nothing and rejects nothing. The panel did not convene, the item returns to the
registry with an `access` impediment (`halt_disposition.py`), and the queue takes the next
item.

**The dissent is kept.** A minority vote that loses is the most interesting thing in the
record, and `review_panel.py` reports it beside the outcome — the same argument
`cycle-judge-codex.md` already makes about Claude and Codex disagreeing.

**This does not replace the alignment gate.** `/plan-alignment` asks whether the item is
understood before anything is built; the panel asks whether the plan that came out of it
holds up. Two different questions, two different artifacts, and passing one has never
implied the other.

## Verdicts

- `INVALID` — hard cap blew (e.g., Coverage Matrix incomplete, fabricated citation). Return to `/plan-write`. **`/plan-improve` does not fix hard caps.**
- `NEEDS_REVISION` — soft caps blew (risks under-addressed, test plan thin). Use `/plan-improve`.
- `SHIPPABLE_WITH_CAVEATS` — proceed to `/implement`; caveats are explicit, not hidden.
- `SHIPPABLE` — green light.
- `ALIGNED` — phase 0 only: machine score ≥ 90% and a reviewer who is not the author signed off. Proceed to `/plan-write`.
- `AWAITING_REVIEW` — phase 0 only: the brief is complete and nobody has signed. Ask for the review, or run `alignment_judge.py` when none is coming.
- `BLOCKED` — phase 0 only: below the machine threshold. The item is **not** built.
- `NEEDS_SPLIT` — phase 0 only: the brief describes independent subsystems. Declared by the reviewer, never inferred.
- `AWAITING_HUMAN` — the phase ran and stopped at a gate only a person opens (a T3 boundary call, an approval, a dependency in another repository). An alignment sign-off is **no longer** one of them: `skills/_kit-rules/alignment-threshold.md § Amended 2026-09-01` requires a reviewer who is not the author, which a judge can be. **Emit it.** The work happened; without the event it leaves no trace, and every reader — the board, the drift checker, the selector, the watchdog — sees an item that was never touched.

## Anti-patterns

- Plans that are essentially "implement X, test it, ship it" — no actual decomposition.
- Plans without a Test Plan section. If the plan can't say how to verify success, the plan is incomplete.
- Plans listing every possible task without prioritization. Tasks need an ordering.
- Skipping `/deps-audit` because "the lib is well-known". Well-known libs ship CVEs too.
- Pivoting the plan during `/implement` instead of returning to `/plan-write`. If the plan was wrong, the plan needs to change; the implementation log is not the place.

## Cross-references

- Schema for cycle rules: `rules/cycle-rule-schema.md`
- Skills: `skills/plan-write/SKILL.md`, `skills/plan-edge-cases/SKILL.md`, `skills/deps-audit/SKILL.md`, `skills/plan-confidence/SKILL.md`, `skills/plan-improve/SKILL.md`
- Macro super-loop: `rules/cycle-maintenance.md` — defines the `milestone_id` frontmatter contract that plans MAY carry
- Upstream: `rules/cycle-discover.md` (when prior art is unknown)
- Downstream: `rules/cycle-implement.md` (consumes the plan with verdict ≥ SHIPPABLE_WITH_CAVEATS)
- Conventions: `rules/architecture.md`, `rules/testing.md`
