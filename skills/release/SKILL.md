---
name: release
version: 0.1.0
requires: [review]
description: Cuts a semver-tagged release from develop → main after /review returns READY_TO_MERGE. Auto-derives version from CHANGELOG sections (major/minor/patch), rewrites [Unreleased] under the new version header, commits chore(release), opens a PR develop→main with rendered release notes, verifies the whole chain passed, and merges it. On merge, creates an annotated tag and a GitHub release. Stops at PR_OPEN_AWAITING_APPROVAL only when a gate did not pass or branch protection requires a reviewer it cannot be. Single entry-point for cycle-release. Use after /review {slug} returned READY_TO_MERGE.
user-invocable: true
allowed-tools: Read Glob Grep Bash Write Edit Skill
argument-hint: "[bump-level: patch|minor|major] (optional — auto-derived from CHANGELOG when omitted)"
---

# Release — develop → main with semver tag

Single entry-point for [`cycle-release`](../../rules/cycle-release.md). Automates the release ritual end-to-end, merge included — see [`rules/autonomy-envelope.md`](../../rules/autonomy-envelope.md) floor 2 and the decision behind it, [`.squad/wiki/decisions/merge-is-inside-the-envelope.md`](../../.squad/wiki/decisions/merge-is-inside-the-envelope.md).

## Cycle contract

This skill is **the only phase** of [`cycle-release`](../../rules/cycle-release.md). The cycle rule is the **source of truth** for pre-conditions, verdicts (`RELEASED` / `PRE_RELEASED` / `PR_OPEN_AWAITING_APPROVAL` / `BLOCKED`), the two cuts and when each fires, hard gates (PR approval mandatory; no direct main commits; annotated-tag-only), stop conditions, and anti-patterns. **Read `cycle-release.md` before invoking.**

## When to trigger

User invokes `/release [bump-level]` when:

- A `/review {slug}` run emitted `READY_TO_MERGE` recently (audit at `.squad/records/reviews/{slug}-review-{date}.md`).
- The working branch is `workspace`; `develop` carries the commits ahead of `main` (promoted from `workspace` via PR).
- `CHANGELOG.md` has content in `[Unreleased]`.
- `gh` CLI is authenticated.

Refuse to start when any pre-condition declared in `cycle-release.md § Pre-conditions` fails.

## Argument

`{bump-level}` is optional. When omitted, the skill derives the bump deterministically from `CHANGELOG.md § [Unreleased]`:

| Trigger in [Unreleased] | Bump |
|---|---|
| `### Removed` non-empty OR `### Changed` entry starts with `BREAKING:` | `major` |
| `### Added` non-empty AND no major trigger | `minor` |
| Only `### Fixed` / `### Security` entries | `patch` |

Derivation always picks. An `[Unreleased]` with no entries at all is refused as a release with nothing in it.

## Workflow

### Step 1 — Pre-condition validation (refuse if any fails)

```bash
# Branch is workspace (release prep is authored here, then promoted)
[ "$(git branch --show-current)" = "workspace" ]
# Clean tree
[ -z "$(git status --porcelain)" ]
# Latest /review verdict is READY_TO_MERGE
LATEST_REVIEW=$(ls -t .squad/records/reviews/*-review-*.md 2>/dev/null | head -1)
grep -q '^\*\*Verdict:\*\* READY_TO_MERGE' "$LATEST_REVIEW"
# CHANGELOG [Unreleased] has content
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/release/scripts/changelog_section_nonempty.py" --section Unreleased
# gh CLI authenticated
gh auth status >/dev/null 2>&1
# No release PR already open
[ -z "$(gh pr list --base main --head develop --state open --json number)" ]
```

If any HARD check fails, refuse with the missing piece surfaced honestly.

### Step 2 — Detect current version and compute next

