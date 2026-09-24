---
type: concept
title: The instrument answered a different question
description: Twelve measurement errors across two sessions in one day. Every instrument worked; every answer was true; none of the questions was the one being asked. Why re-reading found none of them, what did, and the one correction shape that survives the session.
tags: [decision, measurement, honesty, tooling, verification]

generated:
  by: claude/opus-5
  at: 2026-09-24
status: stable
sources:
  - id: freshness
    resource: ../../../mechanisms/gates/check_verification_freshness.py
  - id: conventions
    resource: ../../../mechanisms/gates/check_contribution_conventions.py
  - id: measurability
    resource: ../../../squad/measurability.py
  - id: brief
    resource: ../../../mechanisms/cycle/panel_brief.py
  - id: installer
    resource: ../../../mechanisms/distribution/install.sh
---

# The instrument answered a different question

Two sessions spent 2026-09-24 fixing defects in this kit. Along the way they made
**twelve measurement errors between them**. Not one was a misread output, a typo, or a
tool behaving incorrectly. In every case the command ran, returned a true answer, and
answered something other than what was being asked.

They are recorded together because the individual fixes are unremarkable and the
pattern is not.

## The twelve

| What was run | What it answered | What was being asked |
|---|---|---|
| `find -name 'plan-judge*' \| head -1` | the first of six cached plugin versions | which version the manifest resolves to |
| `find -name 'plan-judge*' \| head -1` (again) | a `.json` schema file | the agent's `.md` frontmatter |
| `ls .claude/rules/` | that directory holds no such file | whether the file exists anywhere |
| `git log --all --diff-filter=A -- <two paths>` | never added under those paths | never added |
| `check_evidence_citations.py --plan X` | a library imported and discarded, exit 0 | whether citations resolve |
| `date -r` | local time | a UTC timestamp at `-0300` |
| `grep -c` vs `grep -ci` | two different counts | one question |
| `tail -n; echo $?` | the exit code of `tail` | the exit code of the gate |
| `pgrep -f run_slice_tests` | its own command line, matching forever | whether the suite is running |
| `str.replace` on a reflowed assertion | zero substitutions, silently | the edit was applied |
| `awk '/start/,/end/'` with a range that never closed | the whole file | one section |
| `Report.already_pushed` | which findings **in this range** are pushed | which commits are on the upstream |

Two of them are the same error made twice by the same session, **after** it had already
been diagnosed and fixed once in another command.

## What they have in common

Each instrument has a scope, and the scope is invisible in the answer. `head -1`
does not say there were six. `ls` does not say it looked in one place. A library with
no `__main__` exits 0 exactly as a passing check does. `already_pushed` is a correct,
well-documented set that answers a question one word away from the one it was asked.

This is why re-reading does not find them. Re-reading confirms that the command was
typed correctly and that its output was read correctly — and both were true every
time. The error is in the gap between the question in the head and the question in the
command, and nothing inside the command can show that gap.

**Every one of the twelve was found the same way: by running something of a different
shape.** A gate read as `--json` rather than by hand. A second reader of the same table
consulted. A `find` across the whole tree instead of an `ls` of one directory. A peer
opening the file a session had declared absent. Across five independent reviewers of
one forty-line fix in another session, *no finding came from re-reading* — every one
came from executing the code by a route its author had not taken.

## The dangerous variant

Eleven of the twelve produced a wrong number, which is loud enough to be doubted. One
produced a **right number about the wrong object**: `0 files in .claude/rules/` was
true, and the conclusion "this document does not exist" was not the same sentence. A
57-occurrence evidence document was written on it before a panel seat opened the file
in `docs/program/`.

The same shape appeared twice more. A consumer applying half a fix saw
`AttributeError` from one missing file and reported it — and recorded the *other*
missing file's fail-safe `unknown` as evidence the guard was working correctly. And a
capability gate printed `HOLDS` by hand while dying with `NameError` under `--json`, so
the manual check **confirmed** the route that was broken.

A wrong answer invites doubt. A plausible answer to the wrong question gets written
down as a finding, and then it is load-bearing.

## What actually holds

The correction that survives is not the one a session remembers. Two sessions each
repeated an instrument error hours after diagnosing it, because what they had fixed was
one command, not the reflex.

What holds is the correction written into the **default**:

- `install.sh --apply-upstream` now names every file that moved with the one it applied,
  because a consumer cannot be expected to ask.
- `check_verification_freshness` now has an `interrupted` state, because a killed run
  and a broken suite wrote the same record.
- `panel_brief` no longer names a module without an entry point, because five readers
  ran one and read exit 0 as a pass.
- `squad/measurability.py` exists because two readers of one question had drifted.

None of those is a reminder. Each removes the chance to ask the wrong question.

## What this does not claim

It does not claim the twelve are all of them. They are the ones that surfaced, and they
surfaced because two sessions happened to run the same checks by different routes and
compared notes. The ones where a single route agreed with itself are, by construction,
not in this table.
