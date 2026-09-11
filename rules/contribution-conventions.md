# Contribution conventions

What a commit, a pull request, an issue and a name have to carry. **The kit's contract**
— a consumer overrides it in `rules/contribution-overrides.txt` without editing this
file, which a reinstall would overwrite.

## Why this is a rule and not a style guide

A convention nobody can check is a preference, and a preference in a `CONTRIBUTING.md`
drifts from the repository within a release. Measured on this repository 2026-09-11:
`CONTRIBUTING.md` instructed contributors to *"end commit messages with the project's
co-author trailer"* while **zero of the last 200 commits carried one** — the document
and the practice had disagreed for long enough that nobody noticed, and an open-source
consumer reading it would have followed the document.

So every convention below is either **computed** by `check_contribution_conventions.py`
or **declared unenforceable** with the reason. Nothing sits in between.

## Commit messages

### Shape — computed

```
<type>(<scope>): <subject>

<body: what changed and WHY, with the measurement if there was one>
```

| Field | Rule |
|---|---|
| `type` | one of the declared set; a consumer extends it in the overrides file |
| `scope` | optional, lowercase, kebab-case. The area, not the file |
| `subject` | imperative mood, no trailing period, at most **85** characters — the p90 of this repository's own 300-subject history, not the 50 or 72 every style guide repeats. A limit that fails 44% of what a repository has always done teaches people to ignore the checker |
| `body` | separated by a blank line. Required for `feat` and `fix` |

The kit's declared types, measured from its own history rather than chosen from a
standard: `fix` (61 of the last 120), `feat` (24), `test` (8), `docs` (7), `refactor`,
`chore`, `perf`, `build`, `ci`, `revert`.

### What the body is for — not computed, and the most important line here

**The subject says what changed; the body says what was true that made it necessary.**
A body that restates the subject in more words has added nothing. A body naming the
measurement, the counter-example, or the thing that was believed and turned out false is
the only durable record of why the code is the way it is.

No mechanism can check this. It is stated because the repositories that keep it do so
because someone wrote it down.

### Trailers — computed

**No co-authorship trailer.** `Co-Authored-By:` in any spelling, for any second party,
is refused. The author of a commit is one person, and a trailer crediting a tool
misattributes the accountability that authorship carries.

This paragraph replaces the instruction `CONTRIBUTING.md` carried until 2026-09-11,
which told contributors to add one.

## Pull requests

| Rule | Computed? |
|---|---|
| Title follows the commit shape — `<type>(<scope>): <subject>` | yes |
| The body says what a reviewer must check, not what the diff shows | no |
| Every PR closing an issue names it — `Closes #N` | yes, when an issue is named |
| `workspace → develop` and `develop → trunk` only | yes — `validate-command.py` |

**A PR body listing the changed files has told the reviewer what `git diff` already
tells them.** What it cannot tell them is which of those changes is the one to look at
hardest, and why.

## Issues

The floor is a repro and an expectation. Below that an issue is a report of a feeling.

| Field | Required | Why |
|---|---|---|
| Expected vs actual | yes | without both, "broken" is not a claim anyone can act on |
| Repro | yes, or `[NEEDS-REPRO]` | an intermittent defect stays worth filing, and says so |
| Build under test | yes | a version or a SHA. "It fails" without one is unfalsifiable |
| Evidence | yes | the output, not a description of the output |
| Probable cause | no | honest uncertainty beats a confident guess |
| Suggested fix | no | and it is never binding on whoever takes the issue |

**Never in an issue body:** a secret, a token, a cookie, a password, or a customer's
data. This is the one rule here with no exception and no override.

**`/file-issue` writes one to this shape and scores it before filing.** The weights are
the FSE 2008 percentages, not a checklist: steps to reproduce 83, stack traces 57,
observed 33, expected 22, version 12, dedup 10, environment 4 — and severity 0, kept for
triage and weighted at nothing, because developers fixing a bug do not use it.

## Names

| Thing | Convention | Computed? |
|---|---|---|
| Python module | snake_case with a `.py` suffix, named for what it DOES | partially |
| Skill directory | `kebab-case`, a verb or a noun phrase | yes |
| Rule file | `kebab-case.md` for the kit's contracts, `.txt` for a project's data | yes |
| Branch | `workspace`, `develop`, trunk — no feature branches | yes |
| Test | `test_<what is true>`, not `test_<function name>` | no |

**Prefer the longer, unambiguous name.** `user_metadata` over `metadata`; `content_type`
over `type`; `from_date` over `from`. The short one collides with a keyword, a builtin,
or another concept exactly when the file grows.

## Language

Everything the repository carries is in English — code, comments, commit messages, PR
titles and bodies, issue text, documentation. `check_english_only.py` computes it.

The exception is content whose language is a product requirement: user-facing copy,
legal text. Even then the code around it — i18n keys, variable names, comments — stays
English.

## Overriding this

A consumer declares its own conventions in `rules/contribution-overrides.txt`:
additional commit types, a different subject length, scopes its areas use. The file
ships empty and a reinstall preserves it, which is why customisation belongs there and
not in this file.

**Two things cannot be overridden**, and the gate refuses an override that tries:
the co-authorship refusal, and the secrets rule for issues. Everything else is the
kit's default and the project's decision.
