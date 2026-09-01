# Cycle: BACKLOG

Source of Truth for the intake cycle. Skills consume this; do not duplicate content into SKILL.md.

## Purpose

Register **one unit of maintenance work** against the Theo ecosystem, cheaply and before anyone has measured anything. Outputs a numbered item in `BACKLOG.md` — never a plan, never code, never evidence.

This is phase 0 of the Squad chain. It exists because the downstream cycle (`cycle-discover`) demands measured evidence for everything it accepts, and that demand, applied at intake, would silence the most valuable signal a maintenance team has: the hunch. *"the trace explorer feels slow"* is a legitimate thing to record and an illegitimate thing to plan against. BACKLOG separates the two — it takes the hunch, and hands DISCOVER the job of proving or killing it.

A backlog item is a **hypothesis with an owner and a closing criterion**. It is not a commitment.

## Pre-conditions

Invoke `/backlog-item {slug}` when ALL of:

- `BACKLOG.md` exists at the root of the governed scope — the umbrella when repos live below it, the repository itself when it is autonomous (created once by `/backlog-init`).
- There is one concrete thing to improve, fix, verify, or evolve in a repo that exists in the umbrella inventory.
- It maps to exactly one registered domain (see § Domain routing). Work spanning two domains is two items.

Do NOT trigger BACKLOG for:

- Work already in flight. Grep `BACKLOG.md` first — the dedup gate is mandatory, not advisory.
- A finding the sweep already produced. `/discover-execute --sweep` registers its own items with evidence attached; re-registering them by hand creates the duplicate the single-registry rule exists to prevent.
- "Project X does it this way." That is not an item. See § Hard gates, G5.
- A question about how our own code works. Read the code.

## Chain

```
/backlog-item {slug}                         ← phase 0 · INTAKE (human, cheap, hypothesis)
     ↓ (produces: B-NNN in BACKLOG.md · status: raw · evidence: none-yet)
/discover-plan B-NNN --mode {review|live-test|bug|evolve}
     ↓ (measures against OUR code/runtime)
     ├── evidence found  → status: triaged · evidence: <pointer>  → /plan-write
     └── nothing found   → status: killed   · kill_reason: <why>  → chain ends here
```

The second producer writes into the same registry without passing through this cycle:

```
/discover-execute --sweep {domain}     ← no prior item
     ↓ (registers findings directly)
B-NNN · source: discover-review · evidence: <file:line> · status: triaged
```

One file, one schema, two entry paths. A sweep finding skips intake because it arrives with the evidence intake is not allowed to require.

## Phase contracts

| Phase | Input | Output | Hard gate |
|---|---|---|---|
| intake | one-sentence description + slug | `B-NNN` block in `BACKLOG.md`, status `raw` | G1–G5 all pass |
| (handoff) | `B-NNN` | item claimed by `cycle-discover` | item is `raw` and unclaimed |

## Item schema

Every item is one `## B-NNN` block. Ids are monotonic, never reused, never renumbered — a killed item keeps its number so the audit trail survives.

```markdown
## B-014 — Reduce the trace explorer p95   [ ]

domain: <a domain from THIS project's routing table>
repo: <a repo from it>
suggested_mode: live-test
source: human
evidence: none-yet
why_now: the dashboard started loading a 30d trace window by default in 2026-07
status: raw
dod:
  - listing endpoint p95 below 800ms with a 30d window
  - regression covered by a test that fails on the current state
```

| Field | Required | Notes |
|---|---|---|
| `domain` | yes | routes to the specialist; must be a registered domain (G1) |
| `repo` | yes | must exist in the umbrella inventory (G1) |
| `suggested_mode` | yes | **a suggestion, not a decision** — DISCOVER may reclassify |
| `source` | yes | `human` \| `discover-review` \| `discover-live-test` \| `discover-bug` \| `discover-evolve` \| `live-incident` |
| `evidence` | yes | `none-yet` at intake; a pointer once DISCOVER measures |
| `why_now` | yes | what changed **in our system**; subject to G5 |
| `status` | yes | `raw` \| `triaged` \| `planned` \| `shipped` \| `killed` |
| `dod` | yes | ≥ 1 verifiable criterion (G4) |
| `kill_reason` | when `killed` | why the measurement did not support the hypothesis |
| `blocked_by` | when impeded | what stops the item from advancing — see below (G6, G7) |

`suggested_mode` being non-binding is deliberate. A hunch filed as a `bug` that measurement reveals to be a `evolve` must change mode without leaving the backlog — reclassification is a DISCOVER outcome, not a re-intake.

