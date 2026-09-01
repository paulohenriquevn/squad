# Two shapes of parallelism, and how the kit came to have both

Running N agents at once is not one technique. It is two, they solve different
problems, and this kit now implements both. It implemented one of them when this
was written, and the record of that gap is why the second one got built.

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
| ✅ | Pipeline | `scripts/pipeline_orchestrator.py` and `/pipeline` — a lane per item with its own worktree, batch/task consumption per stage, backward hops carrying a commit. `cycle-idea-to-release` still takes **one item at a time**, which is correct: it is the chain, and the pipeline is what runs many chains at once |

The measured case that made it worth building: a consumer with 22 triaged backlog
items processed them strictly in sequence, with the agent idle in every phase it
was not currently running.

## Three things the pipeline shape requires — which became its specification

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

All three are met: `Item.worktree` with a live/released set, `take_batch()`
reading a per-stage `CONSUMPTION` mode, and `send_back(slug, to, commit)` whose
signature carries the commit rather than a task.

## Why it was written down before it was built

The three requirements above were not a wish list; they became the specification.
Writing "we should parallelise" into a rule and shipping nothing would have been
the mechanism-with-no-contract shape this kit names elsewhere, inverted — so what
got recorded first was the **distinction**, because the kit had a word for one
shape and no word for the other, and a team without the word cannot notice the
absence.

The sequence is the point. Naming the gap is what made it a thing someone could
close, and the closing implementation was checked against these three clauses
rather than against taste. An alignment judge then refused its first draft for
omitting one of them — backward propagation, in a design resting on the very rule
that names it as one of three things the shape needs.

## The gap this closed

An earlier version of this section recorded that only one of the two kits shipped
`capture_tree_state`, leaving the other passing `isolation="worktree"` with
nothing that would notice if that stopped taking effect. **Both kits ship it
now.** The note stays as a record of how the pair is meant to work: isolation is
the fix and the detector is what proves the fix is still in force, so a kit that
has one without the other is the half that fails quietly.

## Cross-references

- Fan-out in practice: `rules/cycle-review.md`, `skills/review/SKILL.md`
- Model diversity over the same artefacts: `rules/cycle-judge-codex.md`
- The isolation defect that made the case: the comment above `capture_tree_state`
  in `skills/review/scripts/consolidate_findings.py`
- Source of the pipeline shape: [`unclebob/swarm-forge`](https://github.com/unclebob/swarm-forge)
