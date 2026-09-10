---
name: map
description: What every skill in this kit does, when to reach for it, and when reaching for it is the wrong move. Read this before invoking a skill you have not used, and before adding one.
tags: [index, skills, orientation]
generated:
  by: claude/opus-5
  at: 2026-08-31
status: stable
---

# The skill map

**32 skills.** Most are a phase of a cycle and are invoked in an order the
cycle rule fixes; seven are invoked on demand and belong to no chain.

**Every row below carries three things**: what the skill does, when to reach for
it, and — the column that is usually missing from an index — when reaching for it
is the wrong move. The third is not editorial. It is lifted from each skill's own
`## Anti-patterns`, from a prohibition stated in its body, or from the position
the cycle rule gives it. Where a skill's file states no prohibition, the row says
what its **chain position** forbids, which is sourced rather than invented.

## How to read a row

| Column | Answers |
|---|---|
| **Does** | what comes out the other side — the artifact, not the activity |
| **Use when** | the precondition. Most are "the previous phase produced X" |
| **Do NOT** | the misuse that looks reasonable at the time |

Every skill carries three documents, and they answer different questions:

| File | Answers | Written for |
|---|---|---|
| [`rules/squad-map.md`](../rules/squad-map.md) | where a phase sits, who owns it, and what governs it | whoever needs the 360º view |
| `SKILL.md` | what the skill guarantees and how it executes | the agent running it |
| `SOP.md` | what to check before invoking, what comes back, what each verdict obliges | whoever operates it |
| this map | which skill to reach for at all | whoever does not know yet |

When the map and a `SKILL.md` disagree, the `SKILL.md` wins and the disagreement
is a defect — see the last section.

---

## The two registries

Squad has two registries, on two different axes. Confusing them is the most common
mistake, and `cycle-acceptance` says so in its own words: they are *"a different
registry on a different axis. Anything claiming otherwise is a stale redirect."*

| File | Ids | Answers | Created by |
|---|---|---|---|
| `BACKLOG.md` | `B-NNN` | "what should we look at next?" | `backlog-init`, then `backlog-item` |
| `ROADMAP.md` | `M<N>` | "what did we promise a user?" | **hand-authored — no skill generates one** |

Only a milestone has a checkbox, so only a milestone reaches `acceptance`. A
`B-NNN` released without a milestone ends at `RELEASED`, and that is correct.

## The flows

**Deciding what the product is — the one cycle a human attends:**

```
/brainstorm-vision      what it is, who for, and what it is NOT
/brainstorm-objectives  OBJ-N, each with a metric and a horizon
/brainstorm-trd         REQ-N, each citing the objective it serves
/brainstorm-pieces      PIECE-N + the gate: 90% and a PERSON's signature
   ↓
/backlog-init           reads the four documents as context
```

Everything below this line runs unattended. That is what the gate above is for.

**A hunch worth checking — the default maintenance loop:**

```
/backlog-item {slug}                register it; no evidence required, on purpose
/discover-plan B-NNN --mode {mode}  what is measured, and what would kill it
/discover-edge-cases B-NNN          what could make the measurement lie
/discover-plan-confidence B-NNN     is the plan ready to run?
/discover-execute B-NNN             run it — ITEM_KILLED is a success
/discover-confidence B-NNN          is the finding solid enough to act on?
   ↓
/plan-alignment {slug} → /plan-write → /plan-edge-cases → /deps-audit
   → /plan-confidence → /implement → /code-quality → /review → /release
```

**The same chain, unattended:** `/idea-to-release {item}` runs every phase of it
for one item. `/pipeline` runs many items through it at once, a lane each.

There is **no `/discover` command** — the discovery chain is six separate skills,
each with its own gate. A rule referring to the chain as a whole names the cycle,
`cycle-discover`, never a slash command.

---

## Part 1 — The chain

The pipeline is `brainstorm → backlog → discover → plan → implement → code-quality →
review → release → acceptance`. Skills below are in the order they run.

### BRAINSTORM — deciding what the product is

