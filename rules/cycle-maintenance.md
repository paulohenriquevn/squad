# Cycle: MAINTENANCE (macro super-loop)

Source of Truth for the macro super-loop that runs from a `BACKLOG.md` item all the way back to the same `BACKLOG.md` with the item's status advanced. Sits **above** `cycle-idea-to-release`: where `cycle-idea-to-release` orchestrates one item end-to-end, `cycle-maintenance` orchestrates the ongoing work — item by item — for as long as the ecosystem is maintained.

## Purpose

Close the feedback loop between **something someone noticed** (`BACKLOG.md`) and **what actually shipped** (`RELEASED` from `cycle-release`). Without the loop the registry rots: items get fixed but their status never advances, killed hypotheses are re-filed, and within weeks nobody trusts the backlog enough to look at it.

The cycle produces no new files of its own. It produces **status transitions on `B-NNN` blocks** and **traceability** between every released change and the item that motivated it.

### There is no `MAINTENANCE_COMPLETE`

The ancestor loop ended: `ROADMAP_COMPLETE` when every milestone was `[x]`, because a roadmap is a finite scope someone declared. **A backlog is not a scope, and an empty one is not an achievement.** An ecosystem under maintenance always has something worth measuring; an empty registry means nobody has looked recently, not that nothing is wrong.

So the empty state is `BACKLOG_EMPTY`, and it is a **prompt to sweep**, not a terminal verdict. Treating it as completion is how a maintenance system quietly stops working while reporting success.

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
     ↓ scripts/route_domain.py <repo> → domain + specialist
     ↓ unroutable → ITEM_UNROUTABLE, surface to the human (gate G1)
     ↓
LOCK item:
     ↓ record records/maintenance-runs/{B-NNN}-{date}.md (status: in_progress)
     ↓
DELEGATE:
     ↓ status raw     → /discover-plan B-NNN --mode {suggested_mode}, then the chain
     ↓                  ├── opportunity → status triaged → continue below
     ↓                  └── ITEM_KILLED → status killed → LOOP BACK to SELECT
     ↓ status triaged → /idea-to-release B-NNN
     ↓                  (cycle-plan → implement → code-quality → review → release)
     ↓
ADVANCE:                              scripts/advance_items.py --apply
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
| lock | `B-NNN` | run record under `records/maintenance-runs/` | no other run `in_progress` |
| delegate | `B-NNN` + status | opportunity, killed item, or release | the sub-cycle's own gates |
| advance | sub-cycle verdict | updated `B-NNN` block | status transition is legal |

## Verdicts

| Verdict | Meaning | Next |
|---|---|---|
| `ITEM_SHIPPED` | The item reached `RELEASED` and its block says `shipped` | Loop back to SELECT. Written by `scripts/advance_items.py` |
| `ITEM_KILLED` | Measurement refuted the hypothesis | Loop back to SELECT. **A successful outcome** |
| `ITEM_VERIFIED_LOCAL` | The fix is implemented and verified, and every file it changed is untracked, so no release can carry it. Decided by `all_changes_are_untracked()` in `scripts/advance_items.py`, which runs the `git check-ignore` test defined below | Loop back to SELECT. **A terminal state, not a failure** |
| `ITEM_IN_FLIGHT` | Paused at a human-approval gate | Resume when the human answers |
| `ITEM_BLOCKED` | A sub-cycle blocked, recoverably | Surface, then loop back to SELECT — other items still move | _(emitted externally: the maintenance runner that owns ADVANCE does not exist yet — SELECT is mechanized by `select_backlog_item.py`, the phases after it are not, and this row is the declared debt rather than a silent gap)_
| `ITEM_UNROUTABLE` | `repo` is in no domain | Surface. The item cannot proceed until the repo is cloned or the routing table names it. _(emitted externally: the CONDITION is detected by `route_domain.py`, which prints `UNROUTED` and exits 3; the token is written by the runner that surfaces it. The skill that named it was retired 2026-08-31, and the detector was not)_ |
| `BACKLOG_EMPTY` | Nothing `raw` or `triaged` | **Run `/discover-execute --sweep {domain}`.** Not a finish line |
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

## ADVANCE runs after the human, never instead of them

Measured on the first autonomous run: the executing session's own plan ends at
*/release (stops at PR_OPEN_AWAITING_APPROVAL)*. A session driving this cycle
unattended **will never emit `RELEASED`** — the approval, the merge and the tag are
all past a gate it cannot pass.

That is what makes ADVANCE safe to mechanise, and it is the opposite of how it
first read. It is not the autonomous loop closing its own items; it is the
bookkeeping that follows a decision somebody already made. By the time it acts,
every judgement it might have needed has been made by a person.

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

Harvested from `theokit-tui`, where the state was created and measured (2026-08-20). There
thirteen items paid that cost at once, and the rule defining it lived under `.claude/` — so
the item that wrote it ended up in the very state it invented.

## Anti-patterns

- **Calling an item `shipped` because the fix works.** If nothing was released, nothing shipped. `ITEM_VERIFIED_LOCAL` exists precisely so that the honest answer is available.

- **Treating `BACKLOG_EMPTY` as completion.** It means nobody has looked recently. Sweep.
- **Two items in flight.** Two loops editing `BACKLOG.md` collide on `B-NNN` allocation, and the ids are the audit trail.
- **Advancing status without the sub-cycle's verdict.** `shipped` set by hand means the checkbox stopped meaning anything — the exact rot this loop exists to prevent.
- **Re-selecting a killed item.** It carries `kill_reason` for a reason. Re-filing needs a new id with `supersedes:`, per `skills/backlog-item/SKILL.md` — which is where that field is specified.
- **Working only what is loud.** The ranking is there precisely because urgency and importance are not the same signal.
- **Selecting an item whose repo has no checkout.** It routes nowhere; `ITEM_UNROUTABLE` says so instead of pretending.

## Output

- `BACKLOG.md` — status transitions on `B-NNN` blocks
- `records/maintenance-runs/{B-NNN}-{date}.md` — one record per run: what was selected, why, which specialist, what the sub-cycles returned

The run record is what makes the loop auditable after the fact: which items were picked, in what order, and what happened. Without it, a backlog whose items all say `shipped` cannot be distinguished from one somebody edited.

## Rollback

An item advanced in error is moved back with a note recording the advance and why it was withdrawn — never silently reset. An item whose `shipped` was withdrawn carries information a fresh-looking `triaged` item does not.

## Cross-references

- Schema for cycle rules: `rules/cycle-rule-schema.md`
- The registry and its intake: `rules/cycle-backlog.md`
- Measurement: `rules/cycle-discover.md`
- Orchestrator this delegates to: `rules/cycle-idea-to-release.md`
- Routing: `scripts/route_domain.py`
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

### Stopping at a human gate is a phase ending, not a phase skipping

A phase that runs and stops because only a person can open the next door ends with
`AWAITING_HUMAN`, and **the event is emitted**. The work happened; the item is held;
both are facts, and neither reaches any reader on its own.

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
