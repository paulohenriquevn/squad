---
name: pipeline
version: 0.1.0
requires: []
description: Advance many backlog items through the cycle concurrently, one stage each, with a git worktree per lane and the stage prompts written to disk before they run. Use when a consumer has several triaged items waiting and the phases would otherwise sit idle between them — 22 items processed strictly in sequence is the measured case this exists for. Materialises one agent file per stage per item so a wrong finding can be traced to the instruction that produced it.
user-invocable: true
allowed-tools: Read Glob Grep Bash Write
argument-hint: "{item-id} [{item-id} ...]"
---

# `/pipeline` — many items in flight, one stage each

`skills/_kit-rules/parallelism-shapes.md` names two shapes. This kit had FAN-OUT — N agents on
the same work from different angles — and no PIPELINE. `cycle-idea-to-release`
chains its seven phases for **one item at a time**, so a consumer with 22 triaged
items works them in sequence and every phase idles whenever it is not the current
one.

This decides WHICH item enters WHICH stage and WHEN. It never decides whether a
stage passed: the phases keep their own gates, verdicts and thresholds, and a
scheduler that could overrule one would be a way around it rather than through it.

## Cycle contract

Sits above [`cycle-idea-to-release`](../../rules/cycle-idea-to-release.md) and
schedules it. Every gate that cycle declares still applies per item, including
the alignment gate. **The scheduler never satisfies that gate itself** — it is
answered inside the lane, by a reviewer who is not the brief's author: a person,
or `alignment_judge.py` when none is coming. The distinction is the whole point.
A scheduler that could sign would be deciding a verdict, which is the one thing
this skill refuses to do at any stage.

An earlier version of this paragraph said the gate *"needs a signature no agent
may give"*. That read the rule's real clause — the AUTHOR must not sign — as a
ban on every agent, and the difference is the reason an unattended run used to
stop forever. See `skills/_kit-rules/alignment-threshold.md § Amended 2026-09-01`.

That halt is still the argument for the shape where a person does review. It stops
everything; here it stops one item while the rest move, and the operator's
review becomes a batch instead of an interruption.

## Process

### Step 0 — Ask the registry which items may run

```bash
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/backlog-review/scripts/select_backlog_item.py" \
    BACKLOG.md --json > /tmp/queue.json
```

This applies `cycle-maintenance.md`'s ranking — triaged before raw, then oldest
first — and drops the blocked. **Do not hand-write the list.** An item waiting on
another reads `triaged` on disk and cannot be worked on, and no list kept by hand
knows that: the literal `['B-001', 'B-022', 'B-033']` this workflow shipped with
began with an item blocked on a sponsor decision, in the very registry it was
pointed at, and a whole run went by without anyone noticing.

`from_selection()` in `mechanisms/fleet/pipeline_orchestrator.py` turns that JSON into a
pipeline. Blocked items are carried, not dropped — so the scheduler can say why one
is not running, and `unpark()` can bring it back when the blocker lands.

### Step 1 — Materialise the stage agents

```bash
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/pipeline/scripts/spawn_stages.py" \
    --item B-014 --repo <consumer-path>
```

**Do not pass `--output-dir`.** The destination is `squad.layout`'s answer for
that repo — `<eco>/records/pipeline-agents/<item>` — and the caller is the last
thing that should be deciding it. This step used to document a relative path,
which is relative to whoever is running the command rather than to the project:
on a real consumer it built a second `records/` tree at the repository root while
the cycle's own sat in `.claude/records/`, putting the run's audit trail outside
the tree holding every other record. The old code default was worse still — it
wrote generated per-item files into `.claude/agents/`, where the kit keeps its
declared ones.

One file per stage, written before anything runs, versioned. This is the shape
`/review` has used for years and the first pipeline run did not: six agents ran
over a real backlog, three found defects in this kit — one located an id
collision in `score_alignment.py` with line numbers — and **not one of their
prompts was recoverable**. The transcript records what an agent said; only the
generated file records what it was asked.

Read-only stages carry no writing tool. That is the mechanism; the paragraph in
each template explaining it is the explanation, and the first run had only the
explanation.

