# The Squad map — every phase, who owns it, and what it reads

**The 360º view.** `skills/map.md` answers *which skill do I reach for*; this file
answers *where am I, who decides this, and what governs it*. The two are
complementary and neither replaces the other — a checker keeps each honest against
the directory it describes.

A compact form of this map is injected at SessionStart by
`hooks/sessionstart-context.py`, so an agent starting work already knows the chain
and the four roles. That copy is deliberately partial and points here.

## Three layers, and only one is the project's

| Layer | Written by | Survives a reinstall? |
|---|---|---|
| Contracts and skills — `rules/cycle-*.md`, `rules/*.md`, `skills/`, `mechanisms/` | the kit | **No.** Overwritten, and that is how a fix reaches the projects that installed it |
| Configuration — `rules/*.txt`, thresholds, allow-lists | the project | **Yes.** Preserved, because it is what a consumer calibrates |
| Domain specialists — `agents/*.md` | the project, derived from disk | **Yes**, and the kit ships zero of them |

The question that places a file is **not who reads it — it is who owns it**
(`rules/README.md`). A file a consumer tunes must live where the installer
preserves it, or the next update destroys their configuration in silence.

**Where the mechanisms are.** Everything that computes a verdict lives under
`mechanisms/`, in five families: `gates/` measures the kit against its own
contracts, `cycle/` is the cycle at runtime (routing, the event stream, status
transitions, attestation), `fleet/` runs many sessions at once, `dist/` gets the
kit into a consumer, and `conventions/` holds where things live and what shape
they have. The import namespace is flat — a family is a directory, not a package
— and a file there resolves the repository root as `parents[2]`. The directory
was `scripts/` until 2026-09-01; a consumer installed before then has its
`.claude/scripts/` removed by the installer, because a stale copy beside the new
one keeps answering through the hooks' fallback chain.

## The chain

Declared once, machine-readable, in [`rules/cycle-phases.txt`](cycle-phases.txt).
`mechanisms/gates/check_phase_drift.py` confronts that declaration with what actually
emitted.

```
BRAINSTORM → BACKLOG → DISCOVER → PLAN → IMPLEMENT → CODE-QUALITY → REVIEW → RELEASE → ACCEPTANCE
    ↑                      ↓
 a person                ITEM_KILLED ✔  (the chain ends — a successful outcome)
 is required
```

Everything from BACKLOG down runs unattended, merge included. That is only
defensible because BRAINSTORM happened — see
[`rules/autonomy-envelope.md`](autonomy-envelope.md) floor 2 and
[`wiki/decisions/merge-is-inside-the-envelope.md`](../wiki/decisions/merge-is-inside-the-envelope.md).

**DISCOVER through ACCEPTANCE is closed to human intervention** (2026-09-08). Ten phase
rules used to end a halt with *escalate to the human*; all ten now return the item to the
registry instead, and `mechanisms/cycle/halt_disposition.py` decides which of the two ways
it goes back. The one door that still reaches a person is a **material impediment** — a
machine, a credential, elapsed time, a system that is not standing — and it reaches them
through the registry, never by a session standing still. See
[`autonomy-envelope.md § The autonomous span`](autonomy-envelope.md).

## The four roles, and the seam between them

They are **mechanism**: each describes a DECISION, not a repository, which is why
they may be versioned when a domain specialist may not.

