# Cycle: DISCOVER

Source of Truth for the discovery cycle. Skills consume this; do not duplicate content into SKILL.md.

## Purpose

Measure a hypothesis against **our own system** and either prove it or kill it. Outputs an opportunity — evidence, blast radius, and a way to verify the fix — never code.

This cycle inverts its ancestor. In Cycle, DISCOVER studied **how others solved a problem** and produced a blueprint of external patterns; it explicitly forbade looking at your own code. The Squad maintains a running ecosystem, and for that work the question *"how did project X do it?"* is the wrong one — it produces imitation, not maintenance. The question here is *"what is actually true about our code and our runtime, and is it worth changing?"*

The rename from **blueprint** to **opportunity** is deliberate. A blueprint is a design to copy. An opportunity is a measured gap in something we already run.

**Killing an item is a successful outcome of this cycle, not a failure of it.** A run that measures honestly and finds nothing has protected the plan cycle from work that would have been justified by a hunch. That is the job.

## Pre-conditions

Invoke the chain below — entered at `/discover-plan B-NNN --mode {review|live-test|bug|evolve}` — when EITHER:

- A `B-NNN` item in `BACKLOG.md` has `status: raw` and is unclaimed, OR
- You are sweeping a domain for findings nobody has filed (`--sweep {domain}`).

Do NOT trigger DISCOVER for:

- **Studying how another project solved a problem.** This is the removed capability, not an oversight. The Squad justifies work by what is true in our system (`cycle-backlog.md` § Hard gates, G5). Reading someone else's code to learn a technique is fine and normal — it is simply not this cycle, and it is never the evidence.
- Locating a symbol in our own code. Use Grep/Glob.
- Anything answerable by reading our own `README.md` / `CLAUDE.md`.
- An item already `triaged`, `planned` or `shipped`. Re-measuring a closed item is how duplicate work enters.

## Chain

```
/discover-plan B-NNN --mode {mode}       (sweeps enter at /discover-execute --sweep {domain})
     ↓ (what will be measured, where, with which tool — the measurement plan)
/discover-edge-cases {slug}
     ↓ (what could make this measurement LIE — absorbed as MUST-FIX)
/discover-plan-confidence {slug}
     ↓ (gate on the measurement plan itself; INVALID returns to /discover-plan)
/discover-execute {slug}
     ↓ (runs the measurement → records/discoveries/opportunities/{slug}-opportunity.md)
     │                        └─ or → ITEM_KILLED, and the B-NNN block records kill_reason
/discover-confidence {slug}
     ↓ (scores the opportunity; INVALID returns to /discover-plan)
/discover-improve {slug}   [optional — only when the score is NEEDS_REVISION]
```

An opportunity is the terminal artifact. Distilling one into a reusable skill is out of cycle and optional: invoke the standalone `/skill-creator` on demand.

### Proportionality — the fast lane

The full six-phase chain is calibrated for `evolve` and for `--sweep`, where what will be measured is genuinely open. It is disproportionate for a reproduced bug.

**Fast lane** — `--mode bug` where a failing test already exists: phases 1–3 collapse. A test that fails on the current state **is** a stronger measurement plan than any document describing one, and it is verifiable by execution rather than by review. Enter at `/discover-execute` with the repro and the failing test as the plan.

The fast lane is unavailable when the repro is not yet a test. "I can reproduce it by hand" is a plan, not a measurement, and it goes through the full chain like anything else.

## Modes

Every mode measures **our** system. They differ in what counts as a measurement.

| Mode | Finds | Evidence contract (all mandatory) | Primary lie risk |
|---|---|---|---|
| `review` | A defect or violation visible in our code | `file:line` · the rule or principle violated · why it matters *here*, not in general | The code is dead, the caller never existed, or the shape is deliberate |
| `live-test` | Behaviour wrong in the running system | `METHOD URL -> status` · console output · trace id where available · timing · screenshot for UI | **Environment vs product** — a dev-environment fault reported as a product defect |
| `bug` | A reproduced defect | Numbered repro · **a test that FAILS on the current state** | The repro depends on local state nobody else has |
| `evolve` | Measured cost of the status quo | The measurement itself (N round-trips, N duplicated call sites, N ms, N manual steps) | The cost is real and trivial |

