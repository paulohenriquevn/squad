# Git Safety

Source of Truth for the forbidden git commands and their safe substitutes
(Unbreakable Rule 4). The list lives here as a document so the corpus states the
contract even if the runtime hook is disabled; `hooks/validate-command.py` enforces
the mechanizable subset.

## § 1 — Branching model

```
workspace ──PR──> develop ──PR + semver tag──> main
 (work)          (integration)                (release)
```

- **`workspace`** is where work is born. Single, permanent branch — never deleted, never recreated per task. Features, fixes, refactors, docs, chores: every change commits here first.
- **`develop`** integrates work; it never originates it. It advances **only** by promoting `workspace` through a `workspace → develop` PR, plus the push that carries it. That PR is opened by [`mechanisms/cycle/promote_to_develop.py`](../mechanisms/cycle/promote_to_develop.py) (`/promote`), which cuts no version — integration is frequent and cheap, a version is cadenced (`cycle-release.md` § Two cuts). Never commit to, rebase, reset, or cherry-pick onto `develop` locally, and never merge anything other than `workspace` into it.
- **`main`** is release-only. It receives a `develop → main` PR plus a semver tag on merge. Never commit to, merge into, rebase, reset, or cherry-pick onto `main` locally.

**Which layer guarantees what** — the two are not interchangeable:

| Guarantee | Enforced by | Scope |
|---|---|---|
| Work *originates* on `workspace` (no direct authoring on develop/main) | `hooks/validate-command.py` | Local, every machine that installed the hook |
| Promotion *passes through a PR* (no merge that skips review) | Branch protection on the remote | Server-side, unbypassable |

The hook cannot tell a merge that finalizes an approved PR from one that skips it — it only sees `git merge workspace`. A repository without branch protection on `develop` has the origin guarantee but not the review guarantee.

## § 2 — Forbidden commands and substitutes

| Forbidden | Why | Use instead |
|---|---|---|
| `git checkout` | Ambiguous (branch vs file); easy to discard work | `git switch <branch>` / `git restore <path>` |
| `git revert` | Hides history behind an auto-commit | A new explicit commit that reverses the change |
| `git push --force` / `-f` | Rewrites shared history | `git push --force-with-lease` only when explicitly authorized, and never on `main`/`develop` |
| `git reset --hard` | Destroys uncommitted work irrecoverably | `git reset --soft`, or commit on a branch |
| `git stash` while the repository has more than one worktree | The stack is **shared**: `refs/stash` lives in the common git dir, so every worktree pushes and pops the same stack and `pop` returns the top entry whichever tree pushed it | Copy the files aside with `cp`, or commit them on your own branch, then `git restore` |
| Any mutation of `main` (commit/merge/rebase/reset/cherry-pick) | `main` is release-only | Do the work on `workspace`; cut the release via PR |
| Authoring or rewriting on `develop` (commit/rebase/reset/cherry-pick) | `develop` integrates, never originates | Commit on `workspace`; promote via `workspace → develop` PR |
| Merging a non-`workspace` branch into `develop` | Bypasses the workspace→develop gate | Land the work on `workspace` first, then promote |

`git push --force` is forbidden on `main`, `develop` and `workspace` unconditionally;
force-push is tolerated only on disposable, never-shared branches.

**The stash is not part of what a worktree isolates.** A worktree owns its index,
its HEAD and its checkout — which is exactly why the omission is easy to miss.
Measured 2026-09-04 (kit#31): two agents in separate worktrees ran `git stash`
concurrently and each popped the other's entry, exchanging uncommitted work
between two branches. `git stash list` and `git stash show` read the stack and
stay allowed; everything that pushes to or consumes it does not.

**Two agents must never share a working tree.** Whoever dispatches concurrent lanes into one
project gives each its own worktree before any of them writes:

```
git -C <project> worktree add -b <branch> /tmp/<lane>-$(date +%s) HEAD
```

and the lane works only inside it. A branch is not isolation — `git switch` moves the one
checkout, and uncommitted changes travel with it into whatever branch is switched to.

Measured 2026-09-04: two lanes were dispatched to the same project with instructions that said
"cut a branch" and did not say "cut your own worktree". Both used the main checkout. **35 dirty
paths** belonging to two different items sat in one tree with nothing committed on either
side, and the first `git add -A` would have swept one item's work into the other's branch. The
file sets happened to be disjoint and were separated by reading every diff; nothing in the
mechanism would have caught it.

The instruction exists in `mechanisms/fleet/fleet_router.py`'s consumer brief and had for
weeks. It is here because a dispatcher that does not go through `brief()` re-derives the rule
from nothing — which is what happened, on the third such dispatcher — and a constraint that
lives inside one caller is a constraint the next caller does not inherit. Cite this section
rather than restating it.

## § 3 — Enforcement

- `hooks/validate-command.py` (PreToolUse) blocks the mechanizable subset. Exit code 2 = blocked:
  - Any branch: `checkout`, `revert`, `push --force`/`-f`, `reset --hard`.
  - Any branch, when `git worktree list` shows more than one working tree: `stash` and every subcommand that mutates the stack (`list` and `show` stay allowed). The command's own `-C <path>` is read before the current directory, because the fleet drives git that way.
  - `HEAD` is `main`: `commit`/`merge`/`rebase`/`reset`/`cherry-pick`.
  - `HEAD` is `develop` (G1): `commit`/`rebase`/`reset`/`cherry-pick`, and `merge` from anything other than `workspace` (`origin/`/`upstream/` prefixes accepted).
  - The inline forms (`git switch main && …`, `git switch develop && …`) are covered too — reading the live branch alone is bypassable in a compound command.
- `push` is intentionally NOT blocked on `main` or `develop` — release legitimately pushes a tag and the promotion has to reach origin; the dangerous variant (`push --force`) is already blocked globally.
- Branch protection on the remote is what makes the PR itself mandatory (see § 1). The hook governs origin, not review.

## § 4 — Anti-patterns

- Reaching for `git checkout` out of habit — the hook blocks it; retrain to `switch`/`restore`.
- "I'll just fast-forward `main` locally" — `main` advances only through a merged PR.
- "It's a one-line fix, I'll commit straight to `develop`" — the size of the change is not the criterion; origin is. It goes on `workspace` like everything else.
- Merging a side branch into `develop` because "it's already reviewed" — if it did not come through `workspace`, the gate did not see it.
- Force-pushing to recover from a bad rebase on a shared branch — use `--force-with-lease`, and never on `main`/`develop`/`workspace`.
- "My worktree is my own, so a stash is safe here" — the tree is yours and the stash stack is not. Copy aside or commit; the pop you get back may be someone else's.
- "Each lane is on its own branch, so they cannot collide" — a branch names a commit, it does not isolate a checkout. Two lanes on two branches in one working tree are two lanes in one working tree, and the second `git switch` carries the first one's uncommitted edits across.

## Cross-references

- Schema for cycle rules: `cycle-rule-schema.md`
- Hook: `../hooks/validate-command.py`
- Cycles that cite this: `cycle-implement.md`, `cycle-release.md`, `cycle-review.md`
