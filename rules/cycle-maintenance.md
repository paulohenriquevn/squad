# Cycle: MAINTENANCE (macro super-loop)
<!-- rule-id: SQ-CYC-11 -->

Source of Truth for the macro super-loop that runs from a `BACKLOG.md` item all the way back to the same `BACKLOG.md` with the item's status advanced. Sits **above** `cycle-idea-to-release`: where `cycle-idea-to-release` orchestrates one item end-to-end, `cycle-maintenance` orchestrates the ongoing work — item by item — for as long as the ecosystem is maintained.

## Purpose

Close the feedback loop between **something someone noticed** (`BACKLOG.md`) and **what actually shipped** (`RELEASED` from `cycle-release`). Without the loop the registry rots: items get fixed but their status never advances, killed hypotheses are re-filed, and within weeks nobody trusts the backlog enough to look at it.

The cycle produces no new files of its own. It produces **status transitions on `B-NNN` blocks** and **traceability** between every released change and the item that motivated it.

### There is no `MAINTENANCE_COMPLETE`

The ancestor loop ended: `ROADMAP_COMPLETE` when every milestone was `[x]`, because a roadmap is a finite scope someone declared. **A backlog is not a scope, and an empty one is not an achievement.** An ecosystem under maintenance always has something worth measuring; an empty registry means nobody has looked recently, not that nothing is wrong.

So the empty state is `BACKLOG_EMPTY`, and it is a **prompt to sweep**, not a terminal verdict. Treating it as completion is how a maintenance system quietly stops working while reporting success.

**It does, however, cut a pre-release.** A dry queue means everything in flight has landed, which is the one mechanical definition of "this batch is done" that does not require anyone's judgement — so `cycle-release` cuts an `X.Y.Z-rc.N` there (`cycle-release.md § Two cuts`). That is not completion and does not contradict the paragraph above: an rc says *installable*, never *finished*. The final version waits for a milestone to close and be accepted, because a milestone IS a declared finite scope and a backlog is not.

## Pre-conditions

- `BACKLOG.md` exists at the root of the governed scope — umbrella or autonomous repo (created once by `/backlog-init`).
- At least one item is `raw` or `triaged`.
- The working branch is `workspace` (per `rules/git-safety.md` § 1 — `develop` integrates, `main` is release-only).

Do NOT trigger when:

- `BACKLOG.md` is missing — run `/backlog-init` first.
- Every item is `shipped` or `killed` — emit `BACKLOG_EMPTY` and recommend `/discover-execute --sweep {domain}`.
- The human is mid-item on something else. One item in flight at a time; concurrency here means two loops editing the same registry.

## Chain