```bash
CURRENT=$(python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/release/scripts/detect_current_version.py")
NEXT_VERSION=$(python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/release/scripts/compute_next_version.py" \
  --current "$CURRENT" \
  --bump "${ARGUMENTS:-auto}" \
  --changelog CHANGELOG.md)
```

**Not `git describe` (B-043).** That walks the ANCESTRY of HEAD, and in this branching model
(`rules/git-safety.md` § 1) a release tag is created on the merge commit that lands on `main`, so it
is never an ancestor of `workspace`. Measured on this repository: `git describe --tags --abbrev=0`
returned `v0.52.1` while npm served `0.64.0` — **twelve versions stale, structurally**, not because
a fetch was forgotten. A release cut from that base computes a version BELOW the published one, and
the stop condition in § Stop conditions ("tag already exists for the computed version") cannot fire,
because that version was never tagged.

`detect_current_version.py` takes the maximum of the highest semver tag and every version-bearing
manifest it recognizes: `package.json`, `[project].version` in `pyproject.toml`, and
`[package].version` in `Cargo.toml`. Go modules are tag-only because `go.mod` has no project version.
Each source alone has a measured failure mode — published versions may have no tag, while a manifest
can lag a tag between the release commit and the merge.

`compute_next_version.py` always derives a level from a non-empty `[Unreleased]`; a `Changed`-only body resolves to `minor` and prints the rule that resolved it on stderr (`cycle-release.md § Why a `Changed`-only release resolves to `minor`). `AMBIGUOUS` now means only one thing — the section has no entries at all, so there is nothing to release — and it is a refusal, not a question.

If a tag for `$NEXT_VERSION` already exists, halt — never overwrite a published tag.

### Step 2.5 — The maturity gate, when the version crosses 1.0.0

**Only when the computed next version is `1.0.0` or higher and the current one is
below it.** Every other release skips this step; a patch release makes no claim
about maturity and a gate that fires on ordinary work is one somebody disables.

```bash
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/honesty-gate/scripts/check_honesty_gate.py" --json
```

| Exit | Verdict | What follows |
|---|---|---|
| 0 | `EVIDENCE_SUFFICIENT` | cut the release |
| 3 | `EVIDENCE_WITH_CAVEATS` | cut it, and the caveats go **into the release notes** — thin evidence, no failure story or a single operator are facts a reader of a 1.0 announcement is owed |
| 1 | `EVIDENCE_INSUFFICIENT` | **refuse.** Cut `0.x` instead, or gather the evidence. Never lower the version claim by rewording the notes while cutting the tag anyway |
| 2 | — | the gate could not be read; fix that before deciding |

The gate reads `.squad/records/honesty-gate/manifest.md` and the evidence beside it. It
refuses to infer: a missing manifest is `EVIDENCE_INSUFFICIENT`, never *not
applicable*. A project that has not declared what would prove the claim has not
proved it.

This step exists because `1.0.0` is the one number in a release that is a claim
about the product rather than about the diff, and the loop that produces it has
no person in it to feel embarrassed.

### Step 3 — Rewrite CHANGELOG

```bash
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/release/scripts/promote_unreleased.py" \
  --changelog CHANGELOG.md \
  --version "$NEXT_VERSION" \
  --date "$(date -u +%Y-%m-%d)"
```

This script:
1. Moves the current `[Unreleased]` body under a new `## [{version}] - {date}` section.
2. Leaves a fresh empty `## [Unreleased]` at the top.
3. Preserves Keep-a-Changelog category ordering (`Added` → `Changed` → `Deprecated` → `Removed` → `Fixed` → `Security`).

### Step 3.5 — Write the version into every site that carries it

```bash
CURRENT_VERSION=$(python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/release/scripts/detect_current_version.py" --quiet)
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/release/scripts/bump_version.py" \
  --root . \
  --from "$CURRENT_VERSION" \
  --to "$NEXT_VERSION"
```

**A non-zero exit BLOCKS the release. It is not a warning.** The script writes the declared sites
(`package.json`, `pyproject.toml`, `Cargo.toml`, plus an optional `src/index.ts` runtime mirror) and
refuses in three cases. A Go module with no version-bearing manifest is explicitly reported as
tag-only rather than treated as an empty successful rewrite:

| Exit | Meaning |
|---|---|
| 2 | a declared site is missing, has no version, or carries something other than `$CURRENT_VERSION` |
| 1 | a tracked file carries the old version and is NOT a declared site — it is NAMED and left alone |
| 0 | every site written; the sites it wrote are listed |

Exit 1 is the one worth reading. A version string in a test fixture or a documented install example
is not a site, and rewriting it blindly is a corruption no gate would catch — so the script reports
it and stops, and a human decides whether it belongs in `SITES` or in `IGNORED`.

This step exists because B-059 measured the cost of the alternative: cutting 0.63.0, two of three
files were bumped by hand and `npm publish` aborted in `prepublishOnly` with
`expected '0.62.0' to be '0.63.0'` — after the tag had been cut and pushed. `v0.63.0` still points
at a commit whose exported constant is wrong.

### Step 4 — Commit the release prep on workspace, then promote to develop

```bash
git add CHANGELOG.md package.json src/index.ts
git commit -m "chore(release): ${NEXT_VERSION}"
git push origin workspace

# Promotion (git-safety.md § 1): release prep reaches develop like any other change,
# through the SAME mechanism `/promote` uses. One definition, two callers — an inline
# `gh pr create` here would be a second answer to "how does work reach develop".
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/mechanisms/cycle/promote_to_develop.py"
```

Exit `3` means branch protection wants a reviewer: the PR is open and the promotion is
waiting, which is the same state `PR_OPEN_AWAITING_APPROVAL` reports for the release PR.
Exit `1` is a refusal about the branch or the tree; exit `2` is an inability to measure
and is never a pass.

NO `Co-Authored-By` trailer (per `hooks/validate-command.py`). NO `--amend`. The commit is plain and signed by user policy.

### Step 5 — Open the release PR

```bash
RELEASE_NOTES=$(python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/release/scripts/render_release_notes.py" \
  --changelog CHANGELOG.md \
  --version "$NEXT_VERSION")

gh pr create \
  --base main \
  --head develop \
  --title "release: ${NEXT_VERSION}" \
  --body "$RELEASE_NOTES"
```

PR URL is captured and reported.

### Step 6 — Verify the chain, then merge

**Check the gates before touching the PR.** The permission to merge comes from the
verdicts the chain already emitted, and nowhere else:

```bash
ECO=$([ -d .claude/skills ] && echo .claude || echo .)

# /review returned READY_TO_MERGE, /code-quality is not FAIL_HARD,
# and no BLOCKED report stands against this item.
python3 "$ECO/mechanisms/cycle/cycle_events.py" verdicts --slug "$SLUG"
ls "$ECO"/records/**/"$SLUG"-BLOCKED.md 2>/dev/null && { echo "BLOCKED report stands — refuse"; exit 1; }
```

If any of the three fails, **stop and emit `PR_OPEN_AWAITING_APPROVAL`.** Do not
re-run the gate hoping for a different answer, and never move a threshold: that is
envelope floor 3, which now carries the whole weight it used to share with the
human-approval stop.

If all three pass, merge:

```bash
gh pr merge "$PR_NUMBER" --merge   # never --admin: that bypasses branch protection
```

**A refusal from branch protection is an answer, not an obstacle.** If the remote
requires a reviewer the system cannot be, `gh` fails — emit
`PR_OPEN_AWAITING_APPROVAL`, report the PR URL, and take the next item. Never reach
for `--admin`, and never disable the protection: a project that configured it decided
this, and floor 3 makes that decision the system's to honour rather than to route
around.

When the user resumes by re-invoking `/release --resume {pr-number}` (or by running `/release` again with the same `develop`/`main` state), the skill:

```bash
# Detect merge state
MERGE_STATE=$(gh pr view "$PR_NUMBER" --json state,mergedAt --jq '.state')
[ "$MERGE_STATE" = "MERGED" ] || { echo "PR not merged yet — re-run after merge." ; exit 0 ; }
```

If the PR was closed without merge → emit `BLOCKED` and record the rationale in the release log.

### Step 7 — Tag the merge commit + publish GitHub release

```bash
# Fetch the merge commit
git fetch origin main
MERGE_SHA=$(gh pr view "$PR_NUMBER" --json mergeCommit --jq '.mergeCommit.oid')

# Annotated tag pointing at the merge commit
git tag -a "v${NEXT_VERSION}" "$MERGE_SHA" -m "Release v${NEXT_VERSION}"

# The tag-cut hard gate, BEFORE the push. A lightweight tag or one cut off the trunk
# is recoverable while it is local and permanent once it is pushed and a release
# points at it. Exit 2 means the tag could not be measured — not that it passed.
python3 "$ECO/mechanisms/gates/check_tag_integrity.py" --tag "v${NEXT_VERSION}" --trunk main || exit 1

git push origin "v${NEXT_VERSION}"

# Publish GitHub release with the rendered notes
gh release create "v${NEXT_VERSION}" \
  --title "v${NEXT_VERSION}" \
  --notes "$RELEASE_NOTES" \
  --target "$MERGE_SHA"

# Confirm what was just published. The chain used to end at the line above and emit
# RELEASED — so a draft release, or a `gh` call that failed AFTER the tag was pushed,
# produced a verdict over an artifact no consumer could fetch. That verdict is what
# ADVANCE reads to write `shipped`. Exit 2 means it could not be checked.
python3 "$ECO/mechanisms/gates/check_release_reachable.py" --tag "v${NEXT_VERSION}" || exit 1
```

This runs for **every** item, with or without a `milestone_id`. `/acceptance` exercises a
milestone's declared promises and an off-roadmap item has none — but "did it ship at all"
has an answer for both, and until 2026-09-21 nothing asked it for either.

### Step 7.5 — Hand off to `/acceptance` (this cycle does NOT flip the checkbox)

The milestone checkbox flip **moved out of this cycle** into `cycle-acceptance`. See
[`rules/cycle-release.md § Post-merge ROADMAP.md checkbox flip`](../../rules/cycle-release.md).

The reason is what `[x]` is allowed to claim. Flipping here, at tag-cut, made it mean
*"we shipped it"* — a statement no gate in this chain can distinguish from *"we shipped
something broken"*, because nothing in `cycle-release` ever touches the released artifact.
Flipping after `cycle-acceptance` makes it mean *"we shipped it and watched it work."*

So this step does exactly one thing: read `milestone_id` from the plan and name the handoff.

```bash
PLAN_FILE=".squad/records/plans/${SLUG}-plan.md"

MILESTONE_ID=$(python3 -c "
import sys, yaml
with open('$PLAN_FILE') as f:
    raw = f.read()
parts = raw.split('---', 2)
if len(parts) >= 3:
    meta = yaml.safe_load(parts[1])
    print(meta.get('milestone_id', ''))
")

if [ -z "$MILESTONE_ID" ]; then
  echo "INFO roadmap-checkbox: plan has no milestone_id — off-roadmap release, no acceptance handoff"
else
  echo "NEXT: /acceptance ${MILESTONE_ID} — the checkbox flips there, on a green verdict only"
fi
```

`skills/release/scripts/flip_milestone_checkbox.py` **stays in this slice on purpose** — it is the
single implementation of the single-flip invariant, and `cycle-acceptance` invokes it from here
rather than duplicating it. Staying is not the same as being called: **nothing in `/release` runs it.**


Emit the START of this phase before doing the work:

```bash
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/mechanisms/cycle/cycle_events.py" start \
    --cycle release --slug {B-NNN}
```

Without it the board can only draw what FINISHED. Measured on 2026-08-31: seventeen
`phase:end` events and one `phase:start`, so an item under active work showed the
verdict of a phase already over and nothing on the page said anything was running.
A `start` with no matching `end` is exactly the fact "this is happening now".

### Step 8 — Record the release

### Which cut is this?

**`--final` only when a milestone closed**: every `B-NNN` citing `M<N>` is `shipped`
AND `/acceptance M<N>` returned `ACCEPTED`. Otherwise this is a pre-release — the
default — and `cycle-release.md § Two cuts` is the source of truth for both.

```bash
# The version. `--mode pre` is the default; pass --mode final only for a closed milestone.
NEXT_VERSION=$(python3 "$ECO/skills/release/scripts/compute_next_version.py" \
                 --current "$CURRENT" --bump "${BUMP:-auto}" --mode "${CUT:-pre}")
```

**A pre-release does NOT run `promote_unreleased.py`.** Emptying `[Unreleased]` at
`-rc.1` would leave `-rc.2` and the final with nothing to publish, and would file the
entries under a version that is still a candidate. The rc reads `[Unreleased]` for its
notes and leaves it in place; the final promotes it.

Tag and publish accordingly — `gh release create "v$NEXT_VERSION" --prerelease` for a
pre-release, without the flag for a final.

Write `.squad/records/releases/v${NEXT_VERSION}-release.md`:

```markdown
# Release v{NEXT_VERSION}

**Date:** {YYYY-MM-DD}
**Verdict:** {RELEASED | PRE_RELEASED}
**Source review:** {path to /review report}
**PR:** {pr-url}
**Merge commit:** {merge-sha}
**Tag:** v{NEXT_VERSION}
**GitHub release:** {release-url}

## Release notes

{rendered notes}
```

Then record the transition in the stream, which is what a later phase reads:

```bash
# PRE_RELEASED for an -rc.N cut; RELEASED only for a final one.
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/mechanisms/cycle/cycle_events.py" end \
    --cycle release --slug {item-or-milestone} --verdict "${VERDICT:-PRE_RELEASED}"
```

Then tell whoever asked to be told:

```bash
python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/release/scripts/notify_slack.py" \
    --repo . --verdict "${VERDICT:-PRE_RELEASED}" --version "v$NEXT_VERSION"
```

**Inert unless the project opted in, and it never blocks.** The script posts only on
`RELEASED`, only when `rules/notifications.txt` says `slack_enabled = true`, only when
the named environment variable holds a webhook — and exits 0 on every other path,
including failure. Which is why it not being invoked was invisible: `rules/notifications.txt`
ships, so a consumer could configure a notification that was never going to be sent.

**Emitting `RELEASED` for a pre-release would close work that did not finish.**
`advance_items.py` reads that token and writes `shipped` into the registry — the one
artefact that outlives the session. An rc says installable, never finished.

**After the tag and the GitHub release exist, never before.** The record file above
and this event assert the same fact, and asserting it early makes the stream claim a
release that a failing publish step would leave unmade.

This event is the one `cycle-maintenance.md`'s ADVANCE consumes to move an item to
`shipped`. Until 2026-08-30 nothing emitted it, so the only way to learn that a
release happened was to reconstruct it from files on disk — which is precisely what
`cycle_events.py` exists to replace: *a missing file is evidence of nothing in
particular*. An ADVANCE built on that inference would write `shipped` on a guess,
into the one artefact that outlives the session.

### Step 9 — Recommend next step

```
=== /release complete ===
Version: v{NEXT_VERSION}
PR: {url}
Merge commit: {sha}
Tag: v{NEXT_VERSION}
GitHub release: {url}

Next: nothing — release is published. Start a new cycle with /backlog-item, or /plan-write if the item is already measured.
```

## Hard gates (cannot proceed)

1. **`/review` verdict is not `READY_TO_MERGE`** → refuse. Re-run `/review` first.
2. **The chain must have passed** — merge ONLY a PR whose `/review` returned `READY_TO_MERGE`, whose `/code-quality` is not `FAIL_HARD`, and against whose item no BLOCKED report stands. Merging anything else violates envelope floor 2; moving a threshold to get there violates floor 3. **Never `gh pr merge --admin`** — bypassing branch protection is the same act under a different name.
3. **Tag must be annotated** (`git tag -a`) — never lightweight tags. Checked by
   `mechanisms/gates/check_tag_integrity.py` in Step 7, before the push, along with
   whether the commit is contained in the trunk. It does NOT check a signature: the
   rule used to declare `git tag --verify`, which demands one, and would have refused
   every tag this procedure produces.
4. **CHANGELOG [Unreleased] non-empty** — empty releases are forbidden.
5. **No duplicate version tags** — if `v{X}` already exists, halt.
6. **This cycle flips no checkbox** — the single-flip invariant is owned by [`cycle-acceptance § Hard gates`](../../rules/cycle-acceptance.md). The gate stays listed here so nobody re-adds a flip to `cycle-release`.

## Soft gates (proceed with note)

1. **CI not green on develop** — this is no longer soft. Nobody catches it downstream now, so refuse and emit `PR_OPEN_AWAITING_APPROVAL` with the failing run named.
2. **Bump-level ambiguous from CHANGELOG** — AskUserQuestion ONCE per release run.

## Anti-patterns

1. **Merging a PR whose chain did not pass** — the act floor 2 permits is narrow, and this is the way it gets widened by accident. Re-running a gate until it goes green is the same anti-pattern wearing patience.
2. **Skipping `cycle-review`** — every release traces to a `READY_TO_MERGE` audit.
3. **Editing CHANGELOG entries during the release** — discipline lives in the cycles that produce the entries.
4. **Cutting a release with unaddressed FAIL_HARD from `/code-quality`** — the review gate enforces this; never bypass.
5. **`git push --force` on a release tag** — tags are immutable once published; if wrong, deprecate and cut a new version.
6. **Co-Authored-By trailer on the `chore(release)` commit** — blocked by `hooks/validate-command.py`.
7. **Flipping the ROADMAP checkbox from this cycle.** It moved to `cycle-acceptance`. A release proves a tag was cut, not that a user-visible promise was met.
8. **Blocking the release if `milestone_id` is missing.** Ad-hoc / hotfix work is by design — emit INFO, continue as `RELEASED`, and skip the acceptance handoff.
9. **Announcing the milestone as done in the release notes.** Until `/acceptance` returns green, the milestone is released, not accepted.

## Related

- Cycle rule (SoT): [`rules/cycle-release.md`](../../rules/cycle-release.md)
- Upstream cycle: [`rules/cycle-review.md`](../../rules/cycle-review.md) — consumes `READY_TO_MERGE` verdict
- Conventions: [`rules/public-copy.md`](../../rules/public-copy.md) — release notes lint
- Hooks enforced: `hooks/validate-command.py` (git safety + Co-Authored-By block), `hooks/stop-validation.py` (CHANGELOG hard gate)
- Scripts: `scripts/compute_next_version.py`, `scripts/bump_version.py`, `scripts/detect_current_version.py`, `scripts/promote_unreleased.py`, `scripts/render_release_notes.py`, `scripts/changelog_section_nonempty.py`, `scripts/flip_milestone_checkbox.py` (housed here, invoked only by `cycle-acceptance` — see Step 7.5)
- Downstream cycle: [`rules/cycle-acceptance.md`](../../rules/cycle-acceptance.md) — consumes `RELEASED`, owns the single-flip invariant and the roadmap-runs file contract
- Macro super-loop: [`rules/cycle-maintenance.md`](../../rules/cycle-maintenance.md) — selects the next `B-NNN` and delegates one `cycle-idea-to-release` run per item
