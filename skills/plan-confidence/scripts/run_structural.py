"""run_structural.py — orchestrator for the M2 structural plan-confidence check.

Loads rubric-v1.md and thresholds allowlist. Runs all 4 checkers
(Coverage Matrix, ADR completeness, TDD in bug-fix, spec smells).
Composes a final score with ADR D8 renormalization for active dimensions.
Applies hard caps. Returns/prints a StructuralScoreReport JSON.

CLI:
    python3 run_structural.py <plan_slug-or-path> [--rubric PATH] [--thresholds PATH]

Exit codes (EC-10):
    0 — SHIPPABLE or SHIPPABLE_WITH_CAVEATS (green path)
    1 — INVALID (hard cap triggered)
    2 — Error (plan/rubric not found, malformed)
    3 — NON_SHIPPABLE (score < 50 without hard cap; over-penalization to investigate)
"""
from __future__ import annotations

import argparse
import json
import re
import sys

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple

from _rubric_loader import load_rubric
from check_adr_completeness import ADRReport, check_adr_completeness
from check_alignment_gate import check_alignment_gate
from check_architecture_compliance import check_architecture_compliance
from check_baseline_context import check_baseline_context
from check_concurrency_tests import check_concurrency_tests
from check_coverage_matrix import CoverageReport, check_coverage_matrix
from check_criterion_executability import ExecutabilityReport, check_criterion_executability
from check_deps_audit import check_deps_audit
from check_drawbacks_section import check_drawbacks_section
from check_evidence_citations import EvidenceReport, check_evidence_citations
from check_failure_scenarios import check_failure_scenarios
from check_impediment_agrees import check_impediment_agrees
from check_patterns_consumption import PatternsConsumptionReport, check_patterns_consumption
from check_spec_smells import SmellReport, check_spec_smells
from check_symbol_naming import check_symbol_naming
from check_task_interfaces import check_task_interfaces
from check_tdd_in_bugfix import TDDReport, check_tdd_in_bugfix

for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        sys.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.allowlist import (  # noqa: E402 — post-bootstrap import
    MalformedEntry,
    active as _active_entries,
    parse as _parse_allowlist,
)
from squad.paths import DATA_DIRNAME, rules_dir, write_records_dir  # noqa: E402 — post-bootstrap import

SKILL_ROOT = Path(__file__).parent.parent
DEFAULT_RUBRIC = SKILL_ROOT / "templates" / "rubric-v1.md"


def _find_project_root(start: Path) -> Path:
    """Walk up from `start` to find the nearest project root.

    Heuristics (in order):
      1. Directory containing `.claude/` — Claude Code project root
      2. Directory containing `.git/` — git repo root
      3. Fall back to `start.parent.parent.parent` (legacy assumption)

    This makes the skill portable: it works in any project that contains
    a `.claude/` or `.git/` directory above the skill location.
    """
    current = start.resolve()
    while current != current.parent:
        if (current / ".claude").exists() and (current / ".claude").is_dir():
            return current
        if (current / ".git").exists():
            return current
        current = current.parent
    # Last-ditch fallback: assume legacy layout
    return start.parent.parent.parent


