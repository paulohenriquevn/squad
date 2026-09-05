# Convention: where the records lives

Every cycle writes a dated artifact — plans, implementation logs, review reports, releases, acceptance records, roadmap runs. They are the project's audit trail, and an audit trail split across two directories is worse than none: a reader who checks the wrong one reports absence where evidence exists.

## The rule

**`<project>/.claude/records/` is canonical. Always.**

The single exception is the **standalone layout** — the kit's own repository, where `skills/`, `rules/` and `hooks/` sit at the root with no `.claude/` wrapper. There, and only there, the records is `<repo>/records/`.

In a **plugin install** — every consumer — the ecosystem lives at `<project>/.claude/`, and so does its records.

## Why this needed writing down

Measured across three consumers in 2026-08: two wrote to `.claude/records/`, the third wrote to the project root, and all three had **both** directories present. An audit reading `.claude/` reported the third as having "0 implementations, 0 reviews, 0 releases" — the repository actually had 6, 12 and 8. The claim was false, and nothing in the system detected it.

The failure mode is quiet by nature: a second records never errors. It just accumulates half the truth.

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
