---
name: squad-fit
version: 0.1.0
requires: []
description: Report whether the squad can actually run in THIS project — which domains have a specialist and which route to nobody, which of the project's own skills are undocumented or invisible to the validator, and whether a review panel can be formed at all. Use this before adopting the kit into a project, after a restructure moved repositories, when items keep coming back BLOCKED for causes that look unrelated, or when someone is about to write agents and skills and needs to know which ones are missing. Read-only, and it says which sections it could not measure rather than reporting them as clean.
user-invocable: true
allowed-tools: Read Glob Grep Bash
argument-hint: "[project-path] (defaults to the current project)"
---

# `/squad-fit` — can the squad run here?

Read a project's install and report what the squad is missing in it. Writes nothing.

The kit ships fourteen squad agents and thirty-odd skills, and it ships
`agents/<domain>.md` **empty on purpose**: a specialist describes repositories that
exist in one ecosystem, so shipping someone else's makes gate G1 refuse every item a
consumer files. `agents/README.md` records what that cost on an adopter in 2026-08-18
— 88 items carrying real `file:line` evidence, all `BLOCKER/unroutable_repo`.

So every project has a gap on the day it installs, and the gap is the design. What
was missing is anything that **measures** it. The kit could say *this one item is
unroutable* (`route_domain.py`, exit 3) and *this one seat cannot be filled*
(`check_panel_capability.py`) — item by item, seat by seat, after the work had already
been selected. Nothing answered the question a person asks before adopting: **what do
I have to write, and what breaks until I do.**

## Cycle contract

None. This skill is a phase of no cycle and belongs to no chain — it is invoked on
demand, by a person, before the chain runs or when the chain keeps stalling. It is
declared in `check_xrefs.py`'s `AUXILIARY_SKILLS` for that reason.

## When to invoke

- **Before adopting the kit** into a project, to see the work in front of you.
- **After a restructure** moved or renamed repositories — the routing table survives
  the move and the specialists it names may not.
- **When items keep coming back BLOCKED** for causes that look unrelated to each
  other. A panel that cannot be formed returns every item as an `access` impediment,
  which reads as many different problems.
- **Before writing agents or skills**, so what gets written is what is missing.

## When NOT to invoke

Do NOT invoke it to fix anything. Read-only, deliberately: a reviewer that also edits
cannot be trusted to report what it found. And do NOT invoke it to judge whether a
specialist is any GOOD — see the limits below, which are the point rather than a
disclaimer.

## What it delegates, and why it delegates all of it

Every judgement here belongs to a mechanism that already owns it:

| Question | Owner | This skill's part |
|---|---|---|
| What does the routing table say? | `route_domain.parse_routing_table` | asks it of every domain at once |
| Where do specialists live? | `convene_panel.agents_dir` | imported, never re-derived |
| Can a panel be formed? | `check_panel_capability.py` | reports its four values, uncollapsed |
| Which skills came from the kit? | `.kit-manifest.txt` | believes its header verbatim |

A second implementation would disagree with the first, and the disagreement surfaces
as a project passing one check and failing the other with nothing having changed.
What this adds is the **set** — the same questions asked of everything at once, so
the answer is a list of work rather than a wall met one item at a time.

## What it checks

### Agents — who owns what

| Check | Severity | Kind | Why it matters |
|---|---|---|---|
| `domain_without_agent` | blocker | deterministic | The domain routes to a file that is not on disk. Every item whose repo lands here stops at BROKEN ROUTE — this is `route_domain.py` exit 3, known before the first item is selected |
| `domain_names_no_agent` | blocker | deterministic | The row covers repos and names no specialist at all |
| `agent_names_none_of_its_repos` | major | deterministic | The routing table sends repos here and the file names none of them. The specialist cannot tell which code it is responsible for |
| `agent_omits_a_repo` | minor | deterministic | It names some and not others — either the file predates the repo, or work is routed somewhere nobody documented |
| `agent_carries_no_commands` | minor | heuristic | No fenced code block, so probably no build command. `agents/README.md` requires commands verified on disk |
| `agent_unrouted` | minor | deterministic | The specialist exists and no domain names it. `route_domain.py` will never reach it |

### Skills — the project's own, never the kit's

Kit skills are excluded by construction: a finding against one is a defect in the
kit, reported against the wrong project.

| Check | Severity | Kind | Why it matters |
|---|---|---|---|
| `skill_frontmatter_broken` | blocker | deterministic | Claude Code will not surface it. Installed and unreachable |
| `skill_missing_field` | major | deterministic | No `description` means nothing can decide when to reach for it |
| `skill_without_sop` | major | deterministic | `SKILL.md` is the contract the agent executes; the SOP is what a person needs to operate it. Every kit skill carries both |
| `skill_undeclared_auxiliary` | minor | deterministic | A skill in no cycle and not in `rules/auxiliary-skills.txt` makes `check_xrefs.py` warn on every run, which teaches people to ignore the validator |

**Skills carrying `user-invocable: false` are not asked for an SOP.** `/review`
generates one knowledge skill per reviewer per plan — five in one measured consumer,
each saying in its own body *"not invoked directly"*. An SOP is the procedure a person
follows to operate the skill; for an act nobody performs there is no procedure.

### Panel — can DISCOVER and PLAN be gated at all

