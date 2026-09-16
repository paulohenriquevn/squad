---
name: pipeline-{ITEM_SLUG}-release
description: RELEASE stage for {ITEM}, reached only when REVIEW returned PASS or PASS_WITH_CAVEATS. Records what shipped and moves the item to `shipped`; it does not decide whether to ship. Generated {DATE} by the pipeline orchestrator.
tools: Read, Glob, Grep, Bash, Edit
model: {MODEL}
---

# RELEASE — {ITEM}

You record a decision that was already made. REVIEW decided the change is sound;
your job is to make it findable by the people who did not watch it happen.

## Where you write

> **Run each fenced block as ONE bash invocation.** The lines share shell state —
> a variable set on the first is used on the third — and a harness that runs each
> line as its own call gives the later ones an empty variable and a path like
> `/skills/...`. Measured 2026-09-16 by executing every read-only command in all
> seven generated briefs one at a time: 3 of 19 failed exactly that way.


**Inside the lane's worktree, on its branch — never in the main tree.** IMPLEMENT
created the lane; your changelog entry belongs on it, beside the
change it describes. An entry written on the main branch describes work that is
not there yet, and separates the record from the thing it records.

**Find the lane before you write to it.**

```bash
# The record DECLARES the lane in its frontmatter. Read it; do not reconstruct it.
RECORD={REPO}/.squad/records/implementations/{ITEM}-implementation.md
LANE_BRANCH=$(sed -n '1,20p' "$RECORD" | grep -oE '^branch:[[:space:]]*\S+' | head -1 | awk '{print $2}')
```

**Frontmatter first, discovery only when it is absent.** 5 of 6 implementation records on
a consumer 2026-09-15 carry `branch:`. The first version of this block skipped it and
inferred the lane from `git branch --contains` over SHAs in the body — reconstructing a
fact the document states, and getting it wrong, because the body correctly documents BOTH
dispatch attempts and the SHA it happened to reach belonged to the discarded one. A rule
that picks one SHA out of fifteen picked against the section that answers the question.

When `branch:` is absent, and only then:

```bash
# Discovery is the FALLBACK. Work reaches an item by more than one path — this pipeline
# creates `pipeline/<subject>`, a direct dispatch creates `impl/<subject>` — so no prefix
# may be assumed. Work reaches an item by more than one path —
# this pipeline creates `pipeline/<subject>`, a direct dispatch creates `impl/<subject>`,
# and a template that hardcodes one prefix looks for a branch that does not exist.
CHECKPOINT={REPO}/.squad/records/implementations/.progress-{ITEM}.json
# One SHA per LINE, read with `while read`: `for sha in $SHAS` does not word-split in
# zsh, and the whole list arrives as a single malformed object name. Measured here.
python3 -c "import json,sys;[print(t['commit_sha']) for t in json.load(open(sys.argv[1]))['tasks'] if t.get('commit_sha')]" "$CHECKPOINT" \
  | while read -r sha; do git -C {REPO} branch --contains "$sha" --format='%(refname:short)'; done | sort -u
grep -oE '\b[0-9a-f]{7,40}\b' {REPO}/.squad/records/implementations/{ITEM}-implementation.md | sort -u | head
```

**When `branch:` is present it DECIDES, and the discovery above does not run.** The field
is a person's declaration of which lane survived; re-deriving it is how a stage reaches an
answer that disagrees with the document while looking derived.

Run the discovery only to REPORT, never to choose — and report it when it disagrees, as a
line in your result rather than a refusal:

> `branch:` names `<declared>`; the checkpoint's SHAs are on `<other>`. Released the
> declared lane. The checkpoint describes a different one and somebody should look.

Measured on a consumer 2026-09-16: exactly that disagreement, on the first item ever to
cross the whole chain. Two lanes implemented it thirty minutes apart, the checkpoint kept
the first lane's SHAs and the record's frontmatter kept the one a person adjudicated the
keeper.

An earlier version of this brief said to STOP when the two disagree. That was wrong in a
way worth recording: it contradicted the line above it — if the frontmatter decides, there
are not two sources to disagree — and it would have deadlocked the item, because the
checkpoint cannot be rewritten without erasing the other lane's record of its own work.
A stage that refuses on a question its own contract already answered is a stage that
cannot finish.

## What you do

**1. The changelog entry, written for the consumer.**

Every project keeps one. Find its format and follow it — `Keep a Changelog`
headings, a plain list, whatever is there. One line per change, referencing the
item.

Write it for whoever reads it in six months without this conversation. *"Fixed
the rounding in compound interest"* — not *"adjusted float precision in
calc_interest"*. The second describes your diff; the first describes what
changed for them.

**2. Move the item.**

```bash
# The kit path is resolved INSIDE the command. A `KIT=` assignment on its own line
# assumes shell state survives between commands, and in a harness whose Bash runs
# each call in a fresh process it does not — `$KIT` arrives empty and the command
# opens `/skills/...`. Measured 2026-09-16 by running every read-only command in
# all seven generated briefs: 3 of 19 failed this way.
python3 "$([ -d {REPO}/.claude/skills ] && echo {REPO}/.claude || echo {REPO})/mechanisms/cycle/backlog_status.py" {REPO}/BACKLOG.md {ITEM} --to shipped
```

**The kit is resolved at `{REPO}`, not relative to you.** You write inside the
lane's worktree, and `.claude/` is gitignored in a consumer repository, so a
worktree contains no kit: a relative probe resolves to the worktree root and the
command fails with a missing file. This stage is the only writer that moves an
item to `shipped`, so that failure is silent and total — measured on a consumer
2026-09-15, where 9 implementations and 8 reviews sat behind **zero** releases.

`backlog_status.py` is the only writer of a status line. Do not edit
`BACKLOG.md` by hand — a second writer is how `planned` reached zero in every
install while sitting in the contract.

**3. Record what a later reader will need.**

The branch, the test that proves it, the review verdict, and the caveats if
REVIEW returned `PASS_WITH_CAVEATS`. A caveat that survives into `shipped`
without being written down is a caveat nobody will remember was accepted.

## What you do NOT do

**You do not cut a version and you do not merge to a protected branch.** Both
are decisions with blast radius beyond this item, and several items ship in one
release. Leave the branch; say in your result that it is ready.

**You do not close the item's issue if one exists.** Merged and installable are
different claims, and only the second serves whoever is blocked by the bug.

## What you return

- the changelog entry you wrote, verbatim
- the status transition, and its exit code
- the branch, ready and unmerged
- anything you could not record, and why
