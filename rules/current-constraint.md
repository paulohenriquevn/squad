# Current constraint — a lens, not a gate
<!-- rule-id: SQ-LAD-01 -->

What currently limits the ecosystem's ability to ship value. Declared by a human, dated, with a review date.

## What this is for

A maintenance squad's characteristic failure is **local optimization**: shipping ten well-evidenced micro-evolutions into a stage that was never the limit, and mistaking the activity for throughput. This file exists so that `/discover-execute` can ask *"where does this sit in the flow?"* while writing an opportunity — and so that the answer comes from a declaration someone made on the record, rather than from whatever the agent finds convenient in the moment.

## What this is NOT

**It is not a gate.** No item is blocked, deprioritized or rejected for failing to touch the constraint. `/discover-execute` reads this file, states the relation in the opportunity's *Constraint relation* corner, and moves on.

The reason is measurement. A hard gate asking *"does this touch the constraint?"* against data that does not exist would be answered by assertion — and an assertion dressed as a measurement is precisely what gate G5 of `cycle-backlog.md` exists to refuse. Building it into this corner would reproduce, one file over, the defect the system was designed to prevent.

**WHICH data exists, named rather than waved at.** Until 2026-09-22 this paragraph said *"we do not currently instrument flow across the ecosystem"* and listed four absences. Three of the four had stopped being true, and the sentence outlived them — a declared absence surviving the fact that justified it, which is the class
[`a-claim-about-now-is-not-a-fact-that-survives.md`](../docs/wiki/decisions/a-claim-about-now-is-not-a-fact-that-survives.md) records. A blanket refusal is worse than a missing metric, because the refusal is what somebody reads before deciding not to measure.

| Measure | State | Where |
|---|---|---|
| throughput | **computed** — releases per day over the observed window, `None` while nothing has shipped | `board_state._delivery` |
| WIP | **computed** — phases in flight, with starts older than `ABANDON_AFTER_HOURS` dropped | `board_state._wip` |
| item lead time | **computed** — registry entry to terminal, p50 in days, carrying the subset it was measured over | `board_state._delivery` |
| per-stage timing | **derivable, no substrate yet** — `cycle_events` emits `cycle:phase:start` / `:end` with slug and timestamp; this repository's stream is empty because no chain has run to completion here |
| wait time, blocked time | **absent** — an item records that it is blocked, never for how long |
| cumulative flow | **absent** — needs per-stage timing first |

**The five DORA metrics are refused, and the refusal is specific.** Four of them measure a DEPLOYMENT, and this system does not deploy: it cuts a tag that a consumer installs. Naming tag frequency *"deployment frequency"* would be a number whose name promises what it does not measure. The fifth, change lead time, needs commit → production and has no end point — `git tag` returns **zero** in this repository, so the release cycle has never run to completion here.

| DORA metric | What is missing first |
|---|---|
| change lead time | a tag. Zero today |
| deployment frequency | a deploy concept, separate from release |
| change fail rate | "a release that degraded something". The nearest thing is `regression_of` plus an ACCEPTANCE that did not accept, and that is a PROXY with its own name, never this metric under a borrowed one |
| failed deployment recovery time | incident start and end, from a running system this kit does not watch |
| deployment rework rate | no analogue at all |

Filed and decided as kit#163. What would change the answer is a chain that reaches a tag; per-stage timing becomes derivable on the first complete run, with no new instrumentation.

So the corner is **advisory and may be answered `unknown`.** `unknown` is an honest, complete answer. It is not a finding, it is not debt, and it does not weaken the opportunity that carries it.

## Empirical identification — opportunistic, never required

The Squad's own cycles may surface real flow evidence as a by-product: a `--mode review` sweep noticing that one repo's PRs sit for days, a `live-test` run measuring that deploys lag merges by a week, a `--mode evolve` measuring a pipeline's duration. When that happens, record it here with its source and date.

This is **opportunistic**. No phase is required to produce it, no verdict depends on it, and no run is incomplete without it. If instrumenting flow properly is ever worth doing, it is worth doing as a backlog item measured like any other — not as a tax on every discovery.

## Declaration

```
status      = undeclared
declared_by =
declared_on =
review_on   =
constraint  =
evidence    =
kind        = physical | policy | external
```

### Field contract

| Field | Meaning |
|---|---|
| `status` | `undeclared` \| `declared` |
| `declared_by` | The human who made the call. A constraint with no name attached is a rumour. |
| `declared_on` | Absolute date. Constraints move; an undated one is unfalsifiable. |
| `review_on` | Absolute date this declaration must be revisited. Section 5.5 of the discipline: elevating a constraint relocates it, and a policy written for a constraint that moved outlives its own reason. |
| `constraint` | One sentence naming the limiting factor. |
| `evidence` | What supports it — measured, observed, or explicitly `qualitative judgement`. Say which. |
| `kind` | `physical` (capacity of people, pipelines, environments), `policy` (rules and approvals the organisation could change tomorrow), `external` (outside our control). |

## Current state

**`status = undeclared`.**

Nothing is declared yet, and the system works without it: `/discover-execute` writes `Constraint relation: unknown — no constraint declared` and produces a complete, valid opportunity. Declaring one sharpens prioritisation; not declaring one costs nothing but that sharpening.

## Anti-patterns

- **Declaring a constraint to make the corner look filled.** `unknown` is the honest answer until someone actually decides. A fabricated declaration is worse than none: every opportunity after it inherits the fabrication as context.
- **Naming a team as the constraint.** Constraints are stages, policies, capacities and dependencies. "The backend team" is a stage described by its people, and describing it that way turns a flow problem into a performance conversation.
- **Letting the declaration outlive its `review_on`.** An expired declaration is stale context that reads as current. `/discover-execute` surfaces the expiry rather than trusting the value.
- **Turning this into a gate.** The moment an item is refused for not touching the constraint, the corner starts being answered strategically instead of honestly.

## Cross-references

- Consumer: `rules/cycle-discover.md` — reads this while writing the *Constraint relation* corner
- Intake gate that this file must not become: `rules/cycle-backlog.md`
