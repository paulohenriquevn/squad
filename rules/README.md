# Rules

Source of truth for cycle contracts, golden rules, thresholds, and allowlists.
Every cycle reads its contract from here; every quality gate references a golden
rule file.

## Why a rule lives here and not inside the skill that reads it

The obvious rearrangement is to push a rule only one skill uses into that skill's
directory. **It would destroy the consumer's configuration on the next update**,
and the reason is in `install.sh`:

```
install.sh  →  rm -rf <target>/.claude/skills/ ; cp -r source   (full overwrite)
               rules/ and agents/ are snapshotted and preserved
```

`skills/` is deleted and replaced every install. `rules/` is where a project's own
configuration lives — the routing table, the enabled languages, the live target,
the thresholds, the allow-lists — and it survives precisely because it is here.
Measured before the installer gained its backup: a `typescript | ENABLED` line and
a live-target block added to a fresh install were both gone after one re-run, with
no message.

So the question that places a file is **not who reads it. It is who owns it.**

| Owner | Home | Why |
|---|---|---|
| The **project** — anything a consumer tunes | `rules/` | `skills/` does not survive an install |
| The **kit** — a cycle contract | `rules/cycle-*.md` | four root checkers glob exactly that pattern: `check_xrefs`, `check_phase_numbering`, `check_gate_mechanisms`, `check_orphan_verdicts`. Splitting them across skills would end the sweeps that prove the chain coherent |
| The **kit** — a rule two or more skills read | `skills/_kit-rules/` | kit content SHOULD be replaced on update; that is how a fix reaches the projects that installed it |
| The **kit** — a skill's own procedure | inside the skill | it ships and is replaced with that skill |
| The **installer** | `rules/templates/` | copied into a fresh consumer's `rules/`, then deleted from it |

A golden rule usually belongs to both: `§ 1` is marked PER-PROJECT and the verdict
vocabulary below it is LOCKED. That is deliberate, and it is why those files carry
the marks — the marks are what say which half a consumer may touch.

## What Claude Code actually loads from here

**Nothing, automatically.** No hook reads a rule file; `settings.json` names none.
The only automatic contact is a pointer injected by
`hooks/userpromptsubmit-inject.py` on every turn, and the parsimony ladder, whose
six rungs are **inlined in that hook** rather than read from
`parsimony-ladder.md`.

That makes the pointer the whole interface, and a pointer at sixty-three files is
not one — a model told to read sixty-three files before an architectural decision
reads none of them. See the doctrine list the hook names.
`tests/test_rules_readme_claims_recompute.py` recomputes that count.

## Cycle Contracts

Each `cycle-{name}.md` defines:
- Entry conditions and prerequisites
- Phase sequence with advance criteria
- Hard gates (BLOCKER-level) and soft gates (advisory)
- Cross-references to skills, hooks, and scripts
- Verdicts vocabulary (e.g., SHIPPABLE_WITH_CAVEATS, READY_TO_MERGE)

