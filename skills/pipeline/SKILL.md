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

`rules/parallelism-shapes.md` names two shapes. This kit had FAN-OUT — N agents on
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
the alignment gate — which **cannot be satisfied by the pipeline**, because
`ALIGNED` needs a signature no agent may give.

That halt is the argument for the shape, not against it. Today it stops
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

`from_selection()` in `scripts/pipeline_orchestrator.py` turns that JSON into a
pipeline. Blocked items are carried, not dropped — so the scheduler can say why one
is not running, and `unpark()` can bring it back when the blocker lands.

### Step 1 — Materialise the stage agents

```bash
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/pipeline/scripts/spawn_stages.py" \
    --item B-014 --repo <consumer-path> \
    --output-dir records/pipeline-agents/b-014
```

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
Workflow({scriptPath: "scripts/pipeline_workflow.js",
          args: {queue: <the "queue" array from Step 0>, repo: "<consumer-path>"}})
```

`pipeline()`, never `parallel()` — there is no barrier between stages, so one
item may be aligning while another is still discovering. A barrier rebuilds the
sequential chain with extra machinery.

### Step 3 — Read what parked

An item that parks is the gate working. The first run over `theo` returned **0
planned, 3 parked**, and all three refused to fabricate the numbers that would
have let them pass — which is the outcome the anti-patterns ask for.

## Lane budget

Derived, never chosen: `lane_budget()` computes `min(16, cpus-2)` minus REVIEW's
5-7 fan-out. On a 12-core machine that is 3 lanes with at most 1 in REVIEW. An
earlier draft asserted `8`, and an alignment judge refused it — 8 lanes with one
in REVIEW needs 15 agents against a cap of 10, deadlocking on the limit the brief
itself cited.

## Does Not Own

- It does not decide whether a stage passed. Every gate keeps its verdict.
- It does not sign an alignment brief. No agent may.
- It does not run IMPLEMENT or later. Those write to the repository, and a
  writing stage needs its own decision about what its tool list should be —
  named here rather than shipped with permissions nobody examined.

## Files

| Path | What it is |
|---|---|
| `scripts/spawn_stages.py` | Instantiates the templates into per-item agent files |
| `templates/stage-*.md` | One per stage: frontmatter, tool list, and the stage's contract |
| `../../scripts/pipeline_orchestrator.py` | Lanes, worktrees, batch/task, park, backward hops |
| `../../scripts/pipeline_workflow.js` | The Workflow script that reads the generated agents |

## Related

- Shape and its requirements: [`rules/parallelism-shapes.md`](../../rules/parallelism-shapes.md)
- The gate that halts it by design: [`rules/alignment-threshold.md`](../../rules/alignment-threshold.md)
- The design it schedules: [`rules/cycle-idea-to-release.md`](../../rules/cycle-idea-to-release.md)
