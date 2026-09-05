"""L1 — Snapshot regression tests over real plans in the project.

Pins the expected verdict + score band for each real plan to detect silent
behavior drift. If a detector change moves a plan into a different band
(e.g., SHIPPABLE -> NON_SHIPPABLE), this test fails LOUDLY and forces
an explicit decision: either accept the new behavior (update snapshot) or
revert the detector change.

We pin BAND (not exact score) because exact scores can shift slightly with
detector refinements. Bands are the semantic gate.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from run_structural import run_structural  # noqa: E402

SKILL_ROOT = Path(__file__).parent.parent
PROJECT_ROOT = SKILL_ROOT.parent.parent.parent
PLANS_DIR = SKILL_ROOT.parent.parent / "records" / "plans"
COMPLETED_DIR = PLANS_DIR / "completed"
RUBRIC = SKILL_ROOT / "templates" / "rubric-v1.md"
THRESHOLDS = SKILL_ROOT.parent.parent / "rules" / "plan-confidence-thresholds.txt"


FIXTURES_DIR = SKILL_ROOT / "fixtures"


def _resolve_plan(filename: str) -> Path | None:
    """The kit's own corpus first, then a consumer's plans if it has any.

    Order matters. `records/plans/` is gitignored and consumer-owned, so a suite
    that resolves there FIRST is a suite whose result depends on a directory the
    kit does not ship — which is how nine pinned plans became nine silent skips.
    """
    for candidate in (FIXTURES_DIR / filename, PLANS_DIR / filename,
                      COMPLETED_DIR / filename):
        if candidate.exists():
            return candidate
    return None


# Pinned snapshots — band + expected hard caps. Scores may shift ±5; bands MUST NOT.
# Covers diverse plan styles: active, completed, with/without out-of-scope items.
#: The pinned corpus. These four live in `skills/plan-confidence/fixtures/`, are
#: versioned with the kit, and were scored on 2026-09-05 to derive the bands
#: below. Scores may drift +/-5 with detector refinements; BANDS MUST NOT.
#:
#: This replaced nine plans under `records/plans/` — a directory `.gitignore`
#: excludes and `test_kit_is_read_only.py` declares consumer-owned. All nine were
#: absent, every case skipped, and the file reported green having compared
#: nothing (kit#30). One of the nine survives in a backup outside any repository;
#: eight were never versioned. A corpus that cannot be checked out is not a
#: corpus, whatever the dict says.
SNAPSHOTS: dict[str, dict[str, object]] = {
    # Structurally clean, no caps. The upper anchor: if a detector change drops
    # this out of SHIPPABLE, the change is wrong or the rubric moved.
    "good-plan.md": {
        "verdict_in": {"SHIPPABLE"},
        "score_min": 95,
        "expected_hard_caps_subset": set(),
    },
    # No TDD evidence. Lands mid-band: enough structure to ship, enough missing
    # to caveat. The interesting one — it is where a sloppy detector change shows
    # up first, by pushing it either way.
    "no-tdd-plan.md": {
        "verdict_in": {"SHIPPABLE_WITH_CAVEATS"},
        "score_min": 60,
        "score_max": 85,
        "expected_hard_caps_subset": set(),
    },
    # Weak imperatives ("should", "consider") instead of committed ones. Same
    # band as no-tdd by a different route, which is itself worth pinning: two
    # distinct defects must not collapse into one score.
    "weak-imperatives-plan.md": {
        "verdict_in": {"SHIPPABLE_WITH_CAVEATS"},
        "score_min": 60,
        "score_max": 85,
        "expected_hard_caps_subset": set(),
    },
    # The lower anchor. Missing coverage is a hard failure and must stay one.
    "missing-coverage-plan.md": {
        "verdict_in": {"INVALID", "NON_SHIPPABLE"},
        "score_min": 0,
        "score_max": 59,
        "expected_hard_caps_subset": set(),
    },
}

@pytest.mark.parametrize("plan_filename,expected", list(SNAPSHOTS.items()))
def test_real_plan_snapshot(plan_filename: str, expected: dict[str, object]) -> None:
    plan_path = _resolve_plan(plan_filename)
    if plan_path is None:
        pytest.skip(f"plan not found in plans/ or completed/: {plan_filename}")

    report = run_structural(plan_path, RUBRIC, THRESHOLDS)

    # Verdict band
    verdict_in = expected["verdict_in"]
    assert isinstance(verdict_in, set)
    assert report.verdict in verdict_in, (
        f"{plan_filename}: verdict drift — expected one of {verdict_in}, "
        f"got {report.verdict} (score={report.final_score_after_caps})"
    )

    # Score envelope
    if "score_min" in expected:
        score_min = expected["score_min"]
        assert isinstance(score_min, int | float)
        assert report.final_score_after_caps >= score_min, (
            f"{plan_filename}: score regression — got {report.final_score_after_caps} < {score_min}"
        )
    if "score_max" in expected:
        score_max = expected["score_max"]
        assert isinstance(score_max, int | float)
        assert report.final_score_after_caps <= score_max, (
            f"{plan_filename}: score regression — got {report.final_score_after_caps} > {score_max}"
        )

    # Hard caps subset
    expected_caps = expected["expected_hard_caps_subset"]
    assert isinstance(expected_caps, set)
    actual_caps = set(report.hard_caps_triggered)
    # Expected caps MUST be in actual; actual may have extras (we'll catch new ones via overlap)
    missing = expected_caps - actual_caps
    assert not missing, (
        f"{plan_filename}: expected hard caps {expected_caps} not in actual {actual_caps}"
    )


def test_snapshots_cover_active_plans_with_matrix() -> None:
    """Sanity: snapshots should cover every ACTIVE (non-completed) plan that has a Coverage Matrix."""
    skipped_known = {
        "l2-wiring-keep-wire-followup.md",
        "memory-write-redesign-followup.md",
        "observability-cache-maturity-baseline.md",
        "observability-cache-maturity-edge-cases.md",
        # Working plan for the patterns-consumption-gate feature itself (gitignored
        # under records/plans/); not a regression-snapshot fixture.
        "patterns-consumption-gate-plan.md",
    }
    snapshot_plans = set(SNAPSHOTS.keys())
    active_plans = {p.name for p in PLANS_DIR.glob("*.md") if p.is_file()}
    eligible = active_plans - skipped_known
    uncovered = eligible - snapshot_plans
    assert not uncovered, (
        f"new active plans missing snapshot: {uncovered}. Add them to SNAPSHOTS or skipped_known."
    )


def test_score_determinism_real_plans() -> None:
    """Real plans: same input -> same output across multiple invocations."""
    for filename in SNAPSHOTS:
        plan_path = _resolve_plan(filename)
        if plan_path is None:
            continue
        r1 = run_structural(plan_path, RUBRIC, THRESHOLDS)
        r2 = run_structural(plan_path, RUBRIC, THRESHOLDS)
        assert r1.final_score_after_caps == r2.final_score_after_caps, (
            f"{filename}: nondeterministic score {r1.final_score_after_caps} != {r2.final_score_after_caps}"
        )
        assert r1.verdict == r2.verdict
        assert r1.hard_caps_triggered == r2.hard_caps_triggered


def test_the_corpus_is_not_empty() -> None:
    """A snapshot suite that resolves nothing passes having compared nothing.

    That is the defect this file exists to catch, and it lived here: nine pinned
    plans under a gitignored directory, nine `pytest.skip`, one green file
    (kit#30). A skip is invisible in the default report — `-q` prints a dot for a
    pass and an `s` for a skip, and nobody reads the letter.

    So the floor is asserted directly. If the committed corpus stops resolving,
    this fails and names it, instead of the parametrised cases quietly emptying.
    """
    unresolved = [name for name in SNAPSHOTS if _resolve_plan(name) is None]
    assert not unresolved, (
        f"{len(unresolved)} of {len(SNAPSHOTS)} pinned plans do not resolve: "
        f"{unresolved}. The suite would report green having compared nothing — "
        f"the exact failure kit#30 reported. Fixtures live in {FIXTURES_DIR}."
    )


def test_every_committed_fixture_is_pinned() -> None:
    """A fixture nobody pinned is a fixture nobody scores.

    The dict is a list, and a list drifts from the directory it describes. The
    four fixtures existed here for weeks while this suite pinned nine plans
    elsewhere, and no test read any of them.
    """
    on_disk = {p.name for p in FIXTURES_DIR.glob("*.md")}
    unpinned = sorted(on_disk - set(SNAPSHOTS))
    assert not unpinned, (
        f"these fixtures are committed and pinned by nothing: {unpinned}. "
        f"Either pin the band it should hold, or delete it — an unscored fixture "
        f"is a file that looks like coverage."
    )