| Agent | Decides | Runs |
|---|---|---|
| `kairos-product-owner` | what work exists, and in what order | `/backlog-item`, `/backlog-review`, `squad_boss.py` |
| `iris-product-designer` | what the product IS, and what the user will experience | `cycle-brainstorm` (4 skills), `/plan-alignment`, `/acceptance` |
| `daedalus-tech-lead` | one item's technical path — and who builds each part | `/idea-to-release`, the domain specialists |
| `hermes-scrum-master` | flow: which item enters which lane, and what unblocks a halt | `/pipeline`, `rules/autonomy-envelope.md` |
| `vera-technical-arbiter` | the technical shape of a fix — which principle a problem violates, how severe, and the obvious solution | the five lenses; `rules/architecture.md` |
| `eureka-defect-hunter` | what is wrong — not what to do about it | the defect lenses; `rules/architecture.md` |
| `hecate-intake-triager` | what crosses from outside into the registry | the tracker; `rules/cycle-backlog.md` |
| `clio-historian` | nothing — reports what the record says about the past | the event stream; `rules/cycle-backlog.md` |
| `metis-oracle` | nothing — reports what is true right now, and why | live state; `rules/autonomy-envelope.md` |
| `leonardo-researcher` | nothing — supplies what a decision needs | the sources; `rules/cycle-discover.md` |
| `vigil-sentinel` | what deserves an interruption | live metrics; `rules/autonomy-envelope.md` |
| `aesculapius-healer` | which impediments have already been cured | recorded walls; `rules/cycle-backlog.md` |
| `argus-pattern-analyst` | what is common to many cases | halt reports; `rules/cycle-backlog.md` |
| `nemesis-claim-auditor` | whether the system's own claims are supported | the kit's own verdicts; `rules/architecture.md` |

A role that could do two of these could overrule itself — Hermes deciding a stage
passed, or Daedalus choosing which item he prefers. See
[`agents/README.md`](../agents/README.md).

**`cycle-brainstorm` is Iris's**, decided 2026-09-01. The four roles predate the
phase, and Kairos was the other defensible reading — his backlog derives from it. He
did not get it because his role is the QUEUE, and the brainstorm produces what the
queue serves rather than the queue itself.

Iris got it on three counts already in her file: her temperament is *refusing a brief
that describes a system instead of an experience*, which is gate G-B1; her standing
question is *"and then what does the user see?"*, which is the vision's question; and
she already holds the alignment mechanism — same 17-criteria rubric, same 90% floor.
`cycle-brainstorm` is that instrument one level up.

So **Iris holds both alignment gates**, product and item, and in neither does she
sign: the product sign-off is the human's and an item's may be the judge's. She
produces what is graded and never grades it. What Kairos inherits is the output — the
`OBJ-N` ids that items cite through `traces_to`.

## Phase by phase

Each row: the skills in order, the contracts that govern them, and what computes
the verdict. **No verdict in this kit is asserted in prose.**

### BRAINSTORM — phase −1 · Iris, with a person in the room

| | |
|---|---|
| Skills | `/brainstorm-vision` → `/brainstorm-objectives` → `/brainstorm-trd` → `/brainstorm-pieces` |
| Rules | [`cycle-brainstorm.md`](cycle-brainstorm.md) · the 90% floor from [`skills/_kit-rules/alignment-threshold.md`](../skills/_kit-rules/alignment-threshold.md) |
| Computes | `build_agenda.py` (the agenda, before the first question) · `score_product_alignment.py` (17 criteria, hard caps and floor caps) |
| Produces | `wiki/product/` — vision, objectives, trd, technical-pieces, alignment · `records/brainstorms/` for what was discarded |
| Gates | G-B1…G-B5. **A judge may not sign this one** — a product vision has no independent evidence to be scored against |

### BACKLOG — phase 0 · Kairos

| | |
|---|---|
| Skills | `/backlog-init` · `/backlog-item` · `/backlog-review` |
| Rules | [`cycle-backlog.md`](cycle-backlog.md) · [`domain-routing.txt`](domain-routing.txt) — **the project's** |
| Computes | `detect_domains.py`, `scaffold_specialists.py`, `check_intake_gates.py`, `select_backlog_item.py`, `check_backlog_structure.py`, `backlog_index.py`, `squad_boss.py`, `board_server.py` |
| Gates | G1 route · G2 dedup · G3 single domain · G4 verifiable DoD · G5 no prior-art · G6/G7 impediment edges. **G1, G2, G6, G7 mechanised; G3, G4, G5 are judgement by decision** |

`/backlog-init` is where the specialists are born: it reads the topology from disk,
writes the routing table, and scaffolds one agent file per domain it names.

### DISCOVER — phases 1–6 · the domain specialist

