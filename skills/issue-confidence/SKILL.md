---
name: issue-confidence
version: 0.1.0
requires: []
description: 'Score an issue draft before it is filed, then file it — carrying what developers measurably use — weighted by the FSE 2008 survey of 872 developers, where steps to reproduce is wanted by 83%, severity by 0%, and incomplete information is the problem ranked as causing the most delay at 74%. Use whenever a finding has a repro and evidence, from any source: a triage file, a phase caveat, an ad-hoc observation, a re-verification. Scores the draft before filing, refuses a body carrying a secret, and requires a duplicate check because duplication is the leading cause of a report nobody can reproduce.'
user-invocable: true
allowed-tools: Read Glob Grep Bash Write
argument-hint: "{what you found, in your own words}"
---

# `/issue-confidence` — how much of the report the fixer can act on

An issue is a message to somebody who was not there. Everything below follows from
that, and from two studies rather than from taste.

## The measurement this is built on

**Bettenburg et al., *"What Makes a Good Bug Report?"*** (FSE 2008) asked **872
developers** at APACHE, ECLIPSE and MOZILLA what they use when fixing a bug, and asked
reporters what they supply:

| | developers want | reporters supply |
|---|---|---|
| steps to reproduce | **83%** | *not in the top* |
| stack traces | 57% | — |
| observed behaviour | 33% | 48% |
| expected behaviour | 22% | 27% |
| version | 12% | 22% |
| operating system | 4% | 20% |
| **severity** | **0%** | — |
| **hardware** | **0%** | — |

And what delays a fix most, by the same developers: **incomplete information, 74%** —
ahead of duplicates (10%) and far ahead of spam (0%).

**Rahman et al., *"Why are Some Bugs Non-Reproducible?"*** (arXiv:2108.05316) analysed
non-reproducible reports across Firefox and Eclipse and found **duplication the single
most dominant factor**, at roughly 29%.

Three consequences, and they are the whole skill:

1. **The repro is the report.** It is the most wanted item and the one most often
   absent. Everything else is context around it.
2. **Severity is for triage, not for the fix.** Developers fixing a bug do not use it —
   0%. It is still worth stating, for the different reader who decides what gets looked
   at, and `score_issue.py` weights it at zero and says so rather than dropping it.
3. **Deduplicating is not politeness.** It is the highest-yield check available,
   because a duplicate is the leading cause of a report nobody can reproduce.

## Filing is the default, not a question

A finding with a repro and evidence → **file it now**. Do not ask whether to; do not
mention it in a report instead. Mentioning without filing is the worst outcome: it
creates the feeling of coverage and the bug is never tracked.

Pause only for a bulk action (more than five at once) or a destructive one — editing or
closing somebody else's issue. Even then, file after the confirmation.

## Before writing

```bash
gh repo view --json nameWithOwner,hasIssuesEnabled -q '.'   # is this the right tracker?
gh auth status                                               # can you file at all?
gh issue list --search "<the distinctive term>" --state all --limit 10
```

**File where the team FIXES it, not where you happened to be running.** If
`hasIssuesEnabled` is false the tracker is elsewhere — check `CONTRIBUTING.md` or
`.github/ISSUE_TEMPLATE/`.

If a matching issue exists, **comment on it instead**. Say what is new: a second repro,
a different environment, a narrower trigger. A duplicate costs more than silence.

## The body

Write it to a file, then score it. Order by what the fixer reads first.

```markdown
## Severity
<level> — justified by impact, not by how annoying it was. For triage.

## Build under test
<version, SHA, endpoint, runtime>. "It fails" with no build is unfalsifiable.

## Expected vs actual
**Expected:** …
**Actual:** …

## Steps to reproduce
1. <exact command or URL>
2. …

Confirmed <N> times. If it is intermittent, say so and mark `[NEEDS-REPRO]` —
an intermittent defect is still worth filing and the reader must know which it is.

## Evidence
The output, not a description of it. Console, `METHOD URL -> status`, the failing
assertion, a screenshot. Paste the failure, not the whole log: the study warns a
trace without context is "often too large to be useful".

## Probable cause
The file, the layer, the commit — and honest uncertainty. "Possibly the env, not
the product" is more useful than a confident wrong diagnosis.

## Suggested fix
When you have one. Never binding on whoever takes it.

## Dedup
`gh issue list --search "…"` — nothing matching / related to #N.
```

### Score it before filing

```bash
ECO=$([ -d .claude/skills ] && echo .claude || echo .)

python3 "$ECO/skills/issue-confidence/scripts/score_issue.py" draft.md
```

`READY` at 60% of weighted usefulness. `THIN` names what is missing, heaviest first.
`REFUSED` means a secret was detected — nothing is scored and nothing should be filed.

## Secrets — the one rule with no exception

A token, cookie, password, key or customer datum in an issue body is **public the moment
it is filed**, and removing it later leaves it in the edit history. The scorer refuses
the draft outright rather than scoring it, because a score beside a refusal invites
filing anyway.

Replace with a redacted placeholder: `Authorization: Bearer <redacted>` carries the same
information for the reader who needs it.

## File it

```bash
gh issue create --title "<area>: <what is wrong>" --label bug --body-file - < draft.md
```

The title is the only part most people read. `J-01.Web: OIDC GitHub does not redirect`
beats `login broken` — the area, then the specific failure.

## After the fix

**Verify before closing**, and comment the verification with its evidence. And follow
the lifecycle the project declares: a fix merged to the integration branch gets a label
and the issue stays **open**; it closes when the fix is *installable*, naming the
version. "Fixed" and "available" are different claims and only the second serves whoever
opened it.

## What this cannot do for you

- **Establish that the repro works.** The scorer checks that steps are present and
  numbered. Only running them establishes the rest.
- **Establish the diagnosis.** A confident wrong cause scores like a correct one, which
  is why the contract asks for uncertainty rather than confidence.
- **Establish that it is not a duplicate.** It checks that a search was recorded.

## Anti-patterns

- **Mentioning a finding in a report instead of filing it.** The worst outcome, because
  it reads as coverage.
- **Filing in the repo you were running in** rather than where it gets fixed.
- **Padding the cheap fields.** Environment and severity are 4% and 0%. An issue that is
  all metadata and no repro is the 74% case.
- **A whole log as evidence.** The study warns about exactly this.
- **Closing at merge.** The person who opened it still has the bug.

## Related

- Conventions this follows: [`rules/contribution-conventions.md`](../../rules/contribution-conventions.md)
- Registering work rather than reporting a defect: [`skills/backlog-item/SKILL.md`](../backlog-item/SKILL.md)