| Contract | Cycle | Key Verdicts |
|---|---|---|
| `cycle-brainstorm.md` | Product alignment (phase −1) — the only phase a person attends | PRODUCT_ALIGNED / NEEDS_REVISION / AWAITING_REVIEW / INVALID |
| [`cycle-design.md`](cycle-design.md) | Draw the system before a backlog is filed against it — four drawings that force the decisions no product retrofits (lifecycle, trust boundary, call order with failures, durability) plus the component map DERIVED from them. A map drawn first looks like design happened and forces no choice |
| [`design-golden-rule.md`](design-golden-rule.md) | What a DESIGN panel audits against — does the drawing contradict the code, is an open question disguised as a decision, do the drawings contradict each other. Its scope is DERIVED: with code on disk the panel checks against it; with none it checks internal coherence and may not conclude the design is right |
| `cycle-backlog.md` | Intake (phase 0) | ITEM_REGISTERED / ITEM_REJECTED |
| `cycle-maintenance.md` | Macro super-loop | ITEM_SHIPPED / ITEM_KILLED / BACKLOG_EMPTY |
| `cycle-discover.md` | Measurement of our own system | SHIPPABLE_WITH_CAVEATS / ITEM_KILLED |
| `cycle-plan.md` | Planning | SHIPPABLE_WITH_CAVEATS |
| `cycle-implement.md` | Implementation | IMPLEMENTATION_COMPLETE |
| `cycle-code-quality.md` | Code quality audit | PASS, PASS_WITH_CAVEATS, FAIL_SOFT, FAIL_HARD, INVALID |
| `cycle-review.md` | Multi-agent review | READY_TO_MERGE, NEEDS_FIXES, NEEDS_DEEPER |
| `cycle-release.md` | Release cut | RELEASED, PR_OPEN_AWAITING_APPROVAL |
| `cycle-acceptance.md` | End-user validation of the released delivery; owns the milestone flip | ACCEPTED, ACCEPTED_WITH_CAVEATS, REJECTED, NOT_VALIDATED |
| `cycle-judge-codex.md` | External Codex jury (optional plugin) | SHIPPABLE, READY_TO_MERGE |
| `cycle-idea-to-release.md` | Auto-orchestrator | Delegates to sub-cycles |

## Golden Rules (locked severity rubrics)

| File | Purpose |
|---|---|
| `code-quality-golden-rule.md` | Code quality severity levels |
| [`contribution-conventions.md`](contribution-conventions.md) | What a commit, PR, issue and name must carry. **The kit's**, and every rule in it is either computed by `check_contribution_conventions.py` or declared unenforceable with the reason — a convention nobody can check is a preference, and this repository's own CONTRIBUTING drifted from its practice for long enough that nobody noticed |
| `contribution-overrides.txt` | **THIS PROJECT's** overrides: extra commit types, its own scopes, a different subject limit. Ships empty, survives a reinstall. The co-authorship refusal and the secrets rule cannot be overridden and an attempt is refused rather than ignored |
| `critic-phases.txt` | Which phases get a critic, the contract it judges against, and how many rounds before the disagreement escalates. **Four**: the ones measured as having no panel, no judge, no signature and no scorer. A phase absent from this file has no critic ON PURPOSE, which is a statement about the phase rather than an omission |
| `discover-opportunity-golden-rule.md` | Opportunity confidence hard caps |
| `plan-confidence-golden-rule.md` | Plan confidence scoring rubric |
| `deps-audit-golden-rule.md` | Dependency audit severity |
| `honesty-gate-golden-rule.md` | Anchor scenario + status vocab |
| `skills/_kit-rules/discover-plan-golden-rule.md` | Discovery plan scoring rubric — **not here**: two skills read it, so it lives where the kit replaces it on update |

## Thresholds and Allowlists

| File | Purpose |
|---|---|
| `code-quality-thresholds.txt` | Per-project threshold overrides |
| `code-quality-allowlist.txt` | Findings exemptions (mandatory sunset) |
| `code-quality-languages.txt` | Enabled languages per project |
| `plan-confidence-thresholds.txt` | Plan scoring thresholds |
| `plan-confidence-allowlist.txt` | Plan findings exemptions |
| `discover-web-allowlist.txt` | Authoritative domains for WebFetch |
| `deps-audit-allowlist.txt` | Dependency audit exemptions |
| `discover-opportunity-thresholds.txt` | Opportunity confidence thresholds |
| `live-target.txt` | Declared live environments per domain (live-test refuses without one) |
| `current-constraint.md` | The constraint lens — advisory, never a gate |
| `discover-plan-thresholds.txt` | Discovery plan scoring thresholds |
| `code-quality-baseline.txt` | Findings accepted as the starting state, so a new one stands out |
| `acceptance-target.txt` | Where `/acceptance` exercises the released delivery |
| `domain-routing.txt` | Which repositories exist here and who owns each — **the project's**, derived from disk |
| `auxiliary-skills.txt` | Skills bound to no cycle, so the orphan sweep does not report them |
| `auxiliary-cycles.txt` | Cycles the project built alongside the kit's chain, so `check_squad_map` does not ask the kit's map to place them. Its sibling above, for the index one level up |
| `retired-permissions.txt` | Permissions withdrawn, kept so a reinstall does not reintroduce them |
| `notifications.txt` | Where the kit sends what a person must see |
| `skills/_kit-rules/review-model-routing.txt` | Agent model routing for review — **not here**: kit-owned, replaced on update |

