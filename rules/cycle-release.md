# Cycle: RELEASE

Source of Truth for the release-cut cycle. Runs after `cycle-review` emits `READY_TO_MERGE`; produces a merge of `develop` into `main` and a semver tag. Fully automated: the system merges a PR whose whole chain passed, and stops only where branch protection requires a reviewer it cannot be.

## Purpose

Take an approved implementation from `READY_TO_MERGE` to a released, tagged version on `main`. Eliminates the manual release ritual: merge, version bump, tag, push, GitHub release notes.

**The merge is the system's, and it is gated rather than supervised.** `rules/autonomy-envelope.md` floor 2 permits merging a pull request whose full chain passed, and forbids merging anything else — the reasoning is [`wiki/decisions/merge-is-inside-the-envelope.md`](../wiki/decisions/merge-is-inside-the-envelope.md). The branching topology is untouched: nothing commits to the trunk directly, everything arrives by PR with a semver tag, and `hooks/validate-command.sh` still enforces both.

## Pre-conditions

- `cycle-review` emitted verdict `READY_TO_MERGE` (audit at `records/reviews/{slug}-review-{date}.md`).
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
/release {bump-level?} [--pre | --final]
     ↓ detect highest semver tag + stack manifest versions; refuse when no source exists
     ↓ determine the cut: --final only when a milestone closed; otherwise --pre (default)
     ↓ determine next version — compute_next_version.py --mode {pre|final}
     ↓ --pre:   leave [Unreleased] in place; notes are read from it
     ↓ --final: rewrite CHANGELOG, moving [Unreleased] under [{next-version}] - {date}
     ↓ commit "chore(release): {next-version}" on workspace
     ↓ open PR workspace → develop; merge it (promotion — git-safety.md § 1)
     ↓ open PR develop → main with the rendered release notes as body
     ↓ verify the chain passed, then merge (envelope floor 2)
     ↓   branch protection demands a reviewer? → PR_OPEN_AWAITING_APPROVAL, take the next item
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

- `RELEASED` — PR merged, tag created, GitHub release published. Cycle complete. **Only a final cut emits this**; it is what `cycle-maintenance`'s ADVANCE consumes to write `shipped`.
- `PRE_RELEASED` — an `X.Y.Z-rc.N` tag and a GitHub pre-release exist. The batch is installable and the scope is not finished. Items stay at their stage; nothing is marked `shipped`, because nothing was finally released.
- `PR_OPEN_AWAITING_APPROVAL` — the PR is open and the system did not merge it: a gate did not pass, or branch protection requires a human reviewer. **The exception now, not the terminal state.** Resume automatically once the PR merges.
- `BLOCKED` — pre-condition failed OR a hard gate fired during the chain. Surface to human.
- `AWAITING_HUMAN` — the phase ran and stopped at a gate only a person opens (a T3 boundary call, an alignment sign-off, an approval, a dependency in another repository). **Emit it.** The work happened; without the event it leaves no trace, and every reader — the board, the drift checker, the selector, the watchdog — sees an item that was never touched.

## Two cuts: the rc series, and the final

**A release is cut twice, and they answer different questions.**

| Cut | When | Version | What it says |
|---|---|---|---|
| **pre-release** | the queue of ready items dries up | `X.Y.Z-rc.N` | "this batch is done and installable; the scope is not finished" |
| **final** | a milestone closes | `X.Y.Z` | "everything `M<N>` promised is shipped and was accepted" |

### What "the batch is done" means, mechanically

A batch is not a judgement call and must not become one — a cut decided by feel is a
cut nobody can predict or audit. **The batch closes when the queue of ready items
dries up**: `select_backlog_item.py` returns `BACKLOG_EMPTY` or `BACKLOG_BLOCKED`,
meaning nothing eligible remains to hand out. Everything in flight has landed, and
what shipped since the last tag IS the batch.

That moment already exists and already stops the loop — `cycle-maintenance.md` calls
`BACKLOG_EMPTY` *a prompt to sweep*. It still is; it now also cuts an rc. Nothing new
has to be observed, and no counter or timer decides anything.