### Status transitions

```
raw ──/discover-execute measures──┬──> triaged ──/plan-write──> planned ──/release──> shipped
                                  │        ▲                    │
                                  │        └──── send-back ─────┘
                                  └──> killed (kill_reason mandatory)
```

`raw → planned` is forbidden. Nothing reaches a plan without passing DISCOVER's
measurement. `planned → triaged` is the send-back: a plan that did not survive
review returns to the stage that produces plans, not to intake.

`shipped` and `killed` are terminal. A killed item keeps its number forever.

**These transitions are written by `scripts/backlog_status.py`, not by hand.** That
script exists because of a measurement on 2026-08-30: `planned` was in this contract
and in zero items across every install — 22 `triaged`, 133 `shipped`, 11 `killed` in
one project, 3 `raw` and 2 `triaged` in another, and not one `planned` anywhere. The
cause was not discipline. Nothing wrote to `BACKLOG.md` at all, so every transition
was a human editing a line, and the middle one quietly stopped happening. No gate
could see it either: an item that skipped `planned` is indistinguishable from one
that has not reached it yet.

### Impediments

An item that discovers mid-flight that it needs another item — new or already filed —
files that item and records the dependency:

```markdown
status: planned
blocked_by: B-100
```

**`blocked` is a derived state, not a sixth status.** The stage stays where it was,
because the stage is what is needed to resume: an item that stalls at `planned` must
come back at `planned`, and a status that overwrote it would have destroyed the only
copy of that fact. A reader asking "what is the state of B-014" gets `blocked`; the
registry stores `planned` plus an edge, and computes the rest.

Deriving it also means it cannot rot. An item whose blockers have all shipped stops
being blocked at that instant, with nobody remembering to clear a flag.

**The edge is written on the blocked side only.** `blocks` — the reverse edge — is
computed by the index and never typed. Storing both directions stores one fact twice,
and the two copies diverge the first time someone edits in a hurry.

**Not every impediment is an item.** The value is prose that MAY name ids. When it
names them, they become verifiable edges; when it does not, it is still an
impediment — just one nothing here can resolve. This is the field as it was already
being used before it was specified: of the eight items carrying `blocked_by` when it
was measured, seven named a sponsor decision, a ratification, or a revocation in a
hosting panel, and exactly one named an item. A parser demanding `B-NNN` would have
called seven honest impediments malformed.

| Value | Edge | Resolves when |
|---|---|---|
| `B-100` | yes, verified | B-100 reaches `shipped` or `killed` |
| `B-100 — and the sponsor must ratify` | yes, plus prose | a human clears the line |
| `the sponsor must decide` | none | a human clears the line |
| `none` (or an absent line) | none | already unblocked |

An item may not ship while an impediment is live. `backlog_status.py` refuses it, and
`check_backlog_structure.py` reports the ones that got in by hand.

## Domain routing

`domain` is what assigns an item to a specialist. The table itself is **not in
this file** — it lives in `rules/domain-routing.txt`, and that separation is the
point.

This file is the kit's contract: fifteen sections describing what the intake
cycle produces and which gates block it, identical in every install. The routing
table is the opposite — it names WHICH REPOSITORIES EXIST in one project, so it
cannot be copied from anywhere and must be derived where it lives.

Keeping the two in one file cost three defects, all of the same shape:

- `hooks/boundary-check.sh` blocks `rules/*.md` as the kit's, so the kit
  prescribed writing to a file it forbade editing — and the write landed anyway,
  through `Path.write_text`, which no hook watches.
- The section had to be replaced by regex on every re-derive, and the regex took
  the invariants written beside it. Measured on an adopter: 45 lines to 12, while
  `route_domain.py` went on enforcing a rule no file stated.
- A reinstall had to perform surgery to keep the consumer's table, and did it in
  one of its two modes.

`rules/*.txt` is already where project configuration lives: the boundary guard
allows it, and a reinstall preserves it. Moving the table there deletes all three
problems instead of guarding against each.

### Derive yours

```bash
python3 .claude/skills/backlog-init/scripts/detect_domains.py --root . \
  --write .claude/rules/domain-routing.txt
```

The script reads the topology from disk — not from an inventory, not from a
`CLAUDE.md`. Then write the specialist file it names, under `.claude/agents/`.

While the table is empty, `/backlog-item` refuses every item. That refusal is
correct: with no table, routing would be a guess.

## Routing invariants

