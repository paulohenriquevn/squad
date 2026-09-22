# Code-Quality Golden Rule
<!-- rule-id: SQ-GLD-01 -->

Locked unbreakable contract that `/code-quality` reads to score findings, decide verdicts, and gate handoff to `/review`. **This file is the Source of Truth for the severity rubric, the allowlist mechanism, and the verdict score caps.** It mirrors the dogfood-golden-rule pattern: locked sections that require an ADR to change, and per-project sections for tuning.

Without this file, `/code-quality` emits `INVALID` with flag `code_quality_golden_rule_missing` and refuses to score.

## § 1 — Verdict tokens (LOCKED)

`/code-quality` MUST emit one of the following verdicts. They are aligned with the canonical matrix in `cycle-rule-schema.md`.

| Verdict | Score cap | Meaning | Downstream action |
|---|---|---|---|
| `PASS` | 100 | No findings above INFO. Toolchain available for every enabled language. | Proceed to `/review`. |
| `PASS_WITH_CAVEATS` | 89 | Only soft-floor findings (mutation score 60-79%, etc.). | Proceed to `/review`; caveats logged in the audit report and PR description. |
| `FAIL_SOFT` | 70 | Soft-cap findings (orphan exports, mutation < 60%, auditor unavailable). | `/review` MAY proceed if explicit ADR dismisses each soft cap; otherwise loop back to `/implement`. |
| `FAIL_HARD` | 49 | Hard-cap findings (dead code unallowlisted, symbol fabrication). | **Blocks `/review`.** Loop back to `/implement`. |
| `INVALID` | 0 | Structural integrity broken (this file missing, malformed allowlist entry, golden-rule corruption). | Stop the cycle. Surface to human. |

A new verdict token requires an ADR + an entry in `cycle-rule-schema.md` § Canonical verdict vocabularies.

## § 2 — Severity rubric (LOCKED)

In order of severity ceiling; first hit wins (smallest cap is the verdict).

| Finding | Verdict cap | Stable identifier |
|---|---|---|
| Symbol fabrication (production code references undefined symbol) | `FAIL_HARD` (49) | `symbol_fabrication_{language}` |
| Dead exported symbol with no caller and no test (unallowlisted) | `FAIL_HARD` (49) | `dead_code_unallowlisted_{language}` |
| Allowlist entry malformed (parse error) | `FAIL_HARD` (49) | `allowlist_malformed_entry` |
| Declared architecture rule broken by the code (detector D5) | `FAIL_HARD` (49) | `architecture_violation_{language}` |
| Declared architecture rule names something no longer in the tree (D5) | `FAIL_HARD` (49) | `vacuous_architecture_rule_{language}` |
| Code-quality golden rule missing (this file) | `INVALID` (0) | `code_quality_golden_rule_missing` |
| Orphan exported symbol (no importer, exporting from a public package) | `FAIL_SOFT` (70) | `soft_cap_orphan_export_{language}` |
| Mutation score < 60% on declared critical paths | `FAIL_SOFT` (70) | `soft_cap_mutation_score_low_{language}` |
| Mutation runner not configured by the project | `FAIL_SOFT` (70) | `soft_cap_mutation_unconfigured_{language}` |
| Mutation deferred for the language (Rust, Go) | `FAIL_SOFT` (70) | `soft_cap_mutation_deferred_{language}` |
| Mutation run produced zero mutants | `FAIL_SOFT` (70) | `soft_cap_mutation_no_mutants_{language}` |
| No declared public surface for D3 to audit | INFO | `d3_no_public_surface` |
| Auditor unavailable (tool missing for enabled language) | `FAIL_SOFT` (70) | `auditor_unavailable_{tool}` |
| Mutation score 60-79% on declared critical paths | `PASS_WITH_CAVEATS` (89) | `soft_floor_mutation_score_medium_{language}` |
| Dead internal symbol (private function with no caller) | `PASS_WITH_CAVEATS` (89) | `dead_internal_symbol_{language}` |
| Unused parameter (often refactor leftover) | `PASS_WITH_CAVEATS` (89) | `unused_parameter_{language}` |

