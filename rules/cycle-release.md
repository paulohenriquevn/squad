# Cycle: RELEASE

Source of Truth for the release-cut cycle. Runs after `cycle-review` emits `READY_TO_MERGE`; produces a merge of `develop` into `main` and a semver tag. Fully automated: the system merges a PR whose whole chain passed, and stops only where branch protection requires a reviewer it cannot be.

## Purpose

Take an approved implementation from `READY_TO_MERGE` to a released, tagged version on `main`. Eliminates the manual release ritual: merge, version bump, tag, push, GitHub release notes.

**The merge is the system's, and it is gated rather than supervised.** `rules/autonomy-envelope.md` floor 2 permits merging a pull request whose full chain passed, and forbids merging anything else — the reasoning is [`.squad/wiki/decisions/merge-is-inside-the-envelope.md`](../.squad/wiki/decisions/merge-is-inside-the-envelope.md). The branching topology is untouched: nothing commits to the trunk directly, everything arrives by PR with a semver tag, and `hooks/validate-command.py` still enforces both.

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
     ↓ promote_to_develop.py — PR workspace → develop; merge it (git-safety.md § 1)
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
| tag-cut (post-merge) | merged commit on main | annotated tag + GitHub release | `check_tag_integrity.py` — the tag object is annotated AND the commit it names is contained in the trunk |

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
- `PR_OPEN_AWAITING_APPROVAL` — the PR is open and the system did not merge it because **a gate did not pass**. That is the system declining to merge its own work, and it is the only meaning this verdict still carries: a remote requiring a human reviewer is a violated premise caught at intake by `check_merge_autonomy.py`, not a state the chain reaches (envelope floor 2). Resume automatically once the PR merges.
- `BLOCKED` — pre-condition failed OR a hard gate fired during the chain. The item returns to the registry carrying the cause; the queue takes the next one.
- `AWAITING_HUMAN` — the phase ran and stopped at a gate only a person opens (a T3 boundary call, an alignment sign-off, an approval, a dependency in another repository). **Emit it.** The work happened; without the event it leaves no trace, and every reader — the board, the drift checker, the selector, the watchdog — sees an item that was never touched.

## Promotion is not a cut, and it is a separate command

**`workspace → develop` is integration. `develop → main + tag` is a release.** They were
one command until 2026-09-09, and the coupling had a measured cost: the only place in the
kit that opened the promotion PR was the middle of this chain, so **integrating required
versioning**. A project that did not want to publish a version did not integrate — and
this repository sat at **349 commits on `workspace` with zero tags**, finished and
verified work unreachable behind a step nobody wanted to take yet.

Promotion now lives in [`mechanisms/cycle/promote_to_develop.py`](../mechanisms/cycle/promote_to_develop.py),
invoked by `/promote`. It moves no version, writes no CHANGELOG section and cuts no tag —
a promotion that bumps is a release wearing another name, and a test asserts the file
never reaches for `bump_version`, `compute_next_version`, `promote_unreleased` or
`git tag`.

This cycle still promotes as part of its own chain, through that same mechanism: one
definition, two callers. **What changed is that the promotion no longer requires this
cycle.**

> Do not run `/release` merely to get work onto `develop`. That is the coupling the split
> exists to undo, and reaching for it that way rebuilds it.

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

The rule always picks. There is no ambiguous outcome and no pause.

`compute_next_version.py` evaluates these in the order written, and the order is load-bearing: `Added` is consulted before `Changed` so that a section carrying both derives `minor` once, from the first rule that matches, rather than depending on which clause a reader reaches first.

### Why a `Changed`-only release resolves to `minor`

A `[Unreleased]` carrying only `### Changed` — *"we changed how something already published
behaves, without adding or removing"* — matches none of the first three rules. It is an
**ordinary** release shape, not an exotic one, and until 2026-09-08 it paused the chain every
time. Measured on an adopter on 2026-08-18:
`compute_next_version.py --current 0.61.0 --bump auto` → `AMBIGUOUS`.

**The fact it depends on is genuinely absent from the section.** Under 0.x — where
`public-copy.md § 3` holds the package until there is evidence of sustained production use — a
break is **minor** and a compatible change is **patch**. So `Changed` maps to either, depending
on a question the CHANGELOG does not answer:

> **Does this change a behaviour a caller depends on?**

That was the argument for pausing, and it was a good argument for **as long as somebody was
coming to answer it**. Nobody is: `autonomy-envelope.md § The autonomous span` places the whole
of RELEASE inside the system's own authority, and a pause addressed to an absent person is a
stopped release, not a careful one.

**So the question is answered once, in writing, in the safe direction: `minor`.** The two
candidate errors are not symmetric, and that asymmetry is the whole justification:

| Guess | When it is wrong | What it costs |
|---|---|---|
| `patch` | the change broke a caller | the break ships **silently** to everyone on a caret range — precisely the failure semver exists to prevent |
| `minor` | the change was compatible | a version number is larger than it needed to be, and callers on a caret range do not pick it up automatically |

One error is a wrong number. The other is a broken consumer who was told nothing. A rule that
must decide without the fact decides toward the recoverable error — which is the same fail-safe
that makes `decision-delegation.txt` retain an unmatched wall.

**The cost, stated.** Under this rule a release that only reworded a log line takes a minor
bump, and the version series will overstate how much changed. That is accepted. What is not
accepted is inferring the answer from the entry's prose: it is the same guess with a longer
regex, and this very script has already measured how a formatting variation (`**BREAKING:`)
defeats that kind of match.

**`major` is untouched.** An entry that opens with `BREAKING:`, or any `### Removed`, still
derives `major` before this rule is reached. The rule below decides only what a bare `Changed`
means, never whether something is breaking at all.

## Hard gates

- **Gates-passed gate (LOCKED)** — _(not mechanized as one check: composed — it reads the verdicts the chain already emitted — `/review` `READY_TO_MERGE`, `/code-quality` not `FAIL_HARD`, no BLOCKED report standing)_ The merge step merges ONLY a PR whose full chain passed. Merging anything else, or moving a threshold so that it passes, violates envelope floor 2 and floor 3. **This replaced a human-approval gate on 2026-09-01**; what it does not replace is the topology — the PR itself is still mandatory. Branch protection is what makes it mandatory on the remote, and since 2026-09-08 it may enforce the PR **without requiring a human reviewer**: a remote that requires one makes the chain unrunnable and is reported by `check_merge_autonomy.py` at intake.
- **No direct commits to `main`** — `validate-command.py`, which resolves the real trunk rather than matching the literal name. Even from this skill: every change reaches `main` via the PR opened above. **Unchanged by the amendment** — merging a PR and committing to the trunk are different acts, and only the first moved.
- **Tag must be annotated** (`git tag -a`) and pushed only after merge to `main` — never on `develop` or `workspace`. `mechanisms/gates/check_tag_integrity.py --tag v{version} --trunk main` reads the tag object's type (`git cat-file -t` answers `tag` for annotated, `commit` for lightweight) and whether the commit it names is contained in the trunk (`git merge-base --is-ancestor`, not a branch-name match). An absent tag exits 2: not a passing tag.

  **This clause replaced `git tag --verify` on 2026-09-21, and the replacement is the point.** The phase-contract table above demanded that `--verify` resolve, while Step 7 of the skill cuts the tag with `git tag -a`. `--verify` checks a GPG **signature**, so an unsigned annotated tag — the only kind this kit produces — fails it:

  ```
  $ git tag -a v1.0.0 -m "release" && git tag --verify v1.0.0
  error: no signature found
  exit=1
  ```

  Every correct release would have failed its own gate. Nobody found out because neither clause was mechanised: one demanded the impossible, the other was carried as debt with the note that "nothing inspects the tag object's type or the branch it was cut from". Two unmechanised clauses about one object, and the contradiction between them survived because no code ever had to hold both.
- **CHANGELOG must have content** — `changelog_section_nonempty.py` refuses if `[Unreleased]` is empty after stripping headers.
- **Single-flip invariant** — owned by [`cycle-acceptance § Hard gates`](cycle-acceptance.md), which is where the flip moved (see § Post-merge ROADMAP.md checkbox flip). This cycle no longer flips anything; the clause stays as a pointer so nobody re-adds a flip here.
- **No silent flip** — `flip_milestone_checkbox.py --commit`, which writes the run-file and aborts the whole operation (restoring the checkbox) when the commit fails. The roadmap-runs file MUST be appended with the flip commit SHA. A flip without a run-file entry is forbidden.

## Stop conditions

- `gh pr create` fails → halt; surface stderr.
- PR is closed without merge → halt; record the rationale in `records/releases/{version}-release.md`.
- Tag already exists for the computed version → the computed version is already cut, so the chain advances to the next free patch level and records that it did. It halts only if that level is taken too, which means the tag series disagrees with the CHANGELOG — a broken record rather than a version choice, registered as its own item.

## Anti-patterns

- **Merging a PR whose chain did not pass.** Auto-merging one that did is the design since 2026-09-01 (envelope floor 2); what is forbidden is merging past a gate or moving a threshold so that it passes. `gh pr merge --admin` is banned by name.
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
- Conventions: `architecture.md`, `public-copy.md` (release notes lint), `skills/_kit-rules/audit-trail-rotation.md`, `git-safety.md`
- Unbreakable rules consumed: Rule 4 (no commit to `main`; release is the only path — see `git-safety.md`), Rule 6 (CHANGELOG discipline)