**This section is deliberately outside `## Domain routing`, and the separation is load-bearing.** `detect_domains.py --write` replaces everything between that heading and the next `##` — `^##\s+Domain routing\b.*?(?=^##\s|\Z)` under DOTALL. What lives inside that span is bootstrap prose, which is supposed to expire the moment it runs; what lives here is contract, which never does. Do not move these paragraphs back up, and do not demote this heading to `###`: the regex only stops at a `##`.

Both paragraphs were inside the span once. Running the command this very file prescribes deleted them — measured on an adopter, the section went from 45 lines to 12 — and `route_domain.py` kept enforcing a rule no file stated any more. That is the inverse of a fabricated mechanism: a real gate whose contract is written nowhere, which `rules/cycle-rule-schema.md` exists to prevent in the other direction.

**One repo, one domain.** `scripts/route_domain.py` enforces the invariant: listing the same repository under two domains makes routing depend on dict iteration order, and the same item starts routing differently between runs. When one repository holds two genuinely distinct things — a service and the dashboard that consumes it, in the same checkout — separate them by path (`repo` and `repo/subdir`), never by repeating the bare name in both rows.

**Record the divergence instead of deleting it.** A repository the inventory names and disk does not have should stay listed, marked as having no checkout: an item filed against it routes nowhere, and seeing that written down is cheaper than discovering it through the refusal.

## Verdicts

| Verdict | Meaning | Downstream action |
|---|---|---|
| `ITEM_REGISTERED` | Item written to `BACKLOG.md` as `raw` | Available for `cycle-discover` |
| `ITEM_MERGED` | Dedup gate matched an open item; the new context was folded into it | No new id; the existing `B-NNN` proceeds |
| `ITEM_REJECTED` | Outside the ecosystem, or G5 refused it | Nothing written; the reason is surfaced to the human |

There is no "with caveats" band: an item is either in the registry or it is not.

## Hard gates

| # | Gate | Blocks on |
|---|---|---|
| G1 | **Domain + repo resolve** (run by `skills/backlog-item/scripts/check_intake_gates.py`, which delegates to `scripts/route_domain.py`) | `domain` not in the registered set, or `repo` not in the umbrella inventory. An item nobody owns is an item nobody does. |
| G2 | **Dedup search ran** (`check_intake_gates.py`; running it IS the evidence) | No search of `BACKLOG.md` performed before writing. A collision on an open item forces `ITEM_MERGED`. |
| G3 | **Single domain** _(not mechanized: judgement, by decision — deciding that a description spans two domains is not something a regex settles, and the evals cover it instead)_ | The description spans two domains. Split it; one item, one specialist. |
| G4 | **Verifiable DoD** _(not mechanized: judgement, by decision — `check_criterion_executability.py` does the equivalent one phase later, against a plan; at intake an item is a hypothesis and a strict falsifiability check would silence the hunch)_ | Zero `dod` bullets, or every bullet unfalsifiable ("melhorar a performance"). Without a closing criterion the item never closes. |
| G6 | **Impediment edges resolve** (`check_backlog_structure.py`) | `blocked_by` names an id no block defines, or an item names itself. An edge pointing at nothing never resolves. |
| G7 | **No impediment cycle** (`check_backlog_structure.py`) | A ring of `blocked_by` edges. Every item in it waits for another in it, so none can ever ship. This gate did not exist while items were independent; `blocked_by` gave them edges and brought it back. |
| G5 | **No prior-art justification, and no fabricated local one** _(not mechanized: judgement, by decision — the keyword heuristic raises the question and the human decides; automating the refusal would reject an item that merely mentions another project)_ | `why_now` justifies the item by what another project does rather than by something that changed in our system. This is the Squad signature rule (Unbreakable Rule: evidence is ours or it is not evidence). Reject and ask for the local reason. **The second half was measured on 2026-08-28 and is the harder case:** given this item under time pressure, a smaller model refused the prior-art justification and then wrote a local one it had invented — *"shutdown is scattered, error propagation is unclear, testing is brittle"*, none of it observed. A fabricated local problem passes review more easily than a cited blog post, so refusing the appeal to authority is not enough: the replacement must name something someone measured, or the item becomes a spike that measures it. See `wiki/references/judgement-gates-are-insurance.md`. |

G1, G2, G6 and G7 are mechanizable and are now mechanized; G3, G4 and G5 are judgement and stay conversational, covered by the skill's eval battery — automating them would produce verdicts about language, not about the work.

G5 does not forbid *knowing* how others solved a problem — it forbids that knowledge from being the **justification** for the work. "We need caching because project X has it" is rejected. "We need caching because the endpoint makes 4 round-trips per request" is accepted, whether or not project X inspired the look.

