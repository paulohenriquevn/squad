---
name: backlog-item
version: 0.1.0
requires: []
description: 'Register one unit of maintenance work in BACKLOG.md as the next B-NNN item. Use this whenever someone notices something worth fixing, improving, verifying or measuring in the ecosystem — a slow endpoint, a suspicious code path, a flaky behaviour, a duplicated rule, a repo that feels wrong — even when they only mutter it in passing and never say "backlog" or "item". An unmeasured hunch is exactly what belongs here: intake requires no evidence, deliberately. Also use it before starting any maintenance work, so the work has an id, an owner and a Definition of Done.'
user-invocable: true
allowed-tools: Read Glob Grep Bash Write Edit AskUserQuestion
argument-hint: "{item-slug}"
---

# `/backlog-item` — Register one unit of maintenance work

Take a one-line description of something to improve, fix, verify, or evolve in the governed ecosystem (e.g. *"the trace explorer feels slow"*) and append it as the next `B<N+1>` item in `BACKLOG.md`, with domain routing, a suggested discover mode, and a verifiable Definition of Done.

The item this skill produces is **a hypothesis, not yet a commitment**. It carries `evidence: none-yet` by design. Proving it — or killing it — is `cycle-discover`'s job.

That word *yet* is the whole distinction. An item stays a hypothesis through `raw` and `triaged`, and killing one there is the cycle working: the measurement did not support the hunch. **`approved` is where it becomes a commitment** — someone with the authority decided it will be done. From there, killing it reverses a decision rather than reporting a result, and `backlog_status.py` refuses a `--kill-reason` that does not name who reversed it and what changed. This skill never produces an approved item: intake is cheap precisely because it commits nobody.

## Cycle contract

This skill is **phase 0** of [`cycle-backlog`](../../rules/cycle-backlog.md). The cycle rule is the **source of truth** for:

- The item schema and its field semantics
- Status transitions (`raw → triaged | killed → approved → planned → shipped`)
- The 8 registered domains and their repos
- Hard gates G1–G5, verdicts, anti-patterns, rollback
- The handoff contract to [`cycle-discover`](../../rules/cycle-discover.md)

**Read `cycle-backlog.md` before invoking this skill.** This SKILL.md retains only the intake protocol below.

## When NOT to invoke

DO NOT invoke when:

- `BACKLOG.md` does not exist — run `/backlog-init` first. (This skill refuses.)
- A sweep already registered the finding (`source: discover-*`). Grep before filing.
- The work spans two domains — split it into two items.
- You are justifying the work by what another project does. See Step 5.

Unlike its Cycle ancestor `/roadmap-feature`, this skill **does not refuse hotfixes, one-line fixes, or refactors with no user-visible change.** Those are the Squad's core workload, not exceptions routed elsewhere.

## Process

### Step 0 — Pre-flight (MANDATORY, fail-fast)

```bash
# 0.1  BACKLOG.md must exist
test -f BACKLOG.md || { echo "FATAL: BACKLOG.md missing — run /backlog-init first"; exit 1; }

# 0.2  intake log must be writable
mkdir -p .squad/records/backlog 2>/dev/null
test -w .squad/records/backlog || { echo "FATAL: .squad/records/backlog not writable"; exit 1; }

# 0.3  CHANGELOG.md must exist (Unbreakable Rule 6)
test -f CHANGELOG.md || { echo "FATAL: CHANGELOG.md missing"; exit 1; }

# 0.4  BACKLOG.md must parse
python3 -c "
import re, sys
items = re.findall(r'^## (B-\d+) — .*\[(.)\]', open('BACKLOG.md').read(), re.MULTILINE)
print('OK', len(items), 'items found')
"
```

A parse failure is surfaced verbatim so the human fixes the malformed registry before anything is appended. Never repair `BACKLOG.md` silently — a registry that got edited by hand is a signal, not a nuisance.

### Step 1 — Resolve the slug

Take `{item-slug}`. If absent, ask for a one-sentence description and derive a kebab-case slug (*"trace explorer feels slow"* → `web-console-trace-explorer-latency`).

Prefix the slug with the repo when the same problem shape recurs across repos (`web-console-…`, `search-api-…`). A registry spanning many repos makes a bare `latency` slug unsearchable.

### Step 2 — Gates G1 + G2, executados (MANDATORY)

```bash
ECO=$([ -d .claude/skills ] && echo .claude || echo .)   # plugin vs standalone
python3 "$ECO/skills/backlog-item/scripts/check_intake_gates.py" \
  --backlog BACKLOG.md \
  --repo {repo} \
  --term "{noun1}" --term "{noun2}"
```

One script, both mechanizable gates:

- **G1** delegates to `mechanisms/cycle/route_domain.py` — the routing table is parsed from `rules/cycle-backlog.md`, so there is one table and one truth. Exit `1` = the repo is not in it, verdict `ITEM_REJECTED`.
- **G2** searches `BACKLOG.md` for every term **plus the repo name** (always added — the repo is the term that collides most across a registry spanning 21 of them) and returns each matching block with its status and the action the rule prescribes for it. Exit `3` = candidates found.

