# Change log

## 2026-08-31 — later the same day

**The three procedures this bundle listed as missing were written.** `sops/index.md`
had named them as *"a real gap, not a placeholder: the steps live in a header
comment, where nothing verifies them"* — install, patch, and propagate a delta.
They carry `status: draft` and no `verified`, because they were derived from the
scripts rather than from a run someone performed: a weaker claim than the fourth
SOP makes, stated rather than hidden.

**`check_wiki_migration.py` exists.** `tests/test_wiki_fallback.py` had promised it
by name — the mechanism that keeps the two-root tolerance from becoming permanent —
and for four days the sentence describing it was the only thing that existed. It
now reports four states per durable leaf, and `verify_ecosystem.py` runs it in
every consumer: `UNMIGRATED` as a visible note, `SPLIT` as a failure, because a
bundle and an old root both holding documents makes the old copy unreachable and
unable to be seen as stale. First run against a real consumer found ten
opportunity documents nobody could reach from the bundle.

**The decision gained a boundary it was missing.** `where-knowledge-lives.md` now
says what it does NOT govern: a document that ships to consumers stays in `rules/`
whatever shape it has, because `install.sh` copies `rules/` and creates `wiki/`
empty. Category does not decide where a document lives — who reads it does. The
clause exists because the wrong criterion was applied once and would have moved
`records-location.md` out of eight projects to satisfy a taxonomy.

## 2026-08-31

**The bundle described itself as empty while holding two concepts.** `index.md`
marked `decisions/` and `references/` *(empty)*; both had held a document since
2026-08-28 and neither was listed, so a reader following the index would have
concluded the bundle had nothing to say on either. Two entries were added to the
bundle and never logged here, which is the same defect one level up — a change
log that stops recording is indistinguishable from a bundle that stopped
changing.

The two concepts, recorded now rather than backdated:

- `decisions/where-knowledge-lives.md` — durable knowledge moves to this bundle
  and the dated trail stays in `records/`, because they are different kinds of
  artifact.
- `references/judgement-gates-are-insurance.md` — the judgement gates were
  pressure-tested for the first time and the result inverted the case for
  deleting them: four of four gates complied on the stronger model, and the same
  scenario failed on the weaker one. They are insurance against a weaker model,
  not redundancy, and consumers choose their own model.

**`records/` is no longer carried in this repository's index.** The kit's own run
records were removed and the directory ignored whole; every consumer still keeps
one, and the split this bundle rests on is unchanged. What moved is only where
this repository stores its half of it: nowhere. The durable half is here.


## 2026-08-27

**Creation** — bundle initialised. `sops/port-fix-between-kits` migrated from
`records/sops/`, keeping its kit-specific frontmatter (`sop`, `version`,
`owner`, `review_interval_days`) alongside the OKF fields, so the existing gates
keep reading it while consumers gain `type`, `status`, `stale_after` and the
trust tier.

Scope of this migration, decided before starting: only durable knowledge moves.
The dated audit trail under `records/` stays where it is.
