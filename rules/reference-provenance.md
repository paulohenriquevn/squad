# Reference Provenance

Source of Truth for how third-party study material is kept OUT of this project.
`.squad/study-material/` holds material we depend on and study — tool documentation,
vendor sources, anything read to learn from. It is read-only: we read it, and we
write our own code. A literal copy carries the original licence into this
repository, which is a legal problem, not a style one.

## § 1 — The zone

`.squad/study-material/**`. Never versioned, and since 2026-09-21 that is a property of
WHERE it sits rather than a rule somebody maintains: `.squad/` is the project's write
root, ignored whole (`records-location.md`), so nothing under it can reach the index.

**The zone was a top-level `study-material/` until 2026-09-21.** That put third-party
code in the tree the project versions, and kept it out with a `study-material/**` line
in `.gitignore` — one line, deletable, between a cloned peer project's licence and this
repository's history. The legal problem this rule opens with deserves better than a rule
somebody can remove without noticing. Inside the write root the question does not arise.

The zone is spelled once, in `squad/boundaries.py`, and the three guards read it from
there. It used to be spelled three times in three shapes, which is the defect that
module's own docstring records: two hooks knowing one boundary differently is how
`sed -i` reached a file `Edit` had just refused.

**`records/references/` was retired on 2026-09-01.** It held cloned peer
projects, which the Cycle's DISCOVER studied. Squad inverted that question on
purpose — `README.md`: *"Prior art can never be evidence"* — and the same day
`assess_confidence.py` stopped scoring peer material at all. A directory the
flow no longer fills is protection nobody collects, so it left the zone.

**If you still hold material there, move it to `.squad/study-material/`.** It is no
longer guarded: writes into it are allowed, copies out of it are allowed, and
the leakage detector does not read it. That is the cost of the retirement, and
it is stated here rather than discovered later.

## § 2 — Four layers, four different guarantees

| # | Layer | Guarantees | Where |
|---|---|---|---|
| 0 | Write-in guard | Nothing is written INTO the zone (it stays pristine study material) | `hooks/boundary-check`, `validate-command`, `settings.json` deny |
| 1 | Export guard (P1) | Content does not leave the zone by command — `cp`/`mv`/`rsync`/`scp`/`tar`/`dd`, `>`/`>>` redirect, `\| tee` | `hooks/validate-command` |
| 2 | Commit-message guard (P2) | The public history never cites a zone path | `hooks/validate-command` |
| 3 | Leakage detector | Detects the RESULT of a manual paste: a block of consecutive lines shared with a zone file | `mechanisms/gates/check_reference_leakage.py`, wired into `hooks/stop-validation` |

Layers 0–2 are **blocking** (exit 2). Layer 3 is **advisory** (WARN): exact-shingle
matching is strong evidence, not proof, and a false BLOCK on a heuristic is worse
than a WARN — shared boilerplate and a common upstream both produce real matches.

## § 3 — What stays allowed, deliberately

Reading, grepping, listing and opening zone files. That is the entire purpose of
the zone. What is forbidden is duplicating its bytes into the project or into the
git history. The intended path from study to code is:

```
read the zone → understand → write your own version
              → record the finding in records/discoveries/opportunities/, citing the source
```

## § 4 — Limits, stated honestly

- Layer 1 sees commands, not editors. An agent that reads a zone file and *retypes*
  its content is invisible to it — that gap is exactly why layer 3 exists.
- Layer 3 compares changed project files against the zone. It cannot detect a copy
  from a project that was never cloned into the zone, and it will not fire on a
  paraphrase — only on near-literal text (whitespace and case are normalized).
- Layer 3's zone scan is capped (`--max-zone-files`, default 5000) because the zone
  can hold tens of thousands of foreign files. When the cap truncates a run, the
  output says so — coverage is reported PARTIAL, never silently claimed complete.
- Layer 2 matches the full zone path, so ordinary words like "cross-references" are
  untouched. A commit that describes a technique in prose, without the path, passes —
  by design: attribution in the CHANGELOG is welcome, a path into third-party code
  in the public history is not.

## § 5 — Anti-patterns

- Copying a zone file "just to adapt it later" — adaptation of a copy is still a
  derivative work. Write it yourself.
- Recording provenance by pasting the zone path into a commit message. Put the
  source and licence in `CHANGELOG.md` and the opportunity instead.
- Dismissing a layer-3 WARN without opening the match. It is advisory precisely so
  a human decides; ignoring it defeats the layer.
- Using `.references-bootstrap` for anything but the initial population of the zone,
  or leaving the marker in place afterwards.

## Cross-references

- Git safety and branching: `git-safety.md`
- Hooks: `../hooks/validate-command.py`, `../hooks/boundary-check.py`, `../hooks/stop-validation.py`
- Detector: `../mechanisms/gates/check_reference_leakage.py`
- Cycles that cite this: `cycle-discover.md`, `cycle-review.md`

## § 6 — Why layers 0–2 stayed after being found broken

Measured 2026-09-01: every regex in layers 0–2 matched
`records/(references|tools)/` while the rule declared the zone as
`study-material/`. Neither of the matched directories existed; the declared one
did. **The three blocking layers guarded nothing**, and their messages said
otherwise — including the pre-filter, which skipped the segment loop for any
command not containing the literal `records/`, so the guards were unreachable
and the silence read as clean.

Four shell test files covered exactly this case. Nothing executed them — not CI,
not `pytest` (`testpaths` did not include them), not `run_slice_tests.sh` — and
three of the four already failed. That is the real defect: not the regex, which
took one line, but a proof nobody ran.

Layers 0–2 were kept rather than dropped because they cover the deliberate
export, which is cheap to check and expensive to miss in an open-source
repository. What they do NOT cover is the likely path: an agent reading a file
and rewriting it from memory. Only layer 3 sees that, and it is advisory. So the
blocking layers guard the improbable case and the probable one carries a WARN —
stated here because a reader counting three blocking layers would otherwise
assume the zone is closed.