Running it IS the evidence that G2 happened; the old instruction was a `grep` whose execution nobody could verify afterwards. Then read every `B-NNN` block it returned — a keyword hit is a candidate, not a verdict.

- **Open item, same problem** → verdict `ITEM_MERGED`. Do NOT allocate a new id. Append the new context to the existing block's body and record the merge in the intake log. Report which id absorbed it.
- **`killed` item, same problem** → allocate a new id, and add `supersedes: B-NNN` plus what changed since the kill. A hypothesis killed for lack of evidence in April can be legitimately re-filed in August; silently re-filing it without the link is what the gate prevents.
- **`shipped` item, problem is back** → new id with `regression_of: B-NNN`. This is a regression, and naming it as one matters more than the item itself.
- **No hit** → proceed.

Both lineage fields are specified in [`cycle-backlog.md`](../../rules/cycle-backlog.md) § Lineage, which is also what checks them: a `supersedes` naming an undefined id, or a `regression_of` naming an item that never shipped, is a finding rather than a line nobody reads.

Skipping this step is a G2 violation. The single-registry decision only holds if intake actually looks — and a gate whose execution depends on the agent remembering is an intention, not a gate.

### Step 3 — Detect next id

Extract every `## B-(\d+)` from `BACKLOG.md`, take `max(N) + 1`, format as `B-{N:03d}`.

```
Existing items: 27 (18 shipped, 4 planned, 3 triaged, 2 killed)
Next free id:   B-028
```

Ids are monotonic and never reused — including the ids of killed items. No cap.

### Step 4 — Focused grill (4 questions, plus a fifth when objectives exist — ONE per turn)

Same protocol as the Cycle grills: one question per turn, each with a recommended answer and its reasoning, persisted after every answer.

| # | Question | Why it must be answered |
|---|---|---|
| 1 | What is this, and **what changed in our system** to raise it now? | Feeds `why_now` and is the input to gate G5. "What changed" is the load-bearing half — an item with no local trigger is either prior-art envy or a hunch too vague to measure. |
| 2 | Which repo, and therefore which domain? | Feeds `domain` + `repo` (G1) and decides which specialist picks it up. Offer the routing table; if the answer names two domains, G3 fires and the item splits. |
| 3 | Which discover mode looks right — review, live-test, bug or evolve? | Feeds `suggested_mode`. State explicitly to the user that this is **a suggestion DISCOVER may overrule**, so nobody treats their guess as a decision. |
| 4 | What is the verifiable Definition of Done (1-3 bullets)? | Feeds `dod` (G4). This is the criterion that closes the item. Reject bullets that restate the title or cannot fail. |
| 5 | Which declared objective does this serve? | Feeds `traces_to`. **Ask only if `.squad/wiki/product/objectives.md` exists** — offer its `OBJ-N` ids and titles as the options. If none fits, that is the interesting answer: either an objective is missing or the item is. Say so and let the user decide; do not invent an id. Without that document, skip the question entirely — a project that has not run `/brainstorm-objectives` has nothing to trace to, and demanding a link would be inventing a standard it never adopted. |

**Note what is NOT asked: evidence.** Intake has no evidence gate. If the user offers a `file:line` or a trace id unprompted, record it — but never ask for it, and never let its absence block the item.

#### 4.X — Persistence after every answer (MANDATORY)

Append to `.squad/records/backlog/{item-slug}-intake.md` after each answered question, with `generated_by: backlog-item`. Set `status: completed` on success at Step 6, `status: aborted` if the user stops early. A grill abandoned mid-way leaves a log, not a half-written registry entry — `BACKLOG.md` is touched only at Step 6.

### Step 5 — No-prior-art check (MANDATORY — gate G5)

Read the Q1 answer. The item is **rejected** if the justification rests on what another project, product, or framework does, rather than on something observable in our system.

| Rejected | Accepted |
|---|---|
| "LangSmith has a trace waterfall, we should have one" | "The explorer does not show span hierarchy, so debugging a nested agent means opening 6 traces" |
| "Everyone caches this" | "The endpoint makes 4 Postgres round-trips per request" |
| "A blog post says the pattern is X" | "Our handler duplicates auth logic in 3 places and they diverged once" |

On a hit, use `AskUserQuestion`:

```
This item's justification rests on how another project solves the problem:

  "{excerpt}"

Squad only accepts work justified by evidence from our own system
(cycle-backlog § Hard gates, G5). This does not forbid knowing how others solved
it — it forbids that being the reason.

  [ ] Reformulate — there is a local reason, let me describe it
  [ ] Register anyway — the gate misread; the reason is already local
  [ ] Cancel — there is no local reason; this is not an item
```

Record the decision (`g5_reformulated` / `g5_false_positive` / `g5_rejected`) in the intake log. The keyword heuristic surfaces the question; the human decides. A false positive is a normal outcome, not a failure of the gate.


Emit the START of this phase before doing the work:

```bash
python3 "$([ -d .claude/scripts ] && echo .claude || echo .)/mechanisms/cycle/cycle_events.py" start \
    --cycle backlog --slug {B-NNN}
```

