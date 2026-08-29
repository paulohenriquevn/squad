---
name: sop-run
description: Execute a Standard Operating Procedure and record what actually happened — which steps ran, which were skipped or adapted, and what condition forced each deviation. Use when following a documented procedure (install, propagate, port, release), when the situation in front of you differs from what the procedure assumed, or when a run needs an auditable record. This is the judgement half — the SOP says what to do, and this records what was decided when reality disagreed.
user-invocable: true
allowed-tools: Read Write Edit Bash Glob Grep
argument-hint: "{sop-slug, e.g. 'port-fix-between-kits'}"
---

# SOP Run

The SOP is the script. This is the judgement that runs it, written down.

## Why the record is separate from the procedure

A procedure that absorbs its own exceptions stops being a procedure: the next
reader cannot tell the official sequence from the six times somebody worked
around it. So deviations go here, and `/sop-review` decides later whether a
repeated deviation means the SOP should change.

## Steps

1. **Read** the SOP end to end BEFORE starting, and check the prerequisites. A
   prerequisite discovered mid-run is a step performed on a system that was not
   ready.
2. **Note** the SOP's `version` — the record binds to the version that was
   followed, not to whatever the file says later.
3. **Perform** each step in order, recording `done` / `skipped` / `adapted` /
   `blocked` as you go. Record as you go, not from memory afterwards.
4. **Stop** at any condition the `## Escalation` section names, and follow the
   route it gives.
5. **Write** every deviation with three things: the **condition you observed**,
   what you did **instead**, and **who decided**. A deviation missing the
   condition is not judgement — it is improvisation with better manners, and it
   teaches the next reader nothing.
6. **Record** the outcome as `COMPLETED`, `COMPLETED_WITH_DEVIATIONS` or
   `ABORTED`. A `COMPLETED` on a run that deviated contradicts its own body.
7. **Run** `python3 "$([ -d .claude/skills ] && echo .claude || echo .)/scripts/check_sop_run.py"` and fix what it names.

## The step that is easy to skip and worth the most

Step 5's **condition**. Everything else in this record is bookkeeping; the
condition is the only part that answers the question `/sop-review` will ask
later — *should the procedure change, or was this situation singular?* Without
it, a deviation is unusable evidence.

## Where to put it

`records/sop-runs/{slug}-{YYYY-MM-DD}.md`, pointing at the SOP by slug.

## Exploratory mode

Running something that has no SOP yet is legitimate and useful: record it the
same way, leave `sop:` naming the slug you intend to create, and hand the record
to `/sop-author`. A SOP written from a real record beats one written from a
desk, which is why `/sop-author` refuses the other order.

## When NOT to invoke

- Nothing was executed. A record of a procedure nobody ran is the fabricated
  evidence this ecosystem caps a plan at 49 for.
- The work is a cycle phase — `/implement`, `/review` and the rest already write
  their own records, and a second one would be a parallel trail that drifts.
- You are mid-run and tempted to write the record afterwards from memory. Say so
  in the record instead; a reconstructed run is worth less and should not look
  like a contemporaneous one.