| | |
|---|---|
| Skills | `/discover-plan` → `/discover-edge-cases` → `/discover-plan-confidence` → `/discover-execute` → `/discover-confidence` → `/discover-improve` |
| Rules | [`cycle-discover.md`](cycle-discover.md) · [`discover-opportunity-golden-rule.md`](discover-opportunity-golden-rule.md) · [`skills/_kit-rules/discover-plan-golden-rule.md`](../skills/_kit-rules/discover-plan-golden-rule.md) · [`live-target.txt`](live-target.txt), [`discover-web-allowlist.txt`](discover-web-allowlist.txt) — **the project's** |
| Computes | `run_measurement_plan_score.py`, `run_opportunity_score.py`, `check_evidence_pointers.py`, `check_measurement_targets.py`, `check_corner_coverage.py`, `check_opportunity_completeness.py`, `check_spec_smells.py` |
| Modes | `review` · `live-test` · `bug` (hard floor: no failing test, no bug) · `evolve` |

This is where the specialist matters most, and the reason is literal: a reviewer
who does not know that a root `go build ./...` covers almost nothing in a
multi-module repo reports "builds clean" and has measured nothing.

`--sweep` is the registry's second writer — findings land in `BACKLOG.md` with
evidence attached, skipping intake because they arrive with what intake is not
allowed to require.

### PLAN — phases 0–5 · Iris at phase 0, Daedalus after

| | |
|---|---|
| Skills | `/plan-alignment` → `/plan-write` → `/plan-edge-cases` → `/deps-audit` → `/plan-confidence` → `/plan-improve` |
| Rules | [`cycle-plan.md`](cycle-plan.md) · [`plan-confidence-golden-rule.md`](plan-confidence-golden-rule.md) · [`deps-audit-golden-rule.md`](deps-audit-golden-rule.md) · [`skills/_kit-rules/alignment-threshold.md`](../skills/_kit-rules/alignment-threshold.md) |
| Computes | `score_alignment.py`, `alignment_judge.py`, `build_walkthrough.py`, `run_structural.py` + 15 checks |
| Gate | Alignment ≥ 90% **and** a reviewer who is not the author. Here `alignment_judge.py` **may** sign — it reads the item's evidence, which exists independently of the brief |

The symmetry with BRAINSTORM is the design: at item level the judge signs *because
nobody is coming*; at product level a person signs *because that is the one place
they come*. Both apply the same rule — the author does not grade their own form.

### IMPLEMENT · Daedalus → the specialist

| | |
|---|---|
| Skill | `/implement` — TDD halt-loop with the wiring triad |
| Rules | [`cycle-implement.md`](cycle-implement.md) · [`testing.md`](testing.md) · [`architecture.md`](architecture.md) · [`error-handling.md`](error-handling.md) · [`loop-engine-convention.md`](loop-engine-convention.md) |
| Computes | `run_validation.py` orchestrating 17 checks — `check_tdd_shape`, `check_wiring`, `check_acceptance_criteria`, `coverage_gate`, `check_diff_cohesion`, `mini_review`, … |

### CODE-QUALITY · Daedalus → the specialist

| | |
|---|---|
| Skill | `/code-quality` — dead symbols, fabricated APIs, cross-package orphans, weak tests |
| Rules | [`cycle-code-quality.md`](cycle-code-quality.md) · [`code-quality-golden-rule.md`](code-quality-golden-rule.md) · `code-quality-{languages,thresholds,allowlist,baseline}.txt` — **the project's** |
| Computes | `run_code_quality.py` + per-language detectors (Go, Python, TypeScript, Rust) |

### REVIEW · Daedalus → the specialist

| | |
|---|---|
| Skill | `/review` — parallel agents in isolated worktrees |
| Rules | [`cycle-review.md`](cycle-review.md) · [`skills/_kit-rules/review-model-routing.txt`](../skills/_kit-rules/review-model-routing.txt) |
| Computes | `spawn_reviewers.py`, `consolidate_findings.py`, `detect_domain.py`, `check_finding_continuity.py`, `check_upstream_gate.py` |

