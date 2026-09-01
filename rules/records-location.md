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

`install_goal_hook.py` enforces this: a `--roadmap` or `--acceptance-dir` resolving outside the project root is refused.

## Enforcement

- `install.sh` and `patch_install.sh` scaffold `.claude/records/{acceptance,acceptance/evidence,roadmap-runs}`.
- `install_goal_hook.py` defaults to `.claude/records/acceptance` in plugin layout, and refuses paths outside the project.
- `backlog-review --records` emits `split_knowledge_base` (MAJOR) when a second records holds `.md` files.

## Cross-references

- Cycle that writes acceptance records: `rules/cycle-acceptance.md`
- Macro loop that reads the run-files: `rules/cycle-maintenance.md`
- Reviewer that detects the split: `skills/backlog-review/SKILL.md`