Without it the board can only draw what FINISHED. Measured on 2026-08-31: seventeen
`phase:end` events and one `phase:start`, so an item under active work showed the
verdict of a phase already over and nothing on the page said anything was running.
A `start` with no matching `end` is exactly the fact "this is happening now".

### Step 6 — Write

Only after Steps 2–5 pass. Four writes, in this order:

1. **`BACKLOG.md`** — append one `## B-NNN` block per the schema in `cycle-backlog.md § Item schema`, with `status: raw`, `source: human`, `evidence: none-yet`, and the provenance line:
   `> Registered {{DATE}} by `/backlog-item` (slug: `{{SLUG}}`).`
   Append only. Never reorder, never renumber, never touch another block.
2. **`CHANGELOG.md`** — one line under `[Unreleased] § Added`, attributed to the target repo per the umbrella convention: `**{repo}:** backlog B-NNN — {title} (#NNN)`.
3. **`.squad/records/backlog/{slug}-intake.md`** — flip the log to `status: completed`.

4. **The phase event** — the transition, into the stream rather than a file someone reconstructs later:

   ```bash
   python3 "$([ -d .claude/scripts ] && echo .claude || echo .)/mechanisms/cycle/cycle_events.py" end \
       --cycle backlog --slug B-NNN --verdict ITEM_REGISTERED
   ```

   Last, and only if the `BACKLOG.md` write succeeded. An event for an item that
   was not written is worse than no event: it is the stream asserting something
   the registry does not carry.

   Measured on 2026-08-30: `backlog` and `discover` are the cycle's only two
   `required` phases, and both emitted nothing — as did `release`, whose verdict
   is what `cycle-maintenance.md`'s ADVANCE consumes. Four of eight phases were
   silent, and the one real registry examined had no event stream at all.

If the `BACKLOG.md` write fails, do not write the CHANGELOG entry. A changelog line for an item that does not exist is worse than no line.

### Step 7 — Report

```
ITEM_REGISTERED  B-028 — {title}
  domain: {domain} → specialist {domain}
  repo: {repo}
  suggested_mode: {mode}  (suggestion — /discover-plan may reclassify)
  evidence: none-yet      (hypothesis; /discover-execute measures)
  dod: {n} criteria

Next step:  /discover-plan B-028 --mode {mode}
```

For `ITEM_MERGED`, report the absorbing id and what was appended to it. For `ITEM_REJECTED`, report the gate that fired and what would make the item acceptable — a rejection that does not say how to fix it just gets re-filed verbatim tomorrow.

## Filing from inside another item

Work in progress is the most common source of new items: an item reaches IMPLEMENT
and only there turns out to need something else — a migration nobody scoped, a
decision nobody made, a repo that has to move first.

That discovery is filed, not absorbed. Absorbing it grows the item past what was
aligned on, and the growth is invisible to every gate that measured the original.

```
1. File the dependency as its own item        /backlog-item   (this skill, in full)
2. Record the edge on the item that stalled   mechanisms/cycle/backlog_status.py B-014 --block-on B-100
3. Leave the stage alone                      it resumes where it stopped
```

The stage is deliberately untouched. `blocked` is derived from status + `blocked_by`,
so an item that stalls at `planned` comes back at `planned` — and the moment B-100
ships, B-014 stops being blocked with nobody clearing a flag.

Not every impediment has an item to file. When the blocker is a decision or an action
outside the repository, record it as prose and say so:

```
mechanisms/cycle/backlog_status.py BACKLOG.md B-014 --block-on --because "the sponsor must pick the cell map"
```

That edge cannot be resolved by any gate here, which is the honest outcome — nothing
in this repository knows whether a sponsor has decided. A human clears the line.

See `rules/cycle-backlog.md § Impediments` for the field, the derived state, and why
the reverse edge is never written.

## Anti-patterns

Cycle-level anti-patterns live in `cycle-backlog.md § Anti-patterns`. Specific to this skill:

- **Asking for evidence during the grill.** Turns intake into triage and silences the hunch this phase exists to capture.
- **Writing to `BACKLOG.md` before the grill completes.** An aborted grill must leave the registry untouched.
- **Auto-resolving a dedup hit.** The grep finds candidates; the human confirms whether it is the same problem. A wrong merge buries an item forever.
- **Treating a G5 hit as a refusal to do the work.** The gate rejects a *justification*, never an idea. The correct move is to ask for the local reason, not to close the conversation.
- **Growing the current item instead of filing the dependency.** The item then covers work nobody aligned on, and every gate that measured the original is now measuring something else.
- **Deriving `domain` from the slug.** Route from the repo via the table in `cycle-backlog.md § Domain routing`, not from what the slug sounds like.

## Cross-references

- Cycle rule (source of truth): [`rules/cycle-backlog.md`](../../rules/cycle-backlog.md)
- Downstream: [`rules/cycle-discover.md`](../../rules/cycle-discover.md) — measures the hypothesis, flips `raw → triaged | killed`
- Rule schema: [`rules/cycle-rule-schema.md`](../../rules/cycle-rule-schema.md)
- Branching contract for the registry commit: [`rules/git-safety.md`](../../rules/git-safety.md)