Intake deliberately has **no evidence gate**. Requiring evidence here would collapse BACKLOG into DISCOVER and lose the hunch.

## Anti-patterns

- **Intake that turns into planning.** The output is a registry block. Solution design belongs downstream; an item that already prescribes the fix has pre-empted the measurement.
- **Evidence theatre at intake.** Inventing a plausible `file:line` so the item "looks solid". `evidence: none-yet` is the honest and correct value for a hunch — DISCOVER fills it in or kills the item.
- **Renumbering.** Reusing the id of a killed item, or resequencing after a purge. The number is the audit trail; a killed `B-007` stays `B-007` forever.
- **Registering the sweep's output by hand.** Duplicates what `--sweep` already wrote, with weaker evidence.
- **Multi-domain items.** "Improve ecosystem observability" is a program, not an item. It routes to nobody and closes never.
- **`dod` that restates the title.** "DoD: the trace explorer being faster" is the title again, not a criterion.
- **Writing `blocked` into `status`.** It destroys the stage the item must resume at, and then needs a second edit to clear — which nobody makes.
- **Writing the reverse edge by hand.** `blocks:` is derived. Typing it creates a second copy of one fact, and the copies diverge.
- **Leaving `blocked_by` on a closed item.** The registry then tells everyone after you that finished work is stuck.
- **Blocking on an item nobody filed.** "Blocked by the auth rework" with no `B-NNN` and no block is a wish, not an edge.
- **Treating `suggested_mode` as binding.** It is the filer's guess. Locking DISCOVER to it defeats the purpose of measuring.

## The index that opens the registry

`BACKLOG.md` MUST carry an `## Index` section immediately before the item blocks, listing **every**
item — one row each, linked to its own detail block — grouped into three buckets:

| Bucket | Statuses | The question it answers |
|---|---|---|
| **Open** | `raw`, `triaged` | registered, measured or not, but nothing is being built |
| **In flight** | `planned` | a plan exists; work is under way |
| **Closed** | `shipped`, `killed` | the chain ended — and `killed` is a *successful* ending |

`triaged` sits under **Open** deliberately. Measurement has run, but no plan exists, so nothing is
in flight; folding it into the in-flight count would make that number answer a different question
than the one people ask of it.

**The index is generated, never written.** `skills/backlog-review/scripts/backlog_index.py --write`
derives it from the blocks; `--check` exits 1 when it has drifted. `check_backlog_structure.py`
reports `index_stale` (major) when the file's index does not match the one the generator would
produce, and treats **absent as stale** — otherwise a registry opts out of the check by never
having the section, which is how the four registries in this ecosystem reached 592 items with
zero index rows.

This is not ceremony. A summary that disagrees with the items below it is worse than no summary:
a reader stops at the summary, so a wrong one reports absence where evidence exists — the same
failure `rules/records-location.md` records for a split records. Nothing forces the
index and the items to move together, so the gate is what keeps them honest.

## Output

- `BACKLOG.md` at the umbrella root — the single registry, spanning all repos in the inventory.
- `records/backlog/{slug}-intake.md` — the intake grill log (one entry per answered question, with the G5 decision recorded).

The registry lives at the root of the governed SCOPE and not scattered below it, because a maintenance team asking "what is pending?" must have exactly one place to look. Per-directory backlogs inside one scope re-create the orphaned-findings problem the single-registry rule exists to solve.

What this never meant is "an umbrella is required". An autonomous repository is its own scope and keeps its own registry — `theokit-sdk` holds 88 items about `theokit-sdk`, and asking it to file them in a parent directory that is nobody's repository would put the registry outside the thing it governs.

## Rollback

An item registered in error is marked `status: killed` with a `kill_reason` — never deleted, never renumbered. If it was already `triaged`, the evidence DISCOVER attached stays on the block: knowing that something was measured and then dropped is worth more than a clean file.

## Cross-references

- Schema for cycle rules: `rules/cycle-rule-schema.md`
- Skill: `skills/backlog-item/SKILL.md`
- Bootstrap (once, at adoption): `skills/backlog-init/SKILL.md`
- Live environment declaration consumed by `/discover-execute (live-test mode)`: `rules/live-target.txt`
- Downstream: `rules/cycle-discover.md` — measures the hypothesis and flips the item to `triaged` or `killed`
- Then: `rules/cycle-plan.md` — consumes `triaged` items
- Branching contract for the registry commit: `rules/git-safety.md`
