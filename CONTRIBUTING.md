# Contributing to Squad

Thanks for your interest in improving Squad. This project is built with its own
6+1 pipeline, so contributing means using the same discipline the tool enforces.
Read [`HOW-TO-USE.md`](HOW-TO-USE.md) for the full operational guide; this file is
the short checklist.

## Ground rules

- **Branching.** All work is born on `workspace` and reaches `develop` through a
  `workspace → develop` PR. Never commit directly to `develop` or `main`: develop
  integrates work, main receives release merges only (a version cut from `develop`
  + a semver tag). One permanent `workspace` branch — not per-task feature branches.
- **Git safety (enforced by `hooks/validate-command.py`).** No `git checkout`,
  `git revert`, `git push --force`, or `git reset --hard`. Use `git switch` and
  `git restore --staged` instead.
- **Honesty.** Don't claim behavior you haven't verified. Public copy in `README`
  obeys [`rules/public-copy.md`](rules/public-copy.md) — no `production-ready` /
  `battle-tested` framing until there is sustained measured evidence.

## Before you open a change

1. **Pick the lightest entry point** that fits the work — see
   [How it works](README.md#how-it-works).
   A one-line fix needs no cycle; a multi-branch feature should run
   `/plan-write → /implement → /code-quality → /review`.
2. **Test-first (TDD).** Write the failing test before the code. Every bug fix
   starts with a regression test that fails, then passes.
3. **Keep the suite green.**
   ```bash
   ./sq test                 # every suite, and it names the ones that did not run
   ./sq test --touched       # only the suites your changes can affect
   ./sq check                # replay what CI verifies
   ```
   `sq` is a façade — it runs the same
   `bash mechanisms/cycle/run_slice_tests.sh` underneath, which stays the definition of
   "the suites" and is what CI invokes. Use the script directly whenever you prefer; the
   only thing `sq` adds is the report of what was **not** run.
   For the root suite alone, run `python3 -m pytest -q` with **no path argument** — an
   explicit path suppresses `testpaths`, so `pytest tests` silently drops `hooks/tests`
   and `squad/tests`. That is not hypothetical: this file prescribed `pytest tests` and
   the runner passed the same path, so 152 tests ran in no CI job until 2026-09-09.
   Slice tests run **isolated per slice** (one pytest process each) because slices
   ship colliding module basenames by design — see the header of
   `mechanisms/cycle/run_slice_tests.sh`. Add new slice tests under `skills/<slice>/tests/`
   and they are picked up automatically.
4. **Validators.** The CI also runs:
   ```bash
   python3 mechanisms/gates/validate_skill_frontmatter.py
   python3 mechanisms/gates/check_xrefs.py
   python3 mechanisms/gates/verify_ecosystem.py
   python3 mechanisms/distribution/generate_plugin_settings.py --check
   ```
5. **CHANGELOG.** Record every user-visible change under `## [Unreleased]` in
   [`CHANGELOG.md`](CHANGELOG.md), following Keep a Changelog. One line per change,
   written for the consumer, with a reference in parentheses.

## Adding a skill

- A skill lives at `skills/<name>/` with a `SKILL.md` (valid frontmatter:
  `name`, `description`, `user-invocable`, `allowed-tools`, `argument-hint`),
  plus `scripts/` and `tests/` as needed.
- Author new skills with the standalone `/skill-creator`
  ([`skills/skill-creator/`](skills/skill-creator/SKILL.md), the official
  Anthropic skill-creator). It scaffolds, drafts, and evaluates a skill directly
  at `skills/<purpose>/` — there is no separate staging/validate/register step.
- Register cross-references so `mechanisms/gates/check_xrefs.py` stays green.

## Commit messages

Shape, types, limits and the rules a project may override live in
[`rules/contribution-conventions.md`](rules/contribution-conventions.md), and
`mechanisms/gates/check_contribution_conventions.py` computes them:

```bash
python3 mechanisms/gates/check_contribution_conventions.py --range origin/develop..HEAD
```

Two things are worth knowing before your first commit:

- **The body is the point.** The subject says what changed; the body says what was true
  that made it necessary — the measurement, the counter-example, the belief that turned
  out false. No mechanism can check this and it is the only durable record of why the
  code is the way it is.
- **No co-authorship trailer.** `Co-Authored-By:` in any spelling is refused by the gate.
  The author of a commit is one person.

  *This section instructed the opposite until 2026-09-11 — it asked contributors to add
  the trailer, while zero of the last 200 commits carried one. The document and the
  practice had disagreed long enough that nobody noticed, which is the reason the
  conventions are now computed rather than described.*

## Code style

- Python targets 3.10+. Match the surrounding code's idioms, naming, and comment
  density. Prefer the smallest change that solves the problem (see
  [`rules/parsimony-ladder.md`](rules/parsimony-ladder.md)).
- Keep modules cohesive: one clear responsibility per file; split god-files into a
  thin orchestrator plus a `lib/` submodule (precedent in `skills/quality-init/`).

## Reporting bugs and proposing features

The floor is a repro and an expectation — below that, an issue is a report of a feeling.
[`rules/contribution-conventions.md` § Issues](rules/contribution-conventions.md) lists
what an issue must carry and what it must never: a secret, a token, a cookie, a password
or customer data. That one has no exception and no override.

For security issues, follow [`SECURITY.md`](SECURITY.md) instead of filing a public issue.
