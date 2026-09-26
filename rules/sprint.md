# Sprint — the block of work, and the only three things it adds
<!-- rule-id: SQ-SPR-01 -->

> NOT a `cycle-*` rule, and the name says so. The chain's cycles are PHASES — BRAINSTORM
> through ACCEPTANCE — and a sprint is not one of them: it spans them. `check_xrefs`
> caught the first spelling — the one with the `cycle-` prefix — and it was right to: a
> reader would look
> for a phase that does not exist, and `cycle-idea-to-release.md` is already the chain.
> The old spelling is deliberately not written here: naming a file that does not exist
> is the broken pointer this kit caps a plan for.

## Purpose

A queue ordered by age is a task list: every item individually justified, the set as a
whole answering to nothing. A sprint is the missing answer — a declared goal, the items
admitted to it, and a close that records what each admitted item came to.

It is a **unit of focus, not of delivery**. Releasing per item is a measured strength of
this chain, and the process model that motivated sprints names *releasing a whole sprint as
one technical package* as an antipattern in the same document that recommends them.

## What it does NOT do, because the kit already does it

| The mechanic | Where it already lives |
|---|---|
| N items in flight at once | `mechanisms/fleet/pipeline_orchestrator.py` — the lane budget is **derived**, after an asserted `8` deadlocked against the agent cap it cited |
| pull the next when one blocks | `mechanisms/cycle/halt_disposition.py` — `RETURN_TO_QUEUE` when the halt is work, `RETAIN_FOR_PERSON` when it is a material impediment. Both move the item out; neither holds the session |
| offer an idle lane again | `mechanisms/fleet/fleet_router.py`, `fleet_idle.py` |

Three names for the mechanics, each measured into existence. Building a fourth would be two
answers to one question, which is the failure this repository has recorded most often.

## The record

One active block, at the data root, named by `squad.paths.sprint_record`:

```
sprint: S-001
goal: the deck's public seam is reachable
opened_by: human/paulo
admitted: B-286, B-288
traces_to: OBJ-2
```

Closing appends `closed_by` and a `## Verdicts` list, one line per admitted item. Opening
the next sprint **archives** the closed one under `records/sprints/` first: the verdicts are
the only durable output a sprint has.

## The four refusals

| Refused | Why |
|---|---|
| a sprint with no `goal` | a block with no goal is the task list this exists to stop being |
| a sprint admitting nothing | focus on nothing, and the band it feeds would order an empty set |
| `opened_by` / `closed_by` that is not `human/<name>` | focus declared by whoever wants to move on is not focus — the argument `approved_by` rests on |
| closing while an admitted item carries no terminal status | an item that quietly leaves a sprint is indistinguishable from one that was never in it |

## Where it sits in the order

`select_backlog_item.rank()` reads the band **third**:

```
1. obligation        source: live-incident — costing while it waits
2. unblocks a halt   finishing it turns a stopped item back into a moving one
3. THE SPRINT        declared focus
4. status            triaged before raw
5. age               the only signal nobody can inflate
```

Focus does not outrank a live incident: the incident is costing now, the sprint says what
matters generally. With no open sprint every item gets the same band, so the order is
exactly what it was — **no sprint means no focus to honour, not a fabricated one**.

## Invocation

The kit is at the repository root in its own checkout and under `.claude/` in a consumer,
so the path is derived rather than written — an instruction that resolves in only one
layout is one `test_no_shipped_instruction_assumes_a_layout` refuses, and it refuses it
because a consumer following it gets *No such file or directory*:

```
SQ="$([ -d .claude/mechanisms ] && echo .claude || echo .)/mechanisms/cycle/sprint.py"

python3 "$SQ" status
python3 "$SQ" open --id S-001 --goal "<what this block is for>" \
    --admit B-286,B-288 --by human/paulo [--traces-to OBJ-2]
python3 "$SQ" admit --item B-290
python3 "$SQ" close --by human/paulo
```

`close` reads each admitted item's status with the registry's own parser. The library takes
those statuses as an argument and never parses `BACKLOG.md` itself, because a second reader
of `status:` is a second answer to what an item's state is.

## Antipatterns

- **Making the sprint a release window.** The antipattern the source model names, and the
  reason this file says *unit of focus* in its first paragraph.
- **A sprint whose goal restates its items.** "Do B-286 and B-288" is not a goal; it is the
  admitted set with a sentence around it.
- **Opening one with `system/`.** An agent declaring what matters is the same shape as an
  agent assigning itself a low uncertainty level, which this kit refuses by requiring
  evidence rather than a self-report.
- **Building WIP limits, replenishment or blocked-item disposition here.** All three exist.
  See the table above.
