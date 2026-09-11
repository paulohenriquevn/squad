---
name: critic
version: 0.1.0
requires: []
description: 'Run the critic a phase needs when nothing else reviews it — acceptance, code-quality, backlog and release, the four phases measured as having no panel, no judge, no signature and no scorer. The critic RETURNS work rather than blocking: the agent fixes what was named and the phase runs again inside the same autonomous span, and only after the declared rounds does the disposition pass to halt_disposition.py. Use after a phase emits its verdict and before the chain advances.'
user-invocable: true
allowed-tools: Read Glob Grep Bash Agent
argument-hint: "{slug} --phase {acceptance|code-quality|backlog|release}"
---

# `/critic` — a reader for the phases nobody reads

## Why four phases and not ten

Measured across the ten declared phases on 2026-09-11:

| Phase | What already reviews it |
|---|---|
| discover · plan · design | a panel of **three**, 2-of-3, spanning two model families |
| brainstorm · implement | a judge and a scorer |
| **acceptance** | **nothing** |
| **code-quality** | detectors only |
| **backlog** | intake gates only |
| **release** | no scorer |

A critic on a phase that already has three reviewers is a fourth opinion over three, and
`rules/auxiliary-skills.txt` records what repeated redundant output does: it teaches
people to ignore the validator. So the critic goes where there is nothing.

**Acceptance is the urgent one.** It decides whether a release works for its user, it has
no reviewer at all, and `cycle-acceptance.md` carries two debts dated 2026-08-27 that are
exactly a critic's job:

> *"nothing compares the token the agent wrote in the report against the one the script
> emitted; the gate is the script's output existing, not the report agreeing with it"*

> *"no script confronts the caveat list with a tracker"*

## It returns work; it does not stop the chain

This is the constraint the whole design follows. `verdict-bands.txt` already separates
the two axes and argues why deriving one from the other is wrong in both directions:
`FAIL_SOFT` is `redo` and deliberately does **not** block, because walling ordinary
rework *"would wall every loop that is working correctly"*.

So `CRITIC_RETURNED` sits in that band. The agent fixes what was named and the phase runs
again **inside the same autonomous span** — nothing waits for a person.

### And the ceiling, which is the other half

A critic with no round limit stops the chain by another route: two parties disagreeing
forever is a halt nobody declared and nobody can see. After the rounds declared per
phase in `rules/critic-phases.txt` — a release note and an acceptance verdict do not
deserve the same patience — the outcome is `CRITIC_EXHAUSTED` and the disposition passes
to `halt_disposition.py`.

**That is the escalation this kit already has**, the one that decides whether a stop
returns the item to the registry or waits for a person. This adds a critic, not a second
way of halting.

## Run it

```bash
ECO=$([ -d .claude/skills ] && echo .claude || echo .)

# 1 · what is this critic asked, and what did prior rounds already say
python3 "$ECO/mechanisms/cycle/critic_round.py" --phase {phase} --slug {slug} --brief

# 2 · invoke a critic with that brief, unchanged

# 3 · record the round
python3 "$ECO/mechanisms/cycle/critic_round.py" --phase {phase} --slug {slug} \
    --verdict {accepted|returned} --finding "{what to change}"
```

| Exit | Outcome | What happens next |
|---|---|---|
| 0 | `CRITIC_ACCEPTED` | the phase proceeds |
| 1 | `CRITIC_RETURNED` | **the agent fixes what was named and re-runs the phase** |
| 3 | `CRITIC_EXHAUSTED` | `halt_disposition.py` decides |
| 2 | refused | the phase has no critic, or the finding is too thin |

**The brief carries the prior rounds.** A critic that repeats a finding the agent already
addressed produces the round after it, and that is how a ceiling gets reached for nothing.

## What it refuses

- **A phase with no critic declared.** `rules/critic-phases.txt` is the population, and a
  phase absent from it has no critic ON PURPOSE.
- **A `returned` with no finding, or under ten words.** *"I disagree"* returns the work
  and tells the agent nothing to change — which produces this round again, and the one
  after it.

## What it cannot establish

**That a model was called.** The round is recorded by the session that was meant to run
the critic, so a fabricated round produces a file this accepts. Same limit
`check_panel_approval.py` states about the panel record, and nothing here narrows it.

**That a finding is true.** Ten words naming what to change is a floor on the shape of a
finding, not on its correctness.

## Anti-patterns

- **Using it where a panel already votes.** Four opinions over three is noise, and noise
  is what makes people stop reading verdicts.
- **Returning without naming the change.** The floor exists because a critic that cannot
  say what to fix burns a round and leaves the work where it was.
- **Reading `CRITIC_EXHAUSTED` as a failure of the work.** It is a failure to converge,
  which is a different fact and takes a different action.
- **Raising `max_rounds` to win an argument.** The ceiling is what keeps a disagreement
  from becoming an invisible halt.

## Related

- Which phases, and what each is asked: [`rules/critic-phases.txt`](../../rules/critic-phases.txt)
- Why returned does not block: [`rules/verdict-bands.txt`](../../rules/verdict-bands.txt)
- Where an exhausted round goes: `mechanisms/cycle/halt_disposition.py`
- The three-reviewer alternative: [`skills/panel/SKILL.md`](../panel/SKILL.md)