The only cycle with a person in it. Four phases, one document each, then a gate.
Run by `iris-product-designer`, who holds the item-level alignment gate too — same
rubric, same floor, one level up.

| Skill | Does | Use when | Do NOT |
|---|---|---|---|
| `brainstorm-vision` | Writes `.squad/wiki/product/product-vision.md`: the named user, the problem, what it is, and what it is **not** | Starting a product, adopting the kit into a new scope, or when "what are we building?" gets different answers | Accept a category ("developers") as the named user, or skip the non-goals because the session is going well — it is going well because nothing has been ruled out |
| `brainstorm-objectives` | Writes `OBJ-N` objectives, each with a metric containing a number and a horizon | The vision exists and nobody can say what would count as achieving it | Write an objective that cannot fail. "Improve developer experience" closes never, so it is a value — put it in the vision, where nothing traces to it |
| `brainstorm-trd` | Writes `REQ-N` requirements, each citing the `OBJ-N` it serves | The objectives exist and the team is arguing about implementation | Name a technology. If two competent teams could not satisfy it differently, it is a design and belongs to `cycle-plan`, where it gets an audit and a score |
| `brainstorm-pieces` | Writes `PIECE-N` components, generates the unticked sign-off, and runs the product-alignment gate | The TRD is complete | **Tick your own boxes.** The one anti-pattern that defeats the gate. Never read `AWAITING_REVIEW` as a pass — a judge may not sign this one, by design |

### BACKLOG — deciding what is worth doing

| Skill | Does | Use when | Do NOT |
|---|---|---|---|
| `backlog-init` | Creates `BACKLOG.md` once, inventorying repos from disk and deriving the routing table | The project has no registry yet — after `/brainstorm-pieces` returns `PRODUCT_ALIGNED`, whose four documents it reads as context | Write the inventory from `CLAUDE.md` — it drifts; `find` / `git -C` is the source. Never seed "obvious" items: every one needs a human `why_now` and a DoD |
| `backlog-item` | Registers one `B-NNN` — a hypothesis; evidence is **not** required yet | Anyone notices something worth fixing, measuring or verifying | Ask for evidence during the intake grill — that turns intake into triage and silences the hunch this phase exists to capture. Never write to `BACKLOG.md` before the grill completes |
| `backlog-review` | Reports what has rotted in the registry — duplicate ids, evidence-less triaged items, kills with no reason, repos routing to nobody | Before trusting the registry to pick work | Edit the backlog. It is read-only by contract: a reviewer that edits cannot be trusted to report what it found |

### DISCOVER — turning a hunch into evidence, or killing it

| Skill | Does | Use when | Do NOT |
|---|---|---|---|
| `discover-plan` | Writes the measurement plan: what is measured, with which tool, against which target, and what result **kills** the hypothesis | An item is `raw` and someone wants to check the suspicion | "Look around and see what we find" — with no falsification criterion the measurement confirms whatever was already believed. Never write a target without opening it |
| `discover-edge-cases` | Finds what could make the measurement **lie** — a stale target, a proxy read as the thing, an environment fault read as a defect | After `/discover-plan`, before scoring | Widen the investigation. An edge case lives inside what was planned, and speculation about future states is not one |
| `discover-plan-confidence` | Scores the measurement plan, deterministically, in under 5s | Before running the measurement | Add a `--skip-checks` / `--force` flag, or lower a hard cap. The golden rule makes the absence of a bypass a constructor invariant |
| `discover-execute` | Runs the measurement and produces an opportunity — **or emits `ITEM_KILLED`** | The plan scored well enough to run | Write to a governed repo. Discover produces a document; an opportunity carrying the patch has skipped every gate after it. Never cite a pointer nobody opened |
| `discover-confidence` | Scores the opportunity | After the measurement, before `/plan-write` | Treat the score as a judgement about the finding's importance — it scores the ARGUMENT's structure |
| `discover-improve` | Lifts a low score by improving how the finding is **argued** | `/discover-confidence` returned `NEEDS_REVISION` | Rewrite the Evidence corner. It is the record of a measurement, and editing it falsifies findings downstream cannot detect |

