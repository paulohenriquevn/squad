# Two shapes of parallelism, and the one this kit does not have

Running N agents at once is not one technique. It is two, they solve different problems, and this kit implements one of them.

## The two shapes

**Fan-out** — N agents on the SAME work, from different angles. `/review` spawns
5–7 reviewers over one diff: architecture, tests, wiring, cross-validation,
domain. `discover-plan-confidence` runs 4 checkers over one blueprint. The
speed-up is over the *dimensions* of one item, and the output is one verdict.

**Pipeline** — N agents on DIFFERENT work, at different stages. Taken from
[`unclebob/swarm-forge`](https://github.com/unclebob/swarm-forge), whose
`six-pack` runs `specifier → coder → cleaner → architect → hardender → QA`
simultaneously, each in its own worktree, each consuming a queue. While the coder
implements slice 3, the cleaner is on slice 2 and the architect on slice 1. The
speed-up is over the *items*, and the output is a stream.

They are orthogonal. A pipeline stage can itself fan out.

## What this kit has, and what it does not

| | Shape | Where |
|---|---|---|
| ✅ | Fan-out | `/review` (5–7 agents), `discover-plan-confidence` (4 checkers), `cycle-judge-codex` (a second model family over the same artefacts) |
| ❌ | Pipeline | Nowhere. `cycle-idea-to-release` chains DISCOVER → PLAN → IMPLEMENT → REVIEW → RELEASE **one item at a time**, and every phase waits for the previous one to finish on that item |

A consumer with 22 triaged backlog items today processes them strictly in
sequence, and the agent is idle in every phase it is not currently running.

## Three things the pipeline shape requires, which are the interesting part

**Isolation, not detection.** Stages run concurrently, so they cannot share a
working tree. swarm-forge gives each role a git worktree. This kit measured the
alternative on the B-025 run — six reviewers on one tree, a mutation marker
appearing mid-review, and a **false BLOCKER** filed against a symbol that existed
— and built `capture_tree_state` to notice it afterwards. `/review` now passes
`isolation="worktree"`; a pipeline would need the same for every stage.

**Queues with a consumption mode.** swarm-forge declares per role whether it takes
one `task` at a time or a `batch` of everything queued at equal priority. Its
`coder` takes one — implementation is per slice. Its `cleaner`, `architect`,
`hardender` and `QA` take batches, because reviewing five slices together costs
less than reviewing five slices five times. This kit has no queue: a phase is
invoked, or it is not.

**Backward propagation.** A downstream stage that fixes something must return it
without blocking the line. swarm-forge marks each role `forward-only`, `back-one`
or `back-all`, and a back-hop is merge-only — it carries the commit, not a task.

## Why this is written down rather than built

Building a pipeline is not a change to a skill; it is a scheduler, a queue, a
worktree lifecycle and a backward-merge protocol. Writing "we should parallelise"
into a rule and shipping nothing would be the mechanism-with-no-contract shape
this kit names elsewhere, inverted.

What is recorded here is the **distinction**, because the kit had a word for one
shape and no word for the other, and a team without the word cannot notice the
absence. The measured cost is in the table above: items are processed one at a
time, and the phases are idle.

## The gap this rule leaves open

Only one of the two kits ships `capture_tree_state`. The other now passes
`isolation="worktree"` and has **nothing that would notice if that stopped taking
effect** — the worse half of the pair, by the B-025 comment's own reasoning.

Not ported in the same pass on purpose: the detector has seven integration points
including the report renderer, and the two `consolidate_findings.py` have already
diverged this week — copying one wholesale over the other broke a kit. A rushed
port of a detector produces a detector nobody can trust. Recorded here so it is a
decision someone takes, not an oversight someone finds.

## Cross-references

- Fan-out in practice: `rules/cycle-review.md`, `skills/review/SKILL.md`
- Model diversity over the same artefacts: `rules/cycle-judge-codex.md`
- The isolation defect that made the case: the comment above `capture_tree_state`
  in `skills/review/scripts/consolidate_findings.py`
- Source of the pipeline shape: [`unclebob/swarm-forge`](https://github.com/unclebob/swarm-forge)
