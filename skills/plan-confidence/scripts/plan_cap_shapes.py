"""What would clear each cap `run_structural.py` raises, as the literal form accepted (#139).

Measured over a 20-hour consumer session, 676 Bash commands: 64 were an agent reading a
gate's source to learn the shape it wanted, 11 of them in `plan-confidence`. A cap id like
`coverage_matrix_unreadable` names the failure; the header row that would have been read
lived in `TASK_COLUMN_HEADERS`, one grep away. The refusal carried the diagnosis and not
the prescription.

Every shape is built from the constant the checker decides with, imported rather than
restated, so a vocabulary widened in a checker widens the sentence too. The basename is
specific on purpose: every skill ships its scripts as loose modules on one `sys.path`.
"""
from __future__ import annotations

from check_adr_completeness import COST_KEYWORDS
from check_baseline_context import REQUIRED_SUBSECTIONS
from check_concurrency_tests import _accepted_signals
from check_coverage_matrix import (
    GAP_COLUMN_HEADERS,
    OUT_OF_SCOPE_PATTERNS,
    TASK_COLUMN_HEADERS,
)
from check_failure_scenarios import SCAN_HEADINGS

#: Cap ids chosen at run time by a checker rather than written in `run_structural.py`.
#: Named here so the static test can hold each to a shape.
DYNAMIC_CAP_IDS = (
    "deps_audit_insecure",
    "soft_floor_deps_audit_missing",
    "soft_floor_deps_audit_partial",
    "soft_floor_deps_audit_medium",
    "soft_floor_symbol_named_by_ticket",
    "soft_floor_evidence_at_shared_path",
    "soft_floor_symbol_naming_unmeasured",
    "soft_floor_symbol_named_by_ticket_and_shared_evidence_path",
    "alignment_not_reached",
    "alignment_not_applicable",
)


def _quoted(items) -> str:
    return ", ".join(f"`{item}`" for item in items)


def matrix_table_shape() -> str:
    """The Coverage Matrix a reader can parse — printed when there is none, too."""
    return (f"a `## Coverage Matrix` table whose header row names a gap column (one of "
            f"{_quoted(GAP_COLUMN_HEADERS)}) and a task column (one of "
            f"{_quoted(TASK_COLUMN_HEADERS)}), e.g. `| Gap / Requirement | Task(s) |`")


_SHAPES = {
    "coverage_matrix_unreadable": matrix_table_shape,
    "coverage_lt_100": lambda: (
        "every matrix row's task column cites a `T1.1` task id, `Final Phase` (when the plan "
        "has a `## Final Phase` section) or a deferral marker ("
        + _quoted(p for p in OUT_OF_SCOPE_PATTERNS if len(p) > 3)
        + "), and every `T<n>.<n>` the plan mentions appears in the matrix"),
    "matrix_cites_undeclared_criterion": lambda: (
        "every criterion id a matrix row cites (`AC-1`, `FR-2`, …) is declared in that "
        "task's own `#### Acceptance Criteria` block"),
    "adr_without_alternatives": lambda: (
        "every `### D1 — <decision>` under `## ADRs` names a rejected alternative "
        "(`alternative`, `rejected`, `instead of`, `vs.`) and its cost if wrong ("
        + _quoted(COST_KEYWORDS) + ")"),
    "bugfix_without_tdd": lambda: (
        "every bug-fix `### T1.1 — <title>` carries a `#### TDD` block with a `RED` step"),
    "fabricated_citation": lambda: (
        "every citation resolves: `rules/<file>.md § <Section>` names a heading in that "
        "file, `Opportunity §<id>` names a section of the opportunity, and `D1` names an "
        "ADR this plan defines"),
    "vague_acceptance_criteria": lambda: (
        "a `#### Acceptance Criteria` (or `DoD`) block whose bullets name an observable "
        "result with a number or an oracle — at most 10% vague, at least 80% acceptable"),
    "patterns_skill_ignored": lambda: (
        "cite the applicable `*-patterns` skill by name in the plan body, or record a "
        "one-line override ADR naming it"),
    "soft_floor_smell_density_high": lambda: (
        "fewer than 30 spec smells (vague terms, weak imperatives) in the plan's prose"),
    "soft_floor_high_deferred_ratio": lambda: (
        "at most 20% of Coverage Matrix rows deferred"),
    "soft_floor_low_architecture_compliance": lambda: (
        "a compliance score of at least 0.4: name a project rule file (0.40), or cite an "
        "engineering principle (0.30) together with a DoD quality gate (0.15) or a size "
        "budget (0.15)"),
    "soft_floor_baseline_context_incomplete": lambda: (
        "`## Baseline Context` with " + ", ".join(f"`### {s}`" for s in REQUIRED_SUBSECTIONS)
        + ", each filled (no template placeholders)"),
    "soft_floor_drawbacks_section_insufficient": lambda: (
        "`## Drawbacks & Risks` with a table of at least 2 filled rows (risk, severity, "
        "mitigation, owner)"),
    "soft_floor_unresolved_questions_section_missing": lambda: (
        "`## Unresolved Questions` with `- ` question bullets, or the line "
        "`(none — every decision is resolved at plan time)`"),
    "soft_floor_concurrency_tests_missing": lambda: (
        "a `#### Concurrency tests` subsection in each task that touches concurrency, "
        f"naming one of: {_accepted_signals()}"),
    "soft_floor_failure_scenarios_missing": lambda: (
        "`## Failure scenarios` with at least 1 filled row (mode, reproduction, expected "
        "behaviour) per external dependency, or `(none — no external I/O touched)`. "
        "Signals are read under " + ", ".join(f"`## {h}`" for h in SCAN_HEADINGS)),
    "deps_audit_insecure": lambda: (
        "a `/deps-audit <slug>` report with no unwaived CRITICAL/HIGH advisory — fix, "
        "replace, or waive it in the project's `deps-audit-allowlist.txt`"),
    "soft_floor_deps_audit_missing": lambda: (
        "a `<slug>-deps-audit-*.md` report with a `**Verdict:**` line — run "
        "`/deps-audit <slug>`"),
    "soft_floor_deps_audit_partial": lambda: (
        "a deps-audit report that names every dependency the plan declares"),
    "soft_floor_deps_audit_medium": lambda: (
        "a deps-audit report with no unwaived MEDIUM advisory"),
    "soft_floor_symbol_named_by_ticket": lambda: (
        "test and symbol names that say what they do — no `B-014`/ticket id inside a "
        "name the plan demands"),
    "soft_floor_evidence_at_shared_path": lambda: (
        "evidence at a per-run path — `$(mktemp -d)/…` or `/tmp/$RUN/…` — never a fixed "
        "`/tmp/<file>.<ext>` another run can overwrite"),
    "soft_floor_symbol_naming_unmeasured": lambda: (
        "a plan the symbol-naming check can read — see its `unmeasured_because`"),
    "soft_floor_symbol_named_by_ticket_and_shared_evidence_path": lambda: (
        "names without ticket ids AND evidence at a per-run path (`$(mktemp -d)/…`), not "
        "a fixed `/tmp/<file>.<ext>`"),
    "alignment_not_reached": lambda: (
        "an alignment brief for the item this plan implements, scoring at least 90% and "
        "signed off (`score_alignment.py` reports ALIGNED)"),
    "alignment_not_applicable": lambda: (
        "a plan that names its backlog item (`B-001`) or milestone, so its alignment brief "
        "can be found"),
}


def accepted_shape(cap: str) -> str:
    """The literal form that clears `cap`, or "" for an id this module does not know."""
    shape = _SHAPES.get(cap)
    return shape() if shape else ""