**It never merges.** The merge belongs to `/release`, which reads this verdict as a
precondition — a reviewer that could merge on its own verdict would be grading its
own decision to proceed.

### RELEASE · Daedalus

| | |
|---|---|
| Skill | `/release` — semver from the CHANGELOG, `develop → main` PR, merged once the chain verifies |
| Rules | [`cycle-release.md`](cycle-release.md) · [`git-safety.md`](git-safety.md) · [`autonomy-envelope.md`](autonomy-envelope.md) floors 2 and 3 |
| Computes | `compute_next_version.py`, `bump_version.py`, `render_release_notes.py`, `changelog_section_nonempty.py`, `promote_unreleased.py` |

### ACCEPTANCE · Iris

| | |
|---|---|
| Skill | `/acceptance M<N>` — exercises the RELEASED delivery; the only gate that flips `[ ]` to `[x]` |
| Rules | [`cycle-acceptance.md`](cycle-acceptance.md) · [`acceptance-target.txt`](acceptance-target.txt) — **the project's** |
| Computes | `extract_acceptance_criteria.py`, `compute_acceptance_verdict.py`, `flip_milestone_checkbox.py` |

Only a milestone has a checkbox, so only a milestone reaches here. A `B-NNN`
released without one ends at `RELEASED`, and that is correct.

## How the domain specialists are reached

Not by invocation and not by judgement. The route is **deterministic** and starts
from a field the item already declares.

| Step | Mechanism | Failure |
|---|---|---|
| **1. Born** | `detect_domains.py --root . --write` reads the topology from disk and writes `rules/domain-routing.txt` | Empty table → G1 refuses *every* item, and the refusal is correct: with no table, routing would be a guess |
| **2. Filled in** | `scaffold_specialists.py --write` writes one `agents/<domain>.md` per domain, carrying what it measured and marking the invariants `OPEN` | `check_xrefs.py` WARNs on unfilled sections — a scaffold routes correctly and judges nothing, which reads as a specialist that is ready |
| **3. Reached** | The item declares `repo`; `mechanisms/cycle/route_domain.py` resolves it to exactly one domain | exit 1 = repo not in the table · exit 2 = table unreadable · **exit 3 = BROKEN ROUTE** |

**Exit 3 is what tests the role.** When a domain names a specialist nobody wrote,
Daedalus stops and does **not** stand in: a Tech Lead answering for a domain whose
invariants nobody wrote is asserting facts that were never checked. The item stops
and the broken route becomes work for Kairos.

### The line between the Tech Lead and the specialist

| Theirs — the domain specialist | Daedalus — the Tech Lead |
|---|---|
| the invariants of their repos, and why | the item's architecture across domains |
| the build and test commands that actually work there | whether the plan is coherent enough to build |
| the shape a real finding takes, and the false positives | which verdict routes where |
| whether a change is safe inside their blast radius | whether the item halts or continues |

He does not overrule a specialist inside their domain. Work spanning two domains is
two items — gate G3 — which is what keeps that boundary from becoming a negotiation.

## What runs across every phase

| Rule | Governs | Applied by |
|---|---|---|
| [`autonomy-envelope.md`](autonomy-envelope.md) | what the system decides alone and what it never touches — 5 floors + doctrine | Hermes |
| [`git-safety.md`](git-safety.md) | `workspace → develop → trunk`, no force-push, no `reset --hard` | `validate-command.py` (hook) |
| [`architecture.md`](architecture.md) · [`testing.md`](testing.md) · [`error-handling.md`](error-handling.md) | how code is written, tested, and how it fails | plan-confidence, implement, review |
| [`current-constraint.md`](current-constraint.md) | where the limit is — **a lens, never a gate**, and the file says why | discover-execute (advisory) |
| [`cycle-phases.txt`](cycle-phases.txt) · [`blocking-verdicts.txt`](blocking-verdicts.txt) | the declared chain, and the verdicts that hold an item | `check_phase_drift.py`, board, selector, watchdog |
| [`records-location.md`](records-location.md) · [`sop-schema.md`](sop-schema.md) · [`cycle-rule-schema.md`](cycle-rule-schema.md) | where output lives and what shape each contract takes | the `check_*.py` sweeps |
| [`english-only.md`](english-only.md) · [`public-copy.md`](public-copy.md) · [`parsimony-ladder.md`](parsimony-ladder.md) | repository language, honest copy, how much to build | PostToolUse hooks |

