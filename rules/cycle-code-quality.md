# Cycle: CODE-QUALITY

Source of Truth for the post-implementation code-quality audit. Wired between `/implement` and `/review`.

## Purpose

Detect three classes of defect that slip past unit tests and basic linters:

1. **Dead code** — functions, classes, or modules with no reachable caller.
2. **Symbol fabrication** — references to functions/types/modules that do not exist (a frequent failure mode of LLM-generated code).
3. **Wiring gaps** — public exports without the wiring triad (caller + integration test + runtime metric).

These checks are language-aware. Languages enabled in `rules/code-quality-languages.txt` get full coverage; others are skipped with an INFO finding.

## Pre-conditions

- After `/implement` emits `IMPLEMENTATION_COMPLETE`, before `/review`.
- Standalone before merge of a long-running branch.
- Periodic schedule (suggested weekly via `/loop 7d /code-quality`).
- Also invoked **during** `/implement`'s final validation (per ADR 0002 — `cq-gate-in-validate`): `scripts/run_validation.py` calls `/code-quality` via `cq_invoke.invoke()` and fails the validation if the verdict is `FAIL_HARD` or `INVALID`. This makes `/code-quality` a hard gate of `IMPLEMENTATION_COMPLETE`, not just of `/review`.

Do NOT trigger when:
- The branch has uncommitted changes (audit a stable tree).
- No source code exists yet (pre-code phase) — the skill is a no-op then.

## Chain

```
/code-quality {plan-slug-or-empty}
     ↓ detect languages from manifests (go.mod, package.json, pyproject.toml, Cargo.toml)
     ↓ run per-language detectors (dead-code, fabrication, wiring)
     ↓ consolidate findings into severity-classified report
     ↓ verdict: PASS / PASS_WITH_CAVEATS / FAIL_SOFT / FAIL_HARD / INVALID
```

## Phase contracts

| Phase | Input | Output | Hard gate |
|---|---|---|---|
| detect | repo tree | list of enabled languages | at least one manifest present (else NOOP) |
| analyze | per-language detector run | structured findings (file:line, severity, kind) | detector toolchain available for enabled language |
| consolidate | per-language findings | unified report at `.squad/records/audits/{slug-or-date}-code-quality.md` | report references real file:line — no fabricated citations |
| verdict | report | PASS / PASS_WITH_CAVEATS / FAIL_SOFT / FAIL_HARD / INVALID | severity rubric (`code-quality-golden-rule.md` § 1–2) |

## Severity rubric

The Source of Truth for the rubric — score caps **and** the stable finding
identifiers — is `code-quality-golden-rule.md` § 1–2 (LOCKED). This cycle does not
redefine them. The verdict is the smallest cap among the findings:

| Verdict | Cap | When |
|---|---|---|
| `PASS` | 100 | No finding above INFO. |
| `PASS_WITH_CAVEATS` | 89 | Soft-floor only (dead internal symbol, unused parameter, mutation 60–79%). |
| `FAIL_SOFT` | 70 | Soft-cap (orphan export, mutation < 60%, auditor/toolchain unavailable). |
| `FAIL_HARD` | 49 | Hard-cap (`symbol_fabrication_{language}`, `dead_code_unallowlisted_{language}`). |
| `INVALID` | 0 | Structural integrity broken (golden rule missing/corrupt, allowlist malformed). |

## Hard gates (`FAIL_HARD`)

- `symbol_fabrication_{language}` (`run_code_quality.py`, detector D2) — at least one production reference points to a name that does not exist in the source tree or in any imported dependency.
- `dead_code_unallowlisted_{language}` (`run_code_quality.py`, detector D1) — a symbol exported from a public package surface has no caller and no test, and is not allowlisted.

