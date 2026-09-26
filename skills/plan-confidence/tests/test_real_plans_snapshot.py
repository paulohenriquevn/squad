"""L1 — Snapshot regression tests over real plans in the project.

Pins the expected verdict + score band for each real plan to detect silent
behavior drift. If a detector change moves a plan into a different band
(e.g., SHIPPABLE -> NON_SHIPPABLE), this test fails LOUDLY and forces
an explicit decision: either accept the new behavior (update snapshot) or
revert the detector change.

We pin BAND (not exact score) because exact scores can shift slightly with
detector refinements. Bands are the semantic gate.

WHICH VERDICT THIS FILE PINS, AND WHY IT IS NOT THE ONE THE CLI PRINTS
----------------------------------------------------------------------
These snapshots pin the STRUCTURAL verdict — what `run_structural()` returns for
the plan alone. `run_structural.py`'s `main()` then merges the code-quality
verdict over it and prints the composed one, because `cycle-code-quality.md` § 1
requires a plan's verdict to carry the quality state of the code it targets.

So the CLI and this suite report different quantities, and that is by design. A
band read off the CLI output cannot be pinned here: the code-quality cap reflects
the repository, not the plan, so it moves with commits that touch neither. Two
plans of different quality can print the same capped number on the same day, and
one plan can print different numbers on different days (kit#56).

When the merge moves a value, the payload now says so: `verdict_before_code_quality`
and `score_before_code_quality` carry what was composed FROM, and appear only when
the composition actually changed it. Those are the fields to compare against a
band pinned here.
"""
from __future__ import annotations

from pathlib import Path

import pytest

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from run_structural import run_structural  # noqa: E402 — post-bootstrap import

SKILL_ROOT = Path(__file__).parent.parent
PROJECT_ROOT = SKILL_ROOT.parent.parent.parent
PLANS_DIR = SKILL_ROOT.parent.parent / "records" / "plans"
COMPLETED_DIR = PLANS_DIR / "completed"
RUBRIC = SKILL_ROOT / "templates" / "rubric-v1.md"
THRESHOLDS = SKILL_ROOT.parent.parent / "rules" / "plan-confidence-thresholds.txt"


FIXTURES_DIR = SKILL_ROOT / "fixtures"


#: What makes a markdown file a PLAN rather than a note somebody left in the
#: directory. The declaration gate below scoped itself to plans "with a Coverage
#: Matrix" in prose and selected with a bare `glob("*.md")`, so the two never
#: agreed; a probe file was enough to trip it.
_COVERAGE_MATRIX_HEADING = "coverage matrix"


def _eligible_plans(plans_dir: Path) -> set[str]:
    """The plan files in `plans_dir` that carry a Coverage Matrix.

    Returns the empty set for a directory that does not exist. That is not a
    failure and it is not a pass either — it means there was nothing to examine,
    and the CALLER has to say so out loud rather than assert emptiness against
    emptiness. `records/plans/` is gitignored and consumer-owned, so in the kit's
    own checkout the answer is always empty.
    """
    if not plans_dir.is_dir():
        return set()
    eligible = set()
    for path in plans_dir.glob("*.md"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            # An unreadable file is not evidence that it is not a plan. Treat it
            # as eligible so the gate errs toward demanding a declaration.
            eligible.add(path.name)
            continue
        if _COVERAGE_MATRIX_HEADING in text.lower():
            eligible.add(path.name)
    return eligible


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

    report = run_structural(plan_path, RUBRIC, THRESHOLDS, structural_only=True)

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


def test_a_plan_without_a_coverage_matrix_is_not_eligible(tmp_path: Path) -> None:
    """The declaration gate scopes itself to plans that carry a Coverage Matrix.

    It said so in prose and selected on `glob("*.md")`, so any markdown dropped
    into the directory — a one-line note — was demanded to be pinned or declared.
    """
    (tmp_path / "note.md").write_text("just a note someone left here\n", encoding="utf-8")
    (tmp_path / "real-plan.md").write_text(
        "# Plan\n\n## Coverage Matrix\n\n| requirement | test |\n", encoding="utf-8"
    )
    assert _eligible_plans(tmp_path) == {"real-plan.md"}


def test_eligible_plans_is_empty_when_the_directory_is_absent(tmp_path: Path) -> None:
    """An absent consumer directory yields nothing, and the CALLER must say so.

    `records/plans/` is gitignored and consumer-owned, so in the kit's own
    checkout it does not exist. `glob` on a missing directory returns empty
    without raising, which made the declaration gate assert the empty set
    against the empty set — green, forever, having examined nothing.
    """
    assert _eligible_plans(tmp_path / "nope") == set()


def test_snapshots_cover_active_plans_with_matrix() -> None:
    """Every ACTIVE consumer plan carrying a Coverage Matrix is pinned or declared.

    Two things were wrong with this gate, and they hid each other.

    It selected on `glob("*.md")` while its own sentence scoped it to plans with a
    Coverage Matrix, so any markdown in the directory was demanded to be declared.
    And `PLANS_DIR` is `records/plans/` — gitignored, consumer-owned, and ABSENT
    from the kit's own checkout. `glob` on a missing directory yields nothing
    without raising, so `eligible` was empty, `uncovered` was empty, and the
    assertion compared the empty set to itself. **This gate could not fail here.**

    That is the same defect kit#30 reported about the parametrised half of this
    file, surviving in the half kit#30 described as working ("This one fires, and
    it fired today"). It fired in a consumer, where the directory exists.

    The kit's own committed corpus is held by `test_every_committed_fixture_is_pinned`
    instead — that one has files to examine here, and is where this file's floor lives.
    """
    skipped_known = {
        "l2-wiring-keep-wire-followup.md",
        "memory-write-redesign-followup.md",
        "observability-cache-maturity-baseline.md",
        "observability-cache-maturity-edge-cases.md",
        # Working plan for the patterns-consumption-gate feature itself (gitignored
        # under records/plans/); not a regression-snapshot fixture.
        "patterns-consumption-gate-plan.md",
    }
    if not PLANS_DIR.is_dir():
        pytest.skip(
            f"no consumer plan directory at {PLANS_DIR}; this gate governs a "
            f"consumer's records/plans/, which the kit does not ship. The kit's own "
            f"corpus is covered by test_every_committed_fixture_is_pinned."
        )
    uncovered = _eligible_plans(PLANS_DIR) - skipped_known - set(SNAPSHOTS)
    assert not uncovered, (
        f"new active plans missing snapshot: {uncovered}. Add them to SNAPSHOTS or skipped_known."
    )


def test_score_determinism_real_plans() -> None:
    """Real plans: same input -> same output across multiple invocations."""
    for filename in SNAPSHOTS:
        plan_path = _resolve_plan(filename)
        if plan_path is None:
            continue
        r1 = run_structural(plan_path, RUBRIC, THRESHOLDS, structural_only=True)
        r2 = run_structural(plan_path, RUBRIC, THRESHOLDS, structural_only=True)
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