```
PREFLIGHT (once per session, before any item is touched):
     ↓ mechanisms/gates/check_chain_preconditions.py .
     ↓ exit 0 → continue
     ↓ exit 1 → REFUSE TO START and surface what is unconfigured
     ↓ exit 2 → could not measure; surface that, and do not read it as a pass
     ↓
SELECT next item:
     ↓ read BACKLOG.md                    scripts/select_backlog_item.py
     ↓ filter status ∈ {raw, triaged}
     ↓ drop the blocked (derived state, not the status field — an item
     ↓       waiting on another reads `triaged` on disk and cannot be worked)
     ↓ rank: triaged before raw (measured beats unmeasured)
     ↓       then by age (oldest first — a registry that always works the
     ↓       newest item starves the rest and stops being a backlog)
     ↓ pick the first
     ↓
     ↓ if NO eligible item → BACKLOG_EMPTY (a prompt to sweep, not a finish line)
     ↓ if all are blocked  → BACKLOG_BLOCKED (surface the wall; a sweep adds
     ↓                       items beside it and clears nothing)
     ↓
ROUTE:
     ↓ mechanisms/cycle/route_domain.py <repo> → domain + specialist
     ↓ unroutable → ITEM_UNROUTABLE, surface to the human (gate G1)
     ↓
LOCK item:
     ↓ record .squad/records/maintenance-runs/{B-NNN}-{date}.md (status: in_progress)
     ↓
DELEGATE:
     ↓ status raw      → /discover-plan B-NNN --mode {suggested_mode}, then the chain
     ↓                   ├── opportunity → status triaged → continue below
     ↓                   └── ITEM_KILLED → status killed → LOOP BACK to SELECT
     ↓ status triaged  → the DECISION to do the work, recorded:
     ↓                   backlog_status.py {backlog} B-NNN --to approved --approved-by human/<who> --because "…"
     ↓                   └── not approved → status unchanged, LOOP BACK to SELECT
     ↓ status approved → /idea-to-release B-NNN
     ↓                   (cycle-plan → implement → code-quality → review → release)
     ↓

**PREFLIGHT is first because the alternative was measured.** A consumer ran this loop
for hours on 2026-09-13 and produced 85 items, 57 measured opportunities, 39 panels and
13 plans scoring 89-100 structurally — and zero implemented, because every plan hit
`no_languages_audited` at the quality gate. The cause was one unconfigured file that had
been readable in milliseconds before any of it started.

Nothing was wrong with the work and no phase misbehaved. What was wrong is WHEN the
refusal arrived: at the end, after the effort, and item by item — which makes a property
of the INSTALLATION look like a property of each item, and sends the next session to fix
the wrong thing. It did: a session read the stable id and concluded a backlog item had
to be implemented first.

**The system never starts on a backlog nobody approved.** That is a precondition and
not a phase gate, because it has the same shape as the others: an unapproved registry is
not a queue of work, it is a queue of hypotheses, and a run over it decides by
inference — item by item, in the middle of the night — the one question this contract
reserves for a person. Measured on a consumer: 85 items at `triaged`, zero at
`approved`, and hours of execution against a list nobody had said yes to.

ONE approved item satisfies it. A backlog is approved incrementally and the loop works
one item at a time; demanding the whole registry be decided before anything starts would
make the preflight the thing it refuses.

**It is better to run nothing than to carry unresolved conditions that block the chain.**
A precondition here is a fact no amount of good work can overcome. A judgement is not —
which languages to audit, whether a soft cap deserves an ADR, whether to record a
baseline all have defensible answers, and a gate that refused to start until someone
made them would be a gate that refuses to start.

**`triaged → approved` is a step, not a formality, and this chain used to skip it.**
`cycle-backlog.md` states the prohibition in its own words — *"`raw → planned` and
`triaged → planned` are forbidden. Nothing reaches a plan without passing DISCOVER's
measurement AND being approved — the two are separate questions"* — and this file
prescribed the second of them until 2026-09-11. The code side was already correct:
`select_backlog_item.py` answers `approved` with `ITEM_AWAITING_PLAN`, and
`backlog_status.py` has carried the status since 2026-09-04.

**And the step has never been taken.** Measured across ten registries and 651 items,
496 of them shipped: `approved` appears **zero** times. A gate nobody has ever traversed
is either a gate nothing invites, or one every path routes around — and this chain
prescribing the forbidden transition is why. Fixing the prose does not fix that; what
closes it is something in the loop that ASKS for the decision, and nothing does yet.

ADVANCE:                              mechanisms/cycle/advance_items.py --apply
     ↓ RELEASED → status shipped, with the release artifact linked
     ↓ blocked  → status unchanged, blocker surfaced, LOOP BACK to SELECT
     ↓
LOOP BACK to SELECT
```

## Phase contracts

| Phase | Input | Output | Hard gate |
|---|---|---|---|
| select | `BACKLOG.md` | one `B-NNN`, or `BACKLOG_EMPTY` | exactly one item in flight |
| route | the item's `repo` | domain + specialist | the repo resolves (G1) |
| lock | `B-NNN` | run record under `.squad/records/maintenance-runs/` | no other run `in_progress` |
| delegate | `B-NNN` + status | opportunity, killed item, or release | the sub-cycle's own gates |
| advance | sub-cycle verdict | updated `B-NNN` block | status transition is legal |

## Verdicts