### PLAN — deciding how

| Skill | Does | Use when | Do NOT |
|---|---|---|---|
| `plan-alignment` (phase 0.5) | Alignment brief + animated walkthrough + a reviewer checklist, scored on 17 criteria | **Unbreakable for anything from `BACKLOG.md`** — below 90% the item is not built | Tick your own review boxes — that is the single failure the sign-off exists to prevent. Never draw before grilling: a diagram of a vague brief looks rigorous |
| `plan-write` (phase 1) | Turns context into a plan at `.squad/records/plans/{slug}-plan.md` | The item is `ALIGNED` | Invoke it before alignment. `check_alignment_gate.py` hard-caps an unaligned plan at 49, so the plan cannot enter `/implement` anyway |
| `plan-edge-cases` (phase 2) | Annotates the plan with MUST-FIX edge cases | Right after `/plan-write` | Over-engineer. "An `ErrorRecoveryManager` for this edge case" → no; `if input.is_empty()` solves it. Speculation about future API changes is out of scope |
| `deps-audit` (phase 3) | CVE + version audit across npm, Python, Rust, Go | Before any code is written | Edit manifests — read-only, diffs are suggestions. Never audit `package.json` without the lockfile: transitive vulnerabilities live there |
| `plan-confidence` (phase 4) | Scores the plan; `INVALID` returns it to `/plan-write` | After `/deps-audit` | Add a bypass flag. Its golden rule makes the absence of `--skip-checks` a constructor invariant, and `check_deps_audit.py` caps the score when the audit is missing |
| `plan-improve` (phase 5, conditional) | Iterates the plan up to its target verdict | `/plan-confidence` scored below `SHIPPABLE_WITH_CAVEATS` | Expect it to touch anything outside the plan file, or to commit. It does neither, by contract |

### IMPLEMENT → REVIEW → RELEASE → ACCEPTANCE

| Skill | Does | Use when | Do NOT |
|---|---|---|---|
| `implement` | Executes the plan through a TDD halt-loop with the wiring triad and mechanised gates | The plan is at least `SHIPPABLE_WITH_CAVEATS`, on `workspace` | Mark a task done because tests pass without the wiring triad — that is the difference between code that compiles and code that runs. Never skip REFACTOR "to save time" |
| `code-quality` | Audits for dead symbols, fabricated APIs, cross-package orphans and weak tests | After the implement halt-loop closes | Edit source — read-only by contract. Never add `--force` / `--skip-checks` / `--accept-caveats` |
| `review` | The most rigorous gate: quality gates, line-by-line plan vs implementation, integration depth, edge-case coverage, by parallel agents in isolated worktrees | `/implement` validation passed | Approve unreviewed scope, fabricate a finding, or merge. It reviews; it never merges, and `NEEDS_DEEPER` sends the work back to `/plan-write` for re-scoping |
| `release` | Semver tag derived from the CHANGELOG, `develop → main` PR with rendered notes, merged once the chain is verified | `/review` returned `READY_TO_MERGE` | Merge a PR whose chain did NOT pass, or reach for `gh pr merge --admin` when branch protection refuses. Merging is inside the envelope since 2026-09-01; bypassing a gate never was. Never cut a release that does not trace to a `READY_TO_MERGE` audit |
| `acceptance` | Exercises the **released** deliverable against the milestone's Definition-of-done; the only gate that flips a ROADMAP checkbox | After the release exists | Re-run the test suite and call it acceptance — that passed three phases ago. Never mark a criterion `passed` by reading code: reading is not exercising |

---

## Part 2 — Orchestrators

These invoke the chain rather than sitting in it.

| Skill | Does | Use when | Do NOT |
|---|---|---|---|
| `idea-to-release` | Chains DISCOVER → … → ACCEPTANCE for one item, deriving depth from a deterministic confidence score | One item should go end to end without a person invoking nine commands | Fabricate a confidence signal — the script is deterministic and its output is the truth. Never skip `/plan-edge-cases`, `/deps-audit` or `/code-quality` on "high confidence": those gates are cheap and catch what unit tests miss |
| `pipeline` | Runs MANY items through the chain at once — a lane per item, a worktree each, batch/task consumption per stage | Several triaged items are waiting and the phases would otherwise idle between them | Expect it to relax a gate. Every gate the chain declares still applies per item, including the alignment gate, which the pipeline **cannot** satisfy |