**`bug` has a hard floor: no failing test, no bug.** A defect nobody can express as a failing test is not yet understood well enough to fix, and the test is what proves the fix later. This is the same discipline `cycle-implement.md` enforces at RED — brought forward, because writing it here is what makes the plan honest.

**`live-test` refuses on a domain with no block in `rules/live-target.txt`.** Six of the eight domains have none, by design — a Go library, a Postgres extension and a Terraform module have no surface a browser can probe. Refusing is correct; improvising a probe to look thorough produces theatre.

`live-test` carries one obligation the others do not: **name the uncertainty between environment and product.** Whatever `rules/live-target.txt` declares is a dev environment, and dev environments break for reasons that have nothing to do with the code. An opportunity that cannot yet distinguish the two says so, in those words, rather than picking the more interesting explanation.

### Mode is reclassifiable

`suggested_mode` on the backlog item is the filer's guess (`rules/cycle-backlog.md` § Item schema). If measurement shows the hypothesis is a different shape — a "bug" that is really a micro-evolution, a "review" finding only observable at runtime — **reclassify and continue**. Record the reclassification and its reason in the opportunity. Forcing a measurement into the mode someone guessed at intake defeats the purpose of measuring.

## Phase contracts

| Phase | Input | Output | Hard gate |
|---|---|---|---|
| plan | `B-NNN` or domain + mode | measurement plan: what, where, which tool, what would falsify it | the plan names a tool that exists and a target that resolves |
| edge-cases | measurement plan | annotated plan with MUST-FIX items | every MUST-FIX has an answer or a stated open question |
| plan-confidence | annotated plan | score + verdict on the plan | no fabricated target; falsification criterion non-empty |
| execute | scored plan | opportunity **or** `ITEM_KILLED` | every evidence pointer resolves (G-E) |
| confidence | opportunity | score + verdict | INVALID returns to plan |
| improve (opt.) | NEEDS_REVISION opportunity | revised opportunity | bumped verdict on re-score |

## The four corners

Every opportunity populates four corners. An empty corner caps the score.

| Corner | Content |
|---|---|
| **Evidence** | The measurement, in the mode's contract above. Pointers must resolve. |
| **Constraint relation** | Does this **explore**, **subordinate**, **elevate** the declared constraint — or is it **local optimisation**? Cites `rules/current-constraint.md`. |
| **Blast radius** | What else this reaches. In a multi-repo ecosystem: the repos downstream of the one being changed. In a single repository: the modules — or, in a documentation repo, the documents — that cite what is being corrected. |
| **Verification** | How we will know the fix worked — tied to the item's `dod` — and where the limit plausibly moves next. |

**The Constraint relation corner is advisory and may be answered `unknown`.** We do not instrument flow across the ecosystem, and a corner that demanded a constraint claim against data that does not exist would be answered by assertion — the exact defect G5 refuses at intake. `unknown` is honest and complete; it neither weakens the opportunity nor creates debt. See `rules/current-constraint.md` for why this is a lens rather than a gate.

The **Blast radius** corner is the one whose shape depends most on the project. Where the repos form a dependency graph, it is measured across repositories, and a change at the root of that graph is a different proposition from one at a leaf. Where the project is a single repository, the same question is asked of modules or documents. What does not change is the demand: name what is reached, do not assert that nothing is.
## Verdicts

