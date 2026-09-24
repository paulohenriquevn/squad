# Cycle: BACKLOG
<!-- rule-id: SQ-CYC-03 -->

Source of Truth for the intake cycle. Skills consume this; do not duplicate content into SKILL.md.

## Purpose

Register **one unit of maintenance work** against the governed ecosystem, cheaply and before anyone has measured anything. Outputs a numbered item in `BACKLOG.md` — never a plan, never code, never evidence.

This is phase 0 of the Squad chain. It exists because the downstream cycle (`cycle-discover`) demands measured evidence for everything it accepts, and that demand, applied at intake, would silence the most valuable signal a maintenance team has: the hunch. *"the trace explorer feels slow"* is a legitimate thing to record and an illegitimate thing to plan against. BACKLOG separates the two — it takes the hunch, and hands DISCOVER the job of proving or killing it.

A backlog item is a **hypothesis with an owner and a closing criterion** — until it is
approved. `raw` and `triaged` are hypotheses, and killing one is the cycle working: the
measurement did not support the hunch, and the number stays as the record that it was
asked. `approved` is where that stops. From there the item is a **commitment**: somebody
with the authority decided it will be done, and reversing that is a decision rather than
a measurement.

The distinction is not decoration. It changes what killing costs — `killed` from
`approved` or `planned` requires naming who reversed the decision and why, and the
mechanism refuses without it. Before approval, `kill_reason` records what the evidence
showed; after, it records what changed someone's mind.

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
     ├── evidence found  → status: triaged · evidence: <pointer>
     │        ↓
     │   /backlog-approve            ← THE DECISION, recorded · status: approved
     │        ↓                        a person ticks and signs; nothing else writes it
     │   /plan-write
     └── nothing found   → status: killed   · kill_reason: <why>  → chain ends here
```

`triaged → /plan-write` was the chain as written until 2026-09-11, and it skipped the
gate this same document calls a commitment. Measured consequence: `approved` stood at
zero across 325 items while 243 reached `shipped`. A diagram that routes around a gate
is how a gate stops existing.

The second producer writes into the same registry without passing through this cycle:

```
/discover-execute --sweep {domain}     ← no prior item
     ↓ (registers findings directly)
B-NNN · source: discover-review · evidence: <file:line> · status: approved
                                         approved_by: system/autonomous-sweep
```

One file, one schema, two entry paths. A sweep finding skips intake because it arrives with the evidence intake is not allowed to require.

### An item the system found is approved when it is filed

**Decided 2026-09-14.** An item arriving through the sweep is born `approved`, and the
decision is attributed to the system rather than to a person.

The argument is narrow and it is about WHERE the consent was given. Running the loop
unattended IS the decision to act on what the loop finds: a sweep is not a proposal
awaiting an answer, it is the execution of an answer already given. Requiring a person
per finding does not add a decision — it withdraws the one already made, and it makes
the autonomy conditional on somebody being awake.

**What this deliberately does NOT change.** An item whose `source` is `human` is born
`raw` and still needs the decision. `/backlog-approve` renders only those, because a
person deciding what a person asked for is the case the gate was built for.

**`approved_by` is the field that keeps the two apart**, for the same reason
`signed-by: human/…`, `signed-by: peer/…` and `signed-by: judge/…` are three different
claims in a brief:

| `signed-by` | Means | Accountable by |
|---|---|---|
| `human/<name>` | a person read it and committed to it | being a person |
| `peer/<session> (what it verified)` | ANOTHER session measured something about it independently | the measurement named in the parentheses |
| `judge/<name>` | a judge ran its contract over it | the contract it ran |

**A peer signature must say what it verified, and is refused without it.** A person is
accountable by being a person and a judge is named by the contract it ran against; a peer
is another agent with no contract binding it to this document, so the measurement beside
the name is the entire value of the signature. `squad/signoff.py` reports an unqualified
peer separately rather than dropping it — a correctable mistake a reader cannot correct if
they never see it.

**A peer is not a human and does not become one.** `human_signed` stays false while a peer
signer is present, because the weakest signer decides. Decided 2026-09-22, after three
sessions spent a day measuring defects in each other's work with nowhere to record that it
had happened.

| `approved_by` | Means |
|---|---|
| `human/<name>` | a person read the item and committed to it |
| `system/autonomous-sweep` | the loop filed it under a standing authorisation |

They are not worth the same, and a reader must be able to tell without opening a second
file. A registry where everything is `system/…` is a registry nobody has read — which is
a legitimate state to be in, and an illegitimate one to be in unknowingly.

**The cost, stated rather than discovered later.** A loop that approves its own findings
can feed itself: a sweep produces items, working them produces sweeps, and nothing in
this contract bounds that. The bound is the person reading `approved_by` counts and
deciding the loop has found enough. `check_chain_preconditions.py` reports the split so
the number is in front of whoever starts the next run.

## Phase contracts

| Phase | Input | Output | Hard gate |
|---|---|---|---|
| intake | one-sentence description + slug | `B-NNN` block in `BACKLOG.md`, status `raw` | G1–G5 all pass |
| (handoff) | `B-NNN` | item claimed by `cycle-discover` | item is `raw` and unclaimed |

## Item schema

Every item is one `## B-NNN` block. Ids are monotonic, never reused, never renumbered — a killed item keeps its number so the audit trail survives. **The order the blocks sit in the file is not part of this**: newest-first and oldest-first both satisfy it, because the rule is about the values assigned over time. A checker sees one snapshot and cannot observe renumbering at all, so what is enforced is the observable half — no id appears twice (`duplicate_id`).