---

## Part 3 — On demand

A phase of no cycle. Invoked when the question arises.

| Skill | Does | Use when | Do NOT |
|---|---|---|---|
| `ast-grep` | Structural search and refactor via tree-sitter patterns | The question is about AST **shape** — signatures, hierarchies, call sites | Use it to find a file containing a word: Grep is faster and clearer. Never inline a multi-statement pattern — use a YAML rule file |
| `arch-check` | Verifies declared architecture boundaries, or proposes ones the repo already obeys | Boundaries exist and may have drifted, or none are declared | Expect it to invent a boundary the code does not already respect, or to report a clean run it could not perform |
| `deps-audit` | *(also phase 3 of cycle-plan — see above)* | Outside a plan, when dependency risk is the question | — |
| `code-quality` | *(also the whole of cycle-code-quality — see above)* | Outside the chain, to audit a tree | — |
| `honesty-gate` | Blocks a "production-ready" / v1.0 claim without recorded evidence of sustained internal use | Someone is about to make that claim | Read `EVIDENCE_WITH_CAVEATS` as `SUFFICIENT` — the caveats are explicit. Never log evidence for one scenario and claim it satisfies another anchor |
| `quality-init` | Emits quality-gate hooks calibrated to the project's real p90 metrics | Setting a project up, once | Generate hooks that auto-fix — hooks are gates, not fixers. Never set thresholds below the floors: the hook would block every write |
| `squad-fit` | Reports which domains have no specialist, which of the project's own skills are undocumented, and whether a review panel can be formed at all | Adopting the kit into a project, after a restructure moved repositories, or before writing the agents and skills a project is missing | Write a specialist to silence `domain_without_agent` — a correctly-named stub routes the item into an empty prompt and trades a visible failure for a silent one. Never read its verdict without reading `PARTIAL`: the verdict covers only the sections that ran |
| `skill-creator` | Authors, improves and evaluates skills; `run_eval.py` measures whether a description actually makes the model reach for the skill | Creating or improving a skill, and before trusting a description | **Re-sync it blindly.** It is vendored, but `run_eval.py` now carries a local fix — its trigger detector decided the whole turn from its first observation and could only produce false negatives. A copy from upstream reverts that silently, and the symptom is a trigger rate that reads low and looks like a fact about the skill |
| `backlog-init`, `backlog-review` | *(see BACKLOG above)* | — | — |

---

## What this map does not answer

- **Whether a skill's gate will pass.** Only the run answers that.
- **The exact chain order and its numbering.** `rules/cycle-*.md § Chain` owns it,
  and `check_phase_numbering.py` keeps the skills' own claims consistent with it.
- **What a verdict means.** Each cycle has its own vocabulary, documented in its
  rule and swept by `check_orphan_verdicts.py`.

## Why this file is checked rather than trusted

The index it replaces went stale twice, and the second time is in the CHANGELOG:
*"the old `README.md` under `skills/`: it said 35 skills, there are 36, and the table omitted 7"* —
four of those omitted skills had **zero mentions in any entry point**, so they
existed on disk, passed every validator and were unreachable by any discovery
path. When this map was written the same file claimed 36 skills against 34 on
disk and listed 29, with `shared-understanding` — since renamed `plan-alignment`,
and the alignment gate that is
unbreakable for every backlog item — among the missing.

An index that drifts is worse than none: it is read as complete.

So `mechanisms/gates/check_skill_map.py` compares this file against the directory and
fails when they disagree in either direction — a skill on disk and absent here, a
row here for a skill that no longer exists, a count in the prose that does not
match, or a skill with no `SOP.md` beside its contract. It runs in
`verify_ecosystem.py`, and `check_sop_structure.py` sweeps every one of those
SOPs for shape and review date alongside the kit's own procedures.
