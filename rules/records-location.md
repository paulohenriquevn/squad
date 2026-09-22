# Convention: where the records lives
<!-- rule-id: SQ-LOC-01 -->

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

**And nothing AUTHORS into `.squad/` either — including this kit, since 2026-09-21.**
The write root belongs to the project being maintained. What a cycle writes there is run
output: dated, per-execution, and per-machine. A document somebody sat down and wrote is
a different kind of thing, and it belongs with the product that ships it.

The kit broke its own rule here for twelve days. Its eleven ADRs and SOPs lived at
`.squad/wiki/`, versioned through a `!.squad/wiki/` negation in `.gitignore`, on the
argument that *"this kit's durable knowledge IS its source"*. The argument was true and
the location was the problem: one path meant product in this repository and run data in
every consumer, and the kit had a worked example in its own tree of writing authored
documents into the write root. They are at [`docs/wiki/`](https://github.com/paulohenriquevn/squad/blob/main/docs/wiki) now, versioned
like the rest of the product, and `tests/test_write_root_is_versioned_correctly.py`
refuses a tracked file under `.squad/` in this repository at all.

**This changes nothing for a consumer.** A project maintained by the kit still keeps its
OKF bundle at `<project>/.squad/wiki/` — that IS its write root, and `wiki_dir()` still
resolves there. The distinction is between a project's own knowledge, which the kit
writes for it, and the kit's, which people write and git ships.

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

Consumers do **not** share a records. Each project owns its `ROADMAP.md` and its own `.squad/`, and no cycle artifact in one project may reference another's. A goal, a gate or a report pointing outside the project couples two autonomous repositories and makes one milestone's completion depend on another repository's state.

Nothing enforces this today. `install_goal_hook.py` did — it refused a `--roadmap` or `--acceptance-dir` resolving outside the project root — and it was deleted in `77501b0` with the `session-goal` skill it belonged to. The rule survived the deletion still describing it in the present tense. Measured 2026-09-05: the file exists in no commit's worktree and in no tracked path.

## Enforcement

Measured 2026-09-05, because this section named three mechanisms and two of them do not exist.
A rule that lists enforcement a reader cannot find is worse than one that lists none: it stops them
looking.

- `install.sh` and `patch_install.sh` scaffold the records tree under the write root.
  **This one holds** — `install.sh:842` (`mkdir -p "$DATA_ROOT/records/$d"`) and
  `patch_install.sh:403`. Neither shell script spells the root: both ask `squad/paths.py`
  for it, so this line cannot drift from the code the way the two below did.

  **Re-measured 2026-09-21, because it had drifted anyway** — in the direction this
  section exists to catch. It read `.claude/records/{acceptance,acceptance/evidence,
  roadmap-runs}` with line numbers `install.sh:772` / `patch_install.sh:386`. Measured on
  a clean install: `.squad/records/{acceptance,audits,backlog,brainstorms,discoveries,…}`
  is created and `.claude/records/` is not created at all, while `install.sh:772` is a
  comment about `merge_settings.py`. The one item marked **HOLDS** was pointing a reader
  at a directory nothing writes and a line that does nothing — the same failure as the
  two struck-through items, arriving through a verification that aged.
- ~~`install_goal_hook.py` refuses paths outside the project.~~ **GONE.** Deleted in `77501b0`
  with the `session-goal` skill. No replacement was written, so the constraint above is a
  convention now, not a gate.
- ~~`backlog-review --records` emits `split_knowledge_base` (MAJOR).~~ **NEVER EXISTED.** The
  `--records` flag is real (`phase_coverage.py:222`); the finding is not. `split_knowledge_base`
  appears in this file and nowhere else in the repository.

So the honest statement: the scaffold is created, and a second records directory is caught by
nobody. Closing that is worth an item; asserting it is closed is what this section did.

## The guarantee, and exactly how far it reaches

"Everything the Squad produces lands under `<project>/.squad/`" is a claim, and this
section says what backs it, because the paragraph above records what happens when a
rule lists enforcement a reader cannot find.

**Two gates, answering different halves of the question.**

| Gate | Proves | Blind to |
|---|---|---|
| `check_write_containment.py` | No module outside `squad/paths.py` may spell a data root, so every path a writer BUILDS came from the owner | A writer whose destination never passes through `squad.paths` — taken from argv, joined onto the installed kit, handed down by a caller |
| `check_produced_files.py` | Runs the mechanisms in a scratch project and looks at the disk. Whatever appears is what they produce, whatever the code path was | Anything no probe reaches |

The second exists because the static version of it does not work. Tracing all 135 write
call sites through the AST to their originating root left **64 UNKNOWN** — 47%. A proof
with a hole that size is not a proof, and widening the tracer produces a mechanism only
its author can re-run.

**What is allowed to sit outside, and why each one is.**
`rules/write-exemptions.txt` holds the list. A row needs a path, a class
(`platform` / `tool` / `human`) and a reason of at least five words, and the parser
REFUSES a row missing any of them — "we made an exception" and "the platform gave us no
choice" are different claims, and only the second survives review.

As of 2026-09-10 the sweep produces 17 files and 8 sit outside: five `/review` knowledge
skills and one domain specialist (`platform` — Claude Code resolves both by directory,
so the location IS the interface and a file elsewhere is not an agent), plus `BACKLOG.md`
and `CHANGELOG.md` (`human`).

**`domain-routing.txt` was the ninth until this date.** It was the one file under
`rules/` that CODE produced, and nothing outside the kit read it — measured across every
`.json`, `.yml`, `.yaml` and `.toml` in the tree: zero references. It now lives at
`.squad/domain-routing.txt`. Readers fall back to both old locations indefinitely;
`detect_domains.py --write` no longer accepts the old one by default, and a test refuses
any document that teaches the old path.

## A checkout with no registry

`BACKLOG.md` is unversioned (`rules/write-exemptions.txt`, class `human`), so this is a
state a checkout reaches normally rather than a failure: a fresh clone has no registry,
and a second worktree on the same machine has none either. **The policy stays unversioned
— an item that answers "the registry is invisible" by versioning it has answered a
different question.** What follows is how to work under it.

Measured in a consumer 2026-09-21: 93 blocks present against 195 distinct `B-NNN` cited
across the tree — **138 ids spent with no block to show for them**. Of three worktrees on
that machine, one held the file; the other two had none. A session in one of those two
registered a finding as `B-016`, an id already spent, in good faith: it could not see a
single one.

**1. Do not reconstruct the file.** A registry rebuilt from citations looks complete and
is not, which is the state above. The blocks are gone; only the ids survive, and an id
without its block is a number, not an item.

**2. Get the next id from the allocator, never from the file.**

```bash
python3 mechanisms/cycle/next_backlog_id.py BACKLOG.md
```

It reads the blocks present, recovers from the registry's git history every id that ever
HAD a block, and rejects ids that never did — a template placeholder, a test fixture, an
example in prose all look identical to a grep. With no history it falls back to the
present blocks and prints `history unavailable`, which is a different claim from
`0 recovered` and must not be read as one.

**3. Expect the dedup pass to be partial, and read what it says.**
`skills/backlog-item/scripts/check_intake_gates.py` reports `searched_blocks` alongside a
`not_searched` line. An id cited elsewhere but carrying no block is unreachable to G2, so
`candidates: []` over a partial registry means "none among the blocks I could open" — not
"no duplicate exists". A clean result over an incomplete corpus reads identically to a
clean result over a complete one unless the gate says which it had.

**4. A new item in an empty checkout is legitimate.** It gets an id no one has spent, and
the work is recorded. What is NOT legitimate is treating the absence as evidence that
nothing was filed before.

## What this does NOT reach — named, so the claim stops outrunning it

- **Coverage is 18 mechanisms.** 49 files in the kit write to disk. The gate prints the
  number it exercised on every run, so a green result is read as worth eighteen probes
  rather than as a sweep of everything. Growing `PROBES` is how the guarantee gets
  stronger.
- **Bytecode is suppressed by an environment variable.** `PYTHONDONTWRITEBYTECODE` is set
  in `settings.plugin.json`, so it holds for anything Claude Code launches. A person
  running `python3 .claude/mechanisms/...` from a bare terminal has no such variable, and
  Python writes `__pycache__/` next to the installed kit again. Measured cost of the
  suppression, over five runs: 415 ms/run with a warm cache against 360 ms without one —
  inside the noise, which is why it was cheap to choose.
- **An agent is not a mechanism.** A skill is a document an agent follows, and an agent
  that decides to write somewhere is not running code any gate can call. Only the scripts
  are exercised.
- **`~/` and `/tmp` are out of scope, which is not the same as allowed.**
  `skills/code-quality/scripts/_registry.py` caches under `~/.cache/` deliberately: what
  it caches is about a tool version, identical across every repository, and a per-project
  copy would re-fetch once per repo for the same bytes.

## Cross-references

- Cycle that writes acceptance records: `rules/cycle-acceptance.md`
- Macro loop that reads the run-files: `rules/cycle-maintenance.md`
- Reviewer that detects the split: `skills/backlog-review/SKILL.md`