| Verdict | Meaning | Downstream |
|---|---|---|
| `SHIPPABLE` | Opportunity is measured, complete, and its pointers resolve | `/plan-write` |
| `SHIPPABLE_WITH_CAVEATS` | Complete, with stated open questions | `/plan-write`, caveats carried into the plan |
| `NEEDS_REVISION` | Recoverable via `/discover-improve` | loop |
| `INVALID` | Structural — a fabricated pointer, or an empty corner | back to `/discover-plan` |
| `AWAITING_REVIEW` | The opportunity is written and nothing has scored it. **Orthogonal to the four bands** — neither a failure nor a pass; the machine finished and the judgement has not started. Gate G-P already names this state; it was missing from this table until 2026-09-10, so `/discover-execute` could not close its own phase and emitted a completion promise as a verdict instead | `/discover-confidence` |
| `ITEM_KILLED` | Measured honestly; the hypothesis did not hold | Item → `killed` + `kill_reason`. **Chain ends. This is success.** |
| `AWAITING_HUMAN` | The phase ran and stopped at a gate only a person opens — a T3 boundary call, a sign-off, a dependency in another repository | **Emit it.** Without the event the work leaves no trace, and every reader sees an item nobody touched |

`ITEM_KILLED` is orthogonal to the other four: they grade a document, it reports an outcome. A killed item produces no opportunity to score.

## The review panel

**Decided 2026-09-08.** The document this phase produces is judged by **three
reviewers**, and **2 of 3 approvals** advance it. Below the majority it returns as
`NEEDS_REVISION` — a verdict that already exists and already holds an item, so no new
token was invented for a state the vocabulary already had.

| | |
|---|---|
| Who sits | [`rules/review-panel.txt`](review-panel.txt) — **the project's own specialists**, because which agents a project has and which models it can reach is not the kit's business |
| Convened here | `nemesis-claim-auditor` (does the evidence support the claim — verbatim what it decides), `leonardo-researcher` (the gap between what the decision needs and what was read), and the orthogonal `judge-codex:discover-judge` |
| What the kit imposes | Three seats for this phase; at least one from a recognised family **outside** the one the kit runs on; the author never sits |
| Assigns | [`mechanisms/cycle/convene_panel.py`](../mechanisms/cycle/convene_panel.py) — resolves each seat against the agents this project actually has, and writes the assignment the votes are checked against |
| Computes | [`mechanisms/cycle/review_panel.py`](../mechanisms/cycle/review_panel.py) |
| **Blocks** | [`mechanisms/gates/check_panel_approval.py`](../mechanisms/gates/check_panel_approval.py) — **a missing record is not an approval** |
| Premise | [`mechanisms/gates/check_panel_capability.py`](../mechanisms/gates/check_panel_capability.py), at intake |