**Retired 2026-09-17: `plan_missing_critical_paths_section`.** It capped a plan with no `## Critical paths` section at 70, on the strength of that section scoping D4. The scoping was removed deliberately — neither mutmut nor Stryker accepts an arbitrary file list, so `detect_mutation_score` reads the project's own mutation config — and no code has emitted this identifier since. A declared cap nothing can trigger is a rule that reports itself as enforced.

## § 3 — Hard caps (LOCKED)

Hard caps are findings that cap the verdict at `FAIL_HARD` (score 49) or below. They cannot be downgraded by the allowlist alone — they require either a code fix or an explicit ADR.

In order; first failure short-circuits the verdict:

| # | Check | Flag |
|---|---|---|
| 1 | This file (`code-quality-golden-rule.md`) exists and parses | `code_quality_golden_rule_missing` |
| 2 | `code-quality-allowlist.txt` parses without syntax errors | `allowlist_malformed_entry` |
| 3 | No production source references an undefined symbol (per detector D2 introspection) | `symbol_fabrication_{language}` |
| 4 | No exported public symbol is dead AND not allowlisted (per detector D1) | `dead_code_unallowlisted_{language}` |

A finding flagged as hard cap MAY only be downgraded via:
- **Code fix** — the underlying issue is resolved in the source.
- **ADR + allowlist entry with sunset** — entered in `code-quality-allowlist.txt` with a justification and a sunset date ≤ 90 days. The allowlist downgrades severity by ONE level (HARD → SOFT_CAP).

## § 4 — Allowlist mechanism (LOCKED)

`code-quality-allowlist.txt` accepts entries that exempt SPECIFIC findings, with mandatory sunset. The format is documented in the allowlist file itself; the contract here is:

