# Cycle: RELEASE

Source of Truth for the release-cut cycle. Runs after `cycle-review` emits `READY_TO_MERGE`; produces a merge of `develop` into `main` and a semver tag. Human stays in the loop ONLY at PR-approval — every other step is automated.

## Purpose

Take an approved implementation from `READY_TO_MERGE` to a released, tagged version on `main`. Eliminates the manual release ritual (merge, version bump, tag, push, GitHub release notes) while keeping the human-controlled merge approval — Unbreakable Rule 4 (never commit directly to `main`).

## Pre-conditions

- `cycle-review` emitted verdict `READY_TO_MERGE` (audit at `knowledge-base/reviews/{slug}-review-{date}.md`).
- Working branch is `workspace` (never `develop` or `main` directly — see `git-safety.md` § 1). The release commits are authored on `workspace` and reach `develop` through the promotion PR, like every other change.
- No uncommitted changes (`git status --porcelain` empty).
- CHANGELOG `[Unreleased]` section has ≥ 1 entry — otherwise the release has nothing to announce.
- The `gh` CLI is authenticated (`gh auth status` exits 0).
- (Optional) CI is green on `develop` — verified with `gh run list --branch develop --limit 1`.

Do NOT trigger when:

- No commits since the last release tag (nothing to release).
- A release PR is already open (`gh pr list --base main --head develop --state open` non-empty).
- `cycle-review` verdict is not `READY_TO_MERGE`.

## Chain

```
/release {bump-level?}
     ↓ detect highest semver tag + stack manifest versions; refuse when no source exists
     ↓ determine next version (bump-level OR auto-derive from CHANGELOG sections)
     ↓ rewrite CHANGELOG: move [Unreleased] body under [{next-version}] - {date}
     ↓ commit "chore(release): {next-version}" on workspace
     ↓ open PR workspace → develop; merge it (promotion — git-safety.md § 1)
     ↓ open PR develop → main with the rendered release notes as body
     ↓ wait for human approval (hard gate — Unbreakable Rule 4 mandate)
     ↓ on merge: create annotated tag {next-version} pointing at the merge commit
     ↓ push tag; gh release create
     ↓ RELEASED — hand off to /acceptance M<N> for the checkbox flip
```

## Phase contracts

| Phase | Input | Output | Hard gate |
|---|---|---|---|
| detect-version | semver tags + supported stack manifests | parsed semver tuple | at least one trustworthy source exists; cross-major disagreement refuses |
| bump | parsed version + bump-level | next version string | bump-level ∈ {patch, minor, major} OR derivable from CHANGELOG |
| changelog-rewrite | CHANGELOG.md | CHANGELOG with [Unreleased] empty and a new versioned section | [Unreleased] had ≥ 1 entry before the rewrite |
| pr-open | release branch state | PR URL | `gh pr create` exit 0; PR body = release notes |
| tag-cut (post-merge) | merged commit on main | annotated tag + GitHub release | `git tag --verify` resolves AND tag points at the merge commit |

## Post-merge ROADMAP.md checkbox flip — MOVED to cycle-acceptance

This cycle no longer flips the milestone checkbox. The flip is the `flip` phase of [`cycle-acceptance`](cycle-acceptance.md), gated on its verdict.

The reason is what `[x]` is allowed to claim. Flipping at tag-cut made it mean *"we shipped it"* — a statement no gate in this chain can distinguish from *"we shipped something broken"*, because nothing here ever touched the released artifact. Flipping after `cycle-acceptance` makes it mean *"we shipped it and watched it work."*

Consequences for this cycle:

- `RELEASED` is the terminal verdict, emitted once the tag and GitHub release exist. It no longer implies the roadmap advanced.
- After `RELEASED`, hand off: `/acceptance M<N>`.
- `skills/release/scripts/flip_milestone_checkbox.py` stays in this slice — it is the single implementation of the single-flip invariant, and `cycle-acceptance` invokes it rather than duplicating it.
- The escape hatch is unchanged in spirit: a plan with no `milestone_id` still releases normally. It simply never reaches a flip, because there is no milestone to accept.

## Verdicts

- `RELEASED` — PR merged, tag created, GitHub release published. Cycle complete.
- `PR_OPEN_AWAITING_APPROVAL` — chain paused at the human-approval gate. Resume automatically once the PR merges.
- `BLOCKED` — pre-condition failed OR a hard gate fired during the chain. Surface to human.

## Bump-level derivation

When the user does not pass `{bump-level}` explicitly:

- `major` — `[Unreleased] § Removed` is non-empty OR any `[Unreleased] § Changed` entry begins with `BREAKING:`.
- `minor` — `[Unreleased] § Added` is non-empty AND no major triggers.
- `patch` — only `[Unreleased] § Fixed` / `Security` entries.

