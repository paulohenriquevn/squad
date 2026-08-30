---
name: sop-author
description: Write or revise a Standard Operating Procedure for something this kit does repeatedly — installing into a consumer, propagating a delta, porting a fix, cutting a release. Use when someone asks "how do we do X here?" and the answer lives in a script header, in one person's memory, or in a chat thread; when a procedure was performed and nobody wrote it down; or when an existing SOP no longer matches how the work is actually done. Refuses to write a procedure nobody has performed.
user-invocable: true
allowed-tools: Read Write Edit Bash Glob Grep
argument-hint: "{procedure, e.g. 'porting a fix between the two kits'}"
---

# SOP Author

Write the **static script**: prerequisites, the official sequence, the branch
points, and — the part most procedures omit — where the script stops applying.

The contract is `rules/sop-schema.md`. Read it before writing; it carries the
required structure and the reason behind each hard gate.

## The refusal that comes first

**Do not write a SOP for a procedure nobody has performed.** The steps will be
what someone imagines the work to be, and the first real run will contradict
them. If the procedure has not been run, say so and offer the alternative: run
it once with `/sop-run` in exploratory mode, then write the SOP from that record.

This is not process for its own sake. The SOP shipped with this kit —
`port-fix-between-kits` — carries two steps that were improvised during the run
that produced it, and that nobody would have predicted from a desk.

## Steps

1. **Find** the procedure's current home — a script header, a rule, a commit
   message, a chat. Quote it; that text is the draft nobody wrote down.
2. **Confirm** it has been performed, and by whom. Ask for the run if there is
   one; a `sop-runs/` record is the best possible input.
3. **Write** each step opening with an imperative verb and naming the command
   when there is one. "Verify the branch is `workspace` — `git branch
   --show-current`" beats "the branch should be workspace": the second describes
   a state, and nobody performs a description at 3am.
4. **Draw** the decision points as a mermaid `flowchart TD`, and check every
   branch reaches a step or an escalation. A question with one answer is not a
   decision.
5. **Write** `## Escalation` last and never skip it. Ask: *what did the person
   who ran this hit that the steps do not cover?* Each entry is a condition, an
   arrow, an action, and who decides.
6. **Fill** `## Competencies` only when more than one role performs the work,
   and say how each competency is verified — a matrix listing who may act
   without saying how anyone knows they can is a training record with the
   training left out.
7. **Run** `python3 "$([ -d .claude/skills ] && echo .claude || echo .)/scripts/check_sop_structure.py"` and fix what it names.

## Where to put it

`records/sops/{slug}.md`. The slug is stable and never renamed: run
records point at it, and a renamed SOP orphans its own history.

## Does Not Own
- Judge whether the steps are the RIGHT steps. That is domain knowledge held by
  whoever does the work; this skill shapes what they say, it does not supply it.
- Write a `standard:` field naming ISO, OSHA or any norm without evidence the
  procedure was checked against it. Citing a standard nothing verified is the
  fabricated-mechanism defect in a compliance costume.
- Fold exceptions into `## Steps`. The sequence carries the official path;
  everything else belongs in `## Escalation`, or the reader can no longer find
  the path.

## When NOT to invoke

- The procedure is a **phase of the cycle**. `rules/cycle-*.md` owns those, and a
  SOP restating one creates a second source of truth for a single contract.
- It happens once. A SOP is for what repeats; a one-off belongs in the record of
  the thing it was part of.
- Nobody has performed it. See the refusal above.
