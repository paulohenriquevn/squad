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
- **Git safety (enforced by `hooks/validate-command.sh`).** No `git checkout`,
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
3. **Keep the suite green.** Run both:
   ```bash
   python3 -m pytest tests -q        # root suite
   bash scripts/run_slice_tests.sh   # every skills/*/tests slice, isolated
   ```
   Slice tests run **isolated per slice** (one pytest process each) because slices
   ship colliding module basenames by design — see the header of
   `scripts/run_slice_tests.sh`. Add new slice tests under `skills/<slice>/tests/`
   and they are picked up automatically.
4. **Validators.** The CI also runs:
   ```bash
   python3 scripts/validate_skill_frontmatter.py
   python3 scripts/check_xrefs.py
   python3 scripts/verify_ecosystem.py
   python3 scripts/generate_plugin_settings.py --check
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
- Register cross-references so `scripts/check_xrefs.py` stays green.

## Commit messages

- Use clear, scoped messages (e.g. `fix(review): …`, `feat(plan): …`,
  `docs: …`, `chore: …`).
- End commit messages with the project's co-author trailer when pairing with an
  assistant, per the repo conventions.

## Code style

- Python targets 3.10+. Match the surrounding code's idioms, naming, and comment
  density. Prefer the smallest change that solves the problem (see
  [`rules/parsimony-ladder.md`](rules/parsimony-ladder.md)).
- Keep modules cohesive: one clear responsibility per file; split god-files into a
  thin orchestrator plus a `lib/` submodule (precedent in `skills/quality-init/`).

## Reporting bugs and proposing features

Open an issue describing the observed vs expected behavior, with a minimal
reproduction where possible. For security issues, follow
[`SECURITY.md`](SECURITY.md) instead of filing a public issue.
