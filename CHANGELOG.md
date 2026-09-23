# Changelog

All notable changes to this project are recorded in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/) and this project adopts [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- **The alignment report now shows which trees the acceptance criteria name (#177).** A brief
  can score 34/34 `AWAITING_REVIEW` while every path its criteria name lives in a different git
  repository. Two gates, each correct in its own scope, and the space between them:
  `route_domain.py` checks the DECLARED `repo:` and never these paths, and this scorer grades a
  criterion executable when it names something that RUNS rather than something that EXISTS —
  deliberate, because a plan describes files not yet created. `grep -rln 'criteria'
  mechanisms/gates/*.py` returns nothing: no gate reads criteria at all. A consumer paid hours
  of brief and plan for work its registry cannot execute.

  **It SHOWS and does not judge.** Not a comparison — the scorer receives only the brief and has
  no access to the item's `repo:`, which lives in `BACKLOG.md`. Not a gate — a criterion
  legitimately names a config at an umbrella root or a shared test, and
  `code-quality-golden-rule.md § 4.1` is the argument that a check firing on ordinary work is one
  somebody switches off. So no new blocking surface, no new gate in the chain, no contract
  change, and nothing new asked of the caller.

  **Three granularity rules, the first two refuted by running them on the brief that motivated
  the issue** — an item filed as `repo: packages/theo` whose criteria name `packages/ui`.
  Reporting the first segment printed `packages (12)`, identical for both, so the reader saw
  nothing. Reporting two segments only when the group agreed printed `packages (12)` as well,
  because those criteria name BOTH and disagreement collapsed exactly where the answer was. The
  rule that works reports two segments when the second names a DIRECTORY and one when it names a
  file, so the real brief now reads **`packages/ui (11) · packages/theo (1)`** while
  `tests/test_a.py` and `scripts/probe.mjs` still read `tests` and `scripts`.

  A first draft also printed the line inside the sign-off branch, where it would appear only
  after a brief was fully signed — which is after the plan is written, and arriving before it is
  the whole value.

- **`_preflight` called `_verification(root)` and took no `root`, so the verification-freshness
  check had never run once (#176).** No module-level `root` existed either, making the
  `NameError` unconditional in every tree since it was wired in. `promote()` had the value and
  did not pass it.

  **It stayed invisible because the fail-safe worked.** The `except Exception` above the call
  was deliberate — *"a premise we cannot read is reported, not hidden"* — but what it PRINTED,
  `UNCHECKED`, is exactly what a consumer sees when no verification record exists yet: an
  expected, harmless state. Twelve lines above, a comment carefully explains that `stale` and
  `unattributable` both mean the green a reader remembers is about a different tree — and the
  check producing those states had never run. **The shape, named so it can be looked for: a
  fail-safe that reports into the same vocabulary as a legitimate state converts a defect into
  an expected condition.** Not the recorded class *a step that cannot fail loudly did not run* —
  this step DID fail loudly, into a channel where that is indistinguishable from normal. The two
  are now separate: `BROKEN` says in words that it is a defect in the promoter and not a state
  of the repository. Origin: `_preflight`'s docblock says *"Pure code movement"*, which is the
  claim that made nobody look.

- **A slice that ran ZERO tests read `PASS`, because pytest exits 0 when it runs nothing.**
  Measured here: `pytest tests/ -k <no-match>` prints `3141 deselected / 0 selected` and exits
  `0`. A filter matching no name, a path collecting nothing and a selector selecting nothing all
  do this, and `run_slice_tests.sh` judged from the exit code alone. A consumer named it as one
  of four complaints about the kit, having been misled by it twice in one day.

  **The principle was already written four lines above and applied only to the trailer**: *"a 0
  that means 'not reported' and a 0 that means 'none' are different facts, and summing them
  silently is how a total becomes fiction."* The verdict never consulted them. A slice that ran
  nothing now reads `EMPTY` and fails the run. Failing is safe, measured: across the 31 slices
  the smallest legitimately runs 11 tests, and `skipped` is counted separately so a fully
  skipped slice is not called empty.

- **A signature marker on a box's continuation line was invisible, and the tick read as a
  PERSON's (#174).** `score_alignment.py` paired each box's mark to its text with its own
  `_CHECKBOX_RE`, anchored `^…$` under `re.MULTILINE`, capturing ONE line. A
  `<!-- signed-by: … -->` on the next line fell outside the captured text and the `else
  "human"` fallback fired. Measured here: same marker, same judge — on the `- [x]` line
  `judge/alignment-judge`; one line down, `human`. Box authors wrap long text and the natural
  home for a long `(verified: …)` clause is a line of its own, so **the failing shape is the
  one a careful reviewer produces**.

  **The root cause is the duplicate reader.** `squad/signoff.py` declares itself the one reader
  and its `read()` searches the whole body, so it never had this bug; `score_alignment.py` kept
  a second, line-wise one beside it. `attribute()` now lives in the shared module — boxes with
  their continuation lines, weakest-wins in one place — and the duplicate is gone. **The
  `"human"` default is NOT changed**: it is deliberate and documented, and changing it would
  oblige every human to write `human/<name>` or be blocked, which is a contract decision. What
  ships instead is the count — the report now says how many ticks carried no marker, because a
  mechanism that assumes must not assume silently.

- **The concurrency refusal printed the list that DETECTS concurrency, not the one that
  ACCEPTS a test (#175).** A reader who copied a printed token failed again: the message
  rendered `CONCURRENCY_SIGNALS` (39 tokens — `mutex`, `SharedArrayBuffer`) while acceptance is
  decided by `RACE_TEST_SIGNALS` (14 — `go test -race`, `loom::`, `pytest-asyncio`). Same class
  as `rules/code-quality-allowlist.txt` (#343), where following the documentation produced a
  worse outcome than adding nothing.

  **The irony is kept in the docstring.** `_accepted_signals()` exists to stop exactly this, and
  the hand-written parenthetical it replaced — "(race/loom/concurrent/parallel/atomic-counter/
  cancellation)" — names six tokens that are **all `RACE_TEST_SIGNALS` members**. The frozen
  prose was naming the RIGHT list; the fix that removed the drift risk pointed the renderer at
  the wrong constant while asserting, in that same docstring, that it now derived rather than
  restated.

  **Two further defects surfaced by writing the class-closing test**, which asserts that every
  printed token is accepted by the decider — an invariant that holds whichever constant a later
  edit points the renderer at. First: `\b--race\b` **could never match**, because a word
  boundary cannot hold between a space and a hyphen; it accepted only `x--race` and never
  `cargo test --race`, so the acceptance list held a pattern that could not accept the thing it
  named. Second: the regex stripper, written for `\bword\b`, rendered the real list as
  `cancellations+propagat` and `none[—-–]+single[- ]threaded)` — tokens nobody can copy. A
  message naming the right list in an unusable form is not a fix.

  A pre-existing test **encoded the defect**: `test_the_concurrency_refusal_lists_every_accepted_signal`
  required the message to derive from `CONCURRENCY_SIGNALS` and be long. Its purpose was right —
  a frozen parenthetical is how a message drifts from code — and its yardstick was the same wrong
  constant. Corrected rather than deleted, for the third time this day (see #169's two).

- **`install.sh` accepted an install as a place to install, and `--remove-withdrawn` could
  not run without a full reinstall.** Two defects of the same operation, both measured by
  making them: passing a consumer's `.claude` as the target built `.claude/.claude` with
  **917 files** — a complete second copy one level down — plus a records scaffold beside it,
  with nothing warning. The litter was the smaller half. **Every other flag then acted on the
  wrong tree**: `--remove-withdrawn` ran against the nested install, found none of the eight
  withdrawn skills there, and reported nothing, while the real install one level up kept all
  eight. A destructive flag that silently does nothing is what makes an operator believe the
  work is done.

  The refusal reads `squad.layout.has_kit` — the same predicate `resolve()` uses to decide a
  directory IS an install — rather than the basename `.claude`: a consumer may install into a
  differently-named directory, and a name check would miss exactly those while refusing an
  empty directory that happens to be called `.claude`. It names the directory to use instead.
  `test_install_refuses_an_unconfined_root.py` already refuses `$HOME`, the config dir and
  `/`, whose blast radius is the machine; this is the complement, whose blast radius is a
  duplicate.

  And `--remove-withdrawn` now removes and STOPS. It was reachable only through a full
  install, so the narrow, destructive, explicitly-authorised action could not be taken without
  the broad one nobody asked for — authorising the deletion of eight retired skills is not
  authorising every kit file to be replaced. Measured consequence: given that choice, the
  operator deleted the directories by hand, which is the mechanism being routed around. The
  standalone path also drops the test from 47.79s to 6.46s, because it installs nothing.

- **`--apply-upstream` called `classify_file` with two of its four arguments, so it refused
  exactly the files the checker had just declared applicable.** The promotion from `DIVERGED`
  to `STALE` runs only when given `kit_root` AND `rel`
  (`check_install_drift.py:233`), and `rel` is also what enables that function's ownership
  guard. The scan passes both and reported `stale: 9`; this passed neither and refused the
  same nine as `DIVERGED`. **One reader, called with less context than it needs to answer** —
  the inverse of the duplication the `PROJECT_OWNED` import removed in the same file, and
  just as capable of two answers to one question. Reported by a consumer that checked
  MEMBERSHIP of the stale list rather than its count, then could not act on it; verified here
  against a copy of that install, where both files now apply as `stale` and `agents/README.md`
  is refused by the ownership guard rather than misclassified.

  Two smaller defects of the same change closed with it. `classify_file` can now return
  `YOURS`, which fell into the "could not classify" branch — right refusal, wrong reason;
  it has its own branch. And the withdrawal report from #171 printed on EVERY per-file
  invocation: eight lines before a one-line result, 176 lines of repetition in a loop of 22,
  which is how a report teaches people to skip it. A withdrawal is news about the whole
  install, so it now prints only for the operation that touches the whole install.

- **A size in BYTES was spent slicing a string of CHARACTERS, and it made 350 recoverable
  files unreachable (#173).** `_blobs_from_batch` ran `git cat-file --batch` with
  `text=True` and advanced by the declared `size` over the DECODED stream. Every non-ASCII
  character left the cursor short by the difference, and this kit's prose is written with
  em-dashes and accents. Measured on `hooks/validate-command.py`: **59104 bytes against
  58717 characters — 387 lost per revision from 197 non-ASCII characters**;
  `git rev-list --all` names 14 commits for that path and the reader returned 7 contents,
  none of them the one a real install holds.

  **The consequence ran all the way to the upgrade path.** `classify_file` downgrades to
  `STALE` when the install's body appears in history, so a body the parser never produced
  could not match — and the file was reported `DIVERGED`, which `--apply-upstream` refuses by
  design. Measured before and after, on two consumers:

  | consumer | before | after |
  |---|---|---|
  | one with 400 differing files | `diverged 350 · stale 10` | **`diverged 0 · stale 361`** |
  | one installed today | `diverged 9 · stale 0` | **`diverged 0 · stale 9`** |

  Every one of the 350 is now applicable, and by PROOF rather than inference: the body is
  byte-identical to a revision this kit shipped.

  **Two conclusions of the same day were wrong because of it.** A line-level history
  criterion was proposed and then measured against the case it was never tested on — a
  consumer who re-adds a line the kit deliberately deleted — where it does not merely miss
  the case but REMOVES a protection the tool already has (`install_ahead` refuses it
  correctly). And "provenance only serves future installs" was refuted by a peer session
  measuring its own install: `# kit-commit` present, resolving and clean, with 8 of its 9
  differing files byte-identical to that commit. Both detours ended at the parser: the
  mechanism to answer this existed and was broken by a unit.

  Also fixed here: `--apply-upstream` restated `PROJECT_OWNED` inline, making it the fourth
  reader of "whose file is this" — the multiplication `check_install_drift._is_project_owned`
  refuses to add to in its own comment. It imports the declaration now.

- **A write verb inside a QUOTED STRING refused a read-only command — all ten were reachable
  (#168).** `check_kit_boundary` searched `WRITE_VERB_RE` over the raw segment, and
  `segments()` splits on `;`, `&&` and `|` with no notion of quoting, so
  `echo "no install agora: .claude/rules/architecture.md"` was refused and
  `echo "algo aqui: …"` was not — one Portuguese word apart, neither writing anything. Same
  class as the heredoc false positive `_split_heredocs` closed, and worse in one respect: a
  heredoc at least has the SHAPE of a write. Reported by a peer session that re-did the
  blocked read through Python and finished the work unchanged — **the block bought nothing at
  the price of a detour**, which is how an operator learns to route around a guard. Neither
  hypothesis raised was right: `$(grep …)` in a string passed and `--install` as a flag
  passed; it was the bare word. Fixed with `_mask_inert_quotes`, which is length-preserving
  and keeps `$(…)` and backticks readable — blanking a double-quoted span wholesale would
  have made `echo "$(rm .claude/x)"` a two-character bypass of the entire boundary. Masked
  for DETECTION, original for EXTRACTION, so `rm ".claude/x"` still resolves. **Two holes
  that predate the report closed with it**: `rm ".claude/x"` was never refused, because
  `(?<!\S)` rejected the quote as a neighbour, and neither was a backtick substitution,
  because `` ` `` was not in the verb's prefix class. `)`, quotes and backticks now terminate
  an extracted path, so a refusal no longer names `…run_slice_tests.sh)`.

- **A withdrawn kit file reached nobody, and a reinstall put it back (#171).** `install.sh`
  preserves any skill directory the source kit does not ship — right for a project's own
  skill, exactly wrong for one the kit RETIRED, and indistinguishable from it on disk.
  Measured on one consumer: 30 skills present and absent from the kit, **103 of the 111 files
  `check_install_drift` labelled "consumer-local" belonging to them**, and **0 of the 30 named
  in `.kit-manifest.txt`**, whose header states "Anything not here is the project's" — false
  for every one, and false BECAUSE the manifest is regenerated: the install that withdrew a
  skill erased the only record that the kit ever shipped it. Not inert: a stale
  `shared-understanding` cites a rule that moved and breaks `check_xrefs` for the whole
  install, and its pre-`--depth` `score_alignment.py` produced a BLOCKED verdict on an item
  the current copy scores ALIGNED at 92%. **By name, never by absence** —
  `mechanisms/distribution/withdrawn.txt` travels with the kit and is the only list
  `--remove-withdrawn` may delete by, because absence is how a project's own work would be
  deleted. Reported by default; a test asserts no entry names a skill still shipping, which
  would turn the list into a weapon. `check_install_drift` reports them as their own class:
  `consumer-local 111 → 84` on the consumer measured.

- **`skills/backlog-item/SKILL.md` taught that the routing table lives in `cycle-backlog.md`,
  which has been the LAST of five fallbacks since 2026-09-11 (#172).** It also claimed "one
  table and one truth" while `route_domain.py` resolves by precedence over five locations.
  The sibling skill has it right and warns about this exact failure; `route_domain.py`'s own
  docstring records the same drift happening to itself. Third instance, so the fix is a test
  that reads `_TABLE_LOCATIONS` from the source and fails when a document names a location
  the resolver does not read first — a table written to a shadowed location works until
  somebody adds a file ahead of it, and then stops with nothing saying why.

- **`test_cli_a_real_audit_names_what_it_could_not_measure` pinned the whole soft-cap list, so
  it failed on any machine without `knip` (#170).** Any missing optional auditor added its own
  `auditor_unavailable_*` entry and broke a test that is not about it — permanently red here,
  taking the whole `skills/code-quality/tests` suite with it. The test's own name says it
  reports what it could not measure, so an extra entry is the system under test working. Now
  membership, matching the `>=` assertion directly above it.

### Changed

- **`rules/testing.md § 4.1` gains the sharper case: the rule you just wrote does not apply
  to you automatically.** The section already said a builder cannot see the boundary they
  moved. Three measurements on 2026-09-22/23, across two sessions, say something worse —
  the knowledge was not merely present, it was FRESH. A session held an item out of
  `shipped` for four minutes between tag and registry, wrote in three places that
  integration is not availability, and hours later marked its own item `shipped` on a commit
  still only on its disk. A session built `TREE_MOVED`, told a peer that swapping a kit
  mid-run produces a verdict about no tree, then committed twice during its own run. A
  session wrote that unverifiable is not verified, then ran its own checker against a peer's
  files and reported the result as the peer's state. **The switch is from verifying somebody
  else's work to verifying your own**: outward the rule is a lens you hold up, inward it is
  something you already believe you satisfy, and *I just thought about this* reads as *I have
  handled this*. Recorded as an extension rather than a fifth decision document, because the
  section it belongs to already exists — and because a kit whose additions outrun its
  removals 12:1 should consolidate where it can.

- **A commissioned audit now says which directory its commands run from.**
  `select_auditors.py` emits an absolute `--output-dir` under the project's write root,
  and every `loop-*` plugin confines `--output-dir` under its own working directory (a
  path-traversal fix). Both halves are right; the join holds only at the project root,
  and neither side said so — `skills/review/SKILL.md` said "run each command exactly as
  printed", and the plugin's refusal names the FLAG (`--output-dir is unsafe`) rather
  than the directory the reader is standing in. Acting on that reading means moving the
  output directory, which is the one thing that must not move: `check_auditor_coverage`
  looks for the report exactly where the assignment put it. The assignment now carries
  `run_from` in its JSON and a `run from:` line in its printed form, and the skill says
  move the caller, never the `--output-dir`.

### Removed

- **`renumbered` — a finding that read the order blocks sit in a file and stopped the whole
  machine over it (#169).** It tested `numeric_ids != sorted(numeric_ids)`, where the list
  is the order ids APPEARED IN THE FILE, and it sat in `IDENTITY_CHECKS` — so a registry
  listing newest first, a legitimate and common layout, reported `INVALID` and
  `select_backlog_item.py` refused to hand out **any** item. Measured at 40 and 131 items;
  the same ids ascending were `SHIPPABLE_WITH_CAVEATS` / `ITEM_SELECTED`. **It could not
  have worked**: renumbering is a claim about two points in time and a checker sees one
  snapshot, so sortedness was a proxy for a property nothing here can observe. The
  observable half — no id appears twice — is `duplicate_id` and always was, and
  `rules/cycle-backlog.md` justifies the rule by what it protects ("a killed item keeps its
  number so the audit trail survives"), which is about values assigned over time and which
  a descending layout satisfies completely. The contract, `README.md`, `SKILL.md` and the
  selector's docstring now say the layout is the reader's to choose.

  **Found from the outside, and the timing is the lesson.** A peer session reported the
  finding firing on its 131-item registry, then reported that its selector did NOT stop —
  and was right to push back on a severity claim it could not reproduce. Its selector was
  an older generation without the `IDENTITY_CHECKS` refusal. One hour later it upgraded and
  measured the stoppage on the same registry: `grep -c IDENTITY_CHECKS` went 0 → 3 and the
  selector went `ITEM_SELECTED` → `BACKLOG_INVALID`. *Does not reproduce here* meant **not
  yet**, and every install still on the older selector was carrying a latent total halt.

  Two tests encoded the defect and had to be rewritten rather than deleted, because both
  were named for uniqueness and written for ordering: `test_non_monotonic_ids_are_a_blocker`
  and `test_a_reused_id_is_refused_for_the_same_reason_as_a_duplicate` each passed `B-005`
  then `B-002` — two DISTINCT ids — while their names said "reused". They now assert reuse
  where they claim to, and that mere sequence is not a finding.

### Added

- **The upgrade path is walked by a consumer, and coverage is asserted at the granularity that
  failed.** Six defects were filed on 2026-09-23 and the suite found ONE; five were reported by
  a consumer running the kit against a real install. `test_clean_install.py` already installs
  into a temp project and runs the gates from inside it — twelve tests, real install — and none
  of the five was reachable from it, because **a fresh install has no lag**. That is the state
  every expensive defect needed: a body that is an older kit revision (#173), a skill the kit
  once shipped (#171), a file with real git history (the two-argument `classify_file` call), a
  target that already IS an install.

  `tests/test_the_upgrade_path_is_exercised_by_a_consumer.py` materialises an older revision
  with `git worktree`, installs THAT into a temp project, then asks the current kit about it.
  A real worktree and a real install on purpose: a fixture that fabricated "an old install" by
  editing files would test the fabrication — the byte/character defect only appears against
  git's own `cat-file --batch` output. **Proven to detect, not merely to pass**: with #173's
  defect restored by mutation it fails with `diverged: 12` where a consumer that wrote nothing
  must report `0`.

  `tests/test_every_verdict_the_installer_can_reach_has_a_test.py` requires every `case` arm of
  the per-file mode to be exercised, and every `Drift` member to have an arm. **Flag-level
  coverage would not have caught the defect it closes**: `--apply-upstream` WAS tested, and one
  OUTCOME of it — `stale`, the one that mattered — was not. Also proven by mutation: an arm
  named `quarantined` that no test mentions fails the check. The arms are read out of the
  installer rather than restated, so a second list cannot drift from the first.

- **`docs/wiki/decisions/a-suite-measures-what-its-author-imagined.md`** — the fifth recorded
  class, and the only one whose subject is the suite. Three measurements from one day where a
  mechanism reported green about something it never examined: `check_english_only` saying
  `clean — 1153 tracked file(s)` about an untracked file, a history reader returning 7 contents
  for 14 revisions, a flag tested while one of its outcomes was not. It also states what it
  does NOT fix — the most effective detector that day was a second session disagreeing with a
  measurement, which is not a mechanism and does not generalise to working alone.

- **`install.sh --apply-upstream <path>` — a consumer could ignore a kit fix or reinstall 400
  files, and there was nothing in between.** Both existing modes replace the whole kit, and
  `boundary-check` refuses editing a kit file inside an install — right for a fix somebody
  WROTE there, since it protects one machine and the next install erases it. Neither answers
  the other case: a file that differs because the KIT moved and this install did not.
  Measured 2026-09-23 across four consumers with identical distributions — 400 files differ,
  splitting into `diverged 349 · install_ahead 1 · stale 10 · kit_ahead 40`. The new mode
  takes the kit's version of ONE file and **refuses every file this install holds unique
  lines in**, so it applies to 50 and refuses 350. **Six mechanisms were measured
  individually and all six classify `diverged` — the mode resolves none of them.** It is
  not the answer to the drift that motivated it; it is the answer to the cheap half beside
  it, and the file says so in its first paragraph so nobody arrives expecting otherwise. **The refusal is the design and it costs
  real coverage**: 22 of the 349 diverged differ by four lines or fewer, 83 by ten or fewer,
  and this refuses all of them, because *is this my work or my lag* is exactly the judgement
  `check_install_drift` prints that it cannot make — a small diff is not evidence of the
  answer, and a command that looked like it settled the question would be used where it does
  not. `check_install_drift` now names the command on the two classes it accepts and on
  neither of the two it refuses. The rationale first written here claimed the mode covered
  "67 files differing by one or two lines"; that number counted differing LINES and never
  resolved the CLASS, and the files it named are diverged. Corrected before merge, in the
  code as well as here.

- **`docs/wiki/decisions/the-system-already-said-it.md`** — the fourth class recorded on
  2026-09-22/23, and the only one whose subject is the investigator rather than a mechanism.
  Three cases across two sessions in one day: a sidecar lock reported as an escape while
  `write-exemptions.txt` already declared `.*.lock` with its reason; two pull requests opened
  by hand and reported as a defect while the workflow announced the behaviour with a
  `::notice` the log filter excluded; four required formats learned one gate refusal at a
  time while the template documented all four. **This is not *measure the premise*** — there
  was no claim to verify, the system had already written the answer in the file whose job is
  to hold it, and the remedy is opening that file rather than constructing a measurement. The
  record carries the generalised move that came out of the second case — read the STRUCTURE
  before the text, since `gh run view --json jobs` answers *which branch ran* where a
  severity grep cannot — and the question that costs seconds: *which file's job is it to
  answer this, and have I opened it?*

- **`check_verification_freshness.py` — when did this tree last verify itself, and does the
  answer still apply?** `run_slice_tests.sh` printed its verdict and exited, so the only way
  to answer *is it green?* was to run it again for fifteen minutes. Measured 2026-09-22: one
  session ran it four times in one day to answer that question, and two of the four answered
  about a tree that had moved underneath them. The runner now writes
  `.squad/records/verification/last-run.json` — what ran, on which commit, with what result,
  and whether the tree moved — and this gate reads it **in milliseconds rather than fifteen
  minutes**, which is the property that made the question go unasked. Six states, and two of
  them are the reason it exists: `never` is NOT `failing` — a fresh clone has not verified
  itself and is not broken, and collapsing them would fire on every checkout, which is a
  signal that always fires. `unattributable` is the runner saying its own result was about no
  single state of the repository, and reading that as green would launder exactly what the
  flag prevents. It ADVISES inside `promote_to_develop.py`, at the last moment before work
  leaves the branch it was written on, and refuses nothing: promoting unverified work is a
  legitimate call the caller makes, and what the gate refuses is silence about it.

- **`docs/wiki/decisions/a-reference-is-checked-in-one-direction.md`** — the class behind
  four cross-reference defects found in one sweep on 2026-09-22, in four different slices.
  A reference has two sides and one author, who writes the check holding one side in mind;
  the other question is not wrong, it is ABSENT, and absence has no failing test. It is
  worse than a missing check: a gate that covers one direction **reports a verdict**, and
  the verdict is read as covering the topic because its name says so — `is_complete: True`
  over a matrix whose rows point at nothing is not silence, it is an assertion somebody
  acts on. The record carries the two questions that find the missing half before shipping,
  the reason the two directions must stay separate findings, and the guard all four fixes
  needed: when the target document is unreadable, report nothing rather than reporting
  everything as unresolved.

- **`rules/session-injection.txt` — a project can ask the kit to speak less, and cannot ask
  a guard to stop refusing.** The kit injects three times per turn on its own initiative:
  1835 bytes of chain summary at session start, 1249 of parsimony ladder in front of every
  prompt, and 602 of advisory Stop warnings at the end — measured in a consumer 2026-09-18.
  The ladder's docstring argues the injection must be unconditional, *"a rule read at session
  start is a rule forgotten by the fortieth prompt"*, and that is right for a session writing
  code and wrong for one that is not: asking what time it is got the ladder in front of it,
  and **a rule injected into a turn it has nothing to do with is not a rule being remembered,
  it is a rule being spent**. `squad/injection.py` answers the question once for all three
  hooks. What it cannot reach is by CONSTRUCTION, not by comment: `validate-command` and
  `boundary-check` do not import it and a test refuses one that does, because a guard a
  config can silence is a guard that gets silenced by somebody who only wanted less text;
  and `Stop`'s suppression happens at the REPORT, never at the checks, so blockers still
  block and `--json` still carries everything found. `SQUAD_QUIET` overrides the file for one
  session in BOTH directions — turning it back on matters as much as turning it off. Absent,
  unreadable or undecidable text means SPEAKING: a parse failure that quieted the kit would
  remove the doctrine and the report that something is wrong at once. **Designed, measured
  and built inside a consumer's installed `.claude/`**, where the next `install.sh --force`
  would have erased it; found by reading `check_install_drift`'s `install_ahead: 3`, filed as
  #164, adopted with the sponsor's decision (#164).


- **`docs/wiki/decisions/a-step-that-cannot-fail-loudly-did-not-run.md`** — the defect class
  behind five measurements taken on one day across three sessions: a step that silently does
  nothing inside a procedure that reports success. An anchored insertion whose anchor had
  moved (twice here, three times in a sibling repository), a pytest run that never collected
  because its exit code belonged to `tail`, a hook measurement that resolved no layout and so
  refused nothing, and a quoted error message that closed a shell string and truncated the
  program reading it. None is a bug in the tool: each is the documented behaviour of the
  thing being used, and the defect is a caller that cannot tell that behaviour apart from the
  one it wanted. The record names the two defences that are not the same defence — assert the
  precondition, and have something downstream that fails — and the cheap test: *if this did
  nothing at all, what would be different?*

- **`check_plugin_freshness.py` — a premise the kit depended on and never checked: is the
  plugin it audits WITH the one that was committed?** Claude Code installs a plugin into
  `~/.claude/plugins/cache/…` and records the `gitCommitSha` it was built from;
  `installed_plugins.py` resolves by `installPath`, so every commissioned audit runs that
  snapshot rather than the repository. Measured 2026-09-22 by the session maintaining those
  plugins, walking the commission → audit → read chain end to end for the first time:
  **17 of 18 installed plugins were behind their repositories**, and the contract under
  test — `compute-verdict --emit-to` — did not exist in the tree that actually ran. The
  repository was right, this kit's reader was right, and what executed was neither: each
  half honest, the joint wrong, and no test positioned to look at the joint. Asked once
  before the first item, for `check_merge_autonomy.py`'s reason — discovering it per-audit
  costs the run, because the audit completes and only a missing field says anything was
  wrong. Scope is `rules/review-auditors.txt` rather than the machine: drift in a plugin no
  REVIEW commissions is somebody else's finding, and reporting it here trains people to
  skip the output. `unverifiable` — source not a local directory, no `gitCommitSha`, plugin
  absent — is reported apart from `aligned` and is never a failure, since treating *I could
  not ask* as *nothing is wrong* is the defect one layer down. Seven tests, every one
  driving the STALE case from a fixture: this machine currently reads 7 of 7 aligned, which
  is precisely the condition under which a gate gets written and never exercised where its
  defect can occur.

- **A written way back for a checkout that has no registry.** `BACKLOG.md` is unversioned
  by policy, so a fresh clone and a second worktree both reach that state normally — and
  nothing said what to do in it. Measured in a consumer 2026-09-21: 93 blocks present
  against 195 distinct `B-NNN` cited across the tree, 138 ids spent with no block; of three
  worktrees on that machine one held the file and two had none, and a session in one of the
  two registered `B-016` in good faith over an id already spent. `records-location.md §
  A checkout with no registry` now carries the procedure, in the rule that creates the
  situation rather than in a skill the reader would have to know to open. Four steps, and
  the first is **do not reconstruct the file**: a registry rebuilt from citations looks
  complete and is not, which is the state being described. The policy is restated as
  standing, so the section cannot be read as an argument for versioning the registry (#162).

- **`peer/<session> (what it verified)` — a third kind of signature, for a review that
  came from another session.** `squad/signoff.py` knew `human/…`, which an allowlist
  accepts as a person, and everything else, which is an agent. Three sessions worked this
  kit together on 2026-09-22 and each measured real defects in the others' work — a gate
  exercised only where its defect cannot occur, a waiver whose reason had never been
  measured, a status file that outlived the run that wrote it — and none of it could be
  signed. It reached the record as issue comments and nothing else. **A peer signature is
  refused unless it says what it verified**, in parentheses and at least four words: a
  person is accountable by being a person and a judge is named by the contract it ran
  against, but a peer is another agent with no contract binding it to this document, so
  the measurement beside the name is the entire value of the signature. It is NOT a human
  signature — `human_signed` stays false with a peer signer present, the weakest signer
  decides — and `alignment_judge` refuses to sign as one, the same refusal it already
  makes for `human/`.

### Fixed

- **A rule asserted a third party's defect in the present tense, three days after it was
  fixed.** `cycle-judge-codex.md` described the judge plugin hard-coding
  `knowledge-base/…` paths, with *measured on a consumer 2026-09-18* further down — and the
  plugin resolved that on 2026-09-22 (`85e55b5`). A reader took the date as *when the defect
  was found* rather than as *how far this sentence is still true*, believed it correctly,
  and recommended a fix for something already fixed. **A stale mechanism that answers is
  worse than an absent one; a stale document that asserts is worse than both, because
  nothing in it fails.** Verified by reading the installed plugin rather than by taking the
  report: `codex-companion-judge.mjs:39` carries the current root first and accepts both
  `-opportunity.md` and `-blueprint.md` rather than choosing. The passage is now past tense
  with the commit named, and the reasoning is kept — deleting it would erase why the seam
  exists. A sweep for other present-tense claims about third parties in `rules/*.md` found
  none.

- **A commit scope could name two areas and not one path.** `HEADER_RE` accepted
  comma-separated kebab-case segments — added because a change touching two areas had three
  bad options, *name one and be incomplete, invent a portmanteau nobody greps for, or drop
  the scope* — and refused a `/`. Measured 2026-09-23 on a consumer: five commits scoped
  `infra/tests`, a directory and its tests, reported as `header_shape` and reachable by **no
  override**, because `commit_scopes` is consulted only after the pattern matches. The three
  options left were the same three the comma fix already rejected, and `infra-tests` is the
  portmanteau: the hyphen stops matching the path it names. The segment rule did not loosen
  — each part is still lowercase kebab-case, and `infra//tests`, `infra/` and `Infra/tests`
  still fail; a scope may now be several parts separated by `/`, the way the comma made it
  several separated by `,`. The two compose.

- **A rule linked to `../docs/` and broke the post-install validation of every consumer.**
  `docs/wiki/` is the kit's authored knowledge and `install.sh` does not copy it — a
  deliberate placement, since `rules/README.md` places a file by who OWNS it and a consumer
  owns none of that. A relative link added to `current-constraint.md` resolved HERE
  (`rules/../docs/wiki/…` is `docs/wiki/…`) and resolved to `.claude/docs/` in an install,
  where nothing writes. `check_xrefs --strict` passed in this repository, `install.sh`
  exited 1 in a consumer, and **43 tests failed from one link**, all of them in the install
  suite. The sibling rules already had the convention — `cycle-release.md` and
  `autonomy-envelope.md` cite the wiki by absolute URL — and it was not followed. This is
  the shape `run_slice_tests.sh` names in its own banner: *red in an install and green
  upstream is a different finding from red everywhere*, and the kit's own checkout cannot
  see it by construction.
  `tests/test_a_rule_links_to_the_wiki_the_way_a_consumer_can_follow.py` reads the trees
  that travel **from `install.sh` itself** rather than listing them, because a second copy
  of what travels is a second thing to keep in step — which is this whole class of defect.

- **One installed auditor was neither commissioned nor mentioned, so nobody had weighed it.**
  `rules/review-auditors.txt` is careful about what it leaves out: `loop-project-purge` and
  `loop-pentest-audit` are refused with a reason, seven more carry a collective one — *no
  domain here derives them from a change* — and two carry their own. Measured 2026-09-22:
  seventeen `loop-*` plugins installed, seven commissioned, ten idle, and nine of the ten
  reasoned. `loop-system-cartography` appeared in no rule in this kit at all. That is not a
  mapping somebody rejected; it is a capability nobody weighed — and because the file is
  otherwise a record of decisions, **a reader counting the reasons concludes every absence
  was chosen.** Its reason is now written (it maps a system rather than auditing a change,
  and the question belongs to `cycle-design`), and
  `tests/test_every_installed_auditor_was_decided_about.py` fails on the next plugin that
  arrives undecided. The control test refuses the degenerate pass: a file that mentions every
  plugin and commissions none would satisfy a mention check and answer nothing.

- **The product chain was checked forwards and never backwards, so a goal nothing serves
  reached DESIGN.** `score_product_alignment` resolves both citations that point UP the
  chain — a `REQ-N` whose `serves:` names no declared objective, a `PIECE-N` whose
  `realises:` names no declared requirement — and asked nowhere whether every objective is
  SERVED and every requirement REALISED. Probed 2026-09-22 with two objectives and one
  requirement serving only `OBJ-1`: no cap, no dangling entry, nothing. The gap is caught
  eventually — `check_objective_coverage` exits 1 on an objective no ITEM serves — but that
  is at `/backlog-approve`, after DESIGN drew a system without the goal in it and BACKLOG
  filed items against that system. `check_merge_autonomy`'s argument applies verbatim:
  discovering it per-item costs the run, announcing it here costs one criterion. Guarded on
  the documents being readable, because reporting every objective as unserved when the TRD
  is missing turns an inability to measure into a measurement. **Fourth instance of one
  class in one day** — an identifier counted rather than resolved, or resolved in one
  direction only.

- **The system map could draw a piece nobody declared, and the design gate said nothing.**
  `check_design_completeness` computed coverage one way — every `PIECE-N` in
  `technical-pieces.md` must appear in the map — and never read the map back. A map naming
  `PIECE-99` against a list that declares only `PIECE-1` passed in silence. The two
  readings mean different things: a piece missing from the map is work the drawing forgot;
  **a piece in the map that nobody declared is the map drawing something no one decided**,
  or a piece list that lost an entry. `cycle-design` exists to settle the shape before any
  item is filed against it, so both answers are worth having then. Matched with the same
  whole-id rule the existing direction uses, for the same measured reason — `PIECE-1` is a
  substring of `PIECE-10`, and a substring test here would call `PIECE-10` declared on the
  strength of `PIECE-1`. **Third instance of one class found in one day** — an identifier
  counted rather than resolved — after the Coverage Matrix counting a row without opening
  the task it named, and a review finding carrying a path nobody opened.

- **A review finding pointed at a path nobody could open, and the report said nothing.**
  `consolidate_findings` carried each finding's `file`, deduped on it, rendered it and
  computed the verdict from the set — without ever opening it. Probed 2026-09-22: one
  BLOCKER at `src/this/path/does/not/exist.py:42` produced `NEEDS_FIXES` with no field,
  line or heading saying the path was gone. The argument for why that matters was already
  written one gate over, for the backlog's evidence pointers: *the next reader follows the
  pointer, finds nothing, and cannot tell whether the finding moved or was never real.* It
  applies verbatim to a review finding and had been applied to neither. Same shape as the
  Coverage Matrix counting a row without opening the task it named — **an identifier
  counted rather than resolved** — found by looking for more of that class. Resolved
  against the same roots `check_evidence_freshness` uses, asked of its owner rather than
  re-listed, because one root reported 41 dead pointers where 22 were dead. **Reported,
  never blocking**: a backlog item's evidence points at something that WAS measured, while
  a review finding may legitimately cite a path that does not exist — *the file is missing*
  is a defect somebody can report — so the caller keeps the judgement.

- **An empty `file:` became the four-character path `None`.** `_normalize_finding` used
  `str(f.get("file", ""))`, and a YAML `file:` with nothing after it parses to `None` with
  the key PRESENT — so the default never fired and `str(None)` produced a path that
  resolves nowhere and looks like one that could. Found by the pointer check above
  reporting a file nobody had written.

- **The Coverage Matrix gate counted a row and never opened the task it named.** It checked
  the TASK relation in both directions — a row naming no task is unmapped, a task no row
  names is an orphan — and checked the rest of the row in neither. A row reading
  `| G1 | something | T1.1 | AC-999 |` counted as mapped with `AC-999` declared nowhere in
  the plan, and the report came back `coverage_ratio: 1.0, is_complete: True`. Reported
  2026-09-22 with the consequence measured rather than imagined: a reviewer found `AC-004`
  orphaned — the row said `T2.1` and `T2.1`'s block declared something else — and a
  hand-written three-line cross-check then found **five more** the gate was approving as
  complete. The orphaned criterion was the one that would have caught the plan's shape
  defect, so **the gate that exists to prove coverage approved away the gap that mattered.**
  Both directions are now reported and kept apart: a row citing what no task declares caps
  under `matrix_cites_undeclared_criterion`, and a task declaring what no row cites is
  reported without capping — the matrix maps gaps to tasks, and a task may promise more
  than a gap asked. Identifiers are read from the WHOLE row rather than one column, because
  a plan may name its fourth column `Resolution` or `Criterion` and a row cites what it
  cites either way.

- **The rule that refuses flow metrics listed four absences, and three had stopped being
  true.** `current-constraint.md` declined to gate on flow with a good argument — *a hard
  gate against data that does not exist is answered by assertion* — and backed it with a
  blanket claim: *"we do not currently instrument flow across the ecosystem. There is no
  per-stage lead time, no wait time, no WIP series, no cumulative flow diagram."* By
  2026-09-22 the board computed throughput, WIP and item lead time. The sentence outlived
  the fact that justified it. **A stale refusal is worse than a missing metric**, because
  the refusal is what somebody reads before deciding not to measure — a reader acting on
  that paragraph would have rebuilt three measures the system already had. The rule now
  carries a table: what is computed, what is derivable with no substrate yet (per-stage
  timing, where `cycle_events` already emits start and end with slug and timestamp and the
  stream is empty only because no chain has finished here), and what is genuinely absent.
  **The five DORA metrics are refused specifically rather than by blanket** — four measure a
  DEPLOYMENT and this system does not deploy, it cuts a tag a consumer installs; the fifth
  needs commit → production and `git tag` returns zero here. Each carries what would change
  its answer. Decided and closed as #163.

- **`install_ahead: 3` printed beside `kit_ahead: 38`, and only one of them was a
  deadline.** `check_install_drift` rendered all four classes as `<class>: <count>` plus a
  file list, and the summary gave `DIVERGED` its consequence — *a copy in either direction
  deletes the other's fix* — while `INSTALL_AHEAD` got only the fact: *the install holds
  lines the kit does not*. True, and it omits what matters. `install.sh --force` snapshots
  `.claude/` into `.install-backups/` and replaces it, so INSTALL_AHEAD is **the only class
  whose lines are gone after an upgrade**: KIT_AHEAD is pure gain, IDENTICAL is nothing, and
  DIVERGED at least survives on both sides until somebody chooses. Measured 2026-09-22 on a
  real consumer: `install_ahead: 3` — three hooks carrying the wiring for a 94-line module
  the kit does not have at all (#164). The number printed on every run, was read twice that
  day by the session maintaining the kit, and nobody opened the files. Each class now
  carries what it COSTS beside its count, because a count in the same voice as a count that
  loses nothing reads as inventory.

- **`check_xrefs` resolved a citation against `.install-backups/` and named the backup as
  the file's location.** The markdown-link walk already skipped that directory, with the
  reason written above the line: *a backup of an old ecosystem is not this ecosystem*. Two
  other passes in the same file searched the whole tree and did not apply it —
  `_resolve_cited_doc` and the `bare_rule_name_resolves` check. Measured 2026-09-22 against
  a real install by the session that maintains it: *"rules/README.md cites
  `domain-routing.txt` as if it were in rules/; the file is in
  `.install-backups/20260829T121853/rules/`"*. That is the worse of the two possible
  answers — the file is gone, and the message says it is misfiled, sending the reader into
  a snapshot of a tree that has since moved. One predicate, `is_excluded_tree`, now serves
  all three, compared PART BY PART rather than as a substring so a document *about* backups
  is not mistaken for one. Applying it surfaced a citation in this repository that had only
  ever "resolved" by finding a file in an excluded tree.

- **The slice runner could not say whether the tree stood still while it ran.** Measured
  2026-09-22 in this repository: a run was started, three modules were edited during it, and
  the root bundle came back `1 failed`. The sentence was true and was about a state that
  never existed on disk as a whole — every other suite passed, because none of them reads
  the files that were being edited. `/review` already refuses that shape for its reviewers,
  recording HEAD and a status digest when the agents are spawned and reporting a moved tree
  above every finding; the runner those same sessions use to check their own work did not,
  so the one place a person looks before reporting a result was the one place that could not
  tell them the result was unattributable. It now captures HEAD plus a
  `--untracked-files=all` digest before the fan-out and again after, emits a `TREE_MOVED`
  trailer line for `sq test` to read, and prints the notice ABOVE the verdict. **It does not
  change the exit code:** a moved tree is not wrong on its face, it is unattributable, and
  that judgement belongs to the caller — failing here would turn every legitimate concurrent
  edit into a red suite, and staying silent is what produced the measurement above.

- **The board reported `lead_time_p50_hours: None` with a comment saying the item carries
  no entry date. It carries one.** `check_backlog_structure._parse_items` reads
  `Registrado|registered YYYY-MM-DD` into `Item.registered_on`, and `board_state` imports
  that exact parser — but `_board_items` dropped the field when building the dicts
  `_delivery` measures, so the fact existed two calls upstream and was discarded on the way
  down. The comment was right about `_delivery`'s INPUTS and wrong about the item, and a
  reader of that line concluded the registry had no entry timestamp and that adding one was
  a schema change. It is now `lead_time_p50_days`, computed: **days** because
  `registered_on` is a DATE, so the arithmetic is exact and the input is not — every figure
  carries ±1 day from the start side, and rounding to whole days would hide the arithmetic
  without removing the uncertainty. The p50 travels with `lead_time_measured_over` and
  `lead_time_terminal_total`, because most items predate the registration line and a median
  over the ones that had a date is a median over a subset.

- **A fixed-and-merged issue looked exactly like one nobody had touched.** `kit_issues.load()`
  lists open issues and filters those a person must decide; everything else goes to a lane as
  work. An issue whose fix is written, reviewed and merged — open only until the release that
  makes it installable — is open, unlabelled for a person, and indistinguishable from
  untouched. A lane given one spends an agent re-solving a solved problem and writes a report
  that looks like progress. `AWAITING_RELEASE` reads the `in-develop` label the project rule
  already prescribes, and `holding_reason` reports *waiting for a person* and *waiting for a
  release* apart: collapsing them would tell a reader that twenty issues need their attention
  when none of them does. Measured against the twenty this repository is holding in exactly
  that state (#163 is the fifth gap of the same review, filed rather than fixed).

- **A production incident entered the queue by age, behind everything filed before it.**
  `select_backlog_item.rank()` ordered on *(does not unblock a halt, status, item number)*.
  Age deciding among equals is right — it is the one signal an agent that wants to proceed
  cannot inflate — but some items are not equals for a reason unrelated to when they were
  filed. `source: live-incident` was already in the schema and already meant *something is
  wrong in the running system NOW*; it now opens an obligation band ahead of everything
  else, because the cost of waiting depends on the incident's age rather than the item's.
  Above the unblocking rule, and nothing is reversed: the two bands never competed before
  this one existed, and between them the one already burning goes first. **The band covers
  `live-incident` and nothing else** — a security finding or a legal obligation belongs
  there by the same argument, the registry has no field that identifies one, and the claim
  stops where the schema does. Inside the band, status still ranks before age: a `raw`
  incident is one nobody measured, and putting the chain on `evidence: none-yet` is the
  state G5 exists to hold.

- **A killed item could not name what replaced it.** `supersedes` and `regression_of` are
  written on the NEW item and validated in that direction, so a reader arriving at the dead
  one found `status: killed`, a `kill_reason`, and no way to discover that the question had
  been re-asked and answered. The registry held the answer — every edge is in the same file
  — and nothing exposed it. `lineage_successors()` computes the reverse edges and
  `check_backlog_structure` reports them, DERIVED and stored nowhere, like `blocked`: a
  second copy of an edge the file already carries drifts the moment somebody edits one of
  them. An id nothing replaced is absent from the map rather than present with an empty
  list.

- **The freshness gate was declared in two rules and run by nothing, and it answered to the
  wrong flag.** Four of this repository's own meta-gates caught it in the full suite:
  `check_plugin_freshness` took `--project` where the contract in `mechanisms/gates/_contract.py`
  says `--root`, it was absent from the roster that sweeps gates by that flag, and
  `test_something_runs_this_gate` reported it as *executed by nothing — not the CI, not a
  hook, not verify_ecosystem, not any script*. Being declared in `cycle-review.md` and
  `mechanisms/README.md` is being DESCRIBED, not being run. It now answers `--root` with
  `--project` surviving as its own alias, and `select_auditors.py` asks it at commission
  time, which is the moment before any audit runs. **The premise was also stated wrongly and
  is corrected:** the first draft said "asked once before the first item". Measured the same
  afternoon — 7 of 7 aligned, and the same 7 stale sixty minutes later, because the session
  maintaining those plugins had been committing. Drift is not an incident that happened once;
  it is the normal state of any plugin under active development. It ADVISES rather than
  blocks: which revision a consumer installed is theirs, and refusing the audit over it would
  stop a review for something the reviewer cannot fix from there. One unrelated failure in
  the same run: the recovery procedure added to `records-location.md` spelled an invocation
  that resolves in only one of the two install layouts.

- **The freshness gate resolved the home directory itself, and the installer's post-install
  validation failed on it.** `check_produced_files` reads the code for a module that
  CONSTRUCTS a destination under `$HOME` and requires it to be declared in `HOME_WRITERS`
  with a reason; `check_plugin_freshness.py` shipped with two such calls and no declaration.
  `verify_ecosystem` then failed inside `install.sh`, and **29 of 36 install tests failed
  with symptoms that named the installer** — not one of them said *an undeclared home
  writer*, which is why the first hypothesis was a stray untracked file at the root. Fixed
  at the root rather than by widening the exemption: both manifests are now read by
  `mechanisms/conventions/installed_plugins.py`, which already owns `~/.claude/plugins/`
  and already carries that exemption under the reason *reading the user's own configuration
  is not a write*. `Plugin` gained `commit` — the `gitCommitSha`, and the only field that
  says which revision is actually RUNNING, since `install_path` points into a cache — plus
  `marketplace`; `marketplace_source()` reads `known_marketplaces.json`. A second module
  needing the same exemption for the same reason is a second place to get the path wrong.

- **A `.squad` forgotten in `/tmp` made `/tmp` a project, and every throwaway run under it
  recorded there.** `project_root_for` walks up from the work it touched looking for a
  directory that owns a write root, and `/tmp` holds the throwaway tree of every test,
  smoke run and hand-made `mktemp -d` on the machine. One leftover turns all of them into
  one shared project, and nothing reports it because recording somewhere IS the success
  path. The system temp directory is now never accepted as a root — `/tmp`, `/var/tmp` and
  whatever `TMPDIR` names — while everything UNDER it still resolves normally, because
  `pytest`'s `tmp_path` lives there and the install suite builds real projects in it.
  `/tmp/.squad` is somebody's leftover; `/tmp/pytest-of-x/test_y0/.squad` is a fixture.
  Applied to both walks, `cycle_events.project_root_for` and
  `consolidate_findings._project_root_for`: they answer the same question about the same
  tree, and a guard on one of them is a guard on half the paths.

- **The release mechanism could not express the shape its own consumers release in.**
  `promote_unreleased.py --version` took one semver and refused
  `create-toolkit 3.0.2, @acme/http 2.3.0, acme-core 0.69.0`, while the three sections
  below the one being written in that CHANGELOG were multi-package headings of exactly that
  form. So the script could not perform the promotion `cycle-release.md` prescribes for the
  common case, and the promotion was done by hand — the heading read off the file rather
  than invented, which is the only reason it stayed consistent. `squad.semver.parse_release`
  now reads a release line as one bare version or several `<package> <version>` components.
  Every component is validated and one bad component refuses the whole line: partial
  acceptance writes a typo into a heading nobody edits again, and `render_release_notes.py`
  looks the section up by exact string. A pre-release in ANY component refuses the line,
  because promoting at rc empties `[Unreleased]` for every package in the heading (#151).

- **A reviewer's brief forbade the write it also required.** The same template said *"never
  in the shared tree"*, *"scratch files go under /tmp, never under the repository"*, and
  *"save to `{FINDINGS_DIR}`"* — an absolute path in the shared checkout. A reviewer reading
  all three had no legal way to deliver its findings, and one of them staged in `/tmp` and
  copied; the one that does not improvise loses its file at the last step, after the whole
  review has run, and an absent findings file is indistinguishable from a reviewer that
  found nothing. The five templates now name the findings file as the one expected write
  into the shared tree. The boundary half of that report did NOT reproduce on re-measurement
  — `is_project_owned` asks what the install manifest claims rather than what sits under
  `.claude/`, so an agent worktree was already the project's; a test now pins that, since
  correct-but-unasserted behaviour is what a later tightening removes silently (#149).

- **A requirement closed by the Final Phase was unexpressible, so eleven rows read as
  requirements nothing closes.** `TASK_ID_RE` is `T<n>.<n>` and no plan gives its Final
  Phase a task id — the heading is `## Final Phase: Integration Validation`, an H2 rather
  than a task — so a matrix row citing `Final Phase` matched nothing. Measured 2026-09-21,
  once readable matrices made them visible: 19 rows closed nothing and 11 had this
  structural cause. One plan closes NFR-002 by name in its Final Phase acceptance criteria
  while its matrix row could only say `Final Phase`. **The decision, with the option that
  was refused:** the Final Phase does not get a task id; the parser accepts it by name.
  An id would have made it a task to `check_tdd_in_bugfix.py`, which demands a RED-test
  shape per bugfix task, and to `check_concurrency_tests.py`, which reads the same shape —
  propagating a requirement through three gates to fix a citation in one, and forcing a RED
  test onto a phase that validates work already done. The citation is checked rather than
  merely recognised: a row may cite the Final Phase only if the plan has one, since a
  section nobody wrote is the dead pointer this kit refuses everywhere else.
  `plan-template.md` now states what the Task column accepts, so a bare em-dash and prose
  like *already shipped* are visibly not closures (#150).

- **A Coverage Matrix the parser could not read reported as a matrix with no rows, and
  nine plans of twelve were INVALID for it.** `_parse_matrix_rows` took the task from
  `cells[2:]` by POSITION and dropped any row with fewer than four cells. The template
  declares four columns, so a plan that wrote two parsed to nothing — and
  `CoverageReport(total_gaps=0, mapped_gaps=0)` is byte-identical to what an empty matrix
  produces. `coverage_lt_100` then fired at cap 49 and the plan came back INVALID, with
  nothing anywhere saying the table had not been read. Measured 2026-09-20 across twelve
  plans on disk: seven wrote two columns, two more wrote `Requirement | Closed by |
  Verified by` with the task in `cells[1]`, and only two scored SHIPPABLE. The parser now
  finds the task column BY HEADER NAME, accepting the template's `Task(s)` and the
  `Closed by` that plans in the wild wrote, and an unrecognised header caps under its own
  id — `coverage_matrix_unreadable`, same INVALID consequence, stated cause. Chosen over
  refusing a non-conforming header at authoring time, which would help the next plan and
  none of the nine (#155).

- **The review recorded the tree the SPAWNER ran in and the agent prompts called it the
  reviewers'.** `capture_tree_state` writes HEAD and a status digest and said nothing about
  whose tree they belong to, while five reviewer templates told each agent *"the consolidator
  records the tree state when you are spawned and compares it afterwards"* — so a clean
  comparison read as evidence the reviewers saw the change. It is evidence about a tree none
  of them opened. Measured 2026-09-20: the record held the shared checkout at `a84eda52a`
  while every spawned reviewer ran in a worktree at `0051d2f6b`, which
  `git merge-base --is-ancestor` says does NOT contain the change under review. Two of five
  noticed the code looked pre-change and re-derived their findings against the right ref;
  neither was told to, and nothing downstream could tell them from the three who did not.
  `.tree-state` now carries `recorded_by` and `recorded_in`; each reviewer declares the
  `tree_head` it actually read; and `check_reviewer_trees` reports — in the markdown above the
  findings and in the JSON a gate reads — every reviewer whose tree lacks the change. Stale,
  undeclared and unresolved are three answers, not one: an unquoted sha of only digits loses
  its leading zeros to YAML and is reported as unusable rather than as either (#148).

- **A locally-hosted panel seat is a change to the machine, and the table it is written in
  could not say so.** `rules/review-panel.txt` now records what pointing a seat at a
  self-hosted model implies. Measured in a consumer 2026-09-20: three outside seats moved to
  a local `llama3.2`, `ollama serve` began listening on 11434, and a unit test that mounts an
  `ollama/` provider — documenting in its own comment that nothing listens in CI, so the call
  fails fast — instead CONNECTED and hung to a 30 s timeout. 1 failed of 8107 with the port
  open, 3 of 3 with it closed. That run's `/implement` validation reported `coverage` FAIL,
  and the failure was the panel's server rather than the codebase (#147).

- **A panel recorded which document it voted on and never which version of it, and the
  class of records nobody could verify was still growing.**
  `check_panel_approval._artifact_drifted` compares `artifact_sha256` against the bytes on
  disk and treats its absence as *cannot verify* rather than as drift — a deliberate
  allowance for records written before the field existed. Nothing wrote the field:
  `convene_panel.py` never mentioned it and `cast_vote.py` copied `artifact` out of the
  assignment without hashing it, so the only place it existed was prose in two SKILL files
  telling an agent to hand-write the record. Measured 2026-09-20: a record written at 13:09
  approved a plan last edited at 20:04 the same day, and the gate printed `panel APPROVED`
  with nothing a reader could act on. `cast_vote.py` now hashes the artifact when it creates
  the record — once, because the hash belongs to the panel and not to a seat — and writes no
  key at all when the path is empty or the file is absent, because a record that looks bound
  and binds to nothing is worse than one that admits it cannot be checked (#145).

- **A reviewer who returned a document was frozen at the verdict it earned before the fix.**
  `cycle-plan.md` describes the loop — return, revise, re-score — and no mechanism completed
  it: `cast_vote.py` refused a second vote from one seat, and the only other route was
  re-running `convene_panel.py --write`, which `skills/panel/SKILL.md` lists as an
  anti-pattern in its own words. Re-voting happened anyway, by hand, surviving only as
  `<slug>-plan.roundN.json` filenames a previous session chose. `cast_vote.py --supersede`
  makes it a supported path: the verdicts on the previous text are archived into `rounds[]`
  with the hash of that text, the other seats' votes are carried and MARKED
  `carried_from_round` so a tally cannot read three seats agreeing about one document when
  they agreed about two, and the flag is refused when the artifact has not changed —
  otherwise it is the duplicate refusal with an extra argument. The shape is `/review`'s: a
  fixed BLOCKER is marked CLOSED keeping its severity, never deleted (#144).

- **A skip outlived the defect it waited on, and the test went green through the branch
  that says the work is unfinished.** `tests/test_kit_manifest.py` guarded its `legacy_gone`
  assertion with a conditional `pytest.xfail` while the kit still shipped an empty
  `rules/domain-routing.txt` for `install.sh` to copy. When that file was deleted and the
  installer stopped recreating the retired path, the condition became false, the branch stopped
  being taken, and the assertion started passing — with no signal that the thing it was waiting
  for had landed. A skip whose condition has become false does not announce itself; it simply
  stops being exercised. The assertion is now unconditional and the comment records what the
  scaffolding was for (#157).

- **The git guard told a citation apart from an invocation, and each round of that fix
  opened bypasses of the rule it protects.** `hooks/validate-command.py` was refusing
  prose that merely NAMED a forbidden command — `echo "…git checkout main"`, a heredoc
  carrying the phrase, a `grep` searching for it — and correcting that in the direction
  being complained about turned seven false blocks into zero and, across four rounds,
  opened six bypasses, then three, then five. Every one was found by running the same
  payloads in BOTH directions. The guard now reads the command POSITION rather than the
  text: a quoted name (`"git" checkout main`) executes and is blocked, the
  same name inside an `echo` is a citation and stays quoted, and a wrapper (`xargs`,
  `env`) holds the command position open across its own flags rather than merely the next
  token — which is why `xargs git checkout` blocked while `xargs -I{} git checkout {}`
  did not. `tests/hooks/test_citing_a_command_is_not_running_it.py` pins both directions.
  The lesson generalised into `rules/testing.md`: when you are FIXING, the lens you skip
  is the one you just moved.

- **The panel premise gate answered a wrong path with a verdict about the roster.**
  `check_panel_capability.py` returned `VIOLATED` whenever the roster could not be read,
  on the argument — correct for the DEFAULT path — that a project with no declaration
  cannot form a panel. With `--panel` given by the caller, the same branch printed
  `PREMISE VIOLATED — no valid review panel can be formed from rules/review-panel.txt`
  for a file it had never opened. Measured 2026-09-21: `--panel discover` (the phase name,
  where a path belongs) reported the premise violated for all three gated phases while the
  roster on disk in fact HOLDS, and the reader acted on it. A roster the caller named and
  that is absent establishes nothing about the project's panel, so it is now `UNCHECKED`
  (exit 2) and the default path keeps `VIOLATED` with its argument intact — the split
  `check_auditor_coverage.py` already makes on its own side, under the same sentence: an
  inability to measure must not become a passing measurement, and must not become a
  failing one either.

- **The panel waiver outlived the obstacle it named, and the roster contradicted the
  cycle rules it serves.** `rules/review-panel.txt` seated three Anthropic reviewers per
  gated phase under `single_family_panel = accepted`, whose reason named codex CLI 0.120.0
  refusing every model the account exposes. Measured 2026-09-21: the installed CLI is
  **0.154.0**, and `codex exec "Reply with exactly: SEAT_OK"` PRINTS `SEAT_OK` on
  `gpt-5.5`. The obstacle was gone and the waiver was not — so `cycle-discover.md` and
  `cycle-plan.md`, which both already name `judge-codex:*` as the orthogonal chair, were
  describing a seat the roster did not hold. One `argus-pattern-analyst` row per phase now
  names the judge-codex seat and both waiver keys are deleted; `check_panel_capability.py`
  reports `9 seats across anthropic, openai` and stops printing the single-family warning,
  and `convene_panel.py` resolves the seat to family `openai` in all three phases. The
  design seat is `plan-judge` because judge-codex supplies no design-judge — an
  approximation the roster states rather than glosses. `tests/test_a_single_family_panel_is_declared_not_assumed.py`
  asserted the waiver unconditionally, so it failed on a roster that had just got better;
  it now checks both directions — one family requires the declaration, two or more require
  its absence — which is the side that was missing and the side the defect was on.

- **The panel waiver named a reason that was false on this machine, and nothing re-read
  it.** `rules/review-panel.txt` declared `single_family_reason = no non-Anthropic
  provider is configured for this project` while `codex` sat on PATH at `/usr/bin/codex`,
  `~/.codex/auth.json` existed, and the `judge-codex` plugin was installed supplying the
  `discover-judge` / `plan-judge` / `final-judge` seats that `cycle-discover.md` and
  `cycle-plan.md` both name. The panel is genuinely single-family — the installed CLI
  (0.120.0) is refused by every model the account exposes, `400: gpt-5.5 requires a newer
  version of Codex` — but the file named the wrong cause, which is the difference between
  a cost somebody chose and one nobody could see. The reason now states what was measured
  and carries the upgrade path, and `check_panel_capability.py` grew `waiver_contradicted()`
  so a waiver claiming "no provider is configured" is refuted when a provider binary is on
  PATH. Only that class of reason is checkable: a broken CLI or a refused model is a claim
  about behaviour, and probing it would cost a live call on every gate run.

### Added

- **A rule can now be cited by something a rename cannot break.** A rule's only handle
  was its path, and paths move: 1209 citations of the form `rules/<name>.md` inside this
  kit, and on one consumer's registry 33 of 109 backlog items citing a path in here —
  including items about that project's own product. Of the 6 dead pointers a freshness
  check found in that registry, 5 were paths that had moved. `squad/rules.py` gives every
  rule a stable id (`SQ-ERR-01`) that survives any rename, and
  `mechanisms/gates/check_rule_identity.py` holds the three properties a citable id needs:
  every rule declares one, ids are unique, and a retired id is never reused — a reused id
  makes an old citation resolve to the wrong rule, which is worse than a dead one. The
  shape is ESLint's, for its three stated reasons: portability across versions, freedom to
  reorganise internals without breaking consumers, and one namespace for core and plugin
  rules alike.

- **Evidence age is reported and a dead pointer fails.**
  `mechanisms/gates/check_evidence_freshness.py` separates two things a single "staleness"
  number conflates. OLD is not a defect — a thirty-day-old measurement of something nobody
  has touched is still true, and failing on age trains people to re-measure on a calendar
  rather than on a reason. WRONG is: evidence citing a path that no longer resolves leaves
  the next reader unable to tell whether the finding moved or was never real.

- **A wired hook that points at nothing is now caught.**
  `mechanisms/gates/check_wired_hooks.py` checks that every hook an install wires in
  `settings.json` resolves to a file that is there. `hooks/validate-command.sh` left this
  kit in `260892f` when the hooks became Python, and an install predating that commit kept
  the shell copy wired. Measured against the live `.py`: the retired shell hook diverges in
  2 of 36 payloads and BOTH divergences are permissive — it allows `git stash` (forbidden
  while worktrees exist) and `--force-with-lease` on `workspace`. The upgrade left a gate
  running that the kit had already replaced, with the replacement's stricter rules not in
  force, and nothing said so because nothing looked.

- **Commissioned audits now carry a cost ceiling.** `select_auditors.py` built
  `/{plugin} {target} --output-dir … [scope]` and stopped, so every auditor ran at its own
  default — 60 global iterations for the `always` one, 80 for most, 200 for
  `loop-performance-audit`. A change touching `security` and `testing` commissions three of
  them: up to 220 halt-loop iterations for one backlog item, at a depth nobody in the chain
  chose and no reader of the assignment could see. `rules/review-auditors.txt` gains one
  `max_iterations` key, `parse_ceiling()` refuses anything that is not a positive integer,
  and the value reaches every commissioned command as `--max-iterations N`. Declaring none
  omits the flag entirely — the kit does not invent a depth the project never chose. The
  shipped value (40) is a chosen floor, not a measured one, and says so where it is
  declared.

### Changed

- **The kit stopped shipping a `rules/domain-routing.txt` placeholder it had already
  moved.** The routing table lives in the write root — where `squad.paths.write_routing_table`
  puts it and where `detect_domains.py --write` writes it — and the kit went on recreating
  a placeholder under `rules/` on every reinstall for three weeks after the destination
  moved. `rules/README.md` names the real location now, and its own file count follows.

- **The read-only study zone moved into the write root: `study-material/` →
  `.squad/study-material/`.** `rules/reference-provenance.md` guards third-party material
  for a legal reason, not a stylistic one — *"a literal copy carries the original licence
  into this repository"* — and the zone was a TOP-LEVEL directory, kept out of the index
  by a single `study-material/**` line in `.gitignore`.

  One deletable line stood between a cloned peer project's licence and this repository's
  history. Inside `.squad/` the question does not arise: the write root is ignored whole,
  so nothing under it can reach the index at all. The guard is unchanged — nothing is
  written into the zone, nothing leaves it by command, no commit message cites it — and
  the path it guards can no longer be committed by accident.

  **The cost, stated rather than discovered.** A consumer still holding material at the
  old top-level path is no longer guarded: writes into it are allowed, copies out of it
  are allowed, and the leakage detector does not read it. `reference-provenance.md` § 1
  says so and says to move it, the same way it already stated the cost of retiring
  `records/references/`.

- **The zone is spelled once.** It was written three times, in three shapes:

  ```
  hooks/boundary-check.py       (^|/)(\.claude/)?study-material/
  hooks/validate-command.py     (\./)?(\.claude/)?study-material/
  check_reference_leakage.py    ZONE_DIRS = ("study-material",)
  ```

  `squad/boundaries.py` owns it now, which is where its own docstring already argued it
  belonged: *"a rule living in one file and missing from another is how the gap
  reopens"* — recorded there about the previous instance, where `boundary-check` refused
  `Edit`/`Write` into an installed kit while `validate-command` knew nothing about it,
  so `sed -i` reached the file `Edit` had just refused.

### Fixed

- **A checker mis-read the prose it audits, and blamed the code.**
  `test_boundary_check_prose_agrees` extracts every backticked zone path from
  `SECURITY.md` and `hooks/README.md` and asserts the hook blocks each one. Its pattern
  required a zone to start with a LETTER, so when the prose began saying
  `.squad/study-material/` it extracted `squad/study-material/` — and reported the hook
  failing to block a path the prose had never named. A checker that mis-reads its own
  input accuses the code of the checker's bug. It reads a leading dot now.

- **The zone pattern was anchored too tightly for the text the guards actually feed it.**
  The first version required start-of-string or a slash before `.squad/`, which is right
  for a clean path and wrong for the free text these hooks receive: a shell command line
  and a `-m` body. `git commit -m "see .squad/study-material/x"` stopped being blocked.
  A lookbehind gives the same protection without the anchor — `mine.squad/study-material/`
  still does not match, and neither does the `squad/` PACKAGE, which has no leading dot.

### Changed

- **`.squad/` in this repository now means what it means in a consumer: one machine's
  run data, ignored whole.** The kit kept its own eleven ADRs and SOPs at `.squad/wiki/`,
  versioned through a `!.squad/wiki/` negation in `.gitignore`, on the argument that
  *"this kit's durable knowledge IS its source"*.

  The argument was true and the location was the problem. `records-location.md` declares
  `.squad/` the write root **of the project being maintained**, so one path meant two
  things — authored product here, run output in every consumer — and the kit carried a
  worked example in its own tree of writing authored documents into a write root.

  The bundle moved to `docs/wiki/`, versioned like the rest of the product. `.squad/` was
  deleted, `.gitignore` ignores it whole, and
  `tests/test_write_root_is_versioned_correctly.py` now refuses a TRACKED file under it
  at all. A `.squad/` appearing here from a cycle run is not an error — that is what the
  directory is for.

  **Nothing changes for a consumer.** A project maintained by the kit still keeps its OKF
  bundle at `<project>/.squad/wiki/`, and `wiki_dir()` still resolves there. The new
  `authored_wiki_dir()` answers for the other kind — documents people wrote, shipped with
  the product — and is deliberately a separate function rather than a third fallback
  inside `wiki_dir()`: making it a fallback would put both kinds back behind one name,
  which is the ambiguity this move removed.

### Fixed

- **The move silently narrowed a sweep, and the sweep read the same.** `check_sop_structure`
  covers the OKF bundle plus every skill's `SOP.md`. It finds the bundle through
  `resolve_knowledge_dir`, which answers from the write root — so the moment the kit's
  four SOPs left it, they stopped being swept:

  ```
  before the move:  read 43 SOPs: 237 step(s), 167 decision branch(es)
  after the move:   read 39 SOPs: 209 step(s), 142 decision branch(es)   ← unreported
  ```

  Four procedures carrying `last_reviewed` and a review interval, with nothing reading
  those dates any more, and a gate reporting a clean sweep of the remainder. That is the
  defect this kit names more often than any other, caused by the move rather than found
  by it. Both gates sweep both bundles now, and `check_sop_run` resolves a run-file's SOP
  from either — a step-count mismatch against a SOP that cannot be found reads exactly
  like a SOP with no steps. Back to 43.

- **Rules cited documents a consumer never receives, and nothing said so.** Six links
  in `rules/`, `skills/` and `README.md` pointed at the kit's own ADRs with a relative
  path. In an install those resolved to `.claude/../.squad/wiki/…` — outside the tree
  `check_xrefs` walks, so the gate never looked and every install reported zero broken
  links. Moving the bundle to `docs/wiki/` brought the same links INSIDE that tree and
  the warnings appeared at once: not a regression, an exposure. They are repository URLs
  now, which resolve for whoever installed the kit. A clean install reports **0**
  markdown-link warnings, measured.

### Added

- **The chain now confirms that what it published exists.** `cycle-release` ended at
  `gh release create` and emitted `RELEASED`. Nothing looked afterwards — so a release
  left as a DRAFT, a `gh` call that failed *after* the tag was already pushed, or a tag
  that never propagated each produced `RELEASED` over an artifact no consumer can fetch.
  That verdict is what `cycle-maintenance`'s ADVANCE reads to write `shipped` into the
  registry.

  `mechanisms/gates/check_release_reachable.py` runs in Step 7, immediately after the
  publish, and checks three ways the last step half-succeeds: a release exists for the
  tag, it is not a draft, and it names the tag that was cut. It runs for **every** item,
  with or without a `milestone_id`.

  **What it deliberately does not claim.** That a package is installable from npm, PyPI
  or crates.io — that needs the network and a registry. And that the delivery works —
  `/acceptance` exercises that, against declared criteria. Saying so in the gate keeps
  it from being read as the stronger check it is not. An absent or unauthenticated `gh`
  exits 2: an inability to look is not a look that found nothing. 6 tests.

  This came from an external review, which read the milestone-only acceptance rule as
  leaving every off-roadmap item unverified. Half of that reading was right.
  `cycle-acceptance.md` argues that an item nobody promised a user has no user-visible
  promise to exercise, and for the PRODUCT question the argument holds — it was
  answering a different question from the one being asked. Whether the thing shipped at
  all has an answer for every item, and nobody was asking it.

- **`README.md` § Where this ends.** The system never said where it stopped, so every
  outside reading had to assume it meant to cover the whole life of software — and
  report the absences as failures. Deploy, operation, security beyond dependencies,
  deprecation and product discovery are now named as absent, each with what stands in
  for it and why a phase pretending to cover it would produce the exact failure this kit
  refuses: a green verdict over something nobody measured.

  The security row is the one worth reading precisely. One mechanised gate exists and it
  is narrow — `check_deps_audit.py` caps a plan at INVALID on a CRITICAL/HIGH CVE in a
  declared dependency — plus `hooks/boundary-check.py` on write paths. SAST, DAST, SBOM,
  licence audit, threat modelling and secret scanning are not here, and the row says so
  rather than letting two mechanisms imply a practice.

### Changed

- **The three conditional transitions are part of the chain, not exceptions to it.**
  `HOW-TO-USE.md` called the chain unbreakable and then documented three ways around it
  — DESIGN skipped when the system is drawn, entry at DISCOVER for a `--mode bug` with a
  failing test, no ACCEPTANCE without a `milestone_id`. Each is correct and each was
  written as an exception. A chain called unbreakable while three documented paths go
  around it teaches its readers that the word is decorative, and the next shortcut gets
  taken without one. They are a table now, with the condition and the cost of each.

- **"Until a person signs" was re-freezing unattended runs.** `HOW-TO-USE.md` said DESIGN
  ends at `AWAITING_REVIEW` until a person signs, while
  `skills/_kit-rules/alignment-threshold.md` § 80 lets `alignment_judge.py` sign when no
  person is coming, and `score_alignment.py` reports `signed_by_is_human` beside
  `reviewer_signed_off` so a judge's approval reads as the weaker claim it is. Read
  literally, the sentence promised a human block the system does not enforce — the same
  stale wording `cycle-implement.md` records having re-frozen every unattended run at
  `AWAITING_REVIEW`. The diagram's "the ONLY phase a human attends" is now "the only
  phase that WAITS for a human", which is what is true.

- **`SQUAD_AGENTS.md` → `docs/SQUAD_AGENTS-HISTORICAL.md`.** The file has carried a
  `Status: HISTORICAL` banner since 2026-09-08, explaining in its first paragraph that
  its "14 agents" mixes agents with the scripts they run and that only VERA is on disk.
  An external review read it anyway as a live roster and reported "two competing truths".
  The banner was not the problem: the NAME is what a reader meets first — in a directory
  listing, in a search result, in a link — and a file whose name claims to be the
  manifest is read as the manifest whatever its first paragraph says.

### Fixed

- **Two allowlists exempted nothing, and one of them was printed as the remedy.**
  Three files in `rules/` document the same exemption contract — pipe-separated fields,
  an ISO sunset within 90 days, expired entries ignored, malformed entries refused. One
  of the three was read by anything:

  ```
  code-quality-allowlist.txt     load_allowlist()   parsed and enforced
  deps-audit-allowlist.txt       -                  no reader anywhere
  plan-confidence-allowlist.txt  -                  no reader anywhere
  ```

  `check_deps_audit.py` is the worse case, because its HARD cap TELLS a reader to use
  the file nothing opened: *"Bump the dependency, or allowlist the CVE in
  `rules/deps-audit-allowlist.txt` with rationale and sunset."* Following that
  instruction wrote an entry, changed nothing, and produced the same message on the next
  run — a gate teaching a remedy it had not implemented. Both allowlists are now read.
  A waived CVE is stated in the reason rather than waved through in silence: an
  exemption a reader cannot see is indistinguishable from a CVE that was never there.

  `plan-confidence-allowlist.txt` promises *"Plans listed here are permitted to return
  verdict=INVALID without failing CI"* in the file itself, in `PORTABLE.md` § 4 and in
  `plan-confidence-golden-rule.md`. `setup.sh` installed it and `test_portability.py`
  asserted it EXISTS — a test that attests presence and never behaviour, which is how a
  dead allowlist looks alive. The waiver now applies **to the exit code alone**: the
  verdict still prints `INVALID`, because rewriting it would hide the plan's state from
  every reader, which is a different and worse thing than not failing CI.

  **One thing the allowlist still cannot do, stated rather than discovered.** Its own
  example — `my-followup-plan|…|Follow-up note (not a full plan); no Coverage Matrix by
  design` — describes a plan with no Coverage Matrix section, and that never reaches
  `INVALID`: `run_structural.py` exits **2**, "No '## Coverage Matrix' section found in
  plan", the code for a plan it could not read. The waiver deliberately does not cover
  exit 2 — exempting it would turn "unreadable" into "passed".

- **`records-location.md` sent readers to a directory nothing writes, in the section
  that verifies such claims.** The rule declares **"`<project>/.squad/` is the one write
  root. Always, in every layout"** and **"There is no layout exception"**. Its
  *Enforcement* section opens: *"Measured 2026-09-05, because this section named three
  mechanisms and two of them do not exist. A rule that lists enforcement a reader cannot
  find is worse than one that lists none: it stops them looking."*

  The third item — the only one marked **This one holds**, with line numbers — claimed
  `install.sh` and `patch_install.sh` scaffold `.claude/records/{…}`. Measured on a clean
  install: `.squad/records/{acceptance,audits,backlog,brainstorms,discoveries,…}` is
  created, `.claude/records/` is not created at all, and `install.sh:772` is a comment
  about `merge_settings.py`. The one item that said HOLDS had aged into the same defect
  as the two it struck through. It now names the real lines, and points out that neither
  shell script spells the root — both ask `squad/paths.py` — so the claim cannot drift
  the same way twice.

- **39 records paths across 11 cycle rules pointed outside the write root.** Measured:

  ```
  rules/cycle-*.md    22 paths `records/…`      1 `.squad/records/…`
  the skills           0                       35 `.squad/records/…`
  ```

  A clean split: what EXECUTES uses the write root, what DOCUMENTS sends the reader
  where nothing is written — and `records-location.md` opens by naming that exact cost,
  *"a reader who checks the wrong one reports absence where evidence exists."* Same
  defect as the install message corrected two entries above, at seven times the size.
  `tests/test_a_rule_points_at_the_write_root.py` holds every `cycle-*.md` to it, with
  one narrow exemption: the rule ABOUT the move must still be able to write the old path
  in order to say it is old.

### Changed

- **One sunset policy for every allowlist.** `squad/allowlist.py` owns the window, what
  an expired entry means, and that a malformed line is refused rather than silently
  dropped — the knowledge three files documented and one enforced. The FIELDS stay with
  their consumers: a CVE exemption names a package and an advisory, a plan exemption
  names a slug. What was duplicated was never the shape; it was the policy.

  `check_deps_audit.py` also stopped hand-rolling `rules/` vs `.claude/rules/` and asks
  `squad.paths.rules_dir`, whose own docstring records nine sites resolving that pair by
  hand — six in one order, three in the other — so a table edited in one place was
  invisible to half its readers. This would have been the tenth.

### Fixed

- **The normative `ROADMAP.md` block in `cycle-acceptance.md` was one no parser accepted.**
  Copying the rule's own example produced a milestone that could never be accepted.
  Measured on that example, verbatim:

  ```
  extract_acceptance_criteria  ->  NOT_VALIDATED, "no `- [ ]` bullets"
  select_next_milestone        ->  {"dod": [], "depends_on": []}
  ```

  Two details were wrong. The DoD bullets were shown without the `- [ ]` checkbox every
  parser requires and every fixture in the repository has. And the dependency line was
  shown as `**Depends on:**` while the parsers read `**Dependencies:**`.

  The two are corrected differently, on purpose. The bullet shape is the parsers' — they
  are what runs, and the rule now matches them, the same way `code-quality-allowlist.txt`
  was corrected when its header documented a four-field shape `load_allowlist` never
  accepted. The dependency spelling is read BOTH ways, because that mismatch failed in
  **silence**: a bullet mismatch exits 1 and names what is missing, while `depends_on: []`
  is indistinguishable from a milestone that declared no prerequisite. A milestone whose
  dependency was never delivered read as one with no dependency at all.

- **`[-]` meant CANCELLED in one script and nothing in the other two.** `select_next_milestone`
  alone had the character in its class and alone acted on it. To `extract` and to the flip
  script a cancelled milestone was not cancelled — it was absent: `Milestones present: (none)`
  over a file holding one, and `WARN … not found — skipping flip`. A state one reader can
  spell and two cannot is worse than a state nobody supports, because the two that cannot
  each invent their own story about the silence. All three read it now and each refuses it
  by name.

- **A flip that did not happen exited 0.** A milestone whose header sits at `##` instead of
  `###` printed `WARN roadmap-checkbox: M1 not found — skipping flip` and returned success,
  so a caller running `flip || exit 1` was told the milestone closed while the checkbox
  stayed `[ ]`. The rule DOCUMENTED that silence — *"never closes, and never says why"* —
  and left it standing. It exits 1 now and names the header shape it expected.

- **`ACCEPTED` over evidence that does not exist.** The phase-contract table gates the
  `record` phase on *"evidence files exist at the cited paths"*, and the skill repeats
  *"the paths must resolve"*. The check asked whether the list held a non-empty string:

  ```
  evidence=[""]          ->  NOT_VALIDATED
  evidence=["   "]       ->  NOT_VALIDATED
  evidence=["e/x.png"]   ->  ACCEPTED        <- no such file
  ```

  This is the gate the rule says the whole cycle rests on — *"with the human sign-off
  deliberately out of scope, recorded evidence is the only thing standing between a real
  validation and a confident sentence"* — and it was satisfied by typing a plausible
  filename. Paths now resolve against the evidence record's own directory
  (`--evidence-root` overrides), and a **zero-byte file counts as unresolved**: a failed
  screen capture leaves one, and it reads downstream as a successful capture. An evidence
  root that is not a directory is `NOT_VALIDATED`, never an unchecked pass.

- **The flip script had never heard the word `verdict`.** `grep -c verdict` returned 0,
  while `cycle-acceptance.md § Hard gates` has required a green one since the flip moved
  there — carried as an open regression note since 2026-08-31, when the skill that used to
  catch a wrong flip after the fact was cut. Nothing between "the script computed
  `NOT_VALIDATED`" and "the checkbox is now `[x]`" would have objected. `--verdict` is now
  required and checked against `ACCEPTED` / `ACCEPTED_WITH_CAVEATS`.

- **The cycle's verdict had no mechanical consumer, and the rule said it had one.**
  *"a verdict that `cycle-maintenance` consumes"* — `advance_items.py` selects on
  `event.get("verdict") == "RELEASED"`, and no `.py` outside this slice reads `ACCEPTED`.
  The verdict was computed, written to a record, and read by nobody. Passing it into the
  flip gives it exactly one consumer, and § Purpose now says which one rather than naming
  a cycle that never looked.

### Changed

- **One reading of `ROADMAP.md`.** `cycle-acceptance.md` claimed *"Three scripts parse it
  and all three agree"*; the table under that sentence listed two, and the three disagreed
  about the checkbox — the field the whole cycle turns on. `squad/roadmap.py` owns the
  header, the DoD block and the dependency line now, alongside `squad/semver.py` and
  `squad/rubric.py`, and a test refuses a fourth private regex.

- **`records/` → `.squad/records/` in `cycle-acceptance.md`.** `records-location.md`
  declares one write root and the skill already used it; the rule named the legacy path in
  four places. Same class of defect as the install message corrected in the previous entry
  — a document pointing a reader at a directory nothing writes.


### Fixed

- **The release cycle could not read the releases it had itself cut.** `cycle-release.md`
  makes `--pre` the default because *"most cuts are pre-releases"*, and the first step of
  the chain matched `^v?(\d+)\.(\d+)\.(\d+)$` — no pre-release at all. Measured on a
  repository holding `v0.2.0`, `v0.3.0-rc.1`, `v0.3.0-rc.2`:

  ```
  detect_current_version  ->  0.2.0        "note: 2 tag(s) not semver, skipped"
  compute --mode pre      ->  0.3.0-rc.1   ← a tag that already exists
  ```

  The rc series never reached `rc.3`; every cut collided with `rc.1` and fell into the
  "tag already exists" stop condition. Worse, a repository whose ONLY tags were rc was
  refused outright as having "no semver tag" — and `test_detect_current_version.py`
  PINNED that refusal, so the defect had a test protecting it. The tag it used to build
  its "unreadable" case is now `-beta.1`, which is what that refusal was always about.

  The note also lied: `0.3.0-rc.1` **is** semver. It is simply not a version this kit
  cuts, and saying "not semver" sent people looking for a typo in a tag spelled
  correctly. (#R-1, #R-5)

- **Every pre-release published an empty body.** The rule says *"an rc reads
  `[Unreleased]` for its release notes and leaves it in place"*. Nothing implemented the
  first half: the chain rendered notes by version, and on an rc no such section exists
  because `promote_unreleased.py` has not run and must not. Measured:

  ```
  $ render_release_notes.py --version 0.3.0-rc.1
  version section [0.3.0-rc.1] not found in CHANGELOG.md
  exit=1   RELEASE_NOTES=[]
  ```

  stderr, not stdout — so `RELEASE_NOTES=$(...)` captured the empty string and the shell
  carried on. The PR and the GitHub release both opened with nothing in them, silently,
  in the one place a reader goes to find out what shipped. An rc now falls back to
  `[Unreleased]` and SAYS it did, because those notes are a snapshot of a section that
  keeps growing. A final with no section still fails loudly: falling back there would
  publish the right text under a version whose record was never written. An empty body
  is refused rather than printed. (#R-3)

- **The tag-cut gate could not be passed by a correct release.** The phase-contract table
  demanded `git tag --verify` resolve; Step 7 cuts the tag with `git tag -a`. `--verify`
  checks a GPG **signature**:

  ```
  $ git tag -a v1.0.0 -m "release" && git tag --verify v1.0.0
  error: no signature found
  exit=1
  ```

  Beside it sat a second clause — *"Tag must be annotated … pushed only after merge to
  `main`"* — carried as declared debt since 2026-09-01 with the note that "nothing
  inspects the tag object's type or the branch it was cut from". Two unmechanised
  clauses about one object, and the contradiction between them survived precisely
  because no code ever had to hold both. `mechanisms/gates/check_tag_integrity.py` now
  asks the question that is worth asking — annotated (`git cat-file -t`), and contained
  in the trunk (`git merge-base --is-ancestor`, not a branch-name match) — and the skill
  runs it in Step 7 BEFORE the push, while a wrong tag is still local. Signature is
  deliberately not checked. An absent tag exits 2. (#R-2, #R-4)

- **A gate accused a compliant file of having no docstring.** `check_semantic_names.py`
  matched a triple quote only at the start of a line, so a docstring carrying a string
  prefix — `r"""`, the form any module explaining itself with a regex needs — read as no
  docstring at all. It reported an 18-line one as `purpose_not_stated`. Found when it
  fired on a file written in this same change. A gate that accuses a compliant file
  teaches its readers to ignore it.

  The kit already knew the answer in another file: `tests/test_every_gate_is_reachable.py`
  carries `_PY_TRIPLE`, whose comment reads *"Match a Python triple-quoted string in its
  four flavours … optional string prefix"*. The gate and the test each solved the same
  parsing problem, independently, and only one of them got it right — which is the case
  for one reader that this release keeps finding. (#R-7)

- **The install reported migrating a routing table to a path it had not written.**
  B-198 moved the write to whatever `squad.paths` resolves and left the message naming
  the old `rules/domain-routing.txt`. A reader who went to check found the placeholder
  the install recreates there, read "(no domain yet)", and concluded their table was
  lost — which is exactly what `tests/test_clean_install.py` concluded, failing for the
  same reason on a migration that was working. The path is now printed from the value it
  was written to.

### Changed

- **One reading of a version, for the whole release slice.** Three scripts parsed semver
  three ways — no pre-release, `-rc.N` only, any pre-release — and the disagreement
  landed on the default path. `squad/semver.py` now owns it, alongside `squad/rubric.py`
  and `squad/backlog.py`, and a test refuses a fourth regex appearing in the slice.

  It also mechanises a rule that was only ever prose: `promote_unreleased.py` refuses to
  run under a pre-release. *"The CHANGELOG moves once, at the final"* has been written
  in `cycle-release.md` from the start, and the loosest of the three patterns accepted
  any pre-release suffix — so emptying `[Unreleased]` at `-rc.1`, which leaves `-rc.2`
  and the final nothing to publish, was one flag away and nothing stopped it.

- **The bump-derivation rule is stated once.** It was written twice in `cycle-release.md`,
  the second time as an orphaned line outside the list with different wording from the
  script it describes. Same outcome today; it is the shape that diverges later. What
  replaced it is the fact the prose was missing — that `Added` is consulted before
  `Changed`, so a section carrying both derives `minor` from the first rule that matches
  rather than from whichever clause a reader reaches first. (#R-6)


### Changed

- **This project's review panel runs three Anthropic seats, and says what that costs.**
  The kit imposes one composition rule — *"At least one counted vote must come from a
  recognised family outside the one the kit itself runs on. Three Claudes asked three
  times share their failure modes: a plausible fabrication that survives one tends to
  survive its siblings"* — enforced at intake by `check_panel_capability.py` ("three
  seats from one family. Fails everywhere, CI included") and at tally by
  `review_panel.tally()` ("APPROVED on a majority that spans two recognised families;
  RETURNED otherwise").

  This project has no non-Anthropic provider configured, so swapping the `judge-codex`
  seats for Anthropic ones without more would have stopped DISCOVER, PLAN and DESIGN
  outright: the capability gate failing at intake and every document returning at the
  tally. The honest options were two — run no panel, or run one and say what it is worth
  — and this is the second.

  `rules/review-panel.txt` now declares the waiver with its reason, on the layer the
  installer PRESERVES, because which models a project can reach is not the kit's
  business. The kit's rule and its argument are untouched for every other consumer.

  **Declared, never inferred.** A roster that happens to be one family and one that was
  meant to be read identically on disk, and only one of them is a decision — so the
  mechanisms read the keys rather than counting families and guessing. And the waiver is
  never silent: `check_panel_capability` appends `SINGLE FAMILY, BY DECLARATION` with the
  reason to its HOLDS line, and `Panel.outcome_note` carries the same into every outcome,
  so an APPROVED under the waiver reads as the weaker claim it is. Both keys come out the
  day a second provider is reachable.

  The third seat is `argus-pattern-analyst`, which reads many cases together and decides
  what is common to them — orthogonal by LENS rather than by family. That is less than
  the rule asks for, and more than nothing, and this entry says so rather than letting
  the roster imply otherwise. 4 tests.

  A fourth reader of the two-family rule turned up afterwards, in
  `skills/design/tests`, counting families directly and failing on the new roster. It
  reads the declaration now, like the other three. Found by `run_slice_tests.sh` — the
  slice suites are the only thing that runs it, and a check scoped to the changed area
  had not.


### Added

- **An impediment nobody here can clear now gets a number.** `blocked_by` is prose that
  MAY name ids, and the contract records what that measured: **seven of the eight items
  carrying it named a sponsor decision, a ratification, or a revocation in a hosting
  panel** — none of them an id. Accepting prose was right; a parser demanding `B-NNN`
  would have called seven honest impediments malformed. What it cost is in
  `parse_blocked_by`'s own words: *"nothing in this repository can tell you whether a
  sponsor has decided."* Such an impediment resolves only when somebody remembers to
  delete the line, is invisible to G6 and G7 because there is no edge to verify, and
  appears in no report as a thing that is itself pending.

  `source: external-blocker` files the constraint as an ordinary `B-NNN`. `blocked_by:
  B-900` becomes a verifiable edge, and closing the stub frees every item naming it
  **with no second edit** — the property prose could never have, and the one the
  impediment model was built around.

  Three things differ from an ordinary item and nothing else does: no `suggested_mode`
  (it never reaches DISCOVER), no `traces_to` (it is not work, so it serves no
  objective), and `select_backlog_item.py` never hands it out — asking for it by name
  returns `ITEM_EXTERNALLY_BLOCKED`, in the same band as `ITEM_IN_FLIGHT` and for the
  same reason: the work stands, the queue moves on, and the impediment is real rather
  than a defect in the item.

  Four of the seven tests passed before a line of this was written, which is the
  argument for the shape: the edge, the resolution with no second edit, and the report
  all fell out of machinery the registry already had. What was missing was permission to
  give the constraint an id.

  Imported from a cross-read of
  [`gringolito/github-backlog-management`](https://github.com/gringolito/github-backlog-management-skill)
  (2026-09-20), whose `/add-external-blocker` files the constraint as a stub issue — on
  the board, never milestoned, skipped by execution — and registers it as a real
  dependency. The mechanism here is ours, because the registry is a file rather than the
  GitHub API. 7 tests.


### Added

- **BRAINSTORM has eval batteries, which is where its two most expensive gates were
  measured by nothing.** `score_product_alignment.py` can see that `## Who it is for`
  holds 80 characters; it cannot see that those characters say `developers`, which is a
  category and settles no trade-off. The rubric says so on every run — three things it
  does not score — and until now nothing else looked either, while four other skills
  (`backlog-item`, `discover-plan`, `discover-edge-cases`, `discover-execute`) had
  batteries and the one cycle a person attends had none.

  `skills/brainstorm-vision/evals/evals.json` (5 cases) exercises the conversational half
  of G-B1: a category offered as the named user, a problem stated as the absence of the
  solution, and a session trying to close with no non-goal. Two are negative — a single
  feature, and an aligned scope asking for a re-cascade — because a FALSE trigger here
  costs a human session, the most expensive thing this kit spends.

  `skills/brainstorm-pieces/evals/evals.json` (4 cases) covers what a script cannot reach
  even now that the gate refuses a forged signature: being ASKED to tick the reviewer's
  boxes, reporting a copied template as unwritten rather than as low-scoring, what is
  legitimately available while the gate is closed, and refusing to file backlog items from
  a cycle that has no write access to the registry.

  `run_eval.py` measures only whether the skill triggered; the `assertions` are the
  judgement a human or a judge makes on the transcript. That split is stated in both
  batteries rather than implied, because a coverage claim resting on something nothing
  runs is the defect `tests/test_eval_batteries_are_runnable.py` was written to close.

### Changed

- **Three imports from a cross-read of `obra/superpowers` `skills/brainstorming`
  (2026-09-20).** Its gate is prose where ours is an exit code, and its tests cover the
  visual companion's server and whether the skill triggers — not the gate. But it holds
  three things this kit had left implicit.

  **A reply approves the artifact it was shown, and no other**
  (`alignment-threshold.md`). The kit had the signature and not the rule, which leaves
  the most common way past a human gate unaddressed: not forging a signature, but
  CARRYING one forward from a conversation about a different document. Approval is now
  per artifact, an enthusiastic yes is not a wider yes, work resumes at the earliest
  unapproved artifact rather than the furthest one the conversation reached, and editing
  a signed document withdraws the signature it carried.

  **What a block forbids, and what it does not** (`rules/blocking-verdicts.txt`, applied
  in `cycle-brainstorm.md`). A blocking verdict stops the item from ADVANCING; it does
  not stop the agent from reading. Written down because the two readings fail in opposite
  directions — an agent treating the block as total sits idle until a person who may be
  days away returns, and one treating it as advisory starts the chain the signature
  exists to hold. Upstream states the permission rather than only the prohibition:
  *"Read-only project exploration is allowed while those prerequisites remain
  incomplete."*

  **Red flags written in the voice of the rationalisation** (`cycle-brainstorm.md`). The
  anti-patterns name the error; the table names the thought that produces it, which is
  what the reader is holding at the moment the gate is about to be skipped. Eight rows,
  this cycle's own — "94% — that's basically aligned", "they're busy, I'll sign and
  they'll confirm next week", "I'll add the non-goals once we know more".

  **Not imported, and why.** Upstream announces its spike/bounded/architectural
  classification so the human can override it. This kit DERIVES depth instead —
  `classify_alignment_depth.py`, and `cycle-plan.md` says "Derived, never chosen" after
  measuring 2,740 KB of briefs signed zero times. An announced classification a person
  can override is also one an agent can argue for, and the derivation exists precisely to
  remove that conversation. The half that does not collide — complexity discovered
  mid-task raises the path and never lowers it — is not imported either, because nothing
  here re-derives depth mid-item and saying so in prose without the mechanism is the
  contract-without-mechanism shape this kit refuses.


### Fixed

- **Two of the review phase's own mechanisms were invoked by nothing.** A sweep of
  `skills/`, `rules/`, `mechanisms/` and `hooks/` on 2026-09-21, excluding each script
  and its tests, found no caller for either:

  ```
  check_finding_continuity.py   173 lines · tested · in squad-map · invoked by: (nothing)
  check_record_scope.py         165 lines · tested · in squad-map · invoked by: (nothing)
  ```

  The first is the worse one, because its docstring says what it was for: *"`consolidate_findings.py`
  scores from OPEN findings. A re-review that deletes a finding, or lowers a BLOCKER to
  MEDIUM, therefore passes — and until now the only thing standing against either was a
  sentence in `skills/review/SKILL.md`, guarded by a test asserting `"delete" in text`. A
  grep over a contract is not a guard … **This is the mechanised half.**"* The mechanised
  half was written and never connected, so the guarantee stayed the prose it was meant to
  replace — for three weeks, a re-review could delete a BLOCKER and score from what
  remained.

  It enters `consolidate_findings.py` the way `check_upstream_gate` already does, at
  **HIGH** rather than BLOCKER: the checker refuses to rule on intent — *"an honest
  re-scope and a quiet deletion look identical on disk"* — and a BLOCKER would assert the
  judgement it declines to make. HIGH reaches the reader and, through
  `unregistered_high`, has to be named and owned before the review hands off.

  `check_record_scope` measured the other hole — 2 of 48 reviews declared a reviewed
  range, 3 of 16 audits a scope — and concluded *"the past is permanently unrecoverable,
  and the only honest move left is to stop the same hole opening again."* Wiring it as a
  finding about somebody else's old record would not have stopped anything; the report
  this phase writes now opens with a frontmatter declaring the item it covered, and the
  checker runs against that record. The gate verifying the artifact its own phase
  produced.

- **The report a person reads omitted the auditors it could not read.**
  `_read_findings_file` returns `None` for a malformed file and promises the caller
  "lists the file under `unreadable`, by name, **in the report and in the JSON**".
  Measured with three findings files, one carrying broken YAML:

  ```
  JSON:      unreadable: ['perf-auditor.yaml']
  report.md: "**Reviewers (spawned agents):** 2 (quiet-auditor, security-auditor)"
             grep -ci "unreadable|perf-auditor" -> 0
  ```

  `_render_markdown` even declared an `unreadable` parameter and the call site passed it;
  the body never rendered it. The JSON kept the promise, the markdown did not, and the
  markdown is the phase's declared Output — a count of two, alone, reads as the whole
  roster.

- **A BLOCKER whose evidence said `looked in None`.** `records_dir()` returns `None` when
  the directory is absent and `check_upstream_gate.py` interpolated the result straight
  into the sentence. It told nobody where it looked and conflated two facts: the audit is
  missing from a records directory that exists, and there is no records directory at all.
  The sibling BLOCKER in the same report writes the honest form — *"the gate was pointed
  at the wrong tree — it has NOT established that no audit is required"* — and this one
  does now.

  Checked and found correct, recorded because it nearly became a false finding: the
  decision that a `None` edge-case ratio does NOT reach `NEEDS_DEEPER` is deliberate and
  its promise is kept — the report header carries `**Edge-case coverage:** NOT MEASURED —
  the band below was not applied, so this verdict says nothing about edge-case coverage.`

- **The allowlist's own example was in the format the file warns against.**
  `code-quality-allowlist.txt` opens by recording the fix for #343 — *"this header used
  to document a FOUR-field format … that `load_allowlist` has never accepted … so
  following the documentation produced a WORSE outcome (FAIL_HARD, cap 49) than adding
  nothing at all"* — and closed, eight lines later, with a four-field example. Measured
  2026-09-21, uncommenting it: `malformed entry (expected 6 pipe-separated fields, got
  4)`, which is `allowlist_malformed_entry`: HARD, and it aborts allowlist processing for
  the whole run. #343 corrected the header and left the example, so the obvious way to
  write a first entry — copy the example — was the worst available move. A test now
  parses every example under the `# Example` marker.

- **The mandatory sunset window was checked by nothing.** Two documents call it
  mandatory — the golden rule's `| Sunset window | ≤ 90 days from entry creation date |`
  and the file's own "MUST be ≤ 90 days" — and `load_allowlist` validated the ISO shape
  and stopped. A sunset in 2029 was accepted: a permanent exemption with a date on it,
  which § anti-patterns names as *"allowlists growing stale forever"*. Measured against
  today rather than the creation date, which nothing on disk records — an approximation
  strictly tighter than the contract, since a sunset beyond today+90 could not have
  satisfied the rule on any creation date. A sunset already PAST still parses: the
  contract is that an expired entry is ignored at scoring time and REPORTED as expired,
  and refusing to parse it would hide the expiry instead of surfacing it.

- **A detector that ran and found nothing was indistinguishable from one that did not
  run.** Measured on a repository with a committed orphan function, `vulture` installed
  and D1 clean at its threshold:

  ```
  findings_by_detector: {'d3_orphan_export_skipped': …, 'd4_mutation': …,
                         'd2_symbol_fab': …, 'd5_architecture': …}
  skip_reasons: {}
  ```

  D1 — the detector the golden rule lists first — appeared in neither, nor in
  `languages_skipped`. `detectors_run` now names every detector per language, derived
  from `languages_audited` because the audit loop runs all five for every language it
  audits. Same defect this session fixed in `/implement`, where a SKIP meant two
  opposite things.

- **"D1 clean" was a claim with a number missing.** The golden rule defines D1 as *"No
  exported symbol unreachable from a caller or a test"*; `vulture` scores exactly that
  class — unused function, class, variable — at **60%** confidence, and the default
  `min_confidence` is **80**. Measured on one file: 0 findings at 80, 2 at 60, both real
  orphans. So the default D1 reports the 90% class (unused imports) and not the orphan
  symbol its own definition describes.

  The default is NOT changed. The golden rule argues for it directly — turning D1 up
  before the debt is paid *"is how a gate becomes something people work around"* — and
  `--write-baseline` exists for the day a project decides to. What changed is that every
  run reports `thresholds_applied`, so a clean D1 carries the number it was clean AT, and
  the D1 row now says which class the default covers. Counting the below-threshold
  findings would have meant running the detector twice for the same answer.

- **The thresholds rule documented a fallback that a test forbids.**
  `code-quality-thresholds.txt` pointed three times at
  `skills/code-quality/defaults/thresholds.txt` — *"Defaults shipped with the skill"*,
  *"When unset, the value falls back to …"*, *"Defaults remain in … for portability"*.
  The directory does not exist, and `test_no_dead_fallback_copies_of_the_project_config`
  requires that it does not, with the reasoning intact: *"**Nothing fell back.**
  `run_code_quality.py` reads `rules/code-quality-*.txt` and, when one is missing, prints
  an error and exits 2 … the copies served nothing and drifted anyway: 80 lines in
  `rules/`, 83 in `rules/templates/`, 37 here."* The copies were deleted on 2026-09-01
  and the rule went on describing them for three weeks. The defaults live in the detector
  constructors, and the file says so now.

- **The final gate of IMPLEMENT said "proceed" about a repository where `/implement` had
  not run.** `run_validation.py` consolidates twenty checks with `overall = "FAIL" if
  fails else ("PARTIAL" if skips else "PASS")`, and `PARTIAL` exits 0. Every SKIP counted
  the same, and SKIPs have two opposite natures. Measured 2026-09-21 on a tree holding a
  plan and no checkpoint:

  ```
  overall_status: PARTIAL   exit 0
  2 pass · 16 skip · 1 warn · 0 fail
  SKIP checkpoint_consistency: no progress checkpoint — implement may not have run
  SKIP wiring_triad:           no progress file found — implement may not have been invoked
  ```

  The check writes the suspicion in its own reason string and returns SKIP. A SKIP now
  declares its kind — `not_applicable` when the check has no subject here, which is
  honest, or `precondition_missing` when it has one and the thing it reads is absent —
  and the second is counted with the failures. The kit had argued exactly this twice
  before, in the comments of the two checks it fixed one at a time: *"FAIL, not SKIP. The
  plan FILE exists… As a SKIP it counted into `skips`, `overall` became PARTIAL, and
  PARTIAL exits 0, so IMPLEMENTATION_COMPLETE could be emitted with the TDD shape never
  verified."*

  A missing checkpoint counts only when a plan for the slug exists. Without one,
  `/implement` was never supposed to run and its absent checkpoint is the honest state of
  a pre-code tree — the first cut ignored that and turned `test_pre_code_phase_all_skip`
  red, which was the test saying so.

- **"Pre-code phase" was measured by the absence of a manifest, not of code.**
  `test_execution` SKIPs only for *"a repo with no language manifest at all (genuine
  pre-code phase)"*. Measured with `src/thing.py` committed and no `pyproject.toml`:

  ```
  SKIP test_execution: no language manifest at the repo root        PARTIAL, exit 0
  ```

  Adding a two-line `pyproject.toml` and touching no code:

  ```
  FAIL test_execution: manifest(s) for python present but no suite executed   exit 1
  ```

  What separated proceed from refuse was a metadata file. A repository with sources and
  no manifest is not in a pre-code phase — this kit describes itself as shipping *"loose
  scripts"* — so sources present with no runnable suite is a missing precondition, read
  from `git ls-files` rather than a walk, because an untracked scratch file is not the
  repository's code. It is reported as a precondition rather than as a FAIL: the honest
  next step is "declare the manifest this repo needs", not "your tests failed".

  The test that carried the old behaviour is named `test_pre_code_phase_all_skip` and its
  fixture holds `src/` — the name asserting a phase the fixture contradicts.

- **Pulling the blocked checks out of the skip list broke the census.** The first cut
  removed them from `skips`, which the summary counts, so two checks vanished from
  `pass + fail + skip + warn + partial + n_a == total` —
  `test_summary_buckets_account_for_every_check` caught it on the next run. The
  distinction belongs to the verdict, not to the census: every SKIP is counted, and the
  blocked ones are listed separately under `preconditions_missing` so a reader can tell a
  gate that failed from one that could not run at all.

  Writing that up reintroduced the very shape another gate exists to refuse:
  `test_no_procedure_concludes_a_project_phase_from_a_missing_file` caught the new
  paragraph concluding "pre-code phase" from an absent manifest — the defect whose
  docstring records that it *"landed in code and not in what invokes it … eight
  occurrences across four files, after the code was fixed"*. The rule says what was
  looked for and not found instead.

  Four checks verified by sampling before any of this was changed, all of them sound:
  `check_wiring` (orphan symbol → HALT on pillar a), `check_tdd_shape` (prose-only TDD →
  BLOCKED), `check_test_obligations` (plan promises failure scenarios, tree has none →
  FAIL), `test_execution` with a manifest and no suite → FAIL. IMPLEMENT is the most
  mechanised phase in the kit; these three findings are the edges its own two earlier
  fixes did not reach.

- **Four skills used `$ECO` as a path prefix and assigned it nowhere, and the test
  written for the first one could only ever see the first one.** An empty expansion makes
  the command an absolute path from the filesystem root, so the step silently does not
  run:

  ```
  $ python3 "$ECO/skills/plan-alignment/scripts/classify_alignment_depth.py" . B-001
  python3: can't open file '/skills/plan-alignment/scripts/classify_alignment_depth.py'
  ```

  That one matters most: `cycle-plan.md` describes `classify_alignment_depth.py` as
  **"Derived, never chosen"**, and with it unrunnable the depth is chosen — with the
  document's own default being FULL, the outcome the script exists to prevent after a
  consumer produced 2,740 KB of alignment briefs signed zero times. `release` and
  `issue-confidence` carried the same defect.

  `test_every_shell_variable_the_skill_uses_is_one_it_assigned` was written for this on
  2026-09-20 and lived in `skills/design/tests/`, reading one SKILL.md. It has moved to
  `tests/test_a_skill_assigns_the_variables_it_uses.py`, which reads all forty — the only
  scope that could have caught the other three. A test scoped to one slice catches the
  defect in one slice.

- **`plan-write` told the reader to close the phase before opening it.** The `end` block
  sat on line 145 and the `start` block on line 161, under the instruction *"Emit the
  START of this phase before doing the work"* — by which point the work was done. A
  SKILL.md is executed in the order it is read, so the outcome is either an `end` before
  its `start` in the stream, which `check_phase_drift` reads as disorder, or no start at
  all. Swept across every SKILL.md: one file had them in that order and seven had them
  the right way round. A test keeps it that way.

- **The gate auditor reported 42 phase rows as naming no enforcer, and most of them
  named it by id.** A phase-contract table is a summary — one line per phase — and the
  gate itself is declared below with an id and a mechanism. `cycle-brainstorm.md` is the
  clearest case: G-B1 to G-B5 each name `score_product_alignment.py`, and the five rows
  above cite `(G-B1)` … `(G-B4, G-B5)`. The auditor did not follow the reference, so
  seven honest rows were reported as unenforced.

  Burying the rows that really have no mechanism among rows that do is also what made
  `--strict-phase-rows` unusable: a flag that fails the build on 42 findings, most of
  them false, is a flag nobody turns on. `check_gate_mechanisms.py` now resolves an id
  the same rule declares — and refuses to launder one, so a row citing an id nobody
  declared, or a gate that is itself unmechanised, is still reported.

  42 → 35 from the resolution, → **31** after `cycle-plan.md`'s own four rows were fixed:
  `check_coverage_matrix.py` and `check_deps_audit.py` now name the runner that composes
  them, `plan-confidence` names what derives its verdict, and `plan-edge-cases` carries
  the exemption it always needed — *judgement*, because whether an owner is the right
  owner and whether a criterion closes the edge case is the call G3, G4 and G5 are left
  conversational for. A regex would pass `owner: TBD, criterion: it works`, which is
  worse than no check: it reads as enforced.

  The 31 that remain are in eight other cycle rules and are declared debt, reported by a
  gate that exits 0 until somebody passes `--strict-phase-rows`.

- **Two `apply_fixes.py`, 328 lines of code apart.** `plan-improve` fixes weak
  imperatives, loopholes and missing TDD blocks in a PLAN; `discover-improve` fixes prose
  smells inside an opportunity's `## Recommendation`. Comparing the syntax trees without
  docstrings: 223 lines against 151, and 328 differing — the same name for two programs,
  which is the collision `run_slice_tests.sh` isolates processes to survive. Now
  `apply_plan_fixes.py` and `apply_opportunity_fixes.py`, named for what each one fixes.

- **G-M named a checker that only read the word `bug`.** `cycle-discover.md` is
  categorical — *"`bug` has a hard floor: no failing test, no bug"* — and G-M promised to
  block *"the mode's mandatory evidence is incomplete, most often `bug` without a failing
  test"*. `check_opportunity_completeness.py` verified that the line `**Mode:**` existed
  and carried one of four tokens. Measured 2026-09-21 on an opportunity declaring
  `**Mode:** bug` whose Corner 1 says, in words, *"No test written yet — the shape is
  obvious enough from the repro"*: `opportunity_completeness: 100.0`, `weighted_avg:
  100.0`, no mode cap.

  The floor is declared structurally now — `**Failing test:** path/to/test.py::test_name`
  — and the gate asks two questions it can answer: is the line there, and does the file
  resolve. A regex hunting for "the test fails" in prose would produce verdicts about
  language, which is precisely why G3, G4 and G5 are left conversational. Whether the
  test genuinely fails is what `/discover-execute` runs and what the panel judges.

- **The BLOCKED marker's defect lived in three files and was fixed in one.** The
  proximity window was ~80 characters and crossed newlines, so a marker on one list item
  absolved the item above it. That was corrected in `check_evidence_pointers` and the
  same rule sat untouched in `check_measurement_targets` (a character-for-character copy
  of the helper) and `apply_fixes` (the window, inlined). Measured on the untouched one:

  ```
  `src/real/thing.ts` alone                        -> verified=1
  the same, with a BLOCKED item on the next line   -> verified=0, blocked=2
  ```

  `squad/blocked_marker.py` owns the convention — the pattern and the rule that a marker
  excuses what is on its own line — and a test refuses a second definition. Three
  readers of one convention is three places for it to drift, and this one had already
  drifted by being fixed once.

- **DISCOVER opened its phase at step 4 of 6.** Only `/discover-execute` emitted events,
  so the lead time measured the execution of the measurement and not the three phases
  that produce and approve the measurement plan — and a chain stalling at
  `/discover-plan-confidence`, whose INVALID returns to `/discover-plan`, had no open
  start at all and showed as work nobody had begun. `/discover-plan` opens the phase now
  and `/discover-execute` closes it with the verdict; the fast lane still emits its own
  start, because there `/discover-plan` never ran.

- **"Sweeping without registering" was an anti-pattern with no gate, and the kit had
  already measured that.** `grep BACKLOG` across every DISCOVER scorer returned nothing;
  `phase_coverage.py` walks only the other direction and says so in its own source —
  *"two entry paths and only one writes an opportunity file"*. Gate G-R resolves
  `**Item:** B-NNN` against the registry through `squad.backlog.BLOCK_RE`, so a finding
  that never reached `BACKLOG.md` is capped rather than scored. With no registry at the
  project root it reports NOT CHECKED, because `None` is not an empty set and calling
  every opportunity an orphan would assert a violation the evidence does not support.

  The kit knew. `skills/discover-confidence/fixtures/good-opportunity.md` — shipped as
  the EXAMPLE of a good opportunity — is an opportunity about this exact gap, ending
  *"The gate that the anti-pattern implies does not exist."* Measured, written up, used
  to teach, never closed. The fixture now records that the gap it measured is closed,
  because a fixture describing a live defect teaches a reader that the defect is live.

  Two of the kit's own gates caught this change while it was being written:
  `check_gate_mechanisms` refused G-R for naming a checker with no entry point without
  naming the runner that composes it, and `check_xrefs` refused a citation of
  `good-opportunity.md` that read as if the file were under `rules/`.

- **The evidence gate scored 100 for evidence nobody could verify, and a BLOCKED marker
  absolved the pointer above it.** G-E is the cycle's cardinal gate —
  `cycle-discover.md` calls fabricated evidence *"the one unrecoverable defect in this
  cycle: everything downstream trusts it"* — and it promised to block *"a URL never
  actually fetched, a trace id never observed"*. Measured 2026-09-21 against an
  opportunity whose entire Corner 1 was three HTTP calls nobody made:

  ```
  evidence_pointers_score: 100.0
  weighted_avg:            100.0
  hard_caps_triggered:     []
  ```

  `check_evidence_pointers` is honest about why — an HTTP observation is not
  re-verifiable on disk, so no code pointer could have failed — but `100.0` in a
  dimension named `evidence_pointers` reads as "every pointer resolved". The dimension
  now reports itself **unmeasured** and drops out of the weighted average, which is
  what `active_dimensions` and `weight_normalization_factor` were shaped for: both were
  hardcoded, the list naming all four unconditionally and the factor the literal `1.0`,
  so a reader could not tell a full score from a partial one. G-E now states what it
  cannot check instead of promising it, and names the panel as what judges a recorded
  observation.

  The `<!-- BLOCKED: … -->` marker had a worse defect than the one first reported. Its
  proximity window was ~80 characters and it crossed newlines, so a marker on one list
  item absolved the item ABOVE it:

  ```
  src/real/thing.ts:3  alone                            -> verified=1
  the same, with a BLOCKED item on the next line        -> verified=0, blocked=2
  the same, with 100 chars of prose between them        -> verified=1, blocked=1
  ```

  A Corner 1 is written as a list, so this fired on the ordinary shape — one declared
  gap erased the verified pointer above it, and an unmarked fabrication beside a marked
  one was absolved by its neighbour. The marker now has to sit on the pointer's own
  line, and a blocked pointer counts in the denominator: a declared gap is not a
  fabrication (no cardinal cap) and not a verification either (it costs proportion).
  Without that, an author cleared their own unresolvable pointers with a comment —
  1 real + 4 marked scored 100.0.

- **`check_spec_smells.py` existed three times, and the three were the same file.**
  `plan-confidence`, `discover-confidence` and `discover-plan-confidence` each carried
  one, and each said so: *"Copy of plan-confidence/scripts/check_spec_smells.py — same
  algorithm"*. Measured by comparing the three syntax trees with docstrings and comments
  stripped: **89 lines of code, 4 of them different, and all four were the name of one
  parameter** (`plan_path` against `artifact_path`). A smell fixed in one scorer left
  the other two detecting the old shape, silently. `squad/spec_smells.py` is the
  implementation; the three are documented re-exports, exactly what `_rubric_loader.py`
  became when it turned into `squad/rubric.py`. What stays local is the rubric each
  skill reads — the categories and penalties are the skill's, only the scan is shared.

- **One name for two different questions.** `check_corner_coverage.py` existed in
  `discover-confidence`, where it asks whether the four corners of a finished
  opportunity are POPULATED, and in `discover-plan-confidence`, where it asks whether
  each corner is COVERED by a Measurement Question or excused by a `DEFER-CORNER`
  marker — 80 of ~50 lines of code different. That is the collision `run_slice_tests.sh`
  isolates processes to survive, and the G-C row named only one of the two. Now
  `check_corners_populated.py` and `check_corners_questioned.py`, with the gate table
  naming both and `conftest.py`'s worked example pointing at `apply_fixes.py`, a
  collision that still exists.

  Renaming broke a pointer in the kit's own `good-opportunity.md` fixture, and G-E
  caught it on the next run — `fabricated_evidence`, one citation, exact line. Then the
  paragraph recording the rename named the retired file, and
  `test_rules_cite_mechanisms_that_exist` refused it: *"a rule is read as instruction —
  naming a gate that does not exist tells the reader the constraint is enforced and stops
  them looking."* The retired name lives here instead, which is where a name that no
  longer resolves belongs. Two gates catching their own author inside one change is the
  most useful thing that happened in it.

- **Six readers of `BACKLOG.md`, two ideas of what an item block is — and the item that
  fell in the gap corrupted its neighbour.** Measured 2026-09-20 on `## B-003 - Title`,
  written with a plain hyphen instead of the schema's em dash:

  ```
  check_backlog_structure.BLOCK_RE   (the canonical one)   did NOT see it
  backlog_status.BLOCK_HEADER_RE     (the WRITER)          did NOT see it
  detect_domains, phase_coverage                           did NOT see it
  build_approval_brief.ITEM_HEAD_RE                        saw it
  check_objective_coverage.ITEM_RE                         saw it
  apply_delegated_decisions.ITEM_RE                        saw it
  ```

  So an item could enter the approval brief, be ticked and signed, and be invisible to
  the only module allowed to write its status. And because a header no parser recognises
  does not OPEN a block, the unseen item's fields were read as the PREVIOUS item's.
  Measured with two items, the second written with a hyphen:

  ```
  Items   : 1                                  ← there are two
  [BLOCKER] B-001 duplicate_field: `status` is declared 2 times
  [BLOCKER] B-001 self_block: `B-001` names itself in `blocked_by`
  [BLOCKER] B-001 blocker_cycle: B-001 -> B-001
  ```

  Three blockers, all false, all on the wrong item, and one real item gone from the
  count. `check_intake_gates.py` had already reasoned this out and imports the parser
  rather than writing one — *"A second regex here would diverge silently, and the two
  would disagree about what the registry contains"* — and five other readers had not.
  `squad/backlog.py` owns it now: the header (all three separators), the id patterns,
  the block spans and the split. The contract states the header shape, which it never
  did.

- **An id of one or two digits was half-valid.** `## B-15` parses as a block, and
  `ITEM_ID_RE` and the mention pattern both want three digits — so the item exists, the
  writer refuses it on the command line, and `blocked_by: B-15` names no edge. The
  parser deliberately still matches it (a skipped header takes the next item's fields
  with it) and `malformed_id` now reports it, saying the fix is zero-padding rather than
  renumbering.

- **A commitment nobody was attached to.** `rules/cycle-backlog.md` requires
  `approved_by` from `approved` onward and calls a bare `approved` *"not evidence that a
  person decided"*. Nothing asked for it: `backlog_status.py … --to approved` returned
  `OK` and wrote a block with no attribution, `check_backlog_structure.py` reported
  nothing, and `rules/cycle-maintenance.md` prescribed that very command without the
  flag. The writer now refuses the move, the structure check reports
  `approval_unattributed`, and the documented command carries `--approved-by`.

- **`traces_to` was required by the contract and by nothing else.** *"Required once
  `.squad/wiki/product/objectives.md` exists"* — and with an objectives document present
  and an item carrying no link, the structure check said nothing.
  `check_objective_coverage.py` does measure it, correctly, but it is a report run beside
  the approval brief rather than a gate on the path that writes. `objective_link_missing`
  now fires, and only where objectives exist: a project that never ran
  `/brainstorm-objectives` has nothing to trace to, and calling every item an orphan
  against a standard it never adopted is the failure that same script refuses by name.

- **A refusal that named the wrong cause.** `REFUSED: B-14 is not in this backlog` was
  printed about a block sitting in the file, whose header the writer's parser did not
  recognise — sending the reader to look for a missing item that was right there. One
  parser removes the case; the message now distinguishes an absent item from a heading
  that does not parse, and says what the shape is.

  18 tests.

- **A commit touching two areas could not say so.** `fix(gates,boundary):` and
  `fix(board,gates):` were refused as `header_shape` — not for the scope's content but
  for the comma, which the header pattern had no room for. That left three bad options
  for a change that genuinely spans two areas: name one and be incomplete, invent a
  portmanteau nobody greps for, or drop the scope, and all three lose what the field
  exists to carry. A scope may now name several areas, comma-separated with no space.
  Each segment is still lowercase kebab-case, so the rule about a scope did not loosen —
  there may be more than one of them — and a declared `commit_scopes` list is checked
  segment by segment, because comparing the whole string would have passed
  `gates,ghost` while refusing `ghost`.

  With `change` declared in `rules/contribution-overrides.txt` alongside it — for a
  commit that alters an existing contract without fixing a defect and without adding a
  capability — `verify_ecosystem` returns 0 for the first time in this branch, and the
  kit stops failing the gate it ships. 8 tests.

- **The DESIGN gate agreed a design the agent had signed, and refused the one a person
  signed.** Both measured 2026-09-20 against a complete, covered set of five drawings:

  ```
  <!-- signed-by: daedalus-tech-lead -->                 DESIGN_AGREED    exit 0
  <!-- signed-by: human/paulo (approved in session) -->  AWAITING_REVIEW
  ```

  `verdict_of` refused the single prefix `judge/`, which is a denylist of one against an
  open set of names, so the tech lead who draws the diagrams could agree them; and the
  local `([^\s>]+)` pattern stopped at the first space, so a signature carrying its route
  captured nothing at all. `cycle-design.md` says of this gate: *"a person, and only a
  person"*. A gate that accepts the author and rejects the reviewer is worse than no
  gate — it returns the wrong answer confidently. A checklist whose boxes were DELETED
  also passed, because nothing counted TICKED boxes.

  The root cause was three copies: `score_alignment.py`, `score_product_alignment.py` and
  `check_design_completeness.py` each compiled their own `signed-by` pattern and each
  decided for itself what the captured name meant. `squad/signoff.py` is now the one
  reader — pattern, both checkbox counts, and `is_human` as an allowlist — and
  `tests/test_one_signature_reader_for_every_gate.py` refuses a second. The POLICY stays
  per gate, because it genuinely differs: a judge may sign an ITEM's brief and may not
  sign a product vision or a system design.

- **`DESIGN_AGREED` was unreachable by the documented path, and the panel gate it
  declares was never run.** Three defects meeting in one phase:

  * **Nothing wrote `design/sign-off.md`.** The gate reads it, the SOP says to sign it,
    and `/sign` refuses what does not exist — *"is neither a path that exists nor a slug
    of any document waiting for a signature. Nothing was signed."* `brainstorm-pieces`
    generates its equivalent from a template at step 3; this phase had neither step nor
    template. Both now exist.
  * **`$ECO` was used by two steps and assigned by none.** Step 5 and Step 5b expanded to
    `/skills/...` and `/mechanisms/...` — absolute paths from the filesystem root. The two
    commands that did not run were "score the drawings" and "convene the panel". Step 0
    now assigns it, and a test refuses a shell variable the file never set.
  * **G-D8 was declared and never invoked.** The gate table names
    `check_panel_approval.py`; nothing in SKILL.md, SOP.md or the verdict asked it, and
    `DESIGN_AGREED` was measured against a project with no panel record at all. The gate
    itself is sound — exit 2 with no roster, exit 1 on `NO_RECORD` — it was simply never
    called. Step 5b now reads its verdict, and the SOP has the step it was missing.

- **A drawing that could not be READ was reported as ABSENT, and a piece was covered by a
  longer id that contained it.** `_read` swallowed `OSError` into `""`, so a
  present-but-unreadable file came back `MISSING` and `INVALID` — "draw it", about a file
  the person already has; `FileNotFoundError` still returns `""`, because absent and shut
  are different facts and only the second one was missing a name. And coverage tested
  `piece_id not in map_body`, a substring: measured with eleven pieces and a map naming
  only PIECE-10 and PIECE-11, the report read **"11 declared, 3 covered"** — `PIECE-1`
  passed inside `PIECE-10`. It fails only in the permissive direction and it fires on any
  product with ten or more pieces. Also `\?\?\?` sat in the placeholder pattern behind a
  `\b` that can never match beside a `?`, the same defect the product scorer carried in
  the same expression.

- **`BACKLOG_INVALID` was declared and named no band, and that failed the install.**
  `rules/cycle-maintenance.md` declares it; `rules/verdict-bands.txt` did not classify it,
  so `check_verdict_bands` reported `DRIFTED`, `verify_ecosystem` failed, the post-install
  validation failed, `install.sh` exited 1 — and 43 tests across `test_clean_install`,
  `test_kit_manifest`, `test_permissions_retirement` and their siblings fell with it.
  Classified `structural`: SELECT returns nothing because every id it could return is
  ambiguous, and a `traces_to` pointing at an ambiguous id is the same broken pointer
  `INVALID` names one level down.

- **Every eval battery failed in the root suite and passed alone, and the batteries were
  not what failed.** `run_eval.py` reached its helper with `from scripts.utils import
  parse_skill_md`, which resolves through whatever `sys.modules["scripts"]` already holds
  — and nine slices ship a directory called `scripts`, eight of them with an
  `__init__.py`. Whichever one a wide pytest process imported first owned the name, and
  the import then died on `ModuleNotFoundError: No module named 'scripts.utils'` about a
  file sitting beside it. Measured 2026-09-20: 12 failures in `tests/` and 13 passes from
  `pytest tests/test_eval_batteries_are_runnable.py`. A test that passes alone and fails
  in company reports the import order rather than its subject — which is exactly the
  collision `run_slice_tests.sh` exists to keep out of the slices, arriving through the
  root suite instead. The helper is now loaded by path under a unique module name, so no
  other slice can take it.

- **The product-alignment gate passed a cascade nobody wrote and a signature no person
  gave.** Two measurements on 2026-09-20, both against `score_product_alignment.py`, the
  gate the entire unattended chain rests on.

  **The four shipped templates, copied into `wiki/product/` and not edited, scored
  100.0% — 34/34, every one of the seventeen criteria green.** G-B0 was written to stop
  `touch` from buying 35% and it asked whether a file held anything but headings; a
  template holds instructions, and an instruction is text. A 132-character guide comment
  satisfied "this section is complete", `metric:` found its required number in the words
  "Gate G-B2", the template's two bare `- ` bullets counted as two non-goals, and
  `serves: OBJ-<!-- … -->` was non-empty enough to count as a citation while matching no
  `OBJ-\d+` — so it was not dangling either, and a requirement walked through G-B3 by
  being unreadable. Guide comments are now stripped before anything is scored, a bullet
  must carry a non-goal, a citation must match the id pattern it claims to be, and a
  surviving `{{SCOPE}}` is its own hard cap (`unfilled_template`) rather than a low score
  — "revise this" is the wrong instruction for a document nobody has started. The same
  copy now returns `INVALID`, 29.4%.

  **A cascade signed `<!-- signed-by: iris-product-designer -->`, with the four
  checkboxes DELETED, returned `PRODUCT_ALIGNED`, exit 0** — the agent that writes these
  documents signing them under its own name. Two independent holes: `verdict()` refused
  the single prefix `judge/`, which is a denylist of one against an open set of names,
  and `TICKED_RE` was defined in the module and read nowhere, so a checklist with no
  boxes satisfied "nothing is unticked". The gate now requires ticked boxes, a signer,
  and `human/{who}` on every signature — the allowlist `score_alignment.py` has applied
  at item level all along, reporting the weakest signer so one human tick cannot launder
  an agent's. `SIGNED_BY_RE` also stopped at the first space, dropping the route from
  `human/paulo (approved in session)` (the defect the item-level scorer records having
  fixed in its own pattern) and capturing a signer called `" "` from the unsigned marker
  the template ships.

  Two more defects fell out of the same read. `_field` used `\s*` after the colon, which
  matches a newline: an empty `horizon:` reached across the blank line and returned the
  NEXT field's value, so a field with nothing in it was reported as carried. And
  `_gate_signature` was annotated `-> None` while returning the report.

  Templates, SOP, SKILL.md and `cycle-brainstorm.md` now state the signature format where
  the reviewer reads it — being refused for the format is a confusing way to learn it.
  13 tests.

- **Eight skills decided where the kit lives by testing a directory the installer
  deletes.** Thirteen call sites used `[ -d .claude/scripts ]`, and
  `mechanisms/distribution/install.sh` removes `.claude/scripts/` on every install — the
  migration to `mechanisms/<family>/` says so in its own echo. In any consumer installed
  since that rename the probe is false by construction, the branch falls through to `.`,
  and the command becomes `./mechanisms/cycle/cycle_events.py` — a path that exists only
  in the kit's own repository. The phase event was simply never written, and nothing said
  so: `cycle_events` is fail-open by design, and a missing event reads exactly like a
  phase that was skipped. Three of the four brainstorm skills carried the broken probe
  two lines below a correct `[ -d .claude/skills ]` for the scorer, in the same file.
  Invisible here, which is why it survived: in this repository neither directory exists
  and both branches resolve to `.`. 2 tests, parametrised over every SKILL.md.

- **`brainstorm` recorded four phase ends against one start, and `design` recorded an end
  against none.** `tests/test_a_phase_that_ends_also_began.py` holds the pair for the four
  programmatic emitters and defers skills to "its own prose test", which did not exist —
  and the stream it quotes (37 ends, 1 start) names `brainstorm` as the one open start.
  All four cascade skills then emitted `end --cycle brainstorm --slug {scope}` for a phase
  `rules/cycle-phases.txt` declares once, so WIP, lead time and "is a session running right
  now" were uncomputable for the only cycle a person attends. The cascade's middle phases
  hand off instead of closing; `/brainstorm-vision` opens the phase and `/brainstorm-pieces`
  closes it with the gate's verdict, and an abandoned cascade correctly leaves an open start.
  `design` gained the Step 0 it never had. 3 tests, parametrised over every cycle a
  skill emits for.

- **The TypeScript symbol detector reported every workspace package as a fabricated npm
  import.** `_find_workspace_package_names` collected member names with two fixed globs —
  `*/package.json` and `*/*/package.json` — while its own docstring claimed to walk "the
  declared workspace globs". It read no declaration. A consumer declaring `apps/*/packages/*`
  keeps its manifests at depth 4, so every import of them fell through to the npm registry and
  took a 404: **98 HARD findings, one message shape, none of them in the change being audited**.
  D2 carries the `symbol_fabrication_typescript` hard cap, so `/code-quality` returned
  `FAIL_HARD` for the whole language whatever the change did, and that blocks `/review`.

  The defect ran both ways. A `package.json` at depth 2 that NO pattern names was collected
  anyway, so a genuinely fabricated import from such a directory would never have been reported
  either.

  The collector now reads what the project DECLARES — `pnpm-workspace.yaml#packages`,
  `package.json#workspaces` as an array or as `{packages: [...]}`, `deno.json#workspace` — and
  filters one pruned walk by the declared pattern set. A repository declaring nothing keeps the
  previous behaviour, and that is the only path that does.

  Three things this required that are worth stating, because each is a trap measured rather
  than reasoned about:

  * **Neither `Path.glob` nor `fnmatch` can execute pnpm's dialect.** `Path.glob` raises an
    uncaught `ValueError` on the documented `!**/test/**` — a crashing detector, which halts
    the cycle — and descends `node_modules` on `**`. `fnmatch`'s `*` crosses `/`. Negation is a
    property of the SET, so no per-pattern loop expresses it. The matcher is ~20 lines here.
  * **`pathspec` implements the OTHER dialect.** It is gitignore's last-match-wins, under which
    two of pnpm's four documented rows re-include. Adopting it would have swapped a matcher
    that crashes for one that silently disagrees — and it is not a declared dependency.
  * **The root marker had to change with it.** pnpm 10 moved non-workspace settings into
    `pnpm-workspace.yaml`, so stopping the upward walk at the filename now finds a file that
    declares nothing. Reading the declaration is what makes the old marker unsound.

  A missing PyYAML is reported and falls back to the previous behaviour, never to "this
  workspace declares no members" — an absent parser must not read like a repository with no
  workspace.

  Extracted to `detectors/_workspace.py` alongside the existing `_arch`, `_wiring` and
  `_mutation` helpers, so `typescript.py` stays under its row budget without the reasoning
  being cut to fit.


- **The LOCAL alignment depth can now reach the floor it is scored against.**
  `classify_alignment_depth.py` returns `LOCAL` for a small item and names what it removes —
  "DROPPED: the prose sections and the walkthrough HTML" — while `score_alignment.py` graded all
  seventeen criteria, five of which measure exactly those sections. Measured on a real item
  (`B-001`, on a consumer): a LOCAL brief complete by its own contract scored 22/34 = 64.7%, and closing
  both remaining authoring gaps reaches 24/34 = 70.6% — **19.4 points below the 90% floor**. An
  author who followed the classifier wrote a brief that could not pass, and `check_alignment_gate.py`
  hard-caps an unaligned plan at 49 with no `--skip` and no dismissing ADR. The scorer now takes
  `--depth`, and a dropped criterion leaves the total as well as the score: scored out of the
  criteria in force, never out of a constant. The depth is a parameter derived from the ITEM and is
  never read from the brief — a document that declared its own depth would grade itself, which is the
  "reaching 90% by rewording" path `alignment-threshold.md` refuses.

### Added
- **A reader outside the kit can ask where a phase's artifact goes** (#147)
  `panel_brief.py --locate --phase <p> --slug <s>` prints the artifact path, whether it
  is there, and the contract that grades it — without convening anything and without
  failing on absence. `PHASE_SOURCES` already held that table and its comment already
  said why: *"a reviewer pointed at the wrong artifact returns an honest verdict about
  the wrong thing, which reads as coverage."* It happened anyway, to a reader that could
  not reach it. Measured 2026-09-18: `judge-codex` hard-codes
  `knowledge-base/discoveries/blueprints/<slug>-blueprint.md`, where this kit writes
  `.squad/records/discoveries/opportunities/<slug>-opportunity.md` — two stacked
  renames, `records-location.md` moving the root and `cycle-discover.md` renaming
  blueprint to opportunity. All four of its stages missed, every panel came back
  incomplete, and an incomplete panel is abstention and never agreement, so a full
  registry sat at `ITEM_IN_FLIGHT`. The plugin was not careless: there was nothing to
  call. `main` demands a slug and a phase, builds a whole brief, and REFUSES when the
  artifact is missing — so a caller whose question is *where does this file go* was
  answered with a refusal for not having found it, and hard-coding was the only move
  left. Locating and judging fail on different things and are now separate. A phase the
  table does not hold exits 2, this kit's word for could not measure, rather than
  composing a path from the pattern of the others: a convention invented on a caller's
  behalf is what went wrong the first time. Tracked as issue #2 in the plugin's own tracker.

### Changed
- **DISCOVER is optional, and the evidence it produces is not** (#161)
  `cycle-phases.txt` declared `discover | required` while `cycle-plan.md` said the
  opposite in its own pre-conditions — *"A feature has a defined goal and known prior
  art (otherwise, run DISCOVER first)"*. **Otherwise.** `cycle-discover.md` agreed with
  the second reading and always had: it triggers on `status: raw`, and an item already
  `triaged` is in its own do-NOT-trigger list. One word in the chain declaration was the
  outlier, and it was not decoration — `check_phase_drift --expect-complete` reports
  `phase_declared_never_ran` for a required phase that left no event, so every item that
  arrived already measured was filed as an incomplete run. It is `conditional` now, with
  a note naming when it is absent, as every other conditional phase carries.
  **What did not change is the part that protects anything.** The guard against planning
  on a hunch was never the phase declaration: it is `triaged_without_evidence`, a BLOCKER
  in `check_backlog_structure.py`, which asks for the EVIDENCE rather than for the
  ceremony that usually produces it. An item at `status: triaged` with `evidence:
  none-yet` is still refused, and the tests that assert the relaxation assert that
  refusal in the same file — a relaxation whose companion protection is not pinned is one
  nobody can audit later. Optional is not skipped-by-default: an unmeasured item is
  exactly what this cycle exists to pick up, and the selector still hands it out.
  `backlog` remains the one `required` phase, so the drift report still has something to
  measure — `phase_declared_never_ran` now fires for it alone.

### Fixed
- **Six hard gates named a mechanism the reader could not run** (#160)
  `check_gate_mechanisms.py` asks whether a gate line says what enforces it, and is
  explicit about the question it refuses — *"proving that a given `.py` implements a
  given English sentence is not something a text scan can do"*. Between that refusal and
  what it does check sat a question that IS decidable and was not asked: **can the named
  thing be run at all?** Measured 2026-09-19 across the nine cycle rules: 22 mechanisms
  named under `## Hard gates`, six of them modules with no `__main__`. Every one is
  genuinely enforced — each is imported by a runner that has an entry point, so this was
  never a hole in coverage — but a reader following the rule to the mechanism got:
  ```
  $ python3 .../check_evidence_pointers.py --root .
  $                      (no output, exit 0)
  ```
  Silence and zero are what a passing gate looks like, reached through the document that
  exists so "the reader of a rule can reach the mechanism". The gate now reports
  `not_runnable`, per line rather than per script, because a line naming a library
  ALONGSIDE its runner has told the reader what to run. The six lines in
  `cycle-discover.md`, `cycle-implement.md`, `cycle-backlog.md` and `cycle-review.md` now
  name both. **Not a CLI per library**: six entry points into scores that are only
  meaningful composed would be six second ways to reach a partial answer.

- **The selector handed out work from a registry its own gate called INVALID** (#159)
  `select_backlog_item` imports `_parse_items`, `Item` and three helpers from
  `check_backlog_structure` — the parser, never a verdict — so the two read the same
  file and disagreed in the one direction that matters. Measured 2026-09-19 on a
  registry holding `B-001` twice: the checker returned `INVALID` with *"ids are the
  audit trail; two blocks sharing one destroys it"*, and the selector returned
  `ITEM_SELECTED → B-001` with a queue of `['B-001', 'B-001']`. The caller cannot tell
  which of the two blocks it was handed, and the loop would run the id twice. Nothing in
  the selector's output named the structure. It now refuses with `BACKLOG_INVALID`,
  naming the findings rather than counting them.
  **Identity only, and the first draft got this wrong.** Keying on `verdict == INVALID`
  took every blocker with it, so one `triaged_without_evidence` stopped the registry from
  handing out any work — this gate blocking the machine over the very condition the
  machine exists to fix, and a gate that does that is one people route around. Three
  existing tests caught it. The line is now `IDENTITY_CHECKS` — `duplicate_id` and
  `renumbered`, the two the checker itself describes as making a reference ambiguous —
  declared in the checker so a third one joins both readers at once. A content blocker
  leaves the id intact and the item selectable. The lead needed no change: its branch is
  generic on anything that is not `ITEM_SELECTED`, and the comment beside it now names
  the third verdict rather than telling a reader only two arrive there.

- **The origin-name gate could not see a file until after it was committed** (#158)
  It enumerated `git ls-files` — tracked paths only — so a file not in the index yet was
  invisible, and the author got a pass at exactly the moment they made the mistake.
  Measured 2026-09-19: a session wrote a new test carrying ten occurrences of a
  consumer's app and scope names, ran the gate, and it passed; the file was `??`. On a
  branch two sessions share, the finding then lands on whoever commits next. Scanning
  untracked files sounds expensive and is not — `--exclude-standard` honours
  `.gitignore`, and measured in this repository at the same moment that is **1 path**
  against **2277** for the unfiltered form. So the repository's own ignore rules draw the
  line and the gate carries no second list of what to skip. `--cached` was the other
  candidate and sees the file one step later, at `git add`, which is still after the
  author has stopped looking at it. A tracked path deleted from disk is dropped, because
  reading it would be reading nothing.

- **A `touch` on four filenames scored 35% of a product brainstorm** (#156)
  `score_product_alignment` asked the filesystem whether each cascade document existed
  and never asked what was in it. The line below that cap already scored a MISSING
  document from `""`, so missing and empty ran the identical scoring path and only the
  cap separated them — on the wrong question. Measured 2026-09-19 with four files holding
  one heading each: `NEEDS_REVISION`, 35.3%, `hard_caps: []`. The 35.3% is six criteria
  that are vacuously true of emptiness — `no placeholder` ×4 and `0 dangling citation(s)`
  ×2 — which stay as they are, because a real document can fail them and presence is
  already a separate criterion. What could not stand is a recoverable verdict asking
  somebody to revise what nobody had written. Reported as `empty_document`, never folded
  into `missing_document`: one sends a person to create a file and the other to open one
  they already have. "Empty" is drawn narrowly — whitespace and headings only — because a
  heading AND a paragraph is a partial document, and partial is what `NEEDS_REVISION` is
  for; the wider rule would call a badly structured but genuinely written document absent.

- **The 90% alignment floor was stated three times and read none** (#157)
  `cycle-brainstorm.md` G-B4 claimed the cycle "reuses them rather than choosing a second
  number for the same purpose". It did not: `alignment-threshold.md` carried the prose,
  `score_alignment.py` carried `THRESHOLD = 0.90`, and `score_product_alignment.py`
  carried `FLOOR_PCT = 90.0` — not even the same type, so a change to one could not be
  made mechanically in the other and nothing would report the disagreement. They agreed
  by coincidence. The figure now lives in `squad/rubric.py`, whose docstring already
  carried this argument for the rubric PARSE — *"three copies of one convention are three
  places for it to drift, and the drift would be silent"* — and both scorers read it, the
  ratio derived from the percentage rather than written again. The reasoning stays in
  `alignment-threshold.md`: a constant cannot hold an argument and a rule file cannot be
  imported, so each keeps the half it can carry.

- **Removing a Squad hook from `settings.json` now sticks** (#154)
  `settings.json` is Claude Code's own configuration and the kit writes its hooks into
  it — the same shape `spec-kit` uses, where an integration's events go into the agent's
  native config and are removable through it. That is the one configuration surface, and
  it did not hold: measured 2026-09-19, a project removed `UserPromptSubmit`,
  reinstalled, and the hook was back. `merge_hooks` placed *"the kit's groups first,
  verbatim"*, so a removal was invisible to it and the file only looked like
  configuration. A surface that does not hold is why somebody ends up asking for a flag
  instead — and a flag would give one system two behaviours and two sets of gates.
  `.kit-hooks.json` already recorded what the kit shipped and was read in one direction
  only, to retire what the kit dropped, never to respect what the project dropped —
  while `merge_permissions` one function below states the rule verbatim: a rule present
  in the consumer and absent from the kit is *"either something the kit retired or
  something the project added, and those must never share an outcome"*. The install now
  prints `left out — you removed it from settings.json` for each rather than re-wiring
  in silence, and a hook the kit never shipped before is not read as a removal, so gates
  added since a consumer's last install still arrive. **No exemption for the guards** —
  removing `PreToolUse` removes the refusal to write into the installed kit, and nothing
  puts it back. One mechanism, one meaning.

- **A first install left no record of what it shipped** (#155)
  `.kit-hooks.json` and `.kit-permissions.json` were written only by the merge path, and
  a fresh install took the other branch — `cp settings.plugin.json`, because the target
  had no settings yet. Measured on a clean target: both absent. So on a freshly
  installed consumer the first removal was not respected, and the install after THAT one
  was, because by then a merge had finally written the baseline. A rule that starts
  working on the second attempt is one nobody can rely on and nobody can explain. The
  branch is gone rather than patched: `{}` is seeded and the merge always runs, which
  produces the kit's settings exactly — same 108 deny rules, same hooks, differing only
  in the order of `deny`, and the merge is idempotent. A freshly installed consumer now
  holds byte-for-byte what a reinstalled one holds; before this they differed and
  nothing said so.

- **A rollback was either silent or impossible, and the rule asked for neither** (#152)
  `cycle-maintenance.md § Rollback` says an item advanced in error "is moved back with a
  note recording the advance and why it was withdrawn — never silently reset."
  `backlog_status.py` implemented half of that and implemented the half without the
  note: measured 2026-09-18, `approved -> triaged` was accepted and left the block
  reading `status: triaged` and nothing else — the fresh-looking item the rule names as
  the thing to avoid — so an item could be walked back through the whole open chain
  leaving no trace. Meanwhile `triaged -> raw`, the same move one step down, was refused
  outright, which is the gap a consumer actually hit. A move to an earlier entry of the
  open chain is now a withdrawal: it requires `--withdraw-reason`, held to the bar
  `--kill-reason` already holds a committed item to — who withdrew the call and what
  changed, not what the evidence showed — and writes `withdrawn_from` beside it, since
  after the move the status line cannot say what the item used to be. The chain is
  ordered rather than enumerated as legal pairs, because a list of rollbacks is a list
  somebody extends the table without updating, which is how this half arrived.
  `shipped` stays terminal: reopening it changes what shipped means to every reader that
  counts delivery, and that is a person's call.

- **A block could carry another item's evidence and stand at `triaged` on it** (#151)
  `duplicate_field` reported `status` and nothing else, and the narrowing was reasoned:
  `partial_progress` four times is an append-per-increment log a team keeps on purpose,
  and `evidence: none-yet` followed by a pointer is an item advancing. That holds while
  the second line is about the same item. Measured on a consumer 2026-09-18 it was not —
  B-001 carried a second `evidence:` and a second `blocked_by:` describing **B-006**,
  its authorization work and its line count, while B-006's own block read `evidence:
  none-yet, status: raw`. Seventeen blocks read, one finding, and it was `index_stale`.
  B-001 stood at `triaged` on another item's evidence; removing the foreign lines made
  `triaged_without_evidence` fire immediately, which was the honest state all along. The
  two extra lines also shifted every pointer below them by exactly 2, breaking three
  `BACKLOG.md:N` citations in a scored opportunity that three reviewers then spent a
  round on. A placeholder replaced by a real value is still silent — that is the case
  the narrowing existed for — but two substantive values are two claims, and `blocked_by`
  is reported on any repeat because it names the whole edge set rather than adding to
  it, so every line but the last leaves the dependency graph without a trace.

- **On every plugin install, a panel that convened and voted read as one that never
  ran** (#150)
  `convene_panel.default_panel_path()` was fixed months ago and carries the reasoning in
  its docstring: `install.sh` copies `rules/` into `<target>/.claude/`, so the roster is
  at `<project>/.claude/rules/review-panel.txt` and the project-root path does not
  exist. `check_panel_approval.py` held a function of the **same name** with the unfixed
  body. Measured on a consumer 2026-09-18, against a panel with three seats, two
  families and a unanimous verdict on disk: `UNCHECKED: cannot read the roster:
  .../apps/theoclaw/rules/review-panel.txt`. `UNCHECKED` reaches the opportunity scorer
  as `ITEM_IN_FLIGHT` — *the panel could not convene* — so a panel that ran and returned
  was indistinguishable from one that never ran, and the item stalled. Two functions
  with one name and only one of them fixed is a shape this kit has paid for repeatedly;
  the resolution now lives in `squad/layout.py`, which already answers where the kit is,
  and both callers pass the project they were given rather than falling back on the
  process directory. Verified on the same consumer: the gate now reports `RETURNED →
  NEEDS_REVISION` with all three seats, without the `--panel` workaround.

- **A third gate charged `/review`'s own output for being output** (#149)
  `check_xrefs.py` has exempted `review-{slug}-{role}-knowledge` since the day the
  predicate was hoisted out of an inline check, and its docstring closed with *"One
  definition, two consumers: that is what stops the next half from escaping."*
  `check_skill_map.py` never learned it, and warns about that exact shape in its own
  prose while being it. Measured on a consumer 2026-09-18: 13 `missing_from_map`
  findings plus `missing_sop` and a disagreeing count, every one about a file `/review`
  had just written, on an install whose own files were correct. The only exemption
  available was `rules/auxiliary-skills.txt`, maintained by hand — so the remedy on
  offer was to re-list, after every review, the artifacts the kit generates by itself.
  The predicate now lives in `squad/paths.py` with the rest of what the kit knows about
  its own produced data, and both gates import it, so a fourth sweep inherits the answer
  rather than re-deriving it.

- **`/review` generated skills that the kit's own gate then failed, and that Claude
  Code could never load** (#148)
  All five paired-knowledge templates began with an `#` heading and carried no
  frontmatter, so every `/review` run wrote up to five `SKILL.md` files without `name`,
  `description` or `user-invocable`. Two costs, and the second is the expensive one.
  `validate_skill_frontmatter.py` runs as post-install validation and requires exactly
  those three fields: measured on a consumer 2026-09-18, thirteen generated skills, and
  `=== SOME CHECKS FAILED ===` on an install whose own files were all correct. The gate
  was right; the kit had produced what it failed. The larger cost is that Claude Code
  reads a skill's name and description from that frontmatter — a `SKILL.md` without it
  is not discovered at all, so the "paired knowledge skill" the template calls
  *auto-discovered by Claude Code* has never been loadable by the mechanism it names.
  The reviewer agent ran; its knowledge layer did not. The `name` is now
  `review-{SLUG}-{ROLE}-knowledge`, and `ROLE` is substituted by the function that names
  the output directory rather than by its caller — a skill whose frontmatter name
  disagrees with its directory is discovered under one identity and referenced under the
  other, which surfaces as a missing skill and nothing else. Verified end to end: five
  skills generated, five accepted by the gate, every name matching its directory.
  Skills already written by past runs are inert and stay on disk — the kit does not
  write into another project's repository to repair them.

- **A stale report from another run counted as this run's audit coverage** (#145)
  `check_auditor_coverage` globbed the plugin's output directory and took whatever it
  found, with no date, commit or diff base behind the choice. Measured on a consumer
  2026-09-18: it reported COVERED with "2 blocking findings" from a report written
  **2h45 earlier by a different run**, while the audit of the change actually under
  review sat in a sibling directory with four. The assignment file records when the
  audit was *commissioned*, so a report older than it cannot be the audit that was
  asked for — an ordering fact the gate already held both sides of and never compared.
  It now refuses a report that predates its assignment. It deliberately does **not**
  claim the converse: a newer report may still describe the wrong change, and proving
  otherwise needs a `diff_base` only the plugin can declare. A report the gate cannot
  date is still accepted, because a gate that refused everything it could not measure
  would be routed around.

- **The kit refused writes to files belonging to other plugins** (#146)
  `.claude/` is shared — every plugin a project installs writes there — and the boundary
  treated the whole directory as the kit's. Measured on a consumer 2026-09-18 it claimed
  `code-review-loop.local.md`, `code-review-loop.completed.md` and
  `test-audit-loop.local.md`; deleting the first is `loop-code-review`'s own documented
  way to cancel a run. The refusal was not just inconvenient, it was **false about why**,
  and a guard that misstates its reason teaches people to route around it.
  `.kit-manifest.txt` already answered the question — its header reads "Anything not here
  is the project's" — but the boundary consulted it for `skills/` alone. It now asks
  whether any prefix of the path is claimed, which covers all three granularities the
  manifest uses at once. That widening had a precondition: the manifest enumerated
  `skills/`, `rules/`, `agents/` and four directories and named **no loose file at all**,
  so at the kit root it answered by omission — exactly what its header promises it never
  does. The installer now lists the files it copies there, declared once and read by both
  the copy loop and the manifest writer so the two cannot drift. With no manifest the
  boundary concedes nothing and the old refusal stands, because treating an unreadable
  manifest as a blanket unlock is this kit's most-repeated defect wearing the other face.
  The manifest's authority stops at the trees the kit ships whole (`hooks/`,
  `mechanisms/`, `squad/`, `commands/`, `rules/`), where structure answers and no file
  has to. Without that limit the fix opened a larger hole than the one it closed: the
  manifest once covered `agents/`, `rules/` and `skills/` only, by `install.sh`'s own
  admission, so every consumer installed before it widened would have had `hooks/` and
  `mechanisms/` handed to the project. `test_kit_is_read_only` builds exactly that
  manifest and caught it.

### Added
- **The board opens with a verdict, and every column says whether work is happening
  there** (#143)
  It drew ten lanes and a search box: everything true, nothing a conclusion, so the
  reader assembled one by counting amber cards and remembering which lanes had not moved.
  Three readings by the person it is built for found five things it could not answer.
  There is now one band at the top — `blocked` → `at_risk` → `working` → `stalled` →
  `idle`, ordered by urgency rather than by count, because one item waiting on a person
  outranks nine in backlog that move on their own. Each column carries its own state and
  idle time; each card names any phase behind it with no event on the stream, worded as
  "no record" rather than "skipped" because a conditional phase can be legitimately
  absent and the page cannot tell that from one that ran silently. Delivery reports
  shipped, killed counted apart, and throughput over a stated window — rendering `—`
  rather than `0/day` while nothing has shipped, since those are different facts and only
  one is alarming on a young registry.

- **The board classifies every column and computes WIP** (#141, #142)
  Each lane now says whether work is happening there — `working` (a phase started and has
  not ended, or uncarded work moved recently), `queued` (items here, something moved
  inside the stall window), `stalled` (items here, nothing moved — or nothing ever did)
  and `empty`. Card count told the reader how much was there and never whether anything
  was happening: on one consumer `plan` held four cards nothing had touched in two hours
  and looked exactly like a lane in flight. Undated counts as stalled rather than fresh,
  because an item the stream never mentioned has not just moved. A WIP strip reports
  items in flight, the peak over the window, and the smallest concurrency that never
  idled — **derived, never prescribed**: when the window has an idle gap it reports no
  minimum at all rather than the lowest level it ran at, because a system that stopped
  was not kept fed by any concurrency, and four items waiting on an access impediment are
  not helped by starting a fifth.

- **A backlog item that declares itself closed and is filed as open is now reported**
  `check_backlog_structure` read the fields and never the prose, so a block could say
  `remeasured …: **closed in code.**` in its own body while `status: triaged` sat four lines above
  it, and the report still read SHIPPABLE. Measured on a consumer 2026-09-18: twelve items in that
  state across a registry of 44, with the gate clean on every one.

  The cause is structural rather than careless. `backlog_status.py` refuses `triaged -> shipped` —
  from triaged an item may go to `approved` or `killed` — and `approved` is a human decision an
  agent may not make. A remeasurement that finds an item DONE therefore has nowhere legal to put
  that. It goes in the prose, and the two halves of the block disagree from then on.

  `status_contradicts_body` asserts nothing about whether the item is really done; nothing here can
  measure that. It asserts that a reader has two answers and no way to choose. The pattern is
  deliberately narrow — the remedy must be NAMED (`closed in code`, `closed by deletion`), never the
  bare word, which appears in ordinary prose about closing a connection. On that consumer it
  correctly excludes two blocks saying `three of five closed` and `two fresh instances`.

  The comment shipped saying **fourteen**, which was the first draft's count before the narrow
  pattern was written; the code it describes measures twelve. Corrected here.

- **The signing preview now says what the document is, not just which box to tick**
  (#133)
  It showed the sign-off section and the path. Four product documents wait at once and
  their sign-off sections read alike — `- [ ] Read and holds`, four times — so a batch
  preview told them apart by filename, which puts the signer in the position the gate
  exists to prevent: ticking a box whose subject they are taking on trust. Each preview
  now opens with the document's own `# ` title, its own `## ` headings, and its length.
  **Everything in it is extracted, never generated**: a model-written summary would be
  one more thing the reader has to verify, and the signature already asserts that they
  read the document. A test fails on any word in the summary that is not in the file.
- **`/sign --all` signs every document that is waiting, and shows each one first** (#133)
  `/brainstorm-pieces` stops with four product documents waiting at once — they are
  written together and read together — and the tool took one path per invocation. `--all`
  takes the same list `--list` reports. It is deliberately **not** a `--yes`: the default
  run prints every document's sign-off section in full and writes nothing, so what the
  flag removes is the repetition of the command and not the reading. A refusal stops one
  document rather than the batch, because aborting on the first would leave the earlier
  ones signed and the later ones untouched with nothing saying where it stopped; the run
  exits 1 when any document was refused, since a caller that asked for *all* and got some
  did not get what it asked for.

### Fixed
- **WIP counted abandoned phases as work in flight** (#143)
  A `brainstorm` opened 22 hours earlier and never closed held the figure at "1 in
  flight" while no item was being worked at all — so the owner's question, *which item is
  being worked*, returned nothing while the number said one. `_phases_running` had
  already learned that an unclosed start is a fact about the STREAM rather than a claim
  about the WORK; `_wip` counted raw starts and did not inherit it, which made the figure
  grow monotonically as lanes died — the opposite of what it measures. A start past four
  hours is now `abandoned`, named with its age and its slug so it can be closed, and
  withdrawn from the series by removing its `+1` rather than adding a `-1`: a phantom
  close would put a false drop on the timeline and invent an idle gap that never
  happened, corrupting the minimum-WIP figure derived from it. Four hours and not the
  stall window's thirty minutes, because an implement slice legitimately occupies an
  afternoon.

- **Four emitters recorded only phase ends, so nothing could be drawn as working**
  (#142)
  `cycle_events.emit_phase_start` has existed since the stream did and nothing called it:
  code-quality, review, implement and acceptance each called `emit_phase_end` and none
  called its sibling. One consumer's stream held **37 ends against 1 start**, so every
  instant read as zero in flight — no column could be working, no phase had a duration,
  and WIP was uncomputable by construction. `code-quality` alone emitted 29 ends against
  one slug, with no way to tell 29 runs from 29 reports of the same one, which is exactly
  what WIP measures. All four now emit the start **before the work**: a run that dies
  mid-phase leaves a start with no end, which is what an interrupted phase is. This
  measures from now on — the historical events gain no retroactive starts, and no
  computation can invent them.

- **The board discarded 37 of 38 events and rendered a blank page while the cycle was
  working** (#141)
  The only link between a plan and its item was the filename convention `bNNN-name`.
  Plans called `composition-di-plan.md` and `ci-coverage-plan.md` carry no item number,
  so every event under those slugs resolved to nothing and was dropped — and the ids were
  inside the plans all along, where nobody looked. The owner opened the page while a
  `review` phase ended `READY_TO_MERGE_WITH_FOLLOWUPS` and saw no work at all.
  `item_id_of`'s docstring already recorded the smaller version of this — *"12 events, 6
  of them plan slugs, every one invisible"* — and fixed it by teaching one more filename
  shape; a third pattern would have postponed the next occurrence rather than ended it.
  The link now comes from the plan's body, and **work that still cannot be attributed is
  shown rather than dropped**: a strip naming the slug, its phases, its event count and
  its last verdict. The board already counted these as `unplaced` and reported them as a
  failure to place — honest, and useless, because it said something was missing without
  saying what. Placed events went from 1 of 38 to 36 of 38.

- **Eight held items drew eight identical chips, and half were the queue's own work**
  (#141)
  The board carried each wall's prose and never the verdict on it, so the reader's real
  question — which of these is waiting on ME — had no answer on screen.
  `delegated_decision.classify_wall` had answered it since the delegation file existed,
  one import away from the view built to show it. Each blocked card now states who can
  clear it and which class the registry puts it in. Measured on one consumer: **4 the
  system's, 4 the person's**, where the page had shown eight of the same. The person's is
  drawn at full strength and the system's quieted — the queue needs no prompting and the
  person does. Nothing is decided here: an unmatched wall stays `unclassified` and belongs
  to the person, because `on_no_match = retain` is the registry's rule and a view that
  softened it would claim a consent nobody gave.

- **An item waiting on another item was sent to a person, with nothing to decide** (#140)
  `classify_wall` had no class for a wall naming another item in the same registry, so it
  fell to `UNCLASSIFIED` and `on_no_match = retain` addressed it to somebody who was never
  going to answer: the answer is "finish the blocker", which is the queue's own ordering,
  and `autonomy-envelope.md § What the human owns` reserves WHAT is worth doing rather
  than the order the system works through it. A second defect sat beside it — the `SCOPE`
  pattern demanded `scope decision` as adjacent words and missed *"committed scope is a
  decision nobody has taken"*, so a class the sponsor had delegated never reached a wall
  it covers. Measured on one consumer holding six items: **one of six was the system's
  before, three of six after.** The three that remain are an access impediment no
  mechanism resolves and two items whose code lives in other repositories. `on_no_match =
  retain` is untouched: one shape stops reaching it, and `DEPENDENCY` is tested last so a
  wall citing an id while being about something else keeps its more specific class.

- **A nested registry reported every route broken, on specialists that exist** (#138)
  `check_backlog_structure` resolved `agents/<specialist>.md` against the registry's own
  directory, so a monorepo with `apps/<app>/BACKLOG.md` and one installation at the root
  looked in `apps/<app>/agents/` and found nothing. Resolution now starts from the
  directory the routing TABLE was read from — `agents/` hangs off that tree, not off
  wherever the registry sits — with the registry's directory kept as a fallback so a
  registry beside its own `agents/` keeps working. A sub-project with its own table still
  points at its own specialists, and a domain routing to nothing is still a blocker.

- **Refusals that hid the list sent their reader to the gate's source** (#139)
  Measured over one 20-hour consumer session: **64 of 676 commands — 9% — were the agent
  reading a gate's `.py` with grep or sed to discover the shape it wanted.** The gates
  were honest about what failed and silent about what would pass, which is a different
  property. `check_opportunity_completeness` named three missing sections out of ten, so a
  reader fixed three, re-ran, and met the next three. `check_concurrency_tests` carried a
  hand-written parenthetical naming six accepted signals while its matcher held
  thirty-nine, and the two could drift. Both now render the whole list, derived from the
  constant the matcher actually uses rather than restated beside it.

- **A consumer's own cycles and verdicts had nowhere to be registered that survived an
  update** (#137)
  The gates require every cycle to be placed in `rules/squad-map.md` and every verdict to
  be banded in `rules/verdict-bands.txt`, and `install.sh` overwrites both. A project with
  a cycle of its own could register it, watch its gates go green, and have the edit
  reverted by the next install — with no action on its side that lasts longer. Measured on
  one consumer: one cycle and four verdicts, registered by hand, gone after the next
  `--merge`. Two files now carry the extension and are preserved like every other
  `rules/*.txt`: `auxiliary-cycles.txt`, the sibling of `auxiliary-skills.txt` and read
  the same way, and `verdict-bands.local.txt`. The verdict file needed a different shape —
  a skill or a cycle can be EXCLUDED from a sweep when the project claims it, but a
  verdict cannot, because `check_phase_drift` has to classify every verdict that reaches
  the event stream or an unclassified one silently disables the check. So the local file
  adds rows, and the kit's file stays authoritative: a local row naming a verdict the kit
  already classifies is reported and **not applied**, because quietly reclassifying `PASS`
  is the drift a single registry existed to prevent. The reports name which file an entry
  came from. `skills/map.md` needed no change — `rules/auxiliary-skills.txt` has answered
  this for skills since 2026-09-02, and the consumer had edited the wrong file.

- **A registry created exactly as `/backlog-init` instructs was born INVALID** (#136)
  Two rules of the kit contradicted each other. `backlog-init` Step 3 says *"Seed no
  items — an item nobody filed is a placeholder that will be inherited as though it were
  a decision"*, and `check_backlog_structure.py` blocked on `content.strip() and not
  items`, true of every freshly-seeded registry: the scaffold has a header, an `## Index`
  and an `## Items` section, and zero items. Measured over a registry built to the letter
  of Step 3: BLOCKER `registry_parses`, verdict INVALID — obeying the kit produced a
  non-conformant artifact. The check stays, because an unparseable registry reporting
  SHIPPABLE is what it was written for; what it gained is the ability to tell the two
  apart. A registry declaring `## Items` and holding none is empty; one with no such
  section, or with headings under it the parser cannot place, is unreadable and blocks.

- **A registry one directory down had its routing silently unchecked** (#136)
  `_routing_table_path` looked in `.squad/`, `rules/` and `.claude/rules/` relative to
  the registry's own directory and did not climb, so a monorepo with `apps/<app>/BACKLOG.md`
  and `.claude/` at the root never had routing checked — on a table present and valid two
  directories above. The search now walks up, stopping at the repository boundary, and
  the nearer table still wins: a sub-project with its own routing answers a different
  question than the umbrella's. The warning also said *"routing table unreadable"* for
  three different facts — tooling absent, no table found, table found and unparseable —
  so an operator looking at a valid table read it as a false alarm and read the next real
  one the same way. Each cause now names itself.
- **The merge-autonomy premise was never once verified, on any repository that reaches
  GitHub through an SSH host alias** (#134)
  `check_merge_autonomy` asked `gh api repos/{owner}/{repo}/...` and left the placeholders
  for `gh` to expand. `gh` refuses any host it does not recognise, so a remote of the form
  `git@git-alias:owner/name.git` failed with "none of the git remotes ... point to a known
  GitHub host" and the gate returned UNCHECKED. Measured on one consumer ecosystem: 16 of
  17 repositories, every one of them, permanently — while the answer was one call away and
  the slug sat in the remote URL in plain text.

  `UNCHECKED` was never a pass and the file said so at length, which was right. What was
  wrong is that it also grouped this cause with the private-repository 403 as one that
  "NEVER resolves", and that sentence is what stopped anyone fixing it. The slug is now
  read from `origin` and the placeholder form is only the fallback; the 403 keeps its
  permanent status because it genuinely does not resolve.

- **The cross-reference gate read code specimens as references, and 96% of what it
  reported was noise** (#132)
  A skill that teaches a markup language writes that markup out. `check_xrefs` resolved
  every link inside a fenced block against the document's own directory, so
  ```` ```markdown ![bg](image.png) ```` — four lines teaching Marp image syntax — became
  four broken links in a file that has none. Measured on one consumer install: **44 of 46
  findings were specimens**, all in the two skills that document a markup language; the
  other two were real. A gate whose output is mostly noise is a gate somebody switches
  off, and the silence after that is indistinguishable from a clean repository — which is
  the failure this directory exists to prevent. Links are now read from `prose_only()`,
  so `squad/markdown.py` owns the fence regex here as it already does for the six
  checkers that disagreed about whether `~~~` opens one.

- **Three gates reported a verdict about a tree they had not read** (#129)
  `check_prose_tests --root <empty tree>` answered `no test pins the wording of shipped
  prose (394 test file(s) parsed)` — it had swept the repository it was standing in.
  `check_chain_preconditions` did the same under a heading naming the other tree, and
  `check_merge_autonomy` printed `HOLDS` because `gh` inherits the working directory, so
  the flag it accepted changed nothing about what it asked. The first two shared one
  `dest` between a positional and its option, and argparse applies the absent
  positional's default after parsing the option. All three now answer for the tree they
  were given, and an unreadable one exits 2 rather than reporting a pass.

- **One question had eight spellings, so three callers each carried the whole table**
  (#129)
  Thirty-three gates take a tree to sweep and named it eight different ways — 12
  `--root`, 4 `--repo-root`, 3 `--project`, 3 `--project-root`, 2 `--repo`, 2
  `--ecosystem-dir`, two more, and 7 gates taking none. `mechanisms/gates/_contract.py`
  now declares one flag, with every older spelling kept as an alias so no existing
  invocation breaks, and reuses `squad/cli/report.py`'s exit vocabulary rather than
  restating it. The three hand-kept tables are gone: `verify_ecosystem`'s adapters, the
  22-entry `ROOT_FLAG` map — whose own comments record `check_xrefs` sitting outside the
  empty-sweep protection for a week because it spelled its flag `--ecosystem-dir` — and
  the obsolete half of `run_checks.py`'s reason for not globbing. The roster is now the
  glob, which took it from 22 gates to 29 plus 4 that need a slug or an install path to
  run at all, each named with its reason and held to it by a test.
  `check_gate_mechanisms.py` reports any gate that drifts off the contract, reading the
  AST: grepping for the flag called `check_produced_files.py` compliant, and it takes no
  root — the literal is there because it invokes other gates with it.

- **The gate that aggregates every other gate had no machine-readable answer** (#129)
  `verify_ecosystem.py` runs 25 checks and is what a consumer points at to ask whether an
  install is sound. A programmatic caller got an exit code and, in prose, `(N not run —
  each ⊘ above says why)`: the reasons were on screen and nowhere a parser could reach
  them, so sixteen skipped checks were indistinguishable from a clean run. It now accepts
  `--json` and emits a `Report` whose `not_checked` names every check that did not run and
  why, with the human text carried in `lines` rather than racing it to stdout.

- **A Portuguese section header shipped in the installer for four months while the
  language gate called the tree clean** (#130)
  `mechanisms/distribution/install.sh:203` and one ADR heading were in Portuguese.
  `check_english_only` matches a closed list of markers and none of those words carried an
  accent or appeared on it, so 997 files were reported clean on every run. Both lines are
  translated and two markers joined the list. The list's structural gap is filed rather
  than papered over: a first attempt at a dozen more words produced 22 findings across 14
  files, of which one was a defect and the rest were fixtures that carry Portuguese by
  design.

- **Two required CI steps failed on the tree they ship with, and half the suppressions in
  the repository said nothing about why** (#87)
  `ruff check` exited 1 on 90 findings at HEAD and `check_prose_tests.py` exited 1 on five
  asserts, so the job was red from the code and not only from the Actions billing block.
  Both now exit 0. The ruff half was not a formatting sweep: 41 `# noqa` directives named
  rules nothing enforces, 100 `# noqa: PLW1510` hid a `subprocess.run` whose exit code
  nobody declared — each now carries an explicit `check=False` instead of a suppression —
  and 7 `l` bindings, 8 compound statements and one lambda assignment were rewritten rather
  than silenced. 450 suppressions carried no reason at all; every one now states what the
  rule cannot see, except six `E402` lines too long to take a clause, which their file's
  bootstrap note covers. Two real defects surfaced underneath: `run_opportunity_score.py`
  imported the rubric loader and never called it, so a malformed rubric reached the scorers
  and produced a score from nothing, and `run_structural.py` computed an impediment report
  its own comment called REPORTED and then dropped it. The five prose asserts were kept
  with the exemption the gate ships, each naming why the contract text is the subject and
  not a proxy for behaviour.

- **The documentation offered three entry points that resolve to nothing, and pointed at
  the wrong routing table** (#87)
  `HOW-TO-USE.md` listed `/plan-grill`, `/session-goal` and `/trajectory-review`; the kit
  ships no skill or command for any of them, and `skills/plan-write/SKILL.md` told an agent
  to halt and recommend the first. `README.md` and `HOW-TO-USE.md` both named
  `rules/cycle-backlog.md` as the domain routing table, which is worse than stale: the file
  is kit-owned and `squad/boundaries.py` admits only `rules/*.txt`, so an adopter following
  the instruction is refused by `boundary-check`. The table is `rules/domain-routing.txt`
  and the documents now teach the bare `--write`, which resolves its own destination.
  `CONTRIBUTING.md` prescribed a `lib/` submodule that `check_semantic_names.py` refuses in
  CI and cited a precedent directory that does not exist. Four role prompts carried an
  orphaned table row that rendered as a stray one-line table, and their heading counted
  four roles over a table of fourteen.

- **Eight spellings walked through the git-safety hook, and its own suite could not see
  any of them** (#87)
  The guard normalises a command and then matches verbs in it; every normalisation step
  had a hole. `_GIT_GLOBALS` enumerated six of git's twenty-plus global options, so
  `git --no-pager checkout main` carried a verb no guard saw. `_QUOTED` deleted a quoted
  span entirely, so `git "commit" -m x` lost its subcommand. `_git_prefix` took the first
  `-C` anywhere in a compound, so `git -C /tmp status && git commit -m x` asked the wrong
  repository which branch it was on. `_git_out` returned `""` for both "git failed" and
  "git answered nothing", so every trunk guard fell silent exactly when the hook could not
  see. `DANGEROUS_PATH_RE` anchored on whitespace and missed `rm -rf "/etc"`, `rm -rf ~/*`,
  `rm -rf $HOME/*` and `rm -rf ${HOME}`. `BRANCH_DELETE_RE` required the flag before the
  name, so `git branch workspace -D` and `git push origin :workspace` passed. The
  kit-boundary collector took absolute and `./` paths only, so
  `sed -i s/a/b/ .claude/rules/architecture.md` was never examined. And an unreadable
  `-F <path>` raised out of the hook entirely, exiting 1 — "the action proceeds" — before
  the co-author and zone guards ran. All eight measured, each against the spelling that was
  already refused. The suite missed them because it varies the VERB and fixes the SPELLING:
  47 cases carrying `rm -rf /`, `/etc` and `/home` and no quoted or tilde form.
  `tests/hooks/test_the_guard_matches_the_spelling_not_the_verb.py` now pairs each blocked
  spelling with the one that reached the tool.

- **Five gates reported a tree clean after measuring nothing in it** (#87)
  `verify_ecosystem` printed `=== ALL CHECKS PASSED ===` and exited 0 when every check
  returned `NOT_RUN` — `all_pass` is cleared only in the failure branch and the sentinel is
  truthy by design. It also spawned `check_xrefs` without `--strict`, so every WARN class
  arrived as exit 0 while `install.sh` and CI both passed the flag: the smoke test was
  weaker than the installer depending on it. `check_emitted_verdicts` and
  `check_prose_write_paths` printed `CLEAN` over a zero-file sweep against their own
  exit-code tables, each already defining the `UNCHECKED` constant they did not reach.
  `check_orphan_verdicts` reported every verdict reachable after sweeping zero cycle rules.
  `check_phase_emitters` returned 0 with no `cycle-phases.txt` to read, and its
  `SEARCH_GLOBS` still named `scripts/*.py` — zero files since the 2026-09-01 rename — so
  `mechanisms/` was outside the sweep entirely. Each now separates "could not measure" from
  "measured and found nothing", and
  `tests/test_a_gate_that_swept_nothing_is_not_clean.py` asserts that no glob in the sweep
  matches zero files.

- **The documented dispatch prescribed the defect the code no longer had** (#86)
  `pipeline/SKILL.md` told an operator to pass the `queue` array while SELECT had grown
  two more keys carrying schedulable items, and the workflow's own input contract was a
  flat array — so even an operator who knew about them had nowhere to put them. Measured
  on a consumer registry of 102 items: the whole selection builds 71, of which 56 approved
  enter at PLAN; the `queue` array alone builds 13, none approved. A test now pins the
  procedure and the workflow together, so the next key cannot land in one and not the
  other.

- **The installer's header said it ships no specialists, and it ships 14** (#86)
  True when written, false for every install since — found while installing a consumer,
  where `agents/` went from 1 file to 15 and the comment said that could not happen. The
  same file already records this failure happening once before, with a reader who trusted
  a stale line and avoided the installer to protect permissions the merge would have kept.
  The header now counts what it ships, and a test keeps the count honest.

### Fixed
- **Gates reported correct work as a defect, three ways** (#86)
  A phase declared as running *inside* another was judged by its position in the chain, so
  `code-quality` firing around `implement` — which `cycle-phases.txt` has always described
  — produced all 19 divergences of a consumer run, none of them real. `PARTIAL`, the
  verdict the validation gate emits on exit 0, had no declared band, and an unclassified
  verdict silently disables the disorder check for the rest of that item. And an annotated
  `#### Files to edit` bullet parsed as zero declared files, raising HIGH
  `no_declared_scope` against plans that declare their scope precisely — as did an
  explicit `None.`, a `None.` carrying its reason, and a phase whose only change was its
  CHANGELOG entry.

- **The allowlist refused commands nobody could have run another way** (#86)
  `cd` was absent though it is a pure builtin, and the tokenizer split on `)` but not `(`,
  so `(cd api && go test ./...)` — how a workspace repository says "in this module" — was
  refused as the unknown command `(cd`. Operands left over from splitting were read as
  commands, `git hash-object` was refused for a write only `-w` performs, and `mktemp`,
  which builds the control that makes a criterion discriminate, was refused outright. One
  consumer item went from 6 of 12 clauses unrunnable to 1. A hole that predated this is
  closed with it: `env` was on the allowlist as a plain command, so `env FOO=1 git stash`
  walked through — wrappers now have their payload read as its own command.

- **A gate charged the item for a tree it did not write** (#86)
  A red test in a package the change never touched blocked every item in a consumer
  repository, verified pre-existing by building the tree at the commit before the item's
  first. Test suites now have the three states lint already had, and scope drift gained
  its other half: declaring a file and never touching it. The stage that writes also
  records that work started and walks the status back when it halts — an item left at
  `planned` by a stopped lane is invisible to every list the scheduler reads.
- **Nothing wrote the status that makes shipping legal** (#86)
  `approved -> shipped` is not a transition the registry accepts; `approved -> planned ->
  shipped` is. RELEASE wrote the second hop and nothing wrote the first, so an item went
  from `approved` to a RELEASE refused *after* the work was done — a consumer had 87 items
  at `approved`, 9 with implementations behind them, and zero at `shipped`. IMPLEMENT now
  records the hop, and a test walks the statuses the briefs write against the registry's
  own transition table so a future stage cannot write one it would refuse.

- **A lint verdict charged the item for a tree it did not write** (#86)
  Scoping lint to the changed files degraded to absolute when the changed set could not be
  derived, and an item whose work sits on a lane branch has no checkpoint to read commit
  SHAs from — so the gate failed two items over 48 pre-existing findings neither had
  touched. There are three outcomes now: failed for a file the change touched, passed with
  the pre-existing count still reported, or warned when the set could not be derived —
  reported in full, attributed to nobody.

- **A failing test suite reported that it failed and nothing else** (#86)
  `go test` prints failing test names to stdout and reserves stderr for build errors, so a
  runner reading only stderr showed 5 of 8 failing modules with an empty diagnostic. The
  stdout *tail* was no better — a chatty suite fills it with log lines from tests that
  passed. The failing lines are extracted rather than tailed, with stderr still winning
  when a build fails. `coverage` and the no-manifest skip also stopped concluding
  "pre-code phase" from a missing file.

### Added
- **A withdrawn sign-off can be restored** (#86)
  `<!-- sign-off: RESTORED: reason -->`, honoured only after the withdrawal it answers —
  a restoration is a reply, and one written above the withdrawal it restores is not one.
  Without it `WITHDRAWN` was a state with no exit for a project whose discipline is to
  correct forward and leave the superseded reading in place. It also answers a withdrawal
  written only in prose, so a brief predating the marker is cleared by one reviewer line
  rather than by deleting a note the record is right to keep. A restored warrant is named
  on the passing result, because a warrant taken back and given again is not the same
  history as one never questioned.

### Fixed
- **RELEASE could not reach the only writer of a status line** (#86)
  `backlog_status.py` was invoked through a probe relative to the caller, from inside the
  lane's worktree where `.claude/` does not exist — so it resolved to the worktree root
  and failed with a missing file. That script is the only writer of a status line, making
  the failure silent and total: a consumer had 9 implementations, 8 reviews, 87 items at
  `approved` and zero at `shipped`. The guard added earlier the same day passed on it,
  because it checked that the repository appeared somewhere on the line while the kit
  probe stayed relative; it now checks the anchor itself.
- **A sign-off could be withdrawn in prose the gate could not hear** (#86)
  Three consumer items sat BLOCKED for two days while the gate reported `PASS — aligned at
  100%`: the withdrawal was written above boxes that stayed ticked with their `signed-by:`
  comments intact, so every agent that opened a brief read it and stopped while the gate
  counted ticks. `<!-- sign-off: WITHDRAWN: reason -->` now exists, in the same channel as
  NEEDS_SPLIT. Because those three withdrawals predate the marker, prose that reads as a
  withdrawal also stops the gate from *certifying* — it decides nothing, names the line,
  and tells the reviewer how to mark it. The second half of the defect was that
  `check_alignment_gate` re-derived its decision from the scorer's parts instead of reading
  its verdict, so any verdict the scorer grew fell through to ALIGNED; a test now asserts
  the gate names every verdict the scorer can return.
- **Pipeline stages ran in a worktree that does not contain the records they are judged by** (#86)
  `.claude/` and `.squad/*` are gitignored in a consumer repository, so a worktree carries
  neither — measured on a consumer: 19 plans in the repository, 0 in the lane's worktree.
  IMPLEMENT never named `.progress-{slug}.json` or `run_validation.py`, so five items
  produced implementation records and zero checkpoints, and four gates answered SKIP with
  "implement may not have run" about work with commits behind it; the stage also declared
  its own completion, which `cycle-implement.md` reserves for the validation gate. REVIEW
  resolved the kit relative to its own directory, which in a worktree holds no kit, so the
  criteria check failed with a missing file rather than a verdict. Records are now
  addressed at the repository in both briefs, the checkpoint is required in its canonical
  shape, the promise is the gate's to give, and the criteria run against the lane's tree
  rather than the pre-change one.
- **Typecheck and lint answered a JavaScript question on every other language** (#86)
  The test half of the `/implement` gate was made language-aware in August; typecheck and
  lint were not, and skipped with `package.json absent — pre-code phase` on any repository
  without a `package.json`. Measured on a consumer: a Go workspace with 8 modules and 1918
  lines of new Go carried that line on four of seven reviews, for typecheck, lint and
  project gates at once. The repository is not in a pre-code phase; it has no
  `package.json`, which is a different statement. `go build` / `cargo check` now run for
  typecheck and `gofmt` / `cargo clippy` / `ruff` for lint, per language present, with
  `go.work` modules walked individually. A missing toolchain fails typecheck and skips
  lint; neither becomes a silent pass. Lint is judged against the files the change wrote —
  that consumer's tree carries 48 pre-existing `gofmt` findings, none touched by the item
  under validation — and those findings are still reported on the passing result rather
  than hidden.
- **The pipeline named branches after ticket numbers and cut worktrees in `/tmp`** (#86)
  A lane was `pipeline/b-018` at `/tmp/squad-worktrees/b-018-<epoch>`. `§ 5.1` of the
  engineering rules bans a ticket number in a branch or directory name — the number dies
  and the name stays, pointing at a tracker that may not resolve it — and a consumer that
  had just removed 5 branches and 5 worktree directories by hand had them regenerated by
  the next run. Lanes are now named from the item's heading
  (`pipeline/repoint-frozen-tree-adr-defines`), with no fallback to the id: an item that
  cannot be named by its subject is refused so the title gets fixed. Worktrees move to
  `$HOME/.squad-worktrees/`, because a lane holds unmerged commits and `/tmp` is cleared
  by the OS, by a reboot, and by anyone tidying up — measured on that consumer, where a
  wipe took two in-progress sweeps while two lanes holding six commits sat there. The id
  still travels in the commit message.
- **One `(none)` discarded every dependency in a plan's section, so CVE bumps went unaudited** (#86)
  The explicit-none marker was searched across the whole `## Dependencies` body, so a
  `(none)` anywhere in it returned no dependencies at all — the gate did not apply and no
  audit was required. The shape that triggers it is the one `deps-audit/SKILL.md`
  prescribes verbatim: an Existing table carrying real packages above a Removed table
  whose single row reads `(none)`. A security-driven bump of an *existing* dependency is
  the case where an audit matters most, and it was the one case the gate could not see. A
  consumer plan raising a router past three fixed advisories documents having hit this and
  routed around it in prose. The marker is now scoped to the subsection carrying it,
  except in the preamble — a declaration made before any subsection exists still speaks
  for the section. Reading rows also required tightening what counts as a declaration: a
  package is named in the first cell of a table row or at the head of a bullet, not
  mentioned in a sentence, and a token ending in a file suffix is a manifest rather than a
  dependency, and a bullet declares a package only when the package opens it — a sentence
  that merely contains a backtick (`- **B-057** — ... exits 5 on \`unhomed-logic\``) named a
  gate, not a package. Measured across 19 consumer plans: 46 false entries removed, the
  router bump now visible.
- **The TDD gate refused executable Go and accepted a prose sentence** (#86)
  Measured on 19 consumer plans, 8 blocked: `RED: test_xxx` passed the gate and
  `RED: TestXxx` — the same claim in Go's spelling — did not, while "the tests should be
  green after this" sailed through. Six more plans ran real commands and stated what each
  must print, and were refused because the only shell oracle recognised was a backticked
  command followed by the word "prints". The gate was matching one house style, not
  executability. Four shapes now count, each of them greppable: a native test declaration
  (Go, Rust, JUnit, testify), a RED that names its failing test in any casing, a command
  paired with a stated expectation, and a task that declares why it asserts nothing while
  still showing what it runs. Seven agents had hit this across five items and every one
  refused to rewrite its TDD bodies to clear it. All 19 plans pass now, and all 19 still
  block when their TDD sections are replaced with a promise.

- **A CHANGELOG example inside a plan truncated the task quoting it** (#86)
  A literal `## [Unreleased]` inside a fenced snippet was read as the next heading, so
  the task ended there and its own `#### TDD` section was never seen — the plan failed
  for a section it had. Headings are now located in a fence-blanked copy of the same
  length while the body is still sliced from the original.
- **Approved items never reached the scheduler, so the IMPLEMENT fix reached 4 of 92** (#93)
  `queue` is what SELECT hands to `/discover-plan`, and `cycle-maintenance.md § Chain`
  sends an approved item to `/plan-write` instead — so an approved item is correctly
  absent from it. `pipeline_orchestrator.from_selection` built its lanes from `queue`
  alone, so a consumer's registry of 87 approved and 5 triaged items handed the
  scheduler FIVE. The stage machine handled an approved item correctly the whole time
  and was never given one through the documented path, which is why tracing the machine
  directly proved it worked and proved nothing about the system — the same shape as the
  demotion that made IMPLEMENT unreachable, one seam further out. `select_backlog_item`
  now reports `awaiting_plan` beside the queue and never inside it, and the scheduler
  enters those items at PLAN rather than DISCOVER: `approved` records that DISCOVER ran,
  and re-measuring would discard the opportunity file the decision rests on. Measured on
  that registry: 5 items visible before, 62 after.

- **The pipeline could not reach the stage that writes code** (#93)
  `STATUS_ON_ENTERING` wrote `triaged` when an item entered PLAN — reading "DISCOVER
  finished, so the item is measured", which is true and was already recorded.
  `cycle-backlog` puts `approved` AFTER `triaged`, and only `approved` may become
  `planned`, so the map DEMOTED an approved item on its way into PLAN and
  `REQUIRES_STATUS` refused `planned` one stage later. Every item parked at IMPLEMENT
  whatever its status had been. Traced on a consumer that ran three days and shipped
  nothing: the park looked like a gate holding rather than a scheduler contradicting
  itself, which is why it survived — the symptom was indistinguishable from the system
  working. A status only moves forward now, and an approved item runs the whole chain to
  `__done__`.

- **The scheduler had no preference, so everything advanced one phase before anything advanced two** (#93)
  Lanes were filled in registry order, so an item at DISCOVER took a lane ahead of one at
  IMPLEMENT that was three stages from landing. Measured on a consumer: 44 discovers on
  day one against 3 plans, 29 aligns on day three against 1 implement. With 93 items that
  means nothing reaches RELEASE until nearly everything has crossed every phase before
  it — 501 artefacts, zero shipped. Eligible work is now ordered furthest-along-first:
  finishing beats starting, because an item at IMPLEMENT is closer to being work somebody
  can use. Ties keep registry order, so `cycle-maintenance`'s fairness rule still decides
  within a stage.

- **The criteria executor ran whatever a criterion's sentence contained** (#96)
  It executed every runnable span in a bullet, and a consumer measured what that costs:
  a criterion carrying `git stash push` was run, and it pushed SEVEN entries onto a
  stash stack shared by six worktrees — one carrying twenty uncommitted CHANGELOG lines,
  which left the tree. The file's own docstring already said *"running commands out of
  a document is the risk it is"*, and saying it is not protecting against it. Commands
  are now an ALLOWLIST, because a denylist of destructive things is never finished and
  the cost of one gap is somebody else's work: reading tools plus the test runners a
  criterion legitimately needs, and for `git` only the subcommands that read — `stash`,
  `checkout`, `reset`, `clean`, `worktree`, `push`, `merge` and `restore` are absent on
  purpose. `bash -c '<script>'` is unwrapped and inspected, because a split that does
  not enter the quotes lets exactly the measured case through; `python3 -c` and `node
  -e` are refused outright, since a shell script can be unwrapped and a Python one
  cannot. A refused clause is reported as unverified and NEVER as sound, with the reason
  and an invitation to run it by hand — including for the common legitimate case of a
  binary the criterion built, which is refused deliberately because that binary can do
  anything.

- **The pipeline ran five stages and stopped, so an unattended run never landed work** (#93)
  `/pipeline` scheduled `discover → align → judge → plan → implement` and ended there.
  REVIEW and RELEASE did not exist, and the skill still claimed it did not run IMPLEMENT
  either — a sentence that stopped being true on 2026-09-02 and was never corrected. So
  a consumer asking for an unattended run got five stages and a stop, every time,
  whatever was fixed upstream: the gates were never the obstacle, the chain ended before
  the work could land. REVIEW audits the diff read-only — a reviewer who may edit cannot
  be trusted to report what they found — reproduces the pre-change test failure, and
  re-runs the acceptance criteria against the tree AS IT IS at review time, because a
  verification does not survive the tree it measured. RELEASE carries `Edit` and not
  `Write`, writes one changelog entry on the lane's own branch, and moves the status
  through `backlog_status.py`; it does not cut a version or merge, because both have
  blast radius beyond one item. CODE-QUALITY gets no stage because `run_validation.py`
  already invokes it inside IMPLEMENT, and ACCEPTANCE gets none because it validates a
  milestone rather than an item.

- **A guard that passes today is the criterion working, not a defect** (#96)
  `check_criteria_discriminate` reported a non-regression guard with the same sentence
  it reports an inert criterion — *"will pass after the work too"* — and the distinction
  is the whole point: `"the declared terminal sets are untouched"` passing today is the
  criterion working, while `"the four divergences are gone"` passing today is an item
  that closes on work nobody did. The briefs already carry the label in their own words
  and a judge had kept one deliberately for that reason; the tool did not read it. A
  criterion that declares itself a guard is now reported in its own category and
  excluded from the refusal count. Detection is narrow on purpose: without a label a
  criterion counts as a defect, because a defect called a guard is silence while a guard
  called a defect is a question. Re-measured on a consumer: B-023 went from 4 refusals
  to 2 defects and 2 guards.

- **The clause parser invented clauses out of tool names** (#96)
  A criterion mentioning `awk` and `diff` in the prose around its command had both
  executed as clauses, and `awk` alone exits 0 — so the parser inflated the count of
  inert clauses with its own artefacts. A tool name is one token; a command has an
  argument, an operator or a pipe. Self-sufficient commands (`true`, `false`, `pwd`)
  keep working with one.

- **A criterion verification is stamped with the tree it read** (#96)
  A verification does not survive the tree it measured, and the proof came from this
  kit's own hand: writing `go | api/go.mod | ENABLED` into a consumer's language config
  to unblock its quality gate turned a criterion of that consumer's B-034 — a `grep -c`
  over that same file — from discriminating to inert in the same minute. The criterion
  did not change; the tree did. The run now reports the HEAD it read against, says when
  the working tree is dirty because those answers do not reproduce from the commit
  alone, and states that a reading expires: run it against the tree you are about to
  implement on, not against a record of a tree that has moved.

- **A criterion's clauses are read separately** (#96)
  `check_criteria_discriminate` ran only the FIRST runnable span of a bullet, so the
  second half of `<gate exists> AND <test passes>` was never executed — not folded into
  one verdict, silently skipped. And a single verdict over a conjunction cannot find a
  vacuous clause masked by one that fails for an unrelated reason: measured on a
  consumer's B-067, clause 1 returns 0 because the gate is not written yet and clause 2
  (`go test -run TestGateRegistryParity`) exits 0 with `[no tests to run]` because the
  test exists nowhere. The conjunction fails today, so one reading calls the criterion
  sound — and when the gate is built the whole thing passes with clause 2 measuring
  nothing. Every runnable span is now a clause with its own expectation, read from the
  text that follows it: `prints 1` and `exits 0` are different questions, and applying
  the bullet's first one to both made a clause that exits 0 read as failing. A criterion
  carrying any already-passing clause is refused, and the report separates the two
  shapes — passing as a whole, versus failing as a whole while carrying a half that will
  survive the work.

- **The cross-repo detector charged an author for enumerating a negative** (#B-024, #B-027, #B-029)
  `check_opportunity_completeness` collected every known repo name appearing anywhere in an
  opportunity's Blast Radius and required an ADR for each, with no notion of negation. So an
  author who named a repo **in order to record that it was checked and is NOT reached** paid for
  a cross-repo decision that does not exist — and the only way to clear the gate was to delete
  the measurement, which is the strongest thing such a corner can carry.

  Measured 2026-09-12: three independent DISCOVER agents hit this in one session on one project.
  Two wrote a defensive ADR for a non-existent decision; the third relocated the measurement out
  of the corner it belonged in and said so in the document. None deleted the evidence. The
  checker cost three authors work and bought nothing.

  A `<!-- NOT-REACHED: <repo> [<repo> ...] -->` marker in the Blast Radius now subtracts the
  repos it names, following the kit's existing marker shape (`<!-- UNKNOWN: … -->`,
  `<!-- ADR-DEFER-WIRING-B: … -->`). It only ever subtracts, only what it names explicitly: an
  empty marker is not a blanket exemption, and a repo genuinely reached is unaffected by one
  appearing elsewhere in the same corner. Three behavioural tests cover all three directions.

  Deliberately NOT retroactive: opportunities written before the marker existed score exactly as
  they did, so the fix adds a capability rather than loosening a gate.

- **The stop gate graded a Helm chart's own template as a secret** (#B-033)
  `SECRET_FILE` opened with `[a-z0-9_-]*` before `secrets?`, so any prefix glued to
  the word matched: `externalsecrets.yaml` — chart SOURCE, which contains template
  directives and no value — was reported as a secret-shaped file. A prefix must now
  be SEPARATED by `.`, `_` or `-`, so `secrets.yaml` and `app-secrets.yaml` keep
  matching and the template does not. Measured on a consumer 2026-09-12: the gate
  fired nine times in one session over a file that session never opened, and the
  only escape offered is the env var this suite's own docstring calls the thing
  that stops the gate protecting anything. Three behavioural tests cover both
  directions, including the positive controls that must keep blocking.

  Known and NOT fixed here: `changed_files()` folds `git diff HEAD~1..HEAD` into
  "this session's diff", so a commit made BEFORE the session is reported as session
  work. That is what put the template in front of the pattern in the first place.
  Fixing it needs a session-start marker the hook does not have, so it stays open.

### Added
- **Alignment depth is derived per item, so a small change stops costing a 40 KB document** (#96)
  Measured on a consumer over three days: 93 items, 501 artefacts, 4 implementations,
  **zero shipped**, 78 hours of cycle time per item — and 2,740 KB of alignment briefs
  signed by a person **zero** times, each 40-50 KB, longer than the code it described
  (40 to 250 lines across the four items that reached a branch). The walkthrough HTML
  added 1,032 KB across 38 files nobody opened. `cycle-brainstorm` and `cycle-design`
  were already conditional; this phase was not, so deleting an unreferenced package
  crossed the same phases as redesigning the data plane.
  `classify_alignment_depth.py` answers LOCAL or FULL from the item itself. LOCAL keeps
  everything a later phase consumes — requirements with ids, acceptance criteria that
  execute, out-of-scope, closed questions, the signature — and drops the prose and the
  walkthrough. Any one of four signals forces FULL: evidence spanning modules, a blocked
  item, a DoD naming no command, or mode `evolve`. FULL is the default, because
  shallower is the irreversible direction: a brief nobody wrote cannot be consulted
  later, and one nobody needed only cost time. Measured on that registry, 34 of 93 items
  (37%) are LOCAL.

- **`/as-is-to-be` — what this system is today, and what it becomes** (#89)
  A backlog is a list of tickets and nobody can hold twenty-three of them in their head
  to answer what the system will be when they are done. Both columns of a gap analysis
  were already in every item and no page had put them side by side: `evidence` is a
  measurement of the present that DISCOVER refuses to accept as a hunch, and `dod` is a
  statement about the future that gate G4 refuses unless it can fail. The projection
  adds no field and asks no question at intake. It states three limits above the
  content, because a list of promises reads like a plan and the failure mode is being
  read as complete: the current state is only what these items happened to measure, the
  future state is not checked for coherence, and an item is a hypothesis until DISCOVER
  measures it.

- **`traces_to` gets a producer, and the backlog can finally say what it leaves out** (#82, #86)
  The field was read by `build_agenda.py`, described in the product owner's agent file,
  and pointed at `OBJ-N` ids `/brainstorm-objectives` genuinely produces — and it was
  written zero times in 651 items, because `cycle-backlog.md` never listed it among an
  item's fields and `/backlog-item` never asked. A field read by one consumer and written
  by no producer is not a schema; it is a plan somebody had. It is in the schema table
  now, and Q5 of the intake grill asks for it whenever the project has declared
  objectives. What the link buys is the one question a registry cannot answer about
  itself: reading items tells you whether you want each of them, and never what is
  missing, because an item nobody wrote is invisible to any report rendered from items.
  `check_objective_coverage.py` computes the three states the link makes visible — an
  objective no item serves, an item serving no objective, and a citation pointing at an
  id that is gone — and the approval brief now opens with them. With no objectives
  document it reports NOT MEASURED and names the document, rather than calling every
  item an orphan against a standard the project never adopted.

- **`/backlog-approve` — the decision a backlog was never asked for** (#86)
  `cycle-backlog.md` calls `approved` a commitment, *"somebody decided"*, and forbids
  reaching a plan without it. Measured across four registries: 325 items, 243 of them
  `shipped`, and **zero** at `approved`. The chain diagram in that same document routed
  `triaged` straight to `/plan-write`, so the gate was bypassed in the doctrine as well
  as in practice — the same shape recorded when `planned` was zero everywhere, and the
  same cause: a status nothing asks for is a status nobody writes. The skill renders the
  registry as one page carrying, per item, what it claims, what changed that makes it
  worth doing now, how it closes, and whether the files its evidence cites are still on
  disk; a person ticks and signs; `apply_approval.py` moves exactly those, through
  `backlog_status.py` and never around it. Unticked is not rejected. Every box starts
  empty, because a pre-ticked list makes the default yes-to-everything and turns the
  signature into a formality.

- **The board draws the issue tracker beside the cycle** (#84)
  `BACKLOG.md` says what the project decided to do; the tracker says what the people
  using it ran into. The board showed the first and not the second — measured on this
  repository, fourteen open reports were visible nowhere while the cycle they were
  filed against advanced on screen. Issues are grouped by the stage a fix has reached,
  read from labels rather than from GitHub's two states, because OPEN/CLOSED cannot
  express the window between *merged* and *installable* that the issue lifecycle keeps
  an issue open for. The tracker is read on its own thread at its own interval: one
  `gh issue list` took 1.7s against a watcher that runs every 0.5s, so reading it on
  the request path would have traded a board that re-renders on a file save for one
  that stalls. A tracker that could not be read renders as the reason it could not,
  plus the flag that fixes it — never as four empty lanes. `--no-issues` removes the
  tab entirely rather than leaving an empty one.

- **`cycle-design` — the system is drawn before a backlog is filed against it** (#75)
  `brainstorm-pieces` names PIECE-N as *"a responsibility with a boundary"* and states
  its own limit: *"the mapping is not decided here."* `backlog-init` then inventories
  repos from disk. Nothing joined the two, so items were filed against a system nobody
  drew — and the two decisions no product retrofits, state ownership and trust
  boundary, were never forced. The new phase produces five drawings, four of them
  mandatory because each answers a question that is cheap now and expensive later:
  what the central object's lifecycle is, where untrusted code stops, what the real
  call order is when things fail, and what survives a process death. The component map
  is DERIVED from those four and never drawn first — a map drawn first looks like
  design happened and forces no choice. `check_design_completeness.py` refuses a
  document with no mermaid block, a diagram filed in the wrong slot, a stub, a
  placeholder, and a `PIECE-N` with no place in the map; it ends at `AWAITING_REVIEW`
  until a person signs, because whether a state machine has the RIGHT states is not a
  countable property.

### Changed
- **`/design` names two renderers, and says what each one proves** (#75)
  The render step pointed only at `/diagram-design:import-mermaid`. `archify` is now the
  other option, with the slot-to-type mapping written down — the five slots map almost
  one to one onto its five diagram types. What it adds is a different question than this
  phase's gates ask: `check_design_completeness.py` asks whether a drawing EXISTS, sits
  in the right slot and is not a stub, while archify asks whether it is READABLE — it
  simulates a 1440px desktop and refuses a projected font under 6px, a label overlapping
  a node, or a node outside the viewBox. It also constrains the drawing, which the step
  now states before anyone picks it: a workflow column is a rank in 0..5 whose main path
  may not move backwards, and a dataflow carries at most five stages. Both renderers stay
  optional and the phase depends on neither; the mermaid is still the drawing.

### Added
- **`check_chain_preconditions.py` — a chain that cannot finish no longer starts** (#93)
  A consumer ran the loop for hours and produced 85 items, 57 opportunities, 39 panels
  and 13 plans scoring 89-100 structurally — and zero implemented, because every plan hit
  `no_languages_audited` at the quality gate. The cause was one unconfigured file,
  readable in milliseconds before any of it started. Nothing was wrong with the work; the
  refusal arrived at the end, after the effort, and item by item, which makes a property
  of the installation look like a property of each item and sends the next session to fix
  the wrong thing. It did. The gate now runs first in `cycle-maintenance`'s loop and
  refuses to start on four conditions that stop every item whatever anyone does to the
  item: a language config with no ENABLED row, an enabled row whose manifest is absent
  (the case an enablement check alone hides — `go | go.mod` is well formed and audits
  nothing in a `go.work` workspace), an empty routing table, and a missing registry. A
  judgement is deliberately not checked: a gate that waits on a decision is a gate that
  never lets you start.

### Changed
- **An item the loop finds is approved when it is filed** (#93)
  A sweep finding is born `approved`, attributed to `system/autonomous-sweep`. Running
  the loop unattended IS the decision to act on what the loop finds — a sweep is not a
  proposal awaiting an answer, it is the execution of an answer already given, and
  requiring a person per finding withdraws the decision already made and makes the
  autonomy conditional on somebody being awake. An item whose `source` is `human` is
  unaffected: born `raw`, and `/backlog-approve` still renders only those, because a
  person deciding what a person asked for is the case that gate was built for. The new
  `approved_by` field keeps the two apart for the same reason `signed-by: human/…` and
  `signed-by: judge/…` are different claims — they are not worth the same, and a
  registry where everything is `system/…` is one nobody has read. The preflight reports
  the split rather than only the count, because a loop that approves its own findings
  can feed itself and the only bound is somebody seeing the number before the next run.

### Added
- **The system never starts on a backlog nobody approved** (#93)
  `check_chain_preconditions` now refuses to begin when no item is at `approved`. It has
  the same shape as the other preconditions — a fact about the installation that no
  amount of good work overcomes — because an unapproved registry is not a queue of work,
  it is a queue of hypotheses, and a run over it decides by inference, item by item, the
  one question `cycle-backlog.md` reserves for a person. Measured on a consumer: 85 items
  at `triaged`, zero at `approved`, and hours of execution against a list nobody had said
  yes to. ONE approved item satisfies it: a backlog is approved incrementally and the
  loop works one item at a time, so demanding the whole registry be decided before
  anything starts would make the preflight the thing it refuses. The refusal carries the
  three commands that clear it.

### Added
- **`check_criteria_discriminate.py` — acceptance criteria are run, not read** (#96)
  `score_alignment` grades a criterion `executable` from a text match over the bullet: it
  asks whether a command is NAMED, never whether it could run or whether its answer
  distinguishes anything. Measured on a consumer: a brief scored 14/14 executable where
  two criteria could not pass at all, and `go test -run <pattern-that-matches-nothing>`
  exits 0 with `[no tests to run]`, so eight criteria in one brief were satisfied by
  writing no test. The new script runs each criterion against the tree as it is and
  refuses the ones that already pass — a criterion that passes before the work cannot
  tell a finished item from an unstarted one. It marks as undecidable, never as sound,
  the ones whose bullet does not state what it expects, and it states that it checked one
  of three states: the intended state and a deliberately wrong implementation the
  criterion must reject are not covered, and the third is what catches a criterion
  measuring a name rather than a behaviour. Measured on three real briefs: 3 of 13
  criteria in one already passed.

### Fixed
- **kit#18's exemption had no effect on any brief that followed the template** (#96)
  `_without_section` stopped at the next heading of ANY level, so a section with a
  subheading was cut at the subheading and everything under it stayed in the text the
  caller believed it had removed. `## Questions answered` is exactly that shape, and
  this skill's own SKILL.md prescribes it — *"`### Session YYYY-MM-DD` then `- Q: … →
  A: …`"* — so the kit prescribed the structure that voided its own exemption. A brief
  whose only imperfection was one honestly declared open question was charged twice,
  three points of thirty-four, about 9% against a 90% threshold, and the cheapest way
  past was to delete the question: the exact evasion kit#18 was written to remove. A
  section now ends at the next heading of the same level or shallower. Measured over 38
  real briefs: 37 clean afterwards.

- **`<angle-brackets>` reverted out of the placeholder scan, one day after being added**
  (#96) They went in to catch `<gate-name>`, reported by a consumer as invisible.
  Re-measured over 38 briefs the next day: 23 were charged, and the hits were three
  different things wearing one shape — `err=<nil>` (a Go literal quoted from real
  output), `-C <path>` (CLI syntax in prose), and `START_SHA=<sha>` (a parameter a
  criterion needs filled before it can run). Only the third is a defect, and it is not
  the one `no_placeholders` measures: that criterion asks whether a DECISION is open,
  while an unfilled command parameter is a question about executability, which
  `check_criteria_discriminate.py` answers by refusing to run the criterion. Charging
  two points for a Go nil made the column report the wrong thing loudly, which is how a
  reader learns to skip a column.

### Fixed
- **Three defects in the acceptance-criteria scorer that agreed with each other** (#96)
  `_UNRESOLVED_RE` matched `{{CAPS}}` and not `<angle-brackets>`, which is the notation
  these briefs use; `_PRESENCE_RE` exempted on `wc -l` in any position, so a criterion
  that counts something and asserts zero — passing exactly when the subject is absent —
  was exempted by coincidence; and `_EXECUTABLE_RE` grades a criterion executable from a
  text match, so one carrying an invisible placeholder scored beside a scan that could
  not see it. Measured on a consumer: a brief with eight occurrences of `<gate-name>`
  reported "No unresolved placeholder anywhere in the brief — none" together with "10/10
  executable", over five commands its own prose said did not run. Re-measured over 19
  briefs after the fix: vacuous criteria 0 → 61, and six briefs carrying a placeholder
  that had been invisible. The composition is broken — a criterion with an unresolved
  placeholder is no longer graded executable — but grading remains a text match, and
  executing criteria against three states is tracked separately.

- **The allowlist key the gate publishes matched nothing** (#95)
  The gate publishes `allowlist_key` — `go|.|mutation_low|soft_cap_mutation_deferred_go`
  — in the finding, the JSON and the report, and `is_allowlisted` matched the symbol
  column against `symbol_or_line`, which for that finding is `d4`. Copying the advertised
  fields produced a well-formed six-column row matching nothing, and `load_allowlist`
  validated all six without complaint. Measured with a control: the published key and
  `ZZZ_NO_SUCH_SYMBOL` were both `NOT_LISTED` — the advertised key was indistinguishable
  from an invented symbol, and on a consumer the false claim that it worked reached a
  brief and a panel vote before anyone tested it. Matching now accepts either the symbol
  or the key's own symbol field, so existing entries keep working unchanged.

- **An expired allowlist entry was never announced** (#95)
  `is_allowlisted` returns ACTIVE / EXPIRED / NOT_LISTED and the only consumer branched
  on ACTIVE, so an exemption whose sunset had passed fell into the same `else` as one
  that was never written. Golden rule § 4 promises the entry listed under *"Allowlist
  hits — expired"*; nothing implemented it. Measured with a sunset of 2026-01-01:
  `FAIL_SOFT`/70 with the word `expired` absent from the JSON, from stderr and from the
  report. A dated exemption is a promise to revisit and the date is the whole mechanism —
  the finding re-firing at full severity is correct and is not the notification, because
  it looks exactly like a finding nobody ever exempted. Expired rows are now named on
  stderr and carried in `expired_allowlist`, always present so an empty list answers the
  question an absent key would ask.

### Fixed
- **A fixture rewrote the real `rules/domain-routing.txt` and only restored it on teardown** (#87)
  The discover-confidence end-to-end fixture wrote the routing table into the repository
  whenever the shipped one held no data rows — which is how the kit ships it — and
  restored it after `yield`. That restore was the entire safety mechanism, and teardown
  does not run when a process is killed: an interrupted slice left the checkout holding
  two lines of test fixture in place of a 29-line rule file, found days later by an
  unrelated `git status`. The fixture now builds a mirror of the repository in
  `tmp_path` — every top-level entry symlinked, so repo-relative pointers still resolve,
  which is the property the real root was there for — and writes only into the mirror.
  Two tests assert the property directly rather than trusting a teardown to be careful.

- **The plan gate reached the network by default, and its answer changed every run** (#91)
  `cq_invoke.py` appended `--no-network` only when `CODE_QUALITY_NO_NETWORK` was set, and
  nothing in the kit or in any measured install ever set it — so every plan gate
  everywhere took the networked path. That path is not reproducible: measured on a
  consumer, four runs of one module answered 97, 76, 55 and 36 unverified modules, each
  seeding a hard cap that is neither baselinable nor ADR-dismissible. Thirteen plans
  scoring 89-100 structurally sat at INVALID because of it. The kit had already accepted
  this argument for the baseline — `--write-baseline` forces offline because *"a baseline
  recorded with the network on is worthless"* — and the asymmetry was the defect: the
  baseline was protected from irreproducibility and the gate that blocks delivery was
  not. Offline is now the default and `CODE_QUALITY_NETWORK=1` is an explicit opt-in;
  `CODE_QUALITY_NO_NETWORK` still works and still means offline.

- **A config with no enabled language never said why it audited nothing** (#91)
  The run reported `verdict: INVALID`, `hard_caps_triggered: ["no_languages_audited"]`
  and `skip_reasons: {}`. The stable id names the symptom; nothing named the cause, which
  on the measured consumer was the shipped template — 83 lines, all commented examples,
  never configured for that project. A session read the id and concluded a backlog item
  had to be implemented before anything could move; the fix was one configuration row.
  The reason now lands in `skip_reasons`, where a reader looks for why nothing happened,
  and says it is configuration rather than a defect in the code under test.

### Fixed
- **The published chain named nine phases and the kit runs ten** (#75)
  `plugin.json`, `marketplace.json`, `HOW-TO-USE.md` and `rules/squad-map.md` all
  described `BRAINSTORM → BACKLOG → …`, written before `DESIGN` existed and not updated
  when it shipped. The marketplace description is the first thing an adopter reads, and
  it was missing the phase that decides what gets drawn before a backlog is filed
  against it.

### Fixed
- **The alignment scorer counted a wrapped line as a requirement, and scored a walkthrough it never opened** (#B-013)
  Both measured in a consumer install and ported here, because a fix written inside a
  consumer's `.claude/` reaches exactly one machine — that directory is gitignored
  everywhere, so the correction produces no diff and no release.

  `_bullets` matched `^\s*[-*\d]`, so ANY line starting with a digit became a bullet — and
  a wrapped requirement routinely continues on one ("…answers under\n800ms at p95."). The
  report then lied in both directions at once: a single requirement with no number of its
  own was reported as `1/2 measurable`, because the continuation became a second
  requirement AND was credited with the digits that had been wrapped off the first. A
  bullet is now `-`, `*`, `+`, or an ordered `1.` / `1)`; a bare digit is prose.

  Criterion 17 scored `_tri(bool(html), bool(html))` — the presence of a `.html`
  REFERENCE, twice. A brief citing a walkthrough nobody generated took full marks for
  producing one. The citation is now resolved on disk, against the brief's own directory
  and the working directory. A gate reporting that it verified something it never opened
  is the fabricated mechanism this kit exists to refuse, and this gate decides whether an
  item may be built at all.

  Two regression tests, each verified by mutation.

### Added
- **`/sign` — the one act a machine may not perform now has a mechanism** (#74)
  Four points in the chain stop until a person signs, and a person had no tool for it.
  `alignment_judge.py` can sign a brief as a judge; `score_product_alignment.py` states
  its own limit — *"it cannot supply the signature, and there is no flag that makes
  it."* Both refusals are right, and the consequence was that the only act reserved for
  a person was the only one with no mechanism: edit the markdown, find the section,
  change `[ ]` to `[x]` in the right place, add an HTML comment whose syntax lives in a
  regex inside someone else's script. The default run previews and writes nothing —
  there is deliberately no `--yes`, because a tool that makes signing frictionless turns
  a signature into a stamp. Refuses to re-sign, and refuses an author signing their own
  work unless they pass `--despite-authorship "<reason>"`, which does not silence the
  check: it writes the fact and the reason into the document, stating that the signature
  is weaker than one from a reviewer who did not write it. Measured on this kit: one
  author across its whole history, so without that escape the tool would be useless
  exactly where it is needed.
- **The mirror of `check_orphan_verdicts.py`: every verdict a skill INSTRUCTS is one its
  cycle declares** (#70) That sweep asks whether every declared verdict is reachable.
  Nothing asked the other direction, and it fails louder — `cycle_events.py` REFUSES an
  undeclared verdict, so the phase records **nothing at all**, and `cycle-maintenance.md`
  already names the cost: work left silent "is indistinguishable from one nobody touched".
  Measured 2026-09-10, closing a live session: **five skills passed a halt-loop completion
  promise where a verdict goes** — `VISION_WRITTEN`, `OBJECTIVES_WRITTEN`, `TRD_WRITTEN`,
  `PLAN_WRITTEN`, `OPPORTUNITY_COMPLETE`. Three are the brainstorm cascade, phases 1-3 of
  the only cycle a human attends; the other two are the **only** emitters of `end` for
  their cycles, so `discover` and `plan` never closed either. All five now emit
  `AWAITING_REVIEW` — the document exists and nothing has scored it, which is what is
  true. `check_emitted_verdicts.py` keeps it that way, honouring the runtime's rule that a
  rule with no `## Verdicts` section permits any verdict (`implement` and `code-quality`
  rely on it) while separating that from a `--cycle` naming no rule at all.

- **The prose an agent executes now names the write root, and a gate keeps it there** (#69)
  `check_write_containment.py` proves that no module outside `squad/paths.py` spells a
  data root, and it strips prose before matching — correctly, since the kit argues in
  prose about the very directories it forbids in code. A `SKILL.md` is not that kind of
  prose: it INSTRUCTS, and an agent following `Persist to records/brainstorms/…` creates
  a legacy root without importing the owner or running a mechanism. **Measured when a
  live `/brainstorm-vision` session hit it: 164 legacy-root instructions across 49
  files**, 19 of them `SKILL.md`, while `rules/records-location.md` had said the opposite
  since 2026-09-09 — *"`<project>/.squad/` is the one write root. Always, in every
  layout."* Two contracts disagreed and the one an agent reads at execution time won: the
  session wrote its record to `records/` and its vision to `wiki/`, outside the root every
  reader resolves first. All 164 corrected, and `check_prose_write_paths.py` scans
  `skills/`, `commands/`, `agents/` and `hooks/` so the next edit cannot reintroduce one.
  It deliberately skips `rules/` and `docs/`, which argue rather than instruct — scanning
  them would flag `records-location.md` for stating the rule this enforces. Prose that
  genuinely names a legacy root marks itself `<!-- write-path: reason -->`, and an empty
  reason does not count, for the same reason it does not in `rules/english-only.md`.

### Fixed
- **`cycle-discover.md` used a verdict it never declared** (#70) Gate G-P states *"no
  record yet is `AWAITING_REVIEW` — complete and unsigned, neither a failure nor a pass"*,
  and the `## Verdicts` table did not list it. So the contract relied on a state it had
  not declared, which is why `/discover-execute` had no honest verdict available and
  reached for a completion promise. Declared.
- **The board coloured green two events that never arrived** (#70) `board.html` listed
  `PLAN_WRITTEN` and `OPPORTUNITY_COMPLETE` among `GOOD_VERDICTS`. Neither was ever a
  verdict, so nothing ever emitted one. Replaced with verdicts `rules/verdict-bands.txt`
  actually bands as clean. **Known gap:** the board still keeps its own copy of the bands
  rather than reading that file — two copies of one fact, and a separate item.
- **`records/references/` was still being cited as a live zone, 9 days after it was
  retired** (#69) `rules/reference-provenance.md` retired it on 2026-09-01 in favour of
  `study-material/` and states that it is "no longer guarded". Ten places still pointed
  at it as the study zone — including `plan-write`'s `ls records/references/`, two
  golden-rule clauses whose checkers resolve the live path, and `deps-audit`'s exclusion
  list. Repointed. Two others describe the retirement itself and keep the name behind an
  exemption marker. `skills/implement/SKILL.md` also claimed `boundary-check.py` guards
  the retired zone; measured, it guards `study-material/` alone (`boundary-check.py:50`),
  so the claim was removed rather than repointed.

- **A runtime proof that everything the Squad produces lands in `.squad/`** (#72)
  `check_write_containment.py` proves a static property — no module outside
  `squad/paths.py` may spell a data root. It cannot see a writer whose destination
  never passes through `squad.paths`. Tracing all 135 write call sites through the AST
  left 64 UNKNOWN, so `check_produced_files.py` runs 18 mechanisms in a scratch project
  and looks at the disk instead. It reports its own coverage on every run, refuses to
  count a probe that errored as one that ran, and reads `rules/write-exemptions.txt`,
  where every file allowed to sit outside carries a class and a reason.
- **`rules/write-exemptions.txt`** — the eight files that cannot live under the write
  root, each naming what forces it: Claude Code resolves agents and skills by
  directory, and `BACKLOG.md`/`CHANGELOG.md` are opened by people at the root (#72)
- **`/squad-fit` — a diagnosis of whether the squad can run in a given project** (#71)
  The kit ships `agents/<domain>.md` empty on purpose, so every project has a gap on the
  day it installs. Nothing measured that gap: the kit could report one unroutable item
  (`route_domain.py`) and one unfillable seat (`check_panel_capability.py`), after the
  work had already been selected. This asks both of everything at once, plus whether the
  project's own skills carry an SOP and are visible to the validator, and answers the
  question a person asks before adopting — what has to be written, and what breaks until
  it is. Read-only; it never writes the specialist it says is missing, because a
  correctly-named stub routes items into an empty prompt.

### Changed
- **Domains derive from the module boundary the project already declared** (#73)
  `detect_domains.py` gave a single repository exactly one domain, however many
  modules it held. A `go.mod` / `Cargo.toml` / workspace `package.json` is a
  compilation and versioning boundary somebody committed to, and invariants differ
  exactly there — a module has its own dependencies, its own build, and its own answer
  to what may import it. Modules nested under another join their ancestor; what
  remains groups by first path segment, so six thin packages under `packages/` stay
  ONE domain (the measured case that argued against per-package domains) while
  top-level modules become their own. The repository stays a domain beside them,
  because `route()` matches exactly and items filed against the repo name must still
  route. Measured on an adopter: 8 modules, and 13 of 17 live items (76%) touch
  exactly one.
- **The routing table moved to `.squad/domain-routing.txt`** (#72)
  It was the one file under `rules/` that code produced — `detect_domains.py --write`
  derives it, `route_domain.py` reads it, and nothing outside the kit touches either
  (measured across every `.json`, `.yml`, `.yaml` and `.toml`: zero references). Readers
  fall back to both old locations indefinitely, so a consumer that updates without
  migrating keeps routing. `--write` now takes no path and writes where the table
  belongs; a test refuses any document that teaches the old one.
- **Bytecode is no longer written into the installed kit** (#72)
  Python writes `__pycache__/` next to the source, and the kit's source lives in the
  consumer's `.claude/` — eight `.pyc` files after four commands in a clean sandbox.
  `PYTHONDONTWRITEBYTECODE` is now set in `settings.plugin.json`. Measured cost over
  five runs: 415 ms/run with a warm cache against 360 ms without one.

### Fixed
- **The panel's diversity rule protected the seat, not the decision**
  `review_panel.py` checked that a recognised non-home family had VOTED, over the votes
  cast. Nothing checked the votes that CARRY. So two Claudes approving while the only
  orthogonal reviewer returned produced APPROVED, with the dissent filed beside it —
  advancing a conclusion on exactly the correlated approval the seat was bought to
  prevent. An external reviewer found it in the panel's own worked example; this
  repository's `test_a_majority_carries_the_document` had frozen the failure as the
  contract. The majority must now span two recognised families, and the test is
  inverted. No token was invented: a document the orthogonal seat returned is
  `NEEDS_REVISION`, which already means what it needs to mean.
- **A dissent travelled as a name, so nobody downstream could act on it**
  The record carried `["judge"]`. The reason — the thing the objection was ABOUT — was
  dropped, and "kept in the record" then meant kept where nobody looks. Dissent now
  carries reviewer, family and reason, and `check_panel_approval.py` prints it under an
  APPROVAL, where the reader who advances the artifact is the one who must see it.
- **An approval survived a rewrite of the thing approved**
  Every panel guarantee was about WHO voted and HOW; nothing bound the votes to the
  text. Editing the artifact after the votes landed was the cheapest way to launder a
  change past a panel. The record now carries `artifact_sha256`, the gate recomputes it,
  and a record without one is reported as an unverified binding rather than accepted.
- **`check_panel_approval.py` did not say what it could not check**
  It now carries `not_checked`, and the first line is the one that matters: the record
  is written by the session that was meant to collect the votes, so three fabricated
  votes produce a file this gate accepts. `alignment_judge.py` admits the same of
  itself. Building a panel on top made the ceremony more elaborate, not the independence
  real — and closing it needs a signature the executor cannot mint.
- **`scope` and `threshold` could redefine success silently**
  Fail a requirement, delegate the requirement away or lower its target, approve what
  remains, declare success: every step legitimate, the result a pass nothing earned. The
  rationale requirement did not stop it, because a rationale is a sentence and the
  sentence can be true. Both classes must now name the obligation they SUPERSEDE, and
  `rewrite_wall` refuses one that does not. The record then shows an obligation that was
  moved rather than one that was never there.
- **An autonomous run could reach a human decision by returning to the entrance**
  Halts return work to the registry, and intake gate G5 says a person decides. "Zero
  interventions after BACKLOG" did not survive the recirculation. `g5_route` gives the
  items the SYSTEM creates an executable route: a `why_now` citing a phase verdict this
  project's own stream carries is a LOOKUP, not a claim. It fails closed — an
  unconfirmable citation stays with a person, because a fabricated local reason is
  exactly what G5's second half was written about.

### Added
- **`check_review_binding.py` — an approval bound to a revision, not to a name**
  A review verdict said the work was examined and never said WHICH work, so a commit
  landing after consolidation travelled to `develop` on an approval that never saw it.
  This compares the reviewed commit against the tip and refuses when the files the
  review examined have changed. It does NOT refuse on any movement — a gate that did
  would be bypassed within a week, and a bypassed gate protects nothing — and a record
  listing no files widens to every move rather than assuming harmlessness.
  `promote_to_develop.py` calls it, because promotion is where reviewed work leaves.
- **The autonomy envelope names what it does not contain**
  Three findings could not be mechanized in a patch and are now declared where a reader
  looks, because an undeclared gap is indistinguishable from a solved problem: nothing
  restarts the controller if it dies; recovery after publication is contained, not
  closed; and nine hooks existing is not nine constraints holding. Each is listed with
  what would close it, and the section ends on the reviewer's own summary — autonomy
  intended, mechanisms implemented, whole-chain operation and recovery not demonstrated.

### Changed
- **Everything the system writes now lands under `<project>/.squad/`, and a gate proves it**
  The kit wrote its output into the same directory that holds the installed kit. Measured
  across 20 consumer repositories on 2026-09-09: **17 had the kit committed to git**, tracking
  142-984 files each, and **every repository carried between 348 and 566 permanently dirty
  files — all of them inside `.claude/`.** Nothing outside it was dirty anywhere. So a project
  could not un-version the dependency without un-versioning its own decision records, and a
  `git status` nobody can read is a `git status` nobody reads.
  `<project>/.squad/` is now the one write root, in every layout, holding `records/` (the dated
  trail) and `wiki/` (the OKF bundle) plus the session state that used to sit beside the
  install — `session-state/`, `compaction-snapshots/`, `attestations/`, `active-plan`.
  **Nothing executes from it.** The kit stays where the installer put it.
  **The layout exception is gone.** `records-location.md` used to carve out one: `.claude/records/`
  for a plugin install, `<repo>/records/` for the kit's own repository. Two answers meant two
  ways to be wrong, and that exception is what the first instrumented run tripped over — it
  created `.claude/records/cycle-events.jsonl` at the root here, the split trail the convention
  exists to prevent. One root removes the question rather than answering it more carefully.
  **Readers fall back; writers never do.** A consumer that updates without migrating keeps
  working. A writer that fell back would keep every project on its old root forever, and the
  centralisation would be a sentence in a rule with nothing behind it. `_artefact_write_dir`
  stopped following the project's existing trail for exactly that reason. The kit does not
  migrate a consumer: that would be the kit writing to a repository it does not own.

### Added
- **`squad/paths.py` owns every data-root literal, and `check_write_containment.py` enforces it**
  Six modules held their own copy of the root list, in **four different orders**. A reader
  resolving one order found a directory a writer using another had never filled.
  Now one module spells them and the gate fails any other kit file that does — so every path a
  writer builds came from the owner, and the owner produces one root. That is the whole proof,
  and it is re-runnable; reading 164 writing call sites is not.
  It found **70 literals across 33 files** on the first pass, and three more when extended to
  the session state — writers that were outside the guarantee while it read as complete.
  Two defects in the gate itself, both caught by the repository's own tests: it reported its own
  root list (it now derives the list from the owner, so it has none), and it reported CONTAINED
  on an empty tree. The second is the rule this kit repeats most — a gate that examined nothing
  must not print a verdict about everything — so it now names the file count and exits 2 with
  `NOTHING SCANNED` when that count is zero.
  Prose is BLANKED rather than deleted before matching, preserving line numbers: a finding
  reported at a line holding something else is a finding readers stop trusting.
  The shell cannot import the owner, so `install.sh`, `patch_install.sh` and `attest_plan.sh`
  ASK it and refuse to guess when the answer does not come back.

### Added
- **REVIEW consumes an independent audit it did not produce (#67)**
  `/review` spawns 5-7 Claude sub-agents with ad-hoc prompts. Nothing behind them refuses a
  finding that was never grounded: no versioned catalog to cite, no tool measuring what the
  prose estimates, no store that rejects an invented id. The `loop-*` plugins audit the same
  domains with instruments that refuse their own theatre — a finding whose catalog id is not
  registered is rejected at the database boundary, complexity comes from radon / lizard /
  gocyclo rather than from reading, and a run that found nothing is a hard block instead of a
  success. `cycle-judge-codex.md` already made this argument for cycle ARTIFACTS; this extends
  it to the CODE.
  **The selection is derived, never chosen.** `rules/review-auditors.txt` maps each domain
  `detect_domain.py` already computes to the plugin that audits it, and `select_auditors.py`
  resolves that against the plugins actually installed. The reviewing agent may WIDEN the
  selection and never narrow it — the same rule the review panel enforces by refusing to seat
  an author, because the CHOICE is already a judgement. Point a concurrency change at a docs
  auditor and the report comes back clean, honestly, having examined nothing that mattered:
  an independent report about the wrong thing is worse than none, because it reads as coverage.
  **Scope is passed and the mode is recorded.** Each auditor receives `--diff-base`, and what
  that does depends on the domain: `analysis-scoped` reads only the changed files, while
  `report-filtered` reads the whole tree and reports only what the change touched — because
  reachability, duplication and dependency cycles are properties of the whole graph, and
  analysing the diff alone would make every new function look orphaned. A run with no base
  says in writing that it covered the whole tree; the base is never guessed.
  **`check_auditor_coverage.py` blocks**, entering `consolidate_findings.py` as BLOCKER
  findings so the verdict cannot be computed while ignoring it — the shape
  `check_upstream_gate.py` established and argued for. It fires on a missing report, a report
  the plugin's OWN checker rejects, or a plugin this machine does not have. A project that
  declares no auditor is not blocked: that opt-out is a visible edit to a file the installer
  preserves, never a silence.
  **The report contract is the plugins', not a copy of it.** The gate runs each plugin's own
  report checker from its install path. A second copy would diverge the day the contract
  changes, and the kit would accept a shape the plugin itself rejects.
  Two sections travel out of every report on purpose: `## Verdict`, quoted rather than
  re-graded, and `## What Was NOT Analyzed`, which the contract never omits and which is the
  single thing stopping partial coverage from reading as complete — the seam between two
  honest halves is exactly where that caveat gets dropped.
  **Severity is carried as a SIGNAL and never gates.** An earlier draft blocked on Critical
  findings read from the report's markdown; the first smoke run showed that a subsection
  holding an empty table plus "_(none)_ unless critical findings were registered" is not
  decidable by prefix. The finding stores would be decidable, but their schema differs per
  plugin and is not declared to consumers, so reading them would be a second copy of another
  project's internals. This kit's governing sentence cuts both ways: an inability to measure
  must not become a passing measurement, and it must not become a failing one either.

- **The auditor registry cannot name a domain the detector never emits (#67)**
  A row mapping a domain `detect_domain.py` does not produce is an auditor that never runs,
  and nothing would say so — the review would pass with one fewer independent audit than the
  registry claims to require. That is the silent-coverage failure this integration exists to
  prevent, arriving through its own configuration file. A test holds the registry against the
  detector's own domain table, and two more refuse a plugin declared with two different diff
  modes or two output directories: the first would make the recorded scope depend on which
  domain happened to select it, and the second would send an audit somewhere the gate does not
  look.

- **`installed_plugins.py` — where a Claude Code plugin lives, read instead of guessed (#67)**
  `rules/review-panel.txt` recorded on 2026-09-09 that verifying a plugin-supplied reviewer
  "means asking Claude Code which plugins are installed, which nothing in this kit does yet".
  That was true of the kit and false of the machine: `~/.claude/plugins/installed_plugins.json`
  carries an `installPath` per plugin. Measured here — 31 plugins, 17 of them the loop family,
  152 agent files underneath them.

### Fixed
- **Three defects in the soft-cap dismissal marker, none of them covered by a test**
  `<!-- ADR-DISMISS-SOFT-CAP: id: reason -->` is how a plan waives a soft cap. Its parser refused
  a `>` anywhere in the reason, so a justification written with an arrow — `warnings fell 15 -> 0`,
  the idiom this ecosystem states before/after with — ended the match early and the dismissal
  registered as ABSENT: the plan stayed capped and demoted, indistinguishable from a cap nobody
  tried to waive. It refused a `-` in the id, so `auditor_unavailable_dependency-cruiser` — a cap
  this kit's own detector emits — could not be dismissed at all, in any consumer, ever. And it
  accepted an EMPTY reason, registering a waiver with no justification behind it. The parser now
  spans lines, accepts hyphens in the id, and refuses a blank reason; six tests cover it, where
  before there were none.
- **The architecture detector picked the wrong script and reported a clean cruise that never ran**
  It searched `package.json` for the first script mentioning `depcruise` and ran that one. In a
  repository whose `lint` script chains several tools (`eslint . && depcruise ...`), `lint` sorted
  first — so the detector shelled out to the whole chain, and a failure anywhere in it was read as
  a dependency-graph result. It now prefers a script that neither chains (`&&`, `||`, `;`, `|`) nor
  delegates (`npm run`, `pnpm run`, `yarn run`, `npm-run-all`), falling back to the first match when
  a chain is genuinely the only one. Measured in a consumer whose `depcruise` script existed and was
  never the one invoked.
- **A `plugin:agent` panel seat was accepted without verification, and no longer is (#65)**
  `convene_panel.py` skipped the existence check for any seat whose name contained a colon,
  because there is no file for it in this tree. So the largest pool of specialists a project
  has — 152 plugin agents against the kit's 14 — was exactly the one the panel took on the
  strength of a name, in a mechanism that refuses that everywhere else. A plugin seat is now
  resolved through the manifest: the plugin must be installed AND supply that agent.
- **The DISCOVER and PLAN review panel is now convened, and blocks (#65)**
  `rules/review-panel.txt`, `review_panel.py`, an intake premise gate and 377 lines of tests
  shipped on 2026-09-08 declaring that both phases advance on **2 of 3 signed approvals**.
  Nothing convened a panel. `review_panel.py` tallies a RECORD, and no code produced one —
  measured by tracing callers: `review_panel` appeared in `skills/` exactly once, in a
  docstring, while the other gates of the same phase appeared in 6 and 14 files. So the rule
  read as enforced and every DISCOVER and PLAN advanced on its structural score alone.
  That is this kit's own governing failure — *an inability to measure must never become a
  passing measurement* — reached through the governance layer rather than a gate.
  **The reviewers are now the project's own specialist agents.** A seat used to name a model
  and a lens (`evidence-lens | claude-opus-5`), which said how a reviewer would be reached and
  never who was reviewing. It now names an agent that must exist in the running project, and
  both gated phases fall inside a speciality `agents/README.md` already defines: DISCOVER asks
  whether evidence supports a conclusion, which is verbatim what `nemesis-claim-auditor`
  decides; PLAN asks whether a shape is right and grounded on disk, which is
  `vera-technical-arbiter`. `daedalus-tech-lead` sits on neither — on a gated item it is the
  author. The orthogonal seat is `judge-codex:*`, so the family-diversity rule is satisfied by
  a real project agent rather than a model string.
  `convene_panel.py` resolves each seat against the agents actually present and writes the
  assignment. `check_panel_approval.py` refuses to advance a document without a majority, and
  **a missing record is not an approval**: a phase that skipped its panel must not be
  indistinguishable from one whose reviewers all approved. `review_panel.py` gained one
  refusal — a voter the assignment never named — because convening buys nothing if the panel
  that voted may differ from the panel convened, and the assignment is read from disk rather
  than from the record, which would let a document supply the list it is checked against.

### Changed
- **A structural score no longer advances a DISCOVER or PLAN document on its own (#65)**
  `run_opportunity_score.py` and `run_structural.py` apply the panel gate by default. An
  opportunity or plan scoring 100 with no panel record is now `AWAITING_REVIEW`, not
  `SHIPPABLE`. **The gate moves the verdict and never the score**: folding it into the number
  would conflate "this document is weak" with "nobody has reviewed it yet", two facts that
  take opposite actions — which is the distinction the panel mechanism is built around.
  No verdict token was invented, and the three outcomes stay three. `NEEDS_REVISION` — the
  panel returned it, editing can lift it. `AWAITING_REVIEW` — "the structure is complete and
  the judgement has not been made", which is the shape PLAN phase 0 already used for a brief
  nobody signed. `ITEM_IN_FLIGHT` — the panel could not convene at all. All three were already
  in `rules/verdict-bands.txt`, and collapsing the last two would confuse "nobody has reviewed
  this yet" with "nobody can review it here", which take different actions.
  A structural INVALID still wins outright — caught by the scorer's own tests, which went from
  exit 1 to exit 0 on a fabricated pointer while this was being wired. Letting "nobody has
  reviewed this" overwrite `fabricated_evidence`, the one unrecoverable defect in the cycle,
  would have turned the new gate into a way of hiding the oldest one.
  `--structural-only` measures structure without the gate and RECORDS that it did, in the
  report: a bypass nobody can see in the artifact is a bypass that quietly becomes the norm.
  `score-report.schema.json` accepts the two verdicts the gate can produce.

### Added
- **Promotion is a command of its own: `/promote` (#64)**
  `git-safety.md` § 1 says `develop` advances ONLY by promoting `workspace` through a PR, and
  the single place in this kit that opened that PR sat in the middle of `cycle-release.md`'s
  chain — between the version bump and the tag. **So integrating required versioning**, and a
  project that did not want to publish a version simply did not integrate.
  The cost was measured on this repository rather than imagined: **349 commits on `workspace`,
  zero tags** — finished, reviewed and verified work unreachable behind a step nobody wanted to
  take yet, and 45 issues closed against the kit's own lifecycle rule because there was no
  version to name in the closing note.
  Those 349 commits reached `develop` on 2026-09-09 through this command — one run, no version
  cut — which is the argument for the split, exercised rather than asserted.
  `mechanisms/cycle/promote_to_develop.py` is that step alone. **It cuts no version**: no bump,
  no CHANGELOG promotion, no tag — and a test asserts the file never reaches for
  `bump_version`, `compute_next_version`, `promote_unreleased` or `git tag`, because a promotion
  that bumps is a release wearing another name.
  It refuses a branch that is not `workspace` (`develop` integrates, never originates) and a
  dirty tree (which would promote a state nobody reviewed). **Nothing to promote exits 0** — it
  is an answer, not a failure. Branch protection wanting a reviewer exits 3, matching the
  `PR_OPEN_AWAITING_APPROVAL` convention the release PR already uses rather than inventing a
  second one. `gh` absent exits 2, which is never a pass.
  **`/release` now calls the same mechanism** instead of an inline `gh pr create`: one
  definition, two callers. What changed is that the promotion no longer requires the release.
  **What was deliberately NOT changed:** the two cuts stay as they are — `X.Y.Z-rc.N` when the
  queue of ready items dries up, `X.Y.Z` when a milestone closes. Tying the final version to "the
  backlog is empty" was considered and rejected: `cycle-maintenance.md` defines `BACKLOG_EMPTY`
  as *a prompt to sweep*, so it means the queue dried up now, never that the scope finished. And
  stopping `/release` at `develop` would leave `cycle-acceptance` with nothing to exercise — that
  cycle exists to catch what only appears in the released artifact, "a mis-wired env var in the
  deployed build, a proxy that buffers the stream, a login that 500s only against the real
  identity provider".


### Fixed
- **The plan-confidence flake was Hypothesis's deadline, not shared state (#60)**
  It had fired three times in one day and been captured none of them. Hunting it directly
  — 104 runs, eight at a time — produced **21 failures**, and every one was the same
  thing, with no assertion involved:
  > *Unreliable test timings! On an initial run, this test took 257.20ms, which exceeded
  > the deadline of 200.00ms, but on a subsequent run it took 180.23ms.*
  Under load an example crosses Hypothesis's 200 ms default; on the confirming re-run it
  does not, and that is reported as `FlakyFailure`. **That explains every symptom recorded
  since the first occurrence** — it failed inside a parallel suite run, passed in
  isolation, and the reported counter-example never reproduced alone, because the input
  was never the problem.
  `suppress_health_check=[HealthCheck.too_slow]`, which these tests already carried, does
  **not** cover it: the health check and the deadline are separate mechanisms and only the
  first was suppressed. All four `@settings` blocks now set `deadline=None`, deliberately
  rather than raising it to a number that would fail again on a busier host — these tests
  assert properties, never latency, and a wall-clock budget on them measures how busy the
  machine is.
  **Measured, before and after, same load and same machine: 21 failures in 104 runs → 0
  in 104.**
  Two hypotheses were eliminated on the way and are recorded so nobody re-derives them:
  per-example isolation was intact (`example_dir()` gives each example its own directory),
  and `run_structural.py` has no cache, no mutable module state, and writes nothing outside
  the plan it is handed. My own leading suspect — the shared `.hypothesis/` database across
  eight parallel processes — was wrong.

### Fixed
- **`d3_orphan_export` called every import in an `__init__.py` a re-export (#63)**
  `_PY_INIT_IMPORT_RE` matched `^from <anything> import ...`, so
  `from typing import Any, NoReturn, TypeVar` put three typing primitives on the kit's
  public surface and `TypeVar` was reported as an orphan export of the `squad` package.
  The only fix that finding admitted was *stop importing `typing`*. A re-export is a name
  the package republishes from ITS OWN modules — a relative import, or one from the same
  package; an absolute import of another distribution is a dependency.
  **And a correction to the issue that reported it.** It claimed all three findings were
  false because the symbols are in `__all__`. Investigating to fix it inverted the
  premise: being in `__all__` is what PUTS a symbol on the surface, and the detector then
  asks whether anything consumes it — which is the right question. Only `TypeVar` was a
  false positive. `handle_context_error` and `safe_create_context` are genuine: both are
  declared public and nothing outside the module imports either. They are left in place —
  removing public API on the strength of a soft cap would be deciding the package's
  contract from a count, and `FAIL_SOFT` exits 0 so nothing is blocked behind them.

### Fixed
- **The code-quality gate went from FAIL_HARD to a passing exit, and now says what it found (#61)**
  Two defects, and the second is the one that mattered.
  **The hard cap was one dead ternary.** `tests/test_check_xrefs_root.py` carried
  `own.write_text if False else (own / "SKILL.md").write_text(...)` — a conditional whose
  test is the literal `False`, so the first branch was never evaluated. It could not have
  been: `own` is a directory and `Path.write_text` on one raises. Removing it drops
  `dead_code_unallowlisted_python`, and the gate goes `FAIL_HARD` → `FAIL_SOFT`, which
  **exits 0** — `code-quality-golden-rule.md` § 1 makes a soft cap dismissible with an ADR
  rather than a blocker, on the argument that a CI treating soft caps as blockers teaches
  people to route around them.
  **The gate reported a blocking verdict and would not say what triggered it.** The JSON
  carried counts per detector per language and nothing else — no file, no symbol, no
  allowlist key. Grepping the whole payload for anything resembling a path returned zero
  hits, so a `FAIL_HARD` on three dead symbols came with no way to find them; the only
  route was re-deriving the tool invocation by hand. `Finding` has carried `file_path`,
  `symbol_or_line` and `allowlist_key` the entire time — only the summary dropped them.
  It now emits them, sorted, so two runs of the same tree produce the same report and a
  diff between them is about findings rather than about dict ordering. This is
  `test_gates_say_what_they_examined.py` one step on: a gate must say what it examined,
  **and what it found**.

### Fixed
- **The CI lint step went from 52 findings to zero, and three of them were real defects (#59, #62)**
  `ci.yml` runs `ruff check mechanisms squad skills hooks tests conftest.py`, which exited
  non-zero on 52 pre-existing findings — so that step was red with or without the billing
  block. The count is not the interesting part; **what the lint was pointing at is**.
  **A latent `NameError` (`F821`).** `tests/test_check_install_drift.py` annotated a fixture
  as `pytest.MonkeyPatch` and never imported `pytest`. It passed only because
  `from __future__ import annotations` makes the annotation a string that is never
  evaluated; remove that line — or evaluate the annotation, as `typing.get_type_hints` does
  — and it raises.
  **A guard that could not fire.** In `verify_ecosystem.check_readme_advisory_skills` the
  `try` sat BELOW the `subprocess.run` and wrapped only two lines that read
  `result.returncode` and `result.stdout`, neither of which can raise. Its handler
  referenced `result.returncode`, which is what gives away that the invocation was meant to
  be inside it. The call is now in the `try`, catching `OSError`/`SubprocessError` — an
  inability to run the checker is reported as one, never as a pass.
  **Five tests that asserted nothing (#62).** Every `F841` in `tests/` was a value computed
  and discarded, and each turned out to be an assertion that was never written — including
  one that read `skills/release/SKILL.md` and checked nothing while the integration it is
  named after does not exist (`grep -c notify_slack` → 0). Deleting the unused variables
  would have silenced ruff and left five tests verifying nothing, trading a visible symptom
  for an invisible one.
  The rest were narrowed rather than suppressed: four blind `except Exception` became the
  transport errors they meant (`URLError`, `OSError`, `TimeoutError`, `SubprocessError`), so
  a bug in the lines above stops being reported as "Slack is down"; `subprocess.run` calls
  state `check=False`; `l` became `ln`; and the three `E402` got the `# noqa` this
  repository already uses for imports after a `sys.path.insert`.
  **The auto-fix was verified, not trusted.** `--fix` was almost run with `--select`, which
  would have let `RUF100` delete `# noqa: E402` comments as "unused" because E402 was
  outside that selection — while `E4` IS in the project's `select`. Reverted before
  committing. Every import the fix removed was then checked by comparing AST-level import
  bindings before and after, and the 10 affected test files were run both ways: **89 passed,
  identically**.


### Added
### Fixed
- **`sq check` discarded the reason too, after `sq test` was fixed (#57)**
  The same defect, in the sibling — corrected in one place and left standing in the other,
  which is how a lesson becomes a patch. `sq check` replays `run_slice_tests.sh` as one of
  its steps, so a suite failure arrives here; the renderer showed the **last three lines**,
  which for that command are the `FAILED SUITES (1):` banner and the path. Never the cause.
  The human view now shows 30 lines and says how many it elided, and `--json` carries the
  **whole** output under `failure_output`. Truncating for a person is a courtesy;
  truncating for a consumer is the false-coverage report again — a FAIL nothing can act on.
  Proved with a deliberately failing probe test: 33,140 characters captured, the probe's
  marker inside, exit 1.

- **`sq test` reported FAIL and threw away the reason (#57)**
  The runner already prints every suite's pytest output inside `::group::` blocks and the
  command captured all of it — then printed `FAIL` and nothing else, making the caller run
  the suite again to learn what that run already knew.
  It took a real capture to notice, and the capture was the point: a flaky test in
  `plan-confidence` fired during a full run, and **the CHANGELOG's own instruction for that
  test is "capture the failing output rather than re-run until it passes"**. This command
  had discarded it. The failing suite's block is now printed beneath the verdict and
  carried in `--json` under `failures`.
  A filtered run (`--slice`, `--touched`) went through a different path that built the
  trailer by hand and emitted no blocks at all, so it explained nothing either. Both paths
  now emit the same wire format, which is why `failing_output` has one shape to read.

- **`sq` on a clean tree ran the root suite to report nothing, and looked in the wrong root on a consumer (#57)**
  Both found by exercising paths the tests had not: writing a test for every branch is not
  the same as running the command.
  **`--touched` with nothing changed ran 1929 tests for eight minutes.** The selection was
  empty, an empty slice list fell through to `not only`, and the root suite was inserted.
  A clean tree means there is nothing to test — which is not the same as "test the root
  suite". It now reports `no changed files — nothing to run` and names every suite it
  skipped, at exit 0.
  **`sq check` looked for `.github/workflows/ci.yml` inside the kit.** In this repository
  `kit_dir`, `eco` and `project_dir` are one directory, so the conflation works perfectly
  here and breaks on every consumer, where the kit is `<project>/.claude` and the workflow
  is not. This is the shape of kit#36 and kit#37 — two roots resolved differently, and a
  gate reporting on a tree that is not there. `squad/cli/paths.py` now states which of the
  two a verb means, with the structural rule first: `resolve(project_dir=kit_dir)` handed
  `.claude` finds a kit right there and reports both roots as the same directory, which is
  the very conflation being fixed. A consumer without a workflow gets exit 2 and the reason.

- **`sq` documented, and its ADR accepted (#57)**
  `README.md` gains a *Finding your way* section, `CONTRIBUTING.md` prescribes `./sq test`
  while saying plainly that it is a façade over `run_slice_tests.sh` — which stays the
  definition of "the suites" and is what CI invokes — and `rules/squad-map.md` names `sq`
  as its own executable half. The four strings other tests assert on were left untouched.
  The ADR moves to `accepted`, with both open questions settled and one design recorded as
  **not having survived contact**: it proposed discovering gates by glob, which is not
  implementable across seven flag conventions.

- **`sq ci` fetches the annotations, which is the whole verb (#57)**
  Diagnosing a red CI cost roughly eight calls on 2026-09-09: every job died in three
  seconds with zero steps executed, `gh run view --log-failed` returned nothing, and the
  logs had expired. The reason lived in a check-run **annotation** and nowhere else —
  *"The job was not started because recent account payments have failed"*. Through the web
  UI and through job output, that is indistinguishable from a test failure. A `sq ci` that
  reported conclusions without annotations would reproduce the eight calls rather than
  replace them, so it fetches them per failed job. Against this repository it now prints
  the billing reason **in one call**.
  A repeated annotation is marked `(same annotation as above)` rather than dropped: five
  jobs failing for one reason must not read as one reason and four silences. `gh` absent,
  unauthenticated, or returning no runs are all **exit 2** — an empty run list answers
  nothing, and reading it as success is the defect this kit finds most. The `gh` runner is
  injected, so the eight tests need neither network nor token, following
  `check_merge_autonomy.py`. And because this is the only verb that reads the network, it
  says so in its own `not_checked` — a reader cannot otherwise tell a fresh answer from a
  stale one.

- **`sq check` replays the workflow instead of globbing the gates (#57)**
  The obvious design — glob `mechanisms/gates/check_*.py` and run each — is not
  implementable, and finding that out changed the command. The root-path flag is not
  uniform across the 23 gates: eight take `--root`, four `--repo-root`, three
  `--project-root`, one `--repo`, one `--ecosystem-dir`, one a positional, one needs both
  `--install` and `--kit`, three take none — and `check_xrefs` passes while printing WARN
  unless given `--strict`. A glob-and-run would carry seven flag conventions plus a special
  case: **a second list of what "verified" means**, which is what the ADR forbids.
  So the invocations are REPLAYED from `ci.yml`, parsed as YAML rather than read line by
  line — `run: |` is a multi-line scalar that a line reader cannot see, which is why
  `test_ci_targets_exist.py` misses the code-quality step. `check_xrefs` arrives with
  `--strict` because the flag lives in the workflow, and "the CLI reaches what CI reaches"
  becomes true by construction instead of a property somebody maintains.
  **The glob is used for the opposite question**: which gates the workflow never invokes.
  Resolving that honestly took two corrections. Counting only direct invocations reported
  13 unreached when 8 of them run inside `verify_ecosystem` — so reachability now resolves
  one level in, at a stated depth rather than a partial call graph presented as complete.
  And the lens had to keep short string literals: `verify_ecosystem` builds
  `.../check_skill_map.py` as a string, so stripping strings — correct in
  `test_every_gate_is_reachable.py`, which asks whether anything calls a gate — hid every
  call site here, where the filename in a string IS the answer. Comments stay stripped:
  `ci.yml` mentions `check_reference_leakage` in a comment and never runs it.
  The remaining five are reported as *this command does not reach them*, explicitly not as
  unreachable, and the line points at the test that answers that other question.

- **`sq test` — the verb the whole CLI was justified by (#57)**
  It **wraps** `run_slice_tests.sh` rather than reimplementing discovery: that script is
  the definition of "the suites" — `conftest.py` names it in its refusal, a test asserts
  the name is present, and CI invokes it — so a `sq test` that globbed for itself would be
  the second-list defect the ADR forbids wearing a different filename. The script gained a
  machine-readable `SUITE\t<path>\t<rc>\t<passed>\t<failed>\t<collected>` trailer, so the
  count reported comes from the runner instead of from a guess about how pytest phrases a
  summary this release. **An unreported count stays `-`, never `0`** — a zero meaning "not
  reported" summed with a zero meaning "none" is how a total becomes fiction.
  `sq test --slice backlog-item` runs 14 tests and prints the 21 slice suites it did not
  run, by name. That is the report the session of 2026-09-09 needed and did not have.
  **`--touched` widens rather than narrows**, because the only failure that matters here is
  under-running while reporting success: anything under `mechanisms/`, `rules/` or `.github/`
  is shared by every slice and therefore unattributable, and any path no rule maps widens
  too, carrying the path in the reason so it can be mapped later. Untracked files are unioned
  in, because `git diff` does not list them and a brand-new test file would otherwise be
  invisible.
  **Two bugs that only running it revealed.** `lstrip("./")` strips leading `.` and `/`
  CHARACTERS, so `.claude-plugin/plugin.json` arrived as `claude-plugin/plugin.json` — the
  selection stayed safe, but the reason named a path nobody could look up. And the base
  defaulted to the trunk, which on a branch 335 commits ahead of `develop` returned all 792
  tracked files: `--touched` degenerated into "run everything, slowly". The default is now
  the working tree; `--since REF` asks the branch question via merge-base.

- **`sq` — the kit's task-oriented surface, first two verbs (#57)**
  The skeleton plus `sq where` / `sq run`, chosen first because they are pure projection:
  no subprocess, no YAML, no git state, so the shape is proved before anything else is.
  `sq where check_xref` now answers with `did you mean: check_xrefs` — the wrong-directory
  and wrong-argument guesses that cost four calls in one session become one call.
  **Every report states what it did not check**, and it is a FIELD on `Report`, not a printed
  line: making it prose would have left `--json` emitting `{"passed": …}` and handed every
  programmatic consumer exactly the false-coverage report the field exists to prevent. A test
  asserts the field is populated end to end, through the shim.
  **A bare `sq` exits 2, not 0.** That is why the router is a dict rather than
  `argparse.add_subparsers`, which would have printed help and succeeded — a command that did
  nothing and reported success is the doctrine this CLI was built to uphold. It also lets the
  unknown-verb message name the verbs it does have.
  **The shim is deliberately tiny because no gate can see it**: `verify_ecosystem` compiles
  `*.py` and `bash -n`s three `*.sh` globs, `ruff` is given directories, and `shellcheck`
  reads `git ls-files '*.sh'`. An extensionless root file matches none of them, so
  `tests/test_sq_entry_point.py` executes it — that test is the other half of the trade
  between the short name and the syntax gate.
  **`squad/cli/` and not `mechanisms/cli/`**: `mechanisms/README.md` says *"Nothing here is
  user-invocable"*, and `check_mechanisms_inventory.py` hard-codes the five families, so a
  sixth would be reported as an undeclared family. `squad/` also already travels to consumers,
  which the root `sq` does not — `install.sh` copies directories.


### Fixed
- **152 tests ran in no CI job, because an optimisation reopened the hole a testpath had closed (#58)**
  `pyproject.toml` declares `testpaths = ["tests", "hooks/tests", "squad/tests"]`, and its own
  comment says why the last two are there: *"fourteen tests for `stop-validation` and the whole
  hook library sat outside the collected set. A test the suite does not collect is a test that
  passed once."* `run_slice_tests.sh` then passed `tests` to pytest **explicitly**, and an
  explicit path argument suppresses `testpaths` — so the two paths added to close that hole fell
  straight back out of it.
  **Measured 2026-09-09:** a bare `pytest` collects 1894; `pytest tests` collects 1742; the 152
  in between ran in **no CI job at all**, because `ci.yml` runs this script and nothing else.
  The cause was not neglect: `ci.yml:132-134` records that a second root-suite step was removed
  on 2026-08-26 to save *"45s duplicated per run"*, and that step was the pipeline's only bare
  `pytest`. **The 45-second optimisation cost 152 tests**, and `CONTRIBUTING.md` prescribed the
  same `pytest tests` as the house instruction, so the hole was documented rather than hidden.
  The root slot now carries all three testpaths in one pytest process — which is what a bare
  `pytest` already does, so it is the configuration already proven to work; none of the three is
  under `skills/`, so `conftest.py`'s multi-slice guard does not fire. **Verified: 23 suites,
  3556 tests, ALL SUITES GREEN**, with the root suite at 1896 (1894 plus the two tests added
  below). The relationship is now asserted rather than the number:
  `tests/test_slice_runner_covers_every_testpath.py` fails when a declared testpath is not
  passed to pytest by the runner, so a path added later is covered without anyone remembering
  that file exists.
  **And the exit code is no longer collapsed to a boolean.** `run_suite` recorded `"0"`/`"1"`
  instead of `$?`, so pytest 5 (nothing collected) and 1 (a real failure) were the same fact:
  a slice whose tests all vanished reported `FAIL` with no hint that the cause was an empty set.


### Added
- **ADR: the CLI navigates, the mechanisms compute (#57)**
  Recorded in `.squad/wiki/decisions/the-cli-navigates-mechanisms-compute.md`, status `proposed`.
  The first framing of the request — "one place for every check" — was dropped after
  measurement: `verify_ecosystem.py` already aggregates and `test_every_gate_is_reachable.py`
  already proves no gate is orphaned, so a CLI holding its own gate list would be a second
  source of truth diverging from the first. What the kit lacks is not execution but
  **navigation**, and the cause is structural: `rules/README.md` places a file by who OWNS it,
  which is right for the disk and unsearchable by task. The CLI is that projection, and nothing
  else in the kit does it. Its load-bearing property is stated first rather than last — every
  command names what it did NOT check, because the session that produced the ADR reported
  `1894 passed` while 3402 tests in 23 slices had not run, and nothing on screen said the other
  half existed. Scope cut to four verbs measured against real friction rather than twelve chosen
  for symmetry; `explain`, `status` and `issues` wait for their own evidence.


### Added
- **`check_install_drift --consumer-local` lists what an install owns, by path (#33)**
  The classification was already correct and the paths were already computed — then discarded at
  the print site, which reported `consumer-local: N` and nothing else. A number tells a person
  that N files are theirs; it does not tell them WHICH, and which is the only form the answer is
  usable in. A consumer's own `hooks/delivery-gate.sh` was deleted three times by cleanups of
  `.claude/` and restored twice; the third deletion stood for days. At each of those moments the
  kit held the right answer in a drawer. The flag lists the files and exits 0 — asking is not
  auditing — and prints `no files` rather than nothing when the install owns nothing, because
  blank output cannot be told from a crash. Kept off the default report on the issue's own
  argument: `consumer-local` is normally a healthy number, so the right moment to surface it is
  the destructive one, not every session.

- **The two lineage edges are specified where they are stored, and checked (#55)**
  `supersedes` and `regression_of` are the other two item-to-item edges in the registry, and until
  now the kit prescribed writing both and read neither. `blocked_by` carries five deterministic
  findings; these carried zero, so `supersedes: B-999` naming an id no block defines passed clean —
  the exact defect G6 exists to catch on the other edge. **The cause was where they were specified:**
  in `skills/backlog-item/SKILL.md`, which is where they are PRODUCED rather than where they are
  stored, with `cycle-maintenance.md` pointing readers there for a registry field — the inversion of
  `cycle-backlog.md`'s own opening rule (*"Skills consume this; do not duplicate content into
  SKILL.md"*). Both fields now sit in the contract's field table with a `§ Lineage` section, and
  `check_backlog_structure.py` reports `lineage_missing` (undefined id, or the item naming itself)
  and `lineage_wrong_status` (the target exists but is not in the terminal state the field asserts —
  a duplicate of an OPEN item folds in as `ITEM_MERGED` instead). **Deliberately no cycle gate:** a
  lineage edge points only at a terminal item and a terminal item is not reopened, so a ring is
  unreachable and G7 has no analogue.
  **The index walks the chain**, so the registry answers the question it always held the pieces of:
  a row whose item has ancestors reads `3rd attempt — after B-050, B-012`. Items with no ancestor
  are absent from the result rather than mapped to empty — most items are a first attempt, and
  printing that on every row would bury the rare one. The walker deliberately does two things the
  contract calls unnecessary, because it renders registries the checker has not passed yet: an edge
  naming an undefined id is followed and KEPT in the chain (dropping it would hide the visible half
  of the history), and a ring terminates rather than hanging the index. `LINEAGE_EDGES` is imported
  from the checker rather than restated, so the two readers of these fields cannot disagree about
  which fields they are.

### Fixed
- **The composed verdict destroyed the value it was composed from (#56)**
  `run_structural`'s library path returns the plan's own verdict; `main()` merges the code-quality
  verdict over it and prints THAT. The merge is deliberate and contractual — `cycle-code-quality.md`
  § 1 requires a plan's verdict to carry the quality state of the code it targets — but it
  overwrote `verdict` and `final_score_after_caps` **in place**, so the composed-from value was
  gone and the difference could be attributed to nothing. Anyone reading a band off the CLI, which
  is the obvious thing to do, was reading a value the snapshot suite can never reproduce.
  Worse, that cap is not a property of the plan: it reflects the repository, so two plans of
  different quality print the same capped number on the same day and one plan prints different
  numbers on different days. `verdict_before_code_quality` and `score_before_code_quality` now
  carry what was composed from — **emitted only when the merge actually moved the value**, because
  a key that always appears is a key readers learn to skip, and then the one that matters is
  skipped too. `test_real_plans_snapshot.py` says in its own header which of the two quantities it
  pins, so the next reader does not try to reconcile them.
  **Not done, deliberately:** the caps are not renamed to declare their origin. #56 suggested it;
  renaming would break every consumer's `code-quality-allowlist.txt` and `-baseline.txt`, and the
  provenance is already readable — the code-quality caps are listed under `code_quality`, and the
  two new keys name the boundary they crossed.

### Fixed
- **`check_backlog_structure`'s own inventory of findings did not match what it emits (#55)**
  Found while adding the two lineage checks below, by computing the comparison the docstring
  invites. The list declared `malformed_block`, which **no code path emits**, and omitted
  `duplicate_field` and `index_stale`, which two do. A reader consulting it would hunt for a
  finding that cannot fire and would not know to expect two that can — and being the list a reader
  consults is the entire job of that docstring. The list is now correct AND recomputed by a test,
  the same rule `check_mechanisms_inventory.py` already enforces over `mechanisms/README.md`.
  Both directions are pinned, and both mutants were killed before the test was kept: declaring a
  finding nothing emits fails, and emitting one nothing declares fails, each with its own message.

### Fixed
- **The plan-confidence declaration gate could not fail in this repository (#30)**
  `test_snapshots_cover_active_plans_with_matrix` selects from `PLANS_DIR`, which is
  `records/plans/` — gitignored, consumer-owned, and **absent from the kit's own checkout**.
  `glob` on a missing directory yields nothing without raising, so `eligible` was empty,
  `uncovered` was empty, and the assertion compared the empty set against itself. That is the
  same defect #30 reported about the parametrised half of this file, surviving in the half #30
  described as working (*"This one fires, and it fired today"* — it fired in a consumer, where the
  directory exists). The absence is now an explicit `pytest.skip` naming the directory and pointing
  at `test_every_committed_fixture_is_pinned`, which is where the kit's own floor actually lives.
  **And the second half of the same finding:** the gate's sentence scoped it to plans *"that have a
  Coverage Matrix"* while selecting on a bare `glob("*.md")`, so any markdown dropped in — a
  one-line note — was demanded to be pinned or declared. `_eligible_plans()` now reads each file
  and implements the sentence, with an unreadable file erring toward demanding a declaration.

### Fixed
- **`plan-confidence`'s property tests shared one directory across every generated example (#51)**
  Four `@given` tests took pytest's `tmp_path`, a function-scoped fixture that runs **once** for
  the whole test and is therefore shared by all thirty examples Hypothesis generates. Pytest's own
  health check says exactly this, and all four suppressed the warning rather than heed it — so the
  examples were not independent of one another, which is the property the file exists to assert
  about the code under test.
  **Measured, including what is still open:** 2 failures in 15 runs before (~13%), 1 in 85 after
  (~1.2%). Both original failures were in `test_end_to_end_score_invariants` and
  `test_smell_idempotent`, and **neither reproduced when its counter-example was replayed alone** —
  the inputs pass in isolation, which is what pointed at shared state rather than at the scorer.
  Each example now opens its own directory. The remaining 1-in-85 was **not captured**: sixty
  consecutive runs after it produced nothing to read, so this is an elevenfold reduction that was
  measured and not a fix that was proven. If it fires again, the thing to do is capture the failing
  output rather than re-run until it passes — recorded in the test's own header so the next reader
  does not have to rediscover it.

### Changed

- **Every gate exemption declares its class, and the report stops summing them (#51)**
  `check_gate_mechanisms.py` has always required a reason on an exemption, and reported
  `0 unresolved` — no gate lacks both a mechanism and an explanation. What it could not say is
  which KIND of explanation, and the exemptions turned out to hold **five unrelated claims**
  collapsed into one number:
  `judgement` (automating it would grade LANGUAGE rather than the work — permanent by decision,
  and pressure-tested across model tiers on 2026-08-28: redundant on Opus, and one caught a
  fabricated justification on Haiku), `debt` (missing, and the line says what), `regression`
  (**a mechanism existed and was withdrawn**), `external` (a third-party plugin enforces it), and
  `composed` (enforced by reading verdicts other mechanisms emitted, rather than by one script).
  **Two of the twelve were regressions and read exactly like debt never paid** — a retired
  session-binding skill used to refuse a session release on a bad verdict, and a retired skill
  refused to arm a goal until the target file was filled. Lost coverage and unpaid debt are
  different facts with different owners, and "N gates are not mechanized" hid the difference in
  both directions: it invites the reading that the kit has N holes, or that N deliberate
  decisions are equally fine. The sweep now prints:
  `judgement 3 · debt 6 · regression 2 · composed 1`.
  **`debt` and `regression` carry a date** (`since YYYY-MM-DD`, taken from `git blame` on each
  line rather than estimated), so the report can say how long the oldest has stood — 2026-08-27,
  12 days at the time of writing. **Ageing is reported and not enforced**: failing on age by
  default would fire on every consumer that has not decided its own ceiling, so `--max-debt-age
  DAYS` makes it a gate for a project that has. `judgement` and `external` take no date, because
  neither is expected to end and a date on them would be decoration that goes stale.
  The syntax is documented in `rules/cycle-rule-schema.md § An exemption declares its class`.

### Fixed

- **`NOT-REACHED` subtracted a repo it never named** (`discover-confidence`)
  The marker's trailing lookahead permitted `/`, so a marker naming `operators/api` also matched
  `operators` and removed a genuinely-reached repository from `foreign_repos` — suppressing the ADR
  the gate exists to demand. That fails OPEN, worse in kind than the defect the marker fixed, which
  merely charged an author for an ADR nobody needed and did it loudly. Found on a consumer whose
  routing table carries both entries. One behavioural test; the mention matcher above it is left
  permissive on purpose, because over-detecting a mention fails closed.

- **A path-addressed repo counted itself as foreign** (`discover-confidence`)
  `REPO_DECL_RE` excluded `/` from its character class, so `**Repo:** cmd/service-ops` captured as
  `cmd`. A routing table addressing a monorepo module by path matched nothing, the document's own
  repo landed in `foreign_repos`, and the gate demanded an ADR for a cross-repo change to the
  repository the opportunity is about.

  Measured on a consumer path-addressed in 5 of 7 domains. Two authors had worked around it —
  one extended a `NOT-REACHED` marker over its own module, the other wrote a defensive ADR and
  recorded it as a scorer artifact. Three behavioural tests; verified non-regressive, with the
  affected opportunities scoring exactly as before.

- **`done` was a task status the schema accepted and no consumer recognised (#50)**
  Found while reviewing the loop's own documentation. `done` was in `_VALID_STATUSES`, so a
  checkpoint carrying it validated clean — but the halt-loop's exit condition is `committed` OR
  `blocked`, and `check_phase_completeness.py` computes pendency the same way:
  `pending = [t for t in tasks if t.get("status") not in ("committed", "blocked")]`. A task marked
  `done` therefore counted as PENDING **forever**: the completion promise was never emitted, and
  the loop ran until the no-observable-progress brake or a cancellation, with a diagnostic that
  pointed nowhere near the cause. Of the six consumers, the only occurrence of the word in any of
  them was inside a comment.
  **The trap was cheap to fall into**: `done` is the word an agent reaches for to say "finished".
  Accepted-then-ignored is the defect `check_progress_schema.py` was written to end — it already
  did it for the `tasks` envelope, for `task_id`, and for a missing `phase`; this was the fourth.
  Retired from the valid set with its own HIGH finding (`task_status_done`) rather than the generic
  "not one of […]", because that message sends the reader to a list and the answer is not in the
  list. Also corrected in the canonical `templates/progress-schema.json`, the driver prompt (whose
  dependency rule said `committed` or `done`), the task template's status legend, and an anti-pattern
  in `SKILL.md`.
- **Three documents described a roster that no longer exists (#50)**
  `SQUAD_AGENTS.md` counts "14 specialized agents", and fourteen is right by coincidence rather than
  by correspondence: most entries are SCRIPTS (`kit_audit_workflow.js`, `file_findings.py`,
  `lens_review.py`, `check_install_drift.py`), and only VERA is one of the fourteen agent files.
  `docs/SQUAD_AGENTS_NAMED.md` numbers fourteen too, five of which do not exist (Artemis, Atena,
  Apolo, Cerberus, Maestro) while five that do are absent (`daedalus`, `hecate`, `kairos`,
  `leonardo`, `metis`). Both are design material from 2026-09-03 that `agents/` and
  `rules/squad-map.md` overtook, and both read as authoritative to whoever lands on them first —
  two of the three were reachable from no index at all, which is how they drifted unnoticed.
  Each now carries a status header naming what superseded it and what specifically differs. Nothing
  was deleted: the personalities in the named roster informed the agents that shipped.
- **ADR-0025 is marked superseded, and its job titles are in English (#50)**
  It describes a hierarchy of PEOPLE around the system and claims the fourteen agents handle "100%
  of technical execution". The kit implements no org chart, and the two questions the ADR actually
  answers now have mechanisms: `rules/autonomy-envelope.md` for what the system decides versus what
  stays with a person, and `rules/squad-map.md` for who the fourteen are. Kept rather than deleted —
  an ADR records a decision that was taken, and removing one hides that it ever was. Six lines
  carried Portuguese job titles in a repository that is English by policy; `check_english_only.py`
  does not catch them by design (precision over recall, argued in its own docstring), so they were
  corrected by hand.

### Added

- **`rules/verdict-bands.txt` — every verdict declares its band, in one table with an owner (#49)**
  `blocking-verdicts.txt` exists because the list of *what holds an item* had been written twice
  and the two copies disagreed. Its complement — what counts as CLEAN — was then born as
  `_CLEAN_VERDICTS`, a frozenset hardcoded inside `check_phase_drift.py` with no file and no
  owner: the same defect, one file along. **Measured 2026-09-08: of 47 verdicts reachable in the
  event stream, 14 were in the blocking list, 16 in the frozenset, and 23 in neither.**
  The consequence was silent. `check_phase_drift` reads *was the previous verdict clean?* to tell
  legitimate rework from a step out of sequence, and an unclassified verdict fell to the not-clean
  default — so the out-of-order check switched itself off for half the vocabulary with nothing in
  the output to notice. Reproduced before and after: `release → PRE_RELEASED` followed by a return
  to `implement` was SILENT, as were `ITEM_VERIFIED_LOCAL` and `PRODUCT_ALIGNED`. All three are
  success verdicts, and `cycle-rule-schema.md` says of `ITEM_VERIFIED_LOCAL` that it is *"in the OK
  column on purpose — reporting it as blocked would file finished work as outstanding"*. The only
  mechanism computing bands disagreed with the document that declares them.
  **This is not a renaming.** `cycle-rule-schema.md § Why each vocabulary differs` argues per cycle
  why the tokens diverge, and those arguments hold: collapsing `ITEM_KILLED` into `INVALID` would
  file the cycle's most valuable result as a failure and create a standing incentive to ship weak
  findings rather than kill them. The names carry domain meaning a band cannot; only the
  classification is unified. That document is where a band is ARGUED, the registry is where it is
  COMPUTED, and a disagreement between them is a defect in the registry rather than a second opinion.
  **`orthogonal` is a band of its own**, because forcing `AWAITING_REVIEW`, `BACKLOG_EMPTY` and
  `AWAITING_HUMAN` into a scoring column is what produced a classification nobody could state.
  **Band and blocking stay separate axes.** `FAIL_SOFT` is `redo` and blocks nothing; `NEEDS_FIXES`
  is `redo` and blocks. Deriving either from the other would wall every working rework loop, or let
  a real wall advance.
- **`mechanisms/gates/check_verdict_bands.py` (#49)**
  Sibling of `check_orphan_verdicts.py`: that one asks whether anything can EMIT a verdict, this
  asks whether anything knows what it MEANS for the flow. Sweeps in two directions — declared but
  unclassified, and blocking but unclassified — and reports an unreadable registry rather than
  treating it as full coverage. It reuses its sibling's extraction rather than repeating it: two
  definitions of "a declared verdict" would drift, and this gate would pass while sweeping a
  different set.

### Fixed
- **`check_panel_capability.py` would have turned the CI red for a healthy repository (#49)**
  Introduced one commit earlier and caught by running it under a PATH with no `codex`: the gate
  collapsed two facts with opposite audiences into one `VIOLATED`. A declaration that cannot form a
  panel on ANY machine — fewer than three reviewers, or one family supplying every vote — is the
  repository's defect and must fail everywhere. A declared binary missing on THIS machine is not,
  and `verify_ecosystem` runs in CI, where `codex` is absent by definition. `UNREACHABLE` is now its
  own result with its own exit code, reported as NOT_RUN by `verify_ecosystem` and as a real
  obstacle to whoever is about to start a run. Verified: with the tools a runner has and no `codex`,
  `verify_ecosystem` exits 0.
  An unparseable registry moved the other way, from NOT_RUN to a failure — it is a repository file,
  and its own gate already treated the equivalent as a defect.

### Changed
- **`check_phase_drift.py` no longer carries its own copy of the clean-verdict list (#49)**
  `_CLEAN_VERDICTS` is gone; the checker reads `rules/verdict-bands.txt` through
  `verdict_bands.clean_verdicts()`. An absent registry raises rather than defaulting to an empty
  set, on the same grounds `blocking-verdicts.txt` states for itself: an empty list makes every
  stream conform while checking nothing. A test asserts the frozenset does not come back — the
  defect was never a wrong value, it was a second place to hold one.
- **`verdict-bands.txt` is the kit's, not the project's (#49)**
  Added to `kit_owns_txt()` in `install.sh` alongside `cycle-phases.txt` and
  `blocking-verdicts.txt`, for the reason already written there: preserved by extension, a consumer
  keeps whatever classification it first received while the kit ships a corrected one — and an
  unclassified verdict silently disables the drift check.

- **DISCOVER and PLAN are judged by a panel of three, and advance on 2 of 3 (#48)**
  Both phases produce a document no script can judge. `discover-confidence` and
  `plan-confidence` are deterministic and score STRUCTURE — pointers resolve, corners are
  populated, the contract is satisfied — and what they cannot ask is whether evidence that
  *resolves* actually *supports* the conclusion drawn from it. That question now goes to
  three reviewers declared in `rules/review-panel.txt`, and below the majority the document
  returns as `NEEDS_REVISION` — a verdict that already existed and already held an item, so
  no token was invented for a state the vocabulary had.
  **At least one reviewer must come from a recognised model family outside the kit's own.**
  Three Claudes asked three times are three correlated opinions: a plausible fabrication
  that survives one tends to survive its siblings, which is the single thing an orthogonal
  reviewer catches. An unrecognised model supplies neither side — otherwise `--model
  anything` would prove orthogonality by typing.
  **The counting is not the point.** `review_panel.py` refuses the author sitting on their
  own panel, three votes from one family, a reviewer voting twice, a verdict with no
  reasoning, and — the one most likely to be "fixed" later — an abstention counted as
  agreement. Two approvals out of two is not 2-of-3: the threshold is over a FULL panel, so
  a missing reviewer means the panel did not convene, which is a different fact from the
  document being wrong and takes a different action (an `access` impediment for
  `halt_disposition.py`). Collapsing the two would either send an author to rewrite a
  document nobody found fault with, or let a panel of one report a majority.
  **The dissent is kept.** A minority vote that loses is the most interesting thing in the
  record — the same argument `cycle-judge-codex.md` already makes about Claude and Codex
  disagreeing — so it is reported beside the outcome rather than discarded for losing.
- **`mechanisms/gates/check_panel_capability.py` — can a panel be formed at all? (#48)**
  Asked at intake, for the reason `check_merge_autonomy.py` gives at the other end of the
  chain: without it every item is measured, planned, and then returned to the registry at a
  panel that was never formable — one impediment per item, for a cause knowable before the
  first item was selected. An absent declaration is VIOLATED (determinable from disk); a
  declaration that does not parse is NOT CHECKED, which is not a pass.
- **`rules/review-panel.txt`** — who sits on the panel, in the layer the installer
  preserves. Which models a project can reach and what they cost it are not the kit's
  business; the kit owns only the rule that a majority is needed and that the panel must
  not be one family. (#48)

### Changed
- **`alignment_judge.py` must now name the model that reached the verdict (#48)**
  `signed_by` already separated a person from a judge; it did not say WHICH judge, and the
  panel rests entirely on models being distinguishable. A signature that cannot name the
  model behind it cannot be checked for correlation with the author — it is the same
  unfalsifiable claim the judge exists to be more than. `--model` is now required on the
  CLI, and a direct API call that omits it writes `unrecorded` into the brief rather than
  silence, so incomplete provenance is visible instead of assumed.
  **What this does not fix, stated in the file:** the judge still takes its verdict on the
  command line and does not read the evidence itself. Its docstring promises that it does;
  nothing in it verifies that, and nothing can — the promise is made by the invoker. The
  module now says so and points at `review_panel.py`, which is structurally independent
  rather than attributably claimed.

- **BREAKING (doctrine) — nothing between DISCOVER and ACCEPTANCE waits for a person (#47)**
  Ten places in the phase rules ended a halt with *escalate to the human*, *surface to human*
  or *ask the human*: a gate failing twice, a halt-loop with no observable progress, a
  `code_quality INVALID`, a CVE on a planned dependency, a plan the CHANGELOG could not level,
  a tag already cut. Each is correct while somebody is coming, and each is a queue that stops
  for as long as nobody happens to look — the failure `rules/autonomy-envelope.md` names in its
  own opening, distributed across ten phases instead of one. The span is now closed:
  `rules/autonomy-envelope.md § The autonomous span` replaces every one of them with a return
  to the registry, and `mechanisms/cycle/halt_disposition.py` decides which of the two ways an
  item goes back. **Removing the stops is only half a policy** — a loop that cannot finish must
  still stop and a failing gate must still hold, so what changed is who the stop is addressed
  to, not whether it exists. The one door that still reaches a person is a material impediment
  (a machine, a credential, elapsed time, a system not standing), it is reached through the
  registry rather than by a session standing still, and it is the four `retained_classes` of
  `rules/decision-delegation.txt` unchanged.
- **BREAKING (premise) — merging to the trunk is now a requirement of adoption, not a setting (#47)**
  Envelope floor 2 treated a remote whose branch protection requires a human approving review as
  a supported configuration: the system emitted `PR_OPEN_AWAITING_APPROVAL` and took the next
  item. That is the same pause the floor's own amendment had already identified as a stop, moved
  one layer out where it is harder to see — every item clears DISCOVER through RELEASE, parks at
  an open PR, and the queue drains into a pile of branches nobody merges. Such a remote now makes
  the chain unrunnable and is reported **before the first item is selected** by
  `mechanisms/gates/check_merge_autonomy.py`, wired into `verify_ecosystem.py`. Announcing it at
  intake costs one API call; discovering it per item costs the run. The gate reports NOT CHECKED
  distinctly from PASS — an absent or unauthenticated `gh` tested nothing, and a gate that looks,
  sees nothing and approves produces confidence where there was no verification.
  `PR_OPEN_AWAITING_APPROVAL` survives with one meaning only: a gate did not pass, which is the
  system declining to merge its own work.
- **A `Changed`-only release derives `minor` instead of pausing the chain (#47)**
  `compute_next_version.py` returned `AMBIGUOUS` and exited 3 for an `[Unreleased]` carrying only
  `### Changed` — an ordinary release shape, measured hitting the pause on an adopter on
  2026-08-18. The fact it needs is genuinely absent from the section and always will be: a
  CHANGELOG records what changed, not who depended on it. So the question is answered once, in
  writing, toward the recoverable error. The two mistakes are not symmetric — `patch` on a real
  break ships it silently to every caret range, which is the single failure semver exists to
  prevent, while `minor` on a compatible change leaves a version number larger than it needed to
  be and a caret range does not even pick it up. The stated cost: a release that only reworded a
  log line takes a minor bump. `AMBIGUOUS` now means only that the section has no entries at all
  — a release with nothing in it — and stays a refusal rather than becoming a default.
- **The alignment gate stopped saying *a human signed* in the two places that still said it (#47)**
  `cycle-plan.md` described the gate as *machine ≥ 90% AND a human signed off* in its flow diagram
  and its phase table, contradicting `skills/_kit-rules/alignment-threshold.md § Amended
  2026-09-01` — which requires a reviewer who is not the author, a condition `alignment_judge.py`
  satisfies — and contradicting `cycle-implement.md`, corrected at the time. Honoured literally,
  the stale wording re-froze every unattended run at `AWAITING_REVIEW`, which is the exact halt
  that amendment exists to end. The same sentence had already been fixed once elsewhere; this is
  the copy that was missed.
- **`deps-audit` is a step of the chain rather than a human errand (#47)**
  `cycle-plan.md` called running the audit *"the human step that remains"* while everything below
  `cycle-backlog` was already meant to run unattended, which left the cycle's strongest gate
  depending on somebody remembering. The verdict was already mechanized by `check_deps_audit.py`;
  what was missing was who runs the scanner.

### Added
- **`mechanisms/cycle/halt_disposition.py` — where an item goes when a phase stops (#47)**
  Two dispositions, neither of which holds the session: `RETURN_TO_QUEUE` for a halt that is the
  queue's own work, `RETAIN_FOR_PERSON` for a material impediment. **Its fail-safe is deliberately
  the opposite of `delegated_decision.py`'s**, because the two read input from different authors:
  an unmatched `blocked_by` line a person wrote stays walled, since no match is not consent; an
  unmatched halt the system emitted with a known verdict is work, since reading a failing gate as
  an impediment would send every ordinary rework loop to a person. What keeps that default honest
  is a measurement rather than a regex — an item the queue has already returned twice for the
  same cause has demonstrated an impediment the queue cannot move, and is retained on that
  evidence. A wrong guess costs two passes and corrects itself; it does not cost a stopped queue.
- **`mechanisms/gates/check_merge_autonomy.py` — is the system actually allowed to merge? (#47)**
  Asks the remote whether the trunk requires a human approving review, and reports three states
  the caller must not collapse: HOLDS, VIOLATED, and NOT CHECKED. It objects to nothing else —
  required status checks, linear history and a force-push ban are all compatible with the
  envelope, and floor 3 asks for them.

### Fixed
- **`validate-command.py` read the verb from one repository and the branch from another (#42)**
  `strip_git_globals` removed `git -C <path>` so the commit would still be seen, and then the
  branch was resolved in the current directory — so the guard judged the right verb against the
  wrong repository, in both directions. `git -C <repo-on-main> commit` was allowed because the
  session happened to sit on `workspace`, which is a commit onto a trunk walking through the hard
  gate Rule 4 exists for; and the same command against a feature branch was refused naming a
  branch that repository was not on. `working_trees()` in the same file has honoured `-C` since
  kit#31, for the reason its docstring gives — the fleet's briefs drive git that way — and the
  branch guards never got the same treatment. The prefix is now resolved once by `_git_prefix()`
  and passed to every git call the decision rests on.
- **The credential guard read a search TERM as a file PATH (#43)**
  Every token of the command was matched against the deny globs, so `grep -rn credentials src/`
  was blocked: `credentials` matches `**/credentials`, and looking for where credentials are used
  is one of the commonest security reviews there is. `kubeconfig`, `id_rsa` and `.netrc` have the
  same shape. Worse than the block was its advice — *narrow the glob in `settings.json`* — which
  sends the reader to correct a glob that was right. A token now counts as a path when it carries
  a separator, a suffix or a leading dot, or when a file by that name is actually on disk; a bare
  word is prose. The leading dot is not decoration: `Path(".env").suffix` is empty, so the
  commonest credential file of all would otherwise have walked through the narrowing.
- **The kit boundary held against `Edit` and not against `sed -i` (#44)**
  `boundary-check` refused `Edit`/`Write` into an installed kit for a reason that says nothing
  about which tool does the writing — *a fix written inside an installed kit protects exactly one
  machine and is erased by the next install*, with the cost on record in `check_install_drift.py`
  as twenty-two kit fixes stranded in one consumer's `.claude/`. The shell reached the same files
  unread: `sed -i`, `>`, `rm`, `cp`, `mv` and `tee` all passed. The other read-only zone,
  `study-material/`, has had a shell-side guard since the beginning, so the protection existed for
  the tool an agent uses when it is being careful and not for the one it reaches for when it is
  being quick. Where the line runs moved to `squad/boundaries.py` and both hooks now ask it, so
  the two halves of one boundary cannot disagree about where it is. The module carries its own
  unit suite rather than being exercised only through the hooks that call it: it is now the single
  source of one rule, and a rule whose only test is indirect has its next edit checked by whichever
  caller happens to cover it.
- **`git branch -D workspace` was not refused (#45)**
  Every rule about `workspace` assumes it exists — it is a single permanent branch, never deleted
  and never recreated per task. Deleting it discards whatever was not promoted and leaves the next
  `git switch workspace` to create a branch with the same name and none of the history the rules
  refer to. `develop` is refused on the same grounds. A disposable branch stays the caller's
  business.
- **`cd /etc && rm -rf *` passed the recursive-delete guard (#46)**
  Judging each segment alone fixed a false positive and opened its mirror: the dangerous path
  moved into a `cd` that the `rm` segment no longer carried, so the three conditions were never
  all present in one segment. Both halves are needed — the segment rule stays, and a `cd` onto a
  system or home root now travels with it to the segments that follow.
- **`stop-validation.py` never read `stop_hook_active`, so a blocker it could not clear had no exit (#47)**
  The kit's own library documents the trap twice — `squad/contexts.py`: *"A hook that calls
  `prevent()` without checking it makes the session unstoppable"* — and the hook ignored the field.
  With a blocker the model cannot resolve (a `.env` that is deliberately there, a CHANGELOG entry
  it will not invent) the Stop was refused, the model tried again, and the hook answered the same
  way; the only exit was an environment variable the model cannot set for the hook's own process.
  Nothing tested it, because every Stop payload in the suite sent `false`. The gate now fires
  once: on the second attempt the blockers are reported in full and the session ends, saying that
  is what happened and that nothing was resolved by being downgraded.
- **Two states git reports as answers were recorded as failures to measure (#48)**
  `git rev-parse @{upstream}` on a branch that was never pushed and `git diff HEAD~1..HEAD` in a
  one-commit repository both exit 128, and neither message says *not a git repository*, so both
  landed in `_GIT_UNREACHABLE`. Every session on a local branch therefore ended under *"STOP GATES
  DID NOT RUN … This is not a pass"* — an alarm firing on the normal case, which is the alarm
  people learn to scroll past, and this one is the mechanism that keeps a secrets gate from
  passing in silence. Both are states the caller handles two lines later. The warning also claimed
  the gates *"graded an empty file list"* whether or not the list was empty; reproduced with one
  changed file present and named by the TDD gate three paragraphs under the claim it was not
  there. It now reports what it actually held.
- **Hooks granted subprocesses the whole budget the runtime granted them (#49)**
  `stop-validation` gave the leakage scan 120s of its own 120s, plus six git calls at 15s;
  `post-edit-check` gave each of two sequential linters the full 60s; `sessionstart-context` spent
  20s on drift plus four git calls of 5s against a 30s budget; `validate-command` allowed three
  5s git calls inside 10s. Being killed at the runtime's limit is the ONE failure these hooks
  cannot record — the process that would write the note is the process that died — so a
  `stop-validation` that dies takes the secrets blocker with it and leaves a session looking
  clean. Every hook that shells out now declares `*_TIMEOUT` constants, and
  `tests/hooks/test_hook_time_budget.py` checks the worst sequential path against what
  `hooks.json` allows. `validate-command` also stopped evaluating all seven of its guards into a
  tuple before reading the first verdict: three of them shell out to git and one resolves the
  layout from disk, so a command the first guard had already refused still paid for the rest.
- **`sessionstart-context.py` said nothing about git inside a worktree (#50)**
  `git_line()` tested `Path(".git").is_dir()`. In a git worktree `.git` is a file pointing at the
  common git dir, so the branch, the dirty count and the distance from upstream all vanished, with
  nothing saying why — in the environment the kit uses most, since `/review` runs its agents in
  isolated worktrees and `validate-command` carries a whole guard about the stash they share. The
  line that tells an agent which branch it is on disappeared exactly where the git discipline is
  hardest to keep from memory. It now asks git whether this is a work tree, which answers for both
  shapes, and resolves `layout.project_dir` instead of reading the process's working directory —
  a hook does not choose its CWD.
- **The public-copy rule existed twice, and the shorter copy ran last (#51)**
  `public-copy-lint` carries nine checks; `stop-validation` had rewritten two of them by hand, so
  'battle-tested', 'enterprise-grade', 'drop-in replacement', 'zero downtime', 'lock-in free',
  '<X> killer' and an unbacked 'faster than' were warned about at edit time and passed the
  end-of-session gate untouched. This kit already refuses that shape — `_credential_globs` reads
  the deny list from `settings.json` rather than keeping a second copy — and the checks now live
  in `squad/public_copy.py`, with its own unit suite, and both hooks read them.
- **`public-copy-lint.py` judged the fragment an `Edit` replaced, not the file (#52)**
  Two of the nine checks are conditional: a comparative claim is honest WITH a benchmark link, an
  SLA number is honest when qualified as a target. Reading `new_string` meant the evidence two
  paragraphs above in the same README was invisible, so the hook warned about honest sentences —
  and the first fix anybody reaches for is to switch the hook off. It reads the file, falling back
  to the fragment only when the path cannot be read.
- **`precompact-preserve.py` named a file the snapshot did not hold (#53)**
  Its closing line — read after the context is cut, when the session can no longer check it
  against anything it remembers — announced *"plan + progress are on disk under
  `.compaction-snapshots/`"*, and only the plan was ever copied there. The progress log is the
  half that matters: the plan is a stable document that survives on its own, while the progress
  log is the record of THIS session and the thing compaction makes unreproducible. Both are now
  snapshotted, the sentence names only what was actually copied, and the progress path comes from
  `ActivePlan.slug` rather than from slicing the plan's filename a second time — the duplication
  `squad/plan.py` was created to end.
- **`hooks/README.md` still described the shell era in the half nothing checked (#54)**
  `test_hook_declarations_agree.py` verifies the count line and the inventory table. The rest had
  rotted: *"Every hook uses `set -euo pipefail`"*, *"Create `hooks/{name}.sh` with
  `#!/bin/bash`"*, *"Add tests in `tests/hooks/test_{name}.sh`"* — there is no `.sh` in `hooks/`
  or in `tests/hooks/` — and a Shared Library section claiming `squad.layout` *"sets `$ECO` and
  `$PROJECT_DIR`"*, which it does not, being a module that returns a dataclass. The instructions a
  contributor follows pointed at the wrong language and at only one of the two files a hook must
  be wired into.

- **`install.sh` deleted a consumer's own hook wiring while preserving the hook file (#34)**
  Ownership of `settings.json` was modelled per top-level key, and `hooks` is the one key both the
  kit and the consumer legitimately write to. `mine["hooks"] = kit["hooks"]` therefore deleted a
  project's own hook entry on every run — no diff, no warning, and a success message — while the
  same installer walked `hooks/` file by file, ~300 lines earlier, precisely so the script would
  not be lost. The file survived; the line that runs it did not, which is the worst of the three
  states because a hook present on disk reads as installed. Measured in one consumer: its only
  mandatory pre-push checkpoint was present and inert for four days, cited in four documents as
  covering a check, while two tests asserting the hook's existence stayed green — they read the
  file, and the file was never what went missing.
  `hooks` is now merged per ENTRY, the treatment `permissions` already had: a hook is identified by
  its command, the kit's entries are refreshed from the kit, and an entry whose command the kit does
  not ship is the consumer's and survives. Retirement needs the term a union cannot supply — an
  entry in the consumer and not in the kit is either something the kit withdrew or something the
  project added — so the install records what the kit shipped in `.kit-hooks.json`, the same
  provenance `.kit-permissions.json` keeps. With no baseline nothing is removed, because on a first
  install every entry is indistinguishable from a project's own. The installer now also names each
  consumer hook it kept and each kit hook it retired, so the operation stops being silent.
  The merge moved out of the 100-line heredoc into `mechanisms/distribution/merge_settings.py`. That
  was not incidental: it is the most consequential code in the installer — it rewrites a file in
  seventeen repositories — and being unreachable except by string surgery is why almost none of it
  was tested. The one test that did reach it EXTRACTED the heredoc from the shell and exec'd it.
  22 tests now cover the merge directly, and `install.sh` refuses to run rather than copying its own
  settings over a consumer's when the module is absent.
- **`select_backlog_item.py --check` crashed on any approved item (#35)**
  `NOT_SELECTABLE` gained `approved -> ITEM_AWAITING_PLAN` when the hypothesis/commitment split
  entered `cycle-backlog.md`, and the `nexts` dict beside the `--check` return did not, so
  `nexts[verdict]` raised `KeyError: 'ITEM_AWAITING_PLAN'`. Measured on a consumer's registry: 196
  items, 5 approved, 5 crashes. A traceback is the wrong silence — it reads as "the tool is broken"
  when the honest answer is "this item is past the point where SELECT hands out work", and for
  `approved` that answer has a specific next step, which is the whole reason the status exists. The
  two tables are now one: `NOT_SELECTABLE` maps each status to `(verdict, next step)`, so a status
  added to the contract cannot arrive without its note. Nothing had exercised `--check` at all;
  five tests now do, one of which sweeps every entry of the table so the next addition is covered
  by construction.
- **Plan attestation was inert in the plugin-native layout: the writer and the readers resolved two different roots (#36)**
  `attest_plan.sh` probed for `skills/+rules/+hooks/` under `.`, `.claude/` and `.claude/plugins/cycle/`
  — a path named after the ancestor project — and fell back to `.`. In the plugin-native layout the kit
  lives outside the project, so the fallback always fired and the script operated on
  `<project>/records/plans/` and `<project>/.attestations/`, while the three hooks that consume the
  attestation read `<project>/.claude/` through `squad/plan.py`. With the plan where
  `rules/records-location.md` mandates it, `/plan-attest` exited 1 with "plan file not found", so an
  attestation could not be produced at all; with the plan at the project root, one was written where no
  hook would ever open it. Either way `Attestation.expected` stayed `None`, and `tampered` is False when
  there is nothing to compare against — so an edited plan was injected every turn with no warning, and
  the SHA256 tamper detection `SECURITY.md` advertises never fired. The script now asks `squad.layout`
  for the ecosystem, the same module the hooks resolve through, and a layout that does not resolve is an
  error rather than a write into a directory nothing consults. New suite `tests/test_attest_plan.py`
  pins the property that was missing — the file the writer produces is the file the reader opens — in
  both the plugin and standalone layouts, including that an edited plan comes back `tampered` end to end.
- **`route_domain.py` resolved the project root from its own file, so a plugin install routed by the kit's empty table (#37)**
  `_find_project_root(Path(__file__))` walked up from the mechanism's own location. In the plugin-native
  layout that location is inside the kit, and the kit has a `rules/`, so the walk stopped on its first
  step. A consumer with a valid `rules/domain-routing.txt` and its specialist on disk got
  `FATAL: <kit>/rules/domain-routing.txt: has no routing row` — which reads as "you never derived your
  table" and sends the reader to fix something already correct, the same symptom the README attributes
  to an underived table. The root is now derived from the invocation: an explicit `--project-root` wins
  outright, then `CLAUDE_PROJECT_DIR`, then the working directory walking up to the first `.git`, and
  the `__file__` walk remains last so the standalone repository and the copy install behave exactly as
  before. `check_intake_gates.py` now passes `--project-root` instead of relying on the inference, which
  is where the same defect sat one level up. Four tests cover the resolution; every existing test passed
  `--rule` or called the parser directly, which is why nothing saw it.
- **VERA asserted severity, work size and a solution from substring matches (#38)**
  `agents/vera-technical-arbiter.md` already stated the contract — *"`vera.py` still owns the emission …
  It is a formatter … You supply the judgement it used to fake"* — and the code still did the faking.
  `_detect_violations` matched keywords; `_estimate_work` contained `"57" in str(context)`, so
  `--refs app/main.py:57` sized a typo as a two-week refactor because it matched the LINE NUMBER;
  `_propose_solution` returned one of five hard-coded solutions chosen by the lens alone and never read
  its `problem` parameter, so a secret logged in plaintext was answered with "Make structure immediately
  obvious". The `FAIL_FAST` block appeared twice, double-weighting that lens in the `max()` that picked
  the winner, whose `default=` was dead code and whose ties were broken by the Enum's declaration order.
  Six Portuguese default strings reached GitHub issue bodies in an English-by-policy repository. The
  module is now the formatter its contract describes: lens, severity and the solution's parts are
  required inputs, and their absence is a refusal (exit 2) rather than a default. Size is still computed
  because it is countable — from the number of distinct files cited — with `--size` to override it.
  The suite that guarded the old behaviour pinned it against fourteen items from one consumer's registry,
  in Portuguese, one of which reads "costs 57 call sites"; it was the source of the magic literal and was
  deleted with it.
- **`issue_lifecycle.py` reported labelling and closing issues it never touched (#39)**
  Three defects, compounding into one clean report over nothing. `_find_issue_numbers_in_log` assigned
  its git command three times and the last assignment was `git log HEAD`, so the `branch` argument had
  no effect — `label_in_develop(branch="develop")` scanned whatever was checked out, in repositories
  with no `develop` at all. `_run(..., check=False)` never raised, so every `except` guarding it was
  unreachable and `labeled.append()`/`closed.append()` ran unconditionally: reproduced in a repository
  with no remote, `gh issue edit` failed and the result was `{'labeled': [42], 'errors': []}`. And
  closing was gated on `git tag --verify`, which demands a GPG signature, so in a project that does not
  sign tags every tag was skipped by a bare `continue` and the answer was byte-identical to "nothing to
  close". `_run` now returns `Ran(ok=…)` — the shape `fleet_lander.py` already uses in this directory —
  and nothing is recorded as done without it; a branch that does not resolve raises `LookupFailed`
  instead of returning an empty set; signature verification is opt-in via `--require-signature` and its
  refusals are reported in `skipped`; and `Closes #N` is read from the range since the previous tag plus
  the tag's own annotation, rather than from the tagged commit alone, which for a release cut as a
  `develop → main` pull request carries none. `fleet_supervisor.sh` now actually calls the module after
  the lander: the loop's docstring promised "route -> land -> label/close" and the old test asserted the
  order by checking the file had "3+ steps", so the module was executed by nothing.
- **`backlog_status.py --unblock` deleted the stated impediment beside the id it was clearing (#40)**
  `unblock` rebuilt the field from the surviving ids, so clearing `B-002` out of
  `blocked_by: B-002 — awaiting the sponsor's decision on hosting` dropped the whole line. The ship that
  `advance` had refused one command earlier was then allowed, and the registry retained no trace that a
  barrier had existed. This contradicted the rule `live_blockers` states in the same file — *"the ids in
  it are context, the reason is the barrier"* — which the 2026-09-03 audit had already fixed in the
  selector, the structure gate and `advance`; `unblock` was the fourth reader nobody counted. The value
  is now rebuilt from the raw field with only the named ids removed, so the prose survives and the ship
  stays refused. A bare `--unblock`, which means "clear whatever is there", still clears everything.
- **`generate_plugin_settings.py` rewrote `scripts/`, renamed away on 2026-09-01, and not `mechanisms/` (#41)**
  `REWRITE_DIRS` was a hand-curated tuple that the rename never reached, so every `mechanisms/` path in
  `settings.json` was copied into `settings.plugin.json` unprefixed. The one such path is the status
  line, which therefore pointed at `$CLAUDE_PROJECT_DIR/mechanisms/fleet/statusline.sh` in a layout where
  the kit lives at `$CLAUDE_PROJECT_DIR/.claude/`. `--check` could not see it — it compares the generated
  output against the committed file and both come from the same table — and neither could the test, which
  looped over `REWRITE_DIRS` and so only ever confirmed the generator is self-consistent with itself. The
  table now names every tree the installer copies, and the test reads that list out of `install.sh` and
  confronts it with the generated file, so the next tree added to the installer fails here instead of
  shipping a broken path. The generated `_comment_` also stopped calling the kit "the Cycle ecosystem".
- **Fifty permission rules were spelled in a form the permission checks never consult (#11)**
  Claude Code matches file permission rules on `Edit(path)` only — an `Edit` rule covers every
  file-editing tool, `Write` included — and it now warns once per inert rule at startup.
  `settings.json` carried 49 deny rules spelled `Write(...)`, over `.env` and its nine environment
  variants, private keys, keystores, `kubeconfig`, `credentials.json`, `secrets.y*ml` and
  `study-material/**`, plus one `Write(*)` in `allow`. **Nothing was unprotected**: every one of the
  50 already had an exact `Edit(...)` twin, verified as a set comparison before anything was
  touched. They were therefore deleted rather than rewritten — converting `Write(X)` to `Edit(X)`
  would have produced 50 duplicates of rules already in the file. Verified after the edit by
  diffing the parsed JSON against `HEAD`: everything outside `permissions` is byte-identical, and
  each array is exactly its old self minus the `Write(` entries. `settings.plugin.json` was
  regenerated, so a plugin install gets the same file. A test now fails on any rule spelled
  `Write(`, in either file and any of the three arrays, and — because asserting only the absence
  would also pass on a file with no file-permission rules at all — pins that the paths that matter
  are still denied through the spelling the harness honours.
  One existing test had to change with it, and it is the one that matters most here:
  `test_every_denied_read_path_is_also_denied_to_edit_and_write` swept every `Read(` denial and
  required a twin under **both** `Edit` and `Write`. That second leg was a belt that was never
  attached — the intent behind it was real, and only the spelling carrying it moved. It now sweeps
  `Edit` alone, still over every `Read(` path, and refuses to pass on an empty set. Verified by
  mutation: deleting `Edit(**/id_rsa)` fails it. Before removing anything, the tree was checked for
  code that parses `Write(` rules — there is none; the credential guard in `validate-command.py`
  builds its globs from the `Read(` entries alone, so no kit-side enforcement rested on them.
- **The inventory of `rules/` sent readers to four files that were not in it, and the validator could not see a single one (#11)**
  `rules/README.md` is the document that answers *where does a rule live*, and it states the
  ownership doctrine the rest of the kit follows. Measured 2026-09-07: four names in its tables did
  not resolve. `discover-plan-golden-rule.md`, `review-model-routing.txt` and
  `audit-trail-rotation.md` moved to `skills/_kit-rules/` on 2026-09-01 and the tables did not
  follow; `dogfood-golden-rule.md` was residue of the `dogfood` → `honesty-gate` rename in `7d6f228`
  and had been standing in for the `honesty-gate-golden-rule.md` row that is on disk — so the one
  golden rule missing from the list was the one the stale name displaced. Two other documents
  misdirect the same way, found by the same sweep: `cycle-release.md` lists
  `audit-trail-rotation.md` among three siblings that ARE in `rules/`, and `english-only.md` cites
  `rubric-v1.md`, which is in `skills/plan-confidence/templates/`.
  `check_xrefs.py` reported PASS on all six for two independent reasons, and the second is the one
  worth fixing: Check 7 needs the literal `rules/` prefix, which the inventory never uses because
  its reader is already in the directory; and Check 3 resolves a bare leaf with `rglob` across the
  whole tree, so **a file that moved OUT of `rules/` still resolves** — and it only reads the
  `## Cross-references` section of `cycle-*.md`, never the README. New Check 11 closes both: inside
  `rules/*.md`, a bare name whose file lives elsewhere in the kit FAILS unless the same document
  also gives the real path (which is what keeps `alignment-threshold.md` silent — `cycle-brainstorm`
  and `cycle-plan` cite it bare and locate it in the same breath), and in `rules/README.md` alone, a
  name resolving nowhere FAILS. The "lives elsewhere" arm deliberately cannot reach a name that
  exists nowhere, which is what keeps the eleven legitimate bare cites quiet: the four documents a
  consumer produces, an external plugin's state file, and the golden rule `cycle-judge-codex.md`
  names in a sentence saying it never existed here. Mutation-verified — restoring any moved name
  fails the new check alone.
- **The same inventory omitted fifteen of the fifty-one files it inventories (#11)**
  Found by repairing the four dangling rows above and then asking the opposite question.
  `cycle-brainstorm.md` was absent from a table that purports to list the cycle contracts;
  `squad-map.md`, the 360º view the kit points readers at, and `autonomy-envelope.md`, cited by two
  cycle rules as the authority for what runs unattended, were absent from every table. An omission
  reads differently from a dangling row and is worse in one way: a reader who checks the inventory
  and does not find `decision-delegation.txt` concludes the kit has no such rule, rather than that
  the list is short. Half-fixing an inventory is also how the first defect was born — this file
  already records a table trimmed while the prose describing it was not. All fifteen are now listed,
  and a test sweeps the directory rather than trusting the tables, with no exemption category:
  every file under `rules/` is something a reader may have to find.
- **An orchestrator branched on a verdict the cycle it named has never emitted (#11)**
  `cycle-idea-to-release.md` stated that *"`cycle-maintenance` emits `ROADMAP_BLOCKED`"*. That token
  appears zero times in `cycle-maintenance.md`; the one it emits is `BACKLOG_BLOCKED`, declared in
  three places with a table row explaining why it is not `BACKLOG_EMPTY`. `ROADMAP_BLOCKED` is
  residue from the `cycle-roadmap` → `cycle-maintenance` rename — the same rename `check_xrefs.py`
  Check 8 exists because of, surviving one layer deeper: Check 8 validates that the CYCLE named
  exists and never asks whether the TOKEN attributed to it does. This is worse than a dangling
  reference, because a branch wired against it is structurally correct, passes every gate, and can
  never fire. A sweep now asserts that a verdict a rule attributes to a named cycle appears in that
  cycle's own contract, and fails on vacuity so a rotted pattern cannot report green.
- **Four verdicts could stop an item while being absent from the vocabulary that defines verdicts (#11)**
  `cycle-rule-schema.md` closes its matrix with *"Do NOT introduce a new verdict token without
  adding it to this matrix"*, and four tokens in `blocking-verdicts.txt` were not in it. The one
  that matters is `AWAITING_HUMAN`: declared in the `## Verdicts` sections of `cycle-plan.md` and
  `cycle-release.md` with **"Emit it."** in bold, named in six of the twelve contracts, carrying the
  B-058/B-059 measurement that put it on the blocking list — and invisible to anyone learning the
  vocabulary from the schema. `INVALID_AWAITING_HUMAN`, `NEEDS_SPLIT` and `FAIL` were absent for the
  same reason, and they are why the fix is a new `### Tokens that belong to no single cycle` section
  rather than four table rows: none belongs to one cycle's column, and forcing them into a row would
  file a token under a cycle that does not own it. A test now fails when a blocking verdict is
  undocumented, so the two lists cannot drift apart again.
- **The protocol for changing a LOCKED rule required a record in a directory git ignores (#11)**
  `cycle-rule-schema.md § Golden Rule Change Protocol` required, as step 1, an ADR in
  `records/adrs/`. `.gitignore:66` excludes `records/` wholesale, so the justification for changing
  the kit's most locked contracts went somewhere that reaches nobody who clones. The contradiction
  was already load-bearing rather than theoretical: `plan-confidence-golden-rule.md` extended a gate
  on 2026-08-26 and wrote its reasoning into the golden rule instead, saying so in the file —
  *"the files under `records/adrs/` are gitignored and do not reach whoever clones, so the record
  lives here, in the file that travels."* Somebody following the protocol had to break it to be
  useful. Step 1 now names `docs/ADR/`, which is versioned and where the kit's only ADR already
  lives; a consumer's run-local ADRs stay under `records/adrs/`, which is what the two allowlist
  files mean when they require one for an exemption. A test resolves the path step 1 names through
  `git check-ignore`, so the destination cannot silently become unversioned again.
- **An argument against reading fifty-four files counted files nobody had recounted (#11)**
  `rules/README.md` argues the injected pointer is the whole interface and that "a pointer at
  fifty-four files is not one". The directory holds 52. The argument survives the correction — the
  number did not, and `pyproject.toml` already states the doctrine, written after a count there said
  64 while the tree held 80: *a number nothing recomputes is a claim that rots*. The count is now
  recomputed by a test rather than asserted, and the test is scoped to the sentence making the claim
  so the document stays free to quote a figure it has since corrected.
  `rules/records-location.md` told every reader the one-records-per-project constraint was enforced
  three ways. Measured: the scaffold holds (`install.sh:772`, `patch_install.sh:386`);
  `install_goal_hook.py` was deleted in `77501b0` with the `session-goal` skill it belonged to; and
  the finding `split_knowledge_base` appears in that rule and nowhere else in the repository — the
  `--records` flag is real, the finding never was. A section like that is worse than listing none,
  because a reader told a gate exists stops looking for the gap. The rule now says what holds and
  strikes what does not, and a sweep over `rules/` fails when any of them names a script the kit
  ships nowhere.
- **A registered gate had no entry point, so it has never checked anything (#11)**
  `check_readme_advisory_skills.py` defines a correct `check()` and had no `if __name__ == "__main__"`
  block. `verify_ecosystem` runs it with `sys.executable <path>`, which defined three functions and
  exited 0 — and the verifier drew `✓ README advisory skills` for it on every run since the gate was
  added. Measured against a planted inconsistency: a README citing a skill absent from disk produced
  exit 0 and no output. Every test for the module called `check()` directly, so all of them were green.
  It now has a `main()`, prints what it examined on every outcome, exits 1 on findings, and reports
  NOT CHECKED rather than passing when neither document is present. A sweep asserts no gate the
  verifier runs as a script lacks an entry point; it found exactly this one.
- **The README described three skills deleted eighteen months of commits ago (#11)**
  Found by making the gate above actually run: it reported `1 skill(s) cited … 31 on disk`, and the
  paragraph under the one-row table still read "**Each** refuses the shortcut its field is prone to"
  followed by three shortcuts — CP-or-AP, unbounded buffer, non-idempotent retry. Those are
  `cap-theorem-specialist`, `backpressure-specialist` and a resilience skill, all removed in `e5527e6`,
  the commit this gate exists because of. The table was trimmed and the prose was not. The gate cannot
  see it — it matches names in table cells and prose describes without naming — so a test pins the one
  relationship that already went wrong: a one-row table may not be described in the plural.
- **The installer promised a deletion it stopped doing, and the drift report named the wrong owner (#11)**
  `install.sh --force` printed "anything the source does not have is DELETED" — describing behaviour it
  lost on 2026-08-29, the same day the preservation pass landed. That line is what a reader sees at the
  moment they decide how to reinstall, and believing it is a reason to clear your own files out of the
  way first. In one consumer a cleanup did exactly that and took the project's push gate with it, three
  times. Measured before changing it: with the file in place, `--force` exits 0 and it survives.
  Separately, the drift report labelled every install-only file in a kit directory `unharvested`, which
  tells the reader the kit should take it back — right for stranded kit work, wrong for a file the
  project wrote. It now names what was observed and leaves the reading open. The session hook matches
  the stable head of that label rather than the whole sentence, because coupling it to a sentence is
  how a partial upgrade drops the line in silence. (#33)
- **The ecosystem verifier drew a tick for eight checks it never ran, and ignored the flag naming what to check (#11)**
  Eight of its checks delegate to a gate script and skip when that script is absent — deliberate, so
  a partial consumer install does not fail. But the skip was spelled `True`, so it printed `✓ Cross-references`
  with `check_xrefs.py not installed — skipping` on the line below. A reader scanning marks was told a
  gate had checked something that was not on disk. Skips now return a distinct `NOT_RUN`, print `⊘`, and
  are counted on every run. Separately, `main()` read no arguments at all: `--ecosystem-dir <path>` was
  accepted and discarded, so the verifier reported on whatever tree it found while its header named that
  tree — green, complete, and about the wrong subject. The flag is now honoured and an unrecognised
  argument exits 2.
- **The drift report named an empty variable as the source of a value it read elsewhere (#11)**
  The manifest fallback added earlier the same day printed `vs SQUAD_KIT_SOURCE=<path>` even when
  the variable was unset and the path had come from `.kit-manifest.txt` — so a reader chasing a
  wrong path would inspect the variable, find it empty, and find nothing wrong with it. The line
  now names whichever of the two actually answered. Found by running the hook in a real install;
  the unit test for the fallback stayed green throughout, because it called the resolver and never
  read the message. (#23)
- **Two of the three readers the sweep found were enumerated and never checked (#11)**
  Adding a file to the readers list proves it exists, not that the set inside it is right —
  a gap measured the same way it was found, by mutation. Deleting `approved` from
  `check_intake_gates.ACTION_BY_STATUS`, and rewriting `build_agenda`'s terminal-set test as a
  positive list of open statuses, both left the entire suite green. Each now has an assertion on
  its behaviour, and each kills its mutant alone. `build_agenda` needed no fix: it decides by the
  TERMINAL set negatively, which is why `approved` reached it for free while five readers that
  enumerated the open statuses positively all broke — so what is pinned there is the shape, by
  exercising a wall on an approved item rather than by reading the source.
- **The pipeline could not advance an item past PLAN, and the fix was a decision rather than an edit (#11)**
  `approved` entering the contract made `triaged -> planned` illegal, and `pipeline_orchestrator`
  walked exactly that, so every item stopped at the same place. Letting it walk through would have
  made `approved` mean "the pipeline reached this item" instead of "somebody with the authority
  decided", which is the entire content of the state. It now parks there and names the decision it
  is missing. That refusal is read rather than chosen: `rules/decision-delegation.txt` retains
  `governance` — *delegation cannot authorize the thing it would be a bypass OF* — so no consumer's
  delegation file can hand approving over. A second defect surfaced in the same function: a
  send-back to PLAN wrote `triaged`, which `ALLOWED["planned"]` does not permit, so a rejected plan
  emitted a write the registry refuses. Send-backs now have their own map and land at `approved` —
  review rejected the plan, not the commitment. (kit#32)
- **kit#28's closing measurement, taken against real git instead of argued (#28).** The reported defect was N consumer items dispatched into ONE working tree: 21 dirty files from 6 items, every lane's `/implement` pre-flight failing on another lane's artifacts, and the router capped to one consumer item as a workaround — a cap removed in the same commit that added a worktree per lane, so nothing falls back if the isolation does not hold. The unit test added earlier proves the router hands out three distinct paths; it cannot prove three worktrees at those paths are independent, because that is a property of git. This creates them the way the brief prescribes — taking the path FROM the brief rather than retyping it, since a test that invents the command proves nothing about what a lane is told — dirties ONE, and asserts the other two stay clean. Mutation-verified: pointing every lane at a shared path fails both tests, one on the collision and one on the dirt crossing between trees. What it still does not establish, and why the issue stays open: that a lane given the brief obeys it. This measures the mechanism the brief relies on, not the agent reading it. (#28)

### Fixed
- **The test that pins the readers of `status:` enumerated five of eight, and three of the missing ones were wrong the same way (#32).** `test_status_readers_agree.py` was written the day `approved` entered the contract, for exactly the failure of a status reaching some readers and not others — and its own list was the defect it guards against. Sweeping the tree instead of listing it found `check_intake_gates.ACTION_BY_STATUS` (a duplicate of an approved item fell through the dedup table and got its own id), `squad_boss.OPEN_STATUS` (**a halt whose cause had been approved read as no longer live, so the halt was reported resolvable while the thing holding it was open** — an approved cause is more owned than a triaged one, not less), and `pipeline_orchestrator.STATUS_ON_ENTERING`, which is left exempt with its reason because fixing it needs a governance answer rather than an edit: it walks `triaged -> planned`, now illegal, and the obvious repair has the pipeline approving items it selected itself, which empties the state of meaning. Filed as #32 with three options and none taken. Two holes in the new sweep, both found by mutation and both closed: `git grep` reads the INDEX, so an untracked reader was invisible until `--untracked`; and enumerating a file proves it exists while proving nothing about the set inside it — removing `approved` from `squad_boss` left every assertion green until a test asserted on that tuple directly. (#32)

### Fixed
- **The drift gate was wired and still inert: it only ran if a consumer exported a variable documented nowhere (#23).** #23 reported `check_install_drift` cited nine times in prose and executed by nothing. Wiring it into `sessionstart-context.py` did not close that, because `drift_line()` returns None unless `SQUAD_KIT_SOURCE` is set — and the variable appears in no README, no rule and no install output, only in the hook's own source, so a consumer could not learn that opting in was possible. A diagnostic nobody can reach is the drawer it was in, with a nicer handle. The installer already knows the answer: it copies FROM a directory and writes `.kit-manifest.txt` INTO the target on every install, so it now records `# kit-source: <path>` there and the hook falls back to it. The opt-in disappears; a consumer who never heard of the variable is told when their kit is stale — which is the case #23 measured, ten hours on a kit missing three merged repairs. `SQUAD_KIT_SOURCE` still wins when set, because exporting it is an explicit choice (usually a second checkout) and a fallback that overrode it would be its own defect. A `#`-prefixed line, so the manifest's existing readers, which all skip comments, are unaffected. Both halves mutation-verified. (#23)

### Fixed
- **The snapshot suite that exists to catch scorer drift pinned nine plans that do not exist, and skipped its way to green (#30).** All nine lived under `records/plans/` — a directory `.gitignore` excludes wholesale and `test_kit_is_read_only.py` declares consumer-owned — so every parametrised case reached `pytest.skip` and the file reported green having compared nothing. Measured 2026-09-05: one of the nine survives anywhere on this machine, in a backup outside any repository; eight were never versioned, so the corpus cannot be restored and re-pointing at it is not a fix. What could be pinned was already in the kit and unread: `skills/plan-confidence/fixtures/` holds four committed plans that no test in `tests/*.py` opened, and scored today they cover the three bands the suite exists to hold — SHIPPABLE at 100, SHIPPABLE_WITH_CAVEATS at 70 by two different routes, INVALID at 49. The floor now lives in the kit, versioned and reproducible; a consumer's plans remain a bonus rather than the whole basis, and the resolver looks in the kit FIRST because resolving to a gitignored directory first is how nine plans became nine silent skips. Two properties the file never had: vacuity is now a failure rather than a green report, and the corpus is swept rather than listed, so a fixture added and not pinned fails instead of looking like coverage. Both mutation-verified. (#30)

### Fixed
- **Nothing asserted that two lanes get two different worktrees, and the first attempt at asserting it measured the branch name instead (#28).** `test_the_consumer_brief_gives_each_lane_its_own_worktree` proves ONE lane is told to cut a worktree; it would pass identically if every lane were sent to the same one, which is kit#28's defect one indirection along. The new test asserts over a SET — three units must yield three distinct paths, each naming its own item, so a path keyed only by a timestamp cannot collide when the router dispatches inside one second. **The first version of it passed against a mutant that sent every lane to `/tmp/squad-cycle/shared`**, because it captured the whole `worktree add` line, which also carries `-b cycle/<slug>` and therefore differs per lane by construction: it was proving the branch was distinct while the path collided. Now it extracts the quoted path. What this still does not establish, and the issue stays open for it: a live multi-lane run reaching `/implement` Step 1 with a clean `git status` in each worktree. The router controls the instruction, not whether a lane obeys. (#28)

### Fixed
- **A sixth place pinned item ids to exactly three digits, and it was in prose where no assertion could see it (#21).** `tests/test_item_id_readers_agree.py` imports five readers and compares their regexes, which covers code and not a `SKILL.md` that states the shape in words — and `skills/idea-to-release/SKILL.md:52` routed backlog-driven mode on `^B-\d{3}$`. A registry crossing B-999 would have routed nowhere from it, silently, which is the failure the file's own header says it exists to prevent one level down. Widened to `^B-\d{3,}$`, and the tree is now swept rather than trusted: anything writing the exactly-three-digit form must be enumerated with the reason it is not a reader, in the shape of the worktree sweep. Mutation-verified — restoring the narrow form fails exactly the new test. (#21)

### Fixed
- **The fix for #25 added two verdicts and left `main()` unable to print either.** `state()` gained `busy` and `unknown` so a lane mid-turn stops being reported ready — the whole point of that issue — and `_ADVICE` was not extended, while `main()` indexes it unconditionally. So the two verdicts the fix exists to produce were the two that raised `KeyError` at the entry point. It failed CLOSED, which is why nothing was ever typed into a busy lane and why this was not urgent in the dangerous direction; but the operator got a stack trace where the point was a sentence, and `busy` (transient — wait) became indistinguishable from `unknown` (something is wrong — go look), which call for opposite actions. Both now carry advice, and `tests/test_session_ready.py` asserts over the verdict SET rather than the two names, so a seventh verdict added later fails there instead of at an operator's terminal. Found while triaging #25 as genuinely fixed: a fix measured only against the defect it targeted is a fix measured too narrowly. (#25)

### Fixed
- **The repository's own english-only rule was failing on 111 lines, and two of the ten files were entire documents in Portuguese.** `mechanisms/gates/check_english_only.py` is one of the five checks on the promotion PR, and it had been red — so the rule the kit enforces on everyone else was the rule the kit was breaking. Two documents created this week, `docs/LEONARDO_DEEP_RESEARCH.md` (453 lines) and `docs/SQUAD_AGENTS_NAMED.md` (578), were **translated**, not exempted: the per-line escape exists for a line where the Portuguese IS the data, and a whole document is not that. Both are line-for-line replacements with structure preserved — fence counts even, table pipe counts consistent, heading counts identical. The remaining 29 lines across 8 files are the legitimate shape and now say so, each with its own reason rather than a blanket one: a regex that matches Portuguese registry prose (`delegated_decision.py`), keyword lists a classifier matches against Portuguese context (`vera.py`), verbatim quotations of what a real item says about itself, and test fixtures written in the language the classifier under test reads — a test rewritten into English would pass while testing nothing. One reason was keyed by file and landed wrong on a line that was a quotation rather than a pattern; corrected, because a reason that does not describe its line is the same defect this ecosystem spent the week removing. (#11)

### Fixed
- **The shell-boundary rule was written for one caller, and the same hazard bit five times through another door.** `loop-engine-convention.md` said ralph-loop's positional prompt is shell-evaluated, so a driver prompt with backticks goes to a file — correct, and scoped to ralph-loop. The identical failure arrives through `ssh host "… <<'QUOTED' …"`: the heredoc IS quoted, so the remote shell leaves it alone, and the OUTER double quotes hand everything to the local shell first, where backticked words execute and arrive as empty strings. The command exits 0, the file is written, and a sentence loses two words from its middle. Measured five times across 2026-09-04 and 05 by a coordinator driving a remote host — the fifth inside a comment about avoiding it, which is the argument for a written rule over care: care was being applied at the moment it failed. The rule now states the general form (*text with shell metacharacters goes to a file that is copied, never through a command line*) with the loop's prompt as one instance rather than the statement, and `fleet_router.brief()` carries the short form plus the citation, so a lane reads it where lanes actually read. `tests/test_briefs_name_the_shell_boundary.py` pins both halves and the count that makes it a finding; all four assertions mutation-tested. (#11)

### Fixed
- **An item impeded by prose could neither ship nor be cleared, so the mechanism had no legitimate exit and hand-editing was the only one left.** The two readers of `blocked_by` disagreed about what counts as an impediment: `advance` asks `blocked_by_raw` and refuses to ship while the line says anything at all, while `unblock` asked `blocked_by_of`, which extracts `B-NNN` ids, and refused with *"is not blocked"* when the line held a decision instead of an id. Prose is a supported shape — `--because` exists to write it, `carries_prose()` exists to recognise it, and `effective_state_of` reads it as blocked — so the deadlock hit exactly the items whose impediment was a person rather than another item. Measured 2026-09-05 in a consumer: B-168 declared *"fix estrutural pertence ao repo do kit"*, the fix landed in this kit and was verified there, and the mechanism could not move the item at all. A bare `--unblock` now means what it says — clear whatever is there — while `--unblock B-002` still refuses when the named id is absent, because that refusal was always correct. Mutation-verified: deleting the new branch fails exactly the new test. (#11)

### Fixed
- **The recursive-delete guard matched its three conditions across DIFFERENT commands in one line, and refused work nobody had asked it to refuse.** `check_rm` searched `rm`, a recursive flag and a dangerous path independently over the whole command string and ANDed the results, so it assembled a deletion nobody typed: `rm nota.txt && grep -rn padrao /etc/hosts` was blocked as *"'rm -r' on a system/home-root path"* with no `rm -r` and no root path anywhere in it. Same for `grep -rn foo /etc && rm nota.txt` and `ls -R /etc && rm -f nota.txt`. The three conditions are now required to hold in the SAME segment, via the `segments()` helper whose own docstring already stated the rule — *"judged per segment, so an unrelated `cp` in a compound is not blamed on a zone path that appears elsewhere in the same line"* — and which `check_zone` was already the only caller honouring. Every block still blocks: `rm -rf /`, `$HOME`, `~`, `/etc`, and `echo start && rm -rf /etc`, where all three conditions do live in one segment. A NEWLINE now separates segments too, alongside `;`, `&&` and `||`: the Bash tool is handed multi-line blocks routinely, and leaving newline out kept every one of them as a single segment — which is exactly where this false positive survived its first fix, since `rm -f x_test.go\ngrep -rn foo cmd` is two commands and judging it as one assembles an `rm -r` out of parts belonging to neither. Eight cases added to `tests/hooks/test_validate_command.py`, five of them red before the fix and mutation-verified after: reverting `segments(command)` to `[command]` kills exactly those three and leaves the other eight rm cases green. **This regressed before.** A consumer measured it, fixed it in the bash hook, and the Python rewrite reintroduced it — and nothing caught that, because the consumer's own guard test sent a payload with no `hook_event_name`, so the hook failed closed on every row and the whole table was measuring its own malformed input rather than the guard. (#11)

### Added
- **kit#28's scope note left one hazard unmeasured, and measuring it said the opposite (#11)**
  `cycle-events.jsonl` is one file appended by every lane with no lock. The observation was right;
  the conclusion would have been wrong. Eight concurrent processes writing 40 events each at 12 KB,
  200 KB and 1 MB payloads lost nothing, every run: `O_APPEND` makes the seek-and-write one
  operation, and the appender hands the text layer ONE string per event. Both halves are now pinned,
  because neither is guaranteed by the language — splitting the write, or seeking before it, corrupts
  264 of 320 events. Added under `Added` rather than `Fixed`: nothing was broken, and a guarantee
  nobody wrote down is one refactor from being gone.
- **`git-safety.md` § 2 now requires one working tree per lane, because the instruction lived only inside one caller and the third dispatcher re-derived it wrong.** `fleet_router.brief()` has told consumer lanes to cut their own worktree for weeks, and the rule file said nothing about it — so a dispatcher that does not go through `brief()` had nothing to inherit. Measured 2026-09-04: two lanes were sent into one project with instructions that said "cut a branch" and not "cut your own worktree", both used the main checkout, and **35 dirty paths belonging to two different items** sat in one working tree with nothing committed on either side. The first `git add -A` would have swept one item's work onto the other's branch; the file sets happened to be disjoint and were separated by reading every diff. Nothing in the mechanism would have caught it, because a branch is not isolation — `git switch` moves the one checkout and carries uncommitted changes across. The § 4 anti-pattern list now refutes the specific belief that produced it ("each lane is on its own branch, so they cannot collide"), since a general "use worktrees" does not reach someone who thinks they already are. `tests/test_git_safety_one_tree_per_lane.py` pins the rule AND the citation inside it: the rule points at `fleet_router.py` rather than restating it, and the fourth test fails if that brief ever stops handing out a worktree — a pointer that outlives what it points at still reads as authoritative, which is worse than being absent. All four assertions mutation-tested before commit. (#11)

### Fixed
- **`approved` reached three of the five status readers, and the test written that same day to prevent exactly this could not see the gap.** The status was added to `backlog_status.py`, `check_backlog_structure.py` and `select_backlog_item.py`; `backlog_index.BUCKETS` and `board_state.STATUS_PHASE` were left behind, so an approved item fell out of every bucket count on the index and could not be placed on the board at all. `tests/test_status_readers_agree.py` shipped in the same commit and passed, because all four of its assertions check a SUBSET relation — "does this reader invent statuses" — and a missing entry is a subset. The two directions the set can drift are not the same question, and only one of them was being asked. Caught three commits later by a skill-local test in a consumer (`test_every_legal_status_has_a_bucket`), through a failing gate chain in that project rather than in this repo. Three assertions added and each mutation-tested: removing the bucket, the phase entry, or `approved` from `_STOPPABLE` now fails exactly one test. `_STOPPABLE` mattered most and was the easiest to miss — an item somebody committed to and then walled would have rendered as unobstructed, and that is the item a reader is actively waiting on. `approved` buckets as **in-flight**, not open: the bucket answers "is this being pursued", and filing a commitment beside unread hunches is the conflation the status exists to end. On the board it maps to `discover`, the same position as `triaged`, because approval is a decision and not one of the nine declared phases — the two differ in commitment, not in position. (#11)
- **`install.sh`'s own header still described the settings.json behaviour that issue #8 replaced in August, and a reader who trusted it avoided the installer.** Step 4 read *"Writes settings.plugin.json as target/.claude/settings.json"* — true only when the target has none. When one exists the installer has merged by key ownership since #8 was fixed: the kit owns its wiring (`hooks`, `statusLine`, `env`, `defaultMode`), the project owns `permissions`, and the kit's are unioned in as a floor with the consumer's kept. Measured 2026-09-04 in a consumer that had just narrowed six over-matching `deny` globs: the stale line was read as a warning that re-installing would revert that work, so six files were copied by hand instead, and the reason recorded in that project's history was a defect that no longer exists. A comment describing behaviour the code stopped having is not a small error — it is the same carried-forward claim this kit keeps finding in measurements, in the one place a reader has no reason to distrust. The line now states the merge, names what each side owns, and says what it used to say and why, so the next reader can tell a correction from an original. (#8)
- **Two agents in separate worktrees swapped their uncommitted work through the stash, and nothing said the stack was shared (#31).** `git worktree` gives each tree its own index, HEAD and checkout; `refs/stash` is not among them — it lives in the common git dir, so every tree pushes and pops one stack and `git stash pop` returns the top entry whichever tree pushed it. Measured 2026-09-04: two lanes (B-136 and B-067) stashed concurrently in their own worktrees and each popped the other's entry, recovered only because one of them noticed. The trap is that worktrees isolate everything else a lane touches, and the kit's own instructions lean on exactly that. **Five** places hand an agent a worktree and every one of them was silent: `fleet_router.brief()` in both its kit-repair and consumer forms, `kit_repair_workflow.js`, `fleet_dispatch_workflow.js`, and the pipeline's `stage-implement.md` — the issue named two, and fixing two would have left the same defect reachable through three other doors. All five now name the hazard and the substitute (copy the files aside with `cp`, or commit them on your own branch, then `git restore`), and `tests/test_worktree_briefs_name_the_stash.py` asserts it over the set rather than over the two that happened to be reported. Two tests guard the set from both sides: the count is pinned, so a brief that is renamed or moved fails rather than quietly shrinking the parametrisation, and a sweep over the tree fails on any NEW site that hands out a worktree without being enumerated — the first alone catches a removal and is blind to an addition. Guidance in a prompt is guidance the next author does not inherit, so `hooks/validate-command.py` now refuses a stash mutation whenever `git worktree list` shows more than one working tree, reading the command's own `-C <path>` before the current directory because the fleet drives git that way. `list` and `show` stay allowed — they read the stack and refusing them would only teach a lane that the guard is noise — and a repository with a single working tree is untouched, because there is nobody there to swap with. The hook's own `reset --hard` refusal stopped recommending `git stash` as the substitute. (#31)
- **A halt report with a suffix after `BLOCKED` was invisible to the selector, and the item it halted was re-offered forever (#29).** `squad_boss.halt_reports` globs `*BLOCKED*.md` (the fix landed 2026-09-04 at `fcf6029`), but nothing locked that fix — reverting the glob to the old `*-BLOCKED.md` shape passed every test the module had, while breaking the property that made B-079's two halt reports (`B-079-2026-09-04-BLOCKED-implement-preflight.md` and its `-squad1` sibling) hold the item. Measured in a consumer the same day: the item was still returned as `ITEM_SELECTED` and re-dispatched at least three times to different lanes, each writing another equally invisible report, exactly the loop halt detection exists to prevent. Test `test_a_report_with_a_suffix_after_BLOCKED_is_still_found` locks it: reverting the glob fails the test for the right reason (empty result, item missing). A companion `test_a_RESOLVED_rename_no_longer_holds_the_item` locks the retire path — the two mechanisms move together, and both need a test that fires when either drifts.

### Added
- **`delegated_decision.py` — the line between a wall a sponsor can delegate and one nobody can.** `select_backlog_item.py` reports AWAITING_HUMAN for every item whose `blocked_by` names no other item, and that single verdict covers two different situations: a choice waiting on authority, and a machine, a data series or a running system that is absent. Authority moves the first and does nothing to the second, so conflating them keeps a backlog walled for weeks — measured on the Theo registry, **14 items and a lead stalled for 21 hours**. Impediments are matched FIRST and win outright, because a wall that is both a choice and an impediment is an impediment; unrecognised prose stays walled, since no match is not consent; and a delegable item nobody actually decided stays walled too, because clearing a wall with nothing behind it is the failure the mechanism exists to prevent. `apply_delegated_decisions.py` retires the delegable ones, replacing the `blocked_by` line rather than deleting it — a wall removed with no decision in its place is indistinguishable from a wall nobody ever wrote. Against the real registry: **9 walls retired, 5 retained**, and the selector moved from `BACKLOG_BLOCKED` to `ITEM_SELECTED` with 9 startable items. Two of the nine had been walled on a condition that expired weeks earlier — B-079 and B-080 both waited on a kit-sync batch of 91 dirty files, and the tree had been clean since `91b51e7a2`. (#11)

### Removed
- **The first attempt at this, which measured its own matcher.** `mechanisms/fleet/autonomy/` classified backlog walls by substring and reported **42.9% autonomy, 6 of 14 items resolved**. It had resolved nothing: the selector kept reporting the same 14, and the lead stayed stalled. The number came from matching the word `config` inside B-139 — an item asking an operator to provision `/opt/theo` and install systemd unit files, whose own prose says *"não é trabalho de código"* — and `review` inside B-154, which needs a standing build the item marks *"não é verificável desta sessão"*. Both were reported resolvable. Had anything consumed that verdict, a lane would have been handed work it cannot do, and a lane handed impossible work either fabricates it or stalls. It was replaced rather than repaired: the defect was not a bad pattern list but the absence of the distinction the replacement is built on, and it is this kit's most-found defect — an inability to measure, published as a measurement. (#11)  <!-- english-only: verbatim quotation from the registry it describes -->
- **Fleet dispatch via Workflow (`fleet_dispatch_workflow.js`) — structured JSON instead of prose.** The router sent units to lanes as markdown prose instructions, which every lane had to interpret — space for misunderstanding. Dispatch now passes structured JSON with `repo`, `tracker`, `unit{slug, number, title, body, branch}`, `worktreeRoot` — the same payload shape the workflow expects — and the lane is told to invoke the workflow verbatim with those args. `fleet_router.py` gained `resolve_unit_payload()` to fetch issue metadata via `gh`, and `dispatch(mode="tmux"|"workflow")` to support both old and new paths. Default is `tmux` for backward compatibility; mode can be overridden at dispatch time. Workflow is two phases: Repair (RED→GREEN with the unit issue) and Verify (independent agent checks the branch). (#11)
- **Issue lifecycle automation (`issue_lifecycle.py`) — label on develop, close on release tag.** The user's rule: "Never close on merge, only on release." This enforces it: when a commit reaches develop (merged or direct), labels the issue `in-develop` via `gh`; when a version tag is verified (`git tag --verify`), closes it. Two observables, two events, two outcomes. Labeling is idempotent; closing an already-closed issue is safe. Runs as the third step in `fleet_supervisor.sh` loop. (#11)
- **GitHub auto-comment on duplicate findings (`file_findings.py` enhancements).** When `triage()` detects a finding is a duplicate of an existing (open or closed) issue, the old behavior was to skip it. New behavior: post a "seen again" comment on the existing issue via `gh issue comment`, with an anchor to guard against spam (`already_commented()` checks for duplicate comment). Prevents duplicate issues while preserving the audit trail of where the pattern was seen again. (#11)
- **Slack webhook notifications on release (`notify_slack.py`).** Posts a notification to a Slack webhook when a release is finalized (RELEASED verdict, not PRE_RELEASED). Config is project-owned in `rules/notifications.txt` (slack_enabled, slack_webhook_env); webhook URL is read from an environment variable (never hardcoded). Retries once on 5xx (server error), never on 4xx (client error). Always exits 0 — Slack notification failure must never block a release. (#11)
- **Plugin marketplace entry (`marketplace.json`).** New `/.claude-plugin/marketplace.json` for `/plugin marketplace add` installation path. Additive: 42 existing consumers continue via `install.sh` copy-install. Schema includes name, owner{name,email,url}, plugins[]{name,source,description,version}. Tested to stay in sync with `plugin.json` (version and description). (#11)
- **README advisory skills gate (`check_readme_advisory_skills.py`).** Ensures README.md and HOW-TO-USE.md "Advisory skills" tables match the actual skills on disk. Regression test for commit `e5527e6`, which deleted cap-theorem-specialist, backpressure-specialist, and resilience-specialist because "a fixed specialist asserts domain knowledge about repositories it has never read" — correct decision, but README was never updated. This gate catches that drift bidirectionally. Integrated into `verify_ecosystem` as a reachable gate. (#11)

### Fixed
- **The Python dead-code detector resolved `vulture` through PATH, so a host could carry an importable vulture and no reachable binary (B-172).** It shipped as `["vulture", ...]`; it is now `[sys.executable, "-m", "vulture", ...]`, resolving through the interpreter already running the detector rather than through whatever the install put on PATH. The subtle half is why `-m` alone was not enough: it moves the failure from exec to **import**, and the import failure is the quieter of the two — `python -m vulture` without the module exits 1 with an EMPTY stdout, which the parser reads as zero findings, i.e. **a green gate that never ran**. So the module is checked with `importlib.util.find_spec` before the subprocess, and a missing one returns the `auditor_unavailable` cap carrying the install command. Two tests in the same slice were guarding themselves with `skipif(shutil.which("vulture") is None)`, which after this fix would silently skip on exactly the hosts the item is about; they now guard on importability. Measured on a host with the binary removed from PATH but the module present: 5 failed before, 260 passed after. Ported from the consumer where it was written — the fix lived in an install copy of `skills/`, which `install.sh` replaces wholesale on every run, so it would have reverted on the next sync. (#11)
- **`squad_status.sh` and `workflow_watch.sh` — the outside view the single-instance architecture removed.** Retiring the tmux lanes fixed the coordination defects and took the observation surface with them: an operator typed `tmux attach -t squad1`, got `no sessions`, and the replacement — `/workflows` — is reachable only from inside the coordinating session. `squad_status.sh` reports the kit's tree, the consumer's queue and what is actually executing, from any shell. `workflow_watch.sh` reads the JSONL transcripts the subagents write as they work, so their progress is legible without the session's cooperation. Both state what they CANNOT see rather than letting silence read as idleness — `workflow_watch` reports how long a transcript has been quiet and refuses to call it thinking, waiting or finished, because from the file alone those are one observation. (#11)
- **Four roles derived from what went wrong, completing the squad at fourteen.** The source document named them and gave each an emoji; it did not say what any of them *decides*, so the authority of each was derived from a measured failure rather than from the document — stated plainly here because a role whose authority was invented is the thing the other ten are built to avoid. **Vigil** decides what deserves an interruption: the supervisor's period drifted from a configured 10 minutes to 51, 54 and 53 across three consecutive passes, `fleet_idle` sat at 94% for 27 hours, and three branches were refused three times with byte-identical reasons — all visible, all unnoticed until a person complained. **Aesculapius** decides which impediments have already been cured: seven items were held by causes that had been fixed and never re-checked, two of them on *"91 uncommitted files"* against a tree where `git status --porcelain` returned 0. **Argus** decides what is common to many cases: fourteen halt reports read one at a time were fourteen problems; read together they were four, and one was an unfiled coverage debt that four separate items waited on — a finding present in none of the individual reports. **Nemesis** decides whether the system's own claims are supported: *"42.9% autonomy, 6 of 14 resolved"* had resolved nothing, an arbiter that "does not equivocate" chose its lens by substring, and a gate printed *"PASS — every cycle's numbering is unique"* after examining zero cycles. Her seam against Eureka is exact — he audits behaviour, she audits assertions. (#11)
- **Five more roles, and the criterion that decides which scripts become agents.** The squad was four; it is ten. The line is not mechanism-versus-agent — it is **measuring versus judging**. `fleet_lander` stays a script because determinism is its protection; a component that *reads and interprets* becomes an agent because reading is. Added: **Clio** (what the record says about the past — measured: reconstructing why one item halted three times took most of an afternoon of hand-greps across four halt directories, two git logs and an event stream), **Metis** (what is true right now, and why — measured: `fleet_idle` reported 94% idle across 27 hours and nobody had asked), **Leonardo** (what a decision needs and nobody read — measured: B-001's rename was refuted by a measurement and the replacement map was never researched, so the decision recorded was "freeze it", made because research was absent rather than because freezing was right), **Eureka** (defects nobody filed, one lens per pattern this kit has shipped twice, each lens quoting a real number), and **Hecate** (what crosses from outside into the registry, split from Kairos at the moment of entry: she decides whether an arrival becomes an item, he decides where it ranks). Three of the ten decide **nothing** — Clio, Metis and Leonardo — and that is the design: every role that decides has a reason to want the evidence to read a particular way. Adding a role cost six gates: the installer, the `.gitignore` ordering, the role table in every sibling file, and a declared position in `rules/squad-map.md`. That cost is what keeps the seams explicit. (#11)
- **VERA becomes an agent, because judgement written as substring matching is judgement that cannot read.** She is described as *"the autonomous technical decision-maker"* who *"does not equivocate"*, and she chose her lens with `if any(w in problem_lower for w in ["acoplam", "depend", "boundary", "fronteira"])` — two languages of substrings, and `# Default if nothing matched: it's a clarity issue`. She then emitted a lens, a severity and a work size in that confident register, assembled from whether a word appeared in a sentence. **That is this kit's most-found defect living inside the component whose entire purpose is judgement.** A sibling was measured the same day: a delegation classifier matched `config` inside an item asking an operator to provision a host and install systemd units, and reported it resolvable — the item's own prose said *"não é trabalho de código"*. A reader sees that; a matcher cannot. The line this draws is not mechanism-versus-agent, it is **measuring versus judging**: `fleet_lander` stays a script because determinism is its protection, and VERA becomes an agent because reading is hers. `vera.py` keeps the emission — issue body, labels, schema — since formatting is computation. The agent supplies the judgement it used to fake, and refuses `INSUFFICIENT EVIDENCE` rather than inventing one, which on a nine-item batch the same day was the single most useful answer of the nine. (#11)  <!-- english-only: verbatim quotation from the registry it describes -->
- **The supervisor's two jobs run on their own clocks.** Route decides whether a free lane gets work and costs seconds; land runs two full suites per branch and costs twenty minutes. They shared one loop, so land set route's period: measured 2026-09-04, routes landed **51, 54 and 53 minutes apart against a configured interval of 10**, and a lane finishing at 14:35 sat idle until 15:22. `fleet_idle` put the window at **94% idle — 1528 minutes against 92 productive**. Nothing was broken; the cheap job was waiting on the expensive one. Two loops now, `ROUTE_INTERVAL` defaulting to 120s and `LAND_INTERVAL` to 600s, supervised together so that one dying does not leave the other printing — a half-dead supervisor that still logs reads as working, which is the same defect in a new hat. (#11)
- **Each consumer lane now cuts its own worktree, and the one-at-a-time cap is gone (#28).** The cap was the small half of that issue and it worked, but it bought correctness with idleness: with three lanes and a cap of one, two sat idle by construction. `fleet_idle` measured the cost — **94% idle across a 27-hour window, 1528 minutes against 92 productive**. The cause was never concurrency itself, it was the shared checkout: the cycle's pre-flight requires a clean tree and every lane's records dirtied every other lane's gate. Kit repairs solved this long ago by giving each lane a worktree; the consumer brief now does the same, and the lane is told to `cd` into it before running anything. `.gitattributes` in the consumer keeps the append-only records mergeable afterwards (`cycle-events.jsonl merge=union`) — the entries are independent facts about independent items, so losing either side loses a record of something that ran. The cap's two tests are removed rather than adapted: the behaviour they pinned was deliberately reverted, and a test kept for a rule that no longer holds is a rule nobody can find. (#28)
- **A halt report with a suffix after `BLOCKED` was invisible, so its item was re-offered forever (kit#29).** `squad_boss.halt_reports` globbed `*-BLOCKED.md`, anchoring the word to the end of the filename — but the reports are named by lanes, and a lane writing a second report for one item adds a descriptive suffix. Measured 2026-09-04: **B-079 had two halt reports on disk and the function returned neither**, so the selector kept answering `ITEM_SELECTED`, the router kept dispatching, and the lane kept hitting the same wall and writing another invisible report. A loop, with every surface reporting normal operation — the exact failure halt detection exists to prevent. The glob is now `*BLOCKED*.md` and `_item_of` decides whether a name carries an id, which is already its job and already handles both filename forms. `-RESOLVED.md` renames stay excluded because they no longer contain the word. (#29)
- **`fleet_router` dispatched N consumer items into one shared checkout (kit#28).** Kit repairs parallelise safely because each lane cuts its own git worktree; consumer items have no equivalent — the project's cycle runs in the project's own tree. So three lanes each took a consumer item and wrote their cycle artifacts into the same checkout, and `/implement`, which requires a clean tree, failed its pre-flight on the others' dirt. Measured 2026-09-04: **21 dirty files from 6 different items**, and the lane that got furthest refused at step 1 rather than relax a gate failing on a cause its slice did not create. The steady state of N>1 consumer lanes was that none of them landed anything. Consumer units now go one at a time, and a unit held back by the cap is named in `unassigned` rather than dropped — a startable item that vanishes from the plan reads as a shorter queue than there is. Kit units keep their parallelism. **The cap raises throughput rather than trading it away**: three consumer lanes completed zero items, one completes one. It comes out when each consumer lane has its own tree and not before — a cap removed on the assumption that isolation works is how this returns unnoticed. `cycle-events.jsonl`, one file every lane appends to with no locking observed, is a separate hazard still open. (#28)
- **`fleet_router` briefed consumer backlog items as if they were kit issues (kit#27).** Three work sources, two briefs: a consumer item fell through to the kit-repair template, which told the lane to create a worktree in the KIT and run `gh issue view B-NNN` against the kit's tracker. Neither resolves — the id lives in the consumer's `BACKLOG.md`, and the kit's registry is GitHub issues, which cannot hold a `B-NNN`. Measured 2026-09-04: the first two consumer items dispatched after the backlog was unwalled (B-146, B-165) both halted on it, and the lane that diagnosed it deliberately did not file the bug itself on the grounds that diagnosing a dispatcher from inside a dispatched lane is guessing at the caller. **Every consumer item would have failed the same way**, so unwalling the backlog bought nothing until this was fixed. A consumer unit now gets its own brief: the consumer repository, the item's registry, and `/idea-to-release` as the entry point. Briefing a backlog unit with no project path now raises rather than silently falling back to the kit. (#27)
- **`fleet_router.brief()` closed the mechanism that let the kit#27 defect land — silent fall-through to the kit template on any unknown source (kit#27 follow-up).** The specific defect was fixed by adding the `if unit.source == "backlog"` branch; the mechanism that permitted it — silent fall-through to `_BRIEF` for any source that was not "audit" or "backlog" — was unchanged. A typo (`"backlogo"`) or a source added elsewhere without a matching brief branch reproduced the same bug through a different path: a consumer-shaped unit dispatched with kit-repair instructions. `brief()` now refuses an unknown source with a ValueError that names the source it did not recognize and points at the fix (add a brief branch, or fix the source at its origin). Silent misrouting to the kit template is no longer possible. (#27)
- **`fleet_lander` paid suite prices to learn a branch could not merge (kit#26).** It ran the branch's own suite, then attempted the merge — so a branch conflicting on one line was refused only after both suites had run. Measured on the runner 2026-09-04: three repair branches conflicting on `CHANGELOG.md` cost ~20 minutes per pass across three consecutive passes, inflating the supervisor's configured 10-minute cycle to 30 and spending **an hour of fleet time proving branches correct that git would not let land regardless**. The merge is now judged first, in `assess` and in `land` alike, and the suites are not paid for until it is known to apply. A conflicting merge with no suite run reports the merge's reason rather than the unrun suite's: told *"the suite was not run"*, an operator goes hunting a broken test runner instead of a conflict. The companion cause is closed by `.gitattributes` — `CHANGELOG.md merge=union`, because every branch appends under the same `[Unreleased]` heading and the correct resolution is always "keep both". (#26)
- **Variable shadowing in `check_backlog_structure.py` — findings list re-initialized (#11).** Line 320 re-declared `findings: list[Finding] = []`, discarding prior appends. No appends currently exist in range [295-320], but this creates a maintenance trap where future logic additions would silently lose findings. Removed duplicate initialization.
- **Naming collision: three `_routing()` functions with incompatible signatures (#11).** Functions in check_backlog_structure.py (→dict[str, dict]), spawn_stages.py (→dict[str, str]), and route_domain.py created silent type mismatches during refactoring. Renamed spawn_stages._routing() to _parse_routing_rule() for clarity.

### Added
- **The kit's defect lenses now read a diff, not only history.** `kit_audit_workflow.js` carries six lenses, each a pattern this kit has shipped more than once, each quoting the measurement that makes it concrete. It runs over the whole repository, on a sweep, afterwards. Measured 2026-09-03 in a single session and all by the same author: a guard whose predicate held whether the send worked or not, so its success branch had never executed (`guard-that-guards-nothing`); a `finally` that ran a command and discarded the result, so a leaked worktree could not be explained (`absence-as-answer`); a fetch taken once and reused as if current; and a workstation path in a versioned file, twice. **Every one is on the list, and the list had never been pointed at the diff that introduced them.** `lens_review.py` points it there. It **parses the lenses out of the workflow** rather than keeping a second copy — a rule living in two files is this kit's second-most-found defect, found five times in one day — and raises when the parse comes back empty, because reviewing a diff against zero lenses reports every diff clean, which is the first lens itself. A lens whose agent fails or answers with prose is NAMED as not having run, never counted as having found nothing. Its findings do **not** block a landing: a model's opinion about a diff is not grounds to stall an unattended fleet with nobody to override it at 3am. They go to `file_findings.py`, which already refuses a claim with no evidence and one the tracker holds, and become work the next pass picks up.
- **When nothing is owed, the fleet goes looking instead of stopping.** With the consumer's backlog walled on decisions only a person can make and the kit's tracker empty, the honest answer used to be "idle" — and it was honest, which is why it went unexamined for a day while `kit_audit_workflow.js` sat unused. That workflow hunts the defect patterns this kit has shipped more than once and puts every claim in front of an agent whose only instruction is to refute it; nothing ever ran it, and nothing turned what survived into an issue. `fleet_router` now offers a **sweep** as its last source, behind both real queues and behind a six-hour cooldown. Last on purpose: a fleet that prefers auditing itself to shipping the product is worse than an idle one, because it looks busy. Behind a cooldown for the same reason a tracker fills with duplicates and stops being read. It is offered only when the real sources came back **empty** — never when one of them came back unreadable, since sweeping on the strength of a failed read is inventing work out of an absent measurement. A fleet that has never swept sweeps immediately: the cooldown starts from the last recorded sweep, not from the epoch, so whether the first one happens does not depend on today's date.

### Fixed
- **`SECURITY.md` and `hooks/README.md` promised a read-only zone that `boundary-check` stopped guarding (kit#19).** The retirement on 2026-09-01 removed `records/references/` from `ZONE_RE` in `hooks/boundary-check.py` and from the rule it cites, and left two prose readers behind — each still naming the retired path alongside `study-material/` as if both were enforced. A security document that overstates a control is worse than one that omits it: the reader believing the guard exists never asks for the guard they still need. Both sites now name only what the hook matches, and the retirement is stated as its own paragraph, off the boundary-check line, so a future reader learns what changed and why. A new test at `tests/hooks/test_boundary_check_prose_agrees.py` extracts every backticked-or-bare directory token from any line naming `boundary-check` in either file, asks the real hook whether it blocks a write there, and fails on the first mismatch — the shape of `test_hook_declarations_agree.py`, applied to the pair the retirement broke. Written to fail first on the current tree (both prose sites red on `records/references/`), then green after the fix. Without the test, the next retirement leaves the same residue. Filed by an agent auditing the fleet's idle-work queue and reported in kit issue #19.
- **`check_install_drift` was cited nine times in prose and executed by nothing (#23).** The gate that tells a consumer its install has fallen behind the source shipped with no schedule: `hooks/hooks.json` and `settings.json` never named it, `mechanisms/fleet/run_gates.sh` had no list including it, and `verify_ecosystem.py` — the master runner — is single-tree while the gate is two-tree, so it did not belong there. Measured 2026-09-03: the theo consumer ran ten hours on a copy missing three merged repairs, and when a human finally invoked the gate by hand it named the drift in one line, precisely. Two changes. **(1)** `tests/test_every_gate_is_reachable.py` was silent about this because its `_invokes` regex counted the mere pattern `check_install_drift.py` — and the three "callers" it found were prose in comments and a docstring; the same loophole would have hidden `check_orphan_verdicts` had the phase-gate wiring landed a day later. The strip now removes Python triple-quoted string literals, Python `#` line comments, and shell `#` line comments before the regex runs, so a name in narrative no longer passes as an invocation. **(2)** `hooks/sessionstart-context.py` gained `drift_line`: when `$SQUAD_KIT_SOURCE` names a real kit directory that is not the install itself, the hook shells out to `check_install_drift`, folds the count summary into one context line, and reports it — never blocks, never fails the session, and stays silent when the env var is unset. A consumer that pinned an older kit deliberately still learns of the drift without being stopped over it. `tests/hooks/test_sessionstart_drift.py` locks the four cases (unset · misconfigured · same tree · real divergence) against the real gate rather than a stub.
- **`squad_lead` wrote one log for N sessions and no entry said which session it was about (#24).** `--session squad1,squad2,squad3` watches N lanes and every decision from every lane is appended to one log file. The entry recorded `event`, `item`, `reason`, `option` and `idle_seconds` — and **not which lane it was about**. A reader could not tell three lanes stalling once from one lane stalling three times, and those call for opposite responses. Measured on the runner 2026-09-03 with three lanes watched: three entries `asked / stalled / stalled` twenty seconds apart, and whether that was one lane repeating (a broken heartbeat) or three lanes reporting once (correct behaviour) was unanswerable from the log — resolved by inspecting the code, which is the thing the log exists to make unnecessary. The session was populated on two of the several paths — the `gone` line and the `start` line — as ad-hoc additions where someone happened to need it, so exactly the entries that describe an *assignment* carried it and every entry that describes a *problem* did not. The session is a property of the WATCHER, not of the decision, so it now lives in the one place every entry is finalised: `_log` stamps it beside the timestamp for the same reason it stamps that — so no decision can reach the log without one. Both ad-hoc places are gone. A companion suspicion — that `fleet_idle.py` mis-attributes intervals across interleaved lanes today — is real for the fleet-wide aggregation and is filed separately rather than folded into this fix, per the task's instruction.
- **`dispatch_to_lane.sh` reported `NOT submitted` on every dispatch, including the ones that worked (#22).** It decided delivery by grepping the WHOLE pane for the text it had just sent — and the CLI echoes a submitted prompt into the transcript, so the predicate held whether the send worked or not. Measured 2026-09-03: three lanes dispatched, three `NOT submitted` reports, and all three were already building their git worktrees within 30 seconds. **The branch that prints `dispatched` had never once executed.** It shipped looking correct because it was verified against the failing case only, where it happened to give the right answer for the wrong reason — a guard that fires unconditionally cannot distinguish the failure it exists for, and it teaches the operator to ignore the one message that matters. The check now asks `session_ready.composer_text()`, which reads the LAST caret line and nothing above it, because everything above it is what the session has already been told. Three outcomes are kept apart rather than two: empty composer is a delivery (exit 0), text in the composer is not (exit 1), and **a pane with no readable composer is UNKNOWN (exit 3)** — saying "delivered" there would be this kit's most-found defect wearing the uniform of the mechanism written to prevent it. Verified live in both directions on the runner: a real dispatch exits 0 and the lane starts, and text typed without an Enter is read back verbatim.
- **The lead threw away SELECT's reason and then went silent for nine hours.** Two defects, measured together on the runner on 2026-09-03 with three lanes idle for 10h33m: the lead's log read `SELECT exited 1: ` — the reason blank — and its last line was 9h11m old while the process was alive and sleeping. Neither is a stall; both are the watchdog unable to say what it saw. **(1)** `select_backlog_item.py` ends on `return 0 if verdict == "ITEM_SELECTED" else 1`, so a held backlog ALWAYS exits 1, with an empty stderr and the full verdict on stdout. The lead checked the returncode before parsing, which made the branch that reports `BACKLOG_BLOCKED` in the selector's own words **unreachable code** — the exit status is a verdict, not a failure, and reading it first turned `26 selectable item(s) remain and every one is held` into a blank. Stdout is now parsed first and the returncode consulted only when there is no usable answer, so a genuine crash stays legible. **(2)** After one stall report `reported_stall` silenced every later poll with the reason *"no menu is waiting"* — not even the true one; the menu was absent because the backlog was walled. Reporting once was right and reporting nothing ever again is the same defect as a lane holding unsent work: from outside, a live watch and a dead one are identical. A stall is now restated on a 30-minute heartbeat, with its real reason, and the clock restarts on each — quiet, not mute.

### Security
- **Layer 3 of provenance never ran in any consumer.** `rules/reference-provenance.md` names three layers and this is the only one that catches the RESULT of a paste rather than the act. The gate lives with the KIT and runs against the PROJECT — and those are different directories in two of the three layouts `squad.layout` defines: a `copy` install puts the kit at `<project>/.claude/`, a `plugin` install puts it outside the project entirely. The hook looked for the script under `project_dir`, so **only this repository, where the two coincide, ever ran it**. Reproduced in both layouts with a committed `study-material/ref.md` and an untracked literal copy: the hook exited 0 with no output while the same gate on the same tree printed `SUSPECTED COPY … shares 5 consecutive lines` and exited 1. And "not installed" returned the same `None` as "ran and found nothing", so a session ended looking clean on a check that had never happened — in a hook that already says out loud that the CHANGELOG gate cannot run, and that gained `STOP GATES DID NOT RUN` for git earlier the same day. The third branch was the one missing. Found by the kit's own self-audit, and it survived an independent attempt to refute it in both layouts.
- **The end-of-session gates passed in silence whenever git could not be asked.** `stop-validation.py` collects the session's work with `git diff`, `git ls-files` and friends, and its `git()` helper returned the empty string for **every** failure: the binary missing, a timeout, a broken repository, a subcommand exiting non-zero. All four are indistinguishable from *"nothing changed"* — and "nothing changed" is precisely what makes every gate in that hook pass. The hook runs at the end of every session and two of its gates are blockers, one of them **for secrets**, so the silent form of this failure is a secret gate that did not run inside a session that ended clean. Failures are now recorded and reported as `STOP GATES DID NOT RUN … This is not a pass`, naming each command and its reason. Being outside a repository stays silent, because a scratch directory genuinely has nothing to validate and saying so at every prompt is noise; every other failure is a measurement that did not happen.
- **`rules/retired-permissions.txt` — the half the recorded base cannot cover.** The base records what the kit shipped last time, which lets the installer retire a rule automatically. It cannot help the FIRST install under that scheme: with no record every entry is indistinguishable from a project's own, so that path removes nothing — deliberately, because deleting a project's rule across every consumer at once is the worse error. Measured the same hour both landed: the credential globs were rewritten, the base shipped, and the retired `Read(**/*secret*)` **stayed denied in the consumer anyway**. The fix arrived inert, which is precisely the shape it was written to prevent. So the kit now also declares its withdrawals explicitly, and the installer removes those on every run regardless of base. The two halves are different in kind and both are needed: the base is automatic and covers what nobody remembers to declare, while the list is auditable and covers what the base cannot know. Every entry carries a dated reason, so a consumer surprised by a removal finds the reasoning rather than just the deletion; tests refuse a rule that is both declared retired and still shipped, since which of the two won would depend on the order of two loops.
- **A retired permission rule stayed in every consumer forever (kit#16).** `install.sh` merged the kit's permission lists into a consumer's by union: additions propagated and removals did not, so any deny or allow entry the kit retired remained in **all seventeen consumers** that already had a `settings.json`. A retirement was applied, released and inert everywhere but a fresh install — the same shape `defaultMode` had, closed for scalars and left open for lists. It could not be fixed by comparing two lists, because a rule present in the consumer and absent from the kit is *either* something the kit retired *or* something the project added, and those must never share an outcome. The missing term was the base, so the install now records what the kit shipped (`.kit-permissions.json`) and retires only what that record holds and the current template does not. With no record — the first install under this scheme — **nothing is removed**: every existing entry is indistinguishable from a project's own, and deleting a project's rule is the worse error by far. The base stores what the KIT shipped, never the merged result, or the next install would treat a project's rules as its own to delete. Removals are printed, because an install that silently deletes permission rules is one nobody can audit. This landed the same hour the credential globs above were rewritten — without it, the retired `Read(**/*secret*)` would have stayed denied in every consumer alongside its replacements, and that fix would have been inert.
- **The credential deny list refused one tool, and not the one that can change the file (kit#15).** `permissions.deny` carried `Read(**/.env)`, `Read(**/*secret*)` and friends; `permissions.allow` carried `Bash(*)`. So `cat .env` returned the file `Read(.env)` had just refused, and `Edit`/`Write` were never denied on those paths at all — **an agent could not read a credential file and could rewrite it blind**. Measured in a consumer on 2026-09-02: **157 versioned paths refused to `Read`, 79 of them source code** (51 `.go`, 24 `.sh`), and not one refusal a session could not step around in a single command. It cost real work and bought nothing, which is worse than no guard: it teaches people to route around guards. Three changes. The globs now name credential-bearing **forms** rather than files whose name mentions a secret, so the same consumer goes from 157 refused to **8**, all of them Kubernetes Secret templates, with zero source files and `.env.example` readable again. Every denied `Read` path is now denied to `Edit` and `Write` too, pinned by a test. And `validate-command.py` refuses a shell command that reads one of those paths — reading the globs **from `settings.json`** rather than keeping a second copy, because four separate cases of a rule living in one file and missing from another turned up that same day. The guard states its own limit where the pattern is defined: it closes the common door and is **not** a sandbox — `python3 -c` reaches the same bytes, and claiming otherwise would make it the very thing it replaces. Filed by an agent running inside the fleet.

### Added
- **The wiring between "work exists" and "a lane is doing it" — four mechanisms and a loop.** Every unit of work this fleet has completed was typed in by a person. No component was broken: `select_backlog_item.py` names what may start, `kit_issues.py` names what the kit owes, `session_ready.py` says which lane can take something, `dispatch_to_lane.sh` hands it over. The segment between them was a human reading one output and composing the next input, and the cost is measured — **three lanes idle for 10h33m with four actionable issues open**, and five completed repairs sitting on branches a person had to push and merge. **`fleet_router.py`** routes units the sources already declared startable; it never invents work, the consumer's backlog always outranks kit work, and its state is an append-only log replayed each run so a restart resumes instead of double-assigning. Its first live run exposed two things it then had to survive: memory is not the only evidence of work in flight — a branch and a closing commit are observable facts that survive a hand dispatch and survive the router dying between handing a unit over and recording it — and a unit whose lane died must be **released**, since an assignment nothing ever clears is the same idle failure rebuilt one level up. Three facts must hold together before the reaper acts, because each alone is normal: the lane is free (not busy, and not `unknown`, which means the check did not run), no branch exists, and the grace period has passed. **`fleet_lander.py`** closes the other end: it runs the suite on the branch and again on the merge, in **two** scratch worktrees rather than one — a single tree that falls back from a fast-forward to a merge cannot say which state the suite ran against — and pushes only what it watched pass. A suite that could not be run is not a pass, and `pytest` exiting 5 on an empty collection is not a pass. It does not close the issue and does not open the promotion PR to `develop`: a merge to the working branch is not availability, and both are the operator's. **`file_findings.py`** is the step between a sweep and a work queue — findings that survived an agent trying to refute them become issues, with the killed claims, the evidence-free claims and the ones the tracker already holds (open **or closed**) all refused; when the tracker cannot be read it files **nothing**, because filing without dedup turns one real defect into a duplicate on every run. **`fleet_supervisor.sh`** is the loop over the two, and makes no decision either refuses to make.
- **Three mechanisms for running work where the machine is, and a measurement that says why they were needed.** Measured mid-session on 2026-09-02: **15 heavy processes on the workstation at load 18.9 across 12 cores, and ZERO on the runner at load 8.0 across 8**, with four Claude sessions idle there. Four pipeline runs, a 23-agent audit, a 7-way parallel repair and several full suites had all been run locally. The operator had corrected this once already and it recurred within hours, so it gets scripts rather than intent. **`run_remote.sh`** runs work on the runner and **refuses to fall back to local** when it is unreachable — a silent fallback is how the work comes home without anyone deciding it should. **`run_gates.sh`** runs a project's gates concurrently with a per-gate ceiling, reporting a timeout as its own finding (exit 2) separately from a failure, and a passing-but-over-budget run separately again (exit 3) so the ceiling is not advisory; its header states what it refuses to do to go faster, because running less of the suite is the cheapest way and the wrong one. **`dispatch_to_lane.sh`** hands one unit of work to one fleet lane and refuses a lane that is not at a prompt — work typed into a busy lane interrupts its turn, and work typed into one sitting in a dialog answers the dialog.
- **`stage-implement.md` — the pipeline reaches code, and the writing stage answers the question that deferred it.** The pipeline ended at PLAN, and `spawn_stages.py` said why: *"IMPLEMENT and beyond are not here yet — they write to the repository, and a writing stage needs its own review of what the tool list should be."* Measured consequence, on a real consumer: **16 alignment records and 0 implementation records** — the cycle ran and could not reach code by its automatic path, because the path stopped first. Three answers make the stage: **(1)** it carries `Edit` and `Write` on top of the read-only four, and a test asserts it is the ONLY stage that does. **(2)** Every edit goes inside a git worktree **the agent makes itself**, of the CONSUMER's repository, on `pipeline/<item>` — not the harness's `isolation: 'worktree'`, which isolates the CWD's repository and on a consumer run gave each agent a copy of the KIT; that was removed rather than repaired, and this is the repair. The read-only stages share one tree safely and do; two writers in one tree produce a diff neither authored. **(3)** RED before GREEN is not advisory: it runs `check_tdd_shape.py` itself as its first action and halts if a task cannot drive a RED phase, the way JUDGE runs the real scorer instead of accepting one reported to it — and the scheduler deliberately does NOT approximate that gate in JavaScript, because a second implementation of a rule that already has one is the defect this kit found five times in a day. Its refusals are stated where it works rather than in a rule it may not read: no push, no commit on the consumer's branch, no `--no-verify`, no threshold moved, no `BACKLOG.md`. And it reports both runs — the test seen to fail before the change and pass after — because a test written after the code passes on the code you happened to write.
- **`mechanisms/fleet/kit_audit_workflow.js` — the kit hunting itself, on purpose.** Every defect found on 2026-09-02 was found by an agent doing OTHER work: running the pipeline over a consumer's backlog and noticing something wrong in the tooling underneath. **Seven issues arrived that way, all real** — a good source, and a slow one, because it finds only what happens to lie in the path. A gate cannot replace it: these patterns are about MEANING, and the suite already holds 1205 assertions that see shape. The measured evidence for that gap came from an ALIGN agent — one brief scored **31/34 unchanged across five content defects and their fixes**, and what caught them was a reviewer reading the repository rather than the rubric. So this asks agents to look deliberately, one lens per pattern the kit has shipped more than once: absence reported as an answer, a rule living in one file and missing from another, a guard that costs and prevents nothing, something mentioned counted as used, prose describing a world the code left, a mechanism nothing executes. **Every lens quotes a real measurement** rather than an adjective — an agent told *"look for silent failures"* finds prose, one told *"a matcher reported a complete delta of 5 against a true 11"* finds matchers, and a test fails a lens that cites no number. Every finding then meets an agent whose job is to kill it, defaulting to refuted when it cannot confirm: a finding that survives only because nobody looked spends a maintainer's attention and teaches them to distrust the next one. The hunters carry no writing tool, and an empty result is named in the prompt as a real answer, because the alternative incentive is padding.
- **An advisory for acceptance criteria that pass because their SUBJECT is absent.** `! grep -q PROPOSED adr.md` exits 0 against a file with no status line at all, so the criterion approves precisely the case it was written to catch. Found by an ALIGN agent on 2026-09-02 **in two of its own criteria**, which it rewrote to assert the terminal token positively; its words: *"An acceptance criterion that passes when its subject is absent is executable, cites its requirement, and is wrong."* It is invisible to all seventeen scored criteria, and the same agent supplied the evidence for why that matters — its brief held **31/34 unchanged across five content defects and their fixes**, so the machine score moved not at all while the content was wrong and then right. Deliberately **scored nowhere**: the rubric measures shape, this is about meaning, and a false positive must not cost an item a point toward the 90% gate. A negation guarded by a presence check is not flagged, which is the fix the agent applied. The detector nearly shipped matching nothing — acceptance criteria write commands in backticks, and the backtick was missing from its delimiter class, which would have made it an advisory that never fires, silently. That is the shape this release spent the day removing, arriving in the guard against it.
- **`tests/test_gates_say_what_they_examined.py` — every gate held to the honest ones' standard.** This kit's most-found defect, by a wide margin, is an inability to measure published as a measurement: a glob that lost its reach, a matcher pointed at a renamed directory, a launcher that never looked. Every instance had the same tell — a clean report over an empty sweep. So all twelve root-taking gates were run against an empty tree and compared. **Five of six said what they had swept** (*"swept 0 cycle rule(s)"*, *"0 declared phase(s)"*, *"study zone absent or empty — nothing to compare against"*), and one printed *"Overall: PASS — every cycle's declared numbering is unique and in chain order"* after examining **zero cycles**. Two assertions per gate now hold the whole set: an empty tree must produce a report a reader can tell apart from a clean one, and no line may claim a universal property (*every*, *all*) alongside `PASS` without a non-zero count behind it. A third fails when a gate that takes a root is missing from the roster — it caught one while being written. `check_phase_numbering` gained a `NOTHING_DECLARED` verdict that says outright *"this is not a pass"*, and its `PASS` now carries the counts: `17 skill(s) across 4 cycle(s)`.
- **The scheduler's verdict schema is held to what the scorer can actually emit.** The pipeline forces each stage agent through a JSON schema, so a verdict outside the enum leaves the agent two options and both are wrong: fail the structured call, or report a listed value that is not what it measured. `NEEDS_SPLIT` already lived through exactly that — it existed in `SKILL.md`'s table and in no code, so a brief needing a split had to be squeezed into `BLOCKED`, which tells the reader to close gaps no rewrite can close. Two hand-kept lists in two languages, which is the shape that cost three separate defects today, so it gets an assertion instead of a habit.
- **`tests/test_blocked_by_readers_agree.py` — the two readers of `blocked_by` are now held to the same invariants.** `select_backlog_item.py` decides whether an item may be worked on; `check_backlog_structure.py` decides whether the registry is well formed. They parse the same field and deliberately share no code — the gate must review a registry written by anything, so it cannot import the writer and inherit its assumptions. The cost of that choice came due three times in one day: the self-mention filter lived in the selector and the gate lacked it (28 false blockers, every push to a consumer refused); the prose-outlives-the-edge rule lived in the gate and the selector lacked it (an item a person still owed a decision on, handed to the queue); and a stage list lived in the spawner while its test kept a copy that went stale. These 27 assertions do not merge the readers — they pin what must hold across both, over `blocked_by` values taken from a real registry rather than invented. Reverting either fix fails them, independently, which is the property that matters: **the class of bug neither script's own tests can catch is the one where they disagree.**
- **`mechanisms/fleet/kit_issues.py` — self-evolution's missing half: an idle fleet works on the kit.** A consumer's queue reads `BACKLOG_BLOCKED` whenever every remaining item waits on a person, and that is the normal state rather than the exception. Measured on 2026-09-02: both remaining items wanted a governance decision, and a fleet of three lanes and a lead had nothing it was allowed to touch. In the same hour the kit had two open defects — **and both had been filed that day by agents running inside that very fleet**. The capture half of self-evolution already worked; nothing consumed what it caught. Idle lanes and an unworked defect list, same machine, same hour. This reads the kit's own registry (its GitHub issues — the kit has no `BACKLOG.md`) and splits it into what a lane may take and what waits on a person, because routing a decision-shaped issue to a lane rebuilds the blockage one level up. It never invents work: every item is an issue with a number you can open. And it refuses to confuse "the registry is empty" with "the registry could not be read" — a missing `gh` raises `Unavailable` with the reason, because *"the kit has no known defects"*, said on the strength of an absent CLI, is this kit's most-found defect wearing a new hat. The consumer's backlog always wins; this is only where the fleet goes when the alternative is idling, and the lead's brief now says that work on the kit is the cycle and not a shortcut around it — the failing test comes first.
- **`mechanisms/fleet/session_ready.py` — the launchers now look before they report.** `start_fleet.sh` created three tmux sessions, printed `==> Watching: squad1,squad2,squad3` and returned 0; `start_lead_session.sh` created one, slept four seconds, typed a brief into it and printed that it was looping every ten minutes. Neither looked. Measured on 2026-09-02, minutes after the CLI was upgraded to 2.1.258: **all four sessions were sitting in a first-run dialog no earlier version had asked** — *"Try the new fullscreen renderer?"*. The three lanes stayed in it for forty minutes while `fleet_status.sh` reported them idle and `claude agents --json` listed them alive, so the lead read three free lanes and would have dispatched work into sessions that could not take it. The lead itself died: its brief was typed INTO the dialog, and the first newline confirmed the pre-selected option — which on the trust dialog is `No, exit`. It does not enumerate dialogs, because 2.1.144 asked about trust, 2.1.258 asked about a renderer and the next one will ask about something else; it waits for the session to look ready and reports anything else with the last frame of its screen. `dialog` and `starting` are kept apart: one waits for the operator and never clears, the other clears by waiting, and telling someone to wait for something that is waiting for them is the worse of the two. Nothing is typed into a session until it is ready, and the lead is re-checked after its brief.
- **`mechanisms/fleet/claude_stream.py` — the lead talks to Claude over the protocol instead of reading its terminal output.** `claude -p` under `--output-format text` returns prose, so the lead inferred outcome, cost and identity from it — and inference is where a watchdog starts believing things. Measured: a run that exceeded its budget printed `Error: Exceeded USD budget` **on STDOUT and exited 0**, the lead read that sentence as the agent's reply, found no rule in it, and escalated saying no rule covered the case. It had never been asked. `--output-format stream-json --verbose` ends every run with a `result` object carrying `subtype`, `is_error`, `total_cost_usd`, `session_id` and `num_turns` — the same four facts, as fields. A stream that never produced a `result` is reported as a transport failure rather than as the text collected before the process died. One measured call in a real consumer: **$1.3075**.
- **`mechanisms/fleet/start_lead_session.sh` — the lead becomes a Claude session with a brief, not a Python loop.** A named session (`-n lead`) can be reached by `SendMessage`, can run `/pipeline`, and can read the selector's reasoning rather than only its verdict. The brief establishes what it may do and, at greater length, what it may not: no `--no-verify`, no `--force`, no `--allow-dirty-tree`, no threshold or baseline moved to make something pass, no verdict recorded that a phase did not emit, no `BACKLOG.md` edit that unblocks an item a person must unblock. `/loop 10m` sets its cadence.
- **A missing CLI capability is reported as missing, not as an empty answer.** `claude agents --json` — how the lead discovers its peers and their busy/idle state — landed after 2.1.144, and an older CLI answers `unknown option` **while exiting 0**. A returncode check reads that refusal as a fleet with no sessions in it, which is the kit's most frequently re-found defect wearing new clothes: an inability to measure published as a measurement. Measured across two machines the same afternoon: a workstation on 2.1.236 listed three sessions, a runner on 2.1.144 listed none, and nothing in either output said the second had not looked. `Unsupported` now names the version and says what to do instead.
- **`mechanisms/fleet/fleet_idle.py` — where the fleet's time actually went.** The lead's log says what happened; it does not say how much of the window bought nothing, which is the question a stalled fleet raises. It counts the interval between consecutive decisions, attributed to the decision that opened it: disjoint by construction, adding up to the window, and both totals printed so the arithmetic can be checked. Summing the `idle_seconds` field is the obvious measure and is wrong — consecutive observations overlap, and on a real log it gave 45.8 of 56 minutes against a true 36. It also names sessions the fleet never handed work to, but only against the watched list: from the log alone a starved session and one that does not exist look identical, and claiming the first would be inventing the finding. Eight tests, including that a single event reports "nothing to measure" rather than "0% idle".
- **`mechanisms/fleet/fleet_wall.sh` — the whole fleet on one screen.** One tmux session, one pane per executing session, each attached to the real thing so what you see is live rather than polled, plus a pane running the status report on a loop. **Read-only by default**, and that is the feature: a fleet session is being driven by the watchdog, and a keystroke landing in it while an agent holds the turn answers — as the operator — a question the agent asked someone else. `-w` exists for when intervening is the intent. The set of panes comes from a pattern, not from "every tmux session": building it the loose way swept up a throwaway session created two commands earlier, which appeared on the wall as a fleet member.
- **`mechanisms/fleet/fleet_status.sh` — every session at once, from the shell.** `/squad-status` answers *why is the queue in this state* from INSIDE a Claude session; there was nothing that answered *what are the sessions doing* from outside one. Two days of a stalled fleet were diagnosed with `tmux capture-pane` by hand, session by session, plus `tail` on a jsonl whose useful fields sit buried in a `reason` string. It shows each session's item, age and last output, the lead's recent decisions with the session that received each one, and what the selector would hand out right now — and it never attaches, because reading a pane must not steal it from whoever is watching. `-f` follows, `-l` widens, a session name zooms. Seven tests, including that an unreadable selector report says so rather than printing a verdict.
- **`squad/` — a Python library for writing hooks, and all nine now use it.** Hooks were 1591 lines of shell parsing JSON through `jq`. The package gives each event a typed context (`PreToolUseContext`, `PostToolUseContext`, `UserPromptSubmitContext`, `StopContext`, `SubagentStopContext`, `SessionStartContext`, `PreCompactContext`), an output object whose verbs match that event's wire format, and `squad.layout` — `hooks/environment/detect-layout.sh` in Python, keeping the kit's CODE and the cycle's DATA apart. `system_message` travels on every verb the API declares, because a warning written into `reason` is read by Claude and never seen by the person it was for. 81 tests.
- **The library blocks when it cannot build the context, and says so.** Unreadable stdin, malformed JSON, a missing or unknown `hook_event_name`: each exits 2 with a line stating that nothing was checked. `safe_create_context` was described as exiting *gracefully*, which did not say in which direction — and the only graceful-looking direction, exit 0, turns a broken gate into one that approves everything while its log reads clean. `create_context(PreToolUseContext)` narrows the type without `assert isinstance`, which vanishes under `python -O` and, when it does fire, raises `AssertionError` → exit 1, a NON-blocking code: a security hook whose type check failed would have let the action through.

### Fixed
- **Three kit defects repaired concurrently by three fleet lanes on the runner, each in its own worktree.** The first end-to-end run of the fleet doing work rather than reporting that there was none. `check_gate_mechanisms` lost rows to any `###` inside `## Hard gates` — the boundary fix its sibling shipped on 2026-08-31 never crossed over, so a gate whose only product is a count could silently drop rows from its own denominator. `check_orphan_verdicts` tested reachability by substring. And the `blocked_by` self-mention filter had reached the gate and the selector but **not the writer**, where the refusal is terminal: an item cannot ship because it is blocked by itself, and stays open precisely because it cannot ship. Each lane wrote a failing test first and committed it with the fix; each branch was then checked by reverting the production change and watching the test fail. Getting there took removing four stacked obstacles, three of them invisible: 20 tools installed on the runner since May with **none on the PATH**, a kit checkout that **was not a git repository** (rsync had excluded `.git`, so no lane could make a worktree), `send-keys "$text" C-m` leaving the instruction unsent in the composer — a lane holding unsent work looks exactly like an idle one — and the kit's own `Bash(rm -rf *)` deny, correctly refusing to clear a worktree path. The last was fixed by removing the need rather than the rule: worktree paths now carry a timestamp.
- **`AWAITING_HUMAN` was declared by five cycle rules with "Emit it." and emitted by nothing — and the gate that exists to catch that hid the gap inside itself.** `check_orphan_verdicts` tested reachability with `verdict in code`, a bare substring over one concatenated blob, so `AWAITING_HUMAN` matched inside `INVALID_AWAITING_HUMAN` **in a comment**. Its own test asserted `findings == []` for the live repository, and that assertion was satisfied by that comment. Whole-word matching reveals five orphans, all of them the same verdict. The rules say what the absence costs and it is measurable: *"without the event it leaves no trace, and every reader — the board, the drift checker, the selector, the watchdog — sees an item that was never touched."* Measured on a consumer the same day: **14 items in exactly that state**, indistinguishable from untouched, while a fleet ran thirteen autonomous rounds reporting nothing to do. The selector already knew which ones — an impediment naming no item is a person's to open, and it had been computing that since the prose fix earlier the same day — it just never said so. It now reports `awaiting_human` on **every** verdict, not only on an empty queue: an item held by a person is held whether or not other work exists, which is how 14 of them stayed invisible behind a queue of 5. The field is present even when empty, so a reader can tell "nobody is waiting" from "this selector is too old to say". Found by an agent in the kit's own self-audit; the repair was written by a fleet lane on the runner, in its own worktree, in parallel with two others.
- **The cross-reference gate carried link-checking machinery and never ran it.** `check_xrefs.py` runs in CI and in `verify_ecosystem`. It defined `LINK_RE` and a function that used it, and that function had **zero callers** — a checker that existed and did not run. Turning it on as written would have been worse than leaving it off: it also resolved every backtick-quoted token that looked like a path, and measured before replacing it, reported **1451 broken references** — nearly all a bare filename like `alignment_judge.py` resolved against whichever directory happened to cite it. A gate at that signal-to-noise gets switched off, and the silence afterwards is indistinguishable from a clean repository. Markdown links are unambiguous about their target, so those are checkable: **234 relative links, 21 broken, every one real** — three cycle rules pointing at a document that moved to `skills/_kit-rules/`, a template off by one directory level, and a `_kit-rules` file reaching for `../skills/` from inside `skills/`. All 21 fixed, the check wired in as `WARN`, links to documents the kit keeps and deliberately does not install (`README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`, `wiki/`) exempted where they are absent by design — the first run against a fresh install produced nine identical warnings no consumer could act on, which is how a gate loses its reader (a broken link misleads a reader and breaks nothing that executes), and `wiki/` resolved from its own root, since its links are written `/sops/index.md` and reading them as filesystem paths reported ten false positives at once.
- **The fleet's readiness check skipped the lane most likely to be stuck.** `start_fleet.sh` leaves an already-running session alone — correct, since killing a lane mid-turn loses its work — and the check added earlier the same day looked only at sessions the script had just created. That is backwards: a session this script watched start is the case already observed to succeed, and a preserved one is the case **nobody watched**. It is exactly how three lanes spent forty minutes in a first-run dialog while `fleet_status.sh` reported them idle and the lead read three free lanes. Both branches now register, and the list is renamed from `started` to `checked` because it had stopped holding only sessions started here — a name that lies is where the next reader's wrong assumption comes from. Found by the kit's own self-audit, in the lens for absence reported as an answer, pointed at a fix written hours earlier.
- **The CI checked nothing, and had been failing, since the rename — four ways in one file.** `scripts/` became `mechanisms/` and the hooks became Python on the same day; `.github/workflows/ci.yml` was not touched. **(1)** `ruff check scripts …` — ruff exits 2 on a missing path, so the Python lint step failed on every run from that commit, and `squad/` was never linted at all. Behind it waited **133 findings**, now zero. **(2)** `shellcheck … hooks/*.sh hooks/environment/*.sh scripts/*.sh tests/hooks/*.sh` — **all four globs matched zero files**, and shellcheck exits 0 on an empty argument list, so the job reported a clean shell contract having checked nothing; the 12 shell files that do exist were unchecked and one carried a real warning. **(3)** `for test_file in tests/hooks/test_*.sh` — zero files, so the loop body never ran and the step reported success. **(4)** `--cov=scripts` with `ROOT_SUITE_COV: '1'` — 0.00% against a floor of 55%, failing every run; measured against the real trees it is **82.28%**. The rename was caught in the syncer and in the drift report the same day and nothing looked at `.github/`. All four are corrected, and a test now fails when a CI step hands a tool a path that matches nothing — asking each tool where its path arguments begin, because a first version matched tokens by shape, skipped `scripts` (no slash, no extension), and let the exact defect back in with the suite green.
- **Two gates were executed by nothing at all.** Of eighteen gates, `check_orphan_verdicts` and `check_phase_emitters` were run by no CI job, no hook, no script, and not by `verify_ecosystem`. Outside its own tests, `check_orphan_verdicts` appeared exactly once in the whole repository — **inside a comment in a sibling gate**, which read as coverage until someone looked. What they check is not minor: one asks whether every verdict a cycle rule declares can actually be emitted by something, the other whether every declared phase has an emitter at all. A verdict named in a rule and produced by nothing is a state the chain can never enter, and `NEEDS_SPLIT` lived exactly that way — documented, unimplemented, and briefs needing a split squeezed into `BLOCKED`. Both passed clean when finally run, so nothing was hiding behind them; that is luck, and a gate nobody runs reports its first real failure to nobody. Both are registered in `verify_ecosystem` now (14 checks, from 12), and a test fails when any gate has no automatic trigger — distinguishing an invocation from a mention, because a mention is what made this invisible. Its allowlist for deliberately manual gates is empty on purpose: an entry there is a claim that a gate should never fire on its own, and that claim should be hard to make.
- **A regex sat in a keyword list compared with `in`, and it was the only thing separating two copies of the same rule.** `apply_fixes.py` decides whether to INSERT a TDD block into a plan; `check_tdd_in_bugfix.py` decides whether to REQUIRE one. Same question, same plan, two lists kept by hand — a comment in the second still records that they were aligned by hand once. They had drifted by one entry: `"fix.+bug"`, carrying its own admission that it was *"not used as substring; left for grep-of-the-mind"*. It matched nothing, and it would begin matching the day someone converts the comparison to regex, with no record anywhere of what it was meant to catch. Removed, and two assertions now hold: the two lists must be equal, and no keyword may contain regex metacharacters while the comparison is `in`. Fifth instance today of one rule living in two files.
- **`detect_domains.py` invented a domain from the directory name when there was no project.** With no child repositories the script names the single domain after the folder, which is correct for a real repository and is fabrication for an empty directory. Run against an empty temp dir it emitted a complete routing table for `tmp.ICTIKtMB5K` and listed a specialist that must be written for it — a table nobody can act on, derived from a folder name, printed under a heading that says *"derived from this project"*. Worse than the silence this release has been removing: **the absence produced content**. The script already carried a `no derivable domain` message and nothing could reach it. A domain is now derived only when the directory shows some sign of being a project at all — a `.git`, a manifest, a README — which a repository at its first commit satisfies and an empty directory does not. The umbrella branch is untouched.
- **`check_phase_numbering` did not look where a consumer keeps the kit.** It reads `<root>/skills/`, and a consumer keeps the kit in `.claude/`, so `--root .` — the natural thing to type from a project — pointed at a directory with no `skills/` and swept nothing. Before the empty-sweep contract landed that printed a clean `PASS`; after it, an honest `NOTHING_DECLARED`, which is better and still not what the caller meant. It now falls through to `.claude/` when the root itself holds no kit, which is what `squad.layout` has resolved for hooks since 2026-08-26. The gate's own default was already correct — this is only for a caller who names the project root.
- **A brief that QUOTED the split marker was read as declaring one (kit#14).** `NEEDS_SPLIT` is defined by the rubric as *"declared by the reviewer, never inferred"*, and a brief tells its reviewer how to declare one — that is what a sign-off checklist is for. Quoting the syntax made the scorer emit the verdict for a brief in which nobody had declared anything: a regex over a document producing a verdict about intent, and attributing it to a reviewer. The marker now counts only where the document speaks in its own voice — a comment on its own line, outside code fences and code spans. A marker inside a fenced example is documentation, and the verdict stays reachable where it is genuinely used.
- **The judge's approving signature lowered the score of the brief it approved (kit#17).** `alignment_judge.py` appends the judge's `--reason` under `## Reviewer sign-off`, and the placeholder criterion scanned the whole document for the bare token `UNKNOWN`. So a judge writing *"no unanswered UNKNOWN"* as part of saying the brief was clean made that criterion fail. Measured on a real brief: **34/34 before the signature, 32/34 after**, on a signature whose only sin was using the word. Nearer the threshold, an approving signature would have pushed the brief below 90% and turned `ALIGNED` back into a refusal — the gate scoring the reviewer's prose instead of the artefact. The criterion measures the author's brief; the sign-off section belongs to the reviewer, and the threshold rule is explicit that those are two different people. A placeholder in a requirement is still caught after signing.
- **One open question was charged twice, and 9% is enough to fail an honest brief (kit#18).** An `UNKNOWN` inside `## Questions answered` took 2 points from `no_placeholders` and 1 from `questions_closed`, and both closed the instant a reviewer answered that single question. One failure, charged twice, for 3 of 34 points — **~9% against a 90% threshold**, so a brief whose only imperfection was one honestly declared open question could not clear the gate. The cheapest way past it was to delete the question or paraphrase it into prose, which is precisely the evasion `no_placeholders` exists to refuse: a rubric built against gaming was rewarding it. `no_placeholders` is now scoped to the body outside that section, which `questions_closed` already owns; a placeholder in a requirement or an acceptance criterion is still a hole and still charged. Found by an ALIGN agent on a real backlog item, which reported it rather than working around it.
- **Two thirds of the drift report was tool cache.** `install.sh` refuses to copy `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache` and `.hypothesis`; the drift report knew about the first two. A file the installer will not copy cannot be missing from an install in any meaningful sense, so every one of them was noise. Measured the same hour the scope was widened to all six trees: **43 of 64 only-in-kit entries were cache**, in a report whose own docstring warns that *"a report nobody is required to read is a report that goes unread"*. Aligned to the installer's list, and a test fails when the two disagree — fourth time in one day a rule lived in one file and was missing from another. The report went from 64 entries to 5, and all 5 are real.
- **The drift report between a kit and its install looked at one of the six trees.** `--kit` defaulted to the kit's `skills/`, so `rules/`, `hooks/`, `commands/`, `mechanisms/` and `squad/` were never compared — four of them entirely invisible to the check whose whole job is finding where a consumer and the kit have parted ways. Measured on 2026-09-02: `mechanisms/kit_issues.py` and `mechanisms/session_ready.py` existed in the kit and not in a consumer, and nothing reported it — **the same afternoon the syncer was found to have dropped that identical tree from distribution after a rename**. The default is now the kit root, and the comparison covers exactly what `install.sh` carries: widening it to the whole root is the opposite failure, reporting 5994 files only-in-kit, because the kit also holds tests, wiki, images and study material no consumer receives. Comparing a single tree on its own still works and is tested, because restricting the scope there would match nothing and report a clean sweep over an empty comparison — this file's own defect, arriving through its fix.
- **`--item` accepted an entire queue as one item id and built a directory named after it.** The value reaches the filesystem — it becomes the directory holding the stage agents — and it is substituted into every generated prompt. Measured on 2026-09-02: a caller's shell did not split a queue variable, so `--item` received `"B-033 B-136 B-162 B-171 B-172"`, and the script created a directory with that name holding four stage agents whose every mention of *the item* named five. **Nothing objected.** Those agents would have run and reported findings against an item that does not exist. `squad.plan` has validated its own slug since it was written, against this same hazard; this script had no such check. It now refuses anything that is not `<letters>-<digits>`, writes nothing before refusing, and says in the message that an unsplit queue is how the gap was found.
- **The alignment scorer credited a scenario class for a sentence that DENIED it (kit#12).** A Flows section holding the single sentence *"There is no recovery path"* scored `1/4 classes: recovery`. The criterion moved 0 → 1 and added a real point toward the 90% gate that decides whether an item may be implemented — for a brief with zero flows drawn. The rubric is this kit's only mechanical defence against "happy path only", and that criterion was reading a negation as evidence. A class now counts when it is **drawn**: an explicit `[class]` marker, or a heading naming it. Detecting the negation instead was the other option and was rejected — it needs a list of the ways English says no, and every word missing from that list is this same bug again. Filed by an agent running inside the fleet.
- **The alignment scorer blamed a missing heading for an empty section (kit#13).** A brief whose `## Functional Requirements` held prose but no bullets was told the section did not exist. The score was right and only the reason was false, which is the expensive half: the gate's entire value is telling an author what to close, and this line sent them to add a heading already there instead of to add requirements. The two states are now distinguishable — *"`## Functional Requirements` is present and lists nothing"* — and the identical branch in the NFR criterion is fixed with it, because a fix applied to one of two identical branches is half a fix. Also filed by an agent running inside the fleet.
- **Three stage templates promised each agent a worktree the scheduler had stopped giving.** The isolation was removed the same day (it isolated the KIT's repository rather than the consumer's, and every stage is read-only), and the prose went on describing it — including a section headed *"You are alone in this tree"*, which had become the opposite of true. The test that caught it was written for the inverse case, when templates lagged behind the code; it now reads BOTH sources and fails whichever side moves next, rather than asserting a remembered answer.
- **A closed item mentioned in passing erased a decision a person still owed, and the item went into the queue.** `live_blockers` returns the open items still holding an item back, and when none remain it reports the item free. That is right when `blocked_by` is a list of ids and wrong when it states a reason, because then the ids in it are context and the reason is the barrier. Measured on a consumer 2026-09-02: B-060 reads *"aguardando disposição de status: ... bala 2 movida para B-061 (shipped) ... Vide report B-060"*. The parser lifts B-061 and B-060, the self-mention is dropped, B-061 is `shipped` — so no open id remained and **the item was handed to the queue as the next thing to work on**, with a status disposition still owed by a person. B-126 the same way, and the two of them were the entire remote queue that day. Nothing bad happened only because the lead reads the prose and refused. `check_backlog_structure` has carried this exact rule for `stale_block` all along — *"a value that also states a reason outlives its item edge, and nothing in this repository can tell whether the sponsor has ratified"* — the **third time in one day** that a rule lived in one script and was missing from the other reading the same field.
- **An item that mentioned its own id in prose became its own blocker, and 28 false blockers refused every push.** `blocked_by` is prose by design — when the field was measured, seven of the eight items carrying it named a sponsor decision or an external action and only one named an item — so the parser lifts every id it sees anywhere in the value. And prose about an item mentions that item: *"Vide report /idea-to-release **B-060** de 2026-08-31 (4 opções A/B/C/D)"* made B-060 its own impediment, then a ring of one, then a deadlock no work can clear. Measured on a real registry on 2026-09-02: **14 items reported `self_block`, 14 more reported a `B-NNN -> B-NNN` cycle, 28 blockers, every single one false**, and the verdict they produced blocked every push to that repository. `select_backlog_item.py:141` had fixed exactly this for the queue — same field, same reasoning, same one-line filter — and the fix never travelled to the gate reading the same field. The narrowing is careful: an ids-only value naming itself (`blocked_by: B-060` on B-060) describes nothing and is still reported, because that one is a typo. Verdict on the measured registry went `INVALID {blocker: 29}` → `SHIPPABLE_WITH_CAVEATS {blocker: 0}`.
- **The renaming of `scripts/` to `mechanisms/` cut a whole family out of distribution, silently.** `sync_consumers.py` decides what a kit update may push by matching path prefixes, and its tuple still read `scripts/` — a directory that stopped existing the same day. From that commit the syncer propagated **nothing** from `mechanisms/`: not the fleet lead, not the pipeline scheduler, not the protocol client. It also never carried `squad/`, the hook library. Measured on a real consumer: the delta reported **5 files** and the true delta was **11**, and three of the missing ones were fixes made that day — including the one that closed a gate letting unsigned items into PLAN. The dry-run said `stale=0 local-change=0` and looked clean, because a prefix matching nothing produces no findings. Same defect as the shallow globs found three times on 2026-09-01: **a matcher that lost its reach turns silence into a pass.** The tuple is corrected, and a test now fails when it disagrees with the trees `install.sh` copies — the only way the two ever diverge is a rename, and that is exactly what happened.
- **The pipeline's alignment gate named what may not pass, so everything else did — five unsigned items reached PLAN.** `alignment-threshold.md` requires two independent things before an item may be planned: a machine score at or above the threshold, AND a sign-off from a reviewer who is not the brief's author. The scheduler tested `verdict === 'BLOCKED'` and advanced anything else — a denylist, which passes what it was never told to stop. Since ALIGN's own template forbids it from emitting `ALIGNED`, **every reachable verdict fell through it**, and the gate could not close on any item by construction. Measured on a real backlog on 2026-09-02: five of seven items scored `AWAITING_REVIEW` — the state the rule's own anti-patterns describe as *"the machine has finished and the human has not started"* — and all five were sent to PLAN. **Three of those five PLAN agents refused the work on their own reading of the rule and two did not**, so the gate held exactly where an agent chose to hold it. `pipeline_orchestrator.py` had the correct shape the whole time (`if verdict != "PASS"` → park, *"the scheduler obeys the gate; it does not reinterpret it"*); this file duplicated that decision and drifted from it. Both gates are now allowlists.
- **A new JUDGE stage, because the sign-off had no stage to happen in.** The second condition was unsatisfiable, not merely unsatisfied: ALIGN may not sign its own brief, PLAN consumes the verdict rather than issuing it, and nothing sat between them. `stage-judge.md` is a reviewer that did not write the brief — it measures the scorer's exit code itself rather than accepting one reported to it, reads the brief against what the repository actually contains, and signs or refuses under its own name through `alignment_judge.py`, whose `--reason` is the deliverable. It is told, at length, that refusing is the normal outcome: an item it refuses stops while the other lanes keep moving, which is the shape this pipeline exists for. It may not edit the brief — fixing a gap it found would make it the author, and an author may not sign.
- **The pipeline's stage agents were isolated in a worktree of the wrong repository.** Each stage carried `isolation: 'worktree'`, and a worktree isolates the repository of the **cwd** — which on a consumer run is the KIT, not the repo under `args.repo`. So every agent got a working copy of the scheduler's own project while its instruction named an absolute path inside another one: a bare `git log` or `git diff` would have read THIS repository's history and been reported as the backlog item's evidence. The isolation also protected nothing, which is why nobody noticed — all three generated stages are read-only (`tools: Read, Glob, Grep, Bash`), and worktrees exist for agents that mutate files concurrently. Removed, with the conditions for bringing it back written where it was.
- **Nothing in the suite read `pipeline_workflow.js`, and both of its worst defects were one line long.** A `.js` file in a Python project is reviewed by eye and by nothing else. The hand-written queue that opened with a blocked item, and the default repo path that carried a workstation's home directory into an adopter's git history, each sat in this file through review. Five assertions now read it — queue from the registry rather than a literal, no default repo, no worktree, every stage labelled and grouped, and the verdict only ever read and never assigned. They parse the executable lines only: an earlier test of mine asserted a word was absent from a source file and failed on the comment explaining its absence, because prose is where a file argues with itself. Each of the three defects was reintroduced into a copy and drops exactly one assertion.
- **A versioned file carried an author's home directory, and the kit had no gate against it.** A workflow definition under `mechanisms/fleet/` defaulted its repository argument to an absolute path naming both a workstation and the origin ecosystem. It shipped to a consumer, and **that project's publish-hygiene gate caught it — ours did not**: `ORIGIN_RE` matches `theo-[a-z]`, not the name followed by a slash, and nothing looked for home directories at all. The default is gone (the workflow now refuses without an explicit repo, because there is no sensible default for "whichever project invoked it"), and a new check refuses `/home/<user>/` or `/Users/<user>/` in any tracked file. History is public retroactively: a path removed tomorrow still sits in the commit that shipped it. A line that must carry the shape — a fixture reproducing a tool's own error message — declares it with `workstation-path: <why>` on that line or in the comment block above it, which is `english-only`'s mechanism plus the lookback that rule lacks, and lacking it cost a reformat twice today.
- **The agent cooldown was per session, so a three-session fleet asked the same question three times as often.** `main()` builds one `Lead` per session and `agent_asked` is a field on `Lead`, so the 1800s cooldown was one per *(agent, session)* — while the question these consultations carry, *"the queue is stopped, what now"*, is about the QUEUE, which is one thing. Measured on a consumer: **five consultations to the same agent in 36 minutes**, gaps of 96s, 1035s, 852s and 159s, every one answered rather than barred, all five asking about the same two items. They opened 27.5 minutes of a 56-minute window — half of it — and produced nothing the first had not. The clock moved to `Fleet`, beside the claims, which is where the fleet's shared facts already live; a single-session lead keeps its own, where the two are the same thing.
- **The wall reported itself, wasted most of its screen, and formatted for the wrong width.** Three defects a screenshot showed at once. The status pane listed every tmux session, so it listed the wall — whose pane is that report, giving the reader the report inside the report; both scripts now share one `FLEET_PATTERN`. The fleet's sessions were created detached, so tmux sized their windows to the 80x24 default and they stayed there however large the pane was, rendering the remaining seventy percent as dots; `aggressive-resize` makes a window follow the client looking at it. And the report measured its width with `tput`/`COLUMNS`, neither of which survives `watch` — a 110-column pane formatted for 100 and every other line wrapped. It asks tmux through `$TMUX_PANE`, and the wall runs it in a plain loop so that variable reaches it.
- **A BLOCKED report from the cycle that orchestrates the queue was invisible to the reader of that queue.** `squad_boss.HALT_DIRS` watched `implementations/`, `reviews/` and `releases/` — not `maintenance-runs/`, where `cycle-maintenance` writes and where its `ITEM_BLOCKED` reports land. A consumer measured it from the inside on 2026-08-31 and filed the gap as an item's own blocker: *"meus BLOCKED reports desta data ficam invisíveis ao SELECT até isso"* — an item waiting on a kit fix nobody upstream knew was needed, which is what an installed `.claude/` does to a finding.  <!-- english-only: verbatim quotation from the registry it describes -->
- **`records/releases/` was the only watched directory the installer never created.** `cycle-release.md § Output` names `records/releases/{version}-release.md`, `squad_boss` watches it for halts, and the scaffolding list held the other ten. Found by a test asserting that every directory in `HALT_DIRS` is one the installer creates — the kind of pair that only disagrees when somebody asks them to agree.
- **An item could be its own wall, and a wall pointing at itself is a deadlock nobody can clear.** `blocked_by` is prose and the parser lifts every `B-NNN` it finds, so a sentence naming the item — *"same wording as B-079 and B-080"* — listed the item as blocking itself. The board then showed a cause somebody could go and fix, and there was nothing to fix. Measured on a consumer 2026-09-02: 26 selectable items behind seven roots, two of which were holding themselves. The self-reference is dropped; the prose still holds the item, which is the contract — an impediment with no item to point at is exactly what an empty blocker list means.
- **A per-consultation ceiling stopped an entire fleet, and there was no way to raise it without editing the script.** `squad_lead.py` caps each agent call with `--max-budget-usd`, defaulting to 6.00 — a figure its own comment describes as measured "with room for a larger project". A real project exceeded it on 2026-08-31: the lead exited 1, the watchdog died with it, and three executing sessions sat idle for two days. The queue was not stuck on the work; it was stuck on a ceiling. `start_fleet.sh` now reads `AGENT_BUDGET_USD` and passes the flag only when set, so the script's default still stands for everyone who does not touch it.
- **`check_squad_map` had never run in a consumer, and nobody could tell.** Its `--root` defaulted to `Path.cwd()`, which is the ecosystem root only in the kit's own repository. Under a `.claude/` install — the layout every consumer has — the cwd is the PROJECT and the map sits at `.claude/rules/squad-map.md`, so the gate exited `FATAL: not found` every time and `verify_ecosystem` reported it as failed. It resolves the layout now, like every other gate. Found by reinstalling the kit into a real consumer, which is the only place the bug exists.
- **Two more gates asked a consumer's own design to answer to the kit.** `check_skill_map` never read `rules/auxiliary-skills.txt`, so a project with three domain skills got `missing_from_map` ×3, `missing_sop` ×3 and a count disagreement — none about the kit. `check_xrefs` has read that file since the day it was added; this is the same HALF exemption its own docstring warns about, where the first fix covered one check and left its sibling charging. And `check_squad_map` told a kit role from a domain specialist with `git ls-files agents/`, correct only where specialists are gitignored: in a consumer the project versions all of them, so the map was asked to name agents it has no business knowing.
- **The install manifest declared the kit's four agent roles to be the project's.** It listed `agents/README.md` alone while the installer copied kairos, iris, daedalus and hermes beside it — and the manifest's own header states the rule those four were then failing: *anything not here is the project's*. A consumer reading it would conclude it owned four files the next install overwrites. The test that pinned this asserted the omission as correct; it now asserts that the manifest and the directory agree about what arrived.
- **`PR_OPEN_AWAITING_APPROVAL` was not a blocking verdict, and a consumer's queue spent a day re-selecting an item nothing could advance.** `cycle-release.md` declares the state as *"chain paused at the human-approval gate. Resume automatically once the PR merges"* — the same semantics as `AWAITING_HUMAN` under a different token — and `blocking-verdicts.txt` never listed it. Measured on a consumer on 2026-08-31: an item emitted the verdict after commit, push and `gh pr create`; SELECT re-invoked it because the token was absent from the list, and the watchdog read as available something paused at an open PR. Ported back from the consumer that found it, where it had been fixed inside the installed `.claude/` and therefore protected exactly one machine.
- **The TDD gate called 22 covered files untested, and one of them was the gate's own hooks.** `stop-validation` recognised a single shape: a test named after the file, beside it or in the owning unit. This repository files tests by AREA — `tests/hooks/test_reference_zone.py` covers `hooks/boundary-check.py` — so nine hooks carrying 130 tests and a library carrying 91 were all reported as having none. Twenty-two lines of warning every session is the gate people stop reading, which the hook's own comment says about a different case. Three signals were added, each one evidence that a test REACHES the file: it imports the module, it imports the package whose `__init__.py` re-exports it, or it runs the file by path — the last being how every hook here is tested, since a hyphenated filename cannot be imported. 22 findings became 3, and all three were confirmed by hand to have no test at all. `conftest.py` also stopped being graded as production source: it exists to support tests, and asking it for one of its own says nothing.
- **What the widened rule does NOT accept, and why.** A test mentioning a symbol the module defines was measured and rejected: a module defining `run` would be marked covered by any test calling `subprocess.run`. That converts a visible false positive into a silent false negative, and for a gate the silent one is worse — nobody learns a file went unprotected. The known cost of what WAS accepted is stated in the test file: "a test names the file" is a text match, so a TODO list mentioning a filename would clear it. The new tests had to assemble those filenames from fragments to avoid satisfying the very signal they assert is absent, and the docstring explaining the blind spot fell into it on the first attempt.
- **The three blocking layers of the read-only zone guarded nothing at all.** `rules/reference-provenance.md` declares the zone as `study-material/**`; every regex in `boundary-check` and `validate-command` matched `records/(references|tools)/`. `study-material/` exists in this repository and neither of the other two does — so writes into the zone, copies out of it and commit messages citing it were all permitted, while the block messages named `study-material/` as protected. The pre-filter made it worse: it skipped the whole segment loop for any command without the literal `records/`, so the guards were unreachable and their silence read as a clean pass. The zone is now the one the rule declares, and `records/references/` was retired with the practice that filled it — Squad inverted the Cycle's peer-study DISCOVER on purpose, and the same day `assess_confidence.py` stopped scoring peer material. What the retirement costs is written into the rule: a consumer still holding material there is unguarded and must move it.
- **Four hook test files existed and NOTHING executed them; three already failed.** Not CI, not `pytest` (`testpaths` listed only `tests`), not `run_slice_tests.sh`. Their 120 assertions covered the git discipline of Unbreakable Rule 4, the linter scoping that stops every keystroke becoming a full build, and — in the one file furthest from the suite — every secret-file case. `hooks/tests/test_stop_validation.py` was outside `testpaths` too, and its fourteen tests cover the CHANGELOG gate while mentioning a credential once. So the most expensive thing the hook prevents had its only proof in the file nobody ran. All of it is now Python under `tests/hooks/`, collected by the suite: 189 tests across the hooks and the library. The regex fix above took one line; the reason it survived for months was this.
- **`assess_confidence.py` decides whether DISCOVER runs at all, and had no test.** 298 lines, and `/idea-to-release` derives the chain's depth from its verdict — a score of 95 returns `("HIGH", "none", "Sufficient prior art; skip discover.")`, sending the item to PLAN unmeasured. `skills/map.md` says of it *"the script is deterministic and its output is the truth"*, and nothing checked what that truth was. Eleven tests now pin every band boundary on both sides (a band drifting one point silently changes which phases run for a whole class of items), the purity of the mapping, and that a `LOW` verdict returns depth `full` rather than a refusal — the refusal lives in `SKILL.md`, so a consumer must branch on the **verdict**, never on the depth.
- **Prior art bought its way past the measurement, and no longer does.** `references/` carried the **heaviest** weight in `assess_confidence.py` (+30) for a match under `records/references/` — which the script itself defines as *"projects SIMILAR to ours… how did they solve it?"*. The top band returns depth `none`, so enough peer material made `/idea-to-release` **skip a phase `cycle-phases.txt` declares required**, on the strength of the one signal `README.md` calls never-evidence and gate G5 refuses as grounds for an item existing at all. The weight was inherited from Cycle, whose DISCOVER asks how others solved it; Squad inverted that question on purpose — *"it produces imitation, not maintenance"* — and the weights never followed. `score_references` now returns **0 and still returns its matches**: a peer project cannot tell you what is true of your system, so it cannot stand in for measuring it, but knowing the material exists helps whoever writes the plan. Two tests pin it, including one showing that three matching peer projects move the score by nothing.
- **`recommended_depth` was not a refusal signal, and a caller could not tell.** A `LOW` verdict returns `"full"` — the same value as `MED-LOW` — so a consumer branching on the depth proceeds at exactly the confidence the band exists to stop. The refusal lived only in `SKILL.md` prose. The JSON now carries an explicit `refuses` field, with a test that no other band sets it.

### Fixed
- **An `ast-grep` rule shipped an instruction with a hole in it, and nothing had ever loaded the rule files.** `skills/ast-grep` ships five YAML rules and no code, so no test had opened them. `method-call-ts.yml` wrote *"Default $METHOD is `embed` — change to `add`, `search`…"*, but the pattern binds `$OBJ` and hardcodes the method name; `ast-grep` interpolates metavariables into the message at render time, so the unbound one was substituted with nothing and the operator read **"Default  is `embed`"** — an instruction pointing at a knob that does not exist. The message now says what the edit actually is: the method name is a literal, deliberately not a metavariable, because a rule matching every method call answers a question nobody asked. A metavariable the pattern DOES bind stays useful and is not touched — `class-extends-ts` prints `$BASE`, which renders the matched class. Eleven tests now load every rule file, assert `id`, `language` and a `rule:` block, and refuse any message naming a metavariable the rule does not bind; one of them fails if the glob ever matches nothing, so the set cannot go vacuous.
- **A typo in an evidence file deleted the caveat a `1.0` announcement is owed.** `check_honesty_gate.py` treated `outcome` as free text while `§ 5` of its own rule LOCKS it to three values, and the `no_failure_story` soft cap fired only when every outcome was the literal `pass`. So `passed` read as a failure the team never had: the cap stopped firing, the verdict went `EVIDENCE_WITH_CAVEATS` → `EVIDENCE_SUFFICIENT`, and the exit `/release` reads at the `1.0.0` boundary went `3` → `0`. The thing the step exists to put in the release notes simply disappeared, and the file that caused it was still counted as evidence. The vocabulary is now mirrored in the script the way the status one already was, with a test tying the tuple to the line in the rule — and a value outside it makes the file **ignored**, which is the answer the rule already gives for a missing locked field, so a typo costs evidence instead of buying a clean verdict. The three silent skip paths (missing field, unparseable date, unknown outcome) now report what they dropped under `ignored_evidence`: ignoring the file is the rule's instruction, but being silent about it left the operator who typed it no way to learn why it did not count. Six tests, two of which fail with the validation removed.
- **`/implement`'s precondition demanded a human signature the amendment had already lifted — while citing the amended file.** `rules/cycle-implement.md` required *"a machine score >= 90% and **a human's tick** in every `## Reviewer sign-off` box"* and pointed at `alignment-threshold.md`, whose § Amended 2026-09-01 says the reviewer need not be a person: it must not be the AUTHOR, and `alignment_judge.py` can be neither. `cycle-plan.md` had followed the amendment; the implement precondition had not, and `score_alignment.py`'s own docstring still read *"only a human can give it"* above code that already accepted a judge — the verdict turns on `reviewer_signed_off`, with `signed_by_is_human` reported beside it rather than gating on it. **Honoured literally, the stale wording re-freezes every unattended run at `AWAITING_REVIEW`** — exactly the halt the amendment exists to end, reintroduced by prose. Three sites corrected: the precondition, the module docstring, and the comment above the sign-off parser.
- **`tests/test_alignment_signer_contracts_agree.py` keeps the three documents from diverging again.** It reads the authority, refuses any follower that reasserts a human-only signature — while tolerating a file that QUOTES the old wording to explain it changed — and asserts the behavioural half: that the verdict expression gates on `reviewer_signed_off` and **not** on `signed_by_is_human`, which exists to report the weaker claim rather than refuse it. A first version of the test matched a sentence in the module docstring instead of the verdict expression; it now requires the `return`.

### Added
- **`check_tdd_in_bugfix.py` had no test, and it is an active gate.** Sixteen checkers ship in `plan-confidence` and fifteen were covered; this one is imported by `run_structural.py`, called at line 304, and its ratio becomes **twenty points** of the completeness score at line 197 — with nothing pinning what it detects, what it ignores, or what it reports when it finds nothing. Seven tests now cover the bug-fix keyword list (a synonym the list misses is a fix shipping with no regression test), the task-body delimitation (a TDD block belonging to the NEXT task must not cover this one), and two behaviours **documented rather than endorsed**: zero detected bug-fix tasks yields `coverage_ratio == 1.0`, which `run_structural` turns into 20/20 and a reason labelled POSITIVE reading `"TDD in bug-fix (0/0)"`; and a task id outside the canonical `T<n>.<n>` shape is invisible to the gate while still scoring perfectly. Both are consistent with `check_adr_completeness`, which scores an empty ADR set the same way, so they read as a rubric decision rather than an accident — pinned so that changing either is deliberate and carries a failing test.

### Fixed
- **Gate G-L paid points for the targets it exists to refuse.** `check_measurement_targets.py` guarded the live-host check with `if declared_hosts and host not in declared_hosts` — so an EMPTY set of declared hosts skipped the loop body entirely, `undeclared_hosts` stayed empty, and that in turn satisfied `if live_targets and not undeclared_hosts`, awarding the plan a **contributor** reading *"N live target(s), all declared"* when nothing had been declared. **The kit ships `rules/live-target.txt` empty on purpose**, so in every freshly installed consumer the gate was not merely inert — it credited a plan for naming a probe the cycle would refuse to run. An inability reported as approval, which is worse than an inability reported as zero. `_declared_live_targets` now returns `None` for an absent file against `set()` for a present-but-empty one, and the three states are distinct: absent → *could not be checked*; empty → **every** live host is undeclared, which is exactly what G-L is for; declared → passes. Three tests pin them.

### Changed
- **`mechanisms/dist/` is `mechanisms/distribution/`, because `dist/` is the name every project ignores.** A consumer's `.gitignore` carried the ordinary build-output rule — a bare `dist/`, twice — and it matched `.claude/mechanisms/dist/` as readily as any bundler output. The kit arrived there without `install.sh` and `patch_install.sh`: the one directory a consumer needs to update or patch its own copy, missing, while the other five families landed normally. Nothing reported it, because a gitignored path is absent rather than broken. The family is renamed to a word no build tool claims; the consumer that found it also got an explicit un-ignore, since its history still holds the old path.
- **A third glob had lost its reach, found by the migration.** `check_squad_map` listed hooks with `glob("*.sh")` and matched mentions with a `\.sh` pattern. Once the hooks became Python it listed ZERO hooks, found no mention of any, and reported the map as agreeing with the directory — an empty set has no absentees. Same shape as the shell-syntax gate and the orphan-verdict sweep, three times in one day: a glob that lost its reach turns silence into a pass. All three now take both suffixes.
- **All nine hooks are Python.** 1591 lines of shell parsing JSON through `jq` became hooks that receive a typed context. Three pieces moved into the library rather than being written three times: `squad.layout` (which of the three install shapes is on disk), `squad.plan` (which plan is active, what it promises, whether it still matches its attestation) and the output verbs. Each hook was migrated against its tests, and the tests address the hook BY NAME — `hooks/<name>.*` — so the contract survived the rename instead of being rewritten to match it.
- **`install.sh` carries `squad/` into consumers.** Every hook imports it, and a hook whose library is missing exits 2 on every event — fail-closed is right when the payload is unreadable and useless when the hook itself never loads. `hooks/../squad` resolves correctly in all three layouts (standalone, `.claude/` copy, plugin root), so no detection is needed.
- **`.active_plan` is validated before it becomes a path.** Only `userpromptsubmit-inject` checked the slug; `precompact-preserve` and `sessionstart-context` read the pointer and joined it onto `records/plans/` directly, so a pointer containing `../../` resolved. `squad.plan` validates for all three, and an unattested plan is now distinguished from an altered one — conflating them either cries wolf on every plan nobody signed, or lets an edited one through because its record was missing.
- **`scripts/` became `mechanisms/`, in five families.** Thirty-six files sat flat in a directory whose name described their shape and not their job — seventeen of them named `check_*`, alongside the installer, the status line and the fleet launcher. They are now `gates/` (measurement), `cycle/` (routing, the event stream, status transitions, attestation), `fleet/` (many sessions and the line a person watches), `dist/` (into a consumer and kept in step) and `conventions/` (where things live and what shape they have). The import namespace stayed **flat** — a family is a directory, not a package — so `check_xrefs` still imports `ecosystem_utils` by name; `tests/conftest.py` puts all five on the path so a test never has to know which drawer a module was filed in. Two hundred and seventy-one path references were retargeted across 112 files; the ones in released CHANGELOG entries were deliberately left alone, because on the day those were written the directory WAS `scripts/` and rewriting the record would falsify it.
- **`conventions/`, because the kit's own gate refused `lib/`.** The family holding `sop_format.py` and `ecosystem_utils.py` was called `lib/` for about twenty minutes, until `check_semantic_names.py` reported it: *"a name from the bin list says what was left over, not what is here"*. It was right, and `shared/`, `common/` and `core/` are on the same list. The two modules encode the kit's conventions — where material sits on disk, and what shape a SOP has — so that is the name.

### Fixed
- **Moving a gate one directory deeper made it report five real skills as orphans.** `check_xrefs.py` asks the filesystem whether `skills/<name>/` exists, resolving it from its own location. From `scripts/` that was `parent.parent`; from `mechanisms/gates/` the same expression points at `mechanisms/skills`, which does not exist — so every single-word skill stopped being recognised and `acceptance`, `implement`, `pipeline`, `release` and `review` were reported as referenced by no cycle. **It did not crash; it produced five confident WARN.** Seventeen more file-relative paths had the same off-by-one, found by sweeping for the pattern rather than by waiting for each to surface. Caught only because the run was compared against the pre-move tree: with no baseline the five warnings read exactly like a pre-existing backlog.
- **The shell-syntax gate would have gone quietly blind.** `verify_ecosystem` collected shell files with `(ecosystem_dir / "scripts").glob("*.sh")` — a **shallow** glob. With the six `.sh` files now one level down in families, the glob returns nothing and the check reports a clean run over zero files. It is `rglob` now. This is the failure mode a directory reorganisation produces by default: not an error, a silent narrowing of what gets measured.
- **`mechanisms/README.md` declared a rule nothing computed, and covered 5 of 36 files.** Its own words were *"Every new script in this directory MUST be added to the inventory above"*. The inventory listed five scripts; thirty-one were undocumented, and the list still read as a list. `check_mechanisms_inventory.py` now confronts the README with the directory in both directions and separates three findings, because the fix differs for each: a file with no row, a row with no file, and a row filed under the wrong family — the last being the dangerous one, since it is present and therefore trusted. A missing or unparseable README is `INVENTORY_UNREADABLE`, never a pass. It runs in CI and is the twelfth check in `verify_ecosystem`. Eight tests.
- **A consumer installed before the rename would have kept firing the old gates.** `install.sh` copies the kit's directories into `.claude/`, so a consumer already holding `.claude/scripts/` would end up with both it and `mechanisms/` — and the stale one is not inert, because `hooks/` resolves through a fallback chain that still lists `.claude/scripts/`. A hook would keep running the OLD checker and reporting its verdict as current: exactly the drift `check_install_drift.py` exists to name, arriving through the installer itself. The installer now removes the stale directory, and **moves aside rather than deletes** any file in it the kit does not ship — the project put it there and the kit has no standing to remove it. The path is printed. A test pins it and fails with the migration removed.
- **Three scripts are triplicated across the confidence skills, and the copies are declared.** `_rubric_loader.py` exists in `plan-confidence`, `discover-confidence` and `discover-plan-confidence` with **byte-identical logic**; `check_spec_smells.py` in the same three, identical but for a parameter name (`plan_path` → `artifact_path`). Both carry docstrings admitting it — *"Copied as-is from plan-confidence"*, *"Copy-with-attribution"*. Nothing has diverged yet, and that is the point of recording it now: `check_intake_gates.py` imports its block parser from `check_backlog_structure.py` rather than duplicating it, on the stated grounds that *"a second regex here would diverge silently, and the two would disagree"* — the kit has the right pattern and did not apply it here. Left in place rather than merged, because promoting shared code to `scripts/` moves files three skills import and that is a decision, not a cleanup.
- **The trigger detector looked for a name the model never uses, and scored a working skill 0/5.** `run_eval.py` isolates a description by writing a command file under a unique name (`<skill>-skill-<uuid>`) and the detector matched only that — but in a repository where the skill ITSELF is discoverable the model invokes the real one, `Skill(skill='backlog-item')`, and `"backlog-item-skill-9f2a" in "backlog-item"` is False. **Proven by running one of the failing queries by hand: the model called the skill at tool position five, after four `Bash` calls to orient itself.** Five cases were triggers; five were recorded as misses. This is verbatim the failure that class's own docstring describes and claims to have fixed — *"it can call a trigger a miss, never a miss a trigger… a number that looks like a result about the skill"* — surviving in the one place the author of the fix did not look. With both names recognised the same battery went **0/5 → 3/5** at a 120s budget, same model, same prompts — and **→ 4/5** once the budget was raised to 420s, because one of the two remaining misses was the timeout described below rather than a miss. The fifth is a real one: the `G4` case does not trigger, measured with zero inconclusive runs, which is now a fact about the prompt instead of a fact about the clock. One run, so it is a signal and not a rate.
- **A timeout was published as a trigger rate of `0.0`.** The code returned `False` directly under a comment reading *"Timed out, or the stream ended with no `result` event. Neither is evidence the skill was not used; it is evidence nothing was observed"* — the prose identifying the distinction and the next line ignoring it. Measured: a query where the model orients with several `Bash` calls before invoking the skill runs past a 120s budget. `None` now means undetermined; the aggregation keeps those out of the ratio and reports `not_observed` separately, because 3/5 with two timeouts and 3/5 with two real misses are different facts. The fold was extracted as `summarise_runs` so the rule could be tested at all — it lived inside a function that spawns subprocesses, so nothing could check it without invoking a model.
- **All four eval batteries this kit ships had never been executable.** `run_eval.py` came from upstream expecting a LIST of `{query, should_trigger}`; every battery here — `backlog-item`, `discover-plan`, `discover-edge-cases`, `discover-execute` — is a dict of `{skill_name, notes, evals:[{prompt, assertions, …}]}`, so each died on `TypeError: string indices must be integers`, iterating the dict's KEYS as if they were cases. Meanwhile `check_intake_gates.py` justified leaving gates G3/G4/G5 conversational because *"the eval battery covers exactly that"* — **a coverage claim resting on a file nothing could run**. The runner now normalises the kit's shape, and `tests/test_eval_batteries_are_runnable.py` loads every battery on every run, including a guard that no case is silently dropped in translation and one that fails if the glob ever matches nothing.
- **`run_eval.py` reported `0.0` for a skill the model could not see.** `claude -p` discovers skills under `<project>/.claude/skills/`; run against a standalone kit — skills at the repo root, no such directory — the model cannot reach the skill however good its description is, and every case scores zero. `skills/map.md` names this exact trap: *"a trigger rate that reads low and looks like a fact about the skill"*. It now checks discoverability first and emits `SKILL_NOT_DISCOVERABLE` with where it looked, refusing to publish an inability as a measurement — the same distinction fixed this session in `check_intake_gates.py` and, before it, in `check_opportunity_completeness.py`. Third tool, same defect.
- **`run_eval.py` could only be imported from its own directory.** `from scripts.utils import …` resolved against the caller's cwd, so importing or running it from anywhere else — a test, CI, the repo root — died on `ModuleNotFoundError: No module named 'scripts'`. It now resolves against `__file__`. A tool that only works from one directory is a tool nobody runs from where they are standing, and it is why the battery-loading test could not be written until now.
- **What the coverage claim says now.** `check_intake_gates.py` states precisely what is covered and by what: one eval case per judgement gate, a test asserting no claimed gate lacks one, and — said plainly — that a RUN measures **trigger** only. The `assertions` in each case describe behaviour and **no runner checks them**; they remain a reader's judgement. The previous wording read as behavioural coverage and was not.
- **The board drew eight columns for a nine-phase chain.** `board_state.py` carried `PHASES` as a literal tuple; `cycle-phases.txt` gained `brainstorm` and the tuple did not, so `/api/state` reported the chain starting at `backlog` and one phase short. **No test caught it because every test asserted against `PHASES` itself, which agrees with itself whatever it says.** It is now derived from the declaration — the same file `check_phase_drift.py` and `check_squad_map.py` read, so three readers and one source — and a test compares the two rather than the constant to itself. Found by **exercising `board_server.py` for real**, not by reading it: the defect was mine, introduced when the brainstorm phase was declared.
- **`/api/item/B-999` answered 200 for an id nobody ever filed.** The route matched the id FORMAT and never the registry, so an unknown item returned the same all-null body as an item with no records yet — two states a caller cannot tell apart. The board's whole discipline is not presenting inference as observation (a position it inferred carries a `derived` chip; an empty stream says so in a banner), and answering for an item that does not exist is that failure at the transport layer. `item_detail` now reports `in_registry`, read through the shared block parser rather than a second regex, and the route returns 404. Also found by exercising the server.
- **Gate G4 was called eval-covered and had no eval.** `check_intake_gates.py` justifies leaving G3, G4 and G5 conversational by saying the battery covers exactly them. G5 and G3 each had a dedicated case testing the gate FIRING; G4 appeared only as a secondary assertion inside the happy-path case, so the gate that refuses an unfalsifiable DoD was never exercised refusing one. A fifth eval was added — a hunch with a legitimate local `why_now` and a dod of *"faster and cleaner"*, where the item must be accepted and the criterion refused — and a test now checks that every gate the docstring claims covered is named by a case, so the claim cannot go stale again silently.

### Added
- **`/release` cuts twice: an `-rc.N` per batch, a final version only when a milestone closes.** The two answer different questions and are not degrees of one thing — a pre-release says *installable, scope unfinished*; a final says *a milestone closed and was accepted*. **`PRE_RELEASED` joins the verdict vocabulary**, and the separation is load-bearing: `advance_items.py` reads `RELEASED` and nothing else, so a pre-release cannot mark `shipped` work it did not finish. `compute_next_version.py` gained `--mode {pre|final}`, defaulting to `pre` because most cuts are pre-releases. **The final promotes rather than bumping again** — `0.2.0 → 0.3.0-rc.1 → 0.3.0-rc.2 → 0.3.0` — since bumping at the final would publish `0.4.0`, a version none of the pre-releases pointed at, so nobody testing `rc.2` would recognise what shipped. A standing rc also needs no bump level in either mode, so a `Changed`-only body no longer returns `AMBIGUOUS` and pauses the chain over a number that cannot change the answer.
- **"The batch is done" is mechanical, not a judgement call.** A cut decided by feel is a cut nobody can predict or audit, so the batch closes when the queue of ready items **dries up** — `select_backlog_item.py` returning `BACKLOG_EMPTY` or `BACKLOG_BLOCKED`, meaning everything in flight has landed. That moment already existed and already stopped the loop; `cycle-maintenance.md` called it *a prompt to sweep* and it still is, now also cutting an rc. **The limit is stated rather than discovered**: a queue that never dries up never cuts on its own, which is honest — with work continuously arriving any cut point would be arbitrary — and `/release --pre` exists for that case as an escape hatch, not a schedule.
- **The final release is gated on acceptance, not on the backlog emptying.** Every `B-NNN` citing `M<N>` is `shipped` AND `/acceptance M<N>` returned `ACCEPTED`. This is what resolves the collision the request surfaced: `cycle-maintenance.md` states that **a backlog is not a scope and an empty one is not an achievement**, so hanging the final version on `BACKLOG_EMPTY` would have meant either never releasing or contradicting that doctrine. A milestone IS a declared finite scope, the kit already had it in `ROADMAP.md`, and `/acceptance` is what separates *we shipped it* from *we shipped it and watched it work*. A `B-NNN` with no milestone rides the rc series and never triggers a final — the honest state for work nobody promised anyone.

### Fixed
- **`SEMVER_RE` matched a pre-release and threw it away.** The pattern ended `(?:[-+].*)?`, so `parse_semver("v0.3.0-rc.1")` returned `(0, 3, 0)` and every release candidate parsed as the final release of its version. Harmless while nothing produced an rc, and wrong the moment something does — which this change does. It now captures the counter, and `detect_current_version.py` had carried a test for exactly this tag shape since before anything emitted one.
- **The CHANGELOG must move once, at the final, and an rc must not run `promote_unreleased.py`.** Emptying `[Unreleased]` at `-rc.1` would leave `-rc.2` and the final with nothing to publish, and would file the entries under a version that was still a candidate. An rc now reads `[Unreleased]` for its notes and leaves it standing; the body grows across a whole milestone, which is correct — it is the milestone's changelog, accumulating.

### Changed
- **`cycle-brainstorm` is Iris's.** The four roles predate the phase, so it shipped ownerless and `rules/squad-map.md` recorded that as an open decision. Kairos was the other defensible reading — the backlog derives from the objectives — and he did not get it because **his role is the QUEUE**, and the brainstorm produces what the queue serves rather than the queue itself. Iris got it on three counts already written in her own file: her temperament is *refusing a brief that describes a system instead of an experience*, which is gate G-B1 verbatim; her standing question is *"and then what does the user see?"*, which is the vision's question; and she already holds the alignment mechanism — the same 17-criteria rubric at the same 90% floor, of which `cycle-brainstorm` is the instrument one level up. **She now holds both alignment gates, and that is not an overlap of the kind the seams forbid**: in neither does she sign. The product sign-off is the human's, an item's may be `alignment_judge.py`'s, and she produces what is graded without ever grading it. Kairos inherits the OUTPUT — the `OBJ-N` ids items cite through `traces_to`, plus the two questions that link makes computable and `build_agenda.py` puts in front of him. Her file also states a limit rather than hiding it: during the brainstorm there is **no domain specialist to consult**, since `/backlog-init` derives them and runs after, so `/brainstorm-trd` and `/brainstorm-pieces` rest on the room's own knowledge and should say when the technical confidence is thin.

### Fixed
- **The merge ADR claimed the envelope has four floors. It has five.** Corrected in `.squad/wiki/decisions/merge-is-inside-the-envelope.md`, which miscounted the very document it amends.
- **The merge ADR now separates the decision from the argument, and says the argument is unreviewed.** It carried `Decided by: Paulo Henrique (owner)`, which is true of the DECISION — auto-merge was chosen deliberately with the cost stated in front of the choice — and silently implied the same of the *reasoning*, which is the agent's reconstruction of why that decision is sound. The header now reads `Drafted by: the agent, from that decision · Owner review: not performed`, with a paragraph telling a reader to treat the argument as the agent's until a person edits the file. **The agent did not mark it reviewed, and that is the point**: the envelope says changing it is a human act, and it is the one document where an author validating its own draft would be the exact failure the kit refuses everywhere else.
- **BREAKING — `/implement` stopped generating agents and now routes to the project's own specialist.** Its Step 2.5 built a **SEPA** per invocation: an agent definition written to `agents/implement-{slug}-{date}/sepa.md` plus a paired knowledge skill written to `skills/implement-{slug}-sepa-knowledge/SKILL.md`, both composed from the plan, its ADRs, the edge-case review and the audits. Four reasons it went, each a fact about where it wrote or what it knew. **It wrote into `agents/`**, the directory holding the specialists a project derives from its own disk — mixing generated artifacts into the one map a consumer maintains by hand. **It wrote into `skills/`, which `install.sh` deletes**: every generated knowledge skill was destroyed by the next update, and `patch_install.sh` carried a standing workaround to preserve files that should not have been there. **It was specialist about the PLAN, never about the CODE** — every byte of its context came from documents the cycle had just produced, so it could not know that a root `go build ./...` covers almost nothing in a multi-module repo, or which false positives that domain generates, which is exactly what makes a second opinion worth its cost. **And its own contract did not know it existed.** Step 2.5 was justified in its own text as being "per `cycle-implement.md`", and that file contained no mention of SEPA at all. The three consultations per iteration (pre-RED, post-GREEN, pre-COMMIT) keep their cadence — the cadence was never the problem — and now go to the domain specialist resolved by `scripts/route_domain.py`, the same call `daedalus-tech-lead` makes, with the same refusal: **exit 3 (`BROKEN ROUTE`) halts and does not stand in**, because answering for a domain whose invariants nobody wrote asserts facts that were never checked. A plan citing no `B-NNN` has no `repo:` to route on and records a skip — with no declared domain, any specialist chosen is chosen by resemblance. Logs moved from `sepa-iterations/` to `specialist-consultations/`.
- **`cycle-implement.md` now prescribes the step its skill was already calling mandatory.** The contract gained a `## The domain specialist — consulted, never generated` section with the routing table, the four exit codes and their actions, the skip case, and the authority boundary. This closes a gap rather than adding a step: a MANDATORY instruction resting on a contract that does not contain it is the defect this kit exists to catch, pointed inward.

### Removed
- **`hooks/environment/detect-layout.sh`**, whose last consumer became Python. `squad.layout` answers the same question — which of the three install shapes is on disk, and where the kit's CODE ends and the cycle's DATA begins — with tests, which the shell version never had. The prose that cited it now says what it replaced rather than pointing at a file that is gone.
- **`templates/sepa-staff-engineer-template.md` and `templates/sepa-knowledge-skill-template.md`** — the two generators, with nothing left referencing them. `reference/sepa.md` became `reference/domain-specialist.md`, which keeps the protocol and records why the generated agent was replaced. `reference/resume-protocol.md` lost its "refresh the SEPA brief" step: the per-plan agent embedded the plan verbatim, so a corrected plan left a stale copy behind until somebody rebuilt it, and routing to a file the project maintains removes that class of staleness rather than scheduling a refresh for it.

### Fixed
- **Two of the three SEPA consultations pointed at a file the protocol says is never written.** `implementation-prompt.md` asked consultations 2/3 and 3/3 to read `agents/implement-{slug}-{date}/sepa-staff-engineer.md`, while `reference/sepa.md` stated the filename in the same breath as forbidding it — *"file name is `sepa.md`, NOT `sepa-staff-engineer.md`"*. Both consultations were reading a path that never existed, which is how prose that nobody executes stays wrong. Moot now that the generation is gone, and recorded because it is the evidence that the step was never exercised.
- **`*-sepa-knowledge` is now documented as compatibility rather than as a live case.** `check_xrefs.py` exempts it from the orphan sweep and `patch_install.sh` preserves it; with no producer left, both would read as describing something the kit still does. The tolerance stays — consumers hold what was already written to their disk, and dropping the pattern would orphan those files and fail the check in a repository that did nothing wrong — and each site now says it is legacy and when it can go.

### Added
- **`rules/squad-map.md` — the 360º view, and it is in the agent's opening context rather than in a file nobody opens.** `skills/map.md` answers *which skill do I reach for*; nothing answered *where am I, who decides this, and what governs it*. The map places every phase against the skills that run it, the contracts that govern it, the script that computes its verdict and the role that owns the decision — plus the three layers and which of them survives a reinstall, the transversal rules, the eight hooks, and the one cycle delivered from outside. **A compact form is injected at SessionStart** by `sessionstart-context.sh`: the chain, the four roles, and the one routing rule that has a refusal attached. Not per turn — `userpromptsubmit-inject.sh` records why that distinction matters, its additionalContext staying in history so anything re-injected per turn accumulates linearly and drives compaction. Once per session is the right cadence for orientation, and unlike a per-turn hook a pointer here **is** walkable, because the agent has the whole session to open the file. The summary is a copy and the map is the source, held by the same discipline the parsimony ladder already carries in the sibling hook.
- **`check_squad_map.py`, and the two things it refuses to claim.** A map injected at SessionStart is worse than a stale document if it rots: it is a false premise in the opening context, which every later decision rests on. It confronts the map with the directory on phases, cycles, kit agents and hooks — and deliberately leaves the skill inventory to `check_skill_map.py`, since two checkers over one fact can disagree about it. **Cycles and hooks are checked in both directions; phases and agents in one, and the docstring says which and why**: catching a map that names a deleted file needs a name shape unambiguous enough to extract from prose, and `*.sh` and `cycle-*` are while an uppercase phase name and a hyphenated agent name are not — a pattern wide enough to find an invented one matches half the document, and claiming otherwise would be fabricated precision. It runs in `verify_ecosystem.py`, now eleven checks.

### Fixed
- **The map checker's second direction could not fire, on its first run.** `mentioned` was built by filtering the on-disk set — `{h for h in hooks if h in body}` — which makes it a subset of `expected` by construction, so `mentioned - expected` was always empty and `absent_from_disk` was unreachable. Half the checker was inert while reporting green, which is the defect shape this kit exists to catch, in its own new code. `test_a_hook_the_map_invents_is_reported` failed on the first execution and named it; mentions are now read out of the prose. The map itself was written before the checker ran and was missing two cycles — `cycle-idea-to-release` and `cycle-judge-codex` — which the checker found immediately.

### Changed
- **BREAKING (doctrine) — merging moved inside the autonomy envelope.** Floor 2 of `rules/autonomy-envelope.md` said *"a change is proposed, never merged"*, resting on the claim that stopping at the PR *"costs nothing: the work is delivered, the PR is its record, and the queue continues."* **That holds only while somebody is coming.** Unattended, the same pause is a stop: every item passing review parks at an open PR and the queue drains into a pile of branches nobody merges — the failure the envelope names in its own opening, arriving at the last step instead of the first. The floor is now about gates rather than about merging: *no change reaches shared history except through the gates*, and the system may merge a PR whose full chain passed — `/review` `READY_TO_MERGE`, `/code-quality` not `FAIL_HARD`, no BLOCKED report standing. **Three things had to be true first**, and it would be wrong without any: `cycle-brainstorm` exists, so there is a product a person signed for; the gates are scripts with derived verdicts rather than narration; and floor 3 (no gate switched off, no threshold moved) is intact — **it now carries the whole weight it used to share**, because a disabled gate no longer meets a person before shared history. **Branch protection outranks the decision**: where the remote demands a reviewer, the system emits `PR_OPEN_AWAITING_APPROVAL` and takes the next item, and `gh pr merge --admin` is banned by name. The topology is untouched — work is still born on `workspace`, still reaches the trunk only by PR with a semver tag, and `validate-command.sh` still blocks direct commits. Rationale, the three rejected alternatives and the stated cost: `.squad/wiki/decisions/merge-is-inside-the-envelope.md`.
- **`cycle-maintenance`'s ADVANCE kept a safety argument that had expired.** It justified mechanising ADVANCE with *"a session driving this cycle unattended will never emit `RELEASED`… by the time it acts, every judgement it might have needed has been made by a person"* — no longer true once the same loop can merge. Rewritten to the reason that did not change and is narrower: ADVANCE moves an item **only** on an explicit `cycle:phase:end` with `verdict=RELEASED`, a token that exists only downstream of every gate, and it writes through `backlog_status.py` so an illegal transition is refused and the refusal reported. Leaving the old paragraph would have been a contract whose mechanism expired — this kit's signature defect, in the direction where the prose is the stale half. Six contracts that still described the human-approval gate were brought into line (`cycle-release`, `cycle-idea-to-release`, `cycle-rule-schema`'s verdict matrix, `skills/release`, `skills/idea-to-release`, `skills/map.md`); `/review`'s ban on merging **stays** and its reason was corrected — it is separation of duties, not the old doctrine, since a reviewer that could merge on its own verdict would be grading its own decision to proceed.

### Added
- **`cycle-brainstorm` — the one phase a human attends, and the reason the rest may run without one.** Four skills in a cascade: `/brainstorm-vision` (who it is for, the problem, and what it is **NOT**), `/brainstorm-objectives` (`OBJ-N`, each with a metric containing a number and a horizon), `/brainstorm-trd` (`REQ-N`, each citing the objective it serves) and `/brainstorm-pieces` (`PIECE-N` + the gate). Four documents land in `wiki/product/` and the session's discarded ideas land in `records/brainstorms/` — the split `rules/records-location.md` already defines, because the current answer and the reasoning that produced it go stale differently. **Invoked separately on purpose**: one sitting produces its best thinking in the first document and its most tired in the last, and the last is what every later phase reads. `/backlog-init` reads all four as context and still seeds **zero** items — an objective is not a `why_now`, and deriving items from one would manufacture work nobody filed.
- **A product-level alignment gate that refuses to sign itself.** `score_product_alignment.py` scores seventeen structural criteria against a 90% floor — deliberately the same instrument and the same number as the item-level `score_alignment.py`, since defending two thresholds for one purpose is worse than defending one. Two cap tiers, and the distinction is the correction that made the gate real: `hard_caps` (a missing document, a citation whose referent does not exist) are `INVALID` because **no edit to the citing document fixes them**; `floor_caps` (an objective with no number, a requirement serving no objective) force `NEEDS_REVISION` regardless of the percentage, because **a rubric of seventeen dilutes any single one** — an objective with no metric costs one point of thirty-four and still scores 97%, so scoring alone would have let G-B2 read as enforced while passing precisely what it names. **`alignment_judge.py` may not sign here, and the scorer enforces it**: the 2026-09-01 amendment lets a judge sign an ITEM's brief because it reads evidence that exists independently of the brief and can contradict it; a product vision has no such thing — it is what everything else is measured against — so a judge grading it grades the document against itself, which is the failure the sign-off exists to prevent arriving through the door the amendment opened. A `signed-by: judge/…` returns `AWAITING_REVIEW`. Fifteen tests, one of which is that rule.
- **`build_agenda.py` — what stalled for want of a person, assembled before the session starts.** Making the human touchpoint singular has a consequence the pipeline has to honour: everything needing a human now has exactly one place to go, and without something carrying it there it stalls forever while the queue reports itself healthy. It collects halted items, unroutable repos, `blocked_by` lines naming a decision rather than an id, recent kills, never-swept domains — plus two the traceability makes newly computable: **an objective nothing serves** and **shipped work serving no objective**. Those two are the cheap half of the question `rules/current-constraint.md` says it cannot ask, since it does not instrument flow and *"a gate asking whether this touches the constraint, against data that does not exist, would be answered by assertion"*. It reports and never writes — an agenda that could act would be a second writer racing `backlog_status.py`. A missing `BACKLOG.md` renders as a stated note, never as an empty agenda: "nothing is waiting on you" must not be a claim nobody checked. Eleven tests, one of which asserts it leaves every byte on disk unchanged.

### Fixed
- **A cross-repo gate that could not fire outside one ecosystem, under a comment claiming the opposite.** `check_opportunity_completeness.py` detected whether an opportunity's blast radius reached other repositories by matching a name-shape regex, annotated *"deliberately a NAME SHAPE rather than a hardcoded inventory"* so that it would not go stale. **The shape WAS an inventory** — it matched exactly one organisation's naming convention — so in every consumer `cross_repo` was False for every opportunity ever written, `no_adr_on_cross_repo_change` could never fire, and a change reaching three other repos scored identically to a one-line fix in a leaf. It now reads the project's own routing table, which `detect_domains.py` derives FROM DISK and `route_domain.py` already parses; it cannot go stale without the routing gate going stale with it, and that one is exercised on every item. When no table can be read it reports `cross_repo: null` and says so — **never `False`**, which would have stated the change is repo-local, a claim nothing checked, and satisfied the ADR requirement for the same unchecked reason.

### Changed
- **The kit describes any product that adopts it, not one named ecosystem.** The plugin manifest advertised itself as a maintenance squad for one named ecosystem and claimed to ship "8 domain specialists" — a kit that ships **zero**, on purpose, for the reason `agents/README.md` spends a section on. `README.md`, `HOW-TO-USE.md`, four cycle rules and six `SKILL.md` files carried the same name, including the frontmatter `description` of `/backlog-item` and `/backlog-init` — the text Claude Code reads when deciding whether to reach for a skill at all. Every repository name in a fixture, a docstring or an eval was replaced with a generic one (`web-console`, `search-api`, `control-plane`, `contracts`), and the evals fixture directory was renamed with it. **Measurements kept their numbers and lost their subject**: `measured on <a named repo>: 88 items, all unroutable_repo` became `measured on an adopter`, which is the convention `README.md` already used in three places and nowhere else. Anonymising rather than deleting is the only option that does not falsify the record — the fact was observed, and the repository it was observed in is not what makes it evidence. **The external `judge-codex` plugin keeps its real address**, because it is a dependency rather than an identity claim: replacing the org with a placeholder does not make the kit portable, it makes `/plugin marketplace add …` wrong, and a broken install instruction is worse than a generic one. The guard exempts the exact repository slug and nothing else — right-anchored, so a different repo under the same org still fails. That anchoring was not the first attempt: a plain substring elision also passed `…judge-codex-plugin-cc-fork`, which the exemption's own probe caught on its first run. An exemption nobody probes is a door.

### Added
- **The origin-ecosystem guard sweeps the whole versioned tree, not just what the installer copies.** `tests/test_no_origin_ecosystem_leak.py` asserted that a clean install ships an empty routing table — the right place to start, because that is where the consequence was measured (88 items refused by G1), and the wrong place to stop. The name also sat in `README.md`, in the plugin `description`, and in two skill frontmatters, and **none of those are routing failures — they are identity**: a kit telling a consumer it maintains somebody else's product. The sweep now reads `git ls-files` and checks paths as well as contents, so a fixture *directory* carrying the name fails too. Its pattern is anchored — the token must be followed by a hyphen and a lowercase letter, or by a known suffix, or preceded by a vendor prefix, or capitalised and followed by another capital — precisely so that `cap-theorem-specialist` and the `theory of mind` paragraph in `skill-creator` do not match — a case-insensitive search for the token flags both, which is how this kind of guard gets switched off. Three files are exempt **by exact path and with the reason stated**: they are themselves guards, and a guard against a string cannot avoid containing it. The install-time assertions stay underneath the sweep as the narrower case, so they keep failing for their own reason if the broad one is ever relaxed.
- **The squad has names, roles and personalities — four agents, renamed around what a real squad does.** `squad-boss` → **`kairos-product-owner`** (the opportune moment: what work exists and in what order), `squad-runner` → **`daedalus-tech-lead`** (the master builder the myth remembers for what his cleverness cost), `squad-dispatcher` + `squad-lead` → **`hermes-scrum-master`** (roads and crossings: he carries, he does not decide what the message says), and a new **`iris-product-designer`** (the rainbow — the bridge that is SEEN). The temperament is the point of the file, not decoration: Kairos is impatient with vagueness and patient with hunches, Iris refuses a brief that describes a system instead of an experience, Daedalus distrusts his own cleverness first, Hermes never judges the work he is moving. **Dispatcher and lead merged because a real facilitator does both halves** — runs the board and removes the impediment — and neither half requires judging anyone's work; the merge is safe only because of the line both already held, so that line is now stated three ways in the file and every impediment ruling must cite the envelope clause it applied. Each agent is bound to skills that exist: Kairos to `/backlog-item` and `/backlog-review`, Iris to `/plan-alignment` (brief + walkthrough) and `/acceptance`, Daedalus to `/idea-to-release`, Hermes to `/pipeline` and `rules/autonomy-envelope.md`.
- **Developers and QA are the project's own specialists, and the Tech Lead delegates to them mechanically.** They are not shipped, and cannot be: a specialist describes ONE ecosystem's repositories, and shipping a stranger's made an adopter's routing gate refuse all 88 items they had filed with real `file:line` evidence. `daedalus-tech-lead` reaches them through `scripts/route_domain.py` and routes on its exit codes, including the one that tests the role: **exit 3, `BROKEN ROUTE`, is where he must NOT stand in.** A Tech Lead answering for a domain whose invariants nobody wrote asserts facts that were never checked; the item stops and the broken route becomes work for Kairos. What is delegated and what stays his is a table in the file, not a sentiment.

### Fixed
- **`.gitignore` explained why the kit's agents were an exception to a rule that did not exist.** The paragraph describing the exception sat in the file with **nothing ignoring `agents/`** — so any specialist scaffolded there by `scaffold_specialists.py` was tracked, stageable, and one `git add -A` from shipping to every consumer: precisely the failure the paragraph describes as prevented. A contract whose mechanism is missing reads as enforced, which is worse than an absent rule, because nobody goes looking. `agents/*.md` is now ignored with the four excepted by name, and `tests/test_squad_agents.py` checks that a specialist is ignored and every kit agent is not.
- **The kit's agent list lived in three places and only one of them was read.** `tests/kit_agents.py` already derived it from `install.sh`'s copy loop rather than restating it — and `test_clean_install.py` carried a second hardcoded copy in two tests. Both now read the helper. The `.gitignore` exceptions are the third copy and cannot read Python, so a test compares all three against the files on disk, in both directions: an agent the installer copies that does not exist, and an agent on disk nobody installs — the second fails quietly, since its doctrine then applies to this repository alone.

### Fixed
- **`phase_coverage.py` could not start, and twelve tests never noticed.** `main()` read `args.knowledge_base` while the flag it registers is `--records`, so every invocation died with `AttributeError` before printing a line. The suite covered `scan_registry` and `grade` thoroughly and **called `main` zero times**, which is how a script that cannot run once passes its whole test file. Two tests now run the CLI end to end. (deadcode-audit)
- **A rule written into a constant and enforced by no code, four times over.** Each of `FLIP_ALLOWED` (which verdicts may flip a milestone checkbox), `MANDATORY_PER_ITEM` (which phases every backlog item must have), `PRODUCTION_DIR_NAMES` (which directories count as production source) and `TEST_PATTERNS` (which filenames are tests) sat **inside the checker that exists to apply it**, and was read by nobody. A reader greps for the rule, finds it, and concludes it is enforced. All four are now wired, each with tests. Two changed behaviour and say so: `GradedItem.gaps` walked every member of `Phase`, which the ADR above it calls the wrong question for three of the five — code-quality is graded per slice and release per release — so it now walks `MANDATORY_PER_ITEM`; and pillar (a) of `check_wiring.py`, whose first docstring line promises "under src/, lib/, or packages/", grepped from the project root, so a scratch script beside the repo passed it. The narrowing applies only when one of those directories exists, because a repo that keeps source at the root would otherwise report every symbol as unwired. (deadcode-audit)
- **`detect_test_dirs` matched directory NAMES only, so a project with no `tests/` directory reported no tests at all.** `SKILL.md` § stage 5 says the stage locates test directories *and test file patterns*; `TEST_PATTERNS` held ten patterns and nothing read them. A project keeping `test_transfer.py` beside `transfer.py` had every downstream gate calibrated as if it were untested. (deadcode-audit)
- **`plan-improve` rewrote the inside of inline code spans.** The fenced-block guard protected ``` blocks and nothing protected a backticked token mid-sentence, so `` `should` `` — a flag name, a field, a literal the plan is quoting — was rewritten to `` `must` ``, and the whitespace pass collapsed doubled spaces inside spans too. A `_strip_inline_code` / `_restore_inline_code` pair had been written for exactly this and never called; it could not have been wired as written, because `_restore_inline_code` returned the masked line unchanged and never read its `spans` argument, so calling it would have deleted every span it masked. Masking cannot work here at all: the substitutions change the line's length, so the absolute positions a restore step needs are stale by the time it runs. Replaced with `_sub_outside_inline_code`, which splits on the spans and rejoins — no positions, and the substitution count now reports prose changes only, so a change that was not made is no longer counted as made. (deadcode-audit)
- **The `cost if wrong` check ran on every ADR and threw the answer away.** `_has_cost_if_wrong` swept each decision block and `ADRReport.missing_cost_if_wrong` collected the offenders — a field no caller read, not even `run_structural.py`, which unpacks that report field by field. It is now reported under `sub_reports.adr_completeness`. The global-alternatives early return skipped the field entirely, which the source's own comment argues against: a global section can hold the rejected alternatives for a whole plan, but the cost of being wrong belongs to one decision and cannot be shared. (deadcode-audit)
- **`verify_ecosystem.py` reported pytest-benchmark's own output as a broken skill.** It skipped `_`-prefixed directories under `skills/` and not `.`-prefixed ones, so any run that measured left `.benchmarks/` behind and the next check failed with `skill .benchmarks missing SKILL.md`. (deadcode-audit)
- **Two tests shared one name, so one of them had never run.** `tests/test_check_xrefs_root.py` defined `test_a_real_cycle_reference_still_resolves` twice — one covering `CYCLE_NAME_RE`, one covering `_extract_cycle_contract_ref`. Python's second definition replaces the first, so the earlier test was absent from every green run the file ever produced. The second is now `test_a_cycle_contract_reference_still_resolves`; the recovered test passes. Ten unused imports in `tests/` went with it. (deadcode-audit)

### Changed
- **BREAKING — the two score keys in the plan-confidence report are renamed.** `completude_score` → `completeness_score` and `risco_estrutural_score` → `structural_risk_score`, in `score-report.schema.json`, the report template, `SKILL.md` and every test. They were the last Portuguese left in anything the git repository versions, and they were also **inconsistent with the rubric that produces them**: `rubric-v1.md` has always called the two active dimensions `completeness` and `structural_risk`, so the report scored dimensions under names the rubric does not use. Anything outside this repository that parses the score report by key must be updated. Nothing inside it reads those keys — the rename was verified against a repo-wide search, and the schema is `required`-checked by `test_json_schema.py`, so a partial rename cannot pass. The internal `_compute_completude` / `_compute_risco` helpers and their locals follow the same names.

- **Portuguese out of the versioned surface: 53 identifiers and comments.** Forty-six test names across ten files (`test_todos_os_criterios_exercidos_com_evidencia_dao_accepted` → `test_every_criterion_exercised_with_evidence_gives_accepted`), two Portuguese comments in production scripts, four local variables and one JSON-schema `$defs` key in `run_structural.py` / `score-report.schema.json`. Two names are deliberately left in Portuguese — `test_smell_pt_weak_imperative_deveria` and `test_smell_pt_loophole_quando_aplicavel` carry the pt-BR words they exist to detect. **Not changed, and named here rather than done quietly:** `completude_score` and `risco_estrutural_score` are dataclass fields serialised into the score report through `asdict()` and declared in `score-report.schema.json`, so renaming them changes the JSON contract every consumer reads. That is a breaking change and deserves its own decision, not a side effect of a cleanup. (deadcode-audit)

### Removed
- **Twenty-two dead symbols, each read by nothing in the repository.** Four unrequested pytest fixtures (`templates_dir` in three `conftest.py` files, `concepts_dir` in a fourth) — session fixtures that **no test takes as a parameter**, so pytest never ran them, which is setup that looks like it happens; six compiled regexes nobody matched against (`H2_RE` twice, `H3_RE`, `H4_RE`, `TBD_MARKER_RE`, `TARGETS_HEADER_RE`); five fields written at construction and read nowhere (`column`, `type_only`, `total_tasks_referenced`, `parse_errors`, `LanguageInfo.extensions`); the `Edge` dataclass, superseded by `Graph.edges: dict[tuple[str, str], int]`, which carries the same three facts once; `GoDetector._read_go_mod_module`, whose docstring said it was "kept for callers that want a single answer" and whose callers never arrived; the `_has_report` one-liner; an unused `import time`; an unused loop variable; and `EDGE_CASE_KEYWORDS`, the leftover of a keyword sweep this file's own comment records as deliberately deleted after it reported 15 non-cases out of 27. The Python copy of `SETTLED` went with them, and its explanation moved to the JavaScript const in `board.html` that the board actually reads — one fact, and now one source. Three more went with them as cascade (`_resolve_concepts_dir`, `CONCEPTS_DIR`, and `review/`'s `TEMPLATES_DIR`), each of which existed only to feed a deleted fixture. (deadcode-audit)

### Added
- **`check_honesty_gate.py` — the gate on the CLAIM, which was honoured by memory.** Every other gate in this kit asks whether the WORK is done; this one asks whether `production-ready` / `v1.0` is earned, and it is the only one pointed that way. Its rule is a LOCKED contract with four ordered hard caps, named flags, a status vocabulary and a freshness threshold — all mechanizable, **none of it mechanized**: the skill applied it by hand, nothing read its verdicts, no phase invoked it, and a real consumer's whole history holds one artifact. So the gate against an unearned claim was itself the shape it guards against. In an unattended loop that is not weak, it is nothing — nobody remembers, and the claim most likely to be overstated is the one no phase checks. The input already existed: `cycle-acceptance` writes a record per milestone with a computed verdict, and this rule reads those plus a manifest; only the reader was prose. **It refuses to infer** — a missing manifest, a missing rule or an empty evidence directory is `EVIDENCE_INSUFFICIENT` with the flag that says which, never *not applicable*, and the kit itself fails its own gate because it has declared no anchor. The freshness threshold is **read from the rule** rather than frozen in the script, because the rule says it may be lowered freely and a hardcoded number would silently override a project that lowered it. `/release` runs it at the `1.0.0` boundary **and nowhere else** — a patch release makes no claim about maturity, and a gate that fires on ordinary work is one somebody disables. Seventeen tests.
- **The squad has four roles, and now says so.** `squad-lead` and `squad-boss` shipped as agents; `/pipeline` and `/idea-to-release` were skills with nobody named to own the decisions they leave open. Two agents close that: **`squad-dispatcher`** decides which item enters which lane and when — and never whether a stage passed, because a scheduler that could overrule a gate is a way around it rather than through it — and **`squad-runner`** takes one item from idea to a release PR, owning the routing the chain leaves open: which verdict goes where, when the alignment judge signs, and whether a halt stops the item or the queue. The seams are the design: the boss supplies work, the dispatcher allocates it, the runner executes it, the lead is what any of them escalates to. A role that could do two of those could overrule itself. Both are mechanism rather than domain specialists — they describe a decision, not a repository — which is why they may be versioned in `agents/` when a specialist may not. The clean-install gate refused them until its allowlist learned the kit's own agents are four, which is the check working.

- **Every skill now carries a `SOP.md` — the procedure for OPERATING it, beside the contract that executes it.** Measured before writing any of them: **31 of 34 skills already had numbered steps** in their `SKILL.md` — `/implement` has 42 — so copying those into a SOP would have duplicated a procedure into two files that then diverge. What was actually missing is one level up: **only 6 of 34 answered "it returned X, now what"**, and 28 carried no verdict-to-action table at all. That is the gap the SOPs fill, in six sections under the schema the kit's own procedures already use — Purpose, Prerequisites, Steps, Decisions (a verdict table and a decision graph), Escalation, Competencies. Every one carries `sources` pointing at the `SKILL.md` and the cycle rule it was derived from: the `deps-audit` verdict table is the golden rule's six rows with their scores, not a paraphrase, and the escalations are the prohibitions each skill already states. **`check_sop_structure.py` was widened to sweep both roots** rather than leaving them where it could not see: `.squad/wiki/sops/` holds procedures ABOUT the kit and `skills/*/SOP.md` the procedure for operating each skill, and both carry `last_reviewed` with a review interval — thirty-four documents whose review date nothing reads would have been this kit's signature defect at scale. `check_skill_map.py` gained a fourth clause for a skill that ships without one. **38 SOPs, 189 steps, 171 decision branches, 0 structural findings.**

- **`skills/map.md` replaces `skills/README.md`, and a checker keeps it honest.** The old index answered one question — what a skill is called — and had gone stale twice. The CHANGELOG records the second: *"it said 35 skills, there are 36, and the table omitted 7"*, with four of the omitted skills carrying **zero mentions in any entry point** — on disk, passing every validator, unreachable by any discovery path. **On the day it was replaced it claimed 36 skills against 34 on disk and listed 29**, and among the five missing was `shared-understanding`, the alignment gate that is unbreakable for every item coming from `BACKLOG.md`. The map answers three questions per skill instead of one: what comes out the other side, the precondition for reaching for it, and **the misuse that looks reasonable at the time** — a column indexes usually omit. That third column is sourced, not editorial: each entry is lifted from the skill's own `## Anti-patterns`, from a prohibition in its body, or from what its chain position forbids. Twice is a pattern, and the pattern is not carelessness — an index is the one document nothing forces you to open when you add a file, so it drifts by default and reads as complete while it does. `check_skill_map.py` therefore compares the map against the directory in both directions and checks the count it claims, and runs in `verify_ecosystem.py`. Verified by adding a skill and a phantom row to a copy and watching all three clauses fire.

- **`check_phase_numbering.py` — the third phase sweep, and the first to look INSIDE a cycle.** `check_phase_drift.py` asks whether the eight declared pipeline phases ran and `check_phase_emitters.py` asks whether anything records them; neither looks at the order of skills within one cycle, which was written in three places that had no way to disagree out loud. **Measured 2026-08-31: `/deps-audit` was inserted into `cycle-plan` five days earlier and only its own file was renumbered.** `deps-audit` and `plan-confidence` both claimed **phase 3**, while `deps-audit`'s own prose told the reader that `plan-confidence` was phase 4; `plan-improve` claimed the 4 that had become 5; `to-plan`'s chain listed `/edge-case-plan → /plan-confidence` with no `/deps-audit` while `commands-help` listed it; and the frontmatter still said `requires: [edge-case-plan]`, reaching past the skill inserted in front of it. One insertion, four contradicting contracts, shipped to every consumer. The invariant is **convention-agnostic on purpose** — `cycle-discover` is 1-based, `cycle-plan` opens at 0 with a 0.5 inserted between two integers precisely so nothing downstream had to move, and a checker demanding a dense `1..N` would report all of that as broken and be switched off in a week. So: numbers are UNIQUE within a cycle, MONOTONIC over the skills the Chain block orders, and a `requires` never reaches PAST its own predecessor. The third clause is deliberately narrow, because compared naively **five of the six `requires` mismatches in this kit are correct work** — an optional predecessor, an orchestrator that requires sixteen skills, a chain handing off to another cycle. It runs in `verify_ecosystem.py`, and it was verified by reverting each fix in a copy and watching it fail.

- **`check_wiki_migration.py` — the mechanism `test_wiki_fallback.py` had promised by name for four days.** Its docstring stated the limit of the two-root tolerance — *"it is not permanent tolerance for two layouts; `check_wiki_migration.py` reports a project still reading from the old root, so the transition stays visible"* — and **the script did not exist**. The sentence describing what kept the migration visible was the only evidence that nothing did: a contract with no mechanism, in the file whose job was to prevent exactly that. It reports four states per durable leaf, reading `DURABLE_LEAVES` from `sop_format.py` rather than carrying a second copy of the mapping. `SPLIT` — both roots holding documents — fails, because the fallback returns the bundle's copy and the old one becomes unreachable and can never be seen to be stale; `UNMIGRATED` is a visible NOTE rather than a failure, because the fallback exists precisely because the kit cannot run a migration inside a project it does not own, and failing every consumer on day one produces a gate somebody switches off. `verify_ecosystem.py` runs it in every consumer. **First run against a real one found 10 opportunity documents under `records/discoveries/opportunities/` that nothing reading the bundle could reach.** A second defect fell out of wiring it: a passing check's notes were never printed, so `check_xrefs.py not installed — skipping` had never once been seen by anyone.

- **A live board of the cycle.** `board_server.py` serves one page at `127.0.0.1:8765` showing every item and the phase it sits in, re-rendering by itself whenever `BACKLOG.md` or `records/cycle-events.jsonl` changes — the server polls their mtime twice a second and pushes over SSE. Standard library only, the same constraint the rest of the kit works under, because a tool that needs a toolchain gets used once. **It observes and never commands**: there is no control that advances an item, because a board that could write would be a second writer racing `backlog_status.py`, and one writer owning the status line is what makes a transition refusable at all. Bound to localhost deliberately — `BACKLOG.md` carries unreleased plans, kill reasons and sponsor decisions, and the failure mode of binding wider is publishing someone's roadmap to their network. **Position is labelled by its source**: an item placed by an observed `cycle:phase:end` reads as measured, one placed by `status` alone carries a dashed `derived` chip, and the empty-stream case says so in a banner rather than presenting inference as observation — the stream is per-machine and starts empty in every clone, so *derived* is what most viewers see first. `killed` renders grey, never red: the contract calls it a successful outcome, and colouring it as an alarm would misreport honest measurements as failures. Verified against a real registry — 166 items, 1 impeded — and against live edits: moving an item on disk repositioned its card without a refresh, and emitting a phase event moved it again and flipped its label from derived to measured.
- **What ADVANCE may assume about the stream, measured before building it.** Three limits, now written into `cycle-maintenance.md` so they are known rather than discovered by a wrong `shipped`: the stream is **per-machine and per-session by decision** (`.gitignore` carries the reason — one machine's run history does not belong in everyone's diff), so ADVANCE works within a working sequence and finds nothing after a clone; in an installed consumer the stream lands under **`.claude/records/`**, which is not versioned, so an absent stream is never evidence of anything; and there is **no retroactivity** — one registry measured here carries 166 items with 133 shipped and no event file at all, and writing those events now would be inventing a history nobody observed. The consequence is stated too: an item with no `RELEASED` event is not thereby unreleased, it is unknown, and `ITEM_SHIPPED` must not be emitted from a silence.
- **Every declared phase now records that it ran.** Measured on 2026-08-30: four of eight phases emitted nothing, and the two silent ones were the cycle's **only two `required` phases** — `backlog` and `discover`. `release` was silent too, and one real registry with 166 items and 133 of them shipped had no event file at all. The cost is not bookkeeping: `cycle-maintenance.md`'s ADVANCE moves an item to `shipped` when release reports `RELEASED`, and nothing emitted that — so ADVANCE could only have INFERRED the release from files on disk, which is exactly what `cycle_events.py` exists to replace (*a missing file is evidence of nothing in particular*). An ADVANCE built on that inference would write `shipped` on a guess, into the one artefact that outlives the session, and the contract's own anti-pattern names the error: *if nothing was released, nothing shipped*. `backlog`, `discover`, `plan` and `release` now emit at the moment each phase is consummated — after the registry write, after the outcome is decided, after the plan file exists, after the tag and the GitHub release exist. `discover` emits on `ITEM_KILLED` too: a killed item is a **successful** discover, and a stream that records only the outcomes someone likes cannot answer the question it exists for.
- **`check_phase_emitters.py`** — third of the contract-versus-code sweeps, after the hard-gate and orphan-verdict ones. It reads `rules/cycle-phases.txt` and asks whether anything records each phase, so the next phase added cannot be born silent. It is honest about its limit: it proves an emitter exists, not that it fires — an instruction in a `SKILL.md` is weaker than a line of code, and what compensates is `check_phase_drift.py --expect-complete`, which reports a `required` phase that left no event in a given run. The two sweeps are complementary by design.

### Changed
- **Six kit-owned rules moved to `skills/_kit-rules/`, and `rules/` is now the project's alone.** Reviewing `rules/` file by file to place each one produced a placement rule the directory did not have: **the question is not who reads a file, it is who owns it.** `install.sh` does `rm -rf <target>/.claude/skills/` and copies the source over it while snapshotting and preserving `rules/` — so a file the consumer tunes must live in `rules/` or the next update destroys it silently, and a file the KIT owns should be replaced on update, because that is how a fix reaches the projects that installed it. Keeping both in one directory meant a preserved directory carried kit content, and the pointer injected on every turn counted it among the files a reader was told to consider. Moved: `alignment-threshold`, `discover-plan-golden-rule`, `parallelism-shapes`, `prompt-text-is-not-behaviour`, `audit-trail-rotation`, `review-model-routing`. **Three conditions, all required** — the kit owns it, two or more skills read it, and no root script or hook does; fail one and it belongs elsewhere. Staying, each for a measured reason: the twelve `cycle-*.md` because four root checkers glob exactly that pattern and splitting them would end the sweeps that prove the chain coherent; every `*-thresholds.txt`, `*-allowlist.txt` and golden rule marked `PER-PROJECT`, because those are what the installer's backup exists for; `sop-schema`, `reference-provenance`, `auxiliary-skills`, `domain-routing`, whose mechanisms are kit-wide rather than skill-shared; and the eight doctrine files the inject hook names.
- **`check_xrefs` Check 7 now resolves `skills/…` paths, not only `rules/…`.** The move exposed the hole by falling into it: forty-four references pointed at a directory that did not yet exist and the validator reported PASS. Check 3 does resolve arbitrary paths, but only inside a cycle rule's `## Cross-references` section — a path named anywhere else, in any `SKILL.md` or script, was nobody's job. Switched on, it immediately found three dangling references that predated the move, including one to a `README.md` under `skills/` deleted two days earlier and still cited as a live path in a historical quote.
- **Two gates refused the move and were right both times.** `verify_ecosystem` enumerated every directory under `skills/` and demanded a `SKILL.md`, turning a deliberate non-skill into a missing one — it now skips a leading underscore, the marker every other enumerator already respects by finding skills through `SKILL.md`. And `check_semantic_names` rejected the first name outright: *"`_shared` — a name from the bin list says what was left over, not what is here"*, which is the kit's own rule against `utils` / `helpers` / `common` catching its author. Renamed to `_kit-rules`, which names the owner and contrasts exactly with `rules/`.

- **The `cycle-plan` skills now carry the prefix their own family established — a breaking rename.** Five of the seven skills in that cycle did not follow the convention the other two set, and the discover family (six skills), the backlog family and the sop family had all been prefixed from the start. The four renamed:

| Was | Is | Why |
|---|---|---|
| `to-plan` | `plan-write` | the verb was in front of the family |
| `edge-case-plan` | `plan-edge-cases` | the family name was at the END; plural to match `discover-edge-cases` |
| `shared-understanding` | `plan-alignment` | descriptive, and unfindable by family |
| `grill-me` | `plan-grill` | same |

`deps-audit` was deliberately **left alone**: it is phase 3 of `cycle-plan` and is also invoked standalone, and `plan-deps-audit` would misname the second use. **What this breaks, stated:** the slash commands change. Measured in one consumer before deciding, and the occurrences fall into three kinds — the kit's own `rules/` (which travel with the next install and need nothing), the project's dated records under `docs/wiki/` (**47 files, deliberately not rewritten**: they describe what ran under the old name, and rewriting them would falsify the trail), and the project's live documents. That last kind is the real cost: `ROADMAP.md` carried *"awaiting `/to-plan` invocation"* and only the project's owner can update it. **The kit's own history keeps the old names too** — the entries above this one, and every docstring quoting a defect measured before the rename, still say `edge-case-plan`, because a quote rewritten to a name that did not exist yet describes a file nobody ever had. Verified across 82 files: `check_xrefs`, `check_phase_numbering`, `check_skill_map`, `check_sop_structure` and 740 tests all green, including the guard that exists precisely for this — `compose_goal_condition.py` embeds command names as literal strings, and a rename that missed it would have armed a Stop hook pointing at a command that no longer exists.

- **The watchdog writes in the language the session is speaking, instead of the one it was written with.** `squad_lead.py` matched menu options in both languages — matching is reading, and the lead does not choose what the session prints — but composed its own handoff in a fixed language, with an exemption comment on each line saying *"it operates in the operator's language"*. It did not: it operated in one hardcoded language and would have gone on doing so beside an English-speaking session. `detect_language()` reads the screen and the templates are selected per language, reusing `check_english_only.find_markers` rather than carrying a second definition of what Portuguese looks like — the two uses point opposite ways, one refusing what the other mirrors, but the question underneath is the same and a second copy is how they drift. Two distinct markers are required before switching: one word decides nothing, and the cost of switching wrongly is every message after it. English is the default because the repository is English by policy and a screen that printed nothing recognisable has given no reason to change.

### Removed
- **Seven skills cut on utility grounds — 34 to 27, a 20.6% reduction.** Chosen against three tests applied in order, not by picking the lowest scores: *does a mechanism exist, or does the guarantee depend on someone remembering to invoke it* · *has something else come to do it better* · *does the producer still exist*.

| Cut | Evidence |
|---|---|
| `trajectory-review` | its own rule said **"None of the six caps below is computed"**. Zero scripts, zero readers of its output, never ran, opt-in. 854 lines of contract with nothing executing it — the skill and its three rules went together |
| `session-goal` | 1612 lines. Its description says *"Use AFTER the milestones exist in a **hand-authored** ROADMAP.md"*; the kit had already retired all three `roadmap-*` skills, so the producer was a person typing. The measured consumer holds 853 lines of ROADMAP with **0 open milestones** against 172 backlog items |
| `commands-help` | superseded by `skills/map.md`, which answers three questions per skill instead of one and is machine-checked. Its two-registry table and its flows were folded into the map first |
| `grill-me` / `plan-grill` | **one grill in a consumer's entire history**. Phase 0 was OPTIONAL; `plan-alignment` interrogates as its first act and is unbreakable for backlog items, so the interview already happens where the work is |
| `sop-author`, `sop-run`, `sop-review` | **zero run records ever written**, and 34 SOPs were authored on 2026-08-31 without using `sop-author`. `check_sop_structure.py` already reports `sop_stale` with the overdue day count — the audit skill's headline job was mechanised before it was cut. The two validators stay; the three prose layers around them do not |

**What the cut cost, stated rather than absorbed.** Removing `session-goal` removed a real check: `cycle-acceptance`'s *no flip without a green verdict* had an after-the-fact enforcement, and now has none — the flip script has never read the verdict itself. That gate is now `_(not mechanized)_` and says why. Two more consequences the gates caught rather than a human: `check_gate_mechanisms.py` refused three `cycle-acceptance` gates that named a script the cut had deleted — **including inside the exemption note**, which is correct, since a gate naming a mechanism that does not exist is fabricated however it is framed — and `check_orphan_verdicts.py` found `ITEM_UNROUTABLE` orphaned, because the retired skill was the only place that named it. **`honesty-gate` was kept deliberately** despite meeting every cut criterion: zero scripts, zero readers, one artifact. It enforces a real principle and is now the named debt at the top of the next list. Found while sweeping: an old blanket rename had turned the WORD *analysis* into *trajectory-review* across sixteen places — "Deep file dependency trajectory-review", "AST trajectory-review", `trajectory-review.json` — the same defect class as the rename, pre-existing, now repaired.

- **Seven skills shipped to every consumer that no phase of any cycle used.** Found by asking who cites each one rather than by taste: the presentation trio (`slide-deck`, `marp-slide`, `excalidraw`) was referenced only by the installer, the help index and by each other, and `frontend-design` plus the three domain specialists (`cap-theorem-specialist`, `backpressure-specialist`, `resilience-specialist`) not even by each other. None appears in a single `cycle-*.md`. The three specialists are the interesting deletion: a fixed specialist asserts domain knowledge about repositories it has never read, which is what `scaffold_specialists.py` replaces by writing a project's specialists from that project's own disk — and a specialist that describes nobody's code is worse than an absent one, because it will be believed. **`ast-grep` stays** though the same list calls it auxiliary: `code-quality/SKILL.md` and `review/SKILL.md` depend on it, which makes it a tool two phases reach for rather than a loose part. `AUXILIARY_SKILLS` drops 19 → 12, the skill-count assertion 41 → 34, and the two `commands-help` sections left holding nothing are gone.

### Fixed
- **The rules pointer injected on every turn said "54 files — read before architectural decisions".** That is not a pointer, it is a wall: a model told to read fifty-four files before a decision reads none of them, and the injection cost was paid every single turn for an instruction nobody could follow. It now names the eight stack-agnostic doctrine files individually — `architecture`, `testing`, `error-handling`, `parsimony-ladder`, `git-safety`, `records-location`, `autonomy-envelope`, `loop-engine-convention` — and says the rest are phase contracts read when that phase runs. A name is followable; a count is not. Reviewing `rules/` file by file to place them also established, by measurement, **why almost nothing may move out of it** — and that the obvious rearrangement would have broken every consumer. `install.sh` does `rm -rf <target>/.claude/skills/` and copies the source over it, while snapshotting and preserving `rules/`. So a threshold, an allowlist or a live target pushed into the skill that reads it would be **destroyed on the next update, silently** — which is the failure the installer's own backup exists for, measured before it: a `typescript | ENABLED` line and a live-target block both gone after one re-run, with no message. The question that places a file is therefore **not who reads it but who owns it**, and `rules/README.md` now carries that map. The cycle contracts stay for a second measured reason: four root checkers glob exactly `rules/cycle-*.md`, and splitting them across skills would end the sweeps that prove the chain coherent.
- **One configuration, three copies, and the third was read by nothing.** `code-quality`'s enabled-languages list existed at 80 lines in `rules/`, 83 in `rules/templates/` (the installer's input, which it deletes from the consumer after copying) and **37 inside the skill's `defaults/`** — already drifted. A test asserted the third pair's presence and called them *"fallback copies"*; `run_code_quality.py` reads the rule and, when it is missing, prints an error and exits 2. **Nothing fell back.** Deleted, and the test inverted to assert their absence, with the reason: falling back to a stale list would audit a subset silently, which is the *"it looked at something, just not at that"* defect this very gate exists to catch. `check_xrefs` on a fresh install then caught the dead reference left in `cycle-code-quality.md` — and caught it a second time when the sentence explaining the removal named the path in backticks.
- **The parsimony ladder lives in two places and neither said so.** The six rungs are inlined in `userpromptsubmit-inject.sh` and defined in `rules/parsimony-ladder.md`. The copy is necessary rather than lazy — a hook that supplies context cannot ask the model to read a file first, because the injection *is* the context — so both sides now name the rule as the source and say to change it first. Verified in agreement on 2026-09-01, which is the only time anyone had checked.

- **The instrument that measures whether a skill triggers could only ever miss.** Prompted by the *Skills-Coach* paper, which optimises a skill's prose and grades it with keyword presence — and, in its virtual mode, with *"deterministic random numbers generated from a hash of the skill's content"*. The kit already refuses that shape in `rules/prompt-text-is-not-behaviour.md`, and already ships the honest alternative: `run_eval.py` spawns a real `claude -p`, gives it a raw query, and watches the stream for whether the model **reaches for the skill**. It also has what the paper lacks — negative controls (`should_trigger: false`, passing when the rate stays BELOW threshold), repeated sampling, and held-out selection in `run_loop.py`. **It shipped with zero tests, and carried four instances of one defect**: each decided the whole turn from its first observation. Any tool that was not `Skill`/`Read` ended it as a miss; a first block naming some OTHER skill ended it; the first `message_stop` ended it, and a turn routinely has five; and the tail the last read appended was dropped unparsed when the process exited. Every one fails in the same direction — it can call a trigger a miss, never a miss a trigger, so the rate is a lower bound presented as a measurement. Measured against `deps-audit`'s real description: the model ran `Bash` three times to orient itself and invoked `Skill` correctly at position four; that run scored as *did not trigger*. Paired over the same five streams, old logic **4/5**, new **5/5**, the divergence exactly the run whose first tool was `Bash`. The detection is now a `TriggerDetector` fold — extracted so it can be tested at all — where **`False` comes only from the `result` event and from nowhere else**. Twelve tests, six of which fail against the old logic. First honest end-to-end run afterwards: 3/5 with varied rates instead of a uniform zero, and `deps-audit`'s description not reaching for itself on *"are any of the packages we depend on out of date or insecure?"* — recorded as a hypothesis, because at two runs per query the resolution is 0, 0.5 or 1. **`skill-creator` is vendored and now carries a local fix**, so a blind re-sync reverts it silently; `skills/map.md` says so in the row.

- **A gate declared unmechanised had been mechanised for three weeks when the claim was written.** `cycle-discover.md`'s G-K — *kill is reasoned* — carried `_(not mechanized: measured 2026-08-27, no script reads `kill_reason`; ... nothing confronts them)_`. The chronology, from `git log -S`: **2026-08-05**, `check_backlog_structure.py` began emitting `killed_without_reason` as MAJOR, naming *gate G-K* in its own message; **2026-08-27**, the annotation was written asserting a measurement that had missed it; **2026-08-30**, `backlog_status.py` added a point-of-action refusal — `killing an item requires --kill-reason (gate G-K)` — which also names it. Two mechanisms, both citing the gate by id, and the contract said there were none. This is the inverse of the defect this kit usually finds: not a contract with no mechanism, but a mechanism the contract refuses to admit — and it is worse in one specific way, because a reader who believes the gate is honour-based either works around a gate that will refuse them, or builds a second one. The annotation now states what is true on both halves: presence is enforced twice, and the **substance** of the reason is what nothing checks — a `kill_reason` of "n/a" satisfies both layers. Verified by calling `advance()` with no reason and watching it raise. The other annotations from the same 2026-08-27 sweep were re-read and are sound: they say *judgement, by decision*, which is a design choice rather than a measurement, and a design choice cannot be falsified by a grep.

- **`check_xrefs.py` Check 10 — a citation names a SECTION, and nothing checked whether the section existed.** Checks 3 and 7 answer *does the file exist*; a reader is not sent to a file, they are sent to a section of one. Measured by hand on 2026-08-31: **14 dead anchors across 10 files**, in three classes. **Renamed** — `architecture.md § Module hygiene` in four separate files, against a heading that has read `§ 3 — Module cohesion` for as long as git remembers; same shape for `testing.md § BDD`, `cycle-review.md § Trigger conditions` and `§ Stop conditions`. **Misquoted** — `§ What it requires` for `§ 2 — What the rule requires`. **Never written** — and this is the class worth the check: `/implement`, `/discover-execute` and `/plan-improve` each opened their halt-loop step with *"Read `loop-engine-convention.md § How to invoke ralph-loop:ralph-loop safely` BEFORE this step"*, **and that section did not exist**. Each then restated the shell-evaluation fact in its own words, so one piece of knowledge lived in three copies while its named home was empty; the section is now written and the three are summaries of it. Two more of the same family: `implementation-prompt.md` pointed at a `cycle-implement.md § Model routing` contract that exists nowhere, and `cycle-maintenance.md` sent readers to `cycle-backlog.md § Step 2` for a `supersedes:` field that is specified in `backlog-item/SKILL.md`. A citation that survives the rename of what it points at is worse than a missing one: the reader goes looking, finds a document that plainly exists, and concludes the section was deleted on purpose. The negative cases are pinned as hard as the positive ones, because two of the three false-positive classes came from the by-hand sweep itself — a section name wrapped across two lines, and a basename resolving to two files. **Ambiguity is answered with silence rather than a guess**: a finding about the wrong document reads exactly like a real one.
- **A limitation promised a fifth corner the cycle had already made an anti-pattern.** Two files — `discover-plan-confidence/SKILL.md` and its rubric template — carried a Known Limitation announcing a `prior_art` corner "until M2.1 ships", asking human reviewers to cover missing prior-art content meanwhile, and naming `check_research_coverage.py`, renamed to `check_corner_coverage.py` when the corners stopped being about other projects and started being about ours. `cycle-discover.md § The four corners` declares four, and the same rule now lists prior art among the anti-patterns — *"Project X does it this way is not a measurement of our system... it cannot fill the Evidence corner."* The documentation was instructing reviewers to enforce the opposite of the contract.
- **`PORTABLE.md` told the reader to install a file that has never existed.** Step 3 of the portable install ran `cp /path/to/source/scripts/check-plan-confidence.sh scripts/` — `git log --all` finds no such file at any commit — and a compatibility table two screens down rated it "✅ Fully" portable, asserting a behaviour (*"auto-finds `.claude/` from script location"*) nobody could have observed. The gate it describes needs no wrapper: `run_structural.py` already exits 0/1/2/3 for exactly this.

- **A rule asserted four times that the kit lacked something it had built.** `rules/parallelism-shapes.md` was titled *"the one this kit does not have"*, marked `❌ Pipeline | Nowhere` in its table, carried a section explaining why building it would be premature, and recorded that only one of the two kits shipped `capture_tree_state`. Measured: `pipeline_orchestrator.py` is 314 lines with 40 tests and implements **exactly the three requirements that document itself listed** — `Item.worktree` with a live/released set, `take_batch()` reading a per-stage `CONSUMPTION` mode, and `send_back(slug, to, commit)` whose signature carries the commit rather than a task — and both kits ship the detector. This is the same class the CHANGELOG already records for five `/review` templates that still said *"the tree you are reading is SHARED"* after isolation landed: an instruction describing a world the code left behind is worse than none, because it buys precautions against a hazard that is gone. Rewritten so the distinction survives and the false claims do not — the three requirements are now recorded as what became the specification, which is the argument for having written the gap down before closing it.
- **The kit was English by policy in 21 files that were not.** `check_english_only.py` is deliberately precision-over-recall and says so — a word-list matcher that "finds prose and misses phrases built from words the list does not carry" — and it reported clean over comments, docstrings, assertion messages, test fixtures and one `CHANGELOG` entry written in Portuguese, including several paragraphs that switch language mid-sentence. Translated, with the genuinely exempt cases left and marked: the watchdog's own matcher literals, screens captured verbatim from a live session, and the gate's own examples of what it misses. A consumer's agents read these files as instructions, and a contract written half in one language is one whose exact wording nobody can grep for.

- **`blocked` was serialized as a list where the contract says boolean.** `a and b and (c or d)` yields its last truthy operand, so the board's JSON carried the blocker array in a field documented as a flag. The page happened to work — a non-empty array is truthy in JavaScript — which is the class of accident that survives until someone reads the JSON and believes the type.
- **`BACKLOG_BLOCKED` claimed a wall over an item that was ahead, not held back.** Found by using the tool rather than testing it: an item that had reached `planned`, and whose blocker had **shipped**, came back `BACKLOG_BLOCKED`. Nothing was blocking it — it was ready for `/idea-to-release`. One verdict was carrying two states, *held back by an impediment* and *already past this gate*, and only the first is a wall; a reader, or the ADVANCE that will read this, would have concluded the opposite of the truth. `--check` now answers with the contract's own verdicts — `ITEM_IN_FLIGHT` for `planned`, `ITEM_SHIPPED`, `ITEM_KILLED` — while a genuine impediment keeps the name. A status outside the declared set is still `BACKLOG_BLOCKED` rather than guessed into one of them: an unknown status means the contract moved, and inventing a reading for it is how a gate starts lying quietly. **Three verdicts left the declared-debt list by gaining a real emitter**, not by exemption — the maintenance debt is now `ITEM_VERIFIED_LOCAL` and `ITEM_BLOCKED` alone, and the sweep reports 40 emitted by code against 3 exempt.
- **The event CLI wrote wherever it was pointed, while every Python caller normalised first.** `consolidate_findings.py` and its three siblings call `project_root_for(...)` before emitting; `cycle_events.py`'s own CLI passed `--project-root` straight through. Measured on 2026-08-31 in a replica of an installed consumer: emitting from `api/internal` created a **second stream** at `api/internal/.claude/records/cycle-events.jsonl`, invisible to anything reading the project root. That is worse than a lost event — `cycle-maintenance.md`'s ADVANCE reads the stream to learn a phase ran, and a phase whose event landed in an orphan file reads exactly like a phase that was skipped, which is the one distinction the module exists to make. The four `SKILL.md` instructions added the day before all use this CLI, from wherever the agent happens to be standing. The regression guard was verified to fail without the fix.
- **The maintenance chain has an executor.** `rules/cycle-maintenance.md § Chain` specified the whole loop — read `BACKLOG.md`, filter `status in {raw, triaged}`, rank triaged before raw and then oldest first, pick the first — with a section of its own justifying both ranking rules. **Nothing implemented it.** The order was a paragraph an agent was asked to remember while scrolling a file, and the only runner over backlog items carried a literal list of three ids. `select_backlog_item.py` makes it a computation: `--check B-NNN` answers the narrow question with the same code that picks, so the gate and the selector cannot disagree, and `--queue N` returns the head of the order for a caller filling more than one lane. Two things it does that the written chain did not say, because the chain predates them: blocked items are dropped (an item waiting on another reads `triaged` on disk and cannot be worked on, so eligibility uses the DERIVED state), and `BACKLOG_BLOCKED` is distinguished from `BACKLOG_EMPTY` — when items remain and every one is blocked, the sweep that `BACKLOG_EMPTY` prescribes would add items beside a wall instead of clearing it. Verified against a real registry: the runner's literal list started at `B-001`, which is blocked by a sponsor decision; the computed queue starts at `B-022`. **Age is read from the id**, not a date: ids are monotonic and never reused, and 52 of 166 items in that registry carry a registration date (31%), so ordering by the date would leave two thirds of the backlog with no key and would be a second source for a fact the id already carries.
- **A verdict nothing can emit is now a failing check.** `check_orphan_verdicts.py` is the complement of `check_gate_mechanisms.py`: that sweep reads `## Hard gates` and asks *does this line say what enforces it?*, this one reads `## Verdicts` and asks *can anything actually emit this?* Measured across the cycle rules: **48 verdicts declared, 15 in no `.py` or `.js`**; eight of those are legitimately emitted by an agent following a skill, leaving **6 reachable from nowhere at all** — four of them `cycle-maintenance.md`'s, which was invisible even to the gate sweep because it has no `## Hard gates` section. The prompt for writing it was having just fixed the same defect twice by hand: `NEEDS_SPLIT`, in a verdict table and in zero code paths, and `planned`, in a contract and in zero items across every install. Both were found by a person noticing; neither was findable by any check. Exemptions are allowed and must carry a reason — `_(emitted externally: <reason>)_` — so the kit now reports 5 exempt and 0 orphaned: the judge-codex verdicts because that plugin ships from another repository, and the four maintenance verdicts as **declared debt**, naming that SELECT is mechanized and the phases after it are not.
- **Items can now say what stops them, and the registry keeps the links.** Work in progress is the most common source of new items: an item reaches IMPLEMENT and only there turns out to need something else. Until now the registry had no way to express that — the discovery either grew the current item past what was aligned on, or lived in a session that ended. Items now carry `blocked_by`, `scripts/backlog_status.py` writes and refuses the edges, `check_backlog_structure.py` gates them (G6 unresolved edge, G7 cycle), and `backlog_index.py` renders both directions. **`blocked` is a derived state, not a sixth status**, and that is the whole design: the stage stays where it was, because the stage is the fact needed to resume — an item that stalls at `planned` must come back at `planned`, and a status that overwrote it would have destroyed the only copy. Deriving it also means it cannot rot: an item whose blockers all shipped stops being blocked at that instant, with nobody remembering to clear a flag. **The reverse edge is never written** — `blocks` is computed by the index, because storing both directions stores one fact twice and the copies diverge the first time someone edits in a hurry. Cycle detection came back to `check_backlog_structure.py` after being dropped when the file was written: it was dropped because backlog items were independent, and `blocked_by` is exactly what stopped them being independent.
- **`NEEDS_SPLIT` reaches a caller.** It was in `shared-understanding/SKILL.md`'s verdict table and in no code path, so an item describing two subsystems came out as a generic `BLOCKED` — sending the reviewer to close gaps that no rewrite can close, because the gaps are a consequence of two items sharing one brief. A reviewer now marks the brief `<!-- verdict: NEEDS_SPLIT: reason -->`; `score_alignment.py` transports it and `check_alignment_gate.py` caps the plan on it. Transported, never inferred: deciding that a description spans independent subsystems is judgement, left unmechanized at intake (gate G3) for the same reason.
- **The pipeline writes what it learned back to disk.** `pipeline_orchestrator.py` had no mapping from its item state to `BACKLOG.md`'s `status:` field at all, so an item parked in a lane still read `triaged` on disk — and the disk is the only copy that outlives the session. Completing a stage now earns a `StatusWrite`, `Pipeline.block()` frees the lane and records the impediment, a send-back demotes the status it invalidated, and `apply_writes()` applies them. Refusals are returned rather than raised, so one illegal transition does not abort the others: a run that learns three things and can record two should record two.
- **The pipeline's agents are written to disk before they run, the way `/review` has always done it.** The first pipeline run used ephemeral agents: each prompt lived in a workflow script, went to the harness, and left nothing behind. Six agents ran over a real backlog, **three of them found defects in this kit** — one located an id collision in `score_alignment.py` with line numbers and the real-versus-reported coverage figures — and **not one of their prompts is recoverable**. The transcript records what an agent said; only a generated file records what it was asked. `skills/pipeline/scripts/spawn_stages.py` now instantiates `templates/stage-*.md` per item into a versioned directory, and the workflow reads those files instead of carrying prose. **The read-only posture moved from prose into the tool list**, which is the part that matters: the first run asked the agents in a paragraph not to write, and the harness does not read paragraphs. DISCOVER and ALIGN ship with no `Write`, `Edit` or `NotebookEdit`, and a test asserts it. **Three defects surfaced while wiring it in, each the same shape the week has been about.** The `/review` templates still told reviewers *"the tree you are reading is SHARED"* — true until `isolation="worktree"` landed hours earlier, and an instruction describing a world the code left behind is worse than none, because it buys precautions against a hazard that is gone; five templates corrected. `check_xrefs`'s chain parser accepted kebab-case skills by shape but single-word ones only from a hardcoded list (`to-plan|implement|review|release|…`), so a new single-word skill stayed invisible to the orphan check until somebody edited a regex — it now asks the filesystem, which cannot go stale. And widening that pattern to accept `/` as a terminator immediately made `records/maintenance-runs/` parse as a skill reference; caught by the run, reverted, and pinned by a test, because a checker that cries wolf in a consumer is one somebody disables.
- **The pipeline shape this kit named and did not have — built, after an alignment judge refused the first design.** `scripts/pipeline_orchestrator.py` schedules many backlog items through the seven-stage cycle concurrently, one stage each, with a worktree per lane. It decides WHICH item enters WHICH stage and WHEN, and never whether a stage passed: the phases keep their gates, verdicts and thresholds, because a scheduler that could overrule one would be a way around it rather than through it. **The gate that looked like the obstacle turned out to be the argument.** `cycle-idea-to-release` halts at `AWAITING_REVIEW` because the alignment gate needs a human, and today that halt stops everything; in a pipeline it stops one item while the rest move, and the operator's review becomes a batch rather than an interruption. **The alignment judge REFUSED the first draft, and its four findings are why this entry exists.** It verified claims against the repository rather than trusting the brief: 22 `status: triaged` in the consumer (confirmed), the B-025 false BLOCKER (confirmed at `consolidate_findings.py:439-451`), and then three defects — the chain was drawn with FIVE stages when `cycle-idea-to-release` declares SEVEN (CODE-QUALITY and ACCEPTANCE missing, so the design scheduled work that never runs); backward propagation had no FR, flow or AC at all, **in a brief resting on a rule that names it as one of three things the shape requires**; and the concurrency number was asserted rather than derived — `8` lanes with one in REVIEW needs 8+7=15 agents against the `min(16, cpus-2)`=10 cap the brief itself cited, so it deadlocked on its own limit. The derived figure is **3 lanes, at most 1 in REVIEW**. It also caught a substitution nobody had declared: `cycle-idea-to-release.md:80` halts and asks the HUMAN after one retry, and the draft silently put a judge there. **On its fourth question the judge refused to rule**, saying it was the judge being asked to authorize judges — which is the correct answer to that question and the reason it went to the operator. **Signature provenance came with it.** `ALIGNED` no longer means one thing, so a signature now carries its author: `human/…` or `judge/…`, reported by the scorer, and a mixed set reports the WEAKEST signer rather than the majority. Naming the signer must not cost the distinction it protects — an early cut treated any marker other than the bare word `human` as an agent, which would have downgraded a named person's own signature.
- **Six reviewers shared one working tree, and the fix had been written down and not taken.** The comment above `capture_tree_state` records the B-025 run in full: six agents concurrently against ONE tree, `usage-panel.tsx` found carrying a mutation marker mid-review, probe files at the repo root, and the architecture reviewer filing `reportGuardFailure has zero production call sites` **against a symbol called at `usage-panel.tsx:115` and `:147`** — a false BLOCKER, from contamination. Three of six reviewers happened to notice the tree was dirty and re-derived their citations, and the comment names that precisely: *correctness depended on noticing is the defect*. It then ends with the answer — *"Isolation (a worktree per agent) is the fix. This is the DETECTOR beside it"* — and the spawn instruction was left asking for no isolation at all. `/review` now passes `isolation="worktree"`. The detector stays: isolation that silently stops working looks exactly like isolation that works, so the detector is what proves the fix is still in force, not what the fix replaces.
- **The kit had a word for one shape of parallelism and none for the other.** From [`unclebob/swarm-forge`](https://github.com/unclebob/swarm-forge), whose point is parallel multi-agent development: **fan-out** puts N agents on the SAME work from different angles (this kit's `/review`, `discover-plan-confidence`, `cycle-judge-codex`), while **pipeline** puts N agents on DIFFERENT work at different stages — its `six-pack` runs `specifier → coder → cleaner → architect → hardender → QA` simultaneously, each in its own worktree, so while the coder implements slice 3 the cleaner is on slice 2 and the architect on slice 1. They are orthogonal, and a pipeline stage can itself fan out. **This kit has fan-out and no pipeline:** `cycle-idea-to-release` chains its five phases one item at a time, and a consumer with 22 triaged items processes them strictly in sequence with every phase idle whenever it is not the current one. `rules/parallelism-shapes.md` records the distinction and the three things the pipeline shape needs — isolation rather than detection, queues with a per-role `task`/`batch` consumption mode, and backward propagation that carries a commit rather than a task. It is written rather than built on purpose: a pipeline is a scheduler, a queue, a worktree lifecycle and a merge protocol, and shipping the words alone would be the contract-with-no-mechanism shape this kit names elsewhere, inverted. What was missing was the WORD — a team without it cannot notice the absence.
- **Measured how many of our own tests pin the wording of shipped prose, and mechanised the one that mattered.** Prompted by [`unclebob/swarm-forge`](https://github.com/unclebob/swarm-forge), whose entire `AGENTS.md` is four lines: *"Do not test the text of prompts with an automated unit or acceptance test… Prompt wording is not production behavior to pin with `str/includes?`."* This kit reached the same position on 2026-08-29 by paying for it — `test_layout.py` pinned an exemption by grepping for a string literal and broke when that literal became a table resolving a THIRD layout, failing while the behaviour it protects got strictly better. **The measurement: 197 substring asserts over prose-reading tests, of which 2 actually pinned wording.** The gap is the whole story — almost every one is an assert over program OUTPUT (`result.stdout`, a generated report, a parsed settings dict), which is behaviour and legitimate. `scripts/check_prose_tests.py` traces the target of each `in` back to text read from a shipped prose file in the same function, and is deliberately precise rather than exhaustive, with its blind spots named in the docstring. **Of the two, one was schema and one was the real thing.** `"argument-hint" in frontmatter` asserts a KEY, which is structure and survives any rewrite — exempted on the line with the reason. `"delete" in SKILL.md` was the real case, and the deeper reading is what makes it worth the entry: **a grep over a contract is a SYMPTOM that the guarantee exists only as prose.** What it defended is real — `consolidate_findings.py` scores from OPEN findings, so deleting a finding or lowering a BLOCKER to MEDIUM both pass, and only the contract warned against it. A synonym defeats the grep and an unrelated occurrence satisfies it. So the guarantee moved: `check_finding_continuity.py` compares two consolidated reports for one slug and reports findings that were open and are now neither present nor CLOSED, plus findings whose severity dropped. It refuses to rule on intent — an honest re-scope and a quiet deletion look identical on disk — and names that in every report.
- **Six section names for one concept became `## Does Not Own`.** Also from swarm-forge, where every role prompt carries one and the boundary is stated **in the prompt of whoever could cross it**: its `coder` is told, in the coder's own prompt, to ignore the specifier's QA suite and not to run mutation, CRAP or DRY checks, because those belong to three other roles. Measured here: 13 of 40 skills declared a boundary, under six different headings — a DRY violation this kit names for knowledge and had not applied to its own headings. The 27 skills without one are **recorded as they are, not filled in**: fabricating 27 boundaries to make a count look complete is the evidence theatre this kit refuses elsewhere. `skill-creator` now carries the contract for new skills.
- **The 90% alignment threshold was PROSE in three documents, and nothing could enforce it.** `rules/alignment-threshold.md` said an item below the threshold is not built; `cycle-implement.md` repeated it as a pre-condition; `cycle-plan.md` listed it as a phase contract. A grep across the kit for anything that READ `records/alignment/` returned **nothing**. Three documents said the item must not be built and no code could stop it — the same defect measured five times in one week under five names: a mechanism with no contract, a contract with no mechanism, a hook declared in one of two files, a rule implemented on one of two branches, a capability nobody could find. **`check_alignment_gate.py` now enforces it on two layers.** Inside `run_structural.py` it hard-caps an unaligned plan at 49, forcing `INVALID`, and `cycle-plan` needs ≥ 70 to enter `/implement`; the same check re-runs at the end of `run_validation.py` as the last line for whoever reached `/implement` without passing through `plan-confidence`. Four states, each proved end to end: item cited with no brief → `MISSING`, hard cap; brief below 90% → `BLOCKED`; brief at 100% with nobody signed off → `AWAITING_REVIEW`, still capped, which is where the reviewer sign-off stops being decoration; all boxes ticked → `ALIGNED`, clean. **Unlike every other cap in `plan-confidence` there is no `--skip` and no dismissing ADR** — an escape hatch on this one is an escape hatch on the reason the gate exists. **The orchestrator now halts by design.** `/idea-to-release` went DISCOVER → PLAN with no alignment step, so with the gate live every autonomous run over a backlog item would have died at `INVALID`. It stops at `AWAITING_REVIEW` and asks for the review instead — this is the one gate in that chain the pipeline **cannot** satisfy, because `ALIGNED` requires a human tick and the agent may never tick a box. An autonomous chain that could align an item with itself would be the failure the gate exists to prevent. **The remaining bypass is stated rather than hidden:** a plan citing no `B-NNN`, with no brief for its slug, may be a legitimate hotfix or an item that skipped intake precisely to skip this gate, and no check separates those. That case takes a soft floor of 89 and a `WARN`, both naming the reason — it stays out of `SHIPPABLE` and lands in front of a human, which is where the same kind of judgement already lives. Closing it mechanically would refuse every one-line hotfix, and a gate that fires on ordinary work is a gate somebody disables.
- **The walkthrough is generated now, and nothing is placed by hand.** Every defect the drawing shipped was a LAYOUT defect, and every one was patched by hand before the next appeared: nodes clustered in a corner with two thirds of the canvas empty; three steps between one pair drawing a single arc with their labels 16px apart; a lane offset that fixed that and then cancelled itself out, because the direction term multiplied the normal's own flip by a second one; a proportional lane gap that shrank exactly where nodes were most crowded; an edge crossing straight through a node with its label on that node's title. **None of them were testable while a person chose the coordinates** — there is no invariant to violate, only an appearance to dislike, in the one case you happened to open. `scripts/build_walkthrough.py` takes a YAML spec and Graphviz owns the geometry, so the invariants exist and `tests/test_build_walkthrough.py` asserts them: every step gets a route, every route ends inside the box it claims, parallel steps get separate curves, the canvas stays wider than square, and the generated page reaches no external host. **Two passes, and the reason for each is a measurement.** `dot` places the nodes once from one edge per PAIR — a reader sees one flow at a time, and reserving rank space for all nineteen steps sized the gate example at 867x934 (aspect 0.93, a page that scrolls with type shrunk to fit) where one per pair gave 783x210 (aspect 3.73). Then `neato -n2` routes each flow separately over pinned positions, which is what stopped an edge crossing a node and what supplies `lp`, the label position Graphviz computes after reserving room for it — the midpoint of a curve, which the hand-drawn version used everywhere, is not a free spot but a spot nobody checked. **`-n2` has a trap that cost a debugging pass:** it does not move pinned nodes but it does renormalise the bounding box to what that flow's edges occupy, so every flow returns in its own translated frame — `agent` pinned at y=388.7 came back at y=220.5, a 168pt shift that detached every edge from every box while each flow still looked internally consistent. **The animation is three coordinated layers, not a moving dot.** The edge draws itself (`stroke-dashoffset` from its own `getTotalLength()`, GPU-composited, and the drawing IS the duration so nothing is synchronised by hand); a packet rides the identical path via CSS `offset-path`, which avoids `animateMotion`'s trap of translating from the element's current position; and the destination pulses at 82% of the travel time, so arrival is an event rather than a state that was always true. Measured in Chrome across one step: dashoffset 233 → 0, offset-distance 0% → 100%, halo delayed 968ms. `prefers-reduced-motion` pins every animated property to its FINISHED state — disabling the animation alone leaves a blank stage, which for that reader is worse than a static diagram. **Three reference files ship with it** (`references/layout-engines.md`, `animation.md`, `spec-format.md`) carrying why Graphviz rather than ELK, Mermaid or D2; both passes and both traps; the three animation layers; and the spec grammar. Across the four flows of the worked example, labels overlapping a node box: 0. Closest two labels: 21px, from 10px.
- **Two hops between the same pair of nodes now get their own lanes.** Drawing the gate's own flow surfaced it: `Agent → score_alignment` runs three times in one walkthrough and all three landed on the same arc, with the numbers and labels stacked 16px apart. Two defects behind it, both found in the browser rather than reasoned about. An explicit direction term multiplied the normal's own flip by a second one and cancelled it, so the return trip bent the same way as the outbound. And the lane gap was a multiplier on the base bow, which shrinks with distance — exactly where nodes are already crowded — so `Reviewer → Alignment brief`, walked twice by the recovery flow, drew its two lanes 10px apart. The gap is absolute now. Worst label separation across the four flows went 10px → 22px.
- **`skills/shared-understanding/examples/alignment-gate-walkthrough.html` — the skill applied to itself.** Four scenario classes for one gate: `ALIGNED` (primary), `AWAITING_REVIEW` (alternate), `BLOCKED` (exception) and the reviewer refusing a box (recovery). It exists because the contract asks for four classes and shipped with no example of what four look like, and because the step a reader gets wrong is visible in it: at 100% machine score the arrow does NOT go to `/to-plan`.
- **The alignment gate was grading its own homework — five reference implementations were read, and only one had solved it.** `/shared-understanding` shipped with a single number, and the agent that wrote the brief was the same agent that ran the scorer that approved it. It looked rigorous — rubric, threshold, report — and measured whether the author had filled in the author's own form. Read in full on 2026-08-28: [`github/spec-kit`](https://github.com/github/spec-kit) (`/clarify`, `/analyze`, `/checklist`), [`obra/superpowers`](https://github.com/obra/superpowers) (`brainstorming`), [`jeffallan/claude-skills`](https://github.com/jeffallan/claude-skills) (`feature-forge`), [`FredAntB/Spec-Driven-Development`](https://github.com/FredAntB/Spec-Driven-Development) and [`melodic-software/claude-code-plugins`](https://github.com/melodic-software/claude-code-plugins) (`discovery/blindspot`). Only spec-kit had separated the powers: its checklist is **reviewer-owned** — generated unticked, ticked by a human, and its `/implement` reads the boxes as a gate and *may not modify the markers*. Adopted here. `ALIGNED` now needs two independent things: a machine score the agent can reach, and a sign-off only a person can give; `AWAITING_REVIEW` is the normal state in between, and the agent ticking its own box is a Rule 3 violation, not a shortcut. **The rubric grew from twelve criteria to seventeen**, each new one from a source that had it: stable `FR-`/`NFR-`/`AC-` ids (every implementation converged on these independently, because without one nothing can cite anything); acceptance criteria that must cite the requirement they close, checked in both directions since a criterion citing nothing proves nothing in particular and a requirement no criterion cites ships unverified; the four scenario classes (`primary` / `alternate` / `exception` / `recovery`), which turn "happy path only" from an anti-pattern somebody remembers into a check that fires; unquantified quality adjectives — *fast*, *robust*, *seamless* — flagged anywhere they carry weight, where the old rubric demanded numbers from the NFR section alone and let "the explorer shall be responsive" through as a functional requirement; and placeholders scanned across the whole document, where `UNKNOWN` used to cost a point only inside the answers section and a `TBD` in the data model was invisible. The protocol changed with it: the question budget dropped from fifteen to **five** ranked by Impact × Uncertainty, because the cap is what forces the selection; answers are written to disk after each one and must **replace** the ambiguity rather than sit beside it; and the path is classified out loud as spike / bounded / architectural with a one-way ratchet, on the principle that the ceremony scales with the task and the approval gate never does. **A real defect surfaced while doing it:** `_section` stopped at `^##+`, so `## Flows` ended at its own first `###` and the criterion scored 0 over a brief containing four flows — and the fixture still cleared 90%, because two lost points fit inside the tolerance. The gate had been reporting "no named flow" about a document full of them, which is worse than no gate, since it produces a verdict.
- **`/shared-understanding` — an item nobody can draw is an item somebody is about to guess at.** The chain measured whether an item was *worth doing* (`cycle-discover`) and whether its *plan* was sound (`plan-confidence`), and nothing in between measured whether both sides pictured the same system. That gap is where the expensive defects come from: two people read one paragraph, everyone nods, and the disagreement surfaces at review — after the work. The new Phase 0.5 of `cycle-plan` closes it by running the interview and the drawing **in the same pass**, because apart they each fail: a diagram of a vague brief is a confident misunderstanding, and an interview stops at the questions somebody thought to ask, while placing an arrow forces the ones nobody did (who calls whom, with what payload, and what happens when it fails). Output is an alignment brief plus a **self-contained animated HTML walkthrough** — no build step, no dependencies — that a reader watches rather than reads; the moment a packet takes an edge they did not expect, the gap is on screen and nobody has to be persuaded it exists. `score_alignment.py` scores twelve criteria 0/1/2 and gates at **90%**, the Definition-of-Ready convention; below it the item is not built, and `cycle-implement` now refuses a plan whose item never aligned. The scorer measures **structure, not correctness**, and says so: three items — whether the stated problem is the real one, whether the flows drawn are the flows that matter, whether the numbers are the right numbers — are named in every report and excluded from the score rather than silently counted as passing. Fixtures measure both directions: a complete brief scores 92%, and one that *looks* complete to a skim (every section present, "make the dashboard faster", "should feel responsive", one `UNKNOWN`) scores 21% — the second is the failure mode that reaches implementation, since an empty brief is obviously not ready. Three defects were found and fixed while building the walkthrough, each of which made it useless in a different way: `animateMotion` **translates** from the element's current position, so a packet placed at the wire's start ended up at start+path and parked off-screen; a fixed `viewBox` broke at any container width other than the one it was authored at, with labels overlapping and wires pointing where the nodes used to be; and two node states were not enough to read — a node in the flow but not in the current step faded to the same grey as one the flow never touches, so the reader lost the path. All three verified in a real browser, not asserted.
- **Pre-flight on task interfaces, and `cost if wrong` on every decision — both taken from an observed `subagent-driven-development` run.** The output of that run (`obra/superpowers`, 2026-08-28, 7 tasks across 2 repos) was read end to end, and two of its mechanisms had no equivalent here. **(1)** Its pre-flight pass cross-checked 14 producer/consumer pairs **before any code** and found six defects in the plan — a helper no task called, a duplicate import, unrelated changes riding along, and `assert.throws` returning `undefined` at eight call sites, which would have failed every test in two files. This kit asked the same question one phase too late: `check_wiring.py` runs after `/implement`, when the mismatched calls are already written. `check_task_interfaces.py` now reads the `#### Pseudo-code / Signatures` blocks and reports three shapes — produced-and-never-consumed, consumed-and-never-produced, consumed-before-produced — while both tasks are still prose. It is **advisory**: the signature block is optional by template, so an absent one is *unknown*, never clean, and tasks without one are counted and reported as unchecked. Two false positives were found and closed during construction: what the LAST task produces is the plan's entry point by construction (nothing inside the plan calls it), and code blocks in other shapes are deliberately not harvested — reading any ```js block would pick up locals, imports and fixtures and bury the signal. Measured against the motivating plan itself: 7 tasks, 7 unchecked, no fabricated findings. **(2)** Every ruling in that run ended with what it would cost to be wrong — *"cosmetic only"*, *"none — the helper asserts strictly more"*, *"the skill carries a figure whose guarded arm describes an engine crash"* — and naming the cost is what separated the six fixes applied immediately from the two recorded-not-fixed and the one escalated to a human. `check_adr_completeness.py` now reports `missing_cost_if_wrong` per decision. It is deliberately per-ADR and never satisfied by a global section: rejected alternatives can be shared across a plan, the cost of one decision being wrong cannot.
- **The CHANGELOG is in English, and G5 now warns about the defect that was actually measured.** Two loose ends from the day closed. All 37 Portuguese lines were translated (the file had no released version, so nothing published was rewritten); four lines keep Portuguese with the reason on the line, each quoting terms a checker used to accept or an identifier that was renamed. And G5's wording was widened after the baseline showed both tested tiers refusing the prior-art justification and differing only in what they wrote instead: the rule said "reject the appeal to authority" and the harder case is a **fabricated local problem** replacing it, which passes a reviewer more easily. A third tier was tested at the same time — **Sonnet complied**, writing *"no incident or defect currently traces to goroutine lifecycle bugs"* and offering "none found" as a legitimate result, so the cut line sits between Sonnet and Haiku rather than between Opus and everything else.
- **The sixteen judgement gates were tested for the first time, and the result inverted the case for deleting them.** Method borrowed from [`obra/superpowers`](https://github.com/obra/superpowers): run the scenario WITHOUT the rule, under combined pressure, and record what the agent does — *"if you didn't watch an agent fail without the skill, you don't know if the skill teaches the right thing."* Four gates tested (G5 prior-art, verdict-computed-never-asserted, kill-is-reasoned, verifiable-DoD); the other twelve are unmechanised for structural reasons, so pressure-testing them measures nothing. **On Opus 5, four of four complied** — the agent refused the prior-art item and registered a spike to measure whether the problem exists, wrote `NOT_VALIDATED` against a manager asking for a green report, documented a kill nobody would read, and rewrote an unfalsifiable DoD while refusing to invent a threshold. Read alone, that is an argument for deleting all four. **On Haiku 4.5 the same G5 scenario failed differently:** the model also refused the item, then rewrote its justification into a local problem it invented — *"shutdown is scattered, error propagation is unclear, testing is brittle"*, none of it in the scenario — while keeping the appeal to authority beside it. That is the defect G5 exists to prevent, arriving better dressed. **The rules are insurance against a weaker model, not redundancy**, and consumers choose their own model. A second reading came free: both tiers refused the bad input and differed in what they produced instead, so what a judgement gate must catch is "the agent manufactured plausible input to replace it", which is not what G5's prose warns about. Limits stated in the record: N=1 per scenario, scenarios written by someone who knows the rules, four of sixteen, two tiers, and a baseline that inherits `CLAUDE.md` rather than being instruction-free. Finding in `.squad/wiki/references/`, run record in `records/experiments/`.
- **The english-only gate reached consumers as a dead script, and now they get all three layers.** Installing `check_english_only.py` protected nobody: the kit runs it in **its own CI**, and a consumer does not have the kit's CI — the installer does not carry `.github/`. So it landed in 19 installations as a file nobody would ever run. It is the same defect as the rest of the day seen from the other side: first a mechanism with no contract, now a mechanism with no caller. Worse, because `ls` shows the file sitting there and the tree looks complete. Three things ship together now: **`rules/english-only.md`** (the contract the agent reads, with the three legitimate exemptions and why detection is precise rather than exhaustive) and **`hooks/english-only-check.sh`** (`PostToolUse` on `Edit|Write`, reporting on the file just written). The hook is **advisory and the checker is the verdict**, the same split `public-copy-lint.sh` uses: at write time a quotation and a lapse look alike, and blocking the author mid-edit fights them at the moment they can least explain themselves.
- **`test_hook_declarations_agree.py` — two files declare hooks and nothing checked that they agree.** `hooks/hooks.json` serves the native plugin layout; `settings.json` serves standalone and is the source of `settings.plugin.json`, which is what a consumer receives. Measured while adding the hook above: I declared it in `hooks/hooks.json`, it installed correctly into a consumer, and **was never invoked there** — because the consumer reads `settings.json`, where it was absent. File present, executable, correct, and dead. The test also confirms every declared script exists: a declaration pointing at a missing file fails silently, and a hook that never fires is indistinguishable from a hook that found nothing.
- **`check_english_only.py` — the kit and every repository that installs it are English by policy, and nothing enforced it.** Measured before this landed: **334 Portuguese markers across 21 versioned files** here and 93 across 17 in the sibling kit. Two checkers had gone further than tolerating it — `check_adr_completeness.py` MATCHED `"por que não"`, `"considerada"` and `"considerado"` beside the English terms, and `check_deps_audit.py` accepted `(nenhuma)` as a valid declaration of no new dependency. A kit whose gates read a second language has decided its own policy is advisory, and a plan written in Portuguese passed those gates while failing the rule that governs the repository. Both now read English only. The detector is deliberately **precise rather than exhaustive**: it matches function words that cannot plausibly appear in English technical prose, never `para`, `com`, `de` or `mode`, which are English or live inside identifiers, paths and URLs. A gate that cries wolf is a gate somebody disables — and this one runs in every consumer, where whoever sees the false positive did not write it and has no reason to trust it. A line may keep its Portuguese by saying why **on the line itself** (`# english-only: verbatim quote of CLAUDE.md`); an exemption with no reason does not count, because a silent opt-out is the thing being prevented. Wired into CI in both kits, and verified working inside a consumer: installed into a throwaway project with a Portuguese `README.md`, the gate exits 1 and names the line.
- **The 51 Portuguese lines outside the CHANGELOG were translated, and one identifier renamed.** `class Motivo` became `class Reason` — a Portuguese identifier in shipped code is not prose to translate but a rename to perform. Three files keep Portuguese with a stated reason, and each is the case the exemption exists for: `rubric-v1.md` and `test_smell_pt_br.py` are the DETECTOR for Portuguese demonstratives and its fixture, so they must name the words they look for, and `test_check_semantic_names.py` quotes `CLAUDE.md` verbatim, which is written in Portuguese.  <!-- english-only: names the identifier it renamed -->
- **Names that state their purpose, checked by a gate.** `check_semantic_names.py` refuses four shapes of structurally empty name: a directory or file taken from the dumping-ground list (`lib`, `utils`, `helpers`, `misc`, `common`, `shared`, `core`…), two naming conventions in the same directory, `test_*.py` outside any test tree, and an executable with no docstring or header saying what it does. `CLAUDE.md § 5` was already the rule of the house — *"better a long clear name than a short problematic one"* — and it names the anti-pattern (`Manager`/`Helper`/`Utils` as a dumping ground); the gate extends the same rule to folders. Two deliberate exemptions: names fixed by the language (`__init__.py`, `conftest.py`) and **directories that carry their own licence** — renaming a third party's file breaks comparison with upstream and detaches the attribution from what it covers. What it explicitly does NOT decide: whether `analysis` is worse than `trajectory-validation`. That is judgement about meaning, and a checker asserting it would produce confident nonsense at scale. 24 tests, in CI.
- **`wiki/` — the kit's durable knowledge becomes an OKF v0.2 bundle.** We adopted Google's [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) in place of the homegrown convention, because it already mechanises what we were reimplementing: `stale_after` instead of the `last_reviewed`+`review_interval_days` pair, `log.md` instead of a stream of our own, and — what matters most here — **trust tiers** (`unverified` / `machine-confirmed` / `human-reviewed`) derived from the `verified` field, which is exactly the computed-versus-asserted distinction this kit mechanises gate by gate. Rule 9 applied to the record itself. The bundle is born with two linked concepts and passes `okf-validate --strict` (0 orphans, 0 broken links).
- **The split the migration settled on: knowledge in the bundle, the trail where it was.** `wiki/` takes what evolves, has an owner and ages — procedures, decisions, absorbed references, measured opportunities. `knowledge-base/` keeps the dated records: audits, reviews, implementations, releases, acceptance, `*-runs/`, progress. An audit from 2026-08-26 is not a concept that evolves: it does not become `deprecated`, and re-verifying it would falsify what it is. Recorded as an ADR in `.squad/wiki/decisions/where-knowledge-lives.md`, which is itself the bundle's second concept.
- **Resolution with a fallback, so 42 consumers do not break.** `resolve_knowledge_dir()` tries `wiki/` and falls back to `knowledge-base/`; writers only ever write to the new one. No installed consumer breaks, and each migrates as it runs. A leaf outside `DURABLE_LEAVES` **never** resolves to the bundle — accepting a `wiki/sop-runs/` somebody created would invite exactly the mixing the split exists to prevent. 12 tests.
- **SOP family — the static script and the judgement that runs it, kept apart on purpose.** `/sop-author` writes the procedure, `/sop-run` records what an execution actually did, `/sop-review` audits whether either is still true. The split is the whole design: a procedure that absorbs its own exceptions stops being a procedure, because the next reader cannot tell the official sequence from the six times somebody worked around it. `rules/sop-schema.md` is the contract; `check_sop_structure.py` (23 tests) and `check_sop_run.py` (20 tests) are the mechanisation, both in CI. The gate that carries the design is **`missing_escalation`** — every other finding is about a badly written script, that one is about a script claiming to be complete, and the claim is what converts a deviation into an improvisation nobody records. The version control materialises the same split: `knowledge-base/sops/` travels with the project, `knowledge-base/sop-runs/**` is gitignored, because the procedure is shared and what one machine did following it is not.
- **The first SOP is a procedure that was performed, not imagined.** `port-fix-between-kits` was written from the Squad→Cycle port run earlier the same day, and its run record carries the two real deviations: a ported test asserting the sibling's phase chain, and `check_gate_mechanisms.py` rejecting an annotation that cited a module this kit does not have. `/sop-author` refuses to write a procedure nobody has performed — the steps would be what someone imagines the work to be, and the first real run contradicts them. Two of the eight steps in that SOP were improvised during the run and would not have occurred to anyone at a desk.
- **Every declared hard gate names what computes it.** Measured before this landed: across the nine `rules/cycle-*.md` carrying the section, **59 gates declared and 11 naming a script**. The other 48 were not unenforced — sampling the five BLOCKERs of `cycle-review.md` against the hooks found four of them mechanized (`stop-validation.sh`, `validate-command.sh`) and **zero of five saying so**. A mechanized gate whose rule names no mechanism reads, to whoever opens the file, exactly like a gate nobody runs; this repository had already recorded the opposite direction of that confusion (*"a gate listed among four automatic ones reads as automatic, and a gate believed to be automatic is a gate nobody runs"*). `check_gate_mechanisms.py` now demands one of three forms per gate — an executable that exists, a link to the rule that owns it, or `_(not mechanized: <reason>)_` — and runs in CI so the annotation cannot decay. The third form is what keeps it honest: `/backlog-item`'s G3/G4/G5 are judgement by design, and forcing a script name on every line would push someone to invent one. After: **41 named, 7 partially mechanized with the residue declared, 11 exempt with a reason, 0 unresolved**. 24 tests.
- **A phase transition leaves an event, not an archaeological trace.** `cycle_events.py` appends one JSON line per transition to `knowledge-base/cycle-events.jsonl`, and `run_code_quality.py`, `run_validation.py`, `consolidate_findings.py` and `compute_acceptance_verdict.py` emit from the point where their verdict is known. Until now the only proof a phase ran was a file appearing in one of **15 record directories**, reconstructed afterwards by `phase_coverage.py` — which is why that instrument could not separate *"the phase was skipped"* from *"the phase ran and left nothing"* when it measured `code-quality` at 15%. A missing file is evidence of nothing in particular; a missing event is. Two deliberate absences: **no sequence number** (line order in an append-only file already is the sequence, and a counter would race and hand the reader a number that looks authoritative and is not) and **no raising** (a phase that did real work must not fail because its bookkeeping could not be written). 21 tests.
- **`rules/cycle-phases.txt` + `check_phase_drift.py` — the declared plan, confronted with what ran.** The chain was prose in a README, a manifest and eleven rule files; four places to drift, and nothing that could be asked whether a run followed it. The file declares the chain once, with each phase `required` or `conditional`, and the checker compares it against the stream: a phase that ran undeclared, a phase out of order, a required phase that never ran, and — the one worth the work — **a phase that advanced past a blocking verdict**. `check_upstream_gate.py` already refuses `/review` on a `FAIL_HARD` audit, but it reads the audit FILE, so it speaks only for the run that produced it; the stream records ORDER, which is what makes *"review ran anyway, afterwards"* answerable at all. A missing `conditional` phase is never a finding: an item killed in DISCOVER never reaches PLAN, and the rule calls that a successful outcome. 18 tests.
- **D3 and D4 exist.** `code-quality-golden-rule.md § 5` declared both as LOCKED contract and all four language adapters returned the same string — `unavailable("d3"/"d4", …, "is not configured")`. Because `unavailable()` emits SOFT_CAP, **every audit of every project was born with two permanent soft caps**: `PASS` was unreachable by construction, and `/implement` converted the cap into a WARN nobody reads. **D3** (`detectors/_wiring.py`) audits the surface the project DECLARED — `__all__` and `__init__.py` re-exports, what `package.json` points at, `pub` in `src/lib.rs`, exported identifiers outside `internal/` — and infers no surface at all: a project with no declared surface gets INFO, never a verdict about a contract nobody wrote. **D4** (`detectors/_mutation.py`) runs mutmut and Stryker and answers the one question coverage does not. The proof it is worth it: a four-line module under a tautological test gives 100% line coverage and a **12.5% mutation score** (1 killed, 7 survived, measured with mutmut 3.5). Rust and Go remain deferred, now saying so.
- **`/review` checks its own pre-condition.** `check_upstream_gate.py` reads the slug's most recent `/code-quality` audit and emits a BLOCKER when it is missing, unreadable, `FAIL_HARD`/`INVALID`, or `FAIL_SOFT` with any soft cap no ADR names. `consolidate_findings.py` folds those findings into the same verdict computation as the rest, so a review verdict can no longer be produced without the check. It was prose in `SKILL.md` plus a `test -f` someone had to remember to run — and the ADR, which is the piece that makes a soft cap dismissible, was looked for by nobody.
- **The CVE gate stopped depending on memory.** `check_deps_audit.py` binds the plan's `## Dependencies` section to the verdict `/deps-audit` left on disk: a CRITICAL/HIGH CVE caps the plan at 49 (`INVALID`), a missing report caps it at 89. `cycle-plan.md` called this one "the one gate in this cycle nothing mechanizes". The check does not look for CVEs — the scanners do that; it reads the verdict. Absence of an audit never becomes "no CVE".
- **`/quality-init` measures how much of the code the calibrated gate would block.** A new stage 6.5, with verdict `READY` / `REVIEW` / `TOO_STRICT`. The skill promised adaptive calibration "so the gate does not start out rejecting the code already there" and never checked: run against this repository, with the thresholds it produced itself, **49% of the files would be blocked** (61% putting each file through the generated hook, which also checks duplication). The p90 is computed per METRIC and the gate rejects per FILE — thirty functions in a file are thirty chances of holding one of the worst 10%, and five metrics multiply that.
- **The kit runs its own code gate in CI.** `/code-quality` joined the workflow. On the first run: `FAIL_HARD`, over an `unused variable` from an `argparse`-mandated signature that had been there all along, with an empty allowlist — nobody had ever run it.
- **The kit now installs as a native plugin, without copying itself into the project.** `.claude-plugin/plugin.json` (where Claude Code looks for the manifest) and `hooks/hooks.json` (which registers the six events resolving through `${CLAUDE_PLUGIN_ROOT}`). In this mode the kit's CODE lives outside the project and the project keeps only what is its own — `knowledge-base/`, `rules/*.txt`, `agents/*.md`. The copy install (`scripts/install.sh`) remains supported and unchanged for whoever already uses it.
- **The installed kit became read-only.** `hooks/boundary-check.sh` refuses Edit/Write over the kit's skills, normative rules, hooks, scripts and commands — in both layouts. What belongs to the project stays writable, and is enumerated in the hook itself: `rules/*.txt`, `agents/`, `knowledge-base/` and `settings.json`. A skill the PROJECT wrote is recognised as its own by consulting `.kit-manifest.txt`, which the installer already wrote and no hook read. The kit's repository opened standalone is NEVER protected — blocking there would prevent the very work the boundary exists to preserve.
- **`check_record_scope.py` — a review record that does not say what it reviewed cannot be checked afterwards.** After `phase_coverage.py` (B-105) measured `review` at 52% and `code-quality` at 27%, the obvious next step was to DERIVE the records, the way half of `release` was derived — the commit graph knows which tag contains which commit, and 41 of 41 items resolved that way. It does not work here, and the measurement says why: **2 of 48** review files declare the reviewed range, **3 of 16** audits mention scope. A review's findings are judgements made in a session; if the file names neither the items nor the range, nothing recovers that later.
  So this closes the door going forward instead of retroactively. Guessing what 46 old records covered would fabricate exactly the coverage the check exists to make verifiable.
  It is B-084's defect one level up — that one closed "a gate that inspected zero and one that inspected everything emit the same verdict", B-102 added "…and does not say what it left out", and here: **a review that covered seven items and one that covered a single item are indistinguishable from the file.**
  What it refuses to infer is the filename: `b086-findings.yml` looks like it declares B-086, and a slice review covering seven items would look exactly the same. A declared range (`head_reviewed`) is reported and never replaces the list — a range says what was READ, the items say what for.
  **Mutation found a hole in my own tests, not in the code:** swapping the reading of the declaration for "any B-NNN anywhere" passed all seven initial tests, because none of them had a B-NNN outside the declaration. Review records are full of prose referencing other items ("same family as B-084", "supersedes B-050"); a checker that counted those would report coverage that did not happen — the wrong reading the item exists to prevent, arriving via the checker built to prevent it. Eighth test added, mutant dies (an adopter B-108)
- **ADR 0012 decides which phases must leave a record, and the measurement knocked part of it down.** `phase_coverage.py` answered "which artifacts exist per item" and immediately raised the question it could not answer: is a missing artifact debt, or is the metric asking the wrong question? The ADR split it into three classes — `plan` and `review` per item and mandatory; `code-quality` per slice (`cq_invoke` audits a TREE, not an item); `release` per version; `discover` satisfied by the item's own `evidence:` block, because `cycle-discover.md` has two entry points and only one writes an opportunity file.
  **Measured after it was written, and only one column moved:** `discover` 60% -> 98%, while `plan` 82%, `code-quality` 26%, `review` 52% and `release` 50% stayed exactly where they were. The ADR's reasoning called `release` and `code-quality` a "category error in the metric" — that was wrong, and the instrument said so: the scan already matches by CONTENT, so a release record naming ten items covers all ten. **50% and 26% are real debt, not an artifact.** The ADR records its own refuted premise instead of editing it out in silence.
  The tool prints both columns by default and has no flag to switch that off: **a percentage that rises because the metric was corrected is not progress**, and a report that can be run without the control number is a report that will be (an adopter B-105)
- **`phase_coverage.py` — which cycle phases left a record, item by item.** A stopping gate and I spent four rounds asserting opposite things about whether every item had been through every phase of the loop. **Neither of us had measured**, and the one repeating the stronger claim was me. `BACKLOG.md` records an item's STATUS and nothing about which phases produced it, so "the loop ran" was unfalsifiable.
  Measured: `discover` 61%, `plan` 82%, `code-quality` **15%**, `review` 53%, `release` 47% — and **11 of 96** items with a record of all five. Of the ten items worked in the very session that was arguing about it: **0 of 10**.
  What it does NOT say is the finding, not a caveat about it: it measures whether the phase left a RECORD where its contract requires one, not whether the phase ran. In my own session's case, `code-quality` read 0/10 while I had run `pnpm gates`, `run_slice_tests.sh`, `check_xrefs`, `test_e2e_smoke` and a mutation round per fix on all ten. The gate ran; `cycle-code-quality.md` says its output is `knowledge-base/audits/{slug}-code-quality.md`, and I wrote none. Which is to say: the ecosystem could not tell "the phase was skipped" from "the phase ran and left nothing" — B-084's defect one level up.
  Two behaviours the tests pin because getting them wrong would make the report worse than nothing: a `killed` item ends at DISCOVER by design (`cycle-discover.md` calls killing an item a SUCCESSFUL outcome), so its missing phases are excluded rather than counted as debt; and `b010-` is not satisfied by `b100-...`, a trap a `startswith` falls into silently. `IMPLEMENT` is deliberately not measured — its evidence is the commit history, and a directory sweep pretending otherwise would report absence for every item (an adopter B-105)
- **`/arch-check` — the boundaries the repo already has, or the ones it declared.** An idempotent skill: if a config exists, it verifies (via D5); if none exists, it **measures the real import graph and proposes only what the repo already obeys**. The criterion is measurable rather than opinionated — an edge that is already one-way is an invariant, not a taste: if `tui/` imports `agents/` 33 times and the reverse is zero, "agents does not import tui" **is already true**, and writing it down changes no code. If both directions carry traffic, there is nothing to freeze and nothing is proposed. A candidate that would fail on day 1 does not become a gate: it becomes a backlog finding, named in `not_proposed` with the reason. Four families, each with the count that justifies it: `no-circular` (only when there are zero cycles today), `one-way`, `siblings` (two units in the graph that exchange nothing) and `independence`. Validated against `agent-builder`: from measurement alone it derived the same three rules a human wrote by hand there — plus one they did not write. **The skill never writes config; it proposes and you ratify**
- **`/arch-check`'s five gaps, closed — and the cycle proves it on 11 of 11 Go modules.** (1) `theo` was refused: `go list ./...` at a workspace root exits with *"directory prefix . does not contain modules listed in go.work"*, so the ecosystem's largest Go repo was the one the tool could not read. Each module is now walked separately, with units prefixed by the module's directory, and modules **outside** the repo are discarded — `theo`'s workspace uses `../contracts`, which is a sibling repo with its own boundaries. (2) TypeScript had inherited the coarse granularity measurement had already rejected in Go; it now uses the analogue: the smallest prefix directory that directly contains sources. (3) Edges that exist only in test files are measured **separately** and reported in `test_only_edges` — folding them into the allow list would let a test that crosses a boundary license production to cross it. (4) The package at the module root had no unit, and 22 files across three `theo` modules fell outside every rule while the config reported full coverage. (5) The non-architectural name filter was being applied to Go, where `go list` already returns only real packages: `internal/services/build` is a legitimate Go package and was being **erased** by name, producing 14 violations against a component that does not exist
- **`emit_config.py` — the translation from proposal to config, which is where the criterion gets lost.** Adopting the proposal by hand in `control-plane` took four attempts, and no failure was a wrong rule: a component key without `:` (32 schema errors in `ExecutionWarnings`, a field nobody reads, with `ArchWarningsDeps` at 0 — green having validated nothing); `in: internal/auth` that does not cover subpackages (24 ungoverned packages); a unit that cannot import its own subpackages (63 violations that were no crossing at all); and a list derived from production imports against a linter that sweeps tests (49 violations coming solely from `_test.go`). The temptation in each was to widen the rule. The generator goes the other way: it imposes **exactly** the measured set, and what is left over is declared out of scope instead of silently permitted. A multi-module repo gets one config per module, because go-arch-lint resolves the project from `go.mod` and does not read a workspace root
- **The proposer's granularity was too coarse to govern anything.** The first version used the top-level directory as the unit. Measured on `control-plane`: `internal/` has **0 direct `.go` files and 28 subdirectories** — it groups, it does not implement. Treating it as one unit hid every dependency among the 28 (`internal/auth → internal/account` became an invisible self-import) and left **44 packages of a 35-package module outside any component**: the rules governed 2 units and reported success. The unit is now the **smallest path prefix that is itself a package**, which is measurable and not a matter of taste — `internal` is absent from the package list precisely because there is nothing there to govern. And the non-architectural directory filter now checks **every** segment: a vendored `.go` inside a TypeScript app's `node_modules` had become a `control-plane` unit
- **The proposal became an ALLOW list, not an enumeration of prohibitions.** With real granularity `control-plane` has 27 units — 702 ordered pairs, 302 of which never touch. Proposing 302 rules is not rigour, it is noise nobody adopts, and it contradicts the skill's own criterion (*a rule you kept only because a tool suggested it is worse than none*). The rigorous form is the one the tools use natively: each unit declares what it imports today, and **everything unlisted is forbidden** — which also refuses by default a new edge between two units nobody foresaw. `siblings` is restricted to top-level units, where the pair is a pair of genuine architectural surfaces
- **The refusal the skill must make in order not to lie.** The shared extractor returns an empty list when tree-sitter is missing — it degrades instead of failing. An empty graph would make **every** pair look one-way, and the skill would emit a complete rule set built on having read nothing. An empty scan is refused, and the refusal distinguishes two states the edge count conflates: units seen with zero imports between them is real independence (measured on `contracts`: `jwt`, `plan` and `serviceauth` do not import each other) — fewer than two units seen is the parser not having run
- **D5 — architecture rules, and the meta-gate that they can still fail.** `/code-quality` gains a fifth detector that runs each language's architecture linter against the config the **repo** declares: `dependency-cruiser` in TypeScript, `go-arch-lint` in Go, `layered-crate` in Rust, `import-linter` in Python. The Squad ships no layering model at all — a rule asserting an architecture nobody declared would produce findings that are evidence of nothing, which is the same defect gate G5 refuses. A repo with no config emits INFO and is skipped.
  What D5 adds on top of the tools is the meta-gate: **a rule that cannot fail is worse than no rule**, because it transfers confidence to a mechanism that has stopped existing. Two measurements, both from this ecosystem on 2026-08-06. In `contracts`, a `.go-arch-lint.yml` whose component names a non-existent directory answers `ArchHasWarnings: false` — green — with the diagnostic demoted to a field nobody read. In a TypeScript monorepo, the config itself records the class in prose: dissolving `tui/lib` would leave a `forbidden` rule written against the old name matching nothing, and `npm run boundaries` reporting success. D5 verifies that the directories a rule names are still in the tree, distinguishing the two sides — `from` selects the code the rule governs (gone ⇒ HARD), `to` may legitimately match nothing, which is a preventive rule working
- **Three empty-gate traps, each measured before becoming a test.** A cruise that reaches 0 modules passes every rule without inspecting anything — `agent-builder` measured the global binary cruising **0 modules** against a config the local one cruised at 279; `allow.ignoreNotFoundComponents: true` switches off go-arch-lint's own protection against a phantom component; and `tsarch` declared as a dependency with no file importing it is an auditor that never runs, the same shape theo#255 catalogued nine times. All three fail
- **`BACKLOG.md` now opens with an index of ALL items, generated and verified.** Four records across the ecosystem, **592 items in blocks and zero index lines** — the question "what is pending?" could only be answered by grepping `status:`. There is now an `## Index` section before the items, grouped into three buckets with one line per item linking to its own detail block: **Open** (`raw`, `triaged`), **In flight** (`planned`) and **Closed** (`shipped`, `killed`). `triaged` stays in Open on purpose — the measurement ran, but there is no plan, so nothing is being built; folding it into In flight would make that number answer a different question from the one asked of it ("what is someone building right now?").
  **The index is generated, never written.** With 592 items, a hand-written index goes wrong on the first item that changes status — silently, because nothing compares the two — and a summary that disagrees with the items is worse than none: the reader stops at the summary. `backlog_index.py --write` derives from the blocks, `--check` exits 1 when they diverged, and `check_backlog_structure.py` reports `index_stale` treating **absent as stale** — otherwise a record exempts itself from the check simply by never having the section, which is how all four reached 592 items with no index. The generator shares the item parser with the validator: a second parser would diverge silently and the two would disagree about what the record contains, which is the exact defect the index exists to make visible
- **`duplicate_field` — `status` declared twice in the same block.** Discovered while checking why `db-engine`'s index counted 56 items where `grep` counted 58: `B-021` carries `raw` **and** `triaged`, `B-022` carries `planned` **and** `raw`. Every reader keeps the last one, so the item's bucket becomes an arbitrary parser choice rather than data. Only `status` is reported, deliberately: the first version checked every repeated field and lit up `control-plane`, where `partial_progress` four times in B-031 is an increment log the team keeps on purpose and `evidence: none-yet` followed by a pointer is an item that moved on. Neither is a defect, and a gate that reports them is a gate you learn to ignore — which is how the real one slips past
- **`install.sh --merge` — installing into a repo that already has its own `.claude/`.** The installer knew only two things: refuse, or delete-and-copy. Neither serves a target that brought its own content. Measured on an adopter: **598 files** in `skills/` — 5 from the kit and **10 written by the project** (`architecture-debate-table`, `placement-algorithms`, `quota-isolation`, `shard-modeling-specialist`, …) — plus **13 named architect agents** and 38 per-agent memory files. `--force`'s recursive removal would have deleted them all, and a snapshot in `.install-backups/` is a consolation prize, not a correct install. `--merge` adds and **deletes nothing**; and it does not overwrite an existing `settings.json` — it is the most project-specific file in the tree, and losing it costs more than all the skills combined: the kit's goes to `settings.json.kit-reference` to be compared by hand. An unknown flag now fails instead of being ignored, which previously turned into a default install in silence
- **`settings.plugin.json` — broad permissions with a `deny` that carries the weight.** `allow` becomes `Bash(*)` plus `Edit`/`Write`, and `ask` is left empty: a prompt on every `ls` trains people to approve without reading, which is the opposite of what a gate is for. The 27 narrow entries and the 6 `ask` rules go. **The `deny` stays**, and `deny` takes precedence over `allow` — so the breadth above costs nothing: git's 6 safety rules still apply, and with them the **8 secret-reading rules** (`.env`, `**/credentials*`, `**/*secret*`, `**/*.pem`, `**/*.key`). Those eight matter most, because **no hook intercepts `Read`**: `validate-command.sh` is `PreToolUse:Bash`, `boundary-check.sh` is `Edit|Write`, and `stop-validation.sh` only flags a secret **already committed**, after the fact. Destructive commands (`rm -rf /`, `sudo`) are left to `validate-command.sh`, which blocks the class with 17 rules — verified live: it stopped two of my own attempts to write those literals inside a command
- **`install_goal_hook.py` gains `--acceptance-dir` and now refuses paths that do not resolve — a badly aimed gate blocked forever for a false reason.** Found on first real use: a milestone whose checkbox lives in `control-plane/ROADMAP.md` and whose cycle artifacts live in `control-plane/knowledge-base/`, with the hook needing to land in `promptly/.claude/` (where the session reads settings). The installer exposed `--roadmap` but **not** `--acceptance-dir`, so the field stayed at its default pointing at the wrong repo — where the record would never exist. The operator had to edit the state by hand.
  - **The flag now exists**, and the arming report prints the **resolved** roadmap and acceptance paths, not the relative ones — a wrong configuration becomes visible immediately.
  - **Arming with a non-existent path is refused (exit 2), writing neither state nor hook.** `--force` remains available for the legitimate case where the directory is only born on the first `/acceptance` run.
  - **The gate distinguishes the two cases.** A non-existent `acceptance_dir` and a milestone never accepted produce the SAME missing file, and the "never ran" message sounds like a legitimate verdict. The gate now emits `MISCONFIGURED` with the instruction to re-arm — the difference between "fix the config" and "do the work".
  - 8 new tests (48 in the skill), including the end-to-end multi-repo scenario.
- **`/cycle-goal` now arms the gate itself, via a Stop hook — `/goal`'s limitation ceased to exist.** The first version printed a `/goal` command for the user to paste; in real use that broke (`/cycle-goal M27` got to step 3 and stopped). Three paths were investigated, **all three closed**: the `SlashCommand` tool does not expose built-in commands; `type: "prompt"` hooks — what `/goal` registers internally — are only valid in `PreToolUse`/`PostToolUse`/`PermissionRequest`, never in `Stop`; and `/goal` judges the **transcript** with a small model, which a confident sentence satisfies.
  - **The replacement is an upgrade, not a consolation.** `Stop` accepts a `type: "command"` hook, and a command reads **disk**: `scripts/check_goal_met.py` checks the `verdict:` in the acceptance record and the `[x]` checkbox in `ROADMAP.md`. An assertion forges neither. The 4000-char ceiling goes away, and so does the manual step.
  - **`scripts/install_goal_hook.py`** writes `.claude/cycle-goal.json` plus the hook into `.claude/settings.local.json` (personal, gitignored). It merges settings instead of replacing, re-arming swaps the hook instead of stacking, and it refuses a `settings.local.json` with invalid JSON instead of overwriting it. `--clear` removes only our hook.
  - **Fail-open and bounded, both deliberate:** any error in the gate releases the stop (a gate that jams the session is worse than one that fails once), and each block increments a counter — past `max_blocks` (40) the gate lets go with a warning saying the milestone is **not** ready, so that an impossible goal cannot hold the session captive.
  - **New contract between the two skills:** the `cycle-acceptance` record MUST carry `verdict: <TOKEN>` in its frontmatter, now required in `rules/cycle-acceptance.md § Output` and in step 4 of `/acceptance`. A verdict written only in prose is invisible to the gate and would make the milestone look never accepted.
  - 19 new tests (42 total in the skill), covering the two opposite errors: releasing unfinished work, and trapping a session that could never be released.
- **`/roadmap-review` — review the roadmap before the team executes it for months.** A defect in `ROADMAP.md` is not a documentation problem: `cycle-acceptance` reads each milestone's Definition of done **as its acceptance criteria**, so a milestone without one can never be accepted and its checkbox can never flip; a dependency cycle makes the macro loop emit `ROADMAP_BLOCKED` forever; a header at the wrong level silently breaks the flip. Nothing checked any of this until now.
  - **The catalog is sourced, not invented** — the union of `roadmap-init § Anti-patterns` (12 items) and the annotated failure list inside `fixtures/bad-roadmap-vague-milestones.md` (18 items), plus the two downstream contracts a roadmap must satisfy to be executable at all.
  - **Deterministic checks:** dependency cycles, unknown/forward/self dependencies, a milestone marked `[x]` while its own dependency is `[ ]`, duplicate ids, the M0–M8 cap, missing M0, malformed headers, missing/empty Definition of done, unfilled template placeholders, missing top-level sections, empty out-of-scope. **Labelled heuristics:** wish-word DoD bullets with no number, layer-shaped milestone names, single-bullet definitions of done. Every finding declares `deterministic` or `heuristic`, because a heuristic reported as fact trains the team to ignore the reviewer.
  - **The verdict is derived, never asserted** (BLOCKER → `INVALID`, MAJOR → `NEEDS_REVISION`, MINOR → `SHIPPABLE_WITH_CAVEATS`, none → `SHIPPABLE`), reusing the `cycle-plan` vocabulary rather than minting tokens for the same shape of decision.
  - **Honest about its own blind spot:** when a header is malformed the per-milestone checks never run on that milestone, so the script emits `checks_skipped_behind_malformed_header` stating the report is a **floor, not a full accounting**.
  - **Validated against roadmap-init's own reference examples** — it must approve `good-roadmap-ai-gateway.md` (`SHIPPABLE`) and reject `bad-roadmap-vague-milestones.md` (`INVALID`, 17 findings including the headline 12-milestones-over-the-cap). Running it against those fixtures caught two real defects during development: a false BLOCKER on the *good* fixture (it legitimately writes `` `{{name}}` `` in a code span while explaining how to cancel a milestone — the placeholder check now matches only SCREAMING_SNAKE template markers outside code and comments), and a cap check that never fired on the bad fixture because no milestone parsed. 34 unit tests. Read-only and registered as AUXILIARY, alongside its siblings `roadmap-init` and `roadmap-feature`.
- **`/acceptance M<N>` + `rules/cycle-acceptance.md` — a milestone is now `[x]` only after someone watched the released thing work.** Every gate in the chain grades the delivery against the project's own artifacts: tests pass, coverage holds, the reviewer approved, the tag cut. All of them can be green while the shipped product is broken for its user — a mis-wired env var in the deployed build, a proxy that buffers the stream, a login that 500s only against the real identity provider. Nothing in the pipeline ever touched the *released* artifact. The new cycle does, and it owns the roadmap checkbox:
  - **Criteria are the milestone's own promise.** `extract_acceptance_criteria.py` reads the `**Definition of done (all must hold):**` bullets from `ROADMAP.md` *before* the run. Criteria written after seeing the result grade a moved target; a milestone with no declared DoD yields `NOT_VALIDATED` rather than a pass.
  - **The instrument follows the delivery, the rigor does not change:** web → `chrome-devtools` MCP against the deployed URL; native app → `cua-driver`; CLI → install the published artifact and run it from a clean directory; library → consume the published package in a throwaway project; API → call the deployed endpoints. Exercising a local build, staging clone or mock is explicitly the blind spot the cycle removes.
  - **A `passed` with no evidence is not a pass.** `compute_acceptance_verdict.py` derives the verdict from the evidence record; the agent that ran the journeys does not get to name the outcome. With human sign-off deliberately out of scope for this project, recorded evidence is the only thing between a real validation and a confident sentence.
  - **`NOT_VALIDATED` is a separate verdict from `REJECTED`** — "we could not check" and "we checked and it is broken" are different facts, and collapsing them is how a cycle starts reporting untested work as tested. Both block the flip identically. `ACCEPTED_WITH_CAVEATS` requires an issue filed per defect.
  - 23 unit tests, concentrated on the ways a run could dishonestly earn an `ACCEPTED` (evidence-free pass, whitespace-only evidence, unexercised criterion, blocker defect with all criteria green, failure downgraded to caveat).
- **BREAKING (process, not API): `cycle-release` no longer flips the ROADMAP checkbox — `cycle-acceptance` does.** `§ 7.5` moved out of `cycle-release` and became the `flip` phase of the new cycle, gated on its verdict. Flipping at tag-cut made `[x]` mean *"we shipped it"*, which no gate in the chain could distinguish from *"we shipped something broken"*. It now means *"we shipped it and watched it work."* `RELEASED` stays the terminal verdict of `cycle-release` but no longer advances the roadmap; `cycle-roadmap` gains a **No flip without acceptance** hard gate, and `MILESTONE_BLOCKED` now also covers a `REJECTED` / `NOT_VALIDATED` acceptance run. `flip_milestone_checkbox.py` deliberately stays in the release slice — it is the single implementation of the single-flip invariant, and the new cycle invokes it instead of duplicating it.
- **`/cycle-goal`'s stop criterion is now the acceptance run, stated as an unbreakable rule inside the condition itself.** The composed `/goal` condition opens with `UNBREAKABLE — THE STOP CRITERION IS THE ACCEPTANCE RUN`: the goal is met for a milestone **if and only if** `/acceptance M<N>` emitted `ACCEPTED` or `ACCEPTED_WITH_CAVEATS`. It names what explicitly does *not* end it — a green test suite, `READY_TO_MERGE`, `RELEASED`, a published tag, or the agent's own sense that the work looks finished — because `RELEASED` means it shipped and only the acceptance verdict means it works; a goal stopping at `RELEASED` would re-open the very gap `cycle-acceptance` closes. `REJECTED` and `NOT_VALIDATED` never satisfy it, and three exits are closed by name: re-running `/acceptance` without fixing what it found, editing the milestone's Definition of done so the run can pass, and reporting a verdict `compute_acceptance_verdict.py` did not print. The rules live **in the condition text**, not only in `SKILL.md` — the Stop-hook evaluator reads the condition, so a rule kept in the skill file alone would bind nothing. The other six phases stay in the condition as the honest path to that verdict. Worst case (M0–M8) measures 2712 chars against the 4000 cap; 6 new tests.
- **`/cycle-goal M<N> [M<N> …]` — binds a session to roadmap milestones through Claude Code's built-in `/goal`.** `/roadmap-init` writes the milestones and `/auto-plan` executes one, but nothing held the session to the process in between: the agent could stop early, call a phase done without its artifact, or drift into a second milestone before the first shipped. The new skill validates the requested ids against `ROADMAP.md` and hands `/goal` a condition only a genuinely finished milestone satisfies — one line per cycle phase, each naming the artifact that proves it (plan with `milestone_id`, implementation log with real SHAs, code-quality verdict, `READY_TO_MERGE`, release via PR `workspace → develop`, checkbox flipped + `roadmap-runs` status). Details that shaped the design, all verified against the CLI rather than assumed:
  - **`/goal` is a termination condition, not a system prompt.** It registers a session-scoped Stop hook whose text a small model evaluates against the *transcript* on every stop attempt. So the persona and process discipline live in `SKILL.md` (read into the session), and only the verifiable condition is passed to `/goal` — a persona pasted into `/goal` would be judged as a condition and would blow the cap.
  - **The 4000-char cap is a BLOCK, never a truncation.** Silently trimming would drop phases off the end of the condition — precisely the bypass the skill exists to prevent. A test pins the worst case (`M0`–`M8`, the `/roadmap-init` ceiling) under the cap; a real two-milestone condition measures 1512 chars.
  - **Milestones run sequentially, one in flight**, per `cycle-roadmap`'s single-flip invariant. Out-of-order input is normalized ascending and *reported* on stderr rather than reordered silently.
  - `scripts/compose_goal_condition.py` is the deterministic gate: refuses unknown / already-`[x]` / duplicated / malformed ids, dependency walls, duplicate headers, and milestones written at a header level `cycle-release` cannot flip (reading leniently while the writer is strict is how roadmaps drift). 18 unit tests. Registered as an AUXILIARY skill alongside its siblings `roadmap-init` and `roadmap-feature`.
  - Honest limit: whether a skill can invoke a *built-in* command via the `SlashCommand` tool was not confirmed, so the skill issues `/goal` directly when available and otherwise prints the exact command — and states which of the two happened. It never reports the goal active without the CLI's acknowledgement.
- **Provenance guard — third-party study material can no longer leak into the project or its history.** The existing guards only watched writes *into* `knowledge-base/references/` and `knowledge-base/tools/`; everything in the other direction was open. Verified empirically before building: copying a zone file *out* (`cat <zone-file> > src/mine.c`), citing a zone path in a commit message, and pasting zone content into a project file were all accepted. Three new layers, plus `rules/reference-provenance.md` as the SoT stating what each one does and does **not** guarantee:
  - **P1 — export guard (blocking).** `cp`/`mv`/`rsync`/`scp`/`tar`/`dd`, `>`/`>>` redirects and `| tee` involving the zone are blocked. Reading, grepping and listing stay allowed — that is what the zone is for. Judged per command segment (reusing the splitter built for #6), so an unrelated `cp` elsewhere in a compound is not blamed on the zone; the pipe deliberately does not split, since `cat <zone-file> | tee <dest>` is itself an export vector.
  - **P2 — commit-message guard (blocking).** A message citing a zone path is refused, including via `-F <file>`. Matches the full zone path only, so ordinary words like "cross-references" are untouched.
  - **Layer 3 — leakage detector (advisory).** `scripts/check_reference_leakage.py` catches the *result* of a manual paste, which no command guard can see: a shingle of 5 consecutive meaningful lines shared between a changed file and a zone file, normalized for whitespace and case so reindenting a paste does not defeat it. Wired into `hooks/stop-validation.sh` as a WARN — a false BLOCK on a heuristic would be worse than a WARN, and shared boilerplate does produce real matches. Learning from #37 (which peaked at 4.15 GiB scanning this same zone), the index is built from the few changed files and the zone is *streamed*, with a cap whose truncation is always reported instead of silently claiming full coverage.
  - The detector's placement in `stop-validation.sh` sits **before** the no-diff early exit: `git diff` does not list untracked files, so the check would otherwise skip exactly the "pasted a brand-new file" case. 9 unit tests (including two mutation checks confirming the suite detects a weakened normalizer and a neutered scan) plus 13 hook tests; 76/76 hook + 26/26 root.
- **`cycle-rule-schema.md § Golden Rule Change Protocol` + `ADR-0010` — the LOCKED-rule change protocol is now stated once instead of 7× (rules-audit 2026-06-28).** All 7 golden rules carried a near-verbatim "When this rule may change" section (ADR + CHANGELOG + validators PASS) — one fact restated 7×, so a protocol change meant editing 7 files in lockstep. The common core now lives in `cycle-rule-schema.md § Golden Rule Change Protocol`; each golden rule references it and keeps only its own deviations (dogfood's operator sign-off, plan-confidence/discover-blueprint's "Rules that cannot be bent" + threshold-bump, code-quality's verdict-token/detector specifics). `knowledge-base/adrs/ADR-0010` records the decision (first ADR materialized in `knowledge-base/adrs/`). The change protocol itself is unchanged — documentation refactor, not a loosening of enforcement.
- **`rules/error-handling.md` and `rules/git-safety.md` — two Unbreakable principles now codified in the corpus (rules-audit 2026-06-28).** Rule 8 (fail-fast error handling, typed errors) and Rule 4 (forbidden git commands + safe substitutes) previously lived only in the runtime hook + the global CLAUDE.md; the `rules/` corpus stated neither at the document level. Both are now first-class convention files, referenced from `cycle-implement.md`/`cycle-review.md`/`cycle-release.md` Cross-references and listed in `rules/README.md`. `error-handling.md` ties negative-case testing (`testing.md` § 4.1) to the typed-error contract.
- **`*-patterns` skill consumption is now ENFORCED, not just instructed — a plan can no longer silently ignore an applicable domain skill.** Until now `/to-plan` Step 0 and `/implement` only *said* "MANDATORY"/"SHOULD consult" a matching `*-patterns` skill; nothing failed if the LLM skipped it (the system already *detected* applicability via `assess_confidence.py`/`detect_domain.py`, but never gated on *consumption*). Two layers close the gap (plan `patterns-consumption-gate`):
  - **Plan layer (hard, 100% at the citable boundary):** `skills/plan-confidence/scripts/check_patterns_consumption.py` (+ slice-local matcher `patterns_match.py`, reusing the `assess_confidence`/`detect_domain` shape) flags any `*-patterns` skill whose frontmatter `description:` shares a keyword with the plan title/Goal but is neither cited in the plan body nor overridden in `## ADRs`. Wired into `run_structural.py` as the `patterns_skill_ignored` hard cap (score ≤ 49 → **INVALID**, alongside `coverage_lt_100`/`fabricated_citation`). Escape hatch for a heuristic false-positive: a one-line override ADR naming the skill. Documented in `rules/plan-confidence-golden-rule.md` + `skills/to-plan/SKILL.md` Step 0.
  - **Implement layer (soft, honest about the non-mechanizable):** `skills/implement/scripts/run_validation.py` gains a `patterns_consumption` advisory that surfaces (status `WARN`, never `FAIL`) when a plan-cited `*-patterns` skill does not appear in the changed implementation files — visibility at handoff without forcing a fabricated citation.
  - 7 unit/integration tests (`test_check_patterns_consumption.py` 5 + `test_run_structural.py` 2) + 2 advisory tests in `test_run_validation.py`. Dormant in repos with zero `*-patterns` skills (no false blocks). Honest limit: keyword matching is heuristic and "the code applied the pattern" is not semantically verified — the gate guarantees the skill is *acknowledged*, not perfectly applied.
- **Adopted the official Anthropic `skill-creator` as the standalone skill-authoring tool.** `skills/skill-creator/` (the upstream [anthropics/skills](https://github.com/anthropics/skills) skill-creator) is now the single way to author/improve/eval a skill. It is registered as an AUXILIARY (out-of-cycle) skill in `check_xrefs.py` and creates skills **directly** at a friendly `skills/{purpose}/` (e.g. `pdf-table-extract`) — its SKILL.md gained an "Output location (this project)" section spelling out the path convention, the no-staging rule, and the project's required frontmatter (`name`/`description`/`user-invocable`), plus `user-invocable`/`allowed-tools`/`argument-hint` of its own so `validate_skill_frontmatter.py` passes.
- **The pipeline could schedule an item the registry said was blocked.** The write-back landed before the read-back: `Pipeline.block()` recorded an impediment and nothing ever consumed one, so a restarted session rebuilt its queue and scheduled work that could not move. The queue now comes from `select_backlog_item.py` — the workflow script throws rather than falling back to a literal, because Workflow scripts have no filesystem access and a hand-kept list cannot know what the registry knows. **The literal it shipped with proves the point**: `['B-001', 'B-022', 'B-033']`, and `B-001` is blocked on a sponsor decision in the very registry it was pointed at; a whole run went by without anyone noticing. `from_selection()` bridges the two by DATA rather than by import — `scripts/` does not import from `skills/` anywhere in this kit, and having the scheduler read `BACKLOG.md` would both invert that and give it a second job. Blocked items are carried rather than dropped, so the scheduler can say why one is not running and `unpark()` can bring it back. Defence in depth on top: `_eligible()` now skips a blocked item even in a `Pipeline` built by hand, and `None` is the only value meaning "not blocked" — an empty blocker list means blocked by something with no item to point at, which is a real impediment.
- **`NEEDS_SPLIT` was missing from the pipeline's output schema.** Reported by an agent during the first pipeline run, when the verdict existed in `SKILL.md`'s table and in no code at all: a brief needing a split had to be squeezed into `BLOCKED`, which tells the reader to close gaps that no rewrite can close. The scorer learned to return it this week; the schema had not followed.
- **`planned` was in the contract and in zero items, in every install.** Measured on 2026-08-30 across the ecosystem: 22 `triaged`, 133 `shipped`, 11 `killed` in one project, 3 `raw` and 2 `triaged` in another, and not one `planned` anywhere. The cause was not discipline — **nothing wrote to `BACKLOG.md` at all.** `detect_domains.py` bootstraps it and `backlog_index.py` regenerates a marked block, and that was the whole population of writers, so every transition was a human editing a line by hand and the middle one quietly stopped happening. No gate could see it either: an item that skipped `planned` is indistinguishable from one that has not reached it yet. `scripts/backlog_status.py` is the missing writer, and it refuses what the contract forbids — `raw → planned`, killing without a reason, shipping while blocked.
- **A field in use for months was about to be declared malformed.** The first draft of the impediment parser demanded `B-NNN`. Measured against the real registry before shipping: eight items already carried `blocked_by`, and **seven of them named no item at all** — a sponsor decision, a ratification, a revocation in a hosting panel. Those are real impediments with nothing to point at, and the strict parser reported all seven as broken edges, turning a clean backlog INVALID. The value is now prose that MAY name ids: the ids become verifiable edges, the prose stays an impediment no gate here can resolve. That is the honest split — nothing in this repository knows whether a sponsor has decided — and it is why `stale_block` never fires on a value carrying prose.
- **The preservation fix itself broke an install, twice, in one consumer.** `estudos/joca-asr` keeps a virtualenv inside a project skill, and the file-by-file walk added the day before met it: first `cp -p` refused a symlink to a directory (`.venv/lib64`) and aborted under `set -e`, then walking the tree entry by entry pushed the install past every timeout. Both were introduced by the fix for the seventh defect and both were found by running it, not by reading it. The pass now recurses only where the KIT also has a directory: a subtree the kit does not ship is copied whole with `cp -a` rather than walked, which is simultaneously the correct semantics (that subtree is the project's, entire) and the difference between finishing and hanging. Measured after: 49s, install completes, the project's 7 skills and its `.venv` intact.
- **The sweep declared complete had missed the file a person opens first.** `HOW-TO-USE.md` carried five more layout-blind invocations, found by a consumer's gate after it widened on the two holes reported to it. The omission is the same shape as the defect it was fixing: a sweep called complete while covering the directories its author happened to think of — `skills/`, `rules/`, `commands/`, and not the ecosystem root. **Two root files stay exempt, and the criterion is measured rather than assumed:** `install.sh` copies `HOW-TO-USE.md` and `README.md` into a consumer and copies neither `CHANGELOG.md` nor `CONTRIBUTING.md`. The changelog QUOTES broken forms as evidence — rewriting it would edit history to keep a checker quiet, the one thing a changelog must never do. `CONTRIBUTING.md` addresses someone working ON the kit in its own repository, where the bare path is correct and the layout expression would be noise; it never reaches a consumer, so it cannot mislead one.
- **A command in the kit's own SKILL.md that only runs in the kit's own repository — the eighth face, and the worst.** `python3 skills/acceptance/scripts/extract_acceptance_criteria.py` resolves at the standalone root and nowhere else; in a plugin install the same file is at `.claude/skills/…`, so an agent following the instruction verbatim runs python3 against a path that does not exist. Reported by a consumer session on 2026-08-29, caught by that repository's own `skill-script-paths` gate — 25 invocations across 8 skills, blocking its push. The sweep here found **39 across 18 files**, because that gate looks at `skills/` and the kit also writes bare `scripts/`, and because `rules/` and `commands/` carry them too. **This one is worse than the seven before it.** Six were preservation and two were checkers reading the wrong directory; in every one a MACHINE got the wrong answer and something eventually said so. This is an INSTRUCTION TO AN AGENT: nothing validates it, nothing reports it, and the failure surfaces as an agent improvising around a missing file. Fixed as one sweep rather than one more per-case patch, on the peer's suggestion and on the evidence of the seven before it — each was correct for its case and none generalised. The test asserts the RULE (no shipped instruction may assume a layout), and pins both directions: it must not flag the corrected form, and it must still catch the defect.
- **`hooks/` and `scripts/` had no preservation pass at all — the seventh face, and the first that was not a narrow glob.** Measured by a consumer session in `platform`: the installer removed `hooks/delivery-gate.sh`, `hooks/lib/detect-layout.sh`, `scripts/check-allowlist-sunsets.py` and `scripts/test_e2e_smoke.py`, none of which exist in the kit. Not kit parts being retired — the kit never had them, and two were gates that repository's pre-push depends on. Nothing warned, and the install reported success. **The previous six fixes were each written for one directory or one shape**; this one is written for the rule, and now runs for every copied item: whatever the SOURCE kit does not ship is the project's, wherever it sits and whatever its shape. Sub-paths are preserved with it — `hooks/lib/detect-layout.sh` is two levels down and a flat restore would have dropped it while reporting success, which is the same half-fix as the glob before it.
- **The manifest promised more than it covered, and answered by omission.** Its header reads *"Anything not here is the project's"* while it listed only `agents/`, `rules/` and `skills/` — 92 entries, zero for `hooks/` or `scripts/`. For those two a reader could conclude the project owns a kit file, or the kit owns a project file, and both readings looked supported; the peer session reviewing it reported having done exactly that, marking four files as the project's by ABSENCE of coverage rather than by decision. It now lists `hooks/`, `commands/` and `scripts/` per file, while `skills/` keeps one entry per skill — changing that granularity broke three tests that had nothing to do with the gap.
- **A BLOCKER that failed the review and would not say what it was.** `check_upstream_gate` injects BLOCKERs when no `/code-quality` verdict exists for the slug — fail-closed and correct. But those findings carry `title` and the normaliser only kept `summary`, so the finding lost its name at the entry point and rendered as `### : `: counted, decisive, anonymous. And the verdict JSON goes to stdout, so a caller that redirects it — which a consumer's smoke validator does — was left with an exit code and nothing else. It reached this session described as *"exit 1 with empty stderr"*, indistinguishable from a crash. `title` now normalises into `summary` at the boundary, fixing every consumer of the field at once, and a non-zero exit states its reason on stderr naming the findings that decided it.
- **A file sitting directly in `skills/` was deleted while the directory beside it survived — the sixth face of one defect.** `--force` deletes `skills/` and copies a fresh one, and the preservation pass walked `$ECO/skills/*/`, a glob that matches DIRECTORIES. A project keeping a `SKILLS.md` index next to its skill folders lost it on every reinstall, silently. Measured on 2026-08-29 in `speculative`: 207 versioned lines, removed. It came back with `git restore` only because that repository versions `.claude/`; a project following the policy of not versioning it would have lost the file outright. **Both ends of the pass had the same assumption** — the save loop and the restore loop — so fixing either alone still lost it. The preservation rule has now been stated once and implemented one shape at a time six times over: the routing table, `rules/*.txt`, `settings.json` by key, project skill directories, `an adopter.md`, and loose files. Each fix was correct and none generalised, so the test added here asserts the RULE — *whatever the source kit does not ship is the project's, whatever its shape* — parametrised over four shapes rather than pinning a fifth. The mirror case is pinned too: a name the kit DOES ship is refreshed, because preservation that keeps a stale kit file is a gate running last month's rules.
- **A citation to a kit file was called a fabrication in every plugin install.** `_resolve_code_pointer` joins a pointer to the project root; in the kit's own repository `rules/` and `skills/` sit there and resolve, and in a consumer they sit under `.claude/`. So every pointer to a kit rule or script came back `missing_file` and the gate raised `fabricated_evidence` over paths that are on disk. Measured in `platform`: the kit's own `good-opportunity.md` scored `evidence_pointers 0.0`, hard-capped to 49, verdict INVALID — four pointers, four "missing", all four present one directory down. The fixture was the visible casualty; the defect reaches any opportunity a consumer writes that cites a kit file. A pointer is now tried at the root and then under `.claude/`, and widening WHERE it may resolve does not weaken WHETHER it resolves — a citation to a file nobody wrote is still a fabrication, and the line number is still range-checked against whichever copy was found. **The same defect sat in `check_measurement_targets.py`, in a file that already knew the answer:** it resolves `live-target.txt` by trying both roots on line 98, then checks a measurement target with a bare `.exists()` twenty lines later. A rule stated once and implemented on one of two paths — the shape this kit has now measured seven times.
- **The alignment gate judged the kit's own fixtures.** In a consumer that has a `BACKLOG.md`, the registry check passes and the floor fired on `.claude/skills/plan-confidence/fixtures/good-plan.md` — eight tests red, none of them about the project's plans. The rule needed is already written in `DEFAULT_SKIP_DIRS`: *meta-tooling — /code-quality audits the PRODUCT, not its own skills*. The alignment gate is the same kind of gate and had not learned it. A plan under the tooling directory now falls outside the gate entirely; a project's plans live in `records/` or `knowledge-base/`.
- **The new alignment gate taxed every ad-hoc plan, including the kit's own fixture.** Reported from a consumer on 2026-08-29: `alignment_not_applicable` capped `fixtures/good-plan.md` and turned `test_fixture_good_plan_does_not_trigger_caps` red across seven parametrisations. The fixture was right and the floor was wrong. The floor exists to close a one-line bypass — omit the `B-NNN` and skip the gate — and **that bypass only exists where there is a registry to skip**. In a repository with neither `BACKLOG.md` nor `ROADMAP.md` there is nowhere the item could have come from, so ad-hoc is not a suspicion but the only possibility, and penalising it taxes every hotfix in every repository that does not run this cycle at all. The floor now fires only where a registry exists, found by walking up from the plan and stopping at the repository root rather than trusting a cwd that says nothing about the project under test.
- **A unit test asked the dead-code detector to scan a directory the detector is designed to skip.** Same consumer, reported as "vulture returns zero on a known positive" — which reads as the worst class of defect, green over unmeasured. It was neither. `.claude` is in `DEFAULT_SKIP_DIRS` deliberately (`/code-quality` audits the product, not its own tooling) and the detector passes that list to vulture as `--exclude`. In the kit's standalone repository the positive fixture sits at `skills/code-quality/fixtures/…` and is scanned; in **every consumer** the same file sits at `.claude/skills/code-quality/fixtures/…` and the exclude swallows it. Measured both sides: vulture reports all three symbols from either copy, the detector reports three from the standalone tree and zero from the consumer's, and it was right both times. The test now copies the fixture out to `tmp_path` first, which is what a hermetic unit test of a detector should have done from the start — verified passing in both layouts.
- **`test_layout.py` pinned an exemption by grepping for a string literal.** It broke when those literals became `_ARTEFACT_ROOTS`, and it broke while the behaviour it protects got strictly better — a third layout was added. A test that fails when a refactor preserves its intent is a test that gets deleted, and it would take the exemption with it. It now asserts the resolved layouts instead of the source text.
- **A consumer keeps its audit trail somewhere the kit had never heard of, and every gate went quiet there.** `run_validation.py` resolved artefacts in two layouts, `<project>/.claude/records/` and `<project>/records/`. The `platform` repository uses neither: it declares `<project>/.claude/knowledge-base/` canonical in a rule of its own, written after an audit read the wrong directory and reported one repository as having "0 implementations, 0 reviews, 0 releases" when it had 6, 12 and 8. That repository holds **32 plans in `knowledge-base/plans/` and zero in `records/plans/`**, so all nine `_find_plan` call sites answered SKIP there — including an alignment gate installed minutes earlier, inert on arrival. **Third time in this family**, after `B-NNN` versus `milestone_id` between the two kits; the comment directly beneath `_find_plan` already named the failure mode, having been written for the same defect one layout earlier: *a gate that reports SKIP because it looked in the wrong directory is indistinguishable in the report from one that legitimately had nothing to check*. Widening the search cannot produce a false finding — only stop a false SKIP — which is the asymmetry that makes it safe and that should have widened it the first time. **The write path mattered more than the read path.** A validation report landing in `records/reviews/` inside a project whose trail lives in `knowledge-base/` creates the second audit trail that consumer's rule calls worse than none, silently, on every run. The destination is now chosen by evidence: the first root already holding artefacts wins, and only a project with no trail at all falls through to the kit's own layout. This is one instalment of the migration issue #7 already counted and deliberately declined to attempt — **11 skills hardcoding `.claude/records/`, 24 hardcoding `records/`, none resolving the layout**.
- **The alignment gate was ported to the Cycle as a file, and the behaviour did not come with it.** `check_alignment_gate.py` was byte-identical in both kits and **permanently inert in one of them**. It decides whether a plan is answerable to the gate by looking for `B-NNN` in the prose, which is how the Squad names committed work (`cycle-backlog.md § Item schema`). The Cycle names it `milestone_id: M<N>` in the plan's **frontmatter** (`cycle-roadmap.md § Plan metadata contract`) and never writes a `B-NNN` at all — so every plan in that kit landed in the "not applicable" branch: soft floor 89, never a hard cap, gate off. Copying a script between kits and copying the gate it implements are not the same act, and this is the **fourth** time that distinction has cost a defect here — after the routing table, `rules/*.txt`, and the hook declared in one of two files. It is the first time the test was written before the port rather than after: `test_a_cycle_style_plan_is_recognised_as_committed_work` failed with `applies=False` on a plan carrying `milestone_id: M2`, which is what a grep-and-copy would have shipped. The detector now reads both vocabularies, and reads `milestone_id` **only from the frontmatter** — matching it anywhere would fire on a plan explaining why it is *not* part of a milestone, which is the substring defect `detect_domain.py` shipped where 13 of 13 `lock` matches were `lockfile`. All four states re-proved against a Cycle-shaped plan with zero `B-NNN` in it: `MISSING` → `BLOCKED` → `AWAITING_REVIEW` → `ALIGNED`. Full parity audited file by file: thirteen of fourteen artefacts byte-identical, the fourteenth differing only in `BACKLOG`/`ROADMAP` vocabulary.
- **`--force` deleted the skills the PROJECT itself wrote — the fourth instance of one defect in a day.** `skills/` holds the kit's and the project's side by side, and the non-merge branch `rm -rf`s the directory. Measured on 2026-08-28 while reinstalling across the consumers: **six `an adopter-*` skills disappeared from `appteste` and six more from `website`**, every one a versioned file the project wrote; they were recovered with `git restore`, and a project that had not committed them would have lost them. `rules/an adopter.md` went the same way in both — a fifth face of it, since preservation covered only `rules/*.txt`. Same shape as `rules/*.txt`, `settings.json` and the routing table before it: a rule stated once, implemented on one of the two paths. Ownership is now decided by whether the SOURCE kit ships that skill or rule — no manifest lookup, which also holds on a first install where no manifest exists yet. **Three defects were found while building the fix, each of which would have left it silently inert:** `$MANIFEST` is assigned 380 lines after the point that read it (the guard read empty and never fired); the restore block landed inside `if [ "$item" = "rules" ]` and ran on the wrong iteration; and then landed in the `--merge` branch, which is the one that already worked. Test parametrized over both modes, in both kits.
- **Nothing checked that the implementation log exists, and it went missing four times.** `rules/cycle-implement.md § Output` declares `records/implementations/{slug}-implementation.md` as a deliverable of the cycle, and `run_validation.py` runs fourteen checks — checkpoint schema, checkpoint against git, coverage, test execution, wiring, TDD shape, phase mini-review, acceptance criteria, test obligations — and **not one of them reads that path**. Measured on a consumer on 2026-08-28: six logs for eight completed slugs. One of those logs opens by recording that `/review` had to ask for it, that the same gap had appeared one item earlier, and — in those words — that it would not happen again. It happened twice more. The check reports **FAIL, not SKIP**: `SKIP` is what a gate says when there was nothing to look at, and here the cycle declares there is. The one exception is no plan for the slug — then the cycle did not run and there is nothing to record. Empty counts as absent: a `touch` satisfies the letter and defeats the reason, because the log carries what a diff cannot — what was measured, what lied, and what was discarded. **Control against the real repository: the gate found a fourth omission nobody had noticed, minutes after it existed.** (B-027 of an adopter)
- **`.claude-plugin/plugin.json` becomes a declared version site, after refusing three consecutive releases in a consumer.** The file carries its own `version` and ships with the package, so every release stopped on it as an undeclared *stray* and the operator fixed it by hand. The refusal was **right** — blindly rewriting a version string that might be a fixture or a documented example is a corruption no gate catches — but a refusal that is correct and unresolvable trains people to route around the gate, which is the failure this kit exists to prevent, arriving **through** the gate rather than around it. Control: without the declaration the test fails, with it the test passes.
- **`detect_domain.py` matched substrings and sent a CI fix to a concurrency reviewer.** Measured on a consumer on 2026-08-27: a four-file diff — a GitHub workflow, a Node script, its test and the CHANGELOG — returned `primary_domain: concurrency` with `domain_keywords_matched: ["lock", "actor"]`. Traced to source: **13 of 13** occurrences of `lock` were the word `lockfile`, and **5 of 5** of `actor` were `extractor`. The two words the change was *about* were what diverted it. Routing decides which specialist reads the diff — a concurrency reviewer sent to hunt for races in a YAML finds none and reports clean, while npm resolution semantics and `steps.*.outcome` conditions go unexamined. **A review that ran and looked at the wrong thing is worse than one that did not run, because it produces a verdict.** The boundary is asserted with lookarounds against `[a-z0-9]`, and only on the sides where the keyword itself begins or ends alphanumeric: several do not — `aria-`, `POST /`, `CI/CD`, `command-line` — and `\b` beside a non-word character asserts the opposite of what it reads as, which would make them stop matching silently. The rule is now written where it is read rather than inferred from behaviour. Known limit, stated in place: a path like `package-lock.json` contains `lock` as a whole token and still counts — that is keyword quality, not boundary. (B-015 of an adopter)
- **Configuring mutation testing made every gate cost 22 minutes, and D4 re-read the report zero times.** `_mutation.py` ran `npx stryker run` / `mutmut run` **unconditionally on every invocation** — never reading an existing report, with no threshold that would skip. Measured on a consumer on 2026-08-27: the run took **1347s**, and because `run_structural.py` calls `/code-quality` internally through `cq_invoke.invoke`, **every `/plan-confidence` in that repository came to cost 22.5 minutes**. Mutation testing is a periodic deep check; D4 treated it as a per-invocation gate, and for a project on Stryker's `command` runner — which re-runs the whole suite per mutant, with no per-test filtering — the two are incompatible. **A 22-minute gate is a gate people route around**, which is precisely the failure this kit exists to prevent. A report newer than `mutation.max_report_age_minutes` (default 1440) is now read; older, re-measured; with no report there is nothing to reuse and the tool runs. The point that closes the DoD: **a reused score never appears naked** — it carries its age and how many source files changed since it was written, because age alone is not freshness (a four-minute-old report can already describe a tree two commits back). A threshold of 0 restores unconditional re-measurement. (B-012 of an adopter)
- **The mechanism that closes a BLOCKER existed and the contract never mentioned it — the exact mirror of the `FAIL_SOFT` defect.** `consolidate_findings.py` has scored the verdict from **open** findings since B-056: a finding with `status: CLOSED` stays in the report, keeps its severity, and does not count toward `NEEDS_FIXES`. It worked. But `CLOSED` appeared **zero times** in `skills/review/SKILL.md` and **zero times** in `rules/cycle-review.md`. A consumer session hit exactly the case the mechanism exists for — a BLOCKER fixed and re-verified by the agent that raised it, `ACTIONLINT_EXIT=0` with zero bytes of output — read `NEEDS_FIXES`, grepped the consolidator for `outcome` (the field name the harness's `ReportFindings` tool uses), found nothing, and concluded the capability did not exist. It was about to re-run four review agents at ~200k tokens each to work around something that already worked. **A mechanism nobody can find is worth what an absent one is worth.** The SKILL.md schema now carries the example with the severity preserved, the table of the three possible ways past (closing is legitimate; lowering severity and deleting are the anti-patterns the rule already names), and the note that absence of the field keeps the old behaviour. `test_closed_findings_documented.py` pins both halves: the behaviour, and the sentence that makes it findable.
- **`/review` detects the tree moving mid-review and did not document that it does.** Same class, same review. `capture_tree_state` records HEAD plus a digest of `git status --porcelain` at spawn, re-reads both at consolidation, and emits `tree_contaminated` in the JSON plus a section of its own in the report. Nothing in SKILL.md said so, and nothing instructed against editing the tree during the spawn. Measured on a real run: four reviewers, two noticed independently, reported *"TREE MOVED MID-REVIEW"* and re-measured against the new HEAD rather than inferring — their judgement, not the process's. Detection is the remedy, not the cure: the agents have already spent their budget on a tree that moved.
- **`dismissed_soft_caps` and `undismissed_soft_caps` are now always emitted, one of them empty.** They were mutually exclusive: a full dismissal emitted only the first, a total refusal only the second. The consumer on the full-dismissal path could not tell whether the absent key meant *"nothing to dismiss"* or *"this field is not emitted here"* — and said so. If the person who read the implementation cannot separate design from omission by looking at the output, nobody can. An empty list answers the question; an absent key asks another.
- **The previous fix took the whole scorer down — a `NameError` on the default path.** Wiring the ADR extractor into the merge, I passed `content` at a call site inside `main()`, where that variable does not exist: the only other read of the plan lives in a different function. `run_structural.py` exited 1 with empty stdout for **every plan**, and the default path is exactly the one `cycle-plan` uses as its gate. Reported within minutes by the consumer session, which also named the missing test — and its analysis is the lesson: a unit test over `_merge_code_quality_verdict` **would not have caught it**, because the function was correct and the caller was wrong. The branch where `cq_summary` is truthy had no end-to-end coverage at all, so CI stayed green over a dead scorer. `test_main_runs_end_to_end_with_code_quality_active` covers that branch and was verified failing with the `NameError` restored.
- **A repository without a mutation runner could not start `/implement` by any path, and the rule claimed it could.** `rules/cycle-code-quality.md` § 1 has always promised that *"a `FAIL_SOFT` MAY proceed to `/review` only with an ADR dismissing each soft cap"* — and **nothing in the code looked for, read, or reacted to that ADR**. The demotion in `cq_invoke.py` ran unconditionally. The effect was not cosmetic: golden rule § 2 maps an unconfigured mutation runner to `FAIL_SOFT`, so the repository got `FAIL_SOFT` on every run, forever; that caps every plan at 70 and demotes it to `NON_SHIPPABLE`; and `cycle-plan.md` requires `≥ SHIPPABLE_WITH_CAVEATS` to enter `/implement`. Found by the Claude Code session in an adopter, **blocked on a plan with zero hard caps, zero soft caps of its own, and 91.6 weighted**. A soft cap that cannot be dismissed is a hard cap under another name — dismissibility is the entire difference between the two tiers. A plan now dismisses with a marker (`<!-- ADR-DISMISS-SOFT-CAP: <id>: <reason> -->`), the shape copied from `check_wiring.py`'s `ADR-DEFER-WIRING-B` rather than a third convention; a marker and not prose naming the id, because a plan can name a cap precisely to say it will **not** dismiss it. Partial dismissal still demotes and now emits `undismissed_soft_caps`, naming the gap — before, you had to read `cq_invoke.py:60` to find out why a clean plan was refused. The score cap still applies: quality was measured, and an ADR justifies proceeding, not a better number.
- **The language configuration offered nine and the detectors implemented four.** `rules/code-quality-languages.txt` carried `javascript`, `java`, `kotlin`, `ruby` and `csharp` among its copyable examples; `check_symbol_fab._SUPPORTED_LANGUAGES` holds `python`, `typescript`, `rust`, `go`. Enabling one of the five does not degrade gracefully — it produces `languages_skipped` with `no detector implementation`, then the hard cap `no_languages_audited`, then `INVALID`, on every run, with no configuration that recovers. Measured on a consumer whose repository is JavaScript (11 `.mjs`, zero `.ts`): following the commented example gave permanent INVALID, and the only available workaround was declaring `typescript` on a tree with no TypeScript in it — a false declaration kept honest by an eight-line comment. The five now ship marked `[NO DETECTOR — do not enable]`, and `tests/test_language_examples.py` fails if the list and the detectors diverge again, in either direction.
- **A fabrication gate fired on the kit's own vocabulary.** `check_evidence_citations` captures a bare `D\d+` as an ADR reference, and `D1`..`D5` are the detector names used throughout `rules/code-quality-golden-rule.md` § 5. A plan that listed, among rejected alternatives, *"Disable D4 in the thresholds file"* got `ADR D4 is referenced but not defined` → `fabricated_citation` → `INVALID`, score 49. The finding was false and the plan was correct; it cost a cycle and a rewrite to avoid one token. A fabrication gate that fires on internal vocabulary is what teaches people to ignore fabrication gates. The exemption applies **only** when the reference does not resolve **and** the token names a detector: an explicit `ADR D4` is still a citation, and so is a bare `D4` when the plan actually defines that ADR.
- **`exit 3` stopped being a dead end.** The message said the specialist file did not exist and stopped there — naming the absence without saying what goes inside it. Refusing to **generate** the file stays right, and `agents/README.md` already argues why: it requires build commands *that were run*, and its closing line notes that a derived skeleton *"routes correctly and judges nothing, which reads as a specialist that is ready"*. But refusing to fabricate the invariants is not the same as refusing to say **what an invariant is**. The message now prints the contract's five requirements, hands over the repos already derived for that domain, and says which half is reading and judgement. No new mechanism: it reuses the table already parsed and points at the rule rather than restating it. Proposed by the Claude Code session in an adopter, which decomposed a real 107-line specialist by where its content came from to show that two of the five requirements carry all the value and neither is derivable.
- **The empty-file placeholder survived the first write of data.** `render_rows([])` emits `# (no domain yet — run …)`, and on the next write that line is a comment — so the header-preserving logic kept it, and the file came to say there is no domain on the line immediately above the domains. It did not accumulate (measured: 2 → 2 → 2), so it was cosmetic; but a file that contradicts itself in its own first screen is the kind of thing a reader stops checking.
- **`/backlog-init` never wrote the table `route_domain.py` reads — 165 unroutable items across four consumers.** Found by the Claude Code session running in an adopter, which measured the five consumers of an adopter and reproduced the defect from the outside. The skill's Step 1 ran `detect_domains.py --json` (which only prints), Step 3 said to put the table in `BACKLOG.md`, and `route_domain.py` reads **only** the rule. Following the skill exactly produced `FATAL: parsed to zero rows`, exit 2 — in 4 of 4 consumers, over 165 registered items with real evidence. And Step 3 still prescribed the duplication `route_domain.py`'s own header forbids (*"One table, one truth"*): the single consumer that refused to duplicate ended up with no table at all and equally FATAL. **Obeying and disobeying reached the same place, which is the signal that the instruction was the defect.** Step 2 now writes and verifies with `route_domain`, requiring exit 0; Step 3 points rather than copies.
- **Automatic migration of the tables stranded in `BACKLOG.md`, refusing when the map would come out partial.** It runs at install because that is the only moment the kit is inside the consumer's repository with permission to write — a migration that asks for human action is one the oldest tables never get. It reads three sources in order of strength: the legacy section, the table written into `BACKLOG.md`, and the pairs the items declare. **All-or-nothing per file:** measured on `website`, a four-domain table (one repository, so domains are areas and the second column lists paths) parsed to one, and writing that one would hand over a quarter of the map in a file that reads as authoritative. `count_candidate_rows()` compares what looks like a domain row against what became a domain and refuses the difference, printing the command to derive by hand. Measured across the five: `an adopter-gateways` and an adopter went from exit 2 to exit 3 (table recovered, specialist still to be written — human work by design), an adopter stays at exit 0, and the two with no data to migrate refuse out loud rather than being born with an empty file that looks authoritative.
- **Three smaller defects on the same path.** The dispatcher chose the parser by file suffix, and a `.md` copied to a temporary path loses its suffix — the `.txt` parser then read the markdown document as pipe-delimited rows, and the migration recovered a domain called `bug` from the kit's own example table, reporting it as the consumer's routing; it now decides by **content**. `AGENT_RE` required a path starting with `agents/`, so every specialist written as `.claude/agents/x.md` — the correct path in a plugin install — was read as absent (measured on an adopter: two domains with the file on disk, both parsed as `agent: None`). And the derivation command survived only in standalone layout, which a plugin consumer runs from the wrong root; it now detects the layout.
- **`settings.json` has two owners, and replacing it whole was wrong in both directions.** `boundary-check.sh` allowlists it as *"this project's wiring"* — the kit invites the consumer to edit it — and then `--force` copied its own over the top. Measured across four npm consumers: `deny: Read(**/.env*)` disappeared along with the `allow` entries for `vitest`/`tsc`; reinstalling the kit **widened what an agent may read in someone else's repository**, with no line of output saying so. Keeping the consumer's file whole — what `--merge` did — has the opposite failure: `hooks` points at the kit's scripts, and a stale hook stops enforcing without warning. Ownership is now split by key: the kit owns `hooks`, `statusLine`, `env`, `$schema`; the project owns `permissions` (a union, with the consumer's kept and `deny` inserted ahead of `allow`); and a key the kit does not know is the consumer's and survives.
- **The `.txt` suffix stopped distinguishing project config from kit contract, and preservation froze the contract.** `rules/*.txt` was a fine proxy for "the consumer's configuration" while every `.txt` under `rules/` was theirs. `rules/cycle-phases.txt` broke the proxy: it declares the pipeline's phase chain, the consumer never edits it, and `check_phase_drift.py` measures runs against it. Preserved by extension, a consumer kept the stale chain forever — and the drift gate began comparing against a contract the kit no longer ships. The defect predates the fix above (it came from the `--merge` branch's `continue`), but extending preservation to `--force` doubled its reach. Ownership is now declared **by name** rather than inferred from the suffix: guessing an owner from a filename is what produced this pair of defects.
- **`--force` also erased `rules/*.txt`, the project's own configuration.** Same asymmetry, same file, same cause: the installer states the rule inside the `--merge` branch — *"`rules/*.txt` is the project's CONFIGURATION… Copying the template over it erases local tuning in silence: measured on `speculative`, where the declaration of the project's 9 skills died on the next reinstall"* — and the `continue` that enforces it was written only there. The non-merge branch does `rm -rf rules/` and copies the templates over the top. Measured while reinstalling the kit across the 19 consumers of an adopter: four npm projects lost `deny: Read(**/.env*)` along with their `vitest`/`tsc` allowances, and their enabled languages came back as the blank template — a silent loss, because an overwritten `.txt` looks like a fresh one. The consumer's `.txt` is now saved before the `rm -rf` and restored **after** the template, because local tuning outranks the blank. The test is parametrized over both modes; the first version I wrote passed by accident — it used `typescript` as the marker and the template ships `typescript` in a commented example.
- **Reinstalling with `--force` erased the routing table the consumer had derived.** `install.sh` already said so, at the point where it decides whether to apply the template: *"The routing table is only born empty when there is no derived one to preserve. Overwriting the consumer's would trade a correct map for an empty one — the exact opposite of the defect this template fixes."* The save-and-reinject honouring that sentence was written **inside the `--merge` branch**, and `--force` is precisely the flag a reinstall uses. Measured: a consumer with `svc-a` and `svc-b` derived came back as `_(empty — run detect_domains.py --write)_`, and `route_domain` on either went from exit 0 to unroutable — the table is the one thing in that file the consumer cannot recover, because the kit has no way to know which repositories exist there. The branch's own comment cites the same defect as already measured on `speculative`: it was fixed once, on one of the two paths. Preservation is now a single function called outside both branches, and the test runs parametrized over both modes. An already-empty table is not preserved — re-injecting it would skip the template that teaches you to derive.
- **The kit's own bootstrap command erased the contract the kit enforces in code.** `detect_domains.py --write` replaces the whole `## Domain routing` section — `^##\s+Domain routing\b.*?(?=^##\s|\Z)` under DOTALL runs from the heading to the next `##`. Two things of opposite natures lived inside that span: bootstrap instructions, which expire the moment they run, and **invariants, which never expire**. Running the command `agents/README.md` prescribes took both — measured on an adopter, the section fell from 45 lines to 12. The one that hurts is `One repo, one domain`: `route_domain.py:93-113` still refuses a table with the same repo under two domains, and the script's own header declares itself subordinate to the rule as the source of truth — *"One table, one truth: a copy in code drifts from the rule the moment…"*. What was left is the **inverse of a fabricated mechanism**: a real gate whose contract was written nowhere, exactly what `rules/cycle-rule-schema.md` exists to prevent in the opposite direction. Both invariants now live in `## Routing invariants`, a section of their own — the regex only stops at a `##`, so a `###` would not have done, and that is written into the section so nobody demotes it. The two mechanisms that rewrite that span use the **same regex** — `install.sh` lays down the empty template, `--write` fills in the derived table — so the fix had to reach `rules/templates/domain-routing.md` as well: that, not the kit's rule, is what arrives at the consumer. Moving the paragraphs without cutting the template's copy delivered each invariant **twice** on a clean install, and the copy that dies on the first `--write` is exactly the one a reader meets first. The regression tests run against the **shipped rule** and against the **consumer's cycle** (install → derive), not against fixtures: a fixture would prove the regex behaves and say nothing about the file the other machine receives. Both were verified failing with either half of the fix reverted.
- **The SOP sweep read the bundle's own `index.md` as a malformed procedure.** `index.md` and `log.md` are OKF reserved names at every level of the hierarchy — listing and history, never concepts. The checker swept `*.md` and reported three findings against a file that is correct per the spec. A checker that fails on correct input is the false positive this ecosystem treats as worse than no checker at all. 1 test.
- **`validate_skill_frontmatter.py` approved frontmatter no parser can read, and audited whichever project the shell was sitting in.** Two defects in the 112-line script named after the job. It does not import `yaml`: it matches `key: value` with a regex, so a `description:` carrying an unquoted colon passed as **"Validated 39 skills: 0 errors, 0 warnings"** while `test_e2e_smoke.py` — loading the same block with `yaml.safe_load` — reported `mapping values are not allowed here`. Two validators over one artifact, disagreeing about whether it is readable at all, and the blind one is what `install.sh` and the docs point at as the frontmatter gate. It also had **no `--ecosystem-dir`**: the root came from `find_ecosystem_dir()` on the cwd, the same wrong-target defect `check_xrefs.py` was fixed for on 2026-08-03. Both closed; 3 tests, one of which parses all 39 of the kit's own skills.
- **D1 audited the kit installed inside the adopter's project, and failed them on it.** `_shared.DEFAULT_SKIP_DIRS` has carried `.claude` since it was written, with the comment saying why — *"meta-tooling — /code-quality audits the PRODUCT, not its own skills"* — and `enumerate_source_files` honours it. D1 did not: it handed `manifest_dir` to vulture and let vulture walk everything below. Measured 2026-08-27 in a freshly installed demo project (three source files of its own) at `vulture.min_confidence = 60`: **44 findings — 38 in `.claude/skills`, 4 in `.claude/scripts`, 2 in the adopter's code** — and `FAIL_HARD` on their strength. It is the same defect the stop-hook had and fixed (*"107 lines of warning about `.claude/skills/**/*.py` against ONE real finding"*), never propagated to this gate. After the fix, the same run: **2 findings, both real, verdict still `FAIL_HARD`** — which is what a gate about the product should say. 2 tests.
- **`compute_acceptance_verdict.py`'s `main()` had no test, and instrumenting it broke it.** Every assertion in that file called `compute()` directly, so the entry point was unexercised: a suite green over a script that could not start. The `AttributeError` was mine and lived for minutes, but the hole it fell through was there all along. `main()` is now exercised end to end, including that the emitted event carries the verdict the script printed rather than a second opinion.
- **No threshold from `code-quality-thresholds.txt` reached any detector.** The orchestrator called `load_thresholds()` for the side effect of validating the file and discarded the result, with an inline note saying "detectors use hardcoded defaults in v0.1" — every declared `vulture.min_confidence` or `mutation.score_floor_low` was inert. A configuration file that does not change behaviour is worse than none: it reads as a control that exists.
- **The JSON's two cap fields said things that were not so.** `hard_caps_triggered` received ALL identifiers when the verdict was FAIL_SOFT — a dismissible cap with an ADR showed up as a block, and a real HARD would hide in the middle of the list — and `soft_caps_triggered` carried the `allowlist_key`'s tail, which in D3 is the SYMBOL NAME (`flush_caches`), not the stable identifier. Golden rule § 1.4 requires stable identifiers in both: they are what an allowlist is written against and what two runs are compared by.
- **The audit report did not list the soft caps.** `/review` needs them to demand one ADR per cap, and had nowhere to read them from.
- **The kit's coverage floor sat at 40% while it demanded 80% of consumers**, with the divergence declared nowhere. Measured: `scripts/` is at 58.4%. The floor moves to 55 (locks regression without demanding work this commit did not do), with the target of 80 and what is missing to get there — three files with no test at all — written next to the number.
- **Five public exports in this repository had no consumer**, and `init_quality_gates.py`'s `__all__` even listed two private names. D3 flagged them as soon as it started existing.
- **The stop-hook hit its own 120 s timeout, and a dead hook blocks nothing.** The study zone — `knowledge-base/references/` and `tools/`, which the kit declares read-only third-party material and which `validate-command.sh` protects from writes and copies — was never excluded from the audited file set, and `install.sh` does not touch the consumer's `.gitignore` by explicit decision, so those files arrive untracked and unignored: the normal path, not the exceptional one. Measured 2026-08-26 in an adopter with 500 files from a cloned peer project: **16,944 ms and 517 lines of output**, 500 of them TDD warnings about code nobody in this repository wrote. On top of that, a `find` over the entire tree **per changed file** (39 ms each in a repo of 13,000 files, without pruning `.git`, `.venv` or `__pycache__`) — the gate scaled with the size of the REPOSITORY instead of the size of the change. The zone left the set, for the same reason and on the same line where `.claude/` already left; the test-name index is now built **once per unit** and queried in memory. After: **30 ms, zero lines** in the same scenario, and the 56,000-file repository that used to blow the timeout takes 1.1 s.
- **The reference-leakage detector walked the whole zone before knowing whether there was anything to compare.** `check_reference_leakage.py` runs on every Stop, before the hook's early exit, and it listed the zone's files BEFORE building the index of changed files — which is what decides whether any work exists at all. A session that wrote nothing paid the full walk of thousands of third-party files to arrive at "nothing to compare". The order was inverted, and the walk now prunes `.git`, `node_modules` and the build output the peer project's clone brings with it and which is not its code.
- **Two sweeps descended into the whole of `node_modules` only to discard it.** `run_code_quality._enumerate_source_files` and `arch-check._ts_sources` did `rglob("*")` followed by a filter: the right answer by the wrong route. Measured on a repository of 56,128 files, 40,000 of them in `node_modules`: **326 ms against 0.2 ms** pruning during the walk — once per enabled language. It is the same fix this changelog already records in `check_wiring.py` (1,080 ms to 13 ms), which had not been propagated.
- **D2 paid 5 s per unknown package, on every run, forever.** The queries to PyPI, npm, crates.io and the Go proxy are serial, with a 5 s timeout, and an ambiguous result is not cached — correctly, because a network failure is not proof that the package does not exist. What was missing was a limit for the SET: on an offline machine or behind a proxy, 100 imports cost 500 s of waiting that never became an answer. After three consecutive failures the detector declares the network unavailable and returns the SAME ambiguous verdict as before, without the wait; one hit resets the counter, so that a blip does not switch D2 off for the rest of the run. Along with it, a registry 500 stopped becoming "the package does not exist" on the crates.io path — that was a HARD finding derived from unavailability, exactly what EC-2 exists to prevent.
- **The smoke test wrote bytecode inside the target it had just installed.** `check_python_syntax` used `py_compile.compile`, which writes the `.pyc` as a side effect: 267 ms of the script's 693 ms, and the reintroduction of the cache `install.sh`'s copy had just excluded — the reason `prune_caches` exists. Checking syntax requires writing nothing; `compile()` answers the same question without touching disk.
- **The SOTA audit stopped approving work it did not execute.** D3/D4 unavailable now emit `SOFT_CAP` instead of vanishing; the installed settings artifact is regenerated and verified in CI; release detects and updates TypeScript, Python and Rust manifests, with Go explicitly tag-only; public versions were aligned at `0.1.0`; CI gained an E2E smoke test, generation-drift checks, Ruff, ShellCheck, a Python 3.10–3.13 matrix, behavioural hook tests and a coverage baseline. Static cleanup removed dead imports and variables and made deliberate exceptions explicit.
- **An install from a clean clone was born broken.** `.gitignore` hid the whole of `agents/**`, including the `README.md` that describes the routing mechanism and that `scripts/install.sh` copies unconditionally. On any machine but the maintainer's, `.claude/agents/` arrived EMPTY and `check_xrefs.py --strict` exited 1, because `rules/cycle-maintenance.md` cites that file. On the maintainer's machine, green — the nine `.md` files were on disk, ignored. The eight domain specialists, which remained outside git and opt-in, were removed — see § Removed.
- **CI saw that defect and stamped it green.** `check_xrefs.py` without `--strict` prints the finding and exits 0 — the output carries the WARN line and, right below it, `Overall: PASS`. The installer always called it with `--strict`; the workflow called it without. The same commit produced `check_xrefs.py: FAIL` on install and approval in CI.
- **The installer promised to skip caches and carried 342 of them.** The header declared "skips the source repo's history: caches, artifact dirs"; the implementation was `cp -r`, which does not read `.gitignore`, and the caches live inside `skills/`. 887 files reached the consumer against 496 tracked — almost half of what was installed was not the system. The copy now goes through `tar` with exclusions, and the final validation, which runs Python on the target and used to rewrite `__pycache__` there, now cleans up what it generated. Measured after: 463 files, zero caches.
- **Installed through the native mechanism, no gate ran — silently.** The manifest sat at the root instead of `.claude-plugin/`, there was no `hooks/hooks.json`, and the hooks resolved through `$CLAUDE_PROJECT_DIR/.claude/hooks/`, a path that only exists in copy mode. `detect-layout.sh` then ended with `exit 0` without printing a line: `stop-validation.sh` and `sessionstart-context.sh` exited 0, mute. A silently disabled gate is indistinguishable from a gate that approved. Now a `CLAUDE_PLUGIN_ROOT` without the kit WARNS, and `CLAUDE_DEBUG_HOOKS=1` prints the resolution.
- **The consumer inherited another ecosystem's routing table.** `rules/cycle-backlog.md` shipped with eight domains pointing at twenty repositories the consumer does not have — and the file itself already recorded the consequence measured on 2026-08-18: 88 items with real `file:line` evidence, all refused by G1 as `unroutable_repo`. The section now ships empty, with the command that derives it; a table the consumer already derived is never overwritten. `acceptance-target.txt` gained a template, and the live-target declarations stopped citing the originating domain.
- **Three fixes that existed only inside an adopter's gitignored `.claude/` now exist in the kit.** A session in that project had been altering the system instead of merely using it — and that `.claude/` is not tracked, so each fix protected exactly one machine. The three: (1) the **CHANGELOG gate stops demanding an entry for a comment-only commit** — a change with nothing to announce to the consumer invites the two worst outcomes, a fabricated line in the public contract or the override, and reaching for the override to satisfy a question the gate should not have asked is how a gate stops being read; the filter is conservative by construction, removing only lines that are unambiguously comment or blank, so a false negative over a real change is impossible. (2) The **`ITEM_VERIFIED_LOCAL`** verdict, for an item whose fix changes only untracked files: `ITEM_SHIPPED` would be false because nothing shipped, and leaving it `planned` forever makes the record report finished work as pending — the test is mechanical (`git check-ignore -q` over **all** changed files), not rhetorical. (3) Why an `[Unreleased]` with only `Changed` **pauses and keeps pausing**: under 0.x it maps to `minor` or `patch` depending on a fact the section does not contain, and the pause carries the question instead of a guess.
  **One of them was deliberately not harvested:** `§ 3.1` on Ink rendering (`ink@7.1.0`/`react@19.2.7`, boundary guard, measured with `ink-testing-library`) is that project's domain knowledge — the kit mentions TUI nowhere, and bringing it here would repeat the very defect this session has been undoing. And the exclusion of `scripts/` from the CHANGELOG gate was left out: there it is build tooling, here it is production — the kit is made of scripts.
- **The drift detector accused 11 files where there were 4 — and the lesson for not doing that already existed in the other script.** Measured on an adopter: `check_install_drift` reported 7 `DIVERGED` + 4 `INSTALL_AHEAD`, all announced as "needing a human". Five of them were merely **old versions of the kit itself** — `install.sh`, `check_xrefs.py`, `code-quality-golden-rule.md` (the 4-field allowlist format the kit already swapped for 6), `code-quality-allowlist.txt` and `cycle-discover.md`. There the consumer changed nothing: it fell behind. `sync_consumers` learned that distinction when 231 false `local-change` results became 119 by consulting `git rev-list --all -- <path>`; the lesson stayed in one script and not the other. There is now a `STALE` class, and the report separates what needs a decision (4) from what needs a `checkout` (5). A detector that accuses 11 when there are 4 teaches you to ignore it, which is its own declared reason for existing.
- **`settings.json` was compared against the wrong file, and `agents/<domain>.md` was treated as work to harvest.** The consumer receives `settings.plugin.json` AS `settings.json`; the detector compared it against the kit's `settings.json`, which is the development one and points the hooks at a different path — identical as JSON, reported as divergent, across all 41 consumers. And `agents/speculative.md` showed up as `INSTALL_AHEAD`: a specialist describing the consumer's own repository, offered up to be harvested INTO the kit. Both fixed; `agents/README.md` stays in scope, because it describes the routing mechanism and not a domain.
- **Installing over the top undid the previous install — including the routing.** Three paths destroyed consumer decisions on every `install.sh`. (1) `rm -rf "$ECO/agents"` outside `--merge` mode: it took with it the specialists the PROJECT wrote, which are a copy of nothing in the kit and exist nowhere else. (2) The unconditional `cp` of `agents/README.md`, which overwrote the README after someone adapted it to list the project's agents. (3) The worst, because silent: the **routing table** is project configuration and lives in `rules/cycle-backlog.md`, a `.md` the kit owns and overwrites. Measured on `speculative` — reinstalling restored the originating ecosystem's table and `route_domain speculative` went from `exit 0` to `exit 1`: the project stopped routing items about itself, and the install reported success. Now `agents/` is never deleted in any mode, an existing README is preserved, and the `## Domain routing` section is extracted before copying and reinjected after — the rest of the rule still arrives updated from the kit. Discovered by reinstalling twice to PROVE an answer instead of asserting it.
- **The `theo` ecosystem's eight specialists stop being installed by default** (grill `kit-domain-agents-install`, decisions 1 and 4). They describe repos that exist in one ecosystem only, and they went to all of them: `engine-go` covers `theo`, `data-plane-ts` covers six TypeScript products. Measured across 41 installations: **19 already lived without them and nothing broke**, 11 write their own, and the coupling that justified them disappeared when the table started being derived from the project. `--with-domain-agents` brings them to the repos of that ecosystem which still depend on the kit (`search-api` does not track them). The `README.md` still always ships: it describes the routing mechanism, not a domain. The manifest stopped listing what it did not install — a manifest that lies is worse than none, because it is where the consumer reads what is theirs.
- **A specialist skeleton, so the route stops pointing at nobody** (decision 2). Deriving the table without resolving the specialist trades "another ecosystem's table" for `BROKEN ROUTE — the table names an owner who does not exist`; **11 consumers were already in that state**. `render_specialist()` generates the file with what was measured — name, repos, detected languages — and **only that**: commands, real findings, false positives and invariants stay present, empty and marked, because a file without those sections looks like a finished specialist. `check_xrefs` reports a WARN while the marker exists and falls silent on its own once someone fills it in.
- **`agents/*.md` gets out of both synchronizers' way** (decision 5). Out of `sync_consumers`'s prefixes (the kit pushed the eight back on every sync, undoing the consumer's cleanup) and into `check_install_drift`'s consumer-owned scope (which reported `agents/speculative.md` as `INSTALL_AHEAD` — work to be harvested INTO the kit, the opposite of what it is). The `README.md` stays in scope for both.
- **`settings.json` was compared against the wrong file.** The consumer receives `settings.plugin.json` AS `settings.json`; `check_install_drift` compared it against the kit's `settings.json`, which is the development one and points the hooks at a different path. Measured on `speculative`: identical as JSON, reported as `DIVERGED`. It would have accused that across all 41 consumers, forever — and a report that always accuses is a report nobody reads, which is the reason the detector exists at all.
- **The wiring gate counted a duplicated checkout as production callers, and neither `.claude` nor the worktree registry closed the case.** The previous entry in this CHANGELOG describes the `.claude` exclusion — it holds and remains in `exclude_dirs`, but `--exclude-dir` matches a NAME, and a copy of the repository can be called anything. Measured on an adopter, symbol `SlashMenuList`: clean tree **5 callers**; with a worktree in `.claude/worktrees/` still 5 (the name-based exclusion working); with an arbitrarily named worktree at the root, **10** — and all three sampled callers inside the copy, none in `src/`. Pillar (a) is the non-negotiable one, so a symbol whose only "caller" lived there would pass a gate designed to prove it is wired to production.
  The first fix asked `git worktree list --porcelain` which checkouts are nested. **Reviewing that fix knocked it down**: that registry is authoritative for LINKED worktrees and knows nothing about a CLONE, because a clone is another repository with its own registry. Measured: `git clone --local . ./nested-clone` took pillar (a) from 5 back to 10, with the entire sample inside the clone — the original symptom, restored through a door the fix did not close. `git check-ignore` would not catch it either: the clone is not ignored.
  The signal that covers both is git's own layout convention: a checkout carries a `.git` at its root — measured, an 88-byte FILE pointing at the parent in a linked worktree, a DIRECTORY in a clone. The call to the worktree registry was **removed** rather than kept alongside: two definitions where one suffices is the duplication this repository has already paid for once. Detection power: making the helper return `[]` fails 2 of 12 tests — the worktree case AND the clone case.
- **That same fix cost 1080 ms per call, in a gate invoked twice per check.** `rglob(".git")` over the real project measured 1080 ms, against 410 ms to walk the whole tree's 50,956 entries; with ten symbols in a slice, more than twenty seconds of pure directory walking. This is not a performance footnote: a gate slow enough to annoy is a gate people find reasons to skip, and this repository already has the record of what that costs. Pruned by two rules — a directory that IS a checkout is not descended into (a checkout inside another is already covered by the outer one) and `node_modules` and `.git`'s innards are skipped (dependencies bring their own repositories, and `_grep_symbol` already excludes them from the RESULTS). Measured after: **13 ms**, 83x, with both forms still excluded. The test pins the SHAPE the speed comes from, not a duration — a timing assertion is a flaky test on a loaded machine (an adopter B-081, B-104)
- **The install took a consumer's gate from APPROVED to REJECTED.** `speculative` has its own auditor — `scripts/audit.py` walks `.claude/skills/*/SKILL.md` and demands the Agent Skills spec of each, because its 9 skills are domain specialists with numbers traceable to the `wiki/`. Installing the kit puts 37 more skills in that directory, and the auditor started measuring them against the standard of the 9: measured with `git worktree` at the previous HEAD, the verdict was `APPROVED — no blockers` before and `REJECTED` after, with blockers over `review`, `to-plan` and `discover-execute`. The install itself was **purely additive** (46 untracked, zero tracked files modified) — the damage was only this: a project's gate measuring code that is not the project's. Now `install.sh` writes `.claude/.kit-manifest.txt` with the 91 paths the kit brought, and any consumer auditor can tell what is theirs. Without a manifest the only way out would be to guess by name.
- **`--merge` overwrote the project's configuration in `rules/*.txt`.** It adds without deleting, but it copies the template over a file of the same name — and `rules/*.txt` is where configuration lives: enabled languages, live target, allowlists, and now also the declared auxiliary skills. Measured in this session: `speculative`'s declaration of its 9 skills was written, and the next reinstall erased it. In `--merge` mode, a `rules/*.txt` that already exists in the target is now preserved and announced (`kept (yours)`); the `.md` files keep being updated, because they are the normative contract and the kit owns them.
- **The project's skills declared in a rule, instead of edited inside the validator.** `AUXILIARY_SKILLS` is a constant in the body of `check_xrefs.py`, and a consumer with its own skills had no way out but to edit it — `theo` did exactly that, and the edit only survived this session's sync because the comparison was done file by file. The new `rules/auxiliary-skills.txt` is read by **both** checks (`no_orphan_skills` and `skill_has_cycle_contract`); exempting only one is the half-exemption the code itself already documents as a false fix. Measured on `speculative`: 9 own skills produced 18 WARNs — 100% of the checker's warnings — and since `install.sh` invokes it with `--strict`, the entire install was reported as a failure because of the consumer's design
- **The wiring gate counted callers inside agent worktrees, and the non-negotiable pillar could pass over a copy.** `check_wiring.py` had an exclusion list (`node_modules`, `.git`, `dist`, `build`, tests) but not `.claude` — and the Agent's `isolation: "worktree"` mode creates COMPLETE checkouts of the repo itself in `.claude/worktrees/agent-<id>/`. Measured on an adopter on 2026-08-19: **10 callers reported for `SlashMenuList`, about half of them the same files seen twice** — once in `src/`, once in the nested copy. Pillar (a) is the non-negotiable one (`rules/cycle-implement.md` § Wiring triad), so a symbol whose only "caller" lived in a stale worktree would pass a gate designed to prove it is wired to production. `.claude/` is an installed plugin and never project source, so excluding it wholesale is correct and not a worktree workaround. Applied at both search sites — pillar (a) and pillar (b) (an adopter B-081)
- **A code-quality audit that ran zero detectors could report `PASS`.** With an empty or misconfigured `code-quality-languages.txt` — or with every enabled language skipped for a missing manifest — `findings` came out `[]` and `compute_verdict([])` returned `PASS` in silence. That `PASS` is consumed as a HARD gate by `cycle-review.md` (admits on PASS / PASS_WITH_CAVEATS) and by `skills/implement/scripts/run_validation.py` (fails on FAIL_HARD / INVALID): both were reading a constant. Measured on 2026-08-18: `languages_audited: []` returning in under a second with `verdict: PASS`. A `PASS` verdict with no language audited is now forced to `INVALID`, with the stable id `no_languages_audited`. **The fix existed on a single machine, inside an ignored `.claude/`, and was in no commit at all** — this is the commit that makes it travel (an adopter B-092, B-133)
- **`sync_consumers.py` — propagating a delta to 42 consumers without erasing local improvement.** While updating `theo` in this session, five files had diverged and the divergence was **improvement that existed only there**; copying over would have erased three of them. It only did not because the comparison was done file by file, by hand — discipline that does not survive 42 targets. The script classifies each file as `identical` / `new` / `update` / `stale` / `local-change`, and **deliberately does not merge**: an automatic merge across 42 repos is the way to silently spread exactly the error it exists to prevent. Two refinements measurement forced: (1) **being behind is not being modified** — the first dry run marked 231 `local-change`, `install.sh` in almost all of them, and it was not local work, it was an install made from an old version; consulting the kit's history (`git rev-list --all -- <path>`) separated 112 merely stale files from the 119 genuinely modified. (2) **the delta has to be closed** — the synced files cite other kit rules, and in a stale consumer those do not exist: 13 of the 40 targets ended up with `check_xrefs` red citing `rules/knowledge-base-location.md` and `rules/live-target.txt`. Closure copies **only the missing rules**, never overwrites the present ones — the `rules/*.txt` are the project's configuration, and copying over would destroy local tuning
- **The consumer population was 4× larger than the answer that had been given.** Eleven projects had been reported as carrying the kit — the ones that had been installed by hand. A sweep for `.claude/skills/implement/` found **42**, including the 20 repos under `platform/` and nine more outside the `theo` ecosystem. 40 were updated; the 2 under `backup/` were left out, because a snapshot that gets updated stops being a snapshot.
- **`/backlog-init` refused to run in a standalone project, and told you to create the record outside it.** Step 0.2 was `test "$(find . -maxdepth 2 -name .git -type d | wc -l)" -gt 1 || FATAL "no umbrella detected — run at the workspace root"`. In an independent repository that means writing `BACKLOG.md` in the directory above — which, in an adopter, groups **ten independent repos, each with its own cycle**, and is a repository of nothing. The record for all ten would go somewhere nobody versions. an adopter already worked around it by hand: it has 88 items about itself in its own `BACKLOG.md`, against the rule. Now `detect_scope()` answers `umbrella` (the directory is not a repo and groups the ones that are) or `single-repo` (the directory IS the repo), and **both are valid record roots**. The criterion is whether the root *is* a repository, not the count of `.git` below it: the old guard counted depth 2 and a project with a vendored clone inside passed as an umbrella. The principle the rule defends ("one question, one place to look") never required an umbrella — it requires one record per **governed scope**, and a standalone repo is a scope
- **Topology says what exists; it does not say who owns it — and the record already knew.** The first version of `detect_domains.py` derived from layout alone: a single repo becomes one domain. Measured on an adopter five minutes later, the record **already declared five domains** — `sdk-core`, `repo-platform`, `sdk-satellites`, `edge-cli-acp`, `memory-adapters` — and none of them is visible on disk: nothing in `packages/sdk-pty` says it is a "satellite". A detector insisting on layout would impose the wrong granularity with the air of a measurement. `--from-backlog` reads the (`domain`, `repo`) pairs the items carry and builds the table from them; when the record exists, that is the source. Two invariants alongside: a repo declared in two domains **fails** instead of generating an ambiguous table (routing would come out by iteration order, and the same item would go to different places on different runs), and a repo the record cites and disk does not have stays **in the table, named** — deleting it would hide the divergence, which is the decision `theo` already made by hand in its "Repos an inventory names but disk does not" section
- **The routing table is project data, and it lived inside the template.** `rules/cycle-backlog.md § Domain routing` embedded the `theo` ecosystem's 8 domains (`engine-go`, `control-plane`, `db-engine`, …), and **every install carried that table along**. Worse: `backlog-init` told you to fit the target's repos *inside* those 8, with the explicit instruction not to "invent a ninth domain" — in a project that is not `theo`, no repo fits. Measured on an adopter: **88 backlog items with measured `file:line` evidence, all `BLOCKER/unroutable_repo`** — 68 citing `packages/sdk`, 14 an adopter, and four more packages. The gate was right in what it said (*"I do not know who to send this to"*); the table was what was wrong. Now `detect_domains.py` **derives the table from real topology**: an umbrella with cloned repos becomes one domain per repo; a single repo becomes ONE domain named after it, and each monorepo package enters addressed by path (`packages/sdk`) — the form the table already supported and documented in `control-plane/dashboard`. One domain per package would create six specialists where there is one SDK. What is **not** derived is the specialist: the script names `agents/<domain>.md` and stops there, because `route_domain.py` exits 3 when the agent does not exist on disk — generating the table without it would trade one block for another. The test that backs this does not check format: it feeds the generated table to `route_domain`'s real parser and demands that `packages/sdk` routes.
- **`repo: packages/sdk` in an item file reached the router as `packages`.** The table always accepted a path — `control-plane/dashboard` is documented as *"one repo, two domains, resolved by path"* — but the ITEM extractor (`ITEM_REPO_RE`) stopped at the slash. Routing failed over a repo nobody wrote, and only in a monorepo, which is where nobody had looked yet: 68 of an adopter's 88 items are in that form
- **`/backlog-item`'s new instruction told you to run a script by a path that only exists in one of the two layouts.** The freshly written Step 2 invoked `python3 skills/backlog-item/scripts/check_intake_gates.py`, a form that resolves in the standalone layout and breaks in the plugin one (`.claude/skills/...`). I was not the one who caught it: **`theo` caught it**, with a guard it built itself while fixing nineteen instructions with the same defect (B-120), and which was written explicitly to refuse the broken form *"including if it comes back through the next tooling sync"* — which is exactly what happened. It now uses the prefix `ECO=$([ -d .claude/skills ] && echo .claude || echo .)`, the convention the consumer created and the kit still lacks in the other skills
- **The test-execution gate SKIPped on the ecosystem's largest Go repo.** Discovered while updating `theo`'s install: `detect_languages` answered `[]` in an entirely Go repository, because the manifest list only knew `go.mod` and `theo` uses **`go.work`** — a workspace, whose root is not a module. The effect was the original hole back again, in the same shape: no applicable runner, `test_execution` at SKIP, and the silence looking like "nothing to check". Worse, it is a trap this kit had already catalogued: `/arch-check` hit it in 2026-08 (*"`go list ./...` at a workspace root exits with `directory prefix . does not contain modules listed in go.work`"*) and the lesson was not in this module. Now `go.work` counts as a Go manifest, and `go_workspace_modules()` reads the `use` directive to run `go test ./...` **in each module**, with one deliberate exclusion: paths that leave the repository (`../contracts`, which `theo`'s `go.work` lists) belong to a sibling repo with its own gates and are not audited from here. Measured on `theo`: 7 internal modules detected, 1 sibling discarded
- **The mini review's check 4 was an unconditional `SKIP` that read as a verification.** `_invoke_code_quality_on_delta` always returned `SKIP` — `cq_invoke` scores the whole plan, not a subset of files, so no delta-scoped audit ever ran. The honest half was admitting it in the docstring; the dishonest half was the line `### 4. Code-quality delta — status: SKIP` in the boundary report, indistinguishable from a check that ran and found nothing. Step 4.7 announced four checks and delivered three. In its place goes the question the SKIP left open and the boundary answers for free: **will the Step 5 audit look at these files?** A modified file whose language is not `ENABLED` in `rules/code-quality-languages.txt` is seen by no detector — not at the boundary, not in Step 5 — and now comes out named (MEDIUM, `delta_language_not_audited`). It is the same class D5 chases (an auditor that never runs reports success), which had no detector at the phase boundary. Without the rule file the check is a genuine `SKIP`: guessing which languages a project audits would produce the invented finding the kit refuses everywhere
- **Intake's G1 and G2 were mechanizable and were not mechanized.** `/backlog-item` declares five hard gates and shipped **not a single script**, while the following phases carry 16 (`plan-confidence`) and 13 (`implement`). G3/G4/G5 are judgement and stay conversational — that is the right design, and the evals cover it. G1 and G2 are not: `scripts/route_domain.py` already existed, with 23 tests, and the skill **did not call it** (it instructed an inline `python3 -c`), and G2 was a `grep` whose execution nobody verified afterwards. A gate that depends on the agent remembering is an intention. The new `check_intake_gates.py` runs both: G1 delegates to the router (a table parsed from `cycle-backlog.md`, one table and one truth) and refuses with `ITEM_REJECTED`; G2 searches the record for each term **plus the repo name** — always added, because it is the term that collides most in a record spanning 21 repos — and returns each matched block with its status and the action the rule prescribes for it (`ITEM_MERGED` / `supersedes` / `regression_of`). **Running the script IS the evidence that G2 happened.** The script does not decide: a keyword hit remains a candidate, not a verdict, and automating the merge would invent wrong merges. The block parser is imported from `backlog-review` instead of duplicated — a second regex would diverge silently
- **The CI the configuration claimed existed.** `pyproject.toml`'s comment said that *"the 64 per-slice test files run in CI via `scripts/run_slice_tests.sh`"* — and **there was no workflow at all in this repository** (only inside the vendored `codex-plugin-cc/`). Every gate the kit ships was green because someone remembered to run it by hand; nothing failed a push. Now `.github/workflows/ci.yml` runs, on push and PR to `workspace`/`develop`/`main`, `check_xrefs.py`, `validate_skill_frontmatter.py` and `run_slice_tests.sh` (one isolated process per slice). And the number left the comment: it said 64 while the tree had 80 — a count nothing recomputes is a claim that rots
- **A normative anchor pointing at nothing, and the validator that did not look there.** `rules/cycle-acceptance.md` and `rules/cycle-release.md` anchored the single-flip invariant in *"`cycle-roadmap § Hard gates`"*. `cycle-roadmap` was replaced by `cycle-maintenance`, which **has no `## Hard gates` section** — and six more places cited the same non-existent section. `check_xrefs.py` reported `PASS` for two reasons: Check 7 swept `skills/**/SKILL.md`, `skills/**/*.py` and `scripts/**/*.py` and **skipped `rules/` entirely** (a rule citing a rule was the blind spot), and nothing checked a cycle citation **by name** — Check 7 matches paths (`rules/<file>.md`), and `cycle-roadmap § Hard gates` is not a path. The invariant itself never stopped holding (`flip_milestone_checkbox.py` is still the single implementation), so the cost was one of authority: anyone reading what the gate promises would not find the section. The invariant is now declared where the flip happens — `cycle-acceptance § Hard gates` — and `cycle-release` keeps a pointer to it.
- **Check 7 widened + a new Check 8 in `check_xrefs.py`.** Check 7 now sweeps `rules/*.md`; Check 8 (`cycle_reference_resolves`) requires every `cycle-<name>` **in backticks** to resolve to `rules/cycle-<name>.md` or `skills/cycle-<name>/` — in backticks only, because loose text ("a cycle-level decision") would produce noise while naming nothing. Existence is measured **on disk**, not against the cycle list: `cycle-rule-schema.md` is deliberately outside that list, being meta-documentation, and citing it is legitimate. Together they found 10 broken references on the first run, including one no manual review had spotted: `rules/cycle-judge-codex.md` told the `:discover` stage to consult `rules/discover-blueprint-golden-rule.md`, a file that exists in other installations and **never existed in this ecosystem** — corrected to `discover-plan-golden-rule.md`. Also fallen: `cycle-roadmap § Plan metadata contract` (a contract that exists nowhere) in `/auto-plan` and four super-loop pointers in `/analysis` and its golden rule
- **`READY_TO_MERGE_WITH_FOLLOWUPS` existed on paper only — and the gate it carried, nowhere at all.** The verdict was defined in `rules/cycle-review.md` and `rules/cycle-rule-schema.md`, and implemented in zero places: `consolidate_findings.py`'s `_classify_verdict` still sent `> 2 HIGH` to `NEEDS_FIXES` without exception, `/review`'s `SKILL.md` did not know the token, and `/auto-plan` had no transition for it — while `rules/cycle-auto-plan.md` required `= READY_TO_MERGE` to release. An unreachable verdict whose appearance by hand would leave the orchestrator in undefined behaviour at the gate preceding the merge. The classifier now emits it, and **only** when every HIGH is a recorded followup: an id named under the plan's `## Followups` section (read via `--plan`) or an issue reference `#NNN` in the finding's own `recommended_action`. **Fail-closed**: without `--plan`, nothing was proven recorded and the verdict is `NEEDS_FIXES`. A BLOCKER is never softened.
- **The rule said "every HIGH above the cap", which is not a gate.** With 5 HIGHs, "above the cap" names 3 and says nothing about **which** 3 — any subset satisfies it. The rule was hardened to **every HIGH**, which is the strict reading and the implemented one. In the opposite direction, `/review`'s `SKILL.md` opened a valve the script never had (*">2 HIGH → HALT **unless** each HIGH is dismissed with an ADR rationale in the report"*): prose looser than the code is an invitation to operate above the script. A rationale in prose no longer counts; a record with an owner does
- **The two gates the agent itself ran and nobody checked afterwards.** `check_tdd_shape.py` (Step 2) and `mini_review.py` (Step 4.7) were invoked **only by the `SKILL.md`'s prose**. The rule calls skipping the mini review a "documented anti-pattern" and the SKILL says the skill NEVER skips it — both sentences speak to the agent, and no downstream gate asked whether they had run: `run_validation.py` included neither `tdd_shape` nor any phase-boundary check. A run that skipped every boundary was indistinguishable from one that reviewed them all, and a halt-loop driven from a prose-only plan left no trace. The final gate now **re-asserts** `check_tdd_shape` (a task with no executable shape fails) and the new `check_phase_review.py` requires the `{slug}-phase{N}-review-*.md` report for **every** phase whose tasks are all `committed`. It is the same pattern the kit already applied to wiring — do not trust self-reporting, re-derive the evidence — extended to the two disciplines that existed on paper only.
- **`assert add(1, 2) == 3` was classified as prose.** `check_tdd_shape.py`'s assertion pattern only accepted `[\w.\[\]]` before the operator, so **any function call** fell into "no executable shape". It went unnoticed while the detector was advisory; it became a block on a valid plan the minute the gate turned blocking at the end of the run. A new pattern covers `assert f(args) (op) Y`, requiring the comparison operator — which still refuses "assert that it works well"
- **The coverage gate did not read coverage.** `check_coverage` ran `npm run test:coverage` and returned `PASS` from the exit code; its own docstring admitted it never opened lcov or json-summary, so the "≥ 90% on changed files" promised in SKILL.md was guaranteed by nothing — a project whose runner had no threshold configured passed at any coverage. A gate named after a number it never reads is worse than no gate: it converts a command's exit code into a measurement. Now `coverage_gate.py` **reads the report** (istanbul `json-summary`, Cobertura XML, coverage.py JSON) and compares total line coverage against a floor resolved from `rules/code-quality-thresholds.txt:coverage.min_percent` (absent = 80), saying which source the number came from (`cli`/`project`/`default`). Without a parseable report the status is `WARN` — *the threshold was NOT verified* — and never `PASS`. The per-changed-file and per-critical-path floors are still **not** enforced, and are now documented as such instead of implied: asserting them from a total would be the same laundering in another place
- **`VALIDATION_GATE_PASSED` could mean "no test ran".** `run_validation.py`'s four executive checks (`npm test`, `typecheck`, `lint`, `test:coverage`) answered `SKIP` without a `package.json`; in a Python, Go or Rust repo `overall` became `PARTIAL`, and `PARTIAL` exits `0` — while `rules/cycle-implement.md` says the promise is emitted "EXCLUSIVELY when `run_validation.py` exits `0`". The condition was satisfied without a single suite having run, and the report still handed the decision back to the LLM (*"Decide whether SKIPs are acceptable for this phase"*) — exactly the judgement the gate existed to make. The kit is multi-language (`rules/code-quality-languages.txt` enables Python, Go, Rust and TypeScript) and **this repository is Python**, so the defect was strongest where the kit self-hosts. Now `suite_runners.py` detects each language's manifest at the root and runs the suite for real — `pytest` (falling back to `unittest`), `go test ./...`, `cargo test` — and the consolidating `test_execution` check **fails when a manifest exists and no suite ran**, counting as non-execution the two disguises as well: a `pytest` that collected zero tests, and a missing toolchain. Only a repo with no manifest at all (a legitimate pre-code phase) may skip. It is the same class of defect `_find_progress`'s docstring had already named — a SKIP indistinguishable from a verification — now applied to the exit code
- **A plan task missing from the checkpoint passed every `/implement` gate as PASS.** (#9) No guard compared "tasks the plan declares" against "tasks the checkpoint accounts for". `check_phase_completeness` built the phase inventory **from the checkpoint** — so the checkpoint judged itself. `check_checkpoint_consistency` had the plan's list in hand and discarded it on the loop's first line (`if tid not in referenced: continue`), because it was designed to catch "committed but unrecorded" and a task never done has no commit. Each deferred to the other: the second one's docstring literally says *"complements, not replaces, the phase-completeness gate"*. Measured: a plan with T1.1/T1.2/T1.3 where T1.3 was never implemented exited 0 in both, while the **same** task recorded as `pending` was caught HIGH — omitting was cheaper than admitting, in the one artifact the halt-loop writes out of discipline and nothing enforces. The inventory check now runs in both, with scope decided by the caller: `run_validation` passes all the plan's ids (final gate), `mini_review` only the `T{phase}.*` ones (a boundary cannot fail over tasks from phases that have not started). Ids present in git keep the backward check, which is more informative — reporting both would duplicate a single problem
- **Three `run_validation.py` gates only looked at `.claude/`, and SKIPped in the standalone layout.** (#10) `_find_plan`, written just above them, already handled both layouts; `_read_progress`, `check_progress_schema_gate` and `check_checkpoint_consistency_gate` hard-coded the plugin path. In the standalone layout — which `rules/knowledge-base-location.md` makes canonical for the kit's own repository, where it self-maintains — all three answered `SKIP: no progress checkpoint — implement may not have run` for a checkpoint that is on disk. It survived because **a gate that skips because it looked in the wrong place is indistinguishable, in the report, from one that legitimately had nothing to check**, and the message even suggested the innocent explanation. Worse: it disabled the #9 fix — no inventory helps if the gate cannot find the checkpoint. There is now a `_find_progress`, mirroring `_find_plan`
- **In a TypeScript monorepo, `/arch-check` measured 0 edges and proposed the rule that would forbid them all.** (#4) Measured on a TypeScript monorepo: 4 packages exchanging **80 imports** were read as 4 independent units, and the proposer offered `independence` — *"any import between units"*. That is not under-measurement, it is inversion: the catalogue's strongest rule against the repo that least obeys it, red on the first run, exactly what the skill's criterion exists to make impossible. The cause was discarding every *bare* specifier — true for `react`, false for a package of the repo's own `workspaces`, and in a monorepo the cross-unit edges **are** bare (`@a-typescript-monorepo/agent`, not `../agent`). It now resolves via `workspaces` plus the package's `exports` map, which is the real resolution contract: a TypeScript monorepo's `shared` declares three subpath exports and **no** `.` entry, so any layout convention like `<pkg>/src/index.ts` would have resolved nothing for it. And the missing refusal: if a specifier names a package of the repo's own `workspaces` and does not resolve, `propose` returns `refused` instead of concluding independence — in a monorepo, "units seen + 0 edges" is the signature of a failed resolver, not a finding
- **`install.sh --force` silently erased the whole project configuration.** (#8) It overwrote `rules/` and deleted `agents/` with no warning and no copy — and the destroyed files are exactly the ones the installer's own "Next steps" section tells you to edit: `code-quality-languages.txt`, `live-target.txt`, `acceptance-target.txt`, the allow lists, **the routing table** in `cycle-backlog.md` and the domain specialists. Measured: a `typescript | ... | ENABLED` line and a live-target block added to a fresh install vanished after a single re-run, with no message. There is an asymmetry worse than the overwrite: a specialist the source repo does **not** have — that is, every specialist a consumer writes for their own domains — is not overwritten, it is **deleted** by the `rm -rf`. In a repo that tracks `.claude/` that is recoverable with `git restore`; in a TypeScript monorepo, which deliberately does not track it (the kit is a maintainer's tool, not the product's code), silent also meant permanent. The fix does not merge — guessing which side of a config wins is how you get this wrong: it snapshots `rules/` and `agents/` into `.claude/.install-backups/<timestamp>/`, then lists **only the files that changed**, pointing at the snapshot and at `patch_install.sh` as the non-destructive upgrade path. Restoring from the snapshot was exercised, not merely offered
- **`install.sh`'s "Validating install" step validated the source repo, not the installation.** (#7) `test_e2e_smoke.py` resolves the ecosystem from **CWD**, and the normal way to call the installer is `cd squad && bash scripts/install.sh <target>` — where CWD is the source repo itself, which has `skills/rules/hooks` at its root. It found that one, validated that one, and printed OK. Measured: with a routed specialist and a cycle rule **removed** from a fresh install, it answered `ecosystem: /home/paulo/Projetos/squad` / `ALL CHECKS PASSED` / exit 0 — green for a broken installation, having opened a different tree. It is the same class D5's meta-gate exists to catch: a check that cannot fail is worse than none, because it puts a green line next to a broken install. `check_xrefs.py` resolves from its own `__file__` and did catch the corruption, so the two lines printed the same word for very different amounts of verification. Both now run from inside the target, and the behaviour was verified in both directions: clean install, both OK; rule removed, both exit 1
- **`install.sh` carried this repo's audit trail into the consumer.** (#7) The header promises to skip audit trails, but `agents/` was copied whole with `cp -r`, and this repo dogfoods its own cycles — `/implement` and `/review` write per-run agent definitions into subdirectories there. Every install received two artifacts from May 2026 (`implement-slice-s0-*/sepa.md`) from slices the consumer never ran. It now copies only the top-level `*.md`
- **`route_domain.py` answered `routed: true` with `agent: null`.** (#4) The invariant "every domain names a specialist that exists on disk" lived only in `tests/test_route_domain.py`, and `install.sh` **does not copy `tests/`** — so in every consumer repo the guard simply did not exist, and the output already anticipated the case by printing `(none declared)` and returning 0. Measured while installing into a TypeScript monorepo: a second three-column table inside the `## Domain routing` section **is parsed as routing**, which invented two domains whose specialist files were never written, and nothing objected. A resolution that names nobody is the same empty gate D5 exists to catch. The check moves into the tool, which always runs, with its own exit code 3 — an item that does not route (exit 1) is correct G1 behaviour, a table pointing at nobody is a defect in the table, and conflating the two hides the second
- **Following `code-quality-languages.txt`'s own instructions made `/code-quality` crash.** (#6) The template said *"one language identifier per line"* and listed `# typescript` to uncomment; the parser requires `LANGUAGE | MANIFEST-MARKER | STATUS | NOTES` and raises `ValueError: malformed line: 'typescript'` on fewer than three fields. The already-configured repos use the four-column form, so the code was right and the **template** wrong — the worse direction, because the template is the only thing a new repo reads. It is aggravated by the fact that `manifest-marker` is not cosmetic: it is what sends D1 to the right directory. Rewritten with one commented example per language, and the test covering it **reads the template and uncomments the examples** instead of asserting the parser's behaviour — a test that only exercises the parser cannot catch "the doc lies about the code"
- **Dynamic `import()` was not read, and could invert the direction of a `one-way` rule.** (#5) The shared extractor reads import *statements*; `await import('x')` is a call expression and does not show up. Measured on a TypeScript monorepo: 17 of the 23 `cli → agent` crossings and 3 of the 43 `tui → agent` ones exist only in that form — the `cli → agent` edge was under-measured by 74%. An under-measured count does not change direction when both sides under-measure equally, but in a repo where the **reverse** edge existed only as a dynamic import, the proposer would read 0 in that direction and emit a false `one-way` rule; dependency-cruiser follows dynamic imports, and the config would be born red. In a TypeScript monorepo the direction survived — verified, no dynamic reverse — meaning it worked out by a property of the repo, not of the tool. A computed specifier (`import(variable)`) remains invisible to any static means, and the test records that as a known limit instead of pretending coverage
- **Rust's D2 detector accused the standard library of being a fabricated symbol.** `std`, `core`, `alloc`, `proc_macro` and `test` ship with the toolchain and are never published on crates.io, so the query answers "not found" and the rubric read that as fabrication: a file with `use std::collections::HashMap` scored FAIL_HARD. Measured on db-engine on 2026-07-23: **117 of 117** D2 findings were false positives of exactly that shape. They are now recognised, along with modules declared in the file itself (`mod foo;`), workspace crates (path dependencies are not on crates.io either) and names already brought into scope by another `use`. In a file with a glob import (`use pgrx::prelude::*;`) the detector cannot prove the first segment is a crate and not a module, so the honest severity becomes SOFT_FLOOR — "I did not verify" — instead of HARD. Adopted from db-engine (an adopter's issue tracker), which developed it in its vendored copy; the logic arrived there with no tests at all, and the 16 tests for the five helpers were written here
- **`/code-quality` pointed the dead-code detector at the repo root instead of the manifest's directory.** The marker in `code-quality-languages.txt` is a repo-relative path, so a crate in `theodb_rs/Cargo.toml` or a package under `web/` are legitimate, configurable layouts — but the orchestrator passed the root regardless. Dead-code CLIs resolve the project from cwd, so `cargo-udeps` exited with "could not find `Cargo.toml`", the detector honestly reported `auditor_unavailable_cargo-udeps`, and the cycle jammed on a soft ceiling caused by a path assumption, not by the code. It now receives the manifest's directory, which collapses to the root in the common case. Measured on db-engine (an adopter's issue tracker); regression test in `test_orchestrator.py`
- **The fixture plan had a falsification criterion that contradicted the item's DoD.** Found by the eval I expected to find nothing — the scenario existed to test whether the reviewer **invents** a problem in a good plan. It did not invent; it found two real ones. (1) The criterion killed the hypothesis with "a single query", but the item's DoD asks for a "number independent of the span count", and the batched form emits **two** — it satisfies the DoD and would fail the written criterion. Rewritten as constancy. (2) The questions pointed at the file **with no line**, and the file contains both opposite functions: you could answer "confirmed" **or** "hypothesis dead" citing exactly the same target, and the checkpoint "the line exists" could never fail because no line was cited. Pinned to ranges (`:31-57`, `:65-89`), plus a dead-code question the `review` contract requires and the plan did not have.
- **The post-promise integrity check reported EVERYTHING as fabricated when a tool was missing.** Found by an eval run: Step 7's shell command used `$(wc -l < "$path")` in the bounds test, and with a corrupted `PATH` `wc` became unavailable — the substitution expanded empty, every comparison failed, and the check accused **23 real pointers as 23 FABRICATED**. The failure direction is fail-closed, which is correct, but the practical effect is the opposite: a check that collapses to "everything is false" when a tool is missing gets discredited and then ignored — worse than one that fails loudly. Rewritten in `python3`, which is already a project dependency, and it now **prints the cited line**: a pointer is verified by *saying what was claimed*, not merely by existing. The first run of the new command already caught a citation in the fixture itself that resolved to the wrong line.
- **The N+1 fixture got its own count wrong.** The docstring said "200 queries plus one" (201); the real number is **202** — it omitted the per-trace query. Found by the agent that executed the module instead of merely reading the control flow. A fixture whose comment gets its own defect wrong teaches the wrong number to whoever measures it.
- **A repo fixture with a real N+1, so that the measurement measures something.** The `/discover-execute` evals asked you to count round-trips in an endpoint that existed nowhere in the sandbox — an eval whose target does not exist tests the agent's imagination, not the skill. `skills/discover-execute/evals/fixtures/web-console/` brings a TypeScript handler with **a genuine N+1** (`listTraces` emits one query per span, in a loop) and, in the same file, the batched form that does the same work in two queries regardless of the count. The second exists so the KILL path can be exercised against real code: an N+1 hypothesis aimed at it is genuinely refuted, rather than refuted by a stub. The `pnpm-lock.yaml` is there on purpose — a specialist who checks the lockfile before choosing the command finds the right answer.
- **`install.sh` was still installing the Cycle, and would have delivered a broken Squad on every adoption.** Discovered by actually installing into 17 repositories, not by reading. Four defects, and the first is the one that matters: **`agents/` was created EMPTY**. The script copied `skills rules hooks commands scripts` and then ran `mkdir -p agents` — so the 8 specialists never reached the consumer, and `route_domain.py` would happily resolve to `agents/data-plane-ts.md`, a non-existent file. The routing would answer, the specialist behind it would not exist. The other three: `discoveries/blueprints/` (the artifact the Squad renamed to `opportunities/`), `references/` (the prior-art study zone the Squad eliminated) and the absence of `backlog/` and `maintenance-runs/`, without which the new phases have nowhere to write. Fixed and verified in a real install: `check_xrefs` PASS with 0 findings inside the target, and routing returning the correct specialist.
- **Three auxiliary distributed-architecture skills.** `cap-theorem-specialist` (CP/AP trade-offs), `backpressure-specialist` (producer/consumer mismatch and flow control) and `resilience-specialist` (timeouts, retries, breakers, bulkheads, degradation). The latter two arrived at **900 and 1,200 lines** — they would be the repo's largest and would exceed `skill-creator`'s 500 ceiling, which says to add a hierarchy layer as you approach the limit. Structured as `SKILL.md` (~280) + references (4 and 5 files). **The cut was by moment of use, not by section size:** the body carries what decides the direction of the analysis, the references carry the detail consulted once you already know which path to investigate. That matters because the body enters context on every trigger — cutting by size would have left the pseudocode always loaded and the choice criterion in a separate file, exactly inverted.
- **All three descriptions apply the lesson from the triggering audit.** They name concrete symptoms instead of the pattern's name, because the question almost never arrives by name: *"the whole site went down because one service got slow"*, *"we timed out but the payment went through"*, *"the queue never drains"*. Each also declares its main refusal — `resilience-specialist` refuses unbounded retry, unbounded queues and retry on a non-idempotent operation without protection. Without that, they would only trigger for someone who already knows the pattern's name, which is exactly who needs them least.
- **The skills' trigger lived in the place you only read after triggering.** An audit against `skill-creator`'s contract measured the defect: **8 of 9 skills** had `## When to Trigger` in the **body**, and **7 of 9 descriptions** did not say when to use them. The body only enters context *after* the skill triggers — so the triggering criterion lived where it is only read once it has triggered. That is not style; it is the triggering mechanism disarmed. All 9 descriptions were rewritten with what it does **and** when to use it, within the ~100-word budget (54–97w), two of them deliberately "pushy" against the under-triggering the contract itself documents. The body sections became `## When NOT to invoke`: the positive trigger lives in the description, and the body carries the refusals, which are contract with justification and do not fit in 100 words.
- **16 evals with 79 assertions for the 4 skills whose behaviour depends on judgement.** The scripts had 100+ tests; the **skills** were never exercised — pytest verifies whether `check_corner_coverage.py` does what it should, an eval verifies whether **Claude using the skill** produces the right result. They cover `backlog-item` (accept a hunch without evidence, refuse prior art, split two domains, dedup), `discover-plan` (refutable falsification, refuse live-test without a target, pre-validate targets), `discover-execute` (kill when the criterion is met and — more importantly — **not** kill when the measurement could not run) and `discover-edge-cases` (an unfalsifiable hypothesis is always MUST FIX). The gate skills are left out for being deterministic: an eval there would test little beyond the script.
- **Eval harness: a per-run sandbox, a programmatic grader and 14 tests over the grader.** Each run receives an isolated copy of an adopted umbrella (`setup_squad_eval_sandbox.py`) — the skills write to `BACKLOG.md`, and sharing would let one run pollute its neighbour in execution order. The grader (`grade_squad_backlog_item.py`) verifies by script what is verifiable and marks `NEEDS REVIEW` on what requires human reading, **never passing by omission**. The test that holds the rest up is exactly that one: a judgement assertion that passed automatically would inflate every run in the battery precisely on the assertions nobody checked, invisibly.
- **The first battery's "baseline" had the whole system — 4 of 4 read the rules.** The sandbox copied `rules/` and `skills/` into **both** arms, so the "skill-less" agents read `rules/cycle-backlog.md` and cited G2, G3 and G5 by name. That is not a baseline: it measures "was told to read the SKILL.md" against "found the contract on its own", and both had the system. Fixed with `--baseline`, which hands over only the registry and the CHANGELOG — what someone inherits opening a workspace without the Squad installed (the schema stays inferable from the existing items, which is realistic and fair). **The signal that survived the contamination is the round's most interesting:** in the G5 case, the baseline *had* the rules, knew the gate, and routed around it — it found a local reason on the user's behalf to save a request justified by prior art. The rule alone was not enough; the skill, with its explicit step and its table of examples, produced the correct refusal.
- **Eval-0 measured the wrong thing, and failed correct behaviour.** Its prompt collided with the fixture's `B-014` — the item that exists precisely so eval-3 can exercise dedup. Both arms merged, correctly and with independent justification, and scored **0/7** because the assertions expected a new item. Rewritten against `promptly`, which no fixture item mentions. An eval that fails the right behaviour is worse than no eval: it pushes the skill in the wrong direction on the next iteration.
- **The grader failed on a regex, not on a defect.** The "searched the registry" pattern did not match "Busquei" — a false negative inside the validator itself. Caught by the 14 tests written before trusting it, not by reading.
- **The documentation now describes the system that exists.** `README.md`, `HOW-TO-USE.md`, `plugin.json` and the `rules/` and `skills/` indexes rewritten. Anyone opening the repo read "Cycle — ship features with evidence" and a pipeline that started at `ROADMAP.md`; the system underneath had been something else for twelve commits. Documentation describing a different system is worse than none: it is credible enough to be followed. `plugin.json` becomes `squad@0.1.0`, and the internal comment records the inversion inherited from the Cycle instead of leaving it to archaeology. A `## Status` section declares alpha explicitly — the pipeline and the gates are implemented and covered by tests, but no item has run end to end in this version, and the README says so instead of leaving the absence implied.
- **The rules index announced `ROADMAP_COMPLETE` as `cycle-maintenance`'s verdict.** A side effect of the mass redirection of references to the old super-loop: the `sed` swapped the filename and left the vocabulary, creating a line that named the new cycle with the token the previous slice had just eliminated by conscious decision. Same class of defect in the skills indexes, where `roadmap-init` became `backlog-init` but kept "Bootstrap ROADMAP.md" as its purpose. Both fixed, and a final check confirmed that **every skill, script and rule cited in the documents exists on disk** — an index that promises a non-existent command spends the trust of whoever follows it.
- **`cycle-maintenance` replaces `cycle-roadmap` — and there is no `MAINTENANCE_COMPLETE`.** The macro super-loop stops walking `M0..M8` milestones and starts selecting the next item from `BACKLOG.md`. The absence of a completion token is the decision that carries the rest: a roadmap is a finite scope someone declared and **can** be exhausted; a backlog is not a scope, and an empty record means **nobody looked recently**, not that the work is done. The empty state is `BACKLOG_EMPTY` and it is an **invitation to sweep**, not a finish line — treating it as completion is how a maintenance system silently stops working while reporting success. Ranking: `triaged` before `raw` (a measured item has a known cost; and old evidence describes a system that has already changed), then oldest first — a record that always works the newest item starves the rest, and the starved items are exactly the ones nobody feels urgency about, which is not the same as them not mattering.
- **`/backlog-review` — the ways a maintenance record rots.** Written from scratch, not ported: a roadmap is finite, ordered and linked by dependencies, and a backlog is none of those — cycle detection, the `M0..M8` ceiling and order checking have no meaning over independent items, and carrying them over would produce checks that always pass. It checks what actually rots: a duplicated or renumbered id, `triaged` with no evidence (a status is a claim nobody made), `raw` **carrying** evidence (someone measured and nobody advanced — the most informative symptom of all, because it means the loop is being routed around), `killed` with no reason, a repo that does not route, an absent or unfalsifiable DoD, a `raw` item idle for more than 90 days, and probable duplicates among **open** items. Every finding declares `kind: deterministic | heuristic`, and the verdict is **derived** from the findings, never asserted.
- **Three `roadmap-*` skills retired.** `roadmap-init` (its core was cloning SOTA peers — exactly the "copy other projects" the Squad eliminated), `roadmap-feature` (replaced by `/backlog-item`, which accepts precisely the hotfix and the refactor it refused) and `roadmap-review` (replaced by `/backlog-review`). Fourteen files removed, and the fifteen references to the old super-loop redirected — `check_xrefs` mapped them all, including three that would have broken silently.
- **`/backlog-review`'s routing check would never have run in real use.** `_known_repos` located `route_domain.py` relative to the **backlog**, not to itself. In real use the record sits at the umbrella's root and the tool in `.claude/scripts/` — the import would fail, and a generic `except Exception` would swallow that into a silent `None`: the check simply would not run, with the report looking healthy. Found because a test **skipped**: the isolated suite reached no table at all, so the `unroutable_repo` case was never exercised. A check that never runs in the tests is a check that may be broken. Fixed by resolving the import against the file itself, distinguishing `ImportError` (missing tool) from a missing table from a malformed table, and planting a real table in the test — 23 tests, zero skips.
- **The 8 domain specialists — the "squad" part of the Squad.** One agent per Theo ecosystem domain, each carrying the repos it covers **verified on disk**, the build commands that were checked, the domain's invariants, the shape a real finding has there, and the false positives that domain generates. One agent per repo would duplicate the same six TypeScript facts six times and rot six times faster; one agent per role (backend/frontend/SRE) would be too coarse to carry an invariant like "RDS is a protected unit" or "a `go build ./...` at the root covers nothing here". The domain is the granularity at which the **invariants** differ.
- **Deterministic routing, and the table is the only source.** `scripts/route_domain.py` maps repo → domain → specialist by reading the table in `rules/cycle-backlog.md`, instead of keeping a copy in code — a copy diverges the instant someone edits one of the two, and the divergence is silent: the work routes to a specialist that cannot open the repo, and nothing errors. Unlike `/review`'s `detect_domain.py`, which guesses the technical domain by keyword because it runs against an arbitrary plan, here the item already declares `repo:` and a repo belongs to exactly one domain — guessing would only add a way to be wrong. Two guards close the loop in both directions: every domain declares an agent that **exists on disk**, and every agent on disk is **reachable through the table** (a specialist nobody routes to is work that looks done and changes nothing).
- **The umbrella inventory drifted, and the agents would have inherited the drift.** Measured on 2026-08-05 with `find -maxdepth 2 -name .git` + `git -C <repo> rev-list --count HEAD`, against what `control-plane`'s `CLAUDE.md` asserts: (1) **`cli-tool` uses `npm`, not `pnpm`** — the table groups it with the six data-plane repos in a single "`pnpm test`" row, and running tests under the wrong manager resolves a different dependency graph from the one the lockfile pins: green, testing something other than what ships; (2) **five repos the table names have no checkout** — `repo-a`, `repo-b`, `repo-c`, `repo-d`, `repo-e` — in a document asserting an "inventory verified on 2026-07-28" and that "if a repo is not here, it does not exist in the folder". A week later, five of the entries did not exist on disk. That is exactly why `backlog-init` tells you to read the inventory from disk. The five are recorded as absent instead of deleted, so the divergence stays visible, and a test guarantees that **none of them routes**.
- **One domain became silently unreachable, and every test passed.** `control-plane` contains both halves — the control plane in Go and the dashboard in TypeScript (`control-plane/dashboard/package.json`, verified). Listing the raw repo under both domains would make routing depend on dictionary iteration order: the same item routing differently between runs, with nothing having changed. Resolved by addressing by path — but the repo pattern did not accept `/`, so `frontend-dashboard` parsed to an **empty** repo list. Everything else kept passing: an empty list violates no uniqueness, declares an agent that exists, and looks perfectly healthy. The domain simply could never receive an item. New guard: **every domain needs ≥1 repo**, because nothing downstream notices zero.
- **`/discover-improve` improves the ARGUMENT, never the RECORD.** An opportunity is half record and half prose: `## Corner 1 — Evidence` records what was measured, `## Recommendation` argues what to do about it. The deterministic fixer now operates **only** on the Recommendation. The ancestor rewrote the whole document — against a prior-art blueprint that was sloppiness; against a measurement record it is silent falsification of a finding. And `may`/`might` are no longer substituted: *"the endpoint may return 500 under load"* is a measured fact about something intermittent, *"must return 500"* is a different claim, and false. No regex distinguishes description from prescription, so it does not try. The skill also **refuses before starting** when the cap is `fabricated_evidence`, `empty_corner_evidence`, `empty_corner_blast_radius` or `no_adr_on_cross_repo_change` — none of them is resolved by editing text, and iterating on them burns the loop to arrive at the same number.
- **`score-report.schema.json` described an output the scorer no longer emits.** After the conversion to opportunities, the schema still required `blueprint_slug`, `blueprint_path`, `research_coverage_score` and `reference_citations_score`, and listed the old dimensions in its enum. A schema that does not validate the real output is worse than none: whoever consumes it believes they are checking a contract. Aligned and **verified by running the scorer** — zero required fields missing, zero emitted fields outside the schema. `blueprint_version` was removed rather than renamed: it was a `TODO` that always emitted `null`, and a field that was never populated is not a contract, it is noise.
- **`/discover-execute` gains per-mode routing and the AUTHORITY TO KILL the item.** The four modes stop being prose in the rule and become executable procedure in the halt-loop prompt, each with what counts as a measurement in that mode — and evidence from one mode does not satisfy another. `review` carries a discipline the others do not: before recording the finding, discard the three ways it could be wrong — the code is **dead**, the caller **never existed**, or the shape is **deliberate**. All three produce findings that look real and are not. `bug` has a hard, literal floor: write the repro, write the failing test, **and run it**. A test claimed as failing but never executed is fabricated evidence and locks the opportunity at 49. `live-test` refuses in a domain with no declared block and requires naming the environment-vs-product uncertainty. `evolve` demands a number, not an adjective.
- **The kill check runs on EVERY iteration, not at the end.** The prompt reopens the plan's `## Falsification` each time and asks whether what has already been measured satisfies the criterion. If it does, stop measuring and kill the item — `<promise>ITEM_KILLED</promise>`, with a `kill_reason` naming what was measured and what it showed. Running the check at the end would be too late: after a long measurement, sunk cost is the strongest reason for a weak finding to ship, and the prompt names that force explicitly instead of pretending it does not exist. **Killing is a successful outcome of the cycle.** What stays forbidden is killing when the measurement **could not run** — an unreachable target is not a refutation, and there the instruction is to stop and ask the human.
- **The opportunity template fails its own checker until it is filled in, on purpose.** 8/10 sections: `Item` and `Mode` carry placeholders that are neither a B-number nor a mode token. Publishing placeholders in a valid format (`B-000`, `review`) would let a forgotten `B-000` pass the gate and point the opportunity at a non-existent item — a silently wrong answer in place of a noisy absence.
- **The plan gate becomes a MEASUREMENT-PLAN gate — and the falsification criterion replaces the ADR requirement.** The ancestor demanded ≥2 ADRs from every discovery plan. In a measurement plan an ADR is premature: nothing has been measured yet, so there is nothing to decide. What makes a measurement plan honest is declaring **in advance** which result kills the hypothesis — without that, any observation can be reinterpreted afterwards as confirmation of what was already believed, and the measurement becomes a ritual that cannot fail. `## Falsification` is a mandatory section and drops to cap 70 when empty or filled with a placeholder. The per-question method stops being `Phase A`/`Phase B` (local reference search vs web) and becomes **Tool + Target**: a question with no tool is a wish, and a tool with no target is a tool aimed at nowhere. The question floor drops from 5 to 3 — five was calibrated for a prior-art survey across several projects; in a maintenance item a high floor produces questions written to satisfy a counter.
- **A plan target is a path; opportunity evidence is `file:line`. The difference is deliberate.** The plan points at what it **intends** to open, so a directory is a legitimate target and no line number is expected yet. The opportunity points at what it **already** measured, and there the line has to exist. Beyond that, the target checker confronts every URL against `rules/live-target.txt`: a plan naming a host no domain declares is planning a probe the cycle refuses (gate G-L), and catching that in the plan makes the refusal arrive while the plan is still cheap to change.
- **The project's thresholds never won — and the defect hid a second one.** `_resolve_thresholds` looked for the bands only in `.claude/rules/`. In this repo the rules live in `rules/` (standalone layout), so the project's file was never found and the packaged example won **silently** — a scorer evaluating against the wrong bands prints an equally confident verdict, and the decision taken on top of it has already been taken. Same shape as the `check_xrefs` defect recorded above. Fixed in both scorers: both layouts are consulted. **And the fix revealed the second one:** with the file found, its content started mattering — and `rules/discover-plan-thresholds.txt` was in a format (`key = value`) the parser, which splits on `|`, does not read. Result: zero bands, and **every score falling to INVALID, including 100**. The `soft_cap.*`/`hard_cap.*` keys the file carried were consumed by nobody — the caps live in the orchestrator. They were removed rather than reformatted: a config file that configures nothing is worse than no file, because editing it feels like changing behaviour. A new regression guard asserts that the project's real file produces usable bands — resolving a path does not prove the file is readable.
- **`DISCOVER` inverted — it stops studying other people and starts measuring ours.** In the Cycle, discover investigated *"how did project X solve Y?"*, produced a blueprint of external patterns and **explicitly forbade** looking at our own code. For a team maintaining a running ecosystem, that is the wrong question — it produces imitation, not maintenance. The question is now *"what is actually true about our code and our runtime, and is it worth changing?"* Four modes, each with its own evidence contract: `review` (`file:line` + the rule violated + why it matters **here**), `live-test` (`METHOD URL -> status` + console + trace + timing), `bug` (numbered repro + **a test that FAILS in the current state**) and `evolve` (a measurement of the status quo's cost). The mode suggested in the item is a guess: if the measurement reveals another shape, **reclassify and continue** — forcing the measurement into the mode someone guessed at intake defeats the reason for measuring. The terminal artifact renamed from **blueprint** to **opportunity**: a blueprint is a floor plan to copy; an opportunity is a measured gap in something we already run.
- **`ITEM_KILLED` — killing an item is a successful outcome of the cycle, not a failure of it.** A run that measures honestly and finds nothing has protected the plan cycle from work that would have been justified by a hunch. The token is **orthogonal** to the other four: they evaluate a document, this one reports an outcome — there is no artifact to score. It sits in the matrix's OK column by conscious decision: placing it as `INVALID` would file the cycle's most valuable result as a failure and create a permanent incentive to ship a weak finding instead of killing it. `kill_reason` is mandatory (gate G-K) — a kill with no reason is indistinguishable from an abandoned run. And when the measurement **could not run** (unreachable target, missing credential, missing tool), the instruction is to **stop and ask the human**: do not substitute a weaker measurement, do not reason about what it would probably have shown, and do not record `ITEM_KILLED` — nothing was measured, so nothing was refuted.
- **`rules/current-constraint.md` — the system's constraint as a LENS, deliberately not as a gate.** The characteristic failure of a maintenance team is local optimization: shipping ten well-evidenced micro-improvements at a stage that was never the bottleneck, and mistaking the activity for throughput. Every opportunity's *Constraint relation* corner asks whether the item **exploits**, **subordinates to**, or **elevates** the constraint — or is local optimization. **But it blocks nothing, and `unknown` is an honest and complete answer.** The reason is measurement: we do not instrument flow through the ecosystem — there is no per-stage lead time, no wait time, no WIP. A gate demanding "does this touch the constraint?" against non-existent data would be answered by assertion, which is exactly the defect gate G5 refuses at intake; building it here would reproduce, one file later, the problem the system was designed to prevent. Empirical identification is **opportunistic**: if a sweep or a live-test stumbles on real flow evidence, it gets recorded — no phase is charged with producing it.
- **The `BACKLOG` cycle — the phase 0 missing between "someone had an idea" and "someone measured".** The Cycle was born greenfield: `/roadmap-feature` appended an `M<N+1>` milestone to a `ROADMAP.md` and **explicitly refused** hotfixes, one-liners and refactors with no visible change, sending each to ad-hoc `/auto-plan`. That is exactly the workload of a team maintaining 21 repositories — the front door was closed to precisely the work that arrives most. `BACKLOG` opens that door: `/backlog-item {slug}` records **one** unit of maintenance as `B-NNN` in `BACKLOG.md`, with routing to one of the Theo ecosystem's 8 domains, a suggested discover mode and a verifiable Definition of Done. Ids are monotonic and never renumbered — a dead item keeps its number forever, because the number **is** the audit trail. **The decision that carries the rest:** an item is a HYPOTHESIS, not a commitment, and that is why intake **has no evidence gate**. Requiring `file:line` here would collapse `BACKLOG` into `DISCOVER` and silence the hunch — the cheapest signal a maintenance team has. `evidence: none-yet` is the honest value of a hunch; the one who measures is `/discover`, which promotes to `triaged` with evidence or kills with a `kill_reason`. `raw → planned` is forbidden: nothing reaches a plan without going through the measurement.
- **Gate G5 (no-prior-art) — the Squad's signature rule, enforced at intake.** An item **cannot** be justified by "project X does it this way". It does not forbid knowing someone else's solution — it forbids that being the reason. *"LangSmith has a trace waterfall, we should have one"* is rejected; *"the explorer does not show span hierarchy, so debugging a nested agent requires opening 6 traces"* is accepted, whether or not LangSmith inspired the format. The gate runs on keyword heuristics and **raises the question, it does not decide**: the human chooses between rephrasing, marking a false positive, or cancelling, and the decision goes into the intake log. A rejection that does not say what would make it acceptable is simply re-filed tomorrow, verbatim — so the `ITEM_REJECTED` report names the gate and what was missing.
- **`/backlog-init` and `rules/live-target.txt` — bootstrapping the record and declaring the live environment.** `/backlog-init` creates `BACKLOG.md` once, at the umbrella's root, and builds the routing table by **inventorying disk** (`find`/`git -C`), never from `CLAUDE.md`'s table — documentation drifts, and a table naming an uncloned repo sends items to a specialist who cannot open the code. A repo with no commits and a nested clone of the umbrella itself are **explicitly excluded with the reason written down**, instead of silently absent; a repo that falls into no domain raises a question to the human, because a repo outside the table can never receive an item. It seeds **zero items** by decision: an item nobody filed has no `why_now`, no DoD and no owner — it is a placeholder that will be inherited as if it were a decision. Migrating findings already in the `knowledge-base` is **declared out of scope**: each would need to arrive with its original evidence pointer and date, or it loses exactly what made it valuable.
- **`live-target.txt` is separate from `acceptance-target.txt`, and the separation is the point.** The first declares the **dev** environment `/discover --mode live-test` probes to find things to fix; the second, the **released** delivery `/acceptance` exercises to decide whether what shipped works. Merging them would point acceptance at dev and let a milestone be declared validated against an environment nobody publishes. Target verified on 2026-08-05: `app-dev.example.com` answers HTTP 200 in 0.6s with no redirect — declared for `frontend-dashboard` and `control-plane`. The other 6 domains **have no block**, and the absence is a statement, not an oversight: a Go library, a Postgres extension and a Terraform module have no surface a browser can probe. `live-test` refuses on them instead of staging a performance.
- **One record, two producers.** `BACKLOG.md` lives at the umbrella's root and is the single source of truth about what is pending across the 21 repos. `/backlog-item` is the human door (a hypothesis, without evidence); `/discover --sweep` writes **to the same file and the same schema**, with `source: discover-review` and the evidence already attached, born `triaged`. Per-repo backlogs would recreate the problem the single source exists to solve — the current `knowledge-base` already shows review findings that died orphaned inside report files, seen once and never again. One question ("what is pending in web-console?"), one place to look.
- **`READY_TO_MERGE_WITH_FOLLOWUPS` — `cycle-review` was the only cycle with no "OK with caveats" band, and a real run landed exactly in the hole.** `promptly` closed M12 with zero BLOCKERs — all of them independently refuted by an **adversarial** reviewer, instructed to prove they were still open, which failed on all three — and **five** HIGH findings, against a contract that admits two. `READY_TO_MERGE` would call five acknowledged HIGHs clean green; `NEEDS_FIXES` would say the blocking work is unfinished when it was demonstrably closed. Neither is true. The third state now has a name: **mergeable, carrying recorded debt**. **Hard gate:** every HIGH above the ceiling is a *recorded* followup — an entry in `## Followups` or an opened issue, never a mention in prose, because a caveat with no owner is a defect with better manners. The milestone stays locked by `cycle-acceptance`, so this does not loosen what an `[x]` asserts; it only stops forcing a false binary at the review boundary.
- **`/cycle-goal` refuses to arm a goal with no verifiable route to `ACCEPTED`.** I armed three gates before checking whether any of them could close — and one could not. An unsatisfiable goal is worse than none: it blocks every stop attempt up to the ceiling of 40, and **each block looks like a legitimate verdict**. Two conditions are now checked before arming: (1) every milestone has a `Definition of done` — that is where `/acceptance` takes its criteria from, and without it the milestone can never be accepted; (2) the project declares in `rules/acceptance-target.txt` (per-project) how its published delivery is reached — `kind`, `target`, and optionally `build`/`verify`/`credentials`. Credentials go in **by name, never by value**: if a run needs one and it is missing, the instruction is to **ask the human** — do not skip the phase, do not invent a result, do not record `NOT_VALIDATED` and carry on as if the milestone were done. The conscious-risk flag stays available. On the first run the guard already caught `M7` and `M28` in `skills-pkg` with no DoD. 5 new tests (56 in the skill).
- **`/roadmap-review` measures PHASE coverage per milestone — where the cycle is being skipped stops being invisible.** Watching real runs, the dominant bottleneck was none of the ones the reviewer already checked: **plans with no `milestone_id` in the frontmatter** (18 of 27 in `skills-pkg`, 4 of 8 in `workspace-app`, 2 of 11 in `promptly`). Without that field `cycle-release` does not flip, `cycle-roadmap` does not track, and no report can tie a milestone to the work that delivered it — the plan exists, but orphaned. Four new checks under `--knowledge-base`: `plans_without_milestone_id` (MAJOR), `released_without_plan` (MAJOR), `released_without_implementation` and `released_without_review` (MINOR — the phase may have run without recording, and both hypotheses deserve an answer). 5 new tests (49 in the skill).
- **`check_xrefs` audited the current directory's project, not the project it belongs to.** Without `--ecosystem-dir`, the root came from `cwd`: running `python3 <other-project>/.claude/scripts/check_xrefs.py` silently audited `cwd`'s ecosystem and printed **its** verdict, with the other project's name on the command line. Measured on 2026-08-03: three consumers reported `PASS` actually had 3, 0 and 11 findings — the `PASS` was the kit's repo self-validating three times. The root now comes from the script's own path; `--ecosystem-dir` remains the only way to point at another target. A validator that audits the wrong target is worse than none: it produces unfounded confidence, and the decision taken on top of it has already been taken.
- **The exemption for auto-generated skills held in one check and not the other.** `review-*-knowledge` and `*-sepa-knowledge` became exempt from `no_orphan_skills` but were still charged by `skill_has_cycle_contract` — it turned 26 WARNs into 3 and looked like a fix, with the consumer still in FAIL over a defect that does not exist. There is now a single predicate (`_is_auto_generated`) consumed by both checks, and the test calls that predicate instead of reproducing the rule: the previous version reproduced it, and that is why the half-exemption passed green.
- **A skill retired by the kit survived forever in the consumer, and `--strict` failed because of it.** The kit removes skills as it evolves, but `patch_install.sh` never deletes — so `skill-writer`, `skill-validator` and `skill-register`, retired when we adopted the official `skill-creator`, went on living in all three consumers producing 3 orphan WARNs on every run, forever. The patch now knows the retired tail and **MOVES** it to `.claude/.patch-backups/retired/<timestamp>/` — the "the patch never destroys" guarantee still stands and the tree comes out clean. All three returned to `PASS`.
- **`check_xrefs --strict` started failing in every consumer that ran `/review`.** The cycle itself generates knowledge skills — `review-{slug}-{dimension}-knowledge` in review, `*-sepa-knowledge` in discover — and `patch_install.sh` already treats them as artifacts ("Auto-generated skills (SEPA-knowledge, review-*-knowledge) preserved"). The validator did not: it accused each of being an orphan. The effect showed up far from the cause — the consumer ran a review and, runs later, `--strict` failed with dozens of WARNs and no real defect. Measured across the three monitored consumers on 2026-08-03: 26 WARNs, all of this kind. The exemption is by name pattern and deliberately narrow: `skill-writer` and its kin are still orphans, and so is a `knowledge-base-helper`. 4 tests.
- **Third false-positive family in detector D2: a tsconfig alias treated as an npm package — 986 HARD findings, all false.** Reported by the `promptly` session running `/code-quality` against the dashboard where M12's code lives. `@/components/Button` is a **path alias** declared in `compilerOptions.paths`: the `@` is a convention, and the module resolves through tsconfig, not the registry. The detector treated every specifier with `@` as a scope and queried npm. It now reads the declaration instead of guessing — `tsconfig.json` / `tsconfig.base.json` / `jsconfig.json`, tolerating comments and trailing commas, which strict JSON would reject. The session made the right call: it diagnosed, pointed out it was the wrong repo to fix in, and reported. **All three families have a single root** — the detector resolved module names against the public registry without consulting what the project declares (workspaces, exports, paths). 3 new tests (107 in the skill).
- **The gate suggested a command that does not exist, and its ceiling was theatre.** Two failures exposed by the first extended run, both mine. (1) The blocking message said *"run `/cycle-goal clear` if the goal itself is wrong"* — that command **does not exist**; the real one is `install_goal_hook.py --clear`. A blocked session typed the invalid command I suggested, verbatim. The message now prints the full, correct path. (2) `max_blocks` (40, which I even raised to 120) was never the ceiling that counts: **Claude Code overrides a Stop hook after 9 consecutive blocks** (`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`) and ends the turn regardless — observed in the field (`Ran 18 stop hooks` → *"A hook blocked the turn from ending 9 consecutive times — overriding"*). Raising `max_blocks` is not tightening, it is staging; it only governs blocks spread across turns. Documented in both places: **the gate cannot hold a session captive, and that is a property to rely on, not a gap to close.**
- **Detector D2 failed entire monorepos — 112 findings, zero real — and the fix came from a consumer.** The `promptly` session diagnosed two defects in `code-quality/scripts/detectors/typescript.py`: (1) `_find_self_package_name` resolved the ROOT `package.json`, which nobody imports, so every sibling import (`@scope/promptly` from `packages/api`) fell through to the public registry, took a 404 and became HARD — they are `workspace:*`, resolve locally and were never published by decision; (2) a scoped package was queried by its SUBPATH (`@modelcontextprotocol/sdk/server/mcp.js` is not a package name), producing 52 SOFT_FLOORs over a real, installed SDK. With the fix the verdict goes from `FAIL_HARD` to `PASS` with zero findings. The session **refused the cheap allowlist** — which would have recorded 112 non-existent problems as tolerated debt — and wrote 2 regression tests before the fix, one of them failing if the registry is consulted for a local package. Backported to source; 104 tests pass.
- **`patch_install.sh` destroyed a local fix in silence — and destroyed this one.** My own propagation commit reverted the fix above without a line of warning, because the manifest carries `skills/code-quality/` as a whole folder and the directory branch had no guard at all. Now, before overwriting, the patch checks git to see whether the consumer modified that file: if so, it copies it to `.claude/.patch-backups/<timestamp>/` and reports **loudly** in the summary, saying that a fix to a kit defect must go up to the SOURCE or it will be reverted on every propagation. The guard covers both branches — file and directory — and it was the directory one that lost the fix.
- **`cycle-acceptance` was unreachable for internal packages — the three monitored consumers are private npm monorepos.** The target matrix covered a deployed URL, an installed binary, a published package and a live API. None of those exists in a private monorepo, so `/acceptance` could only emit `NOT_VALIDATED` and the `cycle-goal` gate would burn all 40 blocks with no chance of closing — in precisely the projects that need the cycle most. The rule now covers **internal / private package**: build from the **release tag** in a clean checkout, consumed the way the real consumer consumes it. The distinction that matters was never public vs private — it is **the artifact vs the working tree**: a build from the tag reproduces what the consumer receives; `npm run dev` over the working tree does not. Still out: a dev server over the working tree, a mocked backend, a staging clone with different configuration.
- **Root cause of the split knowledge-base: `flip_milestone_checkbox.py` wrote the run-file at the ROOT.** Its `--roadmap-runs-dir` defaulted to `knowledge-base/roadmap-runs` relative to CWD, so every release flip wrote the record at the project root while every other cycle wrote under `.claude/`. Half the audit trail landed next to the other half and nobody noticed. Confirmed in `promptly`: the root's run-files are the stubs auto-generated by the flip (371 bytes, no `slug`/`implementation`/`review`/`tag`), and the canonical ones are the full versions written afterwards — the same milestone recorded twice, in two places, at different fidelity. The default now resolves the canonical path from the layout. 2 tests.
- **`.claude/knowledge-base/` is the canonical location, and the kit now guarantees it — three consumers had TWO knowledge-bases and wrote to different ones.** Discovered the worst way: an audit of mine read `.claude/knowledge-base/` and reported that `skills-pkg` had "0 implementations, 0 reviews, 0 releases". The repository had 6, 12 and 8 — in `knowledge-base/` at the root. The claim was false and **nothing in the system detected it**. A second knowledge-base never errors; it just accumulates half the truth, and whoever reads the wrong side reports absence where there is evidence.
  - **`rules/knowledge-base-location.md`** pins the convention: `.claude/knowledge-base/` always, with the single exception of the standalone layout (the kit's own repo).
  - **`install_goal_hook.py`** stops assuming the root: it resolves the canonical path from the project's layout and writes `.claude/knowledge-base/acceptance` in a plugin install. The previous default pointed outside the real knowledge-base in every consumer.
  - **Autonomy became an executable guarantee.** A `--roadmap` or `--acceptance-dir` that resolves OUTSIDE the project root is refused: consumers are autonomous, and a gate pointing at the neighbouring repo makes one project's milestone depend on the other's state. This closes the path the `--acceptance-dir` flag had opened.
  - **`roadmap-review` emits `split_knowledge_base` (MAJOR)** when it finds a second knowledge-base holding `.md` files. The split becomes visible instead of silent.
  - 9 testes novos (95 nas duas skills).
- **`/roadmap-review` cross-checks the roadmap against the evidence in the `knowledge-base`, and the 9-milestone ceiling stopped being a BLOCKER.** Found by watching real runs in three consumers:
  - **The ceiling was a false BLOCKER.** `/roadmap-init` limits the INITIAL roadmap to M0–M8 to keep the conception scope honest, but `/roadmap-feature` explicitly opens it ("M9, M10, M11… extend freely"). The reviewer failed mature 13- and 30-milestone roadmaps as `INVALID`, grown exactly the way the kit prescribes — the kind of false positive that trains a team to ignore the tool. It is now MINOR/heuristic, with the message explaining the difference between the two caps.
  - **New `--knowledge-base` check:** every `[x]` is cross-checked against `roadmap-runs/` and `acceptance/`. Reading the document alone would never catch the drift that matters most — a checkbox flipped by hand, or flipped by a `cycle-release` that ran before `cycle-acceptance`. Measured on the first run: `skills-pkg` with **24 of 27** `[x]` milestones with no run-file, `promptly` with 2 of 11, `workspace-app` with 3 of 8. `released_without_roadmap_run` is MAJOR; `released_without_acceptance` is MINOR, because milestones closed before this cycle existed are not a defect — but the count must not grow from here on.
  - Backward compatible: without `--knowledge-base`, only the document is reviewed. 7 new tests (41 in the skill).
- **`patch_install.sh` now creates the `knowledge-base/` scaffold the new cycles need — before, 0 of 29 consumers had the directory the `cycle-goal` gate points at by default.** A patch copies files from the manifest; it never created directories. That did not bite while the cycles only wrote into folders `install.sh` had already created — but `cycle-acceptance` is new, and its `knowledge-base/acceptance/` is only born on a clean install. Real, measured consequence: **none** of the 29 patched consumers had the folder, so any gate armed with the default reported `"/acceptance never ran"` — indistinguishable from a legitimate verdict — and blocked forever over a configuration problem. It now creates `knowledge-base/{acceptance,acceptance/evidence,roadmap-runs}` when absent, empty only: existing content stays untouched, within the contract that the patch never deletes.
- **code-quality `/code-quality` audit walked `knowledge-base/references/` (cloned third-party repos) because `DEFAULT_SKIP_DIRS` used `referencia` (PT) instead of the real directory name `references` (EN) (#37).** The PT/singular typo never matched any real path, so `_enumerate_source_files` (`run_code_quality.py`, `repo_root.rglob('*')`) fed the D2 symbol-fabrication detector ~25k foreign files (measured: 97% of TS / 100% of Python in a real module came from `references/`) — a single audit ran 40+ min at 2.1 GiB RSS (peak 4.15 GiB) and produced a spurious `FAIL_HARD` that blocked `/review`. Fixed the typo (`referencia` → `references`) with a behavioral regression test written first (TDD): `test_enumerate_source_files_skips_references_zone` asserts a file under `knowledge-base/references/` is excluded; `test_default_skip_dirs_includes_references` replaces the structural guard that previously codified the typo. Found by tracing a 2.1 GiB process during a host-RAM investigation; propagated to all consumer kits via `patch_install.sh`.
- **code-quality scored `INVALID` as 49 instead of 0, contradicting its own golden rule (rules-audit 2026-06-28).** Two related defects: (1) `skills/code-quality/SKILL.md` § Step 4 mislabeled the score-cap-49 findings (`dead_code_unallowlisted` / `symbol_fabrication` / `allowlist_malformed`) as `49 (INVALID)` — relabeled to `FAIL_HARD` (49); (2) the deeper divergence behind it: `_shared.py:_verdict_to_cap` mapped `INVALID → 49`, but the golden rule § 1 (the LOCKED Source of Truth) fixes `INVALID = 0` (structural integrity broken — worse than `FAIL_HARD`). Corrected the code to `INVALID → 0` with a regression test written first (TDD): `test_emit_json_summary_invalid_caps_score_at_zero` + a per-verdict cap guard. Updated the `cq_invoke` tier comment and the SKILL.md `score_cap` enum (`0 | 49 | 70 | 89 | 100`). All 101 code-quality + 281 plan-confidence slice tests pass.
- **`/implement` phase-boundary mini-review reported `declared_files: 0` for every healthy phase** — `mini_review.py`'s report render used `len(pc.findings) and len(dc.declared_files)`, which short-circuits to `0` exactly when a phase is clean (no completeness findings, e.g. all tasks committed with a populated DoD). The audit artifact thus claimed no files were declared precisely when everything was fine. Now renders the real declared-file count; covered by a regression test (`test_report_declared_files_count_is_real_when_phase_is_clean`) (code-review 2026-06-20).
- **`/implement` validation summary dropped `WARN` and `PARTIAL` checks** — `run_validation.py`'s `summary` counted only pass/fail/skip/n_a, so `WARN` (code-quality `FAIL_SOFT`/`PASS_WITH_CAVEATS`) and `PARTIAL` checks vanished from the numeric breakdown and the buckets no longer summed to `total`. Both buckets are now reported; regression test asserts the buckets always sum to `total` (code-review 2026-06-20).
- **`/implement` code-quality gate could crash validation instead of degrading gracefully** — `run_validation.py` only caught `ImportError` around the `cq_invoke` import, so any exception raised inside `cq_invoke.invoke()` propagated and aborted the whole gate, contradicting ADR 0002's "degrade to SKIP when CQ unavailable". The invocation is now wrapped and degrades to `SKIP` with the raised reason; the helper dir is also no longer leaked into `sys.path` (code-review 2026-06-20).
- **`skills/implement/SKILL.md` documented a broken `check_wiring.py` invocation** — the WIRING-phase step instructed `check_wiring.py {symbol-name}` (positional), but the script requires `--symbol`; running it as documented failed with an argparse error. Corrected to `--symbol {symbol-name}` (code-review 2026-06-20).
- **`check_wiring.py --project-root` crashed on a relative path** — the override branch skipped `.resolve()`, so a relative `--project-root` made pillar (a)/(b)'s `path.relative_to(project_root)` raise `ValueError` against grep's absolute paths. The override is now resolved to an absolute path (code-review 2026-06-20).
- **Six latent slice-test failures, hidden by CI never running them, are fixed** — all six were rotted tests, not production bugs (production was correct in every case):
  - `skills/review/tests/test_detect_domain.py` (4) — tests still asserted a former consumer-specific project's domains (`pgvector-schema`, `memory-layer`); `detect_domain.py` had since been made intentionally agnostic. Tests + `sample_plan` fixture rewritten against the real agnostic `DOMAINS` (`database`, `auth`, …) (architecture-audit 2026-06-20).
  - `skills/discover-confidence/tests/test_check_reference_citations.py` (1) — `test_good_blueprint_all_citations_verified` depended on gitignored repo-resident reference files and a stale `knowledge-base/references/` citation form (missing the canonical `.claude/` prefix). Made hermetic: it now creates the cited reference file under a tmp project root (architecture-audit 2026-06-20).
  - `skills/discover-plan-confidence/tests/test_check_reference_citations.py` (1) — same rot class; `test_good_plan_all_citations_verified` made hermetic so it no longer counts absent gitignored files as fabricated citations (architecture-audit 2026-06-20).
- **Test suite goes from 32 failures to 0** by addressing six independent layout/spec/snapshot drifts that had accumulated across milestones:
  - `tests/conftest.py` — fixtures (`rules_dir`, `concepts_dir`) are now LAYOUT-AWARE. They detect whether the suite runs against the plan standalone (`<root>/rules/`) or against a consumer install (`<root>/.claude/rules/`) and route to whichever exists. Closes 17 failures whose root cause was an empty `.git/` directory that short-circuited the walk-up to project root.
  - `templates/rubric-v1.md` — EC-13 partial fix: PT-BR dictionary entries added to subjective_adjectives, weak_imperatives, vague_pronouns, loopholes, non_verifiable (both ASCII-fold and accented variants — `rapido`/`rápido`, `manutenivel`/`manutenível`, `deveria`/`poderia`, `isso`/`isto`, `se possivel`/`se possível`, …). Per "Reasons NOT to bump" rule, this is an in-place change to existing dictionaries, not a version bump. Closes 9 failures in `test_smell_pt_br.py`.  <!-- english-only: lists the PT-BR terms the rubric detects -->
  - `templates/score-report.schema.json` — `hard_caps_triggered` enum extended with the 5 new SOTA-upgrade soft cap ids (`soft_floor_baseline_context_incomplete`, `soft_floor_drawbacks_section_insufficient`, `soft_floor_unresolved_questions_section_missing`, `soft_floor_concurrency_tests_missing`, `soft_floor_failure_scenarios_missing`). Closes 3 failures in `test_json_schema.py` whose JSON validation rejected the new cap ids because the schema was authored before the upgrade landed.
  - `tests/test_skill_md_reads_rules.py` — assertions now accept any portable form of the rules-directory reference (`rules/` OR `.claude/rules/` OR `.claude/rules`). The previous form required the literal `.claude/rules/` string, which failed when authors used the portable `rules/` form. Closes 2 failures.
  - `tests/test_real_plans_snapshot.py` — three active plans added to SNAPSHOTS with conservative envelopes (any band, score ≥ 0): `harden-fabrication-and-cq-gate-plan.md`, `slice-s0-walking-skeleton-plan.md`, `slice-s0b-walking-skeleton-crd-first-plan.md`. Tightens the envelope after the plans complete their migration to the new template. Closes 1 failure.
  - `tests/test_golden_rule.py § test_golden_rule_documents_m3_status` (renamed from `test_golden_rule_explicitly_marks_m3_as_future`) — the test was authored when M3 was wholly future; M3 v0.1 is now ENFORCED and M3 v0.2 (code-file refs) is DEFERRED per ADR. The test now pins the contract "the golden rule states the status of M3 in some explicit form" — accepting `active`/`deferred`/`enforced`/`fabricated_citation` as legitimate status attestations. Closes 1 failure.
  - Result: 277 passed, 14 skipped (the 14 skipped predate this session and remain intentional — they are property-based test placeholders / environment-conditional cases).
- All halt-loop skills now share a **rigorous template**: pre-flight guard against concurrent ralph-loops, formal Stop conditions section with enumerated cases (≥ 6 each), post-promise sanity check (re-runs the gate command in the same iteration to confirm the marker matches reality — emitting speculatively is treated as fabrication), Anti-patterns section (renamed from "Invariants" / "Halt-loop invariants" for nomenclature consistency), state-file guard inside each driver prompt forbidding nested loops or direct mutation of `ralph-loop.local.md`. Applied to `/discover-execute` (Step 4 pre-flight + Step 7 sanity check + 6 Stop conditions), `/discover-improve` (same + Step 6 re-runs `run_blueprint_score.py`), `/plan-improve` (same + Step 6 re-runs `run_structural.py`). Cycle rules `cycle-discover.md` and `cycle-plan.md` extended with "Halt-loop contracts" section listing promises + measurable exit criteria + cross-link to the skill's Stop conditions. Fixes documentation drift between SKILL.md (which understated rigor) and driver prompts (which already enforced most invariants). Closes the systemic gap: the rigor pioneered in `/implement` Step 5.5 is now applied uniformly to ALL 4 loop-using skills, not isolated to one.
- `/implement` validation gate now has a **mandatory fix-loop by default**. When `scripts/run_validation.py` returns `FAIL` (exit 1), the skill re-invokes `ralph-loop:ralph-loop` with the new `prompts/validation-fix-prompt.md` driver under a rigorous contract: completion promise `VALIDATION_GATE_PASSED`, max 5 iterations, pre-flight guard against concurrent ralph-loops on overlapping state, per-iteration objective table per failing check class (test/typecheck/lint/coverage/wiring/code-quality), and forbidden anti-patterns enumerated (no-op callers, threshold-lowering, ADR-defer of `symbol_fabrication_*` / `dead_code_unallowlisted_*` hard caps). Validation fixes are no longer driven manually — same contract as Step 4 TDD halt-loop. Updates `skills/implement/SKILL.md` Steps 5/5.5/6, `rules/cycle-implement.md` stop conditions and validation halt-loop section. Removes documentation drift where the old Step 5.5 described `/code-quality` as a separate invocation (the script already consolidates it via ADR 0002).
- All 8 hooks under `hooks/` are now layout-aware: each detects ecosystem root at startup (`.claude/` for plugin install, `.` for standalone) and routes filesystem reads through the resolved `$ECO` prefix (`$ECO/knowledge-base/`, `$ECO/rules/`, `$ECO/.active_plan`, `$ECO/.attestations/`, `$ECO/.compaction-snapshots/`). Same source now works identically in both layouts; eliminates the manual sed-fest required when installing as `target/.claude/`.
- `hooks/boundary-check.sh` + `hooks/validate-command.sh` — read-only regex for `knowledge-base/(references|tools)/` extended to also match the optional `.claude/` prefix. Edits and shell mutations are blocked in both layouts identically.
- `skills/plan-confidence/scripts/run_structural.py` — `_invoke_code_quality` and `_merge_code_quality_verdict` are now thin wrappers delegating to `cq_invoke.*` (the public shared helper extracted in T2.1). Removed `_invoke_code_quality_legacy_inline` (dead branch) — closes the `impljudge-legacy-inline-dead-code` finding. The public `cq_invoke.merge_verdict_into_plan_confidence()` now has a real production caller — wiring triad pillar (a) PASS, closing the `wiring_triad_missing_caller_cq_merge_helper` critical from the first judge-codex iteration.
- `knowledge-base/plans/harden-fabrication-and-cq-gate-plan.md` — detoxified to remove tokens that triggered the M3 detector (and tripped Codex orthogonal review) when authored in plan prose: `architecture.md` → `<rule>.md`, `Blueprint §` → `<blueprint-ref>`, `D{N}` example tokens → `<undefined-ADR>`. Unified detector scope statement to "toda prose fora de fenced code" — same wording in Goal, ADR D1, Coverage Matrix and Edge Cases. Added `## Risks` (5 entries), Goal now carries a deadline. Pre-detox snapshot preserved at `.pre-detoxify` for audit-trail.
- `rules/cycle-judge-codex.md` — contract for the **orthogonal LLM jury cycle**, delivered by the external `judge-codex-plugin-cc` plugin (https://github.com/usetheodev/judge-codex-plugin-cc, v0.1.0 released 2026-06-04). Documents the 4-stage chain (`:discover` / `:plan` / `:implementation` / `:final` review-of-review) plus the `:auto` orchestrator, the canonical verdict vocabulary aligned with this ecosystem (`SHIPPABLE` / `SHIPPABLE_WITH_CAVEATS` / `NEEDS_REVISION` / `FAIL_HARD` / `INVALID` + `:final` meta-verdicts `META_DEFECT_FOUND` and `AGGREGATOR_BUG_SUSPECTED`), and the **disagreement protocol** (pipeline halts for human adjudication when Claude `/review` and Codex `:judge-codex` reach different verdicts). Live integration test on 2026-06-04: Codex caught a fabricated `ADR D9` reference in `harden-fabrication-and-cq-gate-plan.md` that the Claude-side `plan-confidence` M3 v0.1 had missed because M3 only scans `#### Evidence` blocks; the disagreement IS the highest-value signal the orthogonal jury exists to surface.
- `cycle-rule-schema.md` — `cycle-judge-codex` row added to the canonical verdict matrix with explanation of why it mirrors upstream cycles plus the 2 review-of-review meta-verdicts.
- `README.md` — new `## Orthogonal LLM jury` section documenting install + recommended workflow, plus a `cycle-judge-codex` row in the "Match the cycle to the shape of the work" table.
- M3 v0.1 — `fabricated_citation` hard cap is now ENFORCED in `/plan-confidence` (was textual-only contract until now). New detector `skills/plan-confidence/scripts/check_evidence_citations.py` (regex + stdlib, zero new deps) covers rule refs (`architecture.md §1`), Blueprint refs (`Blueprint §Q1`), intra-plan ADR refs (`D8`), and Unbreakable Rule refs (range 1..13). ≥1 unresolved citation → score ≤ 49 → verdict `INVALID`. See ADR `0001-m3-fabricated-citation-v01`. Closes audit gap on tese 1 (planos vagos): citations to non-existent rules/sections/ADRs now block `/implement`.
- `skills/code-quality/scripts/cq_invoke.py` — shared subprocess helper extracted from `run_structural.py`. Provides `invoke()` + `merge_verdict_into_plan_confidence()` for any cycle that needs to consult `/code-quality`.
- `rules/cycle-release.md` — new cycle rule that automates the develop → main release ritual after `cycle-review` returns `READY_TO_MERGE`. Verdicts: `RELEASED` / `PR_OPEN_AWAITING_APPROVAL` / `BLOCKED`. Closes the gap where the last 10% of the pipeline was manual.
- `skills/release/` — new skill `/release [bump-level]`. Derives next semver from CHANGELOG sections (auto-bump major/minor/patch), rewrites `[Unreleased]` under the new versioned header, commits `chore(release)`, opens PR develop→main, and on merge creates an annotated tag + GitHub release. Human approval at PR merge is the only manual gate.
- `skills/release/scripts/{compute_next_version,promote_unreleased,render_release_notes,changelog_section_nonempty}.py` — release helpers; idempotent and tested via in-flight smoke runs.
- `rules/code-quality-golden-rule.md` — locked unbreakable contract for `/code-quality`: severity rubric, hard caps, allowlist mechanism, detector contract. Promoted from skill defaults and standardized on the dogfood-golden-rule pattern.
- `rules/code-quality-thresholds.txt` — per-project threshold overrides for `/code-quality`. Defaults remain in `skills/code-quality/defaults/thresholds.txt`.
- `rules/code-quality-allowlist.txt` — explicit exemptions for code-quality findings with mandatory sunset (≤ 90 days) and ADR requirement for HARD-level exemptions.
- `rules/discover-blueprint-golden-rule.md` — locked contract for `/discover-confidence` (promoted from `skills/discover-confidence/templates/discover-blueprint-golden-rule.example.md`). Documents the empty-corner and fabricated-citation hard caps that score-cap blueprints at 49 (INVALID).
- `rules/discover-blueprint-thresholds.txt` — promoted from skill template; per-project thresholds for `/discover-confidence`.
- `rules/discover-plan-golden-rule.md` — locked contract for `/discover-plan-confidence`: empty research-question, fabricated citation, question-budget, empty-coverage-corner hard caps.
- `rules/discover-plan-thresholds.txt` — discover-plan score thresholds (defaults).
- `rules/plan-confidence-golden-rule.md` — promoted from `skills/plan-confidence/templates/plan-confidence-golden-rule.example.md` (was referenced as locked contract but absent on disk).
- `rules/plan-confidence-thresholds.txt` — promoted from skill template.
- `rules/plan-confidence-allowlist.txt` — promoted from skill template.
- `rules/deps-audit-golden-rule.md` — locked unbreakable contract for `/deps-audit`: severity rubric tying CVE severity to plan-confidence score caps; HIGH/CRITICAL on declared dep = FAIL_INSECURE (49).
- `rules/deps-audit-allowlist.txt` — CVE/version exemption file with mandatory ≤ 90-day sunset.
- `rules/review-model-routing.txt` — model-routing config consumed by `skills/review/scripts/spawn_reviewers.py`. Was referenced in code and SKILL.md but absent on disk; now documented with `ROLE: MODEL [KEY=VALUE]` format.
- `skills/auto-plan/scripts/inject_must_fix.py` — auto-injection of MUST-FIX edge cases into the plan, idempotent. Eliminates the manual "human absorbs MUST FIX" step that previously required an `AskUserQuestion` in `/auto-plan`.
- `cycle-release` row added to the verdict matrix in `rules/cycle-rule-schema.md` (`RELEASED` / `PR_OPEN_AWAITING_APPROVAL` / `BLOCKED`).
- `rules/cycle-rule-schema.md` — canonical schema for cycle rules: required sections (`Purpose`, `Pre-conditions`, `Chain`, `Anti-patterns`, `Cross-references`), optional sections, and the canonical verdict matrix per cycle, explaining why each cycle has its own vocabulary.
- `knowledge-base/backlog.md` — backlog of items referenced in docs but not yet implemented (currently: `/audit-rotate`).
- `## Cross-references` section added to `rules/cycle-{plan,discover,implement,code-quality,review,auto-plan}.md`, eliminating the 6 WARNs from `check_xrefs.py`.
- `skills/{deps-audit,code-quality,ast-grep,dogfood}/SKILL.md` — removed the `paths:` field from frontmatter. Claude Code does NOT discover project-level skills (in `<project>/.claude/skills/`) that declare `paths` — the skills silently disappear from `/<tab>` autocomplete and `/{name}` resolves to "Unknown command". Confirmed live on search-api after the cadence->plan migration: `/deps-audit r4-api-documents` returned "Unknown command" because `paths: ["package.json", ...]` was in the frontmatter; removing the line restored discoverability. The other 22 plan skills (without `paths`) were unaffected. `paths` appears to be a plugin-skill-only field; project-level skills must rely on `description` text for contextual matching.
- `settings.json` — `permissions.defaultMode` corrected from `"ask"` (invalid against the Claude Code settings schema) to `"default"`. The schema accepts `acceptEdits` / `auto` / `bypassPermissions` / `default` / `dontAsk` / `plan`; `ask` was a typo that surfaced via `/doctor` when the ecosystem was installed at `<consumer>/.claude/`. Standalone mode silently tolerated it because Claude Code only validates the resolved settings cascade.

### Changed
- **The kit now ships `bypassPermissions`, and the merge that had to carry it was skipping it in silence.** `settings.json` and `settings.plugin.json` set `permissions.defaultMode` to `bypassPermissions` plus `skipDangerousModePermissionPrompt` — without the second, the harness still shows the bypass-mode acceptance dialog, which is itself a prompt. **The change would have shipped inert.** `install.sh` splits ownership of `settings.json` by key, and its permissions merge iterates the kit's entries with `if not isinstance(items, list): continue`. `allow` and `deny` are lists and merge; `defaultMode` is a STRING, so it was skipped without a word — the new default would have reached only consumers with no `settings.json` yet, and none of the seventeen that already had one. Same shape as the six defects before it, caught before shipping this time because the test was written first and failed on `default != bypassPermissions`. `defaultMode` is now a kit-owned scalar, on the reasoning that it is the kit's POSTURE rather than the project's preference; a consumer wanting a different one sets it in `.claude/settings.local.json`, which the harness reads at higher precedence — the mechanism built for exactly this. **`deny` is deliberately kept.** `bypassPermissions` skips prompts; it does not delete a refusal, and the two are not the same request. Keeping it is the difference between *never ask me* and *there is nothing you will not read* — the second would put `.env` inside the blast radius of every session in seventeen repositories. Verified across all seventeen after propagation: mode set, dialog suppressed, project-specific `allow`/`deny` intact, `.env` still refused.
- **`generate_plugin_settings.py` had a drift check in one kit and not the other.** Both ship the generator; only the Cycle guarded it. Editing both settings files by hand desynchronised them, the sibling's suite failed within seconds, and this one stayed green over the same drift. A generator with no drift check is a generator nobody runs — the guard is now in both.
- **The routing table left the kit's `.md` and became `rules/domain-routing.txt`, a file the project owns.** This was the root cause behind everything above it: `rules/cycle-backlog.md` held fifteen sections of the kit's contract and exactly **one** thing belonging to the project. Three defects of the same shape followed — `boundary-check.sh` blocks `rules/*.md` as the kit's, so the kit prescribed writing to a file it forbade editing, and the write landed anyway through `Path.write_text`, a channel no hook watches; the section had to be replaced by regex on every re-derivation, and the regex took the invariants beside it; and a reinstall needed surgery to preserve the consumer's table, surgery that existed in one of the two modes. `rules/*.txt` is already where project configuration lives: the guard permits it, a reinstall preserves it. Moving it deleted all three problems instead of guarding against each — and removed `apply_routing_template`, `save_routing_section` and `restore_routing_section` from the installer. Readers fall back to the legacy `.md`; writers do not.
- **`knowledge-base/` → `records/`, and two things left with it.** Once durable knowledge moved to the bundle, the name came to denote exactly what is **not** knowledge — worse than vague, inverted. But no single name was honest about the four natures the folder held, so the answer was to split rather than hunt for a better name: `tools/` → **`study-material/`** (third-party documentation, read-only, never produced by a run) and `progress/` → **`session-state/`** (an ephemeral checkpoint, not evidence). What remained is what it always was — a dated, immutable trail produced by a phase. Readers fall back to `knowledge-base/` and writers do not, for the same reason as the bundle's fallback: 42 consumers have the old directory on disk and the kit does not run migrations inside someone else's repository. 180 files updated; the reasoning lives in `.squad/wiki/decisions/where-knowledge-lives.md`.
- **The README explains the tree instead of listing it.** Each directory gets one line saying what it holds, and the reason for the `wiki/` + `records/` pair is written where whoever clones the repo arrives first. The section used to list six folders without saying why they existed.
- **Seven skills renamed for what they do rather than their shape.** The structural gate passes a vague name — that is judgement about meaning, and it says so — so this part was done by hand, measuring each name's damage before touching it. `plan-help` → **`commands-help`** (it showed ALL the kit's commands, not help about a plan); `auto-plan` → **`idea-to-release`** (the name said "plan" and it takes a milestone from idea to release PR); `dogfood` → **`honesty-gate`** (opaque jargon for what is a gate blocking a "production-ready" claim without evidence); `analysis` → **`trajectory-review`** (it emits `ON_TRACK` / `COURSE_CORRECTION_NEEDED` / `FUNDAMENTAL_RETHINK`, and "analysis" said none of that); `cycle-goal` → **`session-goal`** (the `cycle-` prefix collided with the `cycle-*.md` rules and had already caused a real defect in `check_xrefs`); `deck` → **`slide-deck`**. The rules and golden rules followed their pairs: `cycle-analysis.md` → `cycle-trajectory-review.md`, `cycle-auto-plan.md` → `cycle-idea-to-release.md`, `dogfood-golden-rule.md` → `honesty-gate-golden-rule.md`.
- **Three names weighed and kept, with reasons.** `ast-grep`, `excalidraw` and `marp-slide` name the tool because the skill *is* about that tool — the name is what someone searches for. And `to-plan` has 47 references and misleads nobody about what it produces: the cost of the rename does not pay for itself.
- **Nine renames, each trading shape for purpose.** `hooks/lib/` → `hooks/environment/` (what the hooks load before running); `skills/quality-init/scripts/lib/` → `gate_authoring/` (detect → calibrate → emit is what those modules do together); `skills/code-quality/scripts/_shared.py` → `_detector_contract.py` (it defines what a detector emits and what it reads); `skills/backlog-review/tests/helpers.py` → `backlog_fixtures.py`. Three tests that lived in `scripts/` moved into their slices' test trees. And `scripts/` came to have one convention: `attest-plan.sh`, `generate-plugin-settings.py` and `session-catchup.py` became snake_case, like the other twenty.
- **`scripts/test_e2e_smoke.py` → `scripts/verify_ecosystem.py`.** The name lied about the file's nature: it is not a test pytest runs, it is the verifier `install.sh` executes against the installation. The `test_` prefix made pytest try to collect it and made readers look for it in `tests/`. The test covering it followed: `test_verify_ecosystem_hygiene.py`.
- **`post-edit-check.sh` checks the edited file, not the entire project.** The hook runs synchronously on every edit — the agent waits for it — and has no debounce. Three of the four paths checked the whole project: `tsc --noEmit -p tsconfig.json` (including when editing a `.js`), `cargo check` (the whole crate) and `go vet <dir>/...`, which turns into the whole module when the edited file sits at the root. With a 60 s timeout, the outcome was one of the two worst: the turn stalled for tens of seconds, or the hook died midway and the feedback it exists to give never arrived. Now: `go vet` on the package, `eslint` on the file, `rustfmt --check` on the file, `ruff` on the file as it already was. **What is lost is real:** per-file `tsc` is not equivalent to project `tsc`, and a cross-module type error no longer shows up here — it is still caught by the suite and by CI, which is where a check of that scale belongs. `POST_EDIT_FULL_TYPECHECK=1` restores both project-wide checks, with `cargo check` now scoped to the crate that owns the file instead of the workspace.
- **The suite runs the slices in parallel.** The isolation `run_slice_tests.sh` defends is PER PROCESS — seriality was never part of it, it was just how it happened to be written. Measured: **100.2 s of wall clock for 69.6 s of summed pytest**, meaning ~30 s spent purely on starting 18 interpreters one at a time. Each slice stays in its own process; several processes now exist at once, with output reordered at the end so it stays deterministic. After: **33 s**. `SLICE_TEST_JOBS=1` returns to serial.
- **CI stopped running the root suite twice and started caching dependencies.** The main job ran `run_slice_tests.sh` (which already runs `tests`) and, in the next step, `pytest tests` again just to measure coverage — 45 s duplicated per run. Coverage is now measured in the run that already happens (`ROOT_SUITE_COV=1`), with the same 40% threshold charged, and the four jobs gained `cache: 'pip'` instead of reinstalling the same dependencies every time.
- **The plugin manifest has exactly one home.** There were two copies — the root one, which the README pointed at and the installer copied, and the one the native mechanism reads. Two copies of a manifest diverge; the canonical one is `.claude-plugin/plugin.json`.
- **`detect-layout.sh` resolves two paths where there was one:** `KIT_DIR` (the kit's code, read-only) and `ECO` (the cycle's data, writable). In native mode they diverge, and it is that divergence that stops the consumer from editing the kit. In copy and standalone modes they coincide, as they always did.
- **The README describes what the repository delivers.** It promised "eight domain specialists" and drew `agents/ ← the 8 domain specialists + README`; git carries the README and nothing else. The table of the eight remains, now framed as this ecosystem's instance — a concrete example — with the command that derives the reader's own.
- **The stop-hook blocked sessions that changed nothing, and let whole new files through.** Five defects, measured against an adopter on 2026-08-26, all in the same family: the gate reported about the wrong set of files.
  1. **The last commit always entered the set.** A read-only session inherited the previous commit's verdict and could not end — nine consecutive blocks over a `.ts` nobody in that session touched. The way out was to fabricate a changelog entry or reach for the override, and an override used to answer a question the gate should never have asked is how a gate stops being read. The commit now only counts while it has **not reached upstream**; with no upstream configured, it stays strict.
  2. **Untracked files were invisible.** `git diff` lists only modifications to tracked files, and the two artifacts these gates most want to see are always new: a `.changeset/` entry and a file's first test. `git ls-files --others --exclude-standard` joins the set, respecting `.gitignore`.
  3. **Only the root `CHANGELOG.md` counted as a record.** A monorepo publishing several packages records in `packages/<p>/CHANGELOG.md` or in `.changeset/*.md` — which is what BECOMES that changelog at `version` time. The gate reported "undocumented" over documented work. `.changeset/README.md` and `config.json` still do not count: they accompany the tool and record nothing.
  4. **The TDD gate looked for a test only next to the source.** That is idiomatic in Go and false across most of the JS/TS and Python world, where tests live in `packages/<p>/tests/unit/`. The search now climbs to the manifest that owns the file and sweeps that package's test tree. Limit declared in the code: it matches by the **source's name**, so a test named after the behaviour — which is what `rules/testing.md` § 3 asks for — is not found and the file is reported. Widening it to grep inside the tests would trade a false warning for a false silence, which is the worse of the two.
  5. **The "substantive change" filter swallowed new files.** It read `git diff HEAD~1 -- <file>`, which is empty for a file with no previous version — indistinguishable from "the diff only carried a comment". A new `src/payments.ts` with four lines of real code exited 0. The comment beside it claimed a false negative over a real change was impossible; it was false, and in the dangerous direction. The filter now prefers the tree's diff against `HEAD`, falls back to the last commit's, and for a new file reads the whole content — every line of a new file IS the change. An unobtainable diff now counts as substantive.
  Covered by `hooks/tests/test_stop_validation.py` — 14 tests that build disposable git repositories and run the hook for real, including the cases that must KEEP blocking, so that none of the fixes becomes a hole.
  **Not fixed, and recorded as a finding:** the gate does not grade `.sh`, and the kit is made of shell scripts — it does not audit itself.
- **The gate reported about the set it managed to see, and nothing checked whether that was the right set.** A repository that audited TypeScript with an unaudited `pyproject.toml` passed: `languages_audited` was not empty, so the existing guard did not fire. "It looked at something, just not at that" was indistinguishable from a clean run — and `cycle-review` admits on PASS.
  The missing question is not "did I audit anything?" but "was there something to audit that I did not audit?". It is answered by looking at the TREE, not at the gate's own list: every language the configuration knows carries its manifest marker, so a marker present for a language nobody audited is a file the gate skipped while the report said PASS. New stable id: `unaudited_manifest_present`.
  The previous guard (`no_languages_audited`) stays as it was. A disagreement with a consumer about the pre-code case — a repository with no manifest at all — is pinned in a test as a disagreement, not resolved unilaterally.
- **Both pointer gates rejected correct citations.** `CODE_POINTER_RE` opened with `\b` and a class that excluded `@` and the leading dot, so it matched a SUFFIX of a real path and produced a different path — one that does not exist. A citation under `node_modules/@scope/...` was truncated at the `@`; one under a dotfile directory lost the dot. Both became `fabricated_evidence`, the cycle's one unrecoverable cap, fired against correct evidence.
  And `PATH_TARGET_RE` read any token with a slash as a repository path: `an adopter/server/plugins` — a real npm subpath specifier — failed `Path.exists()` and became `fabricated_target`. The scoped sibling `@an adopter/sdk/server/auth` passed, but **by accident**: the `@` was outside the class, so the regex never saw it. Two forms of the same thing, treated in opposite ways, with nobody having decided that.
  The token is now captured whole and classified by **resolution**, never by a list of known names: exists on disk → path; resolves as a module (including in pnpm's store, which nests the package two levels down) → specifier; neither → fabricated. The cap stays armed — an invented path and an uninstalled package still fail, and there is a test for each direction.
  The workaround in use was a coincidence of phrasing (writing the specifier as it appears in source, with quotes, which the regex does not match). It would not occur to the next author, and nothing marked the plan as having routed around a gate.
- **Trunk protection only applied to whoever calls the branch `main`.** The guard matched `[ "$BRANCH" = "main" ]` and nothing else. An adopting project whose trunk is `master` installed the kit, read in the documentation that Rule 4 was protected, and it was not. Measured in a disposable project: on `master` `git commit` passed (exit 0); on `main` it blocked.
  It promises and does not deliver, silently — the worst shape, because the guarantee is only tested once it has already failed. Now `main` and `master` are a fixed floor and a custom-named trunk (`trunk`, `release`) comes from `refs/remotes/origin/HEAD`. Over-protecting is the safe side of the error: blocking a commit that could have passed costs a branch switch; the inverse costs the whole guarantee.
  **The first attempt at the fix was itself a fail-open:** with no remote, `git symbolic-ref` exits 128, and under `set -euo pipefail` the assignment inherited that status and aborted the hook — letting EVERY command through in any repo without an `origin`. The six `F12` tests caught it (agnosticism review)
- **The Stop hook audited the kit itself inside the adopting project.** `ALL_FILES` swept `.claude/**`, which is the INSTALLED kit — a dependency, not source. Measured on a fresh install: the first session emitted **107 lines** of warning about `.claude/skills/**/*.py` against **one** real finding in the user's code.
  Auditing your own dependency is the canonical way to teach someone to ignore the gate, and an ignored gate protects nothing. The `^\.claude/` filter serves both layouts without needing to distinguish them: in a plugin install the kit leaves; in standalone the files live in `skills/`, `hooks/`, `scripts/` and stay audited. Measured after: 107 → 0 (agnosticism review)
- **Without a `CHANGELOG.md`, the Rule 6 gate vanished silently.** `if [ -f "CHANGELOG.md" ]` disabled the entire check when the file did not exist — so a project that never created one never found out the kit expected one. Discipline promised in the documentation, absent in practice.
  It now emits an ADVISORY when production code changed and there is no CHANGELOG. Advisory and not BLOCKER on purpose: creating the file is the consumer's decision, and jamming every session of a freshly adopted repo would make the install a wall. The goal is to end the silence, not to stop the session (agnosticism review)
- **The trunk block message sent you where the hook itself blocks.** It said *"Work on 'develop' (single-trunk)"*; G1, ten lines below, blocks commits on `develop` — *"develop INTEGRATES work, it never ORIGINATES it"*. Anyone following the advice took a second BLOCKED with no indication of where work is born. It now points at `workspace` and names the real trunk instead of saying "main" (agnosticism review)
- **`install.sh`'s docstring described the opposite of what the script does.** It said *"agents/ ships the 8 domain specialists, copied from source"*; the real behaviour copies only the `README.md`, and the `theo` ecosystem's eight specialists sit behind `--with-domain-agents`. The behaviour was right — it was the documentation that lied, and in the direction that makes an adopter expect to receive a map of repos that are not theirs (agnosticism review)
- **`cycle-goal`'s error message told you to run a retired skill.** Without `ROADMAP.md`, `compose_goal_condition.py` printed *"run /roadmap-init first"* — a skill withdrawn along with cycle-roadmap. And `rules/cycle-acceptance.md § The ROADMAP.md contract` records that the file is written by hand and that **no** skill generates it, `/backlog-init` included, which creates a different record on a different axis.
  A remedy printed in the failure that does not exist is worse than none: it sends you searching instead of resolving. The message now points at the contract and at the required header form.
  Two siblings in the same file: the size BLOCK said the 4000 cap is *"the cap /goal enforces"* — contradicting the module's own docstring, which records that the cap ceased to apply when the skill started arming its own `Stop` hook, and is kept only as a readability limit. It now says what it is. And `cycle-goal`'s `requires` was wrong in both directions: it declared `to-plan` and omitted `grill-me`, `discover-plan` and `plan-confidence` — which the condition template embeds as a literal string (skill coherence review)
- **Nothing guaranteed that the commands cited in the termination condition exist.** `compose_goal_condition.py` embeds seven skill names in the condition's text, each beside the artifact it must produce; rename any of them and the condition still composes, still arms and still reads as authoritative. `check_xrefs.py` does not cover it: Check 7 sweeps `skills/**/*.py` for `rules/*.md`, never for `/skill-name`.
  `tests/test_goal_condition_names_real_skills.py` closes both levels. The first exempts historical mentions of a CLI primitive (`goal` is the subject of a whole section of the skill); the second exempts nothing, because it sweeps only what reaches a `print` — there, a command is not a reference, it is an instruction. It was that test that found the two defects above. A sweep of the same class over the remaining scripts: clean (skill coherence review)
- **`/auto-plan` skipped a gate of the cycle it claims to orchestrate.** `Phase D` chained `/discover-plan` → `/discover-edge-cases` → `/discover-execute`, with no `/discover-plan-confidence` in between — which is phase 3 of `cycle-discover`, has its own hard gate (*no fabricated target; non-empty falsification criterion*) and is declared by `/discover-execute` in its `requires`.
  What is lost by skipping: the measurement runs against a plan nothing validated, and the result arrives **looking clean**. It is the failure mode `/discover-edge-cases` exists to name — a measurement that cannot fail, believed precisely because it ran without error.
  `/auto-plan`'s `requires` declared 6 skills while the body invoked 15. The two halves now match, with all 16 declared (skill coherence review)
- **`check_xrefs.py` truncated every cycle with two hyphens.** `CYCLE_REF_RE` was `` `?cycle-([a-z]+)`? `` and `[a-z]+` does not match a hyphen: `cycle-code-quality` was read as `cycle-code`, `cycle-auto-plan` as `cycle-auto`, `cycle-judge-codex` as `cycle-judge`. Three of the twelve cycle rules — a quarter of the inventory.
  The validator then accused a file that was right there of being missing. The worst possible failure mode for a gate: the natural reading of the FAIL is *"the validator is broken"*, and that is how you teach a team to ignore it.
  It stayed hidden because `_extract_cycle_contract_ref` returns on the FIRST match, and the skills citing those cycles mentioned a simple-named one first. It only surfaced when `code-quality` gained a `## Cycle contract` citing `cycle-code-quality` on its own. `tests/test_check_xrefs_multi_hyphen_cycle.py` covers all three names, and checks that the error message carries the full name instead of the prefix (skill coherence review)
- **`/edge-case-plan` and `/discover-edge-cases` could not execute their own `Step 5`.** Both instruct you to save the report to `knowledge-base/reviews/` and to create the directory if absent; both declared `allowed-tools: Read Glob Grep Bash`, with no `Write`. Every sibling skill that saves a report (`review`, `analysis`, `deps-audit`, `discover-confidence`) declares it.
  It looks like an over-application of *"does NOT edit the plan"* — correct, and the reason `Edit` stays out — into *"writes nothing at all"*. Both now declare `Write`, and the text says what it is for: the report itself, nothing more (skill coherence review)
- **`marp-slide` told you to use icons that do not exist, by the wrong path.** It pointed at `../../.claude/skills/excalidraw/references/icons/` and cited `brain.svg`, `anthropic.svg` and `python.svg`. The directory is not distributed — `excalidraw/SKILL.md` itself has a section declaring so and explaining why. The sibling skill committed the defect its neighbour documented.
  The path was wrong twice over: it went through `.claude/`, which only exists in plugin mode, and it was relative to `SKILL.md` when Marp resolves an image from the **deck**, which can live at any depth. A literal `../../` copied from there fails as a broken image box on screen, in front of the audience, not at build time. The path is now the `<icons>` placeholder, with the definition beside it (skill coherence review)
- **`cycle-plan`'s CVE gate was the only one nothing enforced, and the rule did not say so.** The `## Phase contracts` table listed `deps-audit` with the hard gate *"no critical CVE on a planned dependency"* alongside four mechanized gates — but `/plan-confidence` does not read the dependency report, because wiring it EXTENDS the gate and `plan-confidence-golden-rule.md` puts extension behind an ADR. `skills/deps-audit/SKILL.md` was the honest one: it already recorded the wiring as undelivered.
  A gate listed among four automatic ones reads as automatic, and a gate believed to be automatic is a gate nobody runs. The rule now yields to the skill and declares the gate human-enforced (skill coherence review)
- **Four pipeline skills had no `## Cycle contract`, and two contradicted each other about `/discover`.** `code-quality`, `deps-audit`, `plan-confidence` and `discover-plan-confidence` are phases documented in `rules/cycle-*.md` and were the only ones without the section all their siblings have — the validator did not catch it because it only validates the section **when present**. The last two already had the text, loose inside `## When to Trigger`.
  On the same axis: `plan-help` and `HOW-TO-USE` state that `/discover` does not exist, while `cycle-backlog.md`, `current-constraint.md` and `backlog-item/SKILL.md` used it as if it did. They now name `cycle-discover` (the cycle) or `/discover-execute` (the phase that writes the opportunity). `plan-help` also said *"five skills"* ten lines above its own table of six, and `release/SKILL.md` had a duplicated `## Cycle contract` — two sources for the declaration whose whole job is to point at one (skill coherence review)
- **`/release` was still flipping the checkbox `cycle-acceptance` had taken from it.** `rules/cycle-release.md` said, in three places, that the flip had MOVED to `cycle-acceptance` — and `Step 7.5` of `skills/release/SKILL.md` went on implementing the flip, with its own single-flip invariant and three anti-patterns about how to flip. The skill contradicted the rule that governs it.
  What that cost is exactly what creating `cycle-acceptance` set out to prevent: the release path goes through no acceptance verdict at all, so `[x]` went back to meaning *"we published"* instead of *"we published and saw it work"*. `Step 7.5` now only reads the `milestone_id` and names the handoff.
  **The audit trail was lying right along with it:** `flip_milestone_checkbox.py` wrote `"Checkbox flipped to [x] by cycle-release"` into the roadmap-run file — when the one invoking it is `cycle-acceptance`. In a system whose thesis is evidence, a record attributing the act to someone who did not perform it is worse than no record (skill coherence review)
- **`ROADMAP.md` had no producer, and `cycle-goal` told you to run the wrong skill.** In the retirement of the roadmap skills (`93393e0`), a mechanical `sed` swapped `roadmap-init` for `backlog-init` across 15 references — including in the link text `"creates ROADMAP.md and its milestones"`, which ended up pointing at a skill that creates `BACKLOG.md`. Different records, different axes.
  Consequence: the pre-condition of `cycle-goal`, `acceptance` and `auto-plan`'s roadmap-driven mode could not be satisfied, and the remedy printed in the failure (`run /backlog-init first`) led nowhere.
  `rules/cycle-acceptance.md` gains `§ The ROADMAP.md contract`, which records the three facts nobody had written down: the file is written by hand and no skill generates it; the header is `###` and why; and the two records coexist on purpose
- **The documentation told you to write `## M<N>` and the three scripts match `###`.** `compose_goal_condition.py`, `extract_acceptance_criteria.py` and `flip_milestone_checkbox.py` agree with each other on `###`; `skills/release/SKILL.md` and `rules/cycle-release.md` said `##`. Anyone writing the ROADMAP by following the docs landed in the script's benign branch — `WARN … not found — skipping flip`, `exit 0`. The milestone never closes and nothing says why
- **`/discover` does not exist and was the command announced in 18 places.** The README, HOW-TO-USE, four rules, `live-target.txt` and two skills documented `/discover --mode X B-NNN` and `/discover --sweep` as the public interface — including in the *"which command do I run"* table, which is the first place anyone looks. The real entry points are `/discover-plan B-NNN --mode X` and `/discover-execute --sweep {domain}`
- **`check_evidence_citations.py` looked for opportunities in a retired directory.** The scanner read `knowledge-base/discoveries/blueprints/`; `/discover-execute` has written to `opportunities/` since the rename. A plan citing a real, resolvable section was reported as `fabricated_citation` — which hard-caps the plan at 49.
  **The suite passed the whole time because every test built its fixture in the same dead directory the scanner read.** The test did not protect the behaviour; it protected the bug. Both paths are now swept (the current one first), the `Opportunity §X` form is accepted alongside the legacy `Blueprint §X`, and three tests cover the real case — including one that ensures the fix did not blind the detector
- **`check_xrefs.py` could not tell a skill named `cycle-something` from a reference to a cycle.** `skills/cycle-goal/` is a skill, not a phase — but Check 2 extracted the first `cycle-X` token from the whole SKILL.md when there was no `## Cycle contract` section. Practical effect: `plan-help`, whose whole job is to LIST commands, could not mention `/cycle-goal` without dropping the validator to FAIL.
  The bug stayed latent while the documentation omitted the command — the omission hid the defect, and fixing the omission revealed it. A `cycle-X` whose X names an existing skill is now read as the skill; whoever genuinely belongs to a cycle declares `## Cycle contract`, which is matched first. Three tests, including the one that ensures a genuinely missing cycle is still caught
- **`skills/excalidraw/references/` was declared the source of truth and never existed.** `SKILL.md` told you to read `references/color-palette.md` *before generating any diagram* and step 2 of `/deck` depended on the same file. The directory was never in git: the skill was vendored without it.
  `color-palette.md` and `element-templates.md` were written, anchored to the GitHub-dark surface `SKILL.md` itself declares (`#0d1117` / `#58a6ff` / `#c9d1d9`), the same one as `/marp-slide`'s `template-tech.md` — diagram and slide with no visible seam. The icon library was **not** fabricated: it is ~176 SVGs and three scripts that did not come along, and `SKILL.md` now says so plainly, with the install command and what to do without it. A skill that tells you to read a non-existent file fails silently — you look, you do not find, and you invent a colour
- **`/acceptance B-NNN` in HOW-TO-USE.** The skill's `argument-hint` is `M<N>`; `B-NNN` is the other record
- **`plan-help` rewritten — it omitted 11 of the 36 skills and misdescribed 3 of those it listed.** It called `/backlog-init` *"Bootstrap ROADMAP.md"* and `/backlog-item` *"Add milestone"* (they are `BACKLOG.md` and `B-NNN` items), used *"blueprint"* where the v0.2.0 `discover-*` skills say *opportunity*, and Flow C — labelled *"Unknown prior art — need research first"* — flatly contradicted `discover-plan`'s description: *"prior art cannot be evidence here"*.
  In a help skill, drift is worse than anywhere else: it is the map someone reads precisely because they do not know the terrain. The new version instructs you to list `skills/*/SKILL.md` on disk and to **explicitly declare** any skill missing from the tables
- **`ACCEPTANCE` joined the announced chain.** `plugin.json`, the README, HOW-TO-USE, `rules/README.md` and `rules/cycle-auto-plan.md` ended the pipeline at `RELEASE`, while `cycle-goal` defines a green `/acceptance` as its ONLY stopping criterion. `auto-plan` now has the phase, its gate and its stopping conditions
- **`cycle-goal` cited five verdicts that exist nowhere.** `MILESTONE_RELEASED`, `MILESTONE_IN_FLIGHT`, `ROADMAP_COMPLETE`, `ROADMAP_BLOCKED` and `MILESTONE_BLOCKED` belonged to the retired `cycle-roadmap`; `cycle-maintenance`'s are `BACKLOG_EMPTY` / `ITEM_UNROUTABLE` / `ITEM_KILLED`. The description also described the old mechanism — an embedded `/goal` and its 4000-char ceiling — which the skill's own body has called a dead end for some time. The ceiling stays in the composer, now justified by what it actually is: a readability limit, not a CLI limit
- **`skills/README.md`: it said 35 skills, there are 36, and the table omitted 7.** `acceptance`, `analysis`, `arch-check`, `cycle-goal`, `frontend-design`, `plan-help` and `quality-init`. Adding `plan-help`, then `cycle-goal`, `analysis` and `quality-init` had **zero mentions** in any entry point: they existed on disk, passed the validators and were unreachable by any discovery path
- Command-validation hook got faster: ~6 processes per tool call instead of ~50, with no behaviour change
- **Branching model is now `workspace → develop → main`, enforced by a gate instead of stated as a convention.** Until now the Cycle was single-trunk: every change committed straight to `develop`, and only `main` was protected. `develop` now **integrates** work but never originates it — work is born on `workspace` (a single, permanent branch, not a per-task feature branch) and reaches `develop` through a promotion PR.
  - **Hook (`hooks/validate-command.sh`, guard G1):** when `HEAD` is `develop`, `commit`/`rebase`/`reset`/`cherry-pick` are blocked, and `merge` is allowed **only** from `workspace` (`origin/`/`upstream/` prefixes accepted) — merging any other branch bypasses the gate. `push` stays open so the promotion can reach origin. The inline form (`git switch develop && git commit`) is covered too, mirroring the F4 fix from #1. 10 tests written first (TDD, RED: 6 failing); the suite's fixture repo now starts on `workspace`, since neither protected branch is a valid place for unrelated tests to run. 57/57 pass.
  - **Contracts:** `rules/git-safety.md` § 1 rewritten as the SoT (diagram + per-branch rules + an explicit table of **which layer guarantees what**); `cycle-implement`, `cycle-roadmap` pre-conditions; `cycle-release` gained a promotion step — the release-prep and roadmap-flip commits are authored on `workspace` and promoted via PR, because the new gate forbids the direct `develop` commits the cycle previously performed.
  - **Skills and docs:** `implement`, `release`, `review`, `auto-plan`, the implementation task template, the review orchestrator prompt, `CONTRIBUTING.md`, `HOW-TO-USE.md` — including the executable branch assertions (`[ "$(git branch --show-current)" = "workspace" ]`). Occurrences of the word "development", the `develop → main` release PR, and a third-party URL were verified as false positives and left untouched.
  - **Honest limit, stated in the rule itself:** the hook governs the **origin** of the work (it must come from `workspace`); it cannot distinguish a merge that finalizes an approved PR from one that skips review. Only branch protection on the remote makes the PR mandatory. A repository with the hook but without branch protection has the first guarantee and not the second.
- **Branching model stated identically everywhere — "or a feature branch" no longer contradicts the single-trunk rule (#3).** `hooks/validate-command.sh:98` (the text a developer reads at the exact moment of a block) and `rules/cycle-implement.md:12` both offered a feature branch as an acceptable alternative, while the two Sources of Truth — `rules/git-safety.md` § 1 and the operator's Unbreakable Rule 4 — say all work happens on `develop`, single-trunk. Both divergent texts now point at `develop` (the rule file also cross-referenced from the pre-condition). No gate loosened: this is wording, and `git-safety.md` § 1 was left untouched as the SoT. `check_xrefs.py` PASS.
- **`.gitignore` — three untracked trees that were never meant to ship are now ignored, and `[Unreleased]` follows its own format again (repo-hygiene 2026-07-27).** `git status` carried permanent noise that made a careless `git add .` a real risk: `specs/` (12 MB of study material), `codex-plugin-cc/` (a nested repository with its own remote — ignored rather than registered as a submodule, so a clone of the cycle never drags it in), and `.claude/` (this repo's own Claude Code runtime dir — the shipped config lives in `settings.json`/`settings.plugin.json` at the root, and `hooks/boundary-check.sh` already treats `.claude/knowledge-base/` as consumer artifact space). Added `*.local.md` under Local overrides. Separately, `[Unreleased]` had accumulated 12 category headers with duplicates (`Changed` 4×, `Fixed` 3×, `Added` 2×, `Removed` 2×) against Keep a Changelog's one-of-each-in-order rule; consolidated to 5 headers in canonical order with every one of the 150 content lines preserved verbatim and each category's internal order untouched (verified by a multiset + per-category ordering check, not by eye).
- **`scripts/patch_install.sh` manifest completed — the kit patcher now propagates the full shared rule set + the missing script dependency (rules-audit 2026-06-28).** The session's `rules/` changes (5 golden rules, `cycle-analysis.md`, the two new conventions `error-handling.md`/`git-safety.md`, `README.md`) plus the hardened `hooks/validate-command.sh` were not in the manifest, so consumers would not receive them. Also closed two pre-existing gaps that surfaced while patching live consumers: the 6 shared convention rules (`architecture`, `testing`, `public-copy`, `parsimony-ladder`, `loop-engine-convention`, `audit-trail-rotation`) — referenced by skills but never propagated, causing `rules_reference_resolves` FAILs in consumers missing `parsimony-ladder.md` — and `scripts/ecosystem_utils.py`, the import dependency of the already-manifested `check_xrefs.py`/`test_e2e_smoke.py`. Per-project files (`*-thresholds.txt`, `*-allowlist.txt`, `*-languages.txt`, `*-config.txt`, `review-model-routing.txt`) remain excluded by design — each consumer tunes them locally. Applied to the 5 patchable consumers (`live-test`, `control-plane`, `ts-consumer`, `data-consumer`, `db-consumer`); all now pass `check_xrefs.py`.
- **`rules/` consistency audit — code-quality verdict vocabulary reconciled across the chain, stale index repaired, redundant prose trimmed (rules-audit 2026-06-28).** A 4-dimension audit (consistency, coverage, content/context-bloat, principle adherence) of all 35 files in `rules/` found one systemic drift plus several smaller defects, all now fixed:
  - **Verdict drift (the dominant defect).** `cycle-code-quality.md` and the canonical verdict matrix in `cycle-rule-schema.md` still described code-quality as a 3-token `PASS`/`PASS_WITH_CAVEATS`/`FAIL` gate, while the Source of Truth (`code-quality-golden-rule.md` § 1) and the skill itself had already moved to 5 tokens (`PASS`/`PASS_WITH_CAVEATS`/`FAIL_SOFT`/`FAIL_HARD`/`INVALID`) — and `cycle-implement.md`/`cycle-release.md` already consumed the new ones. Reconciled the schema matrix, `cycle-code-quality.md` (Chain, Phase contracts, Severity rubric — now a thin table that points at the golden rule as SoT instead of re-defining finding identifiers that had drifted, e.g. `fabricated_symbol` → `symbol_fabrication_{language}`), and the `cycle-review.md` pre-condition (now states `FAIL_SOFT` may proceed only with an ADR dismissing each soft cap, matching the golden rule).
  - **Stale index.** `rules/README.md` listed only 8 of 10 cycles and 6 of 7 golden rules; added `cycle-analysis`, `cycle-judge-codex`, `analysis-golden-rule.md`, the 3 missing threshold/config files, and `cycle-rule-schema.md`; corrected the code-quality and release verdict columns (release showed `MILESTONE_RELEASED`, a roadmap token — now `RELEASED`).
  - **Smaller fixes & de-bloat.** Corrected a truncated token (`COURSE_CORRECTION` → `COURSE_CORRECTION_NEEDED`) in `cycle-analysis.md`; removed stale `(new)` header suffixes in `cycle-roadmap.md`; replaced the re-enumerated parsimony ladder in `cycle-implement.md` with a pointer to the canonical file (DRY — that file explicitly asks callers to reference, not restate it); dropped a duplicated install runbook and a dated integration-test log from `cycle-judge-codex.md` (those belong in the plugin README / CHANGELOG); collapsed the verdict→feedback-action table in `cycle-analysis.md` (it appeared 3× — kept the canonical one in § Verdicts) and its redundant second roadmap diagram. `check_xrefs.py` and `test_e2e_smoke.py` both PASS.
  - **Golden-rule de-bloat (via ADR-0010).** Replaced the 7× "When this rule may change" boilerplate with a one-line reference to the new central protocol (see Added), and compressed the dated migration narrative in `plan-confidence-golden-rule.md` (~27 → ~14 lines) to a "Template provenance" pointer — the contract (caps + sunset 2026-09-07) stays in the rubric table; the concurrency/external-I/O signal taxonomies are summarized and point at `check_concurrency_tests.py`/`check_failure_scenarios.py` as their authoritative source.
- **`cycle-rule-schema.md` § Optional sections reconciled with the actual house-style (rules-audit 2026-06-28).** The schema demanded a single optional-section order that the cycle rules consistently diverged from (`## Output`/`## Rollback` always sit at the foot after `## Anti-patterns`; `## Verdicts` precedes `## Hard gates`). Rewrote the section into two positional bands — body (between Chain and Anti-patterns) and footer (after Anti-patterns) — so the existing rules are conformant by design instead of all being "a smell". No rule files reordered.
- **`userpromptsubmit-inject.sh` now injects a LEAN POINTER to the active plan, not its `head -50` — context-bloat fix.** The hook fires on every prompt and its `additionalContext` stays in the conversation history, so inlining ~2.9KB of plan excerpt + progress tail every turn accumulated linearly across a long session (a ralph-loop with N iterations re-injected N times) — a dominant driver of context bloat and the frequent-compaction symptom observed on a consumer (db-engine: 25 compactions in ~95min). It now injects the parsimony ladder (unchanged) + a pointer to the plan file + the one-line Goal + pointers to the progress log and rules dir; the agent `Read`s the plan on demand. Per-turn payload dropped ~65% (2903 → ~1026 chars; the remainder is the ladder itself). The plan is still SHA256-attested (TAMPERED defense unchanged). e2e smoke + check_xrefs PASS.
- **`/implement` final wiring gate no longer trusts the progress file.** `run_validation.py`'s `wiring_summary` used to AGGREGATE the `wiring.{a,b,c}` field that the halt-loop itself wrote into `.progress-{slug}.json` — a value the LLM authored, so a hallucinated `"wiring": {"a": "pass"}` passed the final gate with zero verification. It now derives symbols from the committed diff and re-runs `check_wiring.py`; a self-report of pillar (a) pass over an actually-uncalled symbol is flagged `fabricated_wiring_evidence` and FAILs the gate. When no symbol can be re-verified the check is honestly `N/A`, never a PASS laundered from a claim. `mini_review.py` migrated to the same diff-derived re-verification (code-review 2026-06-20).
- **`CONTRIBUTING.md`** — contribution checklist aligned with the project's own cycle (develop-only branching, git-safety rules, TDD-first, `run_slice_tests.sh` + validators, CHANGELOG discipline, skill-authoring path). Closes the README's previously-broken `CONTRIBUTING.md` link.
- **CI now runs the 64 per-slice test suites** — `scripts/run_slice_tests.sh` runs every `skills/*/tests` suite in an isolated pytest process (plus the root suite) and the `test-python` CI job invokes it. Until now `pyproject.toml`'s `testpaths=["tests"]` meant CI only ran the 2 root test files, leaving ~600 slice assertions unguarded; six of them had silently rotted to red. The runner's header documents why isolation (one process per slice) is required: slices ship colliding module basenames (e.g. `check_research_coverage.py`) with different content, so a single wide process would resolve imports to whichever slice loads first — a configuration that never happens in real use (architecture-audit 2026-06-20).
- `skills/quality-init/scripts/gate_authoring/{detect,calibrate,emit}.py` — the 906-LOC `init_quality_gates.py` god-file was split into a thin orchestrator (362 LOC) plus three cohesive submodules (environment detection / threshold calibration / hook+settings emission), mirroring the existing `lib/` precedent. Pure code movement, no behavior change; all 36 quality-init tests pass unchanged (architecture-audit 2026-06-20).
- `skills/generated/README.md` — documents that `skills/generated/` is the `/skill-writer` → `/skill-validator` → `/skill-register` staging area, not a shipped skill slice (architecture-audit 2026-06-20).
- **Parsimony ladder — pre-write minimalism gate in `cycle-implement`** — new Source of Truth `rules/parsimony-ladder.md` operationalizes Unbreakable Rules 9/10/11 (Don't-Reinvent/KISS/YAGNI) as a 6-rung deliberation walked BEFORE writing GREEN-phase code (need-to-exist? → stdlib? → native feature? → installed dep? → one line? → minimum that works), with a hard guardrail that the ladder never sacrifices tests/validation/error-handling/security/accessibility. Proactive counterpart to the reactive dead-code (`/code-quality`) and scope-creep (`/review`) gates. Wired into `rules/cycle-implement.md` (Chain + per-iteration hard gate + Parsimony gate section), `skills/implement/SKILL.md` (Quality rules + GREEN step), and `skills/implement/prompts/implementation-prompt.md` (GREEN-phase deliberation). Inspired by the [ponytail](https://github.com/DietrichGebert/ponytail) ruleset's decision ladder.
- **Parsimony ladder re-injected every turn** — `hooks/userpromptsubmit-inject.sh` now prepends the terse ladder to `additionalContext` on every UserPromptSubmit (plan or no plan), so the minimalism deliberation does not decay across a long session. Previously the hook exited silently when no plan was active; it now always emits the ladder.
- **`/analysis` skill + `cycle-analysis` cycle** — PhD-level trajectory validation with empirical evidence. Opt-in per project via `rules/analysis-config.txt`. Post-release feedback loop: runs after `/release`, verdict determines shape of next iteration (ON_TRACK → proceed, WITH_RISKS → inject risk tasks, CORRECTION → corrective /to-plan, RETHINK → /discover-plan + redesign). 6 analysis modules (A1-Performance, A2-Complexity, A3-Architecture, A4-Memory, A5-Scalability, A6-Reference) weighted by project profile (engine/api/library/cli/infrastructure). Hypothesis-driven scientific method. Multi-language (Rust/Python/TypeScript/Go). Golden rule at `rules/analysis-golden-rule.md`.
- **`/quality-init` skill** — one-shot initializer that analyzes a target project (languages, frameworks, linter configs, test dirs), calibrates quality-gate thresholds from actual p90 code metrics, and generates Claude Code PostToolUse hooks that block code smells (complexity, long functions, deep nesting, too many params, long files, duplicate blocks) on every Write/Edit. Supports Python AST analysis natively + multi-language via lizard. 10-stage pipeline with round-trip validation. 36 unit tests. Declared in `scripts/check_xrefs.py § AUXILIARY_SKILLS` (one-shot bootstrap, intentionally absent from every cycle).
- **SOTA plan template upgrade** — `skills/to-plan/templates/plan-template.md` now has 4 new mandatory sections (`## Baseline Context`, `## Prior Art & Related Work`, `## Drawbacks & Risks`, `## Unresolved Questions`) + 1 new mandatory subsection per task (`#### Why this step` — ReAct discipline: action + reasoning chain) + 1 optional subsection (`#### Pseudo-code / Signatures`). Aligns with RFC tradition (Rust RFCs, Python PEPs, IETF), C4 / ARC42 baseline view, and ReAct planning (Yao et al. 2022). Goal: a junior implements without spelunking the repo.
- `skills/to-plan/SKILL.md § Step 1` — rewritten from a single-line "explore the repo" into a mandatory 5-command checklist (LoC + `git log` per touched file, `grep` for current callers, glossary extraction, prior-art search in `knowledge-base/references/` and `*-patterns` skills). The captured output feeds the `## Baseline Context` section directly — fabricated rows are now detectable.
- `skills/plan-confidence/scripts/check_baseline_context.py` — new structural checker (BaselineContextReport): verifies section presence, all 4 required subsections (Files / Callers / Glossary / Architecture boundaries), file-table data rows, and absence of template placeholder fragments. Stable id `soft_floor_baseline_context_incomplete`.
- `skills/plan-confidence/scripts/check_drawbacks_section.py` — new structural checker (DrawbacksReport): verifies `## Drawbacks & Risks` has ≥ 2 entries with severity + mitigation + owner, and `## Unresolved Questions` has entries OR explicit "(none — every decision is resolved)" marker. Stable ids `soft_floor_drawbacks_section_insufficient` + `soft_floor_unresolved_questions_section_missing`.
- 15 unit tests across `tests/test_check_baseline_context.py` + `tests/test_check_drawbacks_section.py` covering empty plans, missing subsections, complete plans, placeholder detection, fenced-code immunity, trailing-text-in-heading tolerance.
- **SOTA Phase 2: conditional concurrency + failure-scenarios enforcement** — `skills/to-plan/templates/plan-template.md` adds `#### Concurrency tests (only when applicable)` per task and `## Failure scenarios (when I/O external)` section. The Final Phase `## Acceptance Criteria` gains a "Failure scenarios green" checkbox tied to the new section.
- `skills/plan-confidence/scripts/check_concurrency_tests.py` — CONDITIONAL structural checker. Scans Baseline Context + Deep Dives + Files-to-edit + phase prose for concurrency signals (mutex, lock, atomic, goroutine, async/await, channel, threading, Promise.all, sync.Mutex, Arc<, tonic::, JCStress, ConcurrentHashMap, …). If signals detected, every task MUST have `#### Concurrency tests` containing either an acceptable race-aware test signal (race detector / loom / atomic-counter invariant / cancellation propagation) OR the explicit `(none — single-threaded)` escape. Plans with no concurrency signals are unaffected. Stable id `soft_floor_concurrency_tests_missing`.
- `skills/plan-confidence/scripts/check_failure_scenarios.py` — CONDITIONAL structural checker. Scans the same sections for external-I/O signals (HTTP clients `requests/httpx/fetch/axios/http.Client/OkHttp/RestTemplate`, DB drivers `psycopg/sqlalchemy/prisma/mongoose/sqlx/jdbc`, queues `Celery/RabbitMQ/Kafka/NATS/SQS/PubSub`, RPC `gRPC/WebSocket/tonic`, object stores `S3/GCS/boto3`). If signals detected, `## Failure scenarios` MUST have ≥ 1 populated row (table OR bullet) per dependency, or explicit `(none — no external I/O touched)` escape. Stable id `soft_floor_failure_scenarios_missing`.
- 15 unit tests across `tests/test_check_concurrency_tests.py` + `tests/test_check_failure_scenarios.py` covering no-signal-skipped, signal-detected-with-tests-pass, signal-detected-without-tests-fail, explicit-escape, fenced-code immunity, queue/gRPC detection, bulleted scenarios.
- `scripts/install.sh` — one-shot installer that copies the ecosystem into a consumer project as `target/.claude/` (plugin install layout), scaffolds an empty `knowledge-base/` tree, writes `settings.plugin.json` as the consumer's `.claude/settings.json`, and runs `check_xrefs.py` + `test_e2e_smoke.py` for post-install validation. Replaces the prior ad-hoc manual cp + filter + sed workflow.
- `settings.plugin.json` — sibling of `settings.json` with hook paths rewritten to `$CLAUDE_PROJECT_DIR/.claude/hooks/*` for plugin install layout. Used by `install.sh` to provision consumer projects without touching the canonical `settings.json`.
- `skills/code-quality/tests/test_cq_invoke.py` — 10 tests for the `cq_invoke` shared helper (script-missing / JSON-parse / timeout / malformed-JSON / non-zero-exit / no-network forwarding + verdict-merge severity tier mapping). Closes the `impljudge-cq-helper-red-tests-missing` finding raised by `judge-codex:implementation` on 2026-06-04 against the harden-fabrication-and-cq-gate slice.
- ADR D3 in `knowledge-base/plans/harden-fabrication-and-cq-gate-plan.md` — formal re-attest for the 2026-06-04 detoxification + extracted-helper consolidation. Closes the `impljudge-plan-amended-without-reattest` finding from the same judge-codex run.
- **`/implement` wiring summary now reports unverified pillar (a) tasks** — `run_validation.py`'s `wiring_triad` check previously folded tasks with no recorded `wiring.a` into neither pass nor fail, so a "non-negotiable" pillar (a) could read PASS with the rate diluted to a misleading value despite zero symbols actually verified. The summary now exposes `pillar_a.unverified` + `pillar_a_unverified_tasks`, making the gap between "no failures found" and "every symbol proven" explicit (code-review 2026-06-20).
- **README reworked as a professional OSS landing page** — added a table of contents, an outcome-shaped Highlights section, a Requirements table, working badge/section links, a Contributing + Security footer, and a proper MIT license section; corrected stale counts (skills 28 → 30, tests 62 → 632) and documented `scripts/run_slice_tests.sh`.
- **Slice tests no longer self-bootstrap `sys.path`** — the per-test `sys.path.insert(...)` lines (23 test files) were consolidated into each slice's `tests/conftest.py`; `skills/plan-improve/tests` and `skills/quality-init/tests` gained the conftest they were missing. Removes the dominant test-side coupling smell; every slice import is now bootstrapped in one place per slice (architecture-audit 2026-06-20).
- `pyproject.toml` — pytest now uses `--import-mode=importlib` and registers the `go`/`python`/`rust`/`typescript` detector markers, so duplicate test-module basenames across slices stop colliding under `--strict-markers`; coverage `source` widened to `["scripts","skills"]`. `testpaths` stays `["tests"]` because slice suites run isolated per-slice (see `run_slice_tests.sh`), not in one wide process (architecture-audit 2026-06-20).
- The `tests/__init__.py` markers were removed from 5 slice test directories (four empty, one a single comment line) — under `importlib` mode they forced every slice's conftest to register as the same `tests.conftest` module and abort collection (architecture-audit 2026-06-20).
- **`/plan-confidence` orchestrator integrates 4 new soft caps with sunset 2026-09-07** (2 unconditional + 2 conditional) — `run_structural.py` invokes `check_baseline_context` + `check_drawbacks_section` (unconditional, applies to every plan) and `check_concurrency_tests` + `check_failure_scenarios` (conditional, only fire when their signal patterns are detected in the plan). Every violation is listed independently in `hard_caps_triggered` (legacy plans without the new sections cap at score 89 → SHIPPABLE_WITH_CAVEATS). After 2026-09-07 the soft caps promote to hard caps at 70 (requires a new ADR). Migration path: re-run `/to-plan` against the updated template OR hand-edit the plan to add the four new sections + per-task `#### Why this step`. Conditional checkers do not affect plans without their signals (no race tests required for a UI markup change; no failure-scenarios required for a pure-logic refactor).
- `rules/plan-confidence-golden-rule.md` — "Rules that cannot be bent" table extended with the 3 new soft caps; new `## SOTA upgrade` section documents the migration calendar + rationale (115 active + 55 completed plans across consumers when this ships, so immediate hard cap would invalidate every in-flight plan).
- `skills/to-plan/SKILL.md § Quality Rules` — expanded from 12 to 18 rules; new rules cover `#### Why this step` subsection, Baseline Context section, Prior Art & Related Work section, Drawbacks & Risks section, Unresolved Questions section, conditional Concurrency tests subsection, conditional Failure scenarios section, and `file:line` citation requirement in Evidence.
- `skills/plan-confidence/fixtures/good-plan.md` — backfilled with the new 4 sections so it scores SHIPPABLE under the upgraded checkers (the previous fixture would have capped at 89 due to legacy structure).
- `scripts/test_e2e_smoke.py § check_skill_frontmatter` — bug fix: now validates the YAML frontmatter STRUCTURALLY with PyYAML instead of checking only for `"name:"` / `"description:"` substrings. The substring check let `roadmap-feature/SKILL.md` pass earlier this session even when its `description:` contained an unquoted colon that broke YAML parsing — Claude Code aborts skill discovery for the entire tree on a single invalid frontmatter, which caused the "no plan skills load on consumers" incident.
- `/implement` final validation gate (`skills/implement/scripts/run_validation.py`) now invokes `/code-quality` and fails when the CQ verdict is `FAIL_HARD` or `INVALID`. Closes audit gap on thesis 2 (code with assumptions): an agent can no longer declare `IMPLEMENTATION_COMPLETE` legitimately while dead exports or fabricated symbols slip through. `FAIL_SOFT` and `PASS_WITH_CAVEATS` surface as WARN (visible, not blocking). Escape via `--no-code-quality` (pre-code phase / CQ not installed). See ADR `0002-cq-gate-in-validate`.
- `rules/plan-confidence-golden-rule.md` — `fabricated_citation` row in § 1.2 + § "Rules that cannot be bent" updated to reflect M3 v0.1 ACTIVE (was "M3, future"). Hard cap 49 unchanged; enforcement is now code, not text.
- `rules/cycle-implement.md` — new "Hard gates (post-halt-loop)" section documenting the `/code-quality` gate in validation.
- `rules/cycle-code-quality.md` — Pre-conditions extended to call out the dual invocation (standalone before `/review` AND inline during `/implement`'s validation).
- `/auto-plan` extended from `discover + plan` to the **full pipeline**: `DISCOVER → PLAN → IMPLEMENT → CODE-QUALITY → REVIEW → RELEASE`. Default mode is full-pipeline; `--plan-only` retains the legacy behavior. Closes the gap where the orchestrator covered only 2 of the (now) 6 cycles. Adds `--no-release` to stop after `/review`, and `--bump=...` forwarded to `/release`.
- `/auto-plan` no longer asks the user to confirm depth (`AskUserQuestion` removed). Depth is now derived deterministically from the confidence band (HIGH→none, MED-HIGH→light, MED-LOW→full). CLI `--depth=` overrides the derivation.
- `/auto-plan` MUST-FIX absorption automated via `skills/auto-plan/scripts/inject_must_fix.py` (idempotent). Previously surfaced via an interactive question.
- `/review` pre-conditions tightened to require a `/code-quality` audit with verdict ∈ `{PASS, PASS_WITH_CAVEATS}` at `knowledge-base/audits/{slug}-code-quality-*.md`. Refuses to start otherwise.
- `rules/cycle-review.md` pre-conditions updated to list the code-quality audit as a required input.
- `rules/cycle-auto-plan.md` chain rewritten to declare the full pipeline + per-gate transitions + the human-approval gate at release-PR merge.
- `skills/review/SKILL.md` + `skills/review/scripts/consolidate_findings.py` + `skills/review/prompts/orchestrator-prompt.md` + 5 templates: severity vocabulary aligned with `rules/cycle-review.md` — was `BLOCKER / CRITICAL / MAJOR / MINOR / INFO`, now `BLOCKER / HIGH / MEDIUM / LOW / INFO`. A back-compat alias map (`CRITICAL → HIGH`, `MAJOR → MEDIUM`, `MINOR → LOW`) preserves findings from legacy agent definitions.
- `skills/review/scripts/consolidate_findings.py` verdict logic updated to match the cycle rule: NEEDS_FIXES fires when > 2 HIGH findings (matching `cycle-review.md § Verdicts` "≤ 2 HIGH with documented mitigation = READY_TO_MERGE"); previously fired on any single CRITICAL.
- `hooks/stop-validation.sh` promoted CHANGELOG-missing and secret-pattern findings from advisory warnings to HARD gates (exit 2), aligning with `rules/cycle-review.md § Hard gates (BLOCKER-level)`. TDD pairing and README production-claim checks remain warn-first. Escape hatch: `STOP_VALIDATION_WARN_ONLY=1`.
- `skills/implement/SKILL.md` corrected the documented hook enforcement (`hooks/boundary-check.sh` does NOT enforce DIP; DIP is a code-review convention per `rules/architecture.md § 4`). Removed misleading claim that the hook validates DIP.
- `skills/implement/SKILL.md` "Next step" updated from `cycle-review (when implemented) — manual review of PR + merge` to `/code-quality → /review → /release`. Removes stale doc that pushed users to the manual path when `/review` and `/release` already exist.
- `skills/review/SKILL.md` removed obsolete `INVALID` verdict mention (not in the review cycle's vocabulary per `cycle-rule-schema.md`).
- `scripts/check_xrefs.py` extended with Check 7: validates every `rules/<name>.md|.txt` reference inside SKILL.md bodies and Python scripts. Previously only the `## Cross-references` sections of cycle rules were scanned, which masked 8 rule references that pointed at files absent from the disk.
- `scripts/check_xrefs.py` chain-extraction regex relaxed to include the single-word `release` skill (joining the existing `to-plan / implement / review` hardcoded list and the kebab-case match).
- `README.md` skill count corrected to 25 (was 24 before `release` was added; original README claimed 25 erroneously when there were 24).
- `README.md` cycle diagram + project structure + flow A updated to include `cycle-code-quality` and `cycle-release`.
- `HOW-TO-USE.md` flow diagram + cycle-vs-skill table + first-time-setup table extended for `cycle-code-quality`, `cycle-release`, and the new rule files in `rules/`.
- Scripts `scripts/{check_xrefs.py, test_e2e_smoke.py, session-catchup.py, attest-plan.sh}` now detect dual-mode (standalone vs `.claude/` vs `.claude/plugins/cycle/`). They previously assumed only the `.claude/` layout, which made `check_xrefs.py` — when run from the project root — find `/home/paulo/.claude/` and report 1 skill instead of the actual 24.
- `scripts/check_xrefs.py` — main argument renamed from `--claude-dir` to `--ecosystem-dir` (alias `--claude-dir` kept for back-compat); render summary now shows `Ecosystem dir:` instead of `Claude dir:`.
- `scripts/test_e2e_smoke.py` — `required_sections` now requires only `Purpose`, `Chain`, and `Anti-patterns` (aligned with the new schema); also includes shell scripts under `scripts/` in the syntax check; validates `settings.local.json` when present.
- Standardized pre-condition headers across all `rules/cycle-*.md` to `## Pre-conditions` (previously 3 terms were in use: `Trigger conditions`, `Pre-conditions`, `When to use`).
- `README.md` — `scripts/` listing corrected from 4 to 5 (missing `test_e2e_smoke.py`); `knowledge-base/discoveries/` now documents `snapshots/` (hash-verified WebFetch snapshots from `/discover-execute`); description of `agents/` corrected to reflect current usage (only `/implement` runs); added `knowledge-base/backlog.md`.
- `scripts/README.md` — inventory now includes `statusline.sh` (consumed by `settings.json` `statusLine.command`), previously missing.
- `skills/to-plan/SKILL.md` § Step 2 — clarified that `/architecture-docs` is an example of a project-specific extension, not an ecosystem skill.
- Translated all repository documentation from Portuguese to English (CHANGELOG, SKILL files, templates, knowledge-base artifacts, agent records). Identifiers in code/schemas/tests renamed accordingly: `risco_estrutural` → `structural_risk`, `motivos` → `reasons`, `completude` → `completeness`, `evidencia` → `evidence`, `calibracao` → `calibration`. Smell-detector dictionaries reduced to EN-only tokens.

### Removed
- **The eight domain specialists left the kit.** `agents/engine-go.md`, `control-plane`, `data-plane-ts`, `db-engine`, `infra-terraform`, `contracts-auth`, `frontend-dashboard` and `platform-cli` described the repositories of ONE ecosystem. The routing table that named them was already derived per project and already shipped empty; the files stayed in source behind the `--with-domain-agents` flag, which left with them and is now refused with exit 2 instead of ignored. **They were never tracked** — `.gitignore` has ignored `agents/**` all along — so the flag copied files that existed on the machine of whoever wrote them and on no other, and `tests/test_kit_manifest.py` only verified it green there. What travels is the mechanism: `agents/README.md` (what a specialist needs to carry and at what granularity to cut the domains), `detect_domains.py` to derive the table, and `route_domain.py`'s exit 3 for when the table names a specialist nobody wrote. `rules/live-target.txt` and `rules/cycle-backlog.md § Domain routing` now ship empty in source too, not only on install.
- **Retired the in-cycle skill-distillation tail: `skill-writer` + `skill-validator` + `skill-register` (and the `skills/generated/` staging area).** These three home-grown skills implemented a blueprint→`{topic}-patterns`→staging→validate→promote pipeline that was never exercised end-to-end (generated/ only ever held `.gitkeep`), and the official `skill-creator` supersedes it with a simpler, evaluated, direct-to-`skills/` flow. Replaced all references across `rules/cycle-discover.md` (chain, phase contracts, rollback, cross-refs — the blueprint is now the cycle's terminal artifact and distillation is explicitly out-of-cycle), `rules/discover-blueprint-golden-rule.md`, `skills/discover-confidence/SKILL.md`, `skills/discover-plan/SKILL.md`, `skills/to-plan/SKILL.md` (Step 0 still consumes `skills/*-patterns/` if present; provenance updated), `skills/implement/SKILL.md` (the halt-loop still consults a matching `*-patterns` skill — wording updated from "registered" to "authored via /skill-creator"), `skills/review/templates/skill-domain-knowledge.md`, `skills/README.md`, `README.md`, `CONTRIBUTING.md`, `HOW-TO-USE.md`, and `scripts/patch_install.sh`. Dropped the now-dead `generated/`-special-case guards in `check_xrefs.py` + `validate_skill_frontmatter.py`. Skill count 30 → 28; `test_skill_count` updated. `check_xrefs.py`, `validate_skill_frontmatter.py`, `test_e2e_smoke.py`, and `generate-plugin-settings.py --check` all PASS.
- **Edge case vs negative case — the two-lens distinction is now a first-class concept in PLAN.** Until now the Cycle treated "edge case" as an umbrella (the term appears in ~22 files) and never named "negative case", so `/edge-case-plan`'s checklist silently mixed extremes-of-valid (boundary) with invalid-input/error-handling under one label, with no guarantee of balanced coverage. (1) `rules/testing.md` § 4.1 now defines the dichotomy — **edge** = extreme of a valid scenario ("does it hold at the boundary?"); **negative** = invalid/wrong/unexpected input ("does it fail-fast and recover with a *typed error*?", tying negative cases to the Error Handling rule) — plus an updated anti-pattern (covering one lens while ignoring the other is half a suite). (2) `skills/edge-case-plan/SKILL.md` restructures the pragmatic checklist into explicit **EDGE | NEGATIVE** rows per family (Inputs/State/I-O/Concurrency/Integration), adds a `Kind: EDGE|NEGATIVE` field + a coverage check to the report format, and a golden rule "cover both lenses". No new skill (KISS/YAGNI — `edge-case-plan` already did the work, it just lacked the lens). check_xrefs PASS.
- **`/implement` now enforces checkpoint↔reality consistency (the checkpoint can no longer silently drift from git).** Nothing forces the halt-loop to update `.progress-{slug}.json` per task at write time — it was a prompt-instructed discipline with only late, indirect detection. `skills/implement/scripts/check_checkpoint_consistency.py` cross-checks the checkpoint against the real git history in both directions: every `committed` task must point at a SHA that actually exists (catches a fabricated/stale SHA), and every plan task referenced by a real commit (the halt-loop's `T{N.M}:` commit-message convention) must be recorded `committed` — which catches the exact failure mode of "task finished + committed but the `.progress` update was skipped". Wired into `run_validation.py` (final gate, blocks handoff) AND `mini_review.py` (every phase boundary, for earlier detection). 8 unit tests (git-backed) + run_validation/mini_review integration tests. Honest limit: the backward check relies on the `T{N.M}` commit convention, so it complements rather than replaces the phase-completeness gate (code-review 2026-06-21).
- **`/implement` progress checkpoint now has a canonical schema + a fail-fast validator.** The halt-loop's `.progress-{slug}.json` is the contract between the iteration that WRITES it and six gate scripts that READ it, but its shape was never specified — and the example in `implementation-prompt.md` diverged from what the gates consume in three ways (a bare task object instead of a `{"tasks": [...]}` envelope, `task_id` instead of `id`, and missing `phase`/`files`). Each divergence made phase-scoped gates degrade SILENTLY (`phase_not_found`, no files detected, empty symbol derivation) with no "your checkpoint is malformed" signal (code-review 2026-06-21):
  - `skills/implement/templates/progress-schema.json` — JSON Schema, single source of truth for the checkpoint shape, referenced by both the prompt and the validator.
  - `skills/implement/scripts/check_progress_schema.py` — fail-fast validator (no `jsonschema` dependency; checks the structural subset the gates depend on). Wired into `run_validation.py` as the FIRST check (`progress_schema`): a malformed checkpoint now FAILs the validation loudly (Unbreakable Rule 8) instead of letting the downstream gates degrade. 10 unit tests + a run_validation integration test.
  - `prompts/implementation-prompt.md` PROGRESS step rewritten to show the correct `{"slug", "tasks": [ {id, phase, status, files, commit_sha, wiring} ]}` shape and spell out the gate-required keys.
- **`/implement` anti-bypass gates — the final validation now verifies what it used to take on faith.** Four guardrails close paths where the halt-loop could self-report success without proof (code-review 2026-06-20):
  - `skills/implement/scripts/diff_symbols.py` — derives the public symbols a phase actually introduced from the committed `git diff`, replacing the LLM's discretionary "identify the new symbols" step and the weak filename-stem heuristic. The symbol set the wiring check runs on is now read from git, which the LLM cannot fake without lying in a commit.
  - `skills/implement/scripts/wiring_recheck.py` — shared helper that RE-RUNS `check_wiring.py` per symbol. Used by both `run_validation.py` (final gate) and `mini_review.py` (phase boundary), so pillar (a) is verified the same trust-nothing way everywhere.
  - `skills/implement/scripts/check_acceptance_criteria.py` — parses the plan's AC/DoD checkboxes and enforces the mechanizable ones the command gates miss (file-size budget per changed file; CHANGELOG-updated), while surfacing non-mechanizable criteria (e.g. "backward compatibility preserved") as `criterion_requires_human_evidence` instead of accepting a self-ticked box. Wired into `run_validation.py` as the `acceptance_criteria` check.
  - `skills/implement/scripts/check_test_obligations.py` — when the plan declares `#### Concurrency tests` or `## Failure scenarios` (without the explicit `(none …)` escape), confirms at least one matching test exists in the tree. A generic green suite that never exercised a race or a 5xx no longer passes silently. Wired into `run_validation.py` as the `test_obligations` check.
  - 31 new unit/integration tests across `test_diff_symbols.py`, `test_wiring_recheck.py`, `test_check_acceptance_criteria.py`, `test_check_test_obligations.py`, plus regression tests in `test_run_validation.py` / `test_mini_review.py` (fabrication detection, diff-derived orphan symbol, gate wiring).
- Token budget system removed throughout the ecosystem: file `rules/token-budget.md` deleted, "Cost reality" / "Token budget" sections suppressed in `README.md` and `HOW-TO-USE.md`, token-based gates/stop-conditions removed from `rules/cycle-implement.md` and `rules/cycle-auto-plan.md`, and token cost annotations removed from `skills/{deps-audit, ast-grep, deck, marp-slide, review, excalidraw, discover-execute, implement, review/templates/*}`. Cycle choice is now driven by qualitative criteria (scope, complexity, shape of the work).
- Obsolete WebFetch snapshot `knowledge-base/discoveries/snapshots/slice-s0b-walking-skeleton-crd-first/d94162ad906bf098223e0ac948234ef2bc7cc67a7d8fc91d74d87495c4048574.md` deleted.

### Security
- **The `<!-- BLOCKED: -->` auto-marker was an automated bypass of the cycle's most important hard cap — removed.** The inherited `apply_fixes.py` annotated every unresolvable citation with `<!-- BLOCKED: path not found -->`. **Measured against the current checker on 2026-08-05:** a marked pointer leaves `fabricated` and enters `explicitly_blocked` — and `fabricated_evidence` **stops firing**. That is, a deterministic script turned an INVALID opportunity (cap 49) into an approved one, with nobody measuring anything. And `fabricated_evidence` exists precisely because everything downstream treats a pointer as a measured fact. A pointer that does not resolve means someone invented it or the code changed; both require a human or a new measurement, never a marker applied in bulk. The fixer now **reports and does not touch**, exits with code 3 so the halt-loop stops instead of iterating, and `test_never_writes_a_blocked_marker` locks the return — a failure there is a hole in the gate, not a formatting regression. A marker written by a human or by the measurement itself is still respected: the difference is who decided. The same prohibition was written into the halt-loop prompt, because Phase B could do by hand what Phase A stopped doing.
- **`/discover-plan` now plans a MEASUREMENT, and the falsification criterion comes before the questions.** The ancestor planned to investigate other people's code; this one plans to investigate ours. The step order carries the decision: `## Falsification` is written **at Step 4, before** the questions are drafted — never after seeing a result. A hypothesis nothing refutes produces a measurement that cannot fail, and its output will be believed precisely for having run clean. A plan target is pre-validated by opening the file, not by plausibility: a plan naming paths nobody can open is a plan that will produce fabricated evidence downstream, where everything treats it as measured fact. The mode is confirmed or reclassified at Step 2, with two explicit refusals — a `live-test` with no declared target does not become an improvised plan, and a `bug` whose defect nobody can express as a failing test comes back as an item instead of being planned blind.
- **`/discover-edge-cases` changes its question: from "what did the research forget?" to "what would make this measurement LIE?".** The difference is not rhetorical. Missing information is a gap you notice; a measurement that runs clean and produces a confident, wrong answer is indistinguishable from one that worked. The checklist became per-mode — `review` checks whether the code is **dead**, whether the caller **never existed** and whether the shape is **deliberate**; `live-test` checks the declared target, environment-vs-product, and a single observation about intermittent behaviour; `bug` checks whether the test will actually be **run** and whether the repro depends on local state only one person has; `evolve` checks whether the cost will be **counted** or estimated and presented as a count. And there is one verdict that admits no negotiation: **an unfalsifiable hypothesis is always MUST FIX** — every other defect produces a wrong answer someone can catch; this one produces a measurement that *cannot* fail.
- **`hooks/validate-command.sh`: the force-push guard now requires the force token to belong to the push (#6).** The guard verified "a push exists" and "a force token exists" as two independent matches over the whole command, so the `-f` of a *neighbouring* program was read as a force push: `rm -f tmp.txt && git push origin workspace`, `tar -xf pkg.tar && git push …` and `cp -f a b; git push …` were all rejected. It bit twice in one session — including the command that ran this issue's own repro script. The command is now split on command separators (`;`, `&&`, `||`, `|`) and each segment is judged on its own, so a force token only counts inside the segment that pushes. **Every** push in a compound is inspected: the issue suggested isolating the push's arguments with a greedy `sed`, which would have dropped the force in `git push --force origin a && git push origin b` — the segment loop keeps that case blocked, and a regression test pins it. Third over-block of this family, after #2 and #4; the `rm` guard's own uncorrelated matching (documented in #4) is untouched, but this segment-splitting helper is the cheap generalization that issue was looking for. Regression tests written first (TDD, RED: 3 failing); an intermediate version of the fix broke 4 previously-green cases (a bare `read` drops the last segment when it carries no trailing newline, silently skipping every single-segment command — i.e. a plain `git push --force`), caught by the suite and fixed with `|| [ -n "$seg" ]`. 63/63 pass.
- **`hooks/validate-command.sh`: closed 2 over-blocks that rejected legitimate commands (#2, #4).** Both guards matched raw text over the whole command string with no notion of context, so commands that never ran git — or never targeted a dangerous path — were rejected with exit 2. (1) **F9 (#2):** the F4 main-protection matched `git switch main` + `git commit` anywhere in the command text, so any command that merely *quoted* them was blocked — an `echo`, a commit message, and notably `gh issue create --body "…"` describing the F4 bypass itself, which made it impossible to document the very rule the hook enforces. The trigger was also terminator-sensitive (`git commit'` did not fire, `git commit ` did), so the false positive looked intermittent. Quoted content is now blanked before main-protection matching only — every other guard still matches the raw command, because there a quoted argument (`rm -rf "$HOME"`) is a real target, not a citation. (2) **F10 (#4):** `DANGEROUS_PATH_RE`'s `/\*` alternative had no anchor, so any `dir/sub/*` matched like a root glob and `rm -rf /tmp/deep/dir/sub/*` was blocked — contradicting the hook's own message, which tells the operator to scope deletions to deep subdirectories and `/tmp/`. The alternative is now anchored to the start of an argument. Regression tests written first (TDD, RED: 4 failing): `tests/hooks/test_validate_command.sh` covers both over-blocks plus the guards that must stay closed — the real `git switch main && git commit` bypass (quoted `-m` included), `checkout -b main`, `rm -rf /*`, `/home/<user>`, `$HOME`, `/etc/foo` — 49/49 pass. Honest limit recorded in #4 and deliberately NOT fixed: the three `rm` greps remain uncorrelated (they scan the whole command, not the same invocation). It bit this very commit — a message citing dangerous commands tripped the guard and had to be passed via `-F` instead of inline. Two fixes were tried and rejected as worse: blanking quoted content in that guard too would destroy real targets (a quoted argument there IS the target), and requiring command position per segment would let indirect execution through `xargs` and `find -exec` slip past, both caught today. A safe fix needs real shell tokenization. **Not yet propagated to consumers** — the hook is in the `scripts/patch_install.sh` manifest, so a kit patch run ships both fixes, but that run has not happened.
- **`hooks/validate-command.sh`: closed 5 git-safety guard bypasses + 1 over-block (#1).** The `rm -rf`, force-push, and git-rule guards matched a single fixed spelling/position, so equivalent rewrites of the same destructive command slipped through: `rm -fr`/`-Rf`/`-f -r`/`--recursive --force` (flag order), `git push origin main --force` and `+refspec` (force token not right after `push`), and `git -C DIR <subcmd>`/`-c K=V` (global options smuggled a forbidden subcommand past the `git <subcmd>` anchor; main-protection also read the cwd branch, not the `-C` target). Also `git switch main && git commit` (stale single branch read) and a jq fail-OPEN (missing/broken jq exited non-2 under `set -e`, which Claude treats as allow → all checks silently disabled). Fixes: strip git global options before matching; detect recursive intent in any flag order; match the force token anywhere in push args + leading-`+` refspec; apply main-protection on an inline `git switch/checkout main`; fail CLOSED when jq is unavailable/parse fails. Also narrowed the `/home` guard to bare roots so legitimate deep project paths under `/home` are allowed. Repro confirmed against the pre-fix hook; regression tests added first (TDD): `tests/hooks/test_validate_command.sh` now covers all bypasses (39/39 pass). Found while building the `review-cycle` project (which mirrored this hook); its M1 adversarial review + a 49-case bypass suite caught these.
- **`hooks/validate-command.sh` now blocks every local mutation of `main`, not just `git commit` (rules-audit 2026-06-28).** The "no work on main" gate only intercepted `git commit`, so `git merge`/`rebase`/`reset`/`cherry-pick` onto `main` slipped through — a hole in the PR-only invariant that `cycle-release.md` promises. The gate now blocks `commit`/`merge`/`rebase`/`reset`/`cherry-pick` when `HEAD` is `main`. `push` is intentionally NOT blocked (release legitimately pushes a tag; `push --force` is already blocked globally on every branch). Regression test added first (TDD): `tests/hooks/test_validate_command.sh` now covers merge/rebase/reset/cherry-pick blocked-on-main and allowed-on-develop (28/28 pass).
