# Audit Trail Rotation

How to retire generated artifacts so the repository stays navigable.

## What counts as audit trail

- `agents/{cycle}-{slug}-{date}/` — per-agent logs from `/review` and `/implement`
- `records/implementations/{slug}/` — per-iteration halt-loop logs
- `.compaction-snapshots/` — PreCompact snapshots
- `session-state/{slug}-progress.md` — incremental progress logs

## Retention policy (defaults — projects may tighten)

| Artifact | Active retention | Archive after | Delete after |
|---|---|---|---|
| `agents/{review,implement}-*` of MERGED features | until merge + 30 days | move to `agents/archive/` | 180 days |
| `records/implementations/{slug}/` iter logs | until plan slug closed | summarize into `{slug}-implementation.md`, delete dir | — |
| `.compaction-snapshots/` | last 10 by mtime | — | rolling delete |
| `session-state/{slug}-progress.md` | duration of plan | append-only into implementation summary | delete with implementation dir |

## Active vs. archive

- `agents/` — current and recently-merged work.
- `agents/archive/` — moved (not deleted) once retention period elapses. Searchable but out of the way.
- Deletion only happens on `agents/archive/` after archive-retention elapses.

## Rotation triggers

- Manual: `/audit-rotate` — **not yet implemented**, and nothing schedules it. Rotation is fully manual until a command exists.
- On merge of a feature: archive the corresponding implement/review trail.
- On a quarterly basis: human-driven sweep of `agents/archive/` against the delete threshold.

## What NEVER rotates

- `records/plans/{slug}-plan.md` — kept indefinitely; the canonical record of "what we agreed to build".
- `records/discoveries/opportunities/` — kept indefinitely; institutional knowledge.
- `records/adrs/` — kept indefinitely; architectural decisions.
- `CHANGELOG.md` — kept indefinitely (it's the public contract).

## Anti-patterns

- Deleting audit trail before its retention window elapses.
- Bulk-archiving without summarizing first — the summary is what makes the archive useful later.
- Letting `.compaction-snapshots/` grow unbounded.
- Putting audit trail in `records/references/` (read-only enforced; will be blocked).