def _find_plans_dir(project_root: Path) -> Path:
    """Auto-detect the plans directory across common project conventions."""
    candidates = [
        write_records_dir(project_root, "plans"),
        project_root / ".claude" / "plans",
        project_root / "plans",
        project_root / "docs" / "plans",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    # Default: the canonical Claude Code path (skill assumes this if absent)
    return candidates[0]


def _find_holdout_dir(project_root: Path) -> Path:
    """Auto-detect holdout dir; fall back to canonical path."""
    candidates = [
        write_records_dir(project_root, "concepts") / "plan-confidence" / "holdout",
        project_root / ".claude" / "plan-confidence" / "holdout",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


PROJECT_ROOT = _find_project_root(SKILL_ROOT)
# Asked of the one owner rather than hardcoded. This line read `.claude/rules/` only,
# and the kit's own file is at `rules/` — so in this repository the path did not exist
# and every run silently fell back to the built-in bands. A consumer that recalibrates
# its cutoffs and keeps the standalone layout was scored against the shipped ones and
# told nothing, which is the failure this whole skill exists to refuse.
_RULES_DIR = rules_dir(PROJECT_ROOT)
DEFAULT_THRESHOLDS = (_RULES_DIR or PROJECT_ROOT / ".claude" / "rules") / "plan-confidence-thresholds.txt"
PLANS_DIR = _find_plans_dir(PROJECT_ROOT)
HOLDOUT_DIR = _find_holdout_dir(PROJECT_ROOT)
HOLDOUT_TARGET = 30  # M1 milestone: N>=30 for Cohen's kappa to make sense

# SOTA composite weights (ADR D8 — renormalize for active dimensions in each milestone)
SOTA_WEIGHTS = {
    "completeness": 0.30,
    "evidence": 0.30,
    "calibration": 0.20,
    "structural_risk": 0.20,
}
M2_ACTIVE_DIMENSIONS = ["completeness", "structural_risk"]


@dataclass
class Reason:
    sign: str  # 'positive' | 'negative' | 'neutral'
    label: str
    weight: float


@dataclass
class StructuralScoreReport:
    plan_slug: str
    plan_path: str
    plan_version: str
    scored_at: str
    completeness_score: float
    structural_risk_score: float
    active_dimensions: list[str]
    weight_normalization_factor: float
    weighted_avg: float
    hard_caps_triggered: list[str]
    final_score_after_caps: float
    verdict: str
    reasons: dict[str, list[Reason]]
    sub_reports: dict[str, Any] = field(default_factory=dict)


def renormalize_weights(active_dimensions: list[str]) -> dict[str, float]:
    """ADR D8: renormalize SOTA weights to active dimensions only.

    Sum of SOTA weights over active dims becomes the denominator; each active
    dim gets weight = SOTA_weight / denominator. Sum is 1.0 across active dims.
    """
    sota_sum = sum(SOTA_WEIGHTS[d] for d in active_dimensions if d in SOTA_WEIGHTS)
    if sota_sum == 0:
        raise ValueError(f"No SOTA weight found for active dimensions {active_dimensions}")
    return {d: SOTA_WEIGHTS[d] / sota_sum for d in active_dimensions if d in SOTA_WEIGHTS}


def _resolve_plan_path(arg: str) -> Path:
    """Accept a slug like 'plan-confidence-setup' or a path."""
    candidate = Path(arg)
    if candidate.exists() and candidate.is_file():
        return candidate
    # Try as a slug
    slug = arg.removesuffix("-plan").removesuffix(".md")
    slug_path = PLANS_DIR / f"{slug}-plan.md"
    if slug_path.exists():
        return slug_path
    raise FileNotFoundError(f"Plan not found: {arg}")


def _read_plan_version(plan_path: Path) -> str:
    content = plan_path.read_text(encoding="utf-8-sig")
    m = re.search(r"\*\*Version\s+([\d\.]+)\*\*", content)
    return m.group(1) if m else "unknown"


def _load_thresholds(thresholds_path: Path) -> list[tuple[str, int]]:
    """Parse thresholds allowlist into [(band, min_score), ...] sorted desc."""
    bands: list[tuple[str, int]] = []
    for line in thresholds_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) < 2:
            continue
        bands.append((parts[0].strip(), int(parts[1].strip())))
    bands.sort(key=lambda x: x[1], reverse=True)
    return bands


def _panel_state(project_root: Path, slug: str) -> dict:
    """What the review panel decided about this plan, if anything.

    Deliberately does not move the score — see the call site. Failing to reach the
    gate is NOT a pass: an unconsulted panel leaves the plan held, never advanced.
    """
    gates = project_root / "mechanisms" / "gates"
    if not gates.is_dir():
        gates = project_root / ".claude" / "mechanisms" / "gates"
    if not gates.is_dir():
        return {"status": "unchecked",
                "detail": "no mechanisms/gates in this project; the panel could not be "
                          "consulted, and an unconsulted panel is not an approval"}
    if str(gates) not in sys.path:
        sys.path.insert(0, str(gates))
    try:
        from check_panel_approval import check as _panel_check
    except ImportError as exc:  # pragma: no cover - environment, not logic
        return {"status": "unchecked", "detail": f"cannot load the panel gate: {exc}"}

    _, result = _panel_check(slug, "plan", project=project_root)
    return result


def _lookup_verdict(score: float, bands: list[tuple[str, int]]) -> str:
    for band_name, min_score in bands:
        if score >= min_score:
            return band_name
    return "INVALID"


def _compute_completeness(cov: CoverageReport, adr: ADRReport, tdd: TDDReport) -> tuple[float, list[Reason]]:
    """v1.1 EC-1 fix: single formula (rubric weights 0.6/0.2/0.2 per Phase 4.3 algorithm)."""
    coverage_int = 1.0 if cov.is_complete else 0.0
    coverage_score = 60.0 * coverage_int  # weight 0.6 * 100
    adr_score = 20.0 * adr.completeness_ratio
    tdd_score = 20.0 * tdd.coverage_ratio
    completeness = coverage_score + adr_score + tdd_score

    reasons: list[Reason] = []
    sign_cov = "positive" if cov.is_complete else "negative"
    reasons.append(Reason(sign=sign_cov, label=f"Coverage Matrix {'100%' if cov.is_complete else f'{cov.coverage_ratio:.0%}'}", weight=coverage_score))
    # A DIMENSION WITH NO SUBJECT IS NEITHER POSITIVE NOR NEGATIVE.
    #
    # Both of these read a ratio that is 1.0 by construction when there is nothing to measure —
    # `check_adr_completeness` returns 1.0 for zero ADRs, deliberately, and `plan-template.md`
    # says a plan with one way to do a thing has no decision to record. The ratio is right; using
    # it as a SIGN was not: a plan with no ADR reported a positive signal at full weight, and so
    # did a plan with no bug-fix task. Reported by a consumer measuring `total_adrs: 0,
    # completeness_ratio: 1.0` beside a perfect dimension score (#187).
    #
    # The SCORE is deliberately unchanged. The weights are `rubric-v1.md`'s and the 90% threshold
    # is calibrated against this formula; redistributing 20 points when a dimension is unexercised
    # would recalibrate every verdict in the kit silently, which is a rubric decision rather than
    # a defect fix. `test_the_score_is_unchanged_by_this` pins that on purpose.
    #
    # The argument for saying it out loud is `check_install_drift`'s, about its own counts: "a 0
    # that means 'not reported' and a 0 that means 'none' are different facts, and summing them
    # silently is how a total becomes fiction."
    if adr.total_adrs == 0:
        sign_adr, label_adr = "neutral", "ADR alternatives — NOT MEASURED (no ADRs in this plan)"
    else:
        sign_adr = "positive" if adr.completeness_ratio >= 1.0 else "negative"
        label_adr = f"ADR alternatives ({adr.with_alternatives}/{adr.total_adrs})"
    reasons.append(Reason(sign=sign_adr, label=label_adr, weight=adr_score))

    if tdd.total_bugfix_tasks == 0:
        sign_tdd, label_tdd = "neutral", "TDD in bug-fix — NOT MEASURED (no bug-fix task)"
    else:
        sign_tdd = "positive" if tdd.coverage_ratio >= 1.0 else "negative"
        label_tdd = f"TDD in bug-fix ({tdd.with_tdd}/{tdd.total_bugfix_tasks})"
    reasons.append(Reason(sign=sign_tdd, label=label_tdd, weight=tdd_score))

    return completeness, reasons


def _compute_structural_risk(smells: SmellReport) -> tuple[float, list[Reason]]:
    structural_risk = max(0.0, 100.0 + smells.total_penalty)
    # Top 3 categories by hit count
    sorted_cats = sorted(smells.by_category.items(), key=lambda x: x[1], reverse=True)
    reasons: list[Reason] = []
    for cat, count in sorted_cats[:3]:
        reasons.append(Reason(sign="negative" if count > 0 else "neutral", label=f"{count} {cat} hits", weight=-float(count)))
    return structural_risk, reasons


#: The caps that force INVALID regardless of the score bands.
#:
#: Named once, as a set, because SKILL.md has to be checkable against it. Spread
#: across five `or` clauses it could not be, and the document drifted to listing two
#: of the five — so a plan returned INVALID on `alignment_not_reached` found no
#: explanation in the contract its author was reading.
#: The two cap values, named once. They were bare literals in eight `triggered.append`
#: calls — the same two numbers, spelled eight times — so a reader could not see that
#: there are exactly TWO severities here, and `_lookup_verdict` reads the band table for
#: the same boundaries under different names. 49 is the top of INVALID; 70 is the top of
#: SHIPPABLE_WITH_CAVEATS.
CAP_INVALID = 49
CAP_WITH_CAVEATS = 70

_INVALID_CAPS: frozenset[str] = frozenset({
    "coverage_lt_100",
    # Same consequence as the line above, different cause. A cap that forces INVALID and
    # is missing from this set scores the plan down without declaring the verdict, which
    # is the half-applied state a reader cannot tell from a passing one.
    "coverage_matrix_unreadable",
    # Same consequence, third cause: the matrix parsed, the ratio is 1.0, and a row points
    # at a criterion no task declares.
    "matrix_cites_undeclared_criterion",
    "fabricated_citation",
    "patterns_skill_ignored",
    "deps_audit_insecure",
    "alignment_not_reached",
})


def _detect_hard_caps(
    cov: CoverageReport,
    adr: ADRReport,
    tdd: TDDReport,
    evidence: EvidenceReport | None = None,
    executability: ExecutabilityReport | None = None,
    patterns_consumption: PatternsConsumptionReport | None = None,
) -> list[tuple[str, int]]:
    """Return list of (cap_id, cap_value) for triggered caps.

    L5 fail-closed principle: when in doubt, FAIL the plan rather than pass.
    Caps are STRICTLY enforced (no soft-cap variants, no '--skip-checks' flag).
    """
    triggered: list[tuple[str, int]] = []
    if cov.criteria_not_declared:
        # A row citing a criterion nobody declares is a gap the matrix only LOOKS like it
        # closed. Reported under its own id rather than folded into `coverage_lt_100`,
        # which would say the ratio is short when the ratio is 1.0 and the row is hollow.
        triggered.append(("matrix_cites_undeclared_criterion", 49))
    if not cov.header_recognised:
        # The verdict is the same — a plan whose coverage cannot be assessed does not
        # enter `/implement`, and L5 is fail-closed. The REASON is what changes.
        # `coverage_lt_100` on a table nobody read is a true statement about a false
        # premise, and it sends the author hunting for a missing row instead of at the
        # header. Not both: two caps for one cause reads as two problems.
        triggered.append(("coverage_matrix_unreadable", 49))
    elif not cov.is_complete:
        triggered.append(("coverage_lt_100", 49))
    if adr.total_adrs > 0 and adr.completeness_ratio < 1.0:
        triggered.append(("adr_without_alternatives", CAP_WITH_CAVEATS))
    if tdd.total_bugfix_tasks > 0 and tdd.coverage_ratio < 1.0:
        triggered.append(("bugfix_without_tdd", CAP_WITH_CAVEATS))
    if evidence is not None and evidence.unresolved_citations:
        triggered.append(("fabricated_citation", CAP_INVALID))
    if executability is not None and executability.soft_cap_triggered:
        # Heuristic-grade soft cap — Acceptance Criteria not executable enough.
        # See check_criterion_executability.py for the gate thresholds.
        triggered.append(("vague_acceptance_criteria", CAP_WITH_CAVEATS))
    if patterns_consumption is not None and not patterns_consumption.is_clean:
        # An applicable *-patterns skill was neither cited nor ADR-overridden.
        # Hard cap at 49 (INVALID) — silently skipping applicable domain
        # knowledge is as corrosive to plan integrity as a fabricated citation.
        # Escape hatch: a one-line override ADR naming the skill.
        triggered.append(("patterns_skill_ignored", CAP_INVALID))
    return triggered


def _apply_conservative_floor(
    score: float, smells_total_hits: int, cov: CoverageReport
) -> tuple[float, str | None]:
    """L5 conservative bias: when signals indicate risk, never give SHIPPABLE.

    Fail-closed rules:
      1) If smell density is suspicious (>= 30 hits in prose-stripped content),
         cap final at 89 (SHIPPABLE -> SHIPPABLE_WITH_CAVEATS).
      2) If coverage is borderline (ratio in [0.9, 1.0) but is_complete due to
         deferred items), cap final at 89.

    These caps are SOFT (cap but don't trigger INVALID); they enforce the
    "false-positive over false-negative" principle.
    """
    reason: str | None = None
    soft_cap = 100.0

    if smells_total_hits >= 30:
        soft_cap = min(soft_cap, 89.0)
        reason = "smell_density_high"
    if cov.deferred_gaps > 0 and cov.total_gaps > 0:
        deferred_ratio = cov.deferred_gaps / cov.total_gaps
        if deferred_ratio > 0.2:  # >20% of gaps deferred
            soft_cap = min(soft_cap, 89.0)
            reason = reason or "high_deferred_ratio"

    if score > soft_cap:
        return soft_cap, reason
    return score, None


class _Checks(NamedTuple):
    """Every checker's report, run once and passed on by name.

    Extracted from `run_structural`, which measured cyclomatic complexity 39. The
    fifteen calls below were fifteen locals in one scope, and everything downstream
    reached them by being in that scope — which is what made the function unsplittable.
    A named tuple, not a dict: a typo in a field name is an error here and a silent
    `None` there, and this is the scorer.
    """

    cov: object
    adr: object
    tdd: object
    smells: object
    compliance: object
    evidence: object
    executability: object
    baseline_ctx: object
    drawbacks: object
    concurrency: object
    failure_scenarios: object
    deps_audit: object
    alignment: object
    interfaces: object
    patterns_consumption: object


def _run_checkers(plan_path: Path, rubric_path: Path) -> _Checks:
    """Run every checker over the plan. Pure code movement from `run_structural`."""
    # Run checkers
    cov = check_coverage_matrix(plan_path)
    adr = check_adr_completeness(plan_path)
    tdd = check_tdd_in_bugfix(plan_path)
    smells = check_spec_smells(plan_path, rubric_path)
    compliance = check_architecture_compliance(plan_path)
    evidence = check_evidence_citations(plan_path, _find_repo_root_from_plan(plan_path))
    executability = check_criterion_executability(plan_path)
    baseline_ctx = check_baseline_context(plan_path)
    drawbacks = check_drawbacks_section(plan_path)
    concurrency = check_concurrency_tests(plan_path)
    failure_scenarios = check_failure_scenarios(plan_path)
    deps_audit = check_deps_audit(plan_path)
    alignment = check_alignment_gate(plan_path)
    # Pre-flight: producer/consumer coherence across tasks, while both are
    # still prose. `check_wiring.py` asks this after /implement, when the
    # mismatched calls are already written.
    interfaces = check_task_interfaces(plan_path)
    patterns_consumption = check_patterns_consumption(plan_path, _find_repo_root_from_plan(plan_path))
    return _Checks(
        cov=cov, adr=adr, tdd=tdd, smells=smells, compliance=compliance,
        evidence=evidence, executability=executability, baseline_ctx=baseline_ctx,
        drawbacks=drawbacks, concurrency=concurrency,
        failure_scenarios=failure_scenarios, deps_audit=deps_audit,
        alignment=alignment, interfaces=interfaces,
        patterns_consumption=patterns_consumption)


def _weighted_score(cov, adr, tdd, smells) -> tuple:
    """The per-dimension scores and their renormalised average (ADR D8).

    Pure code movement from `run_structural`.
    """
    # Compute per-dimension scores
    completeness, completeness_reasons = _compute_completeness(cov, adr, tdd)
    structural_risk, structural_risk_reasons = _compute_structural_risk(smells)

    # ADR D8 — renormalize for active dimensions
    active = M2_ACTIVE_DIMENSIONS[:]
    normalized_weights = renormalize_weights(active)
    norm_factor = sum(SOTA_WEIGHTS[d] for d in active)  # e.g., M2: 0.30+0.20=0.50

    weighted_avg = (
        normalized_weights["completeness"] * completeness
        + normalized_weights["structural_risk"] * structural_risk
    )

    return (completeness, completeness_reasons, structural_risk,
            structural_risk_reasons, weighted_avg, active, normalized_weights,
            norm_factor)


def run_structural(
    plan_path: Path,
    rubric_path: Path = DEFAULT_RUBRIC,
    thresholds_path: Path = DEFAULT_THRESHOLDS,
    *,
    structural_only: bool = False,
) -> StructuralScoreReport:
    """Main orchestrator.

    The review-panel gate is ON by default: a plan no panel carried must not reach a
    verdict that advances it. `structural_only=True` measures structure alone, and the
    choice is RECORDED in `sub_reports["panel"]` rather than left invisible — a bypass
    nobody can see in the artifact is a bypass that quietly becomes the norm.
    """
    plan_version = _read_plan_version(plan_path)
    # Validate rubric parses (raises if malformed) — content used inside check_spec_smells.
    load_rubric(rubric_path)
    # The source of the bands is RECORDED, not assumed. A fallback nobody can see in
    # the artifact is a fallback that quietly becomes the norm.
    if thresholds_path.exists():
        bands = _load_thresholds(thresholds_path)
        bands_source = {"source": str(thresholds_path), "origin": "file"}
    else:
        bands = [
            ("SHIPPABLE", 90), ("SHIPPABLE_WITH_CAVEATS", 70),
            ("NON_SHIPPABLE", 50), ("INVALID", 0),
        ]
        bands_source = {"source": "built-in defaults", "origin": "fallback",
                        "detail": f"{thresholds_path} does not exist"}

    # Every checker, run once. The names below are unpacked from the record so the
    # eighty lines of cap logic that follow read exactly as they did.
    _checks = _run_checkers(plan_path, rubric_path)
    (cov, adr, tdd, smells, compliance, evidence, executability, baseline_ctx,
     drawbacks, concurrency, failure_scenarios, deps_audit, alignment, interfaces,
     patterns_consumption) = _checks

    (completeness, completeness_reasons, structural_risk, structural_risk_reasons,
     weighted_avg, active, normalized_weights,
     norm_factor) = _weighted_score(cov, adr, tdd, smells)

    # Hard caps (strict, fail-closed)
    triggered = _detect_hard_caps(cov, adr, tdd, evidence, executability, patterns_consumption)
    hard_cap_ids = [t[0] for t in triggered]
    if triggered:
        smallest_cap = min(t[1] for t in triggered)
        final_score = min(weighted_avg, float(smallest_cap))
    else:
        final_score = weighted_avg

    # L5 conservative soft-floor (fail-closed bias)
    final_score, soft_reason = _apply_conservative_floor(
        final_score, smells.total_hits, cov
    )
    if soft_reason:
        hard_cap_ids.append(f"soft_floor_{soft_reason}")

    # L6 architecture compliance soft cap: plans that don't reference any rule
    # in `.claude/rules/` (compliance_score < 0.4) cap at 89 (RESSALVAS max).
    # This is the user's "TODAS etapas devem estar 100% alinhadas a .claude/rules/"
    # contract — surfaces non-alignment as a visible deduction.
    if compliance.compliance_score < 0.4 and final_score > 89.0:
        final_score = 89.0
        hard_cap_ids.append("soft_floor_low_architecture_compliance")

    # SOTA-upgrade soft caps, at 89. A sunset date of 2026-09-07 stood here promising a
    # promotion to 70; the date passed, the promotion did not happen, and nothing
    # detected the expiry. Promoting changes the verdict for every consumer and is a
    # decision somebody makes, not a date arriving — so 89 is the rule, stated as one.
    # These verify the new mandatory sections introduced by the SOTA plan-template upgrade:
    #   - Baseline Context (deep review of current state) — file table + callers + glossary
    #   - Drawbacks & Risks — ≥ 2 entries with severity + mitigation + owner
    #   - Unresolved Questions — entries OR explicit "(none — every decision is resolved)"
    # Soft cap at 89 means legacy plans keep working as SHIPPABLE_WITH_CAVEATS until
    # authors migrate them. See `rules/plan-confidence-golden-rule.md § SOTA upgrade`.
    # Every violation is appended independently (not gated by current final_score)
    # so authors see the full migration backlog in the hard_caps_triggered list.
    if not baseline_ctx.is_complete:
        hard_cap_ids.append("soft_floor_baseline_context_incomplete")
        final_score = min(final_score, 89.0)
    if not drawbacks.drawbacks_is_complete:
        hard_cap_ids.append("soft_floor_drawbacks_section_insufficient")
        final_score = min(final_score, 89.0)
    if not drawbacks.unresolved_is_complete:
        hard_cap_ids.append("soft_floor_unresolved_questions_section_missing")
        final_score = min(final_score, 89.0)
    # Concurrency tests check is CONDITIONAL — only triggers when concurrency
    # signals are detected in the plan (mutex/goroutine/async/atomic/channel).
    # Plans with no concurrency signals are skipped.
    if concurrency.signals_detected and not concurrency.is_complete:
        hard_cap_ids.append("soft_floor_concurrency_tests_missing")
        final_score = min(final_score, 89.0)
    # Failure scenarios check is CONDITIONAL — only triggers when external-I/O
    # signals are detected (HTTP/DB/queue/gRPC/object-store). Plans without
    # external I/O are skipped.
    if failure_scenarios.external_io_detected and not failure_scenarios.is_complete:
        hard_cap_ids.append("soft_floor_failure_scenarios_missing")
        final_score = min(final_score, 89.0)

    # `cycle-plan`'s CVE gate stopped depending on someone honouring it. This check
    # does not look for CVEs — `/deps-audit` does that, with the scanners — it READS
    # the verdict that run left on disk. A plan declaring a new dependency with no
    # audit gets a soft floor (nobody checked); one whose report points at a
    # CRITICAL/HIGH CVE gets a hard cap, which is the gate `cycle-plan.md § Phase
    # contracts` declared and nothing enforced.
    if deps_audit.applies and deps_audit.hard_cap:
        hard_cap_ids.append(deps_audit.stable_id)
        final_score = min(final_score, 49.0)
    elif deps_audit.applies and deps_audit.soft_floor:
        hard_cap_ids.append(deps_audit.stable_id)
        final_score = min(final_score, 89.0)

    # A plan may not DEMAND a symbol whose name the project's own rule forbids.
    #
    # Measured on a consumer 2026-09-16: seven plans demanded test names carrying a ticket
    # id — 101 occurrences — while the string appeared in zero `.go` files, because the
    # tests exist under behaviour-shaped names an implementer chose for exactly that
    # reason. The plans also contradicted their own alignment briefs, which already
    # carried the correct names.
    #
    # It is scored HERE and not at implement because by then the contradiction is
    # inherited: a criterion demanding a string that does not exist reads identically to
    # one nobody has satisfied yet, which is what a RED criterion looks like. The name
    # being forbidden is decidable from the plan alone.
    # The plan's declared impediment and the registry's must be the same edge. Nothing
    # compared them: every scheduler resolves `blocked_by` from the REGISTRY, so an item
    # whose plan says it is held reads as free to start. Measured on a consumer
    # 2026-09-16: seven plans declared an impediment their registry block did not carry,
    # all naming the same blocker.
    #
    # Only the missing-in-registry direction caps. The reverse is reported and not
    # charged: the registry is authoritative and a plan may predate an impediment.
    # Reported, never capped. See `check_impediment_agrees.soft_floor` for why: the first
    # version capped this and would have held five structurally perfect plans on an
    # impediment that had already been cured.
    impediment = check_impediment_agrees(plan_path)

    symbol_naming = check_symbol_naming(plan_path)
    if symbol_naming.soft_floor:
        hard_cap_ids.append(symbol_naming.stable_id)
        final_score = min(final_score, 89.0)

    # The 90% alignment threshold, mechanised. Until this line existed the rule
    # was PROSE in three documents — `alignment-threshold.md`, a pre-condition in
    # `cycle-implement.md`, a phase contract in `cycle-plan.md` — and a grep for
    # anything READING `records/alignment/` returned nothing. Three documents said
    # the item must not be built; no code could stop it.
    #
    # Unlike every other cap here there is no dismissing ADR and no `--skip`.
    # An escape hatch on this one is an escape hatch on the reason it exists.
    if alignment.hard_cap:
        hard_cap_ids.append("alignment_not_reached")
        final_score = min(final_score, float(alignment.hard_cap))
    elif alignment.soft_floor:
        hard_cap_ids.append("alignment_not_applicable")
        final_score = min(final_score, float(alignment.soft_floor))

    verdict = _lookup_verdict(final_score, bands)
    if _INVALID_CAPS & set(hard_cap_ids):
        verdict = "INVALID"

    # The panel gates the VERDICT, never the score. A script scores structure; the
    # panel judges whether the evidence supports the conclusion drawn from it, and
    # folding the two would conflate "this plan is weak" with "nobody reviewed it".
    # Both tokens below already exist in `rules/verdict-bands.txt`.
    if structural_only:
        panel = {"status": "not_consulted",
                 "detail": "--structural-only: the panel gate was not applied. This "
                           "verdict describes STRUCTURE and does not say the plan may "
                           "advance"}
    else:
        panel = _panel_state(PROJECT_ROOT, plan_path.stem.removesuffix("-plan"))
        if verdict != "INVALID":
            if panel["status"] == "returned":
                verdict = "NEEDS_REVISION"
            elif panel["status"] == "no_record":
                # Complete, and nobody has signed — the same shape phase 0 already
                # calls AWAITING_REVIEW. The action is to convene, not to rewrite.
                verdict = "AWAITING_REVIEW"
            elif panel["status"] not in ("approved", "not_gated"):
                # Cannot convene here: held on a material impediment.
                verdict = "ITEM_IN_FLIGHT"

    evidence_reasons: list[Reason] = []
    if evidence.total_citations > 0:
        resolved_count = evidence.total_citations - len(evidence.unresolved_citations)
        if resolved_count > 0:
            evidence_reasons.append(
                Reason(sign="positive", label=f"{resolved_count} citations resolved", weight=float(resolved_count))
            )
        if evidence.unresolved_citations:
            evidence_reasons.append(
                Reason(
                    sign="negative",
                    label=f"{len(evidence.unresolved_citations)} fabricated citation(s)",
                    weight=-float(len(evidence.unresolved_citations)),
                )
            )

    reasons_by_dimension: dict[str, list[Reason]] = {
        "completeness": completeness_reasons,
        "evidence": evidence_reasons,
        "calibration": [],  # M5 future
        "structural_risk": structural_risk_reasons,
    }

    return StructuralScoreReport(
        plan_slug=plan_path.stem.removesuffix("-plan"),
        plan_path=str(plan_path),
        plan_version=plan_version,
        scored_at=datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
        completeness_score=round(completeness, 2),
        structural_risk_score=round(structural_risk, 2),
        active_dimensions=active,
        weight_normalization_factor=round(1.0 / norm_factor, 4),
        weighted_avg=round(weighted_avg, 2),
        hard_caps_triggered=hard_cap_ids,
        final_score_after_caps=round(final_score, 2),
        verdict=verdict,
        reasons=reasons_by_dimension,
        sub_reports={
            "panel": panel,
            "thresholds": bands_source,
            "coverage_matrix": {
                "total_gaps": cov.total_gaps,
                "mapped_gaps": cov.mapped_gaps,
                "coverage_ratio": cov.coverage_ratio,
                "is_complete": cov.is_complete,
                "orphan_tasks": list(cov.orphan_tasks),
                "unmapped_gaps": list(cov.unmapped_gaps),
            },
            "adr_completeness": {
                "total_adrs": adr.total_adrs,
                "with_alternatives": adr.with_alternatives,
                "completeness_ratio": adr.completeness_ratio,
                "missing_alternatives": list(adr.missing_alternatives),
                "missing_cost_if_wrong": list(adr.missing_cost_if_wrong),
            },
            "tdd_in_bugfix": {
                "total_bugfix_tasks": tdd.total_bugfix_tasks,
                "with_tdd": tdd.with_tdd,
                "coverage_ratio": tdd.coverage_ratio,
                "missing_tdd": list(tdd.missing_tdd),
            },
            "spec_smells": {
                "total_hits": smells.total_hits,
                "by_category": dict(smells.by_category),
                "total_penalty": smells.total_penalty,
            },
            "architecture_compliance": {
                "compliance_score": compliance.compliance_score,
                "project_rules_found_count": len(compliance.project_rules_found),
                "fallback_to_defaults": compliance.fallback_to_defaults,
                "rules_referenced_in_plan": list(compliance.rules_referenced_in_plan),
                "principles_cited": list(compliance.principles_cited),
                "has_dod_quality_signal": compliance.has_dod_quality_signal,
                "has_size_budget_signal": compliance.has_size_budget_signal,
                "reasons": list(compliance.reasons),
            },
            "evidence": {
                "total_citations": evidence.total_citations,
                "unresolved_citations": [
                    {
                        "kind": c.kind,
                        "raw_text": c.raw_text,
                        "location_line": c.location_line,
                        "reason": c.reason,
                    }
                    for c in evidence.unresolved_citations
                ],
            },
            "criterion_executability": {
                "total_criteria": executability.total_criteria,
                "vague_count": executability.vague_count,
                "weak_count": executability.weak_count,
                "acceptable_count": executability.acceptable_count,
                "executable_count": executability.executable_count,
                "vague_ratio": round(executability.vague_ratio, 3),
                "acceptable_ratio": round(executability.acceptable_ratio, 3),
                "executable_ratio": round(executability.executable_ratio, 3),
                "soft_cap_triggered": executability.soft_cap_triggered,
                "vague_criteria_sample": [
                    c.text for c in executability.criteria if c.score == 0
                ][:5],
            },
            "baseline_context": {
                "section_present": baseline_ctx.section_present,
                "is_complete": baseline_ctx.is_complete,
                "missing_subsections": list(baseline_ctx.missing_subsections),
                "file_table_rows": baseline_ctx.file_table_rows,
                "file_table_placeholder_hits": baseline_ctx.file_table_placeholder_hits,
                "glossary_entries": baseline_ctx.glossary_entries,
                "glossary_placeholder_hits": baseline_ctx.glossary_placeholder_hits,
                "reasons": list(baseline_ctx.reasons),
            },
            "drawbacks_and_unresolved": {
                "drawbacks_section_present": drawbacks.drawbacks_section_present,
                "drawbacks_entries": drawbacks.drawbacks_entries,
                "drawbacks_placeholder_hits": drawbacks.drawbacks_placeholder_hits,
                "drawbacks_is_complete": drawbacks.drawbacks_is_complete,
                "drawbacks_reasons": list(drawbacks.drawbacks_reasons),
                "unresolved_section_present": drawbacks.unresolved_section_present,
                "unresolved_entries": drawbacks.unresolved_entries,
                "unresolved_explicit_none": drawbacks.unresolved_explicit_none,
                "unresolved_is_complete": drawbacks.unresolved_is_complete,
                "unresolved_reasons": list(drawbacks.unresolved_reasons),
            },
            "concurrency_tests": {
                "signals_detected": concurrency.signals_detected,
                "signals_sample": list(concurrency.signals_sample),
                "tasks_with_concurrency_subsection": concurrency.tasks_with_concurrency_subsection,
                "tasks_with_acceptable_test_or_escape": concurrency.tasks_with_acceptable_test_or_escape,
                "tasks_failing": list(concurrency.tasks_failing),
                "is_complete": concurrency.is_complete,
                "reasons": list(concurrency.reasons),
            },
            "patterns_consumption": {
                "applicable": list(patterns_consumption.applicable),
                "cited": list(patterns_consumption.cited),
                "overridden": list(patterns_consumption.overridden),
                "ignored": list(patterns_consumption.ignored),
                "is_clean": patterns_consumption.is_clean,
                "reasons": list(patterns_consumption.reasons),
            },
            # Pre-flight, reported alongside the other structural checks. It is
            # advisory by design: the signature block the plan template calls
            # optional is what it reads, so a finding is a question for the
            # author rather than a verdict about the plan.
            "task_interfaces": {
                "tasks_total": interfaces.tasks_total,
                "tasks_with_signatures": interfaces.tasks_with_signatures,
                "tasks_unchecked": interfaces.tasks_total - interfaces.tasks_with_signatures,
                "produced_never_consumed": list(interfaces.produced_never_consumed),
                "consumed_never_produced": list(interfaces.consumed_never_produced),
                "consumed_before_produced": list(interfaces.consumed_before_produced),
            },
            "failure_scenarios": {
                "alignment_gate": {
                    "applies": alignment.applies,
                    "verdict": alignment.verdict,
                    "reason": alignment.reason,
                    "machine_ratio": alignment.machine_ratio,
                    "brief_path": alignment.brief_path,
                },
                # `impediment` caps nothing by design (see its call site). It is carried
                # here because the comment there says it is REPORTED, and until this block
                # existed the value was computed and dropped — a claim with no channel.
                "impediment": {
                    "applies": impediment.applies,
                    "plan_declares": list(impediment.plan_declares),
                    "registry_declares": list(impediment.registry_declares),
                    "missing_in_registry": list(impediment.missing_in_registry),
                    "missing_in_plan": list(impediment.missing_in_plan),
                    "reasons": list(impediment.reasons),
                },
                "deps_audit": {
                    "applies": deps_audit.applies,
                    "verdict": deps_audit.verdict,
                    "hard_cap": deps_audit.hard_cap,
                    "soft_floor": deps_audit.soft_floor,
                    "declared": list(deps_audit.declared),
                    "audit_path": deps_audit.audit_path,
                    "reasons": list(deps_audit.reasons),
                },
                "external_io_detected": failure_scenarios.external_io_detected,
                "signals_sample": list(failure_scenarios.signals_sample),
                "section_present": failure_scenarios.section_present,
                "explicit_none": failure_scenarios.explicit_none,
                "scenarios_count": failure_scenarios.scenarios_count,
                "is_complete": failure_scenarios.is_complete,
                "reasons": list(failure_scenarios.reasons),
            },
        },
    )


#: The verdicts the PANEL gate produces. Not scores: the plan's number stands, and the
#: verdict is held pending a person. They share exit code 4 because all three mean the
#: same thing to a caller — convene or wait, do not fix the command.
PANEL_VERDICTS: tuple[str, ...] = ("AWAITING_REVIEW", "NEEDS_REVISION", "ITEM_IN_FLIGHT")


#: `<plan-slug>|<sunset-date>|<reason>`, the shape
#: `rules/plan-confidence-allowlist.txt` has documented since it was written.
_PLAN_ALLOWLIST_NAME = "plan-confidence-allowlist.txt"
_PLAN_ALLOWLIST_FIELDS = 3
_PLAN_ALLOWLIST_SUNSET_INDEX = 1


def _plan_project_root(plan_path: Path) -> Path:
    """The project the PLAN belongs to, which is not `PROJECT_ROOT`.

    `PROJECT_ROOT` walks up from the SCRIPT, so in a plugin install it is the consumer
    and in the kit's own checkout it is the kit — but a plan handed to this script by
    absolute path can live in neither. An exemption is the decision of the project that
    owns the plan, so it is looked up from the plan.
    """
    for parent in plan_path.resolve().parents:
        if (parent / DATA_DIRNAME).is_dir() or rules_dir(parent) is not None:
            return parent
    return PROJECT_ROOT


def _plan_waiver(project_root: Path, slug: str) -> tuple[str | None, list[str]]:
    """`(reason, problems)` — why this plan may return INVALID without failing CI.

    WHY THIS EXISTS. Three documents promised this waiver and nothing implemented it:
    the allowlist file itself ("Plans listed here are permitted to return
    verdict=INVALID without failing CI"), `PORTABLE.md` § 4, and
    `plan-confidence-golden-rule.md`. `setup.sh` installed the file and
    `test_portability.py` asserted it EXISTS — a test that attests presence and never
    behaviour, which is how a dead allowlist looks alive.

    The waiver is on the EXIT CODE alone. The verdict stays INVALID in the report,
    because rewriting it would hide the plan's state from every reader — a different
    and worse thing than not failing CI.
    """
    rules = rules_dir(project_root)
    if rules is None:
        return None, []
    try:
        entries = _parse_allowlist(
            rules / _PLAN_ALLOWLIST_NAME,
            field_count=_PLAN_ALLOWLIST_FIELDS,
            sunset_index=_PLAN_ALLOWLIST_SUNSET_INDEX,
            where=_PLAN_ALLOWLIST_NAME,
        )
    except MalformedEntry as error:
        # Refused, not skipped, and it waives nothing: a dropped line is an exemption
        # somebody believes they have and does not.
        return None, [str(error)]
    except OSError as error:
        return None, [f"{_PLAN_ALLOWLIST_NAME} could not be read: {error}"]

    expired = [e for e in entries if e.expired and e.fields[0] == slug]
    for entry in _active_entries(entries):
        if entry.fields[0] == slug:
            return entry.fields[2], []
    if expired:
        return None, [
            f"{_PLAN_ALLOWLIST_NAME}: the entry for {slug!r} expired on "
            f"{expired[0].sunset.isoformat()} and no longer waives anything"
        ]
    return None, []


def _exit_code(verdict: str) -> int:
    if verdict in ("SHIPPABLE", "SHIPPABLE_WITH_CAVEATS"):
        return 0
    if verdict == "INVALID":
        return 1
    if verdict == "NON_SHIPPABLE":
        return 3
    if verdict in PANEL_VERDICTS:
        # 4, not the fall-through 2. SKILL.md maps 2 to "Error (plan not found,
        # malformed rubric)", so a structurally perfect plan waiting on its panel was
        # indistinguishable, to anything reading exit codes, from a command typed
        # wrong — and the two take opposite actions.
        return 4
    return 2


def _calibration_status() -> tuple[str, int, int]:
    """Return (status, holdout_count, target).

    Fix #1+#6: warns users when thresholds are still PROVISIONAL.
    Calibration is PRODUCTION_v1 only when N>=target AND a `.calibrated`
    marker file exists in the holdout dir (set after Cohen's kappa>=0.6 check).
    """
    if not HOLDOUT_DIR.exists():
        return ("PROVISIONAL_v1", 0, HOLDOUT_TARGET)
    entries = [
        p for p in HOLDOUT_DIR.iterdir()
        if p.is_file() and p.suffix == ".md" and p.name != "README.md"
    ]
    count = len(entries)
    calibrated_marker = HOLDOUT_DIR / ".calibrated"
    if count >= HOLDOUT_TARGET and calibrated_marker.exists():
        return ("PRODUCTION_v1", count, HOLDOUT_TARGET)
    return ("PROVISIONAL_v1", count, HOLDOUT_TARGET)


def _emit_calibration_warning() -> None:
    status, count, target = _calibration_status()
    if status == "PROVISIONAL_v1":
        print(
            f"WARN: thresholds are PROVISIONAL_v1 (calibration pending; "
            f"{count}/{target} holdout entries; Cohen's kappa not yet measured). "
            f"Score is structurally meaningful but cutoffs (49/70/90) are not "
            f"yet empirically validated. See `.claude/rules/plan-confidence-thresholds.txt`.",
            file=sys.stderr,
        )


def _find_repo_root_from_plan(plan_path: Path) -> Path:
    """Walk up from the plan path looking for a project-root marker.

    Recognizes (in order of preference):
      - `.git/`
      - `.claude/` (when the plan is NOT inside a `.claude/` subtree)
      - `plugin.json` (Claude Code plugin manifest — the canonical `plan` repo signature)
      - `rules/` directory paired with `skills/` (the planning ecosystem layout)
    """
    cur = plan_path.resolve().parent
    for _ in range(20):
        if ".claude" not in cur.parts:
            if (cur / ".git").exists():
                return cur
            if (cur / ".claude").exists():
                return cur
            if (cur / "plugin.json").exists():
                return cur
            if (cur / "rules").is_dir() and (cur / "skills").is_dir():
                return cur
        if cur == cur.parent:
            break
        cur = cur.parent
    return plan_path.resolve().parent


# T2.1 (R4.x / harden-fab-and-cq-gate) — code-quality subprocess + merge logic
# extracted to `skills/code-quality/scripts/cq_invoke.py` as the shared helper
# consumed by both this orchestrator and `skills/implement/scripts/run_validation.py`.
# Keeps wiring triad pillar (a) honest: cq_invoke.merge_verdict_into_plan_confidence
# has a real production caller below (previously this file kept private copies that
# starved the public helper of a caller — captured by judge-codex implementation stage
# on 2026-06-04 as wiring_triad_missing_caller_cq_merge_helper).
_CQ_INVOKE_DIRS = [
    Path(__file__).resolve().parent.parent.parent / "code-quality" / "scripts",
    Path(__file__).resolve().parent.parent.parent.parent / "skills" / "code-quality" / "scripts",
]
for _cq_dir in _CQ_INVOKE_DIRS:
    if _cq_dir.exists():
        sys.path.insert(0, str(_cq_dir))
        break

#: Why the code-quality gate is off, or None when it is on. The import below used to
#: set `cq_invoke = None` and say nothing else, so on any install where the sibling
#: skill is not resolvable the gate did nothing, reported nothing, and the plan scored
#: as if it had been checked. Nothing here makes the gate mandatory — a project may
#: legitimately not ship `code-quality` — but a gate that turns itself off has to leave
#: the reason somewhere the reader of the score will meet it.
CQ_UNAVAILABLE_BECAUSE: str | None = None

try:
    import cq_invoke  # type: ignore[import-not-found] — sibling skill, resolved by the sys.path line above
except ImportError as _exc:
    cq_invoke = None  # type: ignore[assignment] — the module-or-None sentinel every caller below tests for
    CQ_UNAVAILABLE_BECAUSE = (
        f"cq_invoke could not be imported ({_exc}); looked under "
        f"{', '.join(str(d) for d in _CQ_INVOKE_DIRS)}")


#: A plan dismissing one soft cap, with the reason inline.
#:
#: The shape copies `check_wiring.py`'s `<!-- ADR-DEFER-WIRING-B: <symbol>:
#: <reason> -->` rather than inventing a third marker convention — advice this
#: repository received from a consumer and had already followed once.
#:
#: An explicit marker, not prose mentioning the id: a plan can name a cap in
#: order to say it will NOT be dismissed, and a grep cannot tell the two apart.
#: The gate has to read a decision, not a keyword.
_DISMISS_SOFT_CAP_RE = re.compile(
    #: B-170 (an adopter) — two defects in one expression, neither covered by a test.
    #:
    #: The reason excluded `>`, so a reason written with an arrow (`warnings fell 15 -> 0`, the idiom
    #: this ecosystem states before/after with) ended the match early and the dismissal registered as
    #: ABSENT — silently: the plan stayed capped and demoted, which reads exactly like a cap nobody
    #: tried to dismiss. Reaching an undismissable soft cap by accident is the state
    #: `cycle-code-quality.md` § 1 says must not exist.
    #:
    #: And the id excluded `-`, so `auditor_unavailable_dependency-cruiser` — a real cap id emitted by
    #: this kit's own detector — could never be dismissed at all.
    #:
    #: `(?s)` so a reason may wrap across lines. The empty-reason case is refused by the caller.
    r"(?s)<!--\s*ADR-DISMISS-SOFT-CAP:\s*([a-z0-9_-]+)\s*:(?P<reason>(?:(?!-->).)*)-->"
)


def _dismissed_soft_caps(plan_text: str) -> set[str]:
    """Soft-cap ids this plan dismisses with an ADR.

    `rules/cycle-code-quality.md` § 1 promised the escape and nothing read it.
    This is the reading half.
    """
    # An EMPTY reason is not a dismissal. `\s*` absorbed the nothing between the colon and the closer,
    # so `<!-- ADR-DISMISS-SOFT-CAP: some_cap: -->` counted — a dismissal with no justification, which
    # is precisely what the audit trail exists to refuse. Found by the test written for the `>` defect.
    return {
        m.group(1)
        for m in _DISMISS_SOFT_CAP_RE.finditer(plan_text)
        if m.group("reason").strip()
    }


def _merge_code_quality_verdict(out: dict, cq_summary: dict, plan_text: str = "") -> None:
    """Thin wrapper around `cq_invoke.merge_verdict_into_plan_confidence` for
    backward compatibility with existing call sites + the test suite that
    imports this symbol via `from run_structural import _merge_code_quality_verdict`.

    `plan_text` is optional so the older two-argument call sites keep working;
    without it no cap is dismissed, which is the pre-existing behaviour.
    """
    if cq_invoke is None:
        out["code_quality_unchecked"] = (
            CQ_UNAVAILABLE_BECAUSE
            or "cq_invoke is unavailable; the code-quality gate did not run")
        return
    cq_invoke.merge_verdict_into_plan_confidence(
        out, cq_summary, dismissed_soft_caps=_dismissed_soft_caps(plan_text)
    )


def _invoke_code_quality(plan_slug: str, repo_root: Path, timeout_s: int = 600) -> dict | None:
    """Thin wrapper around `cq_invoke.invoke`. Kept for backward compatibility
    with the test suite (`test_run_structural.py` imports the symbol).
    """
    if cq_invoke is None:
        return None
    return cq_invoke.invoke(plan_slug, repo_root, timeout_s=timeout_s)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run M2 structural plan-confidence scoring.")
    parser.add_argument("plan", help="plan slug (e.g., 'plan-confidence-setup') or .md path")
    parser.add_argument("--rubric", default=str(DEFAULT_RUBRIC))
    parser.add_argument("--thresholds", default=str(DEFAULT_THRESHOLDS))
    parser.add_argument("--no-warn", action="store_true", help="suppress calibration warning")
    parser.add_argument(
        "--structural-only",
        action="store_true",
        help="score structure and do NOT apply the review-panel gate; recorded in the "
             "report, it does not hide",
    )
    parser.add_argument(
        "--no-code-quality",
        action="store_true",
        help="skip /code-quality runtime integration (T6.5)",
    )
    args = parser.parse_args(argv)

    try:
        plan_path = _resolve_plan_path(args.plan)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        report = run_structural(plan_path, Path(args.rubric), Path(args.thresholds),
                                structural_only=args.structural_only)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if not args.no_warn:
        _emit_calibration_warning()

    out = asdict(report)
    out["reasons"] = {
        k: [asdict(m) for m in v] for k, v in report.reasons.items()
    }
    # Embed calibration status in the JSON output for auditability.
    cal_status, cal_count, cal_target = _calibration_status()
    out["calibration"] = {
        "status": cal_status,
        "holdout_count": cal_count,
        "holdout_target": cal_target,
        "kappa_measured": False,
    }

    # T6.5 / EC-29 — runtime integration with /code-quality skill.
    if not args.no_code_quality:
        repo_root = _find_repo_root_from_plan(plan_path)
        cq_summary = _invoke_code_quality(report.plan_slug, repo_root)
        if cq_summary:
            cq_caps = list(cq_summary.get("hard_caps_triggered", []))
            cq_soft = list(cq_summary.get("soft_caps_triggered", []))
            out["code_quality"] = {
                "verdict": cq_summary.get("verdict"),
                "score_cap": cq_summary.get("score_cap"),
                "hard_caps_triggered": cq_caps,
                "soft_caps_triggered": cq_soft,
                "languages_audited": cq_summary.get("languages_audited", []),
            }
            # Severity-tier-aware merge (bug fix 2026-05-23: previous logic blindly
            # forced INVALID on any cq cap entry, neutralizing allowlist downgrades).
            # Read here rather than reusing a `content` from elsewhere: this is
            # `main()`, and the only other read lives inside a different function.
            # Passing a name that is not in scope is exactly what shipped once and
            # killed the scorer for every plan.
            _merge_code_quality_verdict(
                out, cq_summary, plan_path.read_text(encoding="utf-8-sig")
            )
        else:
            out["code_quality"] = {"verdict": "UNAVAILABLE", "reason": "invocation failed or skipped"}

    print(json.dumps(out, indent=2, ensure_ascii=False))
    final_verdict = out.get("verdict", report.verdict)
    code = _exit_code(final_verdict)

    # The allowlist waives the FAILURE, never the finding. A waived plan still prints
    # INVALID above; what changes is that CI does not stop on it.
    if code == 1:
        slug = plan_path.stem.removesuffix("-plan")
        reason, problems = _plan_waiver(_plan_project_root(plan_path), slug)
        for problem in problems:
            print(f"NOTE: {problem}", file=sys.stderr)
        if reason:
            print(f"NOTE: {final_verdict} waived for {slug!r} by "
                  f"`rules/{_PLAN_ALLOWLIST_NAME}`: {reason}. The verdict above is "
                  f"unchanged — the waiver is on the exit code, and it expires.",
                  file=sys.stderr)
            return 0
    return code


if __name__ == "__main__":
    sys.exit(main())