**The header, exactly.** `## B-NNN — Title`, where the separator may be an em dash, an
en dash or a plain hyphen — all three are accepted, because six readers each carried
their own pattern and three of them refused the hyphen. An item written that way entered
the approval brief and was invisible to `backlog_status.py`, the only module allowed to
write its status; worse, a header no parser recognises does not OPEN a block, so the
unseen item's fields were read as the previous item's and produced three false blockers
on its neighbour. `squad/backlog.py` is the one parser now.

**The id carries at least three digits.** `B-015`, not `B-15`. The block parses either
way on purpose — a header skipped takes the next item's fields with it — but a shorter
id is unreachable: `blocked_by: B-15` names no edge, and the writer refuses it on the
command line. `check_backlog_structure.py` reports `malformed_id`, and the fix is
zero-padding, which is the same number written correctly rather than a renumbering.

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
| `source` | yes | `human` \| `discover-review` \| `discover-live-test` \| `discover-bug` \| `discover-evolve` \| `live-incident` \| `external-blocker` — the last one is not work, see § An impediment nobody here can clear **`live-incident` also puts the item in SELECT's obligation band** (`select_backlog_item.is_obligation`): it is ordered ahead of everything else because it is costing while it waits, not merely waiting. That band covers this value and nothing else — a security finding or a legal obligation belongs there by the same argument and the registry has no field that identifies one, so the claim stops where the schema does |
| `evidence` | yes | `none-yet` at intake; a pointer once DISCOVER measures |
| `why_now` | yes | what changed **in our system**; subject to G5 |
| `approved_by` | when `status` is `approved` or past it | `human/<name>` or `system/autonomous-sweep`. Who made the commitment. A bare `approved` with no attribution predates this field; it is not evidence that a person decided |
| `subject` | no, and `product` is assumed | `product` \| `kit` — which system this item CHANGES, which is a different question from what kind of work it is. **`subject: kit` in a project that consumes the kit is a blocker** (`check_backlog_structure`): the item cannot close there, because a `.claude/` is not versioned, so a fix written in it protects one machine and the next install overwrites it — file it in the kit's own tracker and kill this one naming where it went. In the kit's OWN repository the same value is correct, and `squad.layout.has_kit` is what tells the two apart. Optional because 159 items predated it on the registry that motivated it, and a required field that fires on every existing block is a gate somebody switches off. An item that declares nothing and whose evidence names only kit paths gets an ADVISORY finding, never a failure |
| `traces_to` | when the project declares objectives | the `OBJ-N` ids this item serves, comma-separated. Required once `.squad/wiki/product/objectives.md` exists; absent and unenforced before that, because a project that never ran `/brainstorm-objectives` has nothing to trace to |
| `status` | yes | `raw` \| `triaged` \| `approved` \| `planned` \| `shipped` \| `killed` |
| `dod` | yes | ≥ 1 verifiable criterion (G4) |
| `kill_reason` | when `killed` | before approval: why the measurement did not support the hypothesis. After: **who reversed the decision, and what changed** |
| `blocked_by` | when impeded | what stops the item from advancing — see below (G6, G7) |
| `supersedes` | when re-filing a `killed` item | the id this one replaces — see *Lineage* below |
| `regression_of` | when a `shipped` item's problem returned | the id that shipped and came back — see *Lineage* below |

`suggested_mode` being non-binding is deliberate. A hunch filed as a `bug` that measurement reveals to be a `evolve` must change mode without leaving the backlog — reclassification is a DISCOVER outcome, not a re-intake.

### Status transitions

