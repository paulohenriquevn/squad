# mechanisms/

What COMPUTES the kit's verdicts. Nothing here is user-invocable: skills, hooks,
commands and the CI call these, and every verdict the kit reports is produced by
one of them rather than asserted in prose.

The directory was called `scripts/` until 2026-09-01. The name described the
shape of the files; it said nothing about the six different jobs they do, and a
flat directory of 36 files with 17 of them named `check_*` was navigated by
memory. The families below carry the meaning now.

## Families

| Family | What lives here | Called by |
|---|---|---|
| `gates/` | Everything that MEASURES the kit against its own contracts, plus the runner that drives them | CI, `verify_ecosystem`, `install.sh --strict` |
| `cycle/` | The cycle at runtime — routing, the event stream, status transitions, attestation | skills, during a cycle |
| `fleet/` | Many sessions at once, and the surface a person watches them through | `settings.json`, the operator |
| `distribution/` | Getting the kit into a consumer and keeping it in step | a person, once per install |
| `conventions/` | Shared parsing, imported by the rest | the other families |

**The import namespace is flat.** `mechanisms/gates/check_xrefs.py` imports
`ecosystem_utils` by name, not by package path — the families are directories,
not Python packages. A file reaching a sibling family adds that directory to
`sys.path`; `tests/conftest.py` adds all five, so a test never has to know which
drawer a module was filed in.

**Paths resolve two levels up.** A file here is at `mechanisms/<family>/x.py`, so
the repository root is `parents[2]`. Getting this wrong does not crash — it
silently points a default at `mechanisms/` and the gate reports a clean run over
a directory that holds none of what it was looking for. That failure was
measured during the rename itself: `check_xrefs` resolved `skills/` one level
short and reported five real skills as orphans.

## Inventory

Every file, and what it is. `gates/check_mechanisms_inventory.py` refuses a file
that is not listed here and a listing with no file — the previous README declared
*"Every new script MUST be added to the inventory above"* and covered 5 of 36,
which is why the rule is now computed rather than requested.

### `gates/` — measurement

