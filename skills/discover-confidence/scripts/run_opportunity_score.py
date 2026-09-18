#!/usr/bin/env python3
"""Run M2 structural opportunity-confidence scoring.

Sibling of plan-confidence/scripts/run_structural.py — same architecture, different
rubric and checkers (corner_coverage / evidence_pointers / opportunity_completeness /
structural_risk).

Replaces the ancestor `run_blueprint_score.py`.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow sibling imports when invoked directly
sys.path.insert(0, str(Path(__file__).parent))

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap
from pathlib import Path as _Path_bootstrap

from _rubric_loader import load_rubric
from check_corner_coverage import check_corner_coverage
from check_evidence_pointers import check_evidence_pointers
from check_opportunity_completeness import check_opportunity_completeness
from check_spec_smells import check_spec_smells

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.paths import write_records_dir  # noqa: E402 — post-bootstrap import

SKILL_ROOT = Path(__file__).parent.parent


def _find_project_root(start: Path) -> Path:
    current = start.resolve().parent if start.is_file() else start.resolve()
    while current != current.parent:
        if (current / ".claude").exists() or (current / ".git").exists():
            return current
        current = current.parent
    return start.resolve().parent if start.is_file() else start.resolve()


def _resolve_opportunity(arg: str) -> Path:
    p = Path(arg)
    if p.exists() and p.suffix == ".md":
        return p.resolve()
    base = write_records_dir(Path.cwd(), "discoveries") / "opportunities"
    for c in (base / f"{arg}-opportunity.md", base / f"{arg}.md"):
        if c.exists():
            return c.resolve()
    raise FileNotFoundError(f"Could not resolve opportunity: {arg}")


def _resolve_rubric(arg: Path | None) -> Path:
    if arg and arg.exists():
        return arg
    return SKILL_ROOT / "templates" / "rubric-opportunity.md"


def _resolve_thresholds(arg: Path | None, opportunity_path: Path) -> tuple[Path, str]:
    """`(path, origin)` — which bands the verdict was computed against, and from where.

    `origin` exists because nothing recorded it. Four sources answer this question and
    the report named none of them, so a project that recalibrated its bands and kept a
    layout this resolver checks second was scored against the SHIPPED example — and
    told a confident verdict with no way to see which cutoffs produced it. The scorer's
    whole subject is whether a claim is grounded; its own grounding was not reported.
    """
    if arg and arg.exists():
        return arg, "given on the command line"
    project_root = _find_project_root(opportunity_path)
    # Both layouts, deliberately: `rules/` is standalone, `.claude/rules/` is plugin.
    # Checking only one made the project's own bands lose silently in the other, and a
    # scorer grading against the wrong bands still prints a confident verdict.
    for candidate in (
        project_root / "rules" / "discover-opportunity-thresholds.txt",
        project_root / ".claude" / "rules" / "discover-opportunity-thresholds.txt",
    ):
        if candidate.exists():
            return candidate, "this project's own"
    return (SKILL_ROOT / "templates" / "discover-opportunity-thresholds.example.txt",
            "the kit's shipped EXAMPLE — this project declares no thresholds of its own")


def _parse_thresholds(path: Path) -> dict[str, int]:
    bands: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2:
            try:
                bands[parts[0]] = int(parts[1])
            except ValueError:
                continue
    return bands


def _verdict_for(score: float, bands: dict[str, int]) -> str:
    for name, threshold in sorted(bands.items(), key=lambda kv: kv[1], reverse=True):
        if score >= threshold:
            return name
    return "INVALID"


def _panel_state(project_root: Path, slug: str) -> dict:
    """What the review panel decided about this opportunity, if anything.

    The panel is NOT a scoring dimension and deliberately does not move the score.
    `check_panel_approval.py` answers a different question — whether the evidence that
    resolves actually SUPPORTS the conclusion — and folding it into the number would
    conflate "this document is weak" with "nobody has reviewed it yet", two facts that
    take opposite actions.

    Failing to reach the gate is NOT a pass: an unreadable panel machinery leaves the
    document held, never advanced.
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

    _, result = _panel_check(slug, "discover", project=project_root)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run M2 structural opportunity-confidence scoring.")
    parser.add_argument("opportunity", help="opportunity slug or .md path")
    parser.add_argument("--rubric", type=Path, default=None)
    parser.add_argument("--thresholds", type=Path, default=None)
    parser.add_argument("--no-warn", action="store_true", help="suppress calibration warning")
    parser.add_argument(
        "--structural-only", action="store_true",
        help="score structure and do NOT apply the review-panel gate. The choice is "
             "recorded in the output; it does not hide.")
    args = parser.parse_args()

    try:
        opportunity_path = _resolve_opportunity(args.opportunity)
    except FileNotFoundError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 2

    rubric_path = _resolve_rubric(args.rubric)
    # Validate the rubric parses before any dimension is scored — `run_structural` does
    # the same. Until this line the loader was imported here and never called, so a
    # malformed rubric reached `check_spec_smells` and produced a score from nothing.
    load_rubric(rubric_path)
    thresholds_path, thresholds_origin = _resolve_thresholds(
        args.thresholds, opportunity_path)
    bands = _parse_thresholds(thresholds_path)

    coverage = check_corner_coverage(opportunity_path)
    evidence = check_evidence_pointers(opportunity_path)
    # Resolved from the artifact, the same walk `_resolve_thresholds` performs:
    # cross-repo detection reads the project's routing table, and a scorer run from
    # elsewhere would otherwise find no table and report the blast radius unchecked.
    completeness = check_opportunity_completeness(
        opportunity_path, project_root=_find_project_root(opportunity_path)
    )
    smells = check_spec_smells(opportunity_path, rubric_path)

    # Per-dimension scores (0-100)
    cc_score = 100.0 * coverage["corners_populated"] / coverage["corners_total"]

    # An opportunity with zero code pointers is not automatically weak: a `live-test`
    # finding is carried by runtime observations, which are not disk-verifiable. The
    # empty-corner and mode-contract gates are what catch a genuinely evidence-free
    # opportunity, so this dimension does not double-penalise.
    # A dimension that examined nothing must not report that everything resolved.
    # `total == 0` used to award a flat 100.0, so an opportunity citing NOTHING scored
    # perfectly on the 0.30-weight dimension whose entire job is "does the evidence
    # resolve?". Measured 2026-09-16 across a 57-opportunity registry: it never fired
    # there — every real discovery cited something — so this closes a latent hole, not
    # an active one. The hole matters because DISCOVER now answers "is it possible /
    # which technique / where in the system", and that answer can be written entirely
    # as prose about an external technique, with no pointer anywhere.
    #
    # The runtime-only case is deliberately left at 100.0: an HTTP observation is not
    # re-verifiable on disk (see check_evidence_pointers' module docstring), so no code
    # pointer could have failed. That is a real distinction, not a loophole.
    if evidence["evidence_total"] == 0:
        ep_score = 0.0
    elif evidence["total"] == 0:
        ep_score = 100.0
    else:
        ep_score = 100.0 * evidence["verified"] / evidence["total"]

    oc_score = 100.0 * completeness["found"] / completeness["total_required"]
    sr_score = max(0.0, 100.0 + smells.total_penalty)  # penalty is negative

    weights = {
        "corner_coverage": 0.30,
        "evidence_pointers": 0.30,
        "opportunity_completeness": 0.25,
        "structural_risk": 0.15,
    }
    weighted = (
        weights["corner_coverage"] * cc_score
        + weights["evidence_pointers"] * ep_score
        + weights["opportunity_completeness"] * oc_score
        + weights["structural_risk"] * sr_score
    )

    hard_caps_triggered: list[str] = []
    cap_value: float = 100.0

    for empty in coverage["empty_corners"]:
        hard_caps_triggered.append(f"empty_corner_{empty}")
        cap_value = min(cap_value, 49.0)

    if evidence["fabricated"] > 0:
        hard_caps_triggered.append("fabricated_evidence")
        cap_value = min(cap_value, 49.0)

    # Citing nothing is not the same as citing correctly. Without this cap an
    # opportunity with zero pointers of either class reached the same verdict band as
    # one whose every pointer resolved, because `verified / total` is vacuous at zero.
    if evidence["evidence_total"] == 0:
        hard_caps_triggered.append("no_evidence_cited")
        cap_value = min(cap_value, 49.0)

    if completeness["missing_mandatory"]:
        hard_caps_triggered.append("mandatory_section_missing")
        cap_value = min(cap_value, 70.0)

    # ADR is required only when the blast radius reaches beyond the opportunity's own
    # repo. A repo-local fix carries no cap; a cross-repo change without a recorded
    # decision does.
    if completeness["adr_missing"]:
        hard_caps_triggered.append("no_adr_on_cross_repo_change")
        cap_value = min(cap_value, 70.0)

    if smells.total_hits >= 20:
        hard_caps_triggered.append("soft_floor_smell_density_high")
        cap_value = min(cap_value, 89.0)

    if evidence["evidence_total"] > 0 and evidence["evidence_density_per_200w"] < 1.0:
        hard_caps_triggered.append("soft_floor_evidence_density_low")
        cap_value = min(cap_value, 89.0)

    final_score = min(weighted, cap_value)
    verdict = _verdict_for(final_score, bands)

    # The panel gates the VERDICT, never the score. `rules/review-panel.txt`: a script
    # scores structure, a panel judges whether the evidence supports the conclusion.
    # Both tokens below already exist in `rules/verdict-bands.txt` — a state the
    # vocabulary already has must not get a new name.
    #
    # The panel may only ever DOWNGRADE a passing verdict. A structural INVALID wins
    # outright: `fabricated_evidence` is the one unrecoverable defect in this cycle,
    # and letting "nobody has reviewed this yet" overwrite it would turn the new gate
    # into a way of hiding the oldest one. Caught by this file's own tests, which went
    # from exit 1 to exit 0 on a fabricated pointer.
    slug = opportunity_path.stem.replace("-opportunity", "")
    if args.structural_only:
        panel = {"status": "not_consulted",
                 "detail": "--structural-only: the panel gate was not applied. This "
                           "verdict describes STRUCTURE and does not say the document "
                           "may advance"}
        panel_gate = "skipped: --structural-only"
    else:
        panel = _panel_state(_find_project_root(opportunity_path), slug)
        panel_gate = "applied"
    if args.structural_only or verdict == "INVALID":
        pass
    elif panel["status"] == "returned":
        # The panel judged it and did not carry it: editing can lift this.
        verdict = "NEEDS_REVISION"
    elif panel["status"] == "no_record":
        # Structure is complete and the judgement has not been made. Neither a failure
        # nor a pass, and NOT an impediment — the panel simply has not sat yet, and the
        # action is to convene it.
        verdict = "AWAITING_REVIEW"
    elif panel["status"] not in ("approved", "not_gated"):
        # A panel that could not convene, or a record that does not check out: held on
        # a material impediment. Distinct from the line above, because "nobody has
        # reviewed it yet" and "nobody CAN review it here" take different actions.
        verdict = "ITEM_IN_FLIGHT"

    reasons = {
        "corner_coverage": {
            "contributors": coverage["contributors"],
            "detractors": coverage["detractors"],
        },
        "evidence_pointers": {
            "contributors": evidence["contributors"],
            "detractors": evidence["detractors"],
        },
        "opportunity_completeness": {
            "contributors": completeness["contributors"],
            "detractors": completeness["detractors"],
        },
        "structural_risk": {
            "contributors": [f"{smells.total_hits} smell hits across categories"]
            if smells.total_hits == 0
            else [],
            "detractors": [
                f"{cat}: {count} hits"
                for cat, count in sorted(smells.by_category.items(), key=lambda x: -x[1])[:3]
            ],
        },
    }

    sub_reports: dict[str, Any] = {
        "corner_coverage": coverage,
        "evidence_pointers": evidence,
        "opportunity_completeness": completeness,
        "structural_risk": {
            "total_hits": smells.total_hits,
            "by_category": smells.by_category,
            "total_penalty": smells.total_penalty,
        },
    }

    out = {
        "opportunity_slug": opportunity_path.stem.replace("-opportunity", ""),
        "opportunity_path": str(opportunity_path),
        # Which bands produced the verdict below, and from where. A scorer whose
        # own cutoffs are unreported is a verdict nobody can check.
        "thresholds_path": str(thresholds_path),
        "thresholds_origin": thresholds_origin,
        "scored_at": datetime.now(timezone.utc).isoformat(),
        "corner_coverage_score": round(cc_score, 1),
        "evidence_pointers_score": round(ep_score, 1),
        "opportunity_completeness_score": round(oc_score, 1),
        "structural_risk_score": round(sr_score, 1),
        "active_dimensions": [
            "corner_coverage",
            "evidence_pointers",
            "opportunity_completeness",
            "structural_risk",
        ],
        "weight_normalization_factor": 1.0,
        "weighted_avg": round(weighted, 1),
        "hard_caps_triggered": hard_caps_triggered,
        "final_score_after_caps": round(final_score, 1),
        "panel": panel,
        "panel_gate": panel_gate,
        "verdict": verdict,
        "calibration": {
            "status": "PROVISIONAL_v1",
            "holdout_count": 0,
            "holdout_target": 30,
            "kappa_measured": False,
        },
        "reasons": reasons,
        "sub_reports": sub_reports,
    }

    print(json.dumps(out, indent=2))

    if not args.no_warn and out["calibration"]["status"] == "PROVISIONAL_v1":
        print(
            "WARN: PROVISIONAL_v1 calibration — score bands are SOTA defaults, not yet "
            "calibrated against project holdout.",
            file=sys.stderr,
        )

    # Every verdict this scorer can reach has a code. NEEDS_REVISION, AWAITING_REVIEW and
    # ITEM_IN_FLIGHT used to fall through to 0, so a caller reading the exit code — which
    # is what a chain does — could not tell an opportunity nobody had reviewed from one
    # that passed. The verdict was in the JSON the whole time; the code said SHIPPABLE.
    return {
        "INVALID": 1,
        "NON_SHIPPABLE": 3,
        "NEEDS_REVISION": 4,
        "AWAITING_REVIEW": 5,
        "ITEM_IN_FLIGHT": 6,
    }.get(verdict, 0)


if __name__ == "__main__":
    sys.exit(main())
