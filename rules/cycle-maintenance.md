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
ADVANCE:
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
| `ITEM_SHIPPED` | The item reached `RELEASED` and its block says `shipped` | Loop back to SELECT |
| `ITEM_KILLED` | Measurement refuted the hypothesis | Loop back to SELECT. **A successful outcome** |
| `ITEM_VERIFIED_LOCAL` | The fix is implemented and verified, and every file it changed is untracked, so no release can carry it | Loop back to SELECT. **A terminal state, not a failure** | _(emitted externally: the maintenance runner that owns ADVANCE does not exist yet — SELECT is mechanized by `select_backlog_item.py`, the phases after it are not, and this row is the declared debt rather than a silent gap)_
| `ITEM_IN_FLIGHT` | Paused at a human-approval gate | Resume when the human answers |
| `ITEM_BLOCKED` | A sub-cycle blocked, recoverably | Surface, then loop back to SELECT — other items still move | _(emitted externally: the maintenance runner that owns ADVANCE does not exist yet — SELECT is mechanized by `select_backlog_item.py`, the phases after it are not, and this row is the declared debt rather than a silent gap)_
| `ITEM_UNROUTABLE` | `repo` is in no domain | Surface. The item cannot proceed until the repo is cloned or the routing table names it |
| `BACKLOG_EMPTY` | Nothing `raw` or `triaged` | **Run `/discover-execute --sweep {domain}`.** Not a finish line |
| `ITEM_SELECTED` | SELECT picked an item; nothing blocks it | ROUTE |
| `BACKLOG_BLOCKED` | Selectable items remain and **every one is blocked** | Surface the wall. **Not `BACKLOG_EMPTY`** — a sweep would add items beside a wall instead of clearing it |

`ITEM_SELECTED` and `BACKLOG_BLOCKED` are emitted by `skills/backlog-review/scripts/select_backlog_item.py`, which is also what makes
the SELECT phase above a computation rather than a paragraph an agent reads. It was
added on 2026-08-30, when a sweep found this rule to be the kit's largest
contract-without-executor: the chain, the ranking and eight verdicts were written,
four of the verdicts appeared in no skill and no script, and the only runner over
backlog items carried a literal list of three ids.

`--check B-NNN` answers the narrow question — may THIS one start? — with the same
computation that picks, so the gate and the selector cannot disagree. `--queue N`
returns the head of the order for a caller filling more than one lane.

There is no verdict for "the ecosystem is done".

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
- **Re-selecting a killed item.** It carries `kill_reason` for a reason. Re-filing needs a new id with `supersedes:`, per `cycle-backlog.md § Step 2`.
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
