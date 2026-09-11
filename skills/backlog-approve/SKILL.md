---
name: backlog-approve
version: 0.1.0
requires: []
description: Render a backlog into one page a person can actually decide on, then turn the ticked items into `approved`. Use when a registry has accumulated items nobody has committed to, when someone asks "can I trust this backlog", or before starting a cycle on work whose scope was never confirmed. Shows what each item claims, what changed that makes it worth doing now, how anyone will know it is finished, and whether the files it cites still exist. Writes nothing without a signature, and refuses a signature that ticked nothing.
user-invocable: true
allowed-tools: Read Glob Grep Bash
argument-hint: "[project-path] [--status triaged|any] | --apply <brief>"
---

# `/backlog-approve` — the question a mechanism cannot ask

`check_backlog_structure.py` already refuses a malformed item, a dangling impediment and
an impediment cycle. None of that answers the only question the person paying for the
work has: **is this the work I want done?**

## The measurement this exists because of

`rules/cycle-backlog.md` calls `approved` a **commitment** — *"somebody decided"* — and
forbids reaching a plan without it. Measured across four real registries on 2026-09-11:

| Status | Items |
|---|---|
| `shipped` | 243 |
| `triaged` | 47 |
| `raw` | 17 |
| `killed` | 15 |
| **`approved`** | **0** |
| `planned` | 0 |

325 items, and the gate the contract calls a commitment had never been crossed once. The
path actually walked is `triaged → shipped`, straight past it.

The cause is not discipline. Before this skill, the only mention of `--to approved`
anywhere in the kit was a line of prose in `rules/cycle-maintenance.md`. **A status
nothing asks for is a status nobody writes** — the same finding that produced
`backlog_status.py` when `planned` was zero everywhere, recorded in `cycle-backlog.md`
as *"every transition was a human editing a line, and the middle one quietly stopped
happening."*

## Use it

```bash
ECO="$([ -d .claude/skills ] && echo .claude || echo .)"

# 1. render the page
python3 "$ECO/skills/backlog-approve/scripts/build_approval_brief.py" .

# 2. read it, tick what you want done, then sign
/sign .squad/records/backlog-approval.md

# 3. write the decision
python3 "$ECO/skills/backlog-approve/scripts/apply_approval.py" . \
  .squad/records/backlog-approval.md
```

`--status any` renders the whole registry instead of only `triaged`; `--stdout` prints
instead of writing; `--dry-run` on the apply step says what would move and moves nothing.

## What the page shows per item, and why only this

| Shown | Answers |
|---|---|
| title + `why_now` | what it claims, and what changed that makes it worth doing now |
| evidence verdict | can the reader still find the files it cites |
| `dod` | how anyone will know it is finished |
| domain · repo · blocked-on | who would do it, and whether it can start |

Deliberately absent: whether the item is well formed. A machine checked that, and
repeating it here would bury the judgement call under findings nobody needs to make.

## The evidence column is measured, not quoted

An item saying `evidence: infra/x.yaml:91` makes a claim about a file. Quoting it back
renders a dead pointer and a live one identically.

| Verdict | Means |
|---|---|
| `checks out` | every path it cites was found |
| `does not check out` | it cites a path that is not there — read that item twice |
| `not verifiable` | it names no path this checker can test. **Not the same as wrong** |

**Extraction is deliberately conservative,** and the reason is a measured failure. An
early version counted `10.0.0.0/8` and `Status.Reachable` as unresolvable files and
reported twelve sound items as having broken evidence; all twelve were fine. A bare
filename in prose (`build_walkthrough.py`) is treated as a mention rather than a
pointer — of 27 such names in one registry, 2 resolved. Over-reporting costs more than
missing: the reader stops trusting the column and it may as well not be there.

## Every box starts empty

Approving is a positive act. An unticked item stays where it was — not rejected, not
killed, simply work nobody has committed to yet, which is the honest state for it.
Pre-ticking would make the default yes-to-everything and turn the signature into a
formality, which is the failure this skill exists to end.

The item boxes sit **above** `## Sign-off` for a mechanical reason: `/sign` ticks every
unticked box in the section that follows the heading, so an item box below it would be
approved by the act of signing rather than by anyone deciding.

## Three refusals

| Situation | What happens |
|---|---|
| brief not signed | nothing written — ticks without a signature are reading notes |
| signed, nothing ticked | refused and said out loud; silent success would look like an approval |
| item not at `triaged` | skipped and named, with the reason `backlog_status.py` gave |

## The half the item list cannot show

A page rendered from the registry shows what somebody wrote down. It cannot show what
nobody wrote down — an item you did not want is visible and can be left unticked, while
an item nobody thought of is invisible, and no amount of careful reading surfaces it.

`traces_to` is what makes that computable. It has been read by `build_agenda.py` since
the brainstorm phase shipped and was written **zero times in 651 items**, because
`cycle-backlog.md` never listed it and `/backlog-item` never asked. Both now do, and the
brief opens with the three states the link makes visible:

| State | Means |
|---|---|
| objective with no item | work you said you wanted that nobody wrote down — **ticking every box still leaves it undone** |
| item with no objective | either the objective was never declared, or the item should not exist |
| citation to a missing id | the objective was withdrawn and the item still claims to serve it |

**With no `.squad/wiki/product/objectives.md` the section reports NOT MEASURED** and
names the document. A project that never ran `/brainstorm-objectives` has nothing to
trace to, and calling its items orphans would invent a standard it never adopted.

## What it does not claim

A signature says the ticked items are the work you want done. It does not say they are
well formed, does not say the estimates are right, and does not say the work will
succeed. It closes exactly one gap: the difference between work that was written down
and work somebody chose.

## Scripts

| Script | Runs it | What it does |
|---|---|---|
| `build_approval_brief.py` | `/backlog-approve` | renders the registry as one decidable page |
| `check_objective_coverage.py` | the brief, and on demand | objectives no item serves, items serving no objective, citations pointing at ids that are gone |
| `apply_approval.py` | `/backlog-approve --apply` | moves the ticked items, via `backlog_status.py` |

`backlog_status.py` stays the only writer of a status line. A second one here would
reopen the exact failure that put `planned` at zero in every install.