| Verdict | Meaning | Next |
|---|---|---|
| `ITEM_SHIPPED` | The item reached `RELEASED` — the FINAL cut — and its block says `shipped` | Loop back to SELECT. Written by `mechanisms/cycle/advance_items.py`, which reads `RELEASED` and never `PRE_RELEASED`: a pre-release must not close work it did not finish |
| `ITEM_KILLED` | Measurement refuted the hypothesis | Loop back to SELECT. **A successful outcome** |
| `ITEM_VERIFIED_LOCAL` | The fix is implemented and verified, and every file it changed is untracked, so no release can carry it. Decided by `all_changes_are_untracked()` in `mechanisms/cycle/advance_items.py`, which runs the `git check-ignore` test defined below over the file list the runner passes as `--verified-local B-NNN=path[,path...]`. The list is supplied, never inferred — deriving it from the working tree would guess which change belongs to which item, and this test is mechanical | Loop back to SELECT. **A terminal state, not a failure** |
| `ITEM_IN_FLIGHT` | Held on a **material impediment** — a machine, a credential, elapsed time, a system not standing (`halt_disposition.py`, `decision-delegation.txt § retained_classes`). Branch protection requiring a reviewer is no longer one of these: it is a violated premise caught at intake | Resume when the impediment is cleared. **The queue does not wait on it** — it takes the next item |
| `ITEM_BLOCKED` | A sub-cycle blocked, recoverably | Surface, then loop back to SELECT — other items still move | _(emitted externally: the maintenance runner that owns ADVANCE does not exist yet — SELECT is mechanized by `select_backlog_item.py`, the phases after it are not, and this row is the declared debt rather than a silent gap)_
| `ITEM_UNROUTABLE` | `repo` is in no domain | Surface. The item cannot proceed until the repo is cloned or the routing table names it. _(emitted externally: the CONDITION is detected by `route_domain.py`, which prints `UNROUTED` and exits 3; the token is written by the runner that surfaces it. The skill that named it was retired 2026-08-31, and the detector was not)_ |
| `BACKLOG_EMPTY` | Nothing `raw` or `triaged` | **Run `/discover-execute --sweep {domain}`.** Not a finish line |
| `BACKLOG_INVALID` | An id does not name exactly one item — `duplicate_id` or `renumbered` | **Fix the registry's ids, then select.** Every id the selector could return is ambiguous, so it returns none. Only these two findings reach here: a blocker about an item's CONTENT leaves the id intact and the item still selectable, because improving content is what the chain below is for |
| `ITEM_SELECTED` | SELECT picked an item; nothing blocks it | ROUTE |
| `BACKLOG_BLOCKED` | Selectable items remain and **every one is blocked** | Surface the wall. **Not `BACKLOG_EMPTY`** — a sweep would add items beside a wall instead of clearing it |
| `ITEM_HALTED` | A phase stopped on this item and wrote `{slug}-BLOCKED.md` | Read the report. SELECT holds the item out of the queue until the file is gone — handing it out again reruns exactly what halted |

### Attacking the cause of a halt

A BLOCKED report names the items the phase measured as its cause. Those items get the
front of the queue: `skills/backlog-review/scripts/squad_boss.py` reads the reports,
keeps the cited ids the registry still calls open, and SELECT ranks them ahead of
older work. Finishing them is what lets the halt move.

This changes ORDER, never eligibility. A prioritised item that is itself blocked or
halted stays held by the rules that hold it, and nothing about the halted item is
touched — not its status, not `blocked_by`, and never the gate that stopped it. The
decision the report addresses to a person stays with that person; what stops waiting
is the work that decision was blocking.

A report naming no open item is reported as exactly that. It is the case only a
person can move, and the one most easily mistaken for handled.

## Why ADVANCE is safe to mechanise — and why the old reason expired

This section used to argue that ADVANCE could not close an item on its own because
*"a session driving this cycle unattended will never emit `RELEASED`* — the approval,
the merge and the tag are all past a gate it cannot pass", so *"by the time it acts,
every judgement it might have needed has been made by a person."*

**That stopped being true on 2026-09-01.** Envelope floor 2 now permits the system to
merge a pull request whose full chain passed, so the same loop that produces the
release can emit `RELEASED` and then close the item on it. Keeping the old paragraph
would have left a safety argument that had quietly expired — the shape this kit calls
a contract without a mechanism, in the direction where the prose is the stale half.

The real reason ADVANCE is safe is narrower and did not change: **it moves an item only
on an explicit `cycle:phase:end` with `cycle=release` and `verdict=RELEASED`**, a token
that exists only downstream of every gate in the chain. It infers nothing from files on
disk, writes through `backlog_status.py` so an illegal transition is refused and the
refusal reported, and running it twice changes nothing the first run did.

What it never gained is the right to decide. It is still bookkeeping; what changed is
who made the decision it follows — the gates, rather than a person reading them.

It moves an item only on an explicit `cycle:phase:end` with `cycle=release` and
`verdict=RELEASED`, and writes through `backlog_status.py` — so a blocked, killed
or already-shipped item is refused, and the refusal is reported rather than
swallowed. Running it twice changes nothing the first run did.

## What ADVANCE may assume about the stream

ADVANCE learns that a release happened by reading `cycle:phase:end` with
`cycle=release, verdict=RELEASED`. Measured on 2026-08-31, before building it, so the
limits are known rather than discovered by a wrong `shipped`:

- **The stream is per-machine and per-session, by decision.** `.gitignore` carries the
  reason: *what this repository's cycles did here says nothing to whoever clones it,
  and committing it would put one machine's run history in everyone's diff.* So ADVANCE
  works within a working sequence on one machine; after a clone the stream is empty and
  every item looks like a phase that never ran.
- **In an installed consumer the stream lands under `.claude/records/`**, because
  `install.sh` scaffolds `records/` there and `resolve_events_path` prefers it — and
  `.claude/` is not versioned. This is consistent with the point above, not a defect,
  but it means ADVANCE must never treat an absent stream as evidence of anything.
- **There is no retroactivity, and there must not be.** One registry measured here
  carries 166 items with 133 shipped and has no event file at all. Those items will
  never have events, and writing them now would be inventing a history nobody observed.
  ADVANCE applies from the first item processed after instrumentation, forward only.

The consequence for the verdicts: an item with no `RELEASED` event is **not** thereby
unreleased. It is unknown, and `ITEM_SHIPPED` must not be emitted from a silence — the
anti-pattern below (*if nothing was released, nothing shipped*) has a mirror image that
is just as wrong.

## Ranking — why triaged outranks raw, and age outranks everything else

**Triaged before raw** because a triaged item already carries measured evidence. Its cost to finish is known; a raw item's is not. Working measured items first also keeps evidence fresh — an opportunity measured months ago describes a system that has since moved.

**Age is the id.** Ids are monotonic and never reused — the contract says so and
`check_backlog_structure.py` enforces it as `renumbered` — so a lower number was
registered earlier. The selector reads the id rather than a registration date:
measured in one real registry, 52 of 166 items carry a date (31%), so ordering by
it would leave two thirds of the backlog with no key, and it would be a second
source for a fact the id already carries.

**Then oldest first.** A registry that always works the newest item starves the rest, and the starved items are exactly the ones nobody feels urgency about — which is not the same as the ones that do not matter. Age ordering is what keeps a backlog from becoming a list of whatever was mentioned most recently.

Neither rule outranks a human saying "do this one". The ranking exists so the loop can run unattended, not to override judgement.

## `ITEM_VERIFIED_LOCAL` — when the work is real and no release can carry it

Some items fix files the repository does not track. In a plugin install that is typically
everything under `.claude/` — the kit's own `skills/`, `hooks/` and `scripts/`, plus the
`rules/` the project owns there. A fix in one of those is implementable, testable and
verifiable, and `cycle-release` cuts a tag from committed history, so **there is nothing for
a tag to point at**.

Without this state such an item has no honest end. `ITEM_SHIPPED` is false — nothing shipped.
Leaving it `planned` forever is worse, because the registry then reports finished work as
outstanding, and a registry that misreports is the rot this whole loop exists to prevent.

**The test is mechanical, not rhetorical.** An item qualifies when

```bash
git check-ignore -q <every file the fix changed>
```

succeeds for ALL of them. If any changed file IS tracked, the item is not in this state — it
has a release, and it must take it. This matters because the state is otherwise a tempting
place to retire work that simply has not been released yet.

**What it is not.** It is not "done". The fix helps that checkout and no other, including
sibling repositories running the same install. The followup that ends it is carrying the fix
to the kit's own repository, where a release can reach every consumer.

Harvested from an adopter, where the state was created and measured (2026-08-20). There
thirteen items paid that cost at once, and the rule defining it lived under `.claude/` — so
the item that wrote it ended up in the very state it invented.

## Anti-patterns

- **Calling an item `shipped` because the fix works.** If nothing was released, nothing shipped. `ITEM_VERIFIED_LOCAL` exists precisely so that the honest answer is available.

- **Treating `BACKLOG_EMPTY` as completion.** It means nobody has looked recently. Sweep.
- **Two items in flight.** Two loops editing `BACKLOG.md` collide on `B-NNN` allocation, and the ids are the audit trail.
- **Advancing status without the sub-cycle's verdict.** `shipped` set by hand means the checkbox stopped meaning anything — the exact rot this loop exists to prevent.
- **Re-selecting a killed item.** It carries `kill_reason` for a reason. Re-filing needs a new id with `supersedes:`, specified in [`cycle-backlog.md`](cycle-backlog.md) § Lineage.
- **Working only what is loud.** The ranking is there precisely because urgency and importance are not the same signal.
- **Selecting an item whose repo has no checkout.** It routes nowhere; `ITEM_UNROUTABLE` says so instead of pretending.

## Output