**The reviewers are agents, not model strings.** Until 2026-09-09 a seat named a model
and a lens, which said how a reviewer would be reached and never who was reviewing —
and nothing convened them, so this section described a gate that no phase ran
([#65](https://github.com/paulohenriquevn/squad/issues/65)). A seat now names an agent
that must exist in the running project, and `convene_panel.py` refuses a seat it
cannot fill rather than quietly seating nobody.

**The record must match the assignment.** Convening buys nothing if the panel that
voted may differ from the panel that was convened: a document could be routed to the
specialists its content demands and signed off by three others. `review_panel.py`
refuses such a record, and the assignment comes from disk — never from the record,
which would let a document supply the very list it is checked against.

**Why a script cannot do this job.** ``/discover-confidence`` is deterministic and scores
STRUCTURE — pointers resolve, the shape is complete, the contract is satisfied. What it
cannot ask is whether evidence that *resolves* actually *supports* the conclusion drawn
from it. That question is what the panel is for, and it is the one place in this phase
where a second opinion buys something a rule cannot.

**Why the panel must not be one family.** Three Claudes asked three times are three
correlated opinions: a plausible fabrication that survives one tends to survive its
siblings, which is the single thing an orthogonal reviewer catches. An **unrecognised**
model supplies neither side — otherwise `--model anything` would prove orthogonality by
typing.

**An incomplete panel is not a rejection.** Two approvals out of two is not 2-of-3: the
threshold is over a FULL panel, so a missing reviewer is an abstention, and an abstention
approves nothing and rejects nothing. The panel did not convene, the item returns to the
registry with an `access` impediment (`halt_disposition.py`), and the queue takes the next
item. Collapsing the two would send an author to rewrite a document nobody found fault
with — or, far worse, let a panel of one report a majority.

**The dissent is kept.** A minority vote that loses is the most interesting thing in the
record, and `review_panel.py` reports it beside the outcome. This kit already argues the
point about Claude and Codex disagreeing in `cycle-judge-codex.md`: the disagreement is
the highest-value signal in the pipeline, and discarding it because it lost a vote throws
away what the panel was convened to produce.

## Hard gates

| # | Gate | Blocks on |
|---|---|---|
| G-E | **Evidence pointers resolve** (`check_evidence_pointers.py`, run by `run_opportunity_score.py`) | A cited `file:line` that does not exist, a URL never actually fetched, a trace id never observed, a test asserted to fail but never run. Fabricated evidence is the one unrecoverable defect in this cycle: everything downstream trusts it. |
| G-M | **Mode contract satisfied** (`check_opportunity_completeness.py`, run by `run_opportunity_score.py`) | The mode's mandatory evidence is incomplete — most often `bug` without a failing test. |
| G-L | **Live target declared** (`check_measurement_targets.py`, run by `run_measurement_plan_score.py`, at plan time) | `--mode live-test` on a domain with no block in `rules/live-target.txt`. |
| G-C | **Corners populated** (`check_corner_coverage.py`, run by `run_measurement_plan_score.py`) | Any of the four corners empty. `unknown` populates Constraint relation; it is an answer, not a blank. |
| G-K | **Kill is reasoned** — mechanised on two layers: `backlog_status.py` REFUSES a transition to `killed` without a `--kill-reason` (point of action), and `check_backlog_structure.py` reports `killed_without_reason` as MAJOR (after the fact). Both name this gate by id. _(not mechanized: debt since 2026-08-31 — the SUBSTANCE of the reason — nothing confronts what the reason claims against what was measured, and a `kill_reason` of "n/a" satisfies both layers)_ | `ITEM_KILLED` without a `kill_reason` naming what was measured and what it showed. An unexplained kill is indistinguishable from an abandoned run. |
| G-P | **Panel approved** (`check_panel_approval.py`) | A document no panel carried. Three states, not two: *returned* is `NEEDS_REVISION` and editing can lift it; *no record yet* is `AWAITING_REVIEW` — complete and unsigned, neither a failure nor a pass, and the action is to convene; *did not convene* — an absent reviewer, a voter nobody assigned — is `ITEM_IN_FLIGHT`, held on a material impediment. Sending the author to rewrite a document nobody found fault with is the wrong action in both. **A missing record fails**: a phase that skipped its panel must not be indistinguishable from one whose reviewers all approved. |

## Stop conditions

- Verdict `INVALID` → return to `/discover-plan` (the measurement plan was wrong, not necessarily the hypothesis).
- 3 consecutive iterations with no confidence improvement → return the item to the registry
  with the diagnosis on it and take the next one (`autonomy-envelope.md § A loop ran out of
  attempts`). Nothing here waits for a person.
- Measurement cannot be run at all (target unreachable, credential absent, tool missing) → **return the item to the registry with a retained impediment.** Do not substitute a weaker measurement, do not reason about what the measurement would probably have shown, and do not record `ITEM_KILLED` — nothing was measured, so nothing was disproved.

  This is the one shape in the whole DISCOVER→ACCEPTANCE span that legitimately reaches a
  person, and it reaches them **through the registry rather than by holding the session**: an
  absent target, credential or tool is `access` or `liveness` in
  [`decision-delegation.txt`](decision-delegation.txt), and authority does not conjure any of
  them. `halt_disposition.py` classifies it; the queue moves on.
- Either halt-loop emits BLOCKED → the cycle pauses; `/discover-confidence` must not honour the artifact.

## Halt-loop contracts

Two phases drive autonomous halt-loops via `ralph-loop:ralph-loop`, following the template in `rules/cycle-implement.md`: pre-flight guard against concurrent loops, formal stop conditions, post-promise sanity check, and an honest BLOCKED report over a false PASS.

- **`/discover-execute`** — completion promise `<promise>OPPORTUNITY_COMPLETE</promise>`, asserting that every plan question is `done` or `blocked` with a reason, every evidence pointer resolves on disk or in a recorded observation, all four corners are populated, and the mode contract is satisfied. The post-promise check re-verifies pointer integrity. Never emit on a partial state. `ITEM_KILLED` is emitted instead of the promise, with its `kill_reason`.
- **`/discover-improve`** — completion promise `<promise>OPPORTUNITY_IMPROVED</promise>`, asserting a re-run of the scorer in the emitting iteration reaches the target verdict. Partial improvement does not justify the promise.

## Anti-patterns

- **Discovery that turns into implementation.** The output is a document. An opportunity that already contains the patch has pre-empted the plan cycle and skipped its gates.
- **Fabricated evidence.** A plausible `file:line` nobody opened; a status code nobody requested; a test asserted to fail but never executed. This is the cycle's cardinal sin — everything downstream treats it as measured fact.
- **Prior art smuggled in as evidence.** "Project X does it this way" is not a measurement of our system. It may be true, useful, and the reason someone had the idea — it is still not evidence, and it cannot fill the Evidence corner.
- **Reporting a dev-environment fault as a product defect.** The declared live target breaks for its own reasons. Name the uncertainty instead of resolving it toward the more interesting answer.
- **Refusing to kill.** Sunk cost after a long measurement makes a weak finding look shippable. A run that kills an item did its job; a run that ships a hunch it failed to confirm did the opposite.
- **Filling Constraint relation with a confident claim nobody measured.** `unknown` is the honest default while `current-constraint.md` is undeclared.
- **Improvising a live probe on a domain with no declared target.** Produces the appearance of runtime evidence with none of the substance.
- **Sweeping without registering.** A `--sweep` finding that stays in the run's output and never reaches `BACKLOG.md` is the orphaned-finding failure the single registry exists to prevent.

## Output

- `records/discoveries/plans/{slug}-plan.md` — the measurement plan
- `records/discoveries/opportunities/{slug}-opportunity.md` — the terminal artifact
- `BACKLOG.md` — the `B-NNN` block updated: `status` → `triaged` with `evidence`, or `killed` with `kill_reason`. A `--sweep` appends new blocks with `source: discover-{mode}`.

The study zone the ancestor cycle used (`records/references/`, seeded at project inception and governed by a provenance rule) is **retired**: it existed to hold other people's code for imitation, which is the practice this cycle removed.

## Rollback

An opportunity that turns out wrong is simply not consumed downstream — supersede or delete the file under `records/discoveries/opportunities/`. The `B-NNN` item returns to `raw` so it can be re-measured, with a note recording that the first measurement was withdrawn and why. Do not silently reset it: an item that was measured, believed, and then withdrawn carries information a fresh-looking `raw` item does not.

## Cross-references

- Schema for cycle rules: `rules/cycle-rule-schema.md`
- Upstream (intake): `rules/cycle-backlog.md` — supplies the `B-NNN` hypothesis this cycle measures
- Downstream: `rules/cycle-plan.md` — consumes `triaged` items and their opportunities
- Live environment declaration: `rules/live-target.txt`
- Constraint lens (advisory): `rules/current-constraint.md`
- Skills: `skills/discover-plan/SKILL.md`, `skills/discover-edge-cases/SKILL.md`, `skills/discover-plan-confidence/SKILL.md`, `skills/discover-execute/SKILL.md`, `skills/discover-confidence/SKILL.md`, `skills/discover-improve/SKILL.md`
- Halt-loop template: `rules/cycle-implement.md`
- Optional skill distillation (out of cycle): `skills/skill-creator/SKILL.md`
