---
description: "Promote workspace to develop without cutting a version. Integration is frequent and cheap; a version is cadenced. Opens the PR git-safety.md requires, merges it when branch protection allows, and touches no version, CHANGELOG or tag."
disable-model-invocation: true
allowed-tools: "Bash"
---

Move finished work from `workspace` to `develop`, and **only** that.

`git-safety.md` § 1 says `develop` advances only by promoting `workspace` through a PR.
Until 2026-09-09 the sole place in this kit that opened that PR sat in the middle of
`/release`'s chain, between the version bump and the tag — so **integrating required
versioning**, and a project that did not want to publish a version simply did not
integrate. Measured here on 2026-09-09: 349 commits on `workspace`, zero tags, and
finished work unreachable behind a step nobody wanted to take yet — promoted the same day
by this command, in one run, with no version cut.

This command is that step alone.

```bash
ECO=$([ -d .claude/skills ] && echo .claude || echo .)

# See what it would do first — it opens and merges nothing.
python3 "$ECO/mechanisms/cycle/promote_to_develop.py" --dry-run

# Then, if the report is what you expected:
python3 "$ECO/mechanisms/cycle/promote_to_develop.py"
```

Report what the exit code means, verbatim, rather than paraphrasing it:

| Exit | Meaning | What to do |
|---|---|---|
| `0` | promoted — or there was nothing to promote, which is also an answer | nothing |
| `1` | refused: not on `workspace`, or the tree is dirty | commit or stash first; a dirty tree promotes a state nobody reviewed |
| `2` | could not measure: `gh` absent, unauthenticated, or git unreadable | fix the tool, then re-run; **this is not a pass** |
| `3` | the PR is open and branch protection wants a reviewer | a human approves it; the work is not lost, it is waiting |

**It cuts no version, on purpose.** A version is cut by `/release`, and
[`rules/cycle-release.md` § Two cuts](../rules/cycle-release.md) says when: `X.Y.Z-rc.N`
when the queue of ready items dries up, `X.Y.Z` when a milestone closes. Promotion answers
*"is this work integrated?"*; a cut answers *"can somebody install it?"*. Two questions,
two commands.

Do NOT reach for `/release` merely to get work onto `develop` — that is the coupling this
command exists to undo.