A `FAIL_HARD` verdict blocks `/review`; `INVALID` halts the cycle — the contract that computes the verdict is broken, so it is registered as its own item and this one returns to the registry blocked on it (`autonomy-envelope.md § A loop ran out of attempts`). The fix path for `FAIL_HARD` is back to `/implement` (or a targeted fix branch). A `FAIL_SOFT` MAY proceed to `/review` only with an ADR dismissing each soft cap (per golden rule § 1) — writing that ADR is the system's, and the ADR is the decision and its record at once (`autonomy-envelope.md § A structural decision the contract wants recorded`).

### How a plan dismisses a soft cap

The ADR carries a marker naming the cap it dismisses, read by
`skills/plan-confidence/scripts/run_structural.py`:

```markdown
## ADRs

### ADR-3 — Proceed without a mutation runner

<!-- ADR-DISMISS-SOFT-CAP: soft_cap_mutation_unconfigured_typescript: Stryker lands in v0.3; followup registered as B-007 -->

Rejected alternatives: ...
```

The marker, rather than prose naming the id, because a plan can name a cap in
order to say it will NOT be dismissed and no keyword search tells the two apart.
The shape copies `check_wiring.py`'s `ADR-DEFER-WIRING-B` — one convention for
"an ADR waives this", not a new one per gate.

**EACH** cap needs its own marker. A partially dismissed `FAIL_SOFT` still
demotes, and the verdict then lists `undismissed_soft_caps` so the gap is named
rather than discovered by reading the kit's source.

The score cap applies either way: quality was measured, and an ADR justifies
proceeding — not a better number. A dismissed `FAIL_SOFT` reaches
`SHIPPABLE_WITH_CAVEATS`, never `SHIPPABLE`.

**Why this exists.** For a long time the paragraph above promised the escape and
no code implemented it: the demotion ran unconditionally and no ADR was ever
looked for. That was not cosmetic. Golden rule § 2 maps an unconfigured mutation
runner to `FAIL_SOFT`, so a repository that had not set up Stryker got
`FAIL_SOFT` on every run forever, every plan capped at 70 and demoted to
`NON_SHIPPABLE`, and `rules/cycle-plan.md` requires `≥ SHIPPABLE_WITH_CAVEATS`
to enter `/implement`. **A project in that state could not start `/implement` by
any path, while this rule said it could.** Found by a consumer, blocked on a plan
with zero hard caps, zero soft caps of its own and 91.6 weighted.

A soft cap that cannot be dismissed is a hard cap under another name;
dismissibility is the whole difference between the tiers.

## Stop conditions

- A detector crashes (e.g., parse error in a source file) → halt; surface the parse error; do NOT emit a partial report.
- Toolchain for an enabled language is missing → emit `detector_unavailable_{lang}` finding and continue with the remaining languages.

## Anti-patterns

- Running `/code-quality` on an uncommitted tree — false positives from in-progress code.
- Suppressing findings via inline comments without an ADR — every suppression needs justification.
- Treating `PASS_WITH_CAVEATS` as `PASS` — caveats are explicit, address or document them.
- Running `/code-quality` BEFORE `/implement` finishes — the audit is for post-implementation state.

## Output

- `.squad/records/audits/{slug-or-date}-code-quality.md` — consolidated report with severity matrix, file:line evidence, and remediation suggestions.
- The verdict is emitted in the report and in the structured JSON (`verdict` field). The process exits non-zero on blocking verdicts (`FAIL_HARD` / `INVALID`).

## Cross-references

- Schema for cycle rules: `rules/cycle-rule-schema.md`
- Skill: `skills/code-quality/SKILL.md` (phase-specific protocol)
- Enabled languages: `rules/code-quality-languages.txt` — the project's, and the only copy. A second copy shipped inside the skill's defaults directory until 2026-09-01, described as a fallback; nothing fell back to it, and a missing rule correctly exits 2 rather than auditing a stale subset silently.
- Languages enabled per project: `rules/code-quality-languages.txt`
- Downstream: `rules/cycle-review.md` (consumes the audit verdict)
- Upstream: `rules/cycle-implement.md` (must emit `IMPLEMENTATION_COMPLETE` before this runs)