## Other Rules

| File | Purpose |
|---|---|
| `cycle-rule-schema.md` | Canonical schema + verdict matrix for all `cycle-*.md` |
| `squad-map.md` | The 360º view: every phase, who owns it, and what it reads |
| `cycle-phases.txt` | The chain itself, declared once and machine-readable |
| `blocking-verdicts.txt` | Verdicts that stop an item where it is — one definition, two readers |
| `autonomy-envelope.md` | What runs unattended, and the floors that make it defensible |
| `decision-delegation.txt` | What a consumer may delegate, and what delegation can never authorize |
| `write-exemptions.txt` | The files the Squad produces OUTSIDE `<project>/.squad/`, each with a class (`platform` / `tool` / `human`) and what forces it. **The kit's**: the classes are about Claude Code's own discovery rules and about conventions older than this kit, not about one project. `check_produced_files.py` refuses a row missing either field — "we made an exception" and "the platform gave us no choice" are different claims, and only the second survives review |
| `verdict-bands.txt` | Which band each verdict is in — clean, caveats, redo, structural, orthogonal. **The kit's**, like the phase chain and the blocking list: it classifies the verdicts the kit's own cycles emit, and a frozen copy means an unclassified verdict that silently disables the drift check. Where a band is COMPUTED; `cycle-rule-schema.md` is where it is argued |
| `verdict-bands.local.txt` | The same table for verdicts the PROJECT'S own cycles emit — preserved across updates, where its sibling is replaced. It ADDS rows rather than excluding names: a verdict cannot be claimed out of the sweep, because the drift check has to classify every one that reaches the event stream. The kit's file stays authoritative for the kit's own, and a local row naming one of those is reported rather than applied |
| `review-panel.txt` | Who judges a DISCOVER opportunity and a PLAN plan — **the project's own specialist agents**, because which agents it has and which models it can reach is not the kit's business. The kit imposes only the rule: three seats per gated phase, 2 of 3 to advance, never all from one model family, and the author never sits |
| `review-auditors.txt` | Which `loop-*` plugin audits which domain at REVIEW — **the project's**, because which plugins it has and what they cost it are not the kit's business. The kit imposes only that the selection is DERIVED from the domain rather than chosen by the reviewing agent, and that a declared auditor which did not run blocks. Removing a row is a visible decision to stop requiring that audit; the installer preserves this file so the decision survives an upgrade |
| `records-location.md` | Where run output goes, and why `wiki/` and `records/` are two directories |
| `sop-schema.md` | The shape of a procedure performed on the kit |
| `english-only.md` | Everything the repository versions is written in English |
| `architecture.md` | Layering and DIP boundaries |
| `testing.md` | TDD discipline and pyramid |
| `error-handling.md` | Fail-fast discipline, typed errors (Unbreakable Rule 8) |
| `git-safety.md` | Forbidden git commands + safe substitutes (Unbreakable Rule 4) |
| `reference-provenance.md` | Keeping third-party study material out of the project (4 layers) |
| `parsimony-ladder.md` | Pre-write minimalism ladder (YAGNI/KISS/Don't-Reinvent) enforced in GREEN phase |
| `public-copy.md` | Banned framings in README/marketing |
| `loop-engine-convention.md` | Skill vs Agent vs ralph-loop |
| `skills/_kit-rules/audit-trail-rotation.md` | When to archive/delete artifacts — **not here**: kit-owned, replaced on update |

## Modifying Rules

- Cycle contracts and golden rules are **locked** — changes require team discussion
- Thresholds and allowlists are per-project and can be adjusted freely
- Run `python3 "$([ -d .claude/skills ] && echo .claude || echo .)/mechanisms/gates/check_xrefs.py"` after any change to validate references