| Property | Rule |
|---|---|
| Entry format | `ECOSYSTEM \| FILE-PATH \| FINDING-TYPE \| SYMBOL-OR-LINE \| REASON \| SUNSET (YYYY-MM-DD)` — six fields; FINDING-TYPE is the DETECTOR family (`dead_code`, `symbol_fab`, `orphan_export`, `mutation_low`, `architecture`), not a § 2 identifier. Amended by ADR 0011 (#343): this row documented a four-field shape `load_allowlist` never accepted, so following it raised `allowlist_malformed_entry` — a HARD finding, strictly worse than adding nothing. |
| Sunset window | ≤ 90 days from entry creation date |
| Downgrade | ONE severity level (HARD → SOFT_CAP, SOFT_CAP → SOFT_FLOOR) |
| Expired entry | IGNORED — finding re-fires at full severity; entry listed under "Allowlist hits — expired" in the audit report |
| Malformed entry | Emits `allowlist_malformed_entry` HARD finding; aborts allowlist processing |
| Adding an entry | Requires CHANGELOG entry under `[Unreleased] § Changed` |
| Bypassing the allowlist (e.g., `# noqa: code-quality`) | FORBIDDEN — every exemption goes through this file |

## § 4.1 — Baseline mechanism (LOCKED)

A verdict is one per language, and until 2026-08-31 the gate could not tell debt that
was already there from a defect the change introduced.

`rules/code-quality-baseline.txt` records finding keys that already existed. A key
listed there is **removed from the verdict and kept in the report** — the run still
names the finding, and the summary carries `baselined: N`, so the debt stays countable.
It is not forgiven and not hidden; what it stops doing is failing a change that did not
cause it.

**A baseline is a FACT; the allowlist next door is a DECISION.** § 4 is a person
exempting one finding, with a reason and a sunset, one entry at a time. This is a
generated record of what was already true, written by
`run_code_quality.py --write-baseline` — an explicit act, never a side effect of a
normal run. It never grows by itself, so a NEW finding in a baselined file still fails,
and the key is the finding rather than the file.

**Why it was needed**, in the words of the consumer that hit it, written into its own
config on 2026-08-19 as the reason Go stayed disabled:

> the D1 pass brings 36 REAL dead-code findings, and the verdict is one per language —
> turning it on before paying them fails the delivery over legitimate debt, **which is
> how a gate becomes something people work around**

It became worse than that. Every language went `DEFER` or `DISABLED`, the gate then
audited nothing, `no_languages_audited` fired (§ 3), and every plan came back `INVALID`.
Each step was correct and the system was deadlocked — a gate nobody could turn on.

### What a baseline may not record

Two limits, both measured on a real repository the day the mechanism shipped, and both
enforced by `--write-baseline` rather than left to discipline.

**It is written with the network off, always.** The Go symbol detector resolves imports
against the module proxy. With the network reachable it reported **4777** fabrications;
with `--no-network`, **one**. Two consecutive runs even disagreed with each other —
4818, then 4777 — because the result depends on what the proxy answered that second.
Baselining that freezes ~4800 network failures into the repository as if they were
debt, hides whatever is real behind them, and still fails the gate, because the next
run produces a slightly different set the baseline does not cover.

**It records findings about the CODE, never about the GATE.** A run also emits findings
about the tooling: a detector disabled for want of a network, a linter with no config,
a mutation pass deferred, a crash. The first honest baseline on that repository held
five entries and every one was of that kind, including `d2_disabled_no_network`.
Recording them silences the warnings that say the gate is not working — worse than a
gate that fails, because it looks like one that passed. They are told apart by what
they cannot have: a real file. A finding about the code names one; a finding about the
tooling says `.` or `<unknown>`.

The corollary is worth stating, because it is what the measurement actually found
there: **a language can be blocked by tooling rather than by debt, and a baseline does
not help then.** That repository's baselinable debt was ZERO, and its gate still
returned INVALID — the detector needed fixing and two of its three `go.mod` manifests
were undeclared. Turn a language on when the gate works, not when the baseline is
written.

## § 5 — Detector contract (LOCKED)

Detectors run in fixed order. Each detector MUST be subprocess-isolated, never modify source code, and emit findings as structured JSON.

| Detector | Tool family | Languages | What it asserts |
|---|---|---|---|
| D1 — Dead code | vulture, knip, cargo-udeps, deadcode | Python, TS, Rust, Go | No exported symbol unreachable from a caller or a test — **at the configured confidence**. `vulture.min_confidence` defaults to 80 and `vulture` scores an unused function, class or variable at 60, so the default reports the 90%-confidence class (unused imports) and not the orphan symbol this row describes. Measured 2026-09-21 on one file: 0 findings at 80, 2 at 60, both real orphans. The default stands — § 5 argues it directly, and turning D1 up before the debt is paid *"is how a gate becomes something people work around"* — and `--write-baseline` is the path for a project that decides to. Every run now reports `thresholds_applied`, so a clean D1 carries the number it was clean at |
| D2 — Symbol fabrication | tree-sitter + registry introspection | All enabled | Every imported symbol resolves to a real definition |
| D3 — Cross-package wiring | `detectors/_wiring.py` | All enabled | Every DECLARED export has a production consumer (soft cap) |
| D4 — Mutation testing | mutmut, Stryker via `detectors/_mutation.py` | Python, TS (Rust+Go deferred) | Mutation score ≥ floor, scoped by the project's own runner config |

A detector MAY be added to this table only via an ADR + corresponding implementation in `skills/code-quality/scripts/detectors/`.

**D3 and D4 were declared here and implemented nowhere until 2026-08-26.** All four
language adapters returned `unavailable("d3"/"d4", …, "is not configured")`, and
because `unavailable()` emits SOFT_CAP, every audit in every project carried two
permanent soft caps — making `PASS` unreachable by construction and turning the
`/implement` gate into a WARN nobody reads. What they assert now:

- **D3 audits the surface the project DECLARED** — `__all__` and `__init__.py`
  re-exports (Python), the files `package.json` points at (TypeScript), `pub` in
  `src/lib.rs` (Rust), exported identifiers outside `internal/` (Go). Inferring a
  surface from "every name without an underscore" produces hundreds of findings in
  any script repository, which is the most efficient way to disable a gate without
  removing it. A project with no declared surface gets INFO, never a verdict about a
  contract nobody wrote. A test is not a consumer, for the same reason pillar (a) of
  the wiring triad does not count one. A type named in another public export's
  signature IS consumed — it lives through that export.
- **D4 READS a recent report instead of re-running the tool.** Mutation testing is a
  periodic deep check and D4 was treating it as a per-invocation gate: measured in a
  consumer on 2026-08-27, `npx stryker run` took 1347s, and `run_structural.py` invokes
  `/code-quality` internally — so **every plan gate in that repository cost 22.5 minutes**.
  A 22-minute gate is a gate people bypass, which is the failure this kit exists to
  prevent. A report younger than `mutation.max_report_age_minutes` (default 1440) is read;
  anything older is re-measured; with no report there is nothing to reuse and the tool
  runs. A reused score NEVER appears bare — it carries its age and how many source files
  changed since it was written, because a number without its age is a claim about now.
  Setting the threshold to 0 restores unconditional re-measurement.

- **D4 is scoped by the project's own runner config**, not by a file list: neither
  mutmut nor Stryker accepts an arbitrary list as scope, and the orchestrator was
  building one and dropping it. The stats FILE is the evidence, never the exit code —
  measured 2026-08-26, mutmut 3.5 exits 0 when the test runner collected nothing. Zero
  mutants is reported as absence of measurement: a perfect score over an empty set is
  absolute green with nothing measured.

## § 6 — Per-project tuning (PER-PROJECT — EDIT THIS)

Thresholds for the detectors live in `code-quality-thresholds.txt`. The keys are stable; the values are per-project. Defaults are shipped in `rules/code-quality-thresholds.txt` and may be promoted to `rules/code-quality-thresholds.txt` for project-specific overrides.

**Until 2026-08-26 none of them reached a detector.** The orchestrator called
`load_thresholds()` for the side-effect of validating the file and discarded the
result, with an inline note that "detectors use hardcoded defaults in v0.1" — so every
documented key here was inert. A configuration file that cannot change behaviour is
worse than none: it reads as a control that exists. The values now reach the detectors
through `BaseDetector.thresholds` / `BaseDetector.threshold()`.

Each project SHOULD:

1. Enable its languages in `code-quality-languages.txt` (this is per-project by design).
2. Tune thresholds in `code-quality-thresholds.txt` only when defaults are demonstrably wrong for the codebase.
3. Maintain `code-quality-allowlist.txt` with sunset hygiene (no entry older than its sunset).

## § 7 — When this rule may change

Per `cycle-rule-schema.md § Golden Rule Change Protocol`. Rule-specific deviations:

- Changing a verdict token = breaking the cycle contract (requires ADR).
- Adding a new detector = expanding the D-series (requires ADR + implementation in `skills/code-quality/scripts/detectors/`).
- Loosening a hard cap to a soft cap = downgrading the gate (requires ADR with risk assessment).

## § 8 — Failure modes the rule guards against

- LLM-generated code with fabricated symbol references slipping past unit tests.
- Dead exports accumulating because nobody runs cleanup.
- Mutation score regression masked by line-coverage growth.
- Allowlists growing stale forever (sunset enforcement).
- `/code-quality` PASS being mistaken for `/review` PASS (different gates, different vocabularies).

## Cross-references

- Schema for cycle rules: `cycle-rule-schema.md`
- Cycle rule: `cycle-code-quality.md`
- Skill: `skills/code-quality/SKILL.md`
- Languages enablement: `code-quality-languages.txt`
- Thresholds: `code-quality-thresholds.txt`
- Allowlist: `code-quality-allowlist.txt`
- Defaults shipped with the skill: `skills/code-quality/defaults/`