If the rule cannot pick deterministically, the chain pauses and the human chooses.

### Why a `Changed`-only release pauses, and stays pausing

A `[Unreleased]` carrying only `### Changed` — *"we changed how something already published
behaves, without adding or removing"* — matches none of the three rules above. It is an
**ordinary** release shape, not an exotic one, and it hits the pause every time. Measured on
`theokit-tui` on 2026-08-18:
`compute_next_version.py --current 0.61.0 --bump auto` → `AMBIGUOUS`.

**It is not derived, and that is a decision rather than a gap.** Under 0.x — where
`public-copy.md § 3` holds the package until there is evidence of sustained production use — a
break is **minor** and a compatible change is **patch**. So `Changed` maps to either of the two,
depending on a fact the section does not contain:

> **The question: does this change a behaviour a caller depends on?**

Chutar `minor` transforma toda entrada reescrita em sinal de incompatibilidade. Chutar `patch`
understates a real break — exactly the failure semver exists to prevent, delivered silently to
anyone on a caret range. Inferring from the entry's prose is the same guess with a longer regex,
and the same source measured how a formatting variation (`**BREAKING:`) defeats that
tipo de casamento neste mesmo script.

The pause stays, and **carries the question** instead of a guess. Harvested from `theokit-tui`,
where the reasoning was written down and measured.

## Hard gates

- **PR approval gate (LOCKED)** — the merge step ALWAYS waits for a human-approved PR. Auto-merging into `main` violates Unbreakable Rule 4.
- **No direct commits to `main`** — even from this skill. Every change reaches `main` via the PR opened above.
- **Tag must be annotated** (`git tag -a`) and pushed only after merge to `main` — never on `develop` or `workspace`.
- **CHANGELOG must have content** — refuse if `[Unreleased]` is empty after stripping headers.
- **Single-flip invariant** — owned by [`cycle-acceptance § Hard gates`](cycle-acceptance.md), which is where the flip moved (see § Post-merge ROADMAP.md checkbox flip). This cycle no longer flips anything; the clause stays as a pointer so nobody re-adds a flip here.
- **No silent flip** — the roadmap-runs file MUST be appended with the flip commit SHA. A flip without a run-file entry is forbidden.

## Stop conditions

- `gh pr create` fails → halt; surface stderr.
- PR is closed without merge → halt; record the rationale in `knowledge-base/releases/{version}-release.md`.
- Tag already exists for the computed version → halt; ask the human to pick the next version explicitly.

## Anti-patterns

- Auto-merging the release PR. Always human-gated.
- Editing `[Unreleased]` directly during the release chain — entries should be in place beforehand (CHANGELOG discipline is Unbreakable Rule 6).
- Producing a release without a corresponding `cycle-review` audit. Released artifacts must be traceable to a `READY_TO_MERGE` verdict.
- Skipping the GitHub release creation step. Downstream consumers (changelogs, dependency updates) read GitHub releases, not local tags.
- Cutting a release while `cycle-code-quality` reports unaddressed `FAIL_HARD` findings. The review gate already enforces this; never bypass.
- **Flipping the ROADMAP checkbox from this cycle.** It moved to `cycle-acceptance` (see § Post-merge ROADMAP.md checkbox flip). The flip anti-patterns themselves — fuzzy matching, multi-flip, flipping without a roadmap-runs entry — live there, with the flip.
- **Blocking the release if `milestone_id` is missing.** Ad-hoc work (hotfixes, off-roadmap fixes) is by design — emit INFO, continue as RELEASED, skip the acceptance handoff.

## Output

- `knowledge-base/releases/{version}-release.md` — record of the release run: input verdict, computed version, PR URL, merge commit, tag, GitHub release URL.
- `[Unreleased]` empty (until the next change lands).
- `git tag v{version}` annotated, pushed.
- GitHub release published.
- `ROADMAP.md` — **untouched.** The `[ ]` → `[x]` flip is `cycle-acceptance`'s output, not this cycle's.
- A named handoff: `/acceptance M<N>` when the plan declared `milestone_id` (skipped with INFO otherwise).

## Cross-references

- Schema for cycle rules: `cycle-rule-schema.md`
- Skill: `skills/release/SKILL.md`
- Upstream: `cycle-review.md` (consumes its `READY_TO_MERGE` verdict)
- Macro super-loop: `rules/cycle-maintenance.md` — defines the single-flip invariant + the roadmap-runs file contract
- Conventions: `architecture.md`, `public-copy.md` (release notes lint), `audit-trail-rotation.md`, `git-safety.md`
- Unbreakable rules consumed: Rule 4 (no commit to `main`; release is the only path — see `git-safety.md`), Rule 6 (CHANGELOG discipline)
