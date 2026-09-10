# Convention: where the records lives

Every cycle writes a dated artifact — plans, implementation logs, review reports, releases, acceptance records, roadmap runs. They are the project's audit trail, and an audit trail split across two directories is worse than none: a reader who checks the wrong one reports absence where evidence exists.

## The rule

**`<project>/.squad/` is the one write root. Always, in every layout.**

Everything this system produces goes there and nowhere else:

```
<project>/.squad/
  records/     the dated trail — plans, implementation logs, review reports,
               releases, acceptance records, audits, the cycle event stream
  wiki/        the OKF bundle — durable knowledge: decisions, sops, references,
               opportunities
```

**Nothing executes from `.squad/`.** The kit is an installed dependency and stays where
the installer put it (`<project>/.claude/` in a plugin install, the repository root in
the standalone kit). `.squad/` holds output.

There is **no layout exception**. There used to be: `.claude/records/` for a plugin
install, `<repo>/records/` for the kit's own repository. Two answers meant two ways to
be wrong, and the exception is what the first instrumented run tripped over — it
created `.claude/records/cycle-events.jsonl` at the root here, the split trail this
convention exists to prevent. One root removes the question instead of answering it
more carefully.

## Why the separation, and not just a rename

Until 2026-09-09 the system wrote its output into the same directory as the installed
kit. Measured across 20 consumer repositories that day: **17 had the kit committed to
git**, tracking between 142 and 984 files each, and **every repository carried between
348 and 566 permanently dirty files — all of them inside `.claude/`.** Nothing outside
it was dirty anywhere.

So a project could not un-version the dependency without also un-versioning its own
decision records, and a `git status` nobody can read is a `git status` nobody reads.
Separating the two makes the versioning question answerable: `.claude/` is a
dependency, `.squad/` is the project's, and each is versioned or not on its own terms.

## One owner, and a gate that proves it

Every data-root literal lives in [`squad/paths.py`](../squad/paths.py).
[`check_write_containment.py`](../mechanisms/gates/check_write_containment.py) fails any
other kit file that spells one in code — so every path a writer builds came from the
owner, and the owner produces one root.

That is the whole proof, and it is re-runnable. The alternative, reading 164 writing
call sites, is not.

Six modules each held their own copy of the root list, in **four different orders**,
before this. A reader resolving one order found a directory a writer using another had
never filled.

## Readers fall back; writers never do

A consumer that updates the kit without migrating keeps working: readers resolve
`.squad/` first, then the legacy roots in order. Writers only ever produce `.squad/`.

That asymmetry is the migration strategy, and it is deliberate in both directions. A
writer that fell back would keep every project on its old root forever, and the
centralisation would be a sentence in a rule with nothing behind it. A reader that did
not fall back would break every consumer on the day it updated.

**The kit does not migrate a consumer.** A migration this code performed inside another
project's repository would be the kit writing to a repository it does not own.
[`check_data_root.py`](../mechanisms/gates/check_data_root.py) reports what has not
moved; a person moves it.

Its loudest state is `SPLIT`: once the write root holds data and a legacy root still
does, a reader resolving the first never sees the second, so the older copy is
unreachable rather than merely old — and it looks current.

**This repository followed its own rule on 2026-09-09.** Its bundle lived at
`<repo>/wiki/` and its event stream at `.claude/records/`; both moved, and
`tests/test_check_data_root.py` holds it there. A rule the kit does not follow is a
rule its consumers read as optional.

## Autonomy

Consumers do **not** share a records. Each project owns its `ROADMAP.md` and its `.claude/records/`, and no cycle artifact in one project may reference another's. A goal, a gate or a report pointing outside the project couples two autonomous repositories and makes one milestone's completion depend on another repository's state.

Nothing enforces this today. `install_goal_hook.py` did — it refused a `--roadmap` or `--acceptance-dir` resolving outside the project root — and it was deleted in `77501b0` with the `session-goal` skill it belonged to. The rule survived the deletion still describing it in the present tense. Measured 2026-09-05: the file exists in no commit's worktree and in no tracked path.

## Enforcement

Measured 2026-09-05, because this section named three mechanisms and two of them do not exist.
A rule that lists enforcement a reader cannot find is worse than one that lists none: it stops them
looking.

- `install.sh` and `patch_install.sh` scaffold `.claude/records/{acceptance,acceptance/evidence,roadmap-runs}`.
  **This one holds** — `install.sh:772` and `patch_install.sh:386`.
- ~~`install_goal_hook.py` refuses paths outside the project.~~ **GONE.** Deleted in `77501b0`
  with the `session-goal` skill. No replacement was written, so the constraint above is a
  convention now, not a gate.
- ~~`backlog-review --records` emits `split_knowledge_base` (MAJOR).~~ **NEVER EXISTED.** The
  `--records` flag is real (`phase_coverage.py:222`); the finding is not. `split_knowledge_base`
  appears in this file and nowhere else in the repository.

So the honest statement: the scaffold is created, and a second records directory is caught by
nobody. Closing that is worth an item; asserting it is closed is what this section did.

## Cross-references

- Cycle that writes acceptance records: `rules/cycle-acceptance.md`
- Macro loop that reads the run-files: `rules/cycle-maintenance.md`
- Reviewer that detects the split: `skills/backlog-review/SKILL.md`
