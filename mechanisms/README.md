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
| `fleet_idle.py` | Where the fleet's time went, from the lead's own log: idle vs productive, per decision kind, and which sessions were never handed work |
| `fleet_wall.sh` | One tmux session showing every executing session side by side, read-only by default, plus a live status pane |
| `fleet_status.sh` | Every session at once, from the shell: what each is doing, what the lead handed out, what the queue would pick |
| `fleet_queue_line.py` | The selector's verdict as one line for `fleet_status.sh` — a file of its own because a heredoc would take the stdin the pipe needs |
| `session_catchup.py` | Rebuild context after `/clear`, a fresh session, or a compaction |
| `start_fleet.sh` | Start a fleet of executing sessions and one watchdog over all of them |
| `statusline.sh` | The single line Claude Code shows in its status bar |

### `distribution/` — into a consumer, and kept in step

| File | Purpose |
|---|---|
| `install.sh` | Install the kit into a target project |
| `patch_install.sh` | Apply one session's delta to a consumer's `.claude/` tree |
| `sync_consumers.py` | Propagate a kit delta to consumers WITHOUT erasing local improvement |
| `generate_plugin_settings.py` | Generate `settings.plugin.json` from `settings.json` |

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