## The runtime layer

Eight hooks run outside the agent's turn — the layer that does not depend on the
agent remembering. Declared in `hooks/hooks.json`.

| Event | Hook | Effect |
|---|---|---|
| SessionStart | `sessionstart-context.py` | git state, active plan, loop state, **and the compact form of this map** |
| UserPromptSubmit | `userpromptsubmit-inject.py` | parsimony ladder + a lean pointer to the active plan, SHA256-attested |
| PreToolUse (Bash) | `validate-command.py` | **blocks** destructive git and commits on the trunk — exit 2 |
| PreToolUse (Edit/Write) | `boundary-check.py` | **blocks** writes to `study-material/` and into an installed kit |
| PostToolUse | `post-edit-check.py` · `public-copy-lint.py` · `english-only-check.py` | linting, honest copy, repository language — advisory |
| Stop | `stop-validation.py` | **blocks**: CHANGELOG and secret-leak are hard gates; TDD is a warning |
| PreCompact | `precompact-preserve.py` | snapshots plan and progress before compaction |

## Orchestrators and on-demand skills

| Skill | Role | Owner |
|---|---|---|
| `/idea-to-release` | chains discover → … → acceptance for **one** item, per [`cycle-idea-to-release.md`](cycle-idea-to-release.md) | Daedalus |
| `/pipeline` | **N** items at different stages at once, a lane each | Hermes |
| `/arch-check` | whether the repo has boundaries, whether they still fire | — |
| `/ast-grep` | structural search by AST shape, not by word | — |
| `/honesty-gate` | blocks a "production-ready" claim with no recorded evidence | — |
| `/quality-init` | emits quality hooks calibrated to the project's real p90 | — |
| `/skill-creator` | authors, improves and **measures** skills | — |

Above all of it sits `cycle-maintenance`, the macro loop: select (measured before
unmeasured, then oldest first), route, delegate, advance. **It never reports
"complete"** — a backlog is not a scope, and an empty one means nobody has looked
recently.

### The one cycle delivered from outside

[`cycle-judge-codex.md`](cycle-judge-codex.md) is a contract this repository
**consumes but does not implement**: the plugin ships separately and reads `plan`
artifacts by path convention. It is optional, and it is the orthogonal jury — a
second model reading the same artifacts, where **the disagreement is the signal**
rather than a failure to reconcile. Nothing in the chain above requires it; where
it is installed, a divergent verdict halts for adjudication.

## Why this file is checked rather than trusted

`skills/map.md` records the same lesson twice over: an index is the one document
nothing forces you to open when you add a file, so it drifts by default and reads
as complete while it does. The second time, four skills had **zero mentions in any
entry point** — on disk, passing every validator, unreachable.

So `mechanisms/gates/check_squad_map.py` compares this file against the directory in both
directions and runs inside `verify_ecosystem.py`. It deliberately does **not**
re-check what `check_skill_map.py` already owns; it checks what only this map
claims: the phases, the cycles, the kit agents and the hooks.

## Cross-references

- Which skill to reach for: [`skills/map.md`](../skills/map.md)
- The phase chain, machine-readable: [`rules/cycle-phases.txt`](cycle-phases.txt)
- The routing mechanism and how to derive specialists: [`agents/README.md`](../agents/README.md)
- What the system decides unattended: [`rules/autonomy-envelope.md`](autonomy-envelope.md)
- Where each rule belongs and why: [`rules/README.md`](README.md)
- The schema every cycle rule follows: [`rules/cycle-rule-schema.md`](cycle-rule-schema.md)