| Check | Severity | Why it matters |
|---|---|---|
| `panel_not_declared` | blocker | There is no `rules/review-panel.txt` here. What an install predating the declaration looks like — closed by copying the kit's template, not by authoring a roster |
| `panel_not_formable` | blocker | The declaration forms no panel for some gated phase. Every item reaching DISCOVER or PLAN returns as an `access` impediment. Fails on every machine, CI included |
| `panel_reviewer_unreachable` | major | The declaration is valid and a reviewer is missing HERE — no such agent in this project, or no such binary on PATH |

**Absent and invalid never collapse either.** `check_panel_capability.py` reports both
as VIOLATED, and from its seat they are the same fact: a project that cannot form a
panel. But the person reading this is deciding what to do next, and the two next steps
do not overlap — a missing file is closed by copying the kit's template, a present one
that forms no panel is a roster somebody has to edit. Measured across three real
consumer installs: all three had no file at all, and a report saying *"a phase has
fewer than three seats"* would have sent three people to open a file that was not there.

**`panel_not_formable` and `panel_reviewer_unreachable` never collapse.** `check_panel_capability.py` separated them on 2026-09-08
and recorded the cost of conflating them: with a PATH holding no `codex` the gate
reported VIOLATED, which would have failed CI for a repository with nothing wrong with
it. A declaration that can form no panel anywhere is the project's defect; a reviewer
missing on this machine is the operator's impediment.

## What it does NOT check — named, so the claim stops outrunning it

- **Whether an agent is any good.** It counts whether the file names the repos the
  table assigns it. A specialist naming all of them, every invariant wrong, reads as
  clean here. Judging a specialist means knowing the domain, which is exactly what the
  specialist exists to hold.
- **Whether a build command works.** The README requires commands "verified on disk".
  This reports whether a command block is present, never whether running it succeeds —
  running a consumer's build from a read-only diagnostic is a side effect nobody asked
  for.
- **Whether a skill does what it says.** Structure only. A skill whose body contradicts
  its description passes.
- **Whether a specialist is still true.** A file written for a topology that changed
  two quarters ago reads exactly like one written yesterday.

## Verdict

Derived from the findings, never asserted. Tokens come from
[`rules/verdict-bands.txt`](../../rules/verdict-bands.txt) and are never invented —
a test asserts that every token this skill can emit is declared there.

| Verdict | Condition | Exit |
|---|---|---|
| `SHIPPABLE` | no findings | 0 |
| `SHIPPABLE_WITH_CAVEATS` | minors only | 0 |
| `NEEDS_REVISION` | at least one major | 3 |
| `INVALID` | at least one blocker | 1 |

## When a section could not be measured

**A section that was not measured reports no verdict, and the run exits 2** — even
when every section that DID run came back clean. Exiting 0 there would tell a caller
the squad fits, about an install where nothing looked at routing.

The report names each unmeasured section and why, because a section reporting no
findings and no reason is indistinguishable from a clean one. The dataclass refuses to
be constructed without the reason, so the omission is a crash rather than a silent
pass.

Three things make a section unmeasurable, and each says what closes it:

| Section | Cause | What closes it |
|---|---|---|
| agents | no routing table | `detect_domains.py --root . --write` |
| agents | the table exists and does not parse | fix the table; a file that does not parse tested nothing |
| skills | neither `.kit-manifest.txt` nor `skills/map.md` | re-run the installer to regenerate the manifest |
| panel | the declaration does not parse | fix `rules/review-panel.txt` |

**The skills case is the one worth understanding.** With neither file, a kit skill and
a project skill are indistinguishable. The first version of this check returned an
empty set there and reported everything as the project's — *"over-reporting rather
than under-reporting, the safe direction for a diagnostic"*. Measured against a real
consumer install with no map: **51 major findings, every one against a kit skill, none
actionable.** Over-reporting is not a safe direction. It is the same substitution as
passing, made against a different column, and a report of 51 items nobody can act on
is read once.

## Usage

```bash
ECO=$([ -d .claude/skills ] && echo .claude || echo .)
python3 "$ECO/skills/squad-fit/scripts/check_squad_fit.py"
python3 "$ECO/skills/squad-fit/scripts/check_squad_fit.py" /path/to/project --json
```

Read the output and report it. Deterministic findings (`!`) are facts; heuristic ones
(`?`) are questions a person answers. Do not edit anything.

## Anti-patterns

- **Writing a specialist to silence `domain_without_agent`.** A file with the right
  name and no content routes the item into an empty prompt, which is why
  `route_domain.py` exits 3 on absence rather than substituting a default. The blocker
  is the honest state; a plausible stub trades a visible failure for a silent one.
- **Reading a clean verdict without reading `PARTIAL`.** The verdict covers only the
  sections that ran.
- **Treating `agent_carries_no_commands` as certain.** It is the one heuristic here.
- **Treating `panel_reviewer_unreachable` as a repository defect.** It is a fact about
  this machine, and filing it against the project sends someone to fix a file that is
  correct.
- **Invoking it to fix something.** Read-only. That is `/backlog-item`'s business,
  which is where a finding becomes tracked work.

## Related

- What a specialist must carry: [`agents/README.md`](../../agents/README.md)
- Deriving the routing table: [`skills/backlog-init/SKILL.md`](../backlog-init/SKILL.md)
- The panel and its seats: [`rules/review-panel.txt`](../../rules/review-panel.txt)
- Declaring your own skills: [`rules/auxiliary-skills.txt`](../../rules/auxiliary-skills.txt)
- Registering what this finds: [`skills/backlog-item/SKILL.md`](../backlog-item/SKILL.md)