```
                  ┌──────── hypothesis ────────┐┌───────── commitment ─────────┐

raw ──measures──┬──> triaged ──approves──> approved ──/plan-write──> planned ──> shipped
                │        ▲                     │            ▲            │
                │        └───── send-back ─────┘            └── send-back┘
                └──> killed                              killed (who reversed it, and why)
                     (the measurement did not support it)
```

`raw → planned` and `triaged → planned` are forbidden. Nothing reaches a plan without
passing DISCOVER's measurement AND being approved — the two are separate questions, and
collapsing them is what let 174 items in one registry produce exactly 2 `planned`.

`approved → triaged` is the send-back for a decision withdrawn before any plan existed.
`planned → approved` is the send-back for a plan that did not survive review: the
decision to do the work still stands, only the plan failed.

**Killing after approval is not the same act as killing before it.** Before, the item was
a question and the measurement answered it. After, someone had decided, and `kill_reason`
must say who is reversing that and what changed — the mechanism refuses a bare reason on
an item past `triaged`.

`shipped` and `killed` are terminal. A killed item keeps its number forever.

**These transitions are written by `mechanisms/cycle/backlog_status.py`, not by hand.** That
script exists because of a measurement on 2026-08-30: `planned` was in this contract
and in zero items across every install — 22 `triaged`, 133 `shipped`, 11 `killed` in
one project, 3 `raw` and 2 `triaged` in another, and not one `planned` anywhere. The
cause was not discipline. Nothing wrote to `BACKLOG.md` at all, so every transition
was a human editing a line, and the middle one quietly stopped happening. No gate
could see it either: an item that skipped `planned` is indistinguishable from one
that has not reached it yet.

**`approved` was in the same condition, and for the same reason.** Measured on
2026-09-11 across four registries: 325 items, 243 of them `shipped`, and **zero** at
`approved` — the gate this contract calls a commitment had never been crossed. Nothing
was wrong with the rule; nothing asked for the decision. The only mention of
`--to approved` anywhere in the kit was a line of prose, and a status nothing asks for
is a status nobody writes.

**`traces_to` had the same disease and a worse prognosis.** It was read by
`build_agenda.py`, described in `agents/kairos-product-owner.md`, and pointed at ids that
`/brainstorm-objectives` genuinely produces — and it was written **zero times in 651
items across ten registries**, because this table never listed it and `/backlog-item`
never asked. A field read by one consumer and written by no producer is not a schema; it
is a plan somebody had. It is in the table above now, and Q5 of the intake grill asks
for it.

What the link buys is the one question a registry cannot answer about itself. Reading
the items tells you whether you want each of them; it cannot tell you what is **missing**,
because an item nobody wrote is invisible to any report rendered from the items.
`skills/backlog-approve/scripts/check_objective_coverage.py` computes the three states
the link makes visible: an objective no item serves (the gap), an item serving no
objective (the drift), and a citation pointing at an id that is gone (the rot). With no
objectives document it reports NOT MEASURED and names the document, rather than calling
every item an orphan against a standard the project never adopted.

`skills/backlog-approve` is what asks.

`skills/as-is-to-be` reads the same registry for a different question. An item's
`evidence` is a measurement of the present and its `dod` is a falsifiable statement
about the future, so the pair is a gap analysis that was already written down and
already gated — nothing was added to the schema to produce it. It answers *what will we
have*; the brief answers *is this what I want*, and only the second writes a status. It renders the registry as one page carrying, per
item, what it claims, what changed that makes it worth doing now, how it closes, and
whether the files its `evidence` cites are still on disk; a person ticks what they
commit to and signs; `apply_approval.py` then moves exactly those, through
`backlog_status.py` and never around it. Unticked is not rejected — it is work nobody
has committed to yet, which is the honest state for it.

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

#### An impediment nobody here can clear

Row three is the common case and the weak one. Measured: **seven of the eight items
carrying `blocked_by` named a sponsor decision, a ratification, or a revocation in a
hosting panel** — none of them an id. `parse_blocked_by` says what that costs in its own
words: *"nothing in this repository can tell you whether a sponsor has decided."* Such an
impediment resolves only when somebody remembers to delete the line, is invisible to G6
and G7 because there is no edge to verify, and appears in no report as a thing that is
itself pending.

**File the constraint as an item.** `source: external-blocker` registers it as an
ordinary `B-NNN`, so `blocked_by: B-900` is a verifiable edge and closing the stub frees
every item naming it **with no second edit** — the property prose could never have.