- `BACKLOG.md` — status transitions on `B-NNN` blocks
- `.squad/records/maintenance-runs/{B-NNN}-{date}.md` — one record per run: what was selected, why, which specialist, what the sub-cycles returned

The run record is what makes the loop auditable after the fact: which items were picked, in what order, and what happened. Without it, a backlog whose items all say `shipped` cannot be distinguished from one somebody edited.

## Rollback

An item advanced in error is moved back with a note recording the advance and why it was withdrawn — never silently reset. An item whose `shipped` was withdrawn carries information a fresh-looking `triaged` item does not.

`backlog_status.py --withdraw-reason` is what enforces this, and it held neither half until 2026-09-18: the two backward moves the transition table allowed were accepted with no note at all, leaving exactly the fresh-looking item this clause names, and `triaged -> raw` — the same move one step down — was refused outright. A move to an earlier entry of the open chain now requires the reason, holds it to the bar `--kill-reason` holds a committed item to (who withdrew it and what changed, not what the evidence showed), and writes `withdrawn_from` beside it, because after the move the status line cannot say what the item used to be.

`shipped` remains terminal. The sentence above is the argument for why the note matters and not a licence to reopen a shipped item: doing so changes what `shipped` means to every reader that counts delivery, which is a decision for a person.

## Cross-references

- Schema for cycle rules: `rules/cycle-rule-schema.md`
- The registry and its intake: `rules/cycle-backlog.md`
- Measurement: `rules/cycle-discover.md`
- Orchestrator this delegates to: `rules/cycle-idea-to-release.md`
- Routing: `mechanisms/cycle/route_domain.py`
- Specialists: `agents/README.md`
- Branching contract: `rules/git-safety.md`

### Who decides what, when nobody is watching

`rules/autonomy-envelope.md` says which decisions belong to the system and which belong
to a person, and — for the system's — the doctrine that decides them, so the same
situation gets the same answer twice.

It matters most exactly here. A chain that halts at every judgement call is correct
while someone is reading the log and is a stopped queue when nobody is. The envelope is
what makes the difference a policy a project chooses, rather than an accident of who
happened to be watching.

Read it before adding a stop to any phase: a gate that waits for an answer nobody will
give is not a gate.

### Stopping on a material impediment is a phase ending, not a phase skipping

A phase that runs and stops because the item needs something no authority supplies —
a machine, a credential, elapsed time — ends with `AWAITING_HUMAN`, and **the event is
emitted**. The work happened; the item is held; both are facts, and neither reaches any
reader on its own.

**This is now the only way a phase between DISCOVER and ACCEPTANCE ends on a person**
(`autonomy-envelope.md § The autonomous span`). A gate that failed, a loop that stopped
improving and a plan that cannot be levelled are all the queue's own work, and they end
with the item back in the registry rather than in front of somebody.

An item worked this way and left silent is indistinguishable from one nobody touched:
zero events, zero artefacts, the status it started with. The board draws it as
underived, the drift checker has nothing to compare, a halt-reader finds no report,
and a watchdog that sees no event concludes the command never landed and starts it
again. Every one of those readers behaves correctly on the evidence it has. The
evidence is what is missing.

`AWAITING_HUMAN` is in `rules/blocking-verdicts.txt`, so an item that ends on it is
held everywhere the same way — the selector will not hand it out and the watchdog will
not restart it, both reading that one list.

**A halt is measured, never judged.** `ITEM_HALTED` asserts one thing: a BLOCKED
report exists on disk for this item. What to DO about the halt — accept the failure
with a caveat, fix its cause first, change the gate — is content, and stays with
whoever the report addresses. SELECT only declines to hand the item out again.

The failure it prevents: an item is open, nothing in the registry blocks it, and it is
the oldest of its status — so SELECT hands it out, while a report on disk says a phase
already halted on it. Any caller looping on SELECT restarts the halt, forever.

`ITEM_SELECTED`, `ITEM_HALTED` and `BACKLOG_BLOCKED` are emitted by `skills/backlog-review/scripts/select_backlog_item.py`, which is also what makes
the SELECT phase above a computation rather than a paragraph an agent reads. It was
added on 2026-08-30, when a sweep found this rule to be the kit's largest
contract-without-executor: the chain, the ranking and eight verdicts were written,
four of the verdicts appeared in no skill and no script, and the only runner over
backlog items carried a literal list of three ids.

`--check B-NNN` answers the narrow question — may THIS one start? — with the same
computation that picks, so the gate and the selector cannot disagree. `--queue N`
returns the head of the order for a caller filling more than one lane.

There is no verdict for "the ecosystem is done".
