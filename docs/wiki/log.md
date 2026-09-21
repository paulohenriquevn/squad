# Change log

## 2026-09-09 — later the same day

**`decisions/the-cli-navigates-mechanisms-compute` moves to `accepted`.** All four verbs
are implemented and the two things it left open are settled.

`sq` passes `check_semantic_names`, and the same suffix filter that lets it through means
**no gate reads the shim at all** — so the shim is six lines and a test executes it.

The ADR's claim about consumers was FALSE and is corrected in place, with the error
recorded rather than edited away: `install.sh` copies directories, so a loose root file
reaches nobody. What travels is `squad/cli/`.

**And one design in the ADR did not survive contact.** It said `sq check` would be "a
façade over `verify_ecosystem`" discovering gates by glob. That is not implementable: the
root-path flag takes seven different spellings across the 23 gates, so a glob-and-run
carries a table of conventions — a second list of what "verified" means, which the ADR
itself forbids. The command replays `ci.yml` instead, which makes "the CLI reaches what CI
reaches" true by construction.

## 2026-09-09

**`decisions/the-cli-navigates-mechanisms-compute` added**, status `proposed`. A single
entry point `sq` is recorded as a FAÇADE: it resolves names, scopes a run to what
changed, and states what it did not examine — and it computes no verdict, which is why
it is not a sixth family under `mechanisms/`.

The decision is the owner's; the argument is the agent's and is marked as unreviewed,
following the precedent `merge-is-inside-the-envelope` set. What is not opinion is the
evidence: seven frictions measured in one session, of which three produced false
statements rather than wasted time. Those three are the justification — a tool that
saves minutes is a convenience, and one that cannot report a passing measurement over
an unrun half is a correctness measure.

Two things the ADR deliberately does not decide: whether a two-letter root entry point
satisfies `check_semantic_names`, and whether `explain`, `status` and `issues` are worth
building — each is defensible and none was the source of a measured failure, so each
waits for its own evidence.


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