### Step 2 — Run the workflow

```
Workflow({scriptPath: "mechanisms/fleet/pipeline_workflow.js",
          args: {selection: <the WHOLE object from Step 0>, repo: "<consumer-path>"}})
```

**The whole object, not the `queue` array.** SELECT emits three keys carrying
items a stage can act on — `queue` (triaged and raw), `awaiting_plan` (approved,
DISCOVER done) and `in_flight` (planned, work started) — and each exists because
a scheduler reading only the earlier ones could not see most of the registry.
Measured on a consumer 2026-09-15 with 102 items: the whole selection builds 71,
of which 56 approved enter at PLAN; the `queue` array alone builds 13, none of
them approved.

This line said `queue` until 2026-09-15, so an operator following it exactly
reproduced a defect the code no longer had. A fix that lands in code and not in
the procedure that invokes it is half a fix, and the missing half is the one a
new reader follows.

`pipeline()`, never `parallel()` — there is no barrier between stages, so one
item may be aligning while another is still discovering. A barrier rebuilds the
sequential chain with extra machinery.

### Step 3 — Read what parked

An item that parks is the gate working. The first run over a real registry returned **0
planned, 3 parked**, and all three refused to fabricate the numbers that would
have let them pass — which is the outcome the anti-patterns ask for.

**A park is not the end of the run, and this sentence used to read as though it were.**
The other lanes keep moving; a parked item is one item held, surfaced with the reason.
What it needs is the reason addressed — usually a criterion rewritten or a number
re-measured — and then `unpark()`. Reading a park as "the run is over" is how a
scheduler built to keep several items moving ends up reporting zero.

### Step 4 — The chain runs to RELEASE

`discover → align → judge → plan → implement → review → release`.

Until 2026-09-14 it stopped at IMPLEMENT, and the two stages after it did not exist —
so a consumer asking for an unattended run got five stages and a stop, whatever was
fixed upstream. REVIEW audits the diff read-only and re-runs the acceptance criteria
against the tree AS IT IS at review time, because a verification does not survive the
tree it measured. RELEASE writes the changelog entry and moves the status.

## Lane budget

Derived, never chosen: `lane_budget()` computes `min(16, cpus-2)` minus REVIEW's
5-7 fan-out. On a 12-core machine that is 3 lanes with at most 1 in REVIEW. An
earlier draft asserted `8`, and an alignment judge refused it — 8 lanes with one
in REVIEW needs 15 agents against a cap of 10, deadlocking on the limit the brief
itself cited.

## Does Not Own

- It does not decide whether a stage passed. Every gate keeps its verdict.
- It does not sign an alignment brief. The lane's own chain does that, through a
  reviewer that is not the author — never the scheduler, and never the author.
- It does not cut a version or merge to a protected branch. RELEASE records what
  shipped and leaves the branch ready; both of those decisions have blast radius
  beyond one item, and several items ship in one release.
- It does not run ACCEPTANCE. That validates a MILESTONE rather than an item, and
  a per-item stage would answer a question nobody asked at this granularity.
- It does not run CODE-QUALITY as a stage. `run_validation.py` invokes it inside
  IMPLEMENT; a stage here would run it twice and make the second run look like an
  independent confirmation of the first.

## Files

| Path | What it is |
|---|---|
| `scripts/spawn_stages.py` | Instantiates the templates into per-item agent files |
| `templates/stage-*.md` | One per stage: frontmatter, tool list, and the stage's contract |
| `../../mechanisms/fleet/pipeline_orchestrator.py` | Lanes, worktrees, batch/task, park, backward hops |
| `../../mechanisms/fleet/pipeline_workflow.js` | The Workflow script that reads the generated agents |

## Related

- Shape and its requirements: [`skills/_kit-rules/parallelism-shapes.md`](../../skills/_kit-rules/parallelism-shapes.md)
- The gate that halts it by design: [`skills/_kit-rules/alignment-threshold.md`](../../skills/_kit-rules/alignment-threshold.md)
- The design it schedules: [`rules/cycle-idea-to-release.md`](../../rules/cycle-idea-to-release.md)
