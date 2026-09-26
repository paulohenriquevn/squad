---
type: concept
title: A suite measures what its author imagined
description: Six defects filed in one day, five reported by a consumer and none found by 5954 passing tests. What the five had in common, why green was honest and useless, and the two mechanisms that close the gap they lived in.
tags: [decision, testing, gates, coverage, consumers, honesty]

generated:
  by: claude/opus-5
  at: 2026-09-23
status: stable
sources:
  - id: drift
    resource: ../../../mechanisms/gates/check_install_drift.py
  - id: installer
    resource: ../../../mechanisms/distribution/install.sh
  - id: upgrade-test
    resource: ../../../tests/test_the_upgrade_path_is_exercised_by_a_consumer.py
  - id: verdict-test
    resource: ../../../tests/test_every_verdict_the_installer_can_reach_has_a_test.py
  - id: clean-install
    resource: ../../../tests/test_clean_install.py
---

# A suite measures what its author imagined

## The measurement

On 2026-09-23 this kit filed six defects. The suite found **one**.

| # | defect | found by |
|---|---|---|
| #168 | a write verb inside a quoted string refused a read-only command | a consumer, blocked |
| #169 | `renumbered` read file layout and stopped the whole selector | a consumer, blocked |
| #170 | a test pinned an exact list and failed without `knip` | **the suite** |
| #171 | a withdrawn file reached nobody, and a reinstall restored it | a consumer, measuring |
| #172 | a skill taught the last of five fallbacks as the source | reading an external document |
| #173 | a blob size in BYTES sliced a string of CHARACTERS | a consumer refuting a claim |

At the time, `run_slice_tests.sh` recorded `31 suites, 5948 passed, 0 failed,
tree_moved: false`. That record was accurate. It was also useless for every row above but one.

## The shape

**Five of the six lived on a path no test walked, and four of those five needed a state no
test could construct: an install that LAGS.**

`test_clean_install.py` installs the kit into a temp project and runs the gates from inside
it — twelve tests, real install, real gates. It is good, and a fresh install has no lag, so
none of these defects is reachable from it:

- #173 needs a file whose body is an OLDER kit revision, so the history reader is asked a
  question it can get wrong. Against a fresh install every file is identical.
- #171 needs a skill the kit once shipped and no longer does.
- The `--apply-upstream` two-argument call needs a file with real git history behind it.
- The nested install needs a target that already IS an install.

So the gap was not *whether consumers were tested*. It was that **one half of the consumer's
life — upgrading — had no coverage at all**, and it is the half where every expensive defect
lives, because it is the only half where the kit's past and present disagree.

## Why green was honest

None of the missing tests was an oversight in the ordinary sense. Each mechanism had tests,
and each test passed, because:

> **The tests assert behaviour on inputs the author constructed, and an author constructs
> inputs that work.**

Three instances from the same day, each measured:

| mechanism | what it reported | what was true |
|---|---|---|
| `check_english_only` | `clean — 1153 tracked file(s) examined` | the file with Portuguese in it was untracked and never examined |
| `_blobs_from_batch` | 7 contents | `git rev-list` named 14 commits for that path |
| `--apply-upstream` | called `classify_file(a, b)` | the function needs four arguments to promote to `STALE` |

The third is the sharpest, because **flag-level coverage would not have caught it**. The flag
was tested. What was untested was one OUTCOME of the flag — the `stale` arm — and that arm
was the one that mattered.

## The two mechanisms

Neither is a rule. A rule about this class already exists in this directory and was violated
three times on the day it was cited.

**1. The upgrade path is walked by a consumer** —
`tests/test_the_upgrade_path_is_exercised_by_a_consumer.py`. It materialises an older
revision of this kit with `git worktree`, installs THAT into a temp project, and then asks the
current kit about it. Deliberately a real worktree and a real install: a fixture that
fabricated "an old install" by editing files would test the fabrication, because the
byte/character defect only appears against git's own `cat-file --batch` output and the
two-argument call only appears when a file genuinely has history.

Proven to detect, not merely to pass. With #173's defect restored by mutation, it fails:
`diverged: 12` where a consumer that wrote nothing must report `0`.

**2. Coverage is asserted at the granularity that failed** —
`tests/test_every_verdict_the_installer_can_reach_has_a_test.py`. Every `case` arm of the
per-file mode must be mentioned by some test, and every `Drift` member must have an arm. Both
directions, because an unnamed member falls through to *could not classify* — a refusal for
the wrong reason, which reads to an operator as a broken tool rather than a guarded one. The
arms are read out of the installer rather than restated, so a second list cannot drift from
the first.

Also proven by mutation: an arm named `quarantined` that no test mentions fails the check.

## What this does not fix

**The most effective detector that day was a second session disagreeing with a measurement.**
It refuted three claims of this one, and one refutation — *your generalisation does not apply
to my install, and here is the sha* — is what led to #173's root cause. That is not a
mechanism, is not in any rule, is not reproducible for someone working alone, and happened
because two sessions were open.

What can be carried across from it is narrower and does generalise, and it is the peer's
sentence rather than any discipline either session wrote down:

> **What saved me was the contradiction, not the care.**

Both saves that day had the same shape. A number that did not change after a change that
should have changed it. A refusal that did not match a report that had just said otherwise.
Neither came from being careful; both came from holding an expectation concrete enough for
reality to contradict.

That is the difference between a check and an expectation, and it is why `test_the_consumer_actually_lags`
exists in the first mechanism above: without it, every assertion after it runs over a tree
with nothing to find and passes.

## The two questions

- **Does a test for this exist for the state a consumer is actually in?** Not the state the
  author built to write the test — the state that arrives after six months of not upgrading.
- **If this mechanism silently did nothing, which assertion would fail?** If the answer is
  none, the green is about the author's imagination.
