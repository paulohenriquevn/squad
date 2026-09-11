---
type: SOP
title: Diagnose whether the squad can run in a project
description: Report which domains have no specialist, which of the project's own skills are undocumented, and whether a review panel can be formed — read-only, and explicit about which sections could not be measured.
tags: [procedure, adoption, audit]

# The OPERATOR's procedure. `SKILL.md` is the contract the agent executes; this is
# what a person needs to run the diagnosis and act on what comes back.
# Derived from the documents in `sources` — no step here was invented.
generated:
  by: claude/opus-5
  at: 2026-09-10
status: stable
sources:
  - id: contract
    resource: ./SKILL.md
  - id: specialists
    resource: ../../agents/README.md
  - id: panel
    resource: ../../rules/review-panel.txt

sop: diagnose-squad-fit
version: 1.0.0
owner: whoever is about to adopt the kit into a project, or about to write its agents
standard: agents/README.md
last_reviewed: 2026-09-10
---

# Diagnose whether the squad can run in a project

## Purpose

Produce the list of agents and skills a project still has to write, and name what
breaks until it does — before the chain runs, rather than one blocked item at a time.

## Prerequisites

- The kit is installed in the target project (`.claude/skills/` or `skills/` exists).
- Nothing else. This procedure reads and never writes.

## Steps

1. **Run** the diagnosis — `/squad-fit`, or the checker directly:
   `python3 skills/squad-fit/scripts/check_squad_fit.py /path/to/project`.
2. **Read `PARTIAL` first, before the verdict.** A clean verdict covers only the
   sections that ran. If a section says NOT MEASURED, close that first — the table in
   `SKILL.md § When a section could not be measured` names what closes each one.
3. **Act on blockers before anything else.** `domain_without_agent` and
   `panel_not_formable` each stop the chain for every item, not for one.
4. **Read deterministic findings (`!`) as facts and heuristic ones (`?`) as questions.**
   `agent_carries_no_commands` is the only heuristic; confirm it by opening the file.
5. **Separate the machine from the project.** `panel_reviewer_unreachable` is about
   THIS host — a missing binary on PATH or an agent absent from this checkout. Filing
   it against the project sends someone to fix a file that is correct.
6. **Register what you will not fix now** — `/backlog-item`. A finding that stays in a
   terminal is a finding nobody tracks.

## Writing what is missing

The diagnosis stops at the report on purpose. Writing a specialist is human work, and
`agents/README.md` says why: *"a specialist with no content would route the item into
an empty prompt, and `route_domain.py` exits 3 when the file does not exist, on
purpose."* A stub named correctly turns a visible failure into a silent one.

What the report gives you is the material: the domain, the repositories the table
assigns to it, and which of them the current file fails to name.

| Finding | What to write | Where the contract is |
|---|---|---|
| `domain_without_agent` | one specialist for that domain | `agents/README.md § Domain specialists` |
| `agent_names_none_of_its_repos` | the `Covers:` line, and the build reality | `agents/README.md § Choosing the granularity` |
| `skill_without_sop` | the operating procedure | `rules/sop-schema.md` |
| `skill_undeclared_auxiliary` | one line in `rules/auxiliary-skills.txt` | that file's own header |
| `panel_not_formable` | seats in `rules/review-panel.txt` | `check_panel_capability.py` |

## Verdicts, and what each obliges

| Verdict | Exit | Obliges |
|---|---|---|
| `SHIPPABLE` | 0 | nothing — but check `PARTIAL` |
| `SHIPPABLE_WITH_CAVEATS` | 0 | read the minors; they are real and cheap |
| `NEEDS_REVISION` | 3 | write the missing files before running the chain |
| `INVALID` | 1 | the chain cannot route or cannot gate. Fix before selecting any item |
| *(any, with `PARTIAL`)* | 2 | a section was not measured. The verdict says nothing about it |

## Escalation

- A section reads NOT MEASURED and the file it names exists → the file does not parse.
  → fix the file; do not read the run as a pass. A checker that looks, sees nothing and
  approves produces confidence where there was no verification.
- `panel_not_formable` and nobody owns `rules/review-panel.txt` → the project cannot gate
  DISCOVER or PLAN at all. → whoever decided to adopt the kit here; this is a decision,
  not a defect.
- `panel_reviewer_unreachable` on a machine that should have the binary → an environment
  problem, not a project one. → whoever owns the environment.
- A domain has no owner to write its specialist → the routing table names a domain nobody
  answers for. → `/backlog-item`, so the gap is tracked rather than remembered.
- The report contradicts `route_domain.py` or `check_panel_capability.py` on the same
  question → a defect in THIS skill, which delegates every judgement precisely so the two
  cannot disagree. → file it against `squad-fit`.

## Competencies

- Reading `PARTIAL` before the verdict. A clean token over an unmeasured section says
  nothing about that section.
- Telling a finding about the project from a finding about this machine —
  `panel_not_formable` versus `panel_reviewer_unreachable`.
- Resisting the stub. A specialist file with the right name and no content silences the
  blocker and routes the item into an empty prompt.

## Cadence

On adoption, and after any restructure that moves or renames a repository. There is no
schedule beyond that: this reports a state that only changes when someone changes it.