| | An external blocker |
|---|---|
| What it is | a constraint outside this repository: a sponsor decision, a ratification, a vendor fix, a regulatory hold |
| What closes it | somebody outside acting. Then it goes `shipped` (they did it) or `killed` (they will not) |
| Selected as work | **never.** `select_backlog_item.py` skips it, and asking for it by name returns `ITEM_EXTERNALLY_BLOCKED` |
| `suggested_mode` | not required — it never reaches DISCOVER |
| `traces_to` | not required — it is not work, so it serves no objective |
| Everything else | an ordinary item: an id, a `why_now`, a `dod` naming what would close it, and a place in the index |

The shape is adapted from [`gringolito/github-backlog-management`](https://github.com/gringolito/github-backlog-management-skill)
(cross-read 2026-09-20), whose `/add-external-blocker` files the constraint as a stub
issue — on the board, never milestoned, skipped by execution — and registers it as a real
dependency. The mechanism here is ours, because the registry is a file rather than the
GitHub API.

**A stub still closes honestly.** `shipped` means the outside thing happened; `killed`
means it will not, and the items it held need another way through. Leaving it open
forever is the same lie as prose, with a number attached.

An item may not ship while an impediment is live. `backlog_status.py` refuses it, and
`check_backlog_structure.py` reports the ones that got in by hand.

### Lineage

An item may be the descendant of one that already closed. Two fields say so, and the
dedup gate at intake is what produces them: a search hit on a `killed` item prescribes
`supersedes`, a hit on a `shipped` item prescribes `regression_of`
(`check_intake_gates.ACTION_BY_STATUS`). A hit on an item that is still **open** produces
neither — it folds in as `ITEM_MERGED` and no new id is allocated.

| Field | Points at | Means |
|---|---|---|
| `supersedes` | an item that is `killed` | the hypothesis was measured, did not hold, and something has changed since |
| `regression_of` | an item that is `shipped` | the work was delivered and the problem came back |

**Both fields were specified here only from 2026-09-09.** Before that they lived in
`skills/backlog-item/SKILL.md`, which is where they are PRODUCED rather than where they
are stored, and `cycle-maintenance.md` pointed readers there for the specification of a
registry field — the inversion of this file's own opening rule. The consequence was
mechanical: `blocked_by` carried five deterministic findings and these two carried none,
so `supersedes: B-999` naming an id nothing defines passed clean. That is the defect G6
exists to catch on the other edge (kit#55).

**Each field is a claim about a state, so the claim is checked.**
`check_backlog_structure.py` reports `lineage_missing` when the named id is undefined or
is the item itself, and `lineage_wrong_status` when the target exists but is not in the
terminal state the field asserts.

**There is deliberately no cycle gate here.** A lineage edge points only at a terminal
item, and a terminal item is not reopened, so a ring is unreachable — G7 has no analogue.

**Re-filing without the link is what the gate prevents.** A hypothesis killed in April
can be legitimately re-filed in August; the edge is the difference between doing that
knowingly and doing it because nobody looked.

## Domain routing

`domain` is what assigns an item to a specialist. The table itself is **not in
this file** — it lives at `.squad/domain-routing.txt`, resolved by
`squad.paths.write_routing_table` rather than spelled by each reader, and that
separation is the point.

This file is the kit's contract: fifteen sections describing what the intake
cycle produces and which gates block it, identical in every install. The routing
table is the opposite — it names WHICH REPOSITORIES EXIST in one project, so it
cannot be copied from anywhere and must be derived where it lives.

Keeping the two in one file cost three defects, all of the same shape:

- `hooks/boundary-check.py` blocks `rules/*.md` as the kit's, so the kit
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
  --write
```

The script reads the topology from disk — not from an inventory, not from a
`CLAUDE.md`. Then write the specialist file it names, under `.claude/agents/`.

While the table is empty, `/backlog-item` refuses every item. That refusal is
correct: with no table, routing would be a guess.

## Routing invariants

**This section is deliberately outside `## Domain routing`, and the separation is load-bearing.** `detect_domains.py --write` replaces everything between that heading and the next `##` — `^##\s+Domain routing\b.*?(?=^##\s|\Z)` under DOTALL. What lives inside that span is bootstrap prose, which is supposed to expire the moment it runs; what lives here is contract, which never does. Do not move these paragraphs back up, and do not demote this heading to `###`: the regex only stops at a `##`.

Both paragraphs were inside the span once. Running the command this very file prescribes deleted them — measured on an adopter, the section went from 45 lines to 12 — and `route_domain.py` kept enforcing a rule no file stated any more. That is the inverse of a fabricated mechanism: a real gate whose contract is written nowhere, which `rules/cycle-rule-schema.md` exists to prevent in the other direction.

**One repo, one domain.** `mechanisms/cycle/route_domain.py` enforces the invariant: listing the same repository under two domains makes routing depend on dict iteration order, and the same item starts routing differently between runs. When one repository holds two genuinely distinct things — a service and the dashboard that consumes it, in the same checkout — separate them by path (`repo` and `repo/subdir`), never by repeating the bare name in both rows.

**Record the divergence instead of deleting it.** A repository the inventory names and disk does not have should stay listed, marked as having no checkout: an item filed against it routes nowhere, and seeing that written down is cheaper than discovering it through the refusal.

## Verdicts

| Verdict | Meaning | Downstream action |
|---|---|---|
| `ITEM_REGISTERED` | Item written to `BACKLOG.md` as `raw` | Available for `cycle-discover` |
| `ITEM_MERGED` | Dedup gate matched an open item; the new context was folded into it | No new id; the existing `B-NNN` proceeds |
| `ITEM_REJECTED` | Outside the ecosystem, or G5 refused it | Nothing written; the reason is surfaced to the human |
| `ITEM_EXTERNALLY_BLOCKED` | The id asked for records a constraint nobody here can clear (`source: external-blocker`) | Nothing to do here. It closes when whoever owns it acts, and every item naming it is freed with no second edit |

There is no "with caveats" band: an item is either in the registry or it is not.

## Hard gates

- **An open item's cited pointers must resolve** — `mechanisms/gates/check_evidence_freshness.py`. Evidence AGE is reported and never fails: a measurement taken a while ago about something nobody has touched is still true, and failing on age trains people to re-measure on a calendar rather than on a reason. A cited path that resolves nowhere is a different fact — the next reader follows it, finds nothing, and cannot tell whether the finding moved or was never real. Scoped to `triaged` and `approved`, the items about to be planned against; a settled item's pointers are history and may name a tree that has since moved.


| # | Gate | Blocks on |
|---|---|---|
| G1 | **Domain + repo resolve** (run by `skills/backlog-item/scripts/check_intake_gates.py`, which delegates to `mechanisms/cycle/route_domain.py`) | `domain` not in the registered set, or `repo` not in the umbrella inventory. An item nobody owns is an item nobody does. |
| G2 | **Dedup search ran** (`check_intake_gates.py`; running it IS the evidence) | No search of `BACKLOG.md` performed before writing. A collision on an open item forces `ITEM_MERGED`. |
| G3 | **Single domain** _(not mechanized: judgement — deciding that a description spans two domains is not something a regex settles, and the evals cover it instead)_ | The description spans two domains. Split it; one item, one specialist. |
| G4 | **Verifiable DoD** _(not mechanized: judgement — `check_criterion_executability.py` (run by `run_structural.py`) does the equivalent one phase later, against a plan; at intake an item is a hypothesis and a strict falsifiability check would silence the hunch)_ | Zero `dod` bullets, or every bullet unfalsifiable ("melhorar a performance"). Without a closing criterion the item never closes. |
| G6 | **Impediment edges resolve** (`check_backlog_structure.py`) | `blocked_by` names an id no block defines, or an item names itself. An edge pointing at nothing never resolves. |
| G7 | **No impediment cycle** (`check_backlog_structure.py`) | A ring of `blocked_by` edges. Every item in it waits for another in it, so none can ever ship. This gate did not exist while items were independent; `blocked_by` gave them edges and brought it back. |
| G5 | **No prior-art justification, and no fabricated local one** _(not mechanized: judgement — the keyword heuristic raises the question and the human decides; automating the refusal would reject an item that merely mentions another project)_ | `why_now` justifies the item by what another project does rather than by something that changed in our system. This is the Squad signature rule (Unbreakable Rule: evidence is ours or it is not evidence). Reject and ask for the local reason. **The second half was measured on 2026-08-28 and is the harder case:** given this item under time pressure, a smaller model refused the prior-art justification and then wrote a local one it had invented — *"shutdown is scattered, error propagation is unclear, testing is brittle"*, none of it observed. A fabricated local problem passes review more easily than a cited blog post, so refusing the appeal to authority is not enough: the replacement must name something someone measured, or the item becomes a spike that measures it. See `docs/wiki/references/judgement-gates-are-insurance.md`. |

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
- `.squad/records/backlog/{slug}-intake.md` — the intake grill log (one entry per answered question, with the G5 decision recorded).

The registry lives at the root of the governed SCOPE and not scattered below it, because a maintenance team asking "what is pending?" must have exactly one place to look. Per-directory backlogs inside one scope re-create the orphaned-findings problem the single-registry rule exists to solve.

What this never meant is "an umbrella is required". An autonomous repository is its own scope and keeps its own registry — one adopter holds 88 items about itself, and asking it to file them in a parent directory that is nobody's repository would put the registry outside the thing it governs.

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
