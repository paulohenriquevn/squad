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
| `check_gate_mechanisms.py` | Every declared hard gate names the mechanism that computes it |
| `check_merge_autonomy.py` | Does the remote let the system merge its own passing PRs to the trunk? Envelope floor 2 makes that a premise of running the kit, so it is asked at intake — a required human approving review would park every item at an open PR at the end of its chain. Reports NOT CHECKED distinctly from PASS: an absent or unauthenticated `gh` tested nothing |
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
| `verify_ecosystem.py` | End-to-end smoke test; runs the checks above and reports one verdict |

### `cycle/` — the cycle at runtime

| File | Purpose |
|---|---|
| `advance_items.py` | Close the items a release actually shipped, from the stream rather than a guess |
| `backlog_status.py` | Mechanize the BACKLOG.md status transitions — and the impediment edges |
| `cycle_events.py` | The cycle's phase transitions, as a stream instead of an excavation |
| `route_domain.py` | Route a repo (or a B-NNN item) to its domain specialist |
| `halt_disposition.py` | Where an item goes when a phase stops, now that no phase between DISCOVER and ACCEPTANCE may address a person. A halt is the queue's own work unless it names a material impediment — and an item the queue returned twice for the same cause is retained on that evidence rather than on a regex |
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
| `lens_review.py` | The kit's own defect lenses, pointed at a diff instead of at history. It parses the six lenses out of `kit_audit_workflow.js` rather than keeping a second copy, and raises when it cannot — a review against zero lenses reports every diff clean. Its findings never block a landing: a model's opinion is not grounds to stall an unattended fleet, so they become issues and get fixed on the next pass |
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