| File | Purpose |
|---|---|
| `check_english_only.py` | Refuse Portuguese in a repository that is English by policy |
| `check_contribution_conventions.py` | Do the commits follow the conventions this project declares? Reads `rules/contribution-overrides.txt` first, then the kit's defaults. The subject limit is 85 — DERIVED from 300 of this repository's own subjects (median 71, p90 85), not the 72 every style guide repeats: a check failing 44% of what a repository has always done teaches people to ignore it. Refuses a co-authorship trailer in any spelling, and refuses an override that tries to allow one |
| `check_chain_preconditions.py` | Can this installation FINISH the chain? Asked before it starts, not at the final gate. Measured on a consumer that ran for hours and produced 85 items, 13 plans scoring 89-100, and zero implemented — every plan INVALID on one unconfigured file readable in milliseconds beforehand. Checks only facts no amount of good work can overcome: a language config with no ENABLED row, an enabled row whose manifest is absent, an empty routing table, a missing registry, and a registry where NOTHING is approved — an unapproved backlog is a queue of hypotheses, and a run over it decides by inference what only a person may decide. A judgement — which languages, whether a soft cap deserves an ADR — is deliberately NOT here, because a gate that waits on a decision is a gate that never lets you start |
| `_contract.py` | What every gate in this directory agrees to: one flag for the tree to sweep (`--root`, older spellings kept as aliases) and the exit vocabulary `0` clean / `1` finding / `2` could-not-measure. Not a base class — the directory has no ABCs and that restraint stays; it is a name and a helper, so a caller can invoke any gate without knowing which one it is. Before it there were eight spellings of one question across 33 gates, and three separate callers each carried the whole table. `check_gate_mechanisms.py` reports any gate that drifts off it |
| `check_gate_mechanisms.py` | Does every declared hard gate name what computes it? Three accepted forms: an executable, a pointer to the rule that owns it, or an exemption — and since 2026-09-08 an exemption must declare its CLASS. `judgement` (permanent by decision), `debt` and `regression` (both dated, and the second means a mechanism EXISTED and was withdrawn), `external`, `composed`. Summing them said "N gates are not mechanized" and hid that lost coverage read exactly like debt never paid. `--max-debt-age` makes ageing enforceable; off by default, because the ceiling is the operator's call |
| `check_verdict_bands.py` | Does every declared verdict name its band? Sibling of `check_orphan_verdicts.py`, which asks whether anything can emit it; this asks whether anything knows what it means for the flow. An unreadable registry is reported, never treated as full coverage |
| `check_panel_capability.py` | Can a review panel be formed at all, for EVERY phase one gates? Three seats per phase, at least one from a recognised family outside the kit's own, and every seat reachable — a `builtin` seat naming an agent this project has, anything else on PATH. Asked at intake because otherwise every item is measured, planned, and returned at a panel that was never formable. Counts PER PHASE: six valid rows can still leave one gated phase with two |
| `check_panel_approval.py` | Refuses to advance a DISCOVER or PLAN document the panel did not carry. **A missing record is not an approval** — a phase that skipped its panel must not be indistinguishable from one whose reviewers all approved. Three outcomes, not two: returned is `NEEDS_REVISION` and editing can lift it; did not convene is `ITEM_IN_FLIGHT`, an `access` impediment, because sending an author to rewrite a document nobody found fault with is the wrong action |
| `check_auditor_coverage.py` | Refuses a REVIEW whose required independent audits did not happen. Runs each plugin's OWN report checker from its install path rather than copying the contract — a second copy diverges the day it changes, and the kit would accept a shape the plugin itself rejects. Carries `## Verdict` and `## What Was NOT Analyzed` out of every report, because the seam between two honest halves is where the coverage caveat gets dropped. Severity is carried as a SIGNAL and never gates: it is a parse of another tool's markdown, and an inability to measure must not become a failing measurement either |
| `check_produced_files.py` | The RUNTIME half of the same guarantee. The static gate below cannot see a writer whose destination never passes through `squad.paths` — one taken from argv, joined onto the installed kit, or handed down by a caller; tracing all 135 call sites through the AST left 64 UNKNOWN. So this seeds a scratch project, runs 18 mechanisms, and looks at the disk. Anything produced outside the write root must match a row in `rules/write-exemptions.txt`, which requires a class and a reason. Reports its own coverage, and refuses to count a probe that errored as one that ran |
| `check_write_containment.py` | Proves nothing this system writes escapes `<project>/.squad/`. Every data-root literal lives in `squad/paths.py`, and this fails any other kit file that spells one in CODE — so every path a writer builds came from the owner, and the owner produces one root. The alternative, reading 164 writing call sites, is not a proof anybody can re-run. Strips prose first and BLANKS it rather than deleting, because a finding reported at a line that holds something else is a finding readers stop trusting |
| `check_prose_write_paths.py` | The third half, and the one neither sibling can see. `check_write_containment.py` reads CODE and strips prose — correctly, since the kit argues in prose about the directories it forbids. But a `SKILL.md` does not argue; it INSTRUCTS, and an agent following `Persist to records/brainstorms/…` creates a legacy root without importing the owner or running a mechanism. Scans `skills/`, `commands/`, `agents/`, `hooks/` — not `rules/` or `docs/`, which argue. Prose that genuinely names a legacy root marks itself `<!-- write-path: reason -->`, and an empty reason does not count. Measured 2026-09-10, when a live session hit it: 164 instructions across 49 files |
| `check_emitted_verdicts.py` | The mirror of `check_orphan_verdicts.py`: that one asks whether every DECLARED verdict is reachable, this one whether every INSTRUCTED verdict is declared. The second failure is louder — `cycle_events.py` REFUSES an undeclared verdict, so the phase records nothing at all and reads as one nobody ran. Measured 2026-09-10: five skills passed a halt-loop completion promise where a verdict goes, including three of the four brainstorm phases. Honours the runtime's rule that a rule with no `## Verdicts` section permits any verdict, but separates that from a `--cycle` naming no rule at all, which the runtime cannot afford to distinguish |
| `check_data_root.py` | Reports a project still holding data outside `<project>/.squad/`. Reports and never moves: a migration run inside a repository the kit does not own is the kit writing to somebody else's project. `SPLIT` is the loudest state — once both roots hold data, readers resolve the write root and the old copy is unreachable while still looking current |
| `check_review_binding.py` | **Not yet fed:** nothing in this kit writes the `{slug}-review-*.json` record carrying `reviewed_sha` that it reads, so the refusal has never fired and every run returns NO_RECORD. What it WOULD do: refuse to promote work whose review is about a different commit. A verdict said the work was examined and never said WHICH work, so a commit landing after consolidation travelled on an approval that never saw it — the approval was bound to a NAME, not a CONTENT. Reports what moved and refuses only on overlap with the files the review examined: a gate that blocked on any movement would be bypassed within a week. A record listing no files widens to every move rather than assuming harmlessness |
| `check_merge_autonomy.py` | Does the remote let the system merge its own passing PRs to the trunk? Envelope floor 2 makes that a premise of running the kit, so it is asked at intake — a required human approving review would park every item at an open PR at the end of its chain. Reports NOT CHECKED distinctly from PASS: an absent or unauthenticated `gh` tested nothing |
| `check_release_reachable.py` | Does the release this run says it published actually exist, and is it public? The chain ended at `gh release create` and emitted `RELEASED` — so a DRAFT release, or a `gh` call that failed after the tag was already pushed, produced that verdict over an artifact no consumer can fetch, and `RELEASED` is what ADVANCE reads to write `shipped`. Checks existence, not-draft, and that the release names the tag that was cut. Deliberately NOT a claim that a package is installable from a registry, nor that the delivery works — the first needs a registry, the second is `/acceptance`. Runs for every item, with or without a milestone. An absent or unauthenticated `gh` exits 2 |
| `check_wired_hooks.py` | Does every hook this install WIRES point at a file that is there? Routed by a consumer whose install predated `260892f`: `hooks/validate-command.sh` was still wired long after the kit deleted it, and the retired shell hook diverges from the live Python one in 2 of 36 payloads — both permissively, allowing `git stash` and `--force-with-lease` on the workspace. `.kit-hooks.json` could not withdraw it because that baseline only exists from 2026-09-02; a missing FILE needs no baseline. Reports, never edits a consumer's settings. A command naming no file is not a finding — a shell one-liner is wired on purpose, and reporting it would make the check noise |
| `check_evidence_freshness.py` | How old is each open item's evidence, and does every pointer it cites still resolve? Age is REPORTED and never fails — a thirty-day-old measurement of something nobody touched is still true, and failing on age trains people to re-measure on a calendar rather than on a reason. A dead pointer FAILS, and only for `triaged`/`approved` items: a settled item's pointers are history, and failing on them makes the check red forever. Written by a consumer session and ported rather than reimplemented — three of its decisions came from measurement (paths resolve against package source roots, no `\\b` before a dotted path, the LATEST date in a block wins) and a rewrite from the description would have lost all three |
| `check_rule_identity.py` | Can a rule be cited by something a rename cannot break? A rule's only handle was its path: 1209 citations of `rules/<name>.md` inside the kit, and on one consumer's registry 33 of 109 backlog items citing a path in here — 5 of its 6 dead pointers were paths that had MOVED. Checks that every rule declares an id, that ids are unique and never reused, that a retired rule names its successor (ESLint's `replacedBy`), and that every id written down still resolves. Deliberately does NOT demand prose cite ids over paths — a file reference in a sentence about that file is not a defect |
| `check_tag_integrity.py` | Is a release tag the object `cycle-release.md` says it is — annotated, and naming a commit contained in the trunk? It replaces two clauses that between them checked nothing: one declared `git tag --verify`, which demands a GPG **signature** and therefore refuses every unsigned annotated tag this kit cuts (`error: no signature found`, exit 1); the other was carried as open debt with the note that "nothing inspects the tag object's type or the branch it was cut from". Two unmechanised clauses about one object, and the contradiction between them survived precisely because no code ever had to hold both. Signature is deliberately NOT checked. An absent tag exits 2 — an absent tag is not a passing tag |
| `check_install_drift.py` | Has a consumer's install and this kit drifted, and which way? |
| `check_orphan_verdicts.py` | Every verdict a contract declares must be reachable by something |
| `check_phase_drift.py` | The declared phase plan, confronted with what actually ran |
| `check_phase_emitters.py` | Every declared phase must have something that records it ran |
| `check_phase_numbering.py` | The phase number a skill claims must agree with the chain that orders it |
| `check_prose_tests.py` | Find tests that pin the WORDING of prose the kit ships |
| `check_reference_leakage.py` | Detect literal copies of third-party study material inside the project |
| `check_semantic_names.py` | A file's name is the first documentation anyone reads |
| `check_skill_map.py` | `skills/map.md` must list every skill on disk, and only those |
| `check_sop_run.py` | The run record: what was judged, and why it differed |
| `check_sop_structure.py` | The shape of an operating procedure, checked |
| `check_squad_map.py` | Confront `rules/squad-map.md` with the directory it claims to describe |
| `check_readme_advisory_skills.py` | README.md and HOW-TO-USE.md must list only skills that exist on disk |
| `check_wiki_migration.py` | Report a project still reading its durable knowledge from the old root |
| `check_xrefs.py` | Cross-reference validator for the planning ecosystem |
| `check_mechanisms_inventory.py` | This README against this directory, both ways |
| `validate_skill_frontmatter.py` | Validate SKILL.md frontmatter conformance across all skills |
| `verify_ecosystem.py` | End-to-end smoke test over a **subset** of the gates above, reported as one verdict. It is not the whole table: the rest run from CI, from a hook, or from the skill that owns them, and `tests/test_every_gate_is_reachable.py` is what proves each gate has a trigger somewhere. One green verdict here does not mean every gate in this directory passed. |

### `cycle/` — the cycle at runtime

| File | Purpose |
|---|---|
| `advance_items.py` | Close the items a release actually shipped, from the stream rather than a guess |
| `backlog_status.py` | Mechanize the BACKLOG.md status transitions — and the impediment edges |
| `cycle_events.py` | The cycle's phase transitions, as a stream instead of an excavation |
| `next_backlog_id.py` | The next free `B-NNN`, from every id ever spent rather than from the registry's own contents |
| `route_domain.py` | Route a repo (or a B-NNN item) to its domain specialist |
| `verdict_bands.py` | Which band each verdict is in — clean, caveats, redo, structural, or orthogonal — read from `rules/verdict-bands.txt`. Replaces a frozenset that lived inside `check_phase_drift.py` with no owner: 23 of 47 verdicts were classified nowhere, and the unclassified ones silently disabled that checker's out-of-order detection |
| `review_panel.py` | Tallies the three reviewers that judge a DISCOVER opportunity and a PLAN plan: 2 of 3 advances the document, below that it returns as `NEEDS_REVISION`. The counting is trivial and is not the point — what it REFUSES is: the author on their own panel, three votes from one model family, an abstention read as agreement, a verdict with no reasoning, one reviewer voting twice, and a voter the assignment never named |
| `convene_panel.py` | Assigns the reviewers that must judge one DISCOVER or PLAN document, resolving each seat against the specialist agents the running project actually has. Writes the assignment because the votes must be checkable against it: convening is theatre if the panel that voted may differ from the panel convened. It does not vote and cannot — the judgement a panel exists for is the one no script can make. A seat it cannot fill is an ABSENT reviewer, exit 3, never a rejection |
| `panel_brief.py` | What each assigned reviewer must READ and what it is being asked, derived from the phase: artifacts from the phase, contract from its golden rule, questions from that contract. A reviewer told "review this" reviews whatever it decided to look at, and three such reviews are three opinions about three different questions. Refuses a phase with no contract |
| `cast_vote.py` | Records one vote, refusing what the tally would refuse later — an unassigned reviewer, the author, a duplicate seat, a reason under fifteen words. `review_panel.py` validates a COMPLETE panel and refuses it whole, which is right at tally time and useless while collecting: the session learns its first vote was invalid after spending three invocations |
| `critic_round.py` | Records one critic round and decides whether the work goes BACK or the disagreement escalates. `CRITIC_RETURNED` sits in the `redo` band on FAIL_SOFT's argument — walling ordinary rework walls every loop that is working correctly — so the agent fixes what was named and the phase re-runs inside the same autonomous span. After the declared rounds the disposition passes to `halt_disposition.py`, the escalation this kit already has rather than a second one |
| `select_auditors.py` | Which independent auditors a change must face, DERIVED from the domain `detect_domain.py` already computes and never chosen by the reviewing agent — the same rule that refuses to seat an author on the panel judging their own document. Emits the exact command each plugin takes, with the scope flag and the output directory the gate will look in. Records whether the run is scoped or whole-tree, because a base is never guessed and a scoped audit must not read as a full one |
| `halt_disposition.py` | Where an item goes when a phase stops, now that no phase between DISCOVER and ACCEPTANCE may address a person. A halt is the queue's own work unless it names a material impediment — and an item the queue returned twice for the same cause is retained on that evidence rather than on a regex |
| `promote_to_develop.py` | `workspace → develop`, and nothing else. Promotion lived inside `/release`'s chain, so integrating required versioning — measured here as 349 commits on `workspace` behind zero tags. Cuts no version, and a test asserts it never reaches for one |
| `delegated_decision.py` | The line between a wall a sponsor can delegate and one nobody can: a choice between named alternatives, versus an absent machine, an unelapsed series, or a system that is not standing. Impediments are matched first and win, because a wall that is both is an impediment; unrecognised prose stays walled, since no match is not consent |
| `apply_delegated_decisions.py` | Retires the walls the classifier calls delegable and leaves the decision in their place — never deleting a wall, refusing one with no rationale, and refusing a delegable item nobody actually decided |
| `attest_plan.sh` | Compute a plan's SHA256 and write it to `.attestations/{slug}.sha256` |
| `run_gates.sh` | A project's quality gates in parallel with a per-gate ceiling: wall-clock becomes the slowest gate instead of their sum, and one hang cannot eat the budget of the rest |
| `run_slice_tests.sh` | Run every skill slice's test suite in ISOLATION |

### `fleet/` — many sessions at once

| File | Purpose |
|---|---|
| `squad_lead.py` | Keep an executing session moving, without deciding anything for it |
| `pipeline_orchestrator.py` | Schedule many backlog items through the cycle, one stage each, concurrently |
| `pipeline_workflow.js` | The `backlog-pipeline` workflow definition the orchestrator drives |
| `start_lead_session.sh` | The lead as a named Claude session — addressable by peers, and the only shape that can invoke the pipeline |
| `claude_stream.py` | Talking to Claude Code over its own protocol: verdict, cost and session id as fields instead of prose to be recognised |
| `kit_repair_workflow.js` | N audited findings repaired at once, one git worktree each, test-first, every branch checked by an agent that did not write it |
| `kit_audit_workflow.js` | The kit hunting itself for its own recurring defect patterns, one lens each, every finding then handed to an agent trying to refute it |
| `kit_issues.py` | The kit's OWN registry, so an idle fleet can work on the kit: open issues split into what a lane may take and what waits on a person |
| `run_remote.sh` | Heavy work on the runner instead of the workstation, checked reachable first and refusing to fall back to local — the fallback is how the work comes home without anyone deciding it should |
| `session_ready.py` | Did a launched session reach a prompt, or is it sitting in a first-run dialog? The check both fleet launchers lacked |
| `dispatch_to_lane.sh` | One unit of work to one fleet lane, refusing a lane that is not at a prompt — work typed into a busy lane interrupts its turn, and into one in a dialog answers the dialog |
| `fleet_router.py` | The wiring between "work exists" and "a lane is doing it". Reads the consumer's queue first and the kit's issues only when it is walled, assigns one unit per free lane, and remembers what it routed in an append-only log so a restart resumes instead of double-assigning |
| `fleet_dispatch_workflow.js` | Two-phase workflow (Repair RED→GREEN, Verify independent) for executing kit issues; called by `dispatch_to_lane.sh` with structured JSON payload containing issue metadata and branch name |
| `issue_lifecycle.py` | Issue automation — label with 'in-develop' when a commit reaches develop, close when a verified release tag is detected |
| `lens_review.py` | The kit's own defect lenses, pointed at a diff instead of at history. It parses the six lenses out of `kit_audit_workflow.js` rather than keeping a second copy, and raises when it cannot — a review against zero lenses reports every diff clean. **Run by hand: `python3 mechanisms/fleet/lens_review.py --repo . --branch <branch>`.** This row described it as a step inside the landing flow — "so they become issues and get fixed on the next pass" — and nothing invokes it, so no diff was ever reviewed against the lenses. Wiring it into `fleet_supervisor.sh` is a COST decision, not a missing line: it spends one model call per lens per branch, on every landing, unattended. That is a choice somebody makes; until then this says what it is. Its findings would never block a landing either way — a model's opinion is not grounds to stall an unattended fleet |
| `file_findings.py` | The step between a sweep and a work queue: audit findings that survived an agent trying to refute them become issues a lane can take. Refuses a killed claim, a claim with no evidence, one the tracker already holds open or closed — and refuses everything when the tracker cannot be read, because filing without dedup turns one defect into a duplicate per run |
| `fleet_supervisor.sh` | The loop that runs the two above and nothing else: route what is startable, land what is verified, repeat. It makes no decision either mechanism refuses to make, and when both have nothing to do it says so rather than manufacturing activity |
| `fleet_lander.py` | A lane's verified branch onto the working branch, or the reason it may not. Runs the suite on the branch and again on the merge, in two scratch worktrees, and pushes only what it watched pass. Never closes an issue and never opens the PR to `develop` — both are the operator's |
| `vera.py` | The EMITTER behind `vera-technical-arbiter`: one arbitrated problem turned into one issue a lane can execute — title, body, labels, schema. It formats a judgement and never supplies one, so the lens, the severity and the solution are inputs; given none it refuses rather than guessing. It used to guess, by matching substrings against the problem text (#38) |
| `fleet_idle.py` | Where the fleet's time went, from the lead's own log: idle vs productive, per decision kind, and which sessions were never handed work |
| `fleet_wall.sh` | One tmux session showing every executing session side by side, read-only by default, plus a live status pane |
| `fleet_status.sh` | Every session at once, from the shell: what each is doing, what the lead handed out, what the queue would pick |
| `fleet_queue_line.py` | The selector's verdict as one line for `fleet_status.sh` — a file of its own because a heredoc would take the stdin the pipe needs |
| `session_catchup.py` | Rebuild context after `/clear`, a fresh session, or a compaction |
| `start_fleet.sh` | Start a fleet of executing sessions and one watchdog over all of them |
| `statusline.sh` | The single line Claude Code shows in its status bar |
| `squad_status.sh` | The state of the squad from any shell — the kit's tree, the consumer's queue, and what is actually executing. Says outright what it cannot see: the coordinating session's own progress lives inside that session, and silence here is not proof of idleness |
| `workflow_watch.sh` | A running workflow's agents, watched from OUTSIDE the session that spawned them. Reads the JSONL transcripts they write as they work, because the single-instance architecture took the observation surface with it when it retired the tmux lanes. Reports how long a file has been silent and never guesses whether that is thinking, waiting or finished |

### `distribution/` — into a consumer, and kept in step

| File | Purpose |
|---|---|
| `install.sh` | Install the kit into a target project |
| `patch_install.sh` | Apply one session's delta to a consumer's `.claude/` tree |
| `sync_consumers.py` | Propagate a kit delta to consumers WITHOUT erasing local improvement |
| `generate_plugin_settings.py` | Generate `settings.plugin.json` from `settings.json` |
| `merge_settings.py` | Merge the kit's `settings.json` into a consumer's, entry by entry: the kit's wiring is refreshed, the consumer's own hooks and permissions survive, and a recorded baseline is what lets a retirement be told from a project's own addition |

### `conventions/` — where things live and what shape they have

| File | Purpose |
|---|---|
| `ecosystem_utils.py` | Layout detection: standalone repo, `.claude/` install, or plugin root |
| `sop_format.py` | The SOP format, parsed in exactly one place |
| `touched_slices.py` | Which test suites a set of changed files can affect. Widens to everything when a path cannot be attributed, because narrowing runs fewer tests and still reports success |
| `installed_plugins.py` | Where a Claude Code plugin lives, from the machine's own manifest instead of a guess. `rules/review-panel.txt` recorded that verifying a plugin-supplied reviewer needed something the kit did not have; the manifest was on disk the whole time, and every entry carries an `installPath`. Computes no verdict and runs nothing — a caller that cannot find a plugin has a coverage gap to report |

## Adding one

Put it in the family whose consumers already call that kind of thing, add the row
above, and let the gate confirm the two agree. A file that belongs to exactly one
skill is not a mechanism — it lives in `skills/{name}/scripts/`, which is a
different directory with a different owner.

## VERA — the arbiter and the emitter

Two things share the name, and the split is what keeps the verdict honest.

**`agents/vera-technical-arbiter.md` is the arbiter.** It reads the code, decides
which principle a problem violates, how severe it is, and what the fix is. That is
a reading, and only a reader can do it.

**`mechanisms/fleet/vera.py` is the emitter.** It takes that judgement and formats
one issue a lane can execute: the title, the body, the labels, the schema. It is a
formatter, and formatting is computation.

**Lenses:** SOLID · DRY · Coupling · Fail-Fast · Clarity. The module holds each
principle's canonical statement, and selects one by the lens it was handed — never
by reading the problem.

**It refuses instead of guessing.** No lens, no severity, no evidence, no
`file:line`, or a solution that does not say what changes and how to verify it:
each is a refusal (exit 2), because the output is filed as an issue and a lane
executes what it says.

Until 2026-09-08 it guessed all of it, by substring. `--refs app/main.py:57` sized
a typo as a two-week refactor, because the literal `"57"` was matched against the
stringified context; a secret in a log was answered with "Make structure
immediately obvious", because the five solutions were selected by lens alone and
never read the problem. That is the shape `mechanisms/cycle/delegated_decision.py`
names in its own docstring — *"a number that measured nothing but its own
matcher"* — fixed there first, and now here (#38).

```bash
python3 mechanisms/fleet/vera.py B-022 \
  --problem       "Engine cannot deploy while the dashboard is down" \
  --evidence      "init() calls the dashboard health check before serving" \
  --refs          "api/internal/routes/engine/init.go:156" \
  --lens          solid \
  --severity      high \
  --solution      "Decouple the engine from the dashboard health check" \
  --what-changes  "init() stops calling the dashboard; the check moves behind a port" \
  --how-to-verify "the engine deploys with the dashboard down"
```

Result: an issue titled `[high] Decouple the engine from the dashboard health
check`, labelled `severity:high`, `size:t1`, `lens:solid`, carrying the evidence
and the reference it was given.
