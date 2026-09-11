---
name: panel
version: 0.1.0
requires: []
description: 'Run the review panel a gated phase needs — convene the assigned reviewers, brief each one against the phase contract, invoke them, record their votes, and tally. Use when a phase gated by a panel (DISCOVER, PLAN, DESIGN) has an artifact ready and check_panel_approval reports NO_RECORD. The scripts assign, brief and validate; this skill is what actually invokes the reviewers, because a Python mechanism can refuse an absent panel and cannot be the thing that runs one.'
user-invocable: true
allowed-tools: Read Glob Grep Bash Agent
argument-hint: "{slug} --phase {discover|plan|design}"
---

# `/panel` — the step between "a panel is required" and "a panel voted"

`convene_panel.py` assigns. `review_panel.py` tallies. Between them sat nothing, and
issue #65 named the consequence: *"the panel is declared and computable and no phase
convenes it."* The mechanisms were right and unreachable.

## Why a skill and not a script

A `loop-*` plugin is an agentic halt-loop driven by a stop hook, and a subagent is
invoked by a session. So a Python mechanism can decide who must review and refuse their
absence — it cannot be the thing that runs them. `convene_panel.py` says this about
itself and `check_auditor_coverage.py` takes the same split.

This skill is the half that invokes. Everything it does NOT invoke is a script, so the
session composes nothing: the artifact paths, the contract, and the questions are
derived from the phase.

## Run it

```bash
ECO=$([ -d .claude/skills ] && echo .claude || echo .)

# 1 · assign — three reviewers, two model families, from rules/review-panel.txt
python3 "$ECO/mechanisms/cycle/convene_panel.py" \
    --slug {slug} --phase {phase} --author {who-wrote-it} --project . --write

# 2 · see who was assigned and what they will read
python3 "$ECO/mechanisms/cycle/panel_brief.py" --slug {slug} --phase {phase} --project .
```

### 3 · Invoke each reviewer

For every assigned agent, print its brief and invoke it with that text verbatim:

```bash
python3 "$ECO/mechanisms/cycle/panel_brief.py" \
    --slug {slug} --phase {phase} --project . --reviewer {agent}
```

**Pass the brief unchanged.** It names the contract, the artifacts, the author, and the
verdict vocabulary. A reviewer told "review this" reviews whatever it decided to look
at, and three such reviews are not a panel — they are three opinions about three
different questions.

Invoke `builtin` seats as subagents. Invoke a `codex` seat through its own command; the
seat's `invocation` field in the assignment says which it is.

### 4 · Record each vote as it comes back

```bash
python3 "$ECO/mechanisms/cycle/cast_vote.py" --slug {slug} --phase {phase} \
    --reviewer {agent} --model {model} --verdict {approve|return|abstain} \
    --reason "{at least fifteen words}"
```

It refuses what the tally would refuse later — an unassigned reviewer, the author, a
duplicate seat, a reason under fifteen words — three invocations earlier than
`review_panel.py` would.

### 5 · Tally

```bash
python3 "$ECO/mechanisms/cycle/review_panel.py" --record .squad/records/panels/{slug}-{phase}.json
```

`APPROVED` needs 2 of 3 **and** approvals spanning two model families. Two reviewers from
the same family agreeing is the correlated failure the outside seat is bought to catch.

## What this cannot establish, and says so

**That a model was called.** The record is written by the session that was meant to
collect the votes, so three fabricated votes produce a file the tally accepts. This
skill shortens the distance — the brief is derived, the vote is validated against the
assignment — and does not close it. `check_panel_approval.py` states the same limit
about the record, and nothing here narrows it.

**That a reason is true.** The floor is fifteen words saying what was checked against
which evidence. Nothing confronts that claim with the evidence.

## Anti-patterns

- **Writing the votes yourself.** The refusals above are about form. Form is all they
  can be about, which is exactly why the invocation has to be real.
- **Composing your own brief.** Then the panel judges against whatever you framed, and
  the contract the phase declares was not used.
- **Reading an abstention as agreement.** It is counted as an incomplete panel. A
  reviewer that could not audit did not approve.
- **Re-running `convene_panel.py --write` after votes exist.** It rewrites the
  assignment; votes already cast then reference a roster that changed.

## Related

- Who sits: [`rules/review-panel.txt`](../../rules/review-panel.txt)
- What DESIGN reviewers are asked: [`rules/design-golden-rule.md`](../../rules/design-golden-rule.md)
- The gate that refuses an absent record: `mechanisms/gates/check_panel_approval.py`
- Why an author may not sit: [`skills/_kit-rules/alignment-threshold.md`](../_kit-rules/alignment-threshold.md)
