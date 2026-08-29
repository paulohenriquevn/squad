---
name: sop-review
description: Audit this project's SOPs and their run records — procedures past their review date, steps nobody ever accounts for, deviations that keep recurring, competencies nobody is verified for, and procedures with no run at all. Use when asking "are our documented procedures still true?", before onboarding someone onto a procedure, after a system change that may have invalidated one, or when a SOP keeps being worked around. Reports and never edits.
user-invocable: true
allowed-tools: Read Bash Glob Grep
argument-hint: "{optional sop-slug; default: every SOP}"
---

# SOP Review

The ways a documented procedure rots, checked on purpose rather than noticed by
accident.

## What it audits

| Question | Mechanism | Kind |
|---|---|---|
| Is the shape sound? | `check_sop_structure.py` | deterministic |
| Does each record account for its procedure? | `check_sop_run.py` | deterministic |
| Has a SOP passed its review interval? | `check_sop_structure.py` (`sop_stale`) | deterministic |
| Has a SOP ever been run? | this skill, over `sop-runs/` | deterministic |
| Does the same deviation keep recurring? | this skill, reading conditions | heuristic |
| Is anyone verified for each competency? | this skill, against run records | heuristic |

Every finding declares its kind. A heuristic reported as a fact is how a report
earns the habit of being ignored.

## Steps

1. **Run** `python3 "$([ -d .claude/skills ] && echo .claude || echo .)/scripts/check_sop_structure.py"` and
   `python3 "$([ -d .claude/skills ] && echo .claude || echo .)/scripts/check_sop_run.py"`. These are the deterministic floor; do not
   restate by hand what they already computed.
2. **List** every SOP with no run record. A procedure documented and never
   performed is either dead or a description of hope; both are worth naming.
3. **Read** the deviations across runs of the same SOP and group them by the
   condition observed. **The same condition twice is the finding**: the
   procedure's assumption is wrong, not the operator's judgement, and the fix is
   a step or a branch — not a third person working around it.
4. **Cross** the `## Competencies` matrix with who appears as `operator:` in the
   records. A competency nobody is verified for is a single point of failure the
   matrix is hiding.
5. **Report**. Never edit a SOP from this skill — a reviewer that fixes what it
   finds is a reviewer nobody can trust to have found everything. Hand the
   findings to `/sop-author`.

## The judgement this skill does not make

Whether a deviation was correct. That belongs to whoever was there, and the
record exists so a human can weigh it later. What this skill decides is narrower
and mechanical: whether the evidence is legible, current, and complete enough for
that weighing to be possible at all.

## When NOT to invoke

- The project has no SOPs. The report would be an empty gate, and the honest
  answer is that there is nothing to audit yet.
- You intend to fix what you find in the same pass. Split it: review, then
  author. The separation is the point.
- You want to know whether a procedure is a GOOD procedure. This skill measures
  whether it is a live and legible one.