**The limit, stated rather than discovered.** A queue that never dries up never cuts
an rc on its own. That is honest — with work continuously arriving, any cut point
would be arbitrary — but it means a busy project can accumulate shipped items behind
no tag. `/release --pre` cuts on demand for exactly that case. It is an escape hatch
and not a schedule: reaching for it every time turns the mechanical rule back into a
judgement call.

### Why the final does not bump again

The first rc bumps the core version; every rc after it only advances the counter; the
final **promotes**. `0.2.0 → 0.3.0-rc.1 → 0.3.0-rc.2 → 0.3.0`.

Bumping at the final would publish `0.4.0` — a version none of the pre-releases
pointed at, so nobody testing `0.3.0-rc.2` would recognise what shipped. The rc series
reserves the number; the final claims it.

`compute_next_version.py --mode {pre|final}` implements exactly this, and **`pre` is
the default** because most cuts are pre-releases.

### The CHANGELOG moves once, at the final

`promote_unreleased.py` empties `[Unreleased]` into a versioned section. **An rc must
NOT run it.** Emptying at `-rc.1` would leave `-rc.2` and the final with nothing to
publish, and the entries would be filed under a version that was still a candidate.

So an rc reads `[Unreleased]` for its release notes and leaves it in place; the final
promotes it. The `[Unreleased]` body therefore grows across a whole milestone, and
that is correct: it is the milestone's changelog, accumulating.

### What a milestone closing means

Every `B-NNN` citing `M<N>` is `shipped` **and** `/acceptance M<N>` returned
`ACCEPTED`. The acceptance gate is what separates "we shipped it" from "we shipped it
and watched it work" (§ Post-merge ROADMAP.md checkbox flip), and only the second
earns a final version.

A `B-NNN` with no milestone never triggers a final. It rides the rc series and is
published when some milestone closes — or stays in a pre-release indefinitely, which
is the honest state for work nobody promised anyone.

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
an adopter on 2026-08-18:
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
kind of match in this very script.

The pause stays, and **carries the question** instead of a guess. Harvested from an adopter,
where the reasoning was written down and measured.

## Hard gates

- **Gates-passed gate (LOCKED)** — _(not mechanized as one check: it reads the verdicts the chain already emitted — `/review` `READY_TO_MERGE`, `/code-quality` not `FAIL_HARD`, no BLOCKED report standing)_ The merge step merges ONLY a PR whose full chain passed. Merging anything else, or moving a threshold so that it passes, violates envelope floor 2 and floor 3. **This replaced a human-approval gate on 2026-09-01**; what it does not replace is the topology — the PR itself is still mandatory, and branch protection is still what makes it so on the remote.
- **No direct commits to `main`** — `validate-command.sh`, which resolves the real trunk rather than matching the literal name. Even from this skill: every change reaches `main` via the PR opened above. **Unchanged by the amendment** — merging a PR and committing to the trunk are different acts, and only the first moved.
- **Tag must be annotated** (`git tag -a`) and pushed only after merge to `main` — never on `develop` or `workspace`. _(not mechanized: nothing inspects the tag object's type or the branch it was cut from; `validate-command.sh` blocks the commit paths, not the tag)_
- **CHANGELOG must have content** — `changelog_section_nonempty.py` refuses if `[Unreleased]` is empty after stripping headers.
- **Single-flip invariant** — owned by [`cycle-acceptance § Hard gates`](cycle-acceptance.md), which is where the flip moved (see § Post-merge ROADMAP.md checkbox flip). This cycle no longer flips anything; the clause stays as a pointer so nobody re-adds a flip here.
- **No silent flip** — `flip_milestone_checkbox.py --commit`, which writes the run-file and aborts the whole operation (restoring the checkbox) when the commit fails. The roadmap-runs file MUST be appended with the flip commit SHA. A flip without a run-file entry is forbidden.

## Stop conditions

- `gh pr create` fails → halt; surface stderr.
- PR is closed without merge → halt; record the rationale in `records/releases/{version}-release.md`.
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

- `records/releases/{version}-release.md` — record of the release run: input verdict, computed version, PR URL, merge commit, tag, GitHub release URL.
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
