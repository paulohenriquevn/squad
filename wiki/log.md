# Change log

## 2026-08-27

**Creation** — bundle initialised. `sops/port-fix-between-kits` migrated from
`records/sops/`, keeping its kit-specific frontmatter (`sop`, `version`,
`owner`, `review_interval_days`) alongside the OKF fields, so the existing gates
keep reading it while consumers gain `type`, `status`, `stale_after` and the
trust tier.

Scope of this migration, decided before starting: only durable knowledge moves.
The dated audit trail under `records/` stays where it is.
