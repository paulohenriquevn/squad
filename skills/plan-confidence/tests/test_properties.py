"""L2 — Property-based tests with hypothesis.

Invariants that MUST hold for ALL inputs, not just the cases we thought of.
Hypothesis generates hundreds of inputs per property and tries to find one
that breaks the invariant.
"""
from __future__ import annotations

import json
import tempfile
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from check_coverage_matrix import check_coverage_matrix  # noqa: E402 — post-bootstrap import
from check_spec_smells import check_spec_smells  # noqa: E402 — post-bootstrap import
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from run_structural import (  # noqa: E402 — post-bootstrap import
    SOTA_WEIGHTS,
    renormalize_weights,
    run_structural,
)

SKILL_ROOT = Path(__file__).parent.parent
RUBRIC = SKILL_ROOT / "templates" / "rubric-v1.md"
THRESHOLDS = SKILL_ROOT.parent.parent / "rules" / "plan-confidence-thresholds.txt"


# ---------------------------------------------------------------------------
# Invariant 1: renormalize_weights ALWAYS sums to 1.0 for ANY active dimension subset
# ---------------------------------------------------------------------------

@given(
    st.sets(
        st.sampled_from(list(SOTA_WEIGHTS.keys())),
        min_size=1,
        max_size=4,
    )
)
def test_renormalize_weights_always_sums_to_one(dims: set[str]) -> None:
    weights = renormalize_weights(sorted(dims))
    assert abs(sum(weights.values()) - 1.0) < 1e-9, (
        f"weights {weights} for dims {dims} don't sum to 1.0"
    )


@given(
    st.sets(
        st.sampled_from(list(SOTA_WEIGHTS.keys())),
        min_size=1,
        max_size=4,
    )
)
def test_renormalize_weights_all_positive(dims: set[str]) -> None:
    weights = renormalize_weights(sorted(dims))
    for d, w in weights.items():
        assert w > 0, f"weight {w} for {d} is non-positive"


# ---------------------------------------------------------------------------
# Invariant 2: spec smells produce non-positive total penalty (penalty IS negative)
# ---------------------------------------------------------------------------

# Generate arbitrary markdown content
markdown_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd", "Zs"),
        whitelist_characters="\n.,!?-",
    ),
    min_size=10,
    max_size=2000,
)


@given(content=markdown_text)
@settings(
    max_examples=50,
    deadline=None,  # see the note above: the deadline measured machine load, not the code
    suppress_health_check=[HealthCheck.too_slow],
)
def test_smell_total_penalty_always_non_positive(content: str) -> None:
    with example_dir() as workdir:
        plan = workdir / "fuzz.md"
        plan.write_text(content, encoding="utf-8")
        report = check_spec_smells(plan, RUBRIC)
        assert report.total_penalty <= 0, f"penalty {report.total_penalty} positive"
        assert report.total_hits >= 0
        assert sum(report.by_category.values()) == report.total_hits


# ---------------------------------------------------------------------------
# Invariant 3: coverage_ratio always in [0, 1] for any plan with Coverage Matrix
# ---------------------------------------------------------------------------

@given(
    n_gaps=st.integers(min_value=0, max_value=20),
    n_mapped=st.integers(min_value=0, max_value=20),
)
@settings(
    max_examples=50,
    deadline=None,  # see the note above: the deadline measured machine load, not the code
)
def test_coverage_ratio_always_in_range(n_gaps: int, n_mapped: int) -> None:
    # Build a synthetic plan with n_gaps rows, n_mapped of which have task refs
    n_mapped = min(n_mapped, n_gaps)
    rows = []
    for i in range(n_gaps):
        if i < n_mapped:
            rows.append(f"| {i + 1} | gap {i} | T1.{i + 1} | done |")
        else:
            rows.append(f"| {i + 1} | gap {i} |  | unmapped |")
    plan_text = (
        "# Plan\n\n## Coverage Matrix\n\n"
        "| # | Gap | Task(s) | Resolution |\n"
        "|---|-----|---------|------------|\n"
        + "\n".join(rows)
        + "\n"
    )
    with example_dir() as workdir:
        plan = workdir / "synth.md"
        plan.write_text(plan_text, encoding="utf-8")
        report = check_coverage_matrix(plan)
        assert 0.0 <= report.coverage_ratio <= 1.0, f"ratio {report.coverage_ratio} OOR"


# ---------------------------------------------------------------------------
# Invariant 4: end-to-end score always in [0, 100], verdict in allowed set, JSON valid
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Why these tests do not take pytest's `tmp_path`
#
# A function-scoped fixture runs ONCE for a `@given` test and is shared by every
# example Hypothesis generates — pytest's own health check says so, and the four
# tests below used to suppress that warning rather than heed it. The examples were
# therefore not independent of each other, which is the property the whole file
# exists to assert about the code under test.
#
# `example_dir()` gives each example its own directory, so an example cannot see what
# an earlier one wrote.
#
# WHAT WAS MEASURED, INCLUDING WHAT IS STILL OPEN
#
#   before   2 failures in 15 runs   (~13%)
#   after    1 failure in 85 runs    (~1.2%)
#
# THE RESIDUAL WAS FOUND ON 2026-09-09, AND IT WAS NOT SHARED STATE
#
# 104 runs, eight at a time, produced 21 failures — and every single one of them was
# Hypothesis's DEADLINE, not an assertion:
#
#   "Unreliable test timings! On an initial run, this test took 257.20ms, which
#    exceeded the deadline of 200.00ms, but on a subsequent run it took 180.23ms"
#
# Under load an example crosses the 200 ms default; on the confirming re-run it does
# not, and Hypothesis reports `FlakyFailure`. That explains every symptom recorded
# above — it failed in a parallel suite run, passed in isolation, and the reported
# counter-example did not reproduce alone, because the input was never the problem.
#
# `suppress_health_check=[HealthCheck.too_slow]` does NOT cover this. The health check
# and the deadline are different mechanisms, and only the first was suppressed.
#
# These tests assert PROPERTIES, never latency. A wall-clock budget on them measures
# how busy the machine is, which is not a property of the code under test — so the
# deadline is off, deliberately, rather than raised to a number that would fail again
# on a busier host.
#
# Both original failures were in `test_end_to_end_score_invariants` and
# `test_smell_idempotent`, and NEITHER reproduced when its reported counter-example
# was replayed alone — the inputs pass in isolation, which is what pointed at shared
# state rather than at a bug in the code under test.
#
# WHERE THIS STANDS NOW
#
# The paragraph that used to close this section said the residual "was not captured"
# and was "NOT a fix that was proven". That was written BEFORE the 2026-09-09
# measurement above, and the section it sat under now identifies the cause precisely:
# 104 runs produced 21 failures and every one was Hypothesis's deadline, never an
# assertion. `deadline=None` on both decorators is the fix for that, and it is not a
# mitigation — a wall-clock budget is not a property of the code under test, so there
# is no number that would be correct here.
#
# What remains open is only this: the ONE failure in 85 predates the deadline finding
# and was never captured, so nothing proves it was the same cause. If an assertion here
# ever fails — an assertion, not a `FlakyFailure` — capture the output rather than
# re-running until it passes. The two are distinguishable in the report, which is the
# whole reason the distinction is written down.
# ---------------------------------------------------------------------------

@contextmanager
def example_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


VALID_VERDICTS = {"SHIPPABLE", "SHIPPABLE_WITH_CAVEATS", "NON_SHIPPABLE", "INVALID"}


@given(
    n_gaps=st.integers(min_value=1, max_value=15),
    n_mapped=st.integers(min_value=0, max_value=15),
    n_adrs=st.integers(min_value=0, max_value=10),
)
@settings(
    max_examples=30,
    deadline=None,  # see the note above: the deadline measured machine load, not the code
    suppress_health_check=[HealthCheck.too_slow],
)
def test_end_to_end_score_invariants(
    n_gaps: int, n_mapped: int, n_adrs: int
) -> None:
    n_mapped = min(n_mapped, n_gaps)

    adr_section = ""
    for i in range(n_adrs):
        adr_section += (
            f"### D{i + 1} — toy\n"
            "- Decisão: x\n"
            "- Rationale: alternativa rejeitada y\n"
            "- Consequências: z\n\n"
        )

    rows = []
    for i in range(n_gaps):
        if i < n_mapped:
            rows.append(f"| {i + 1} | gap {i} | T1.{i + 1} | done |")
        else:
            rows.append(f"| {i + 1} | gap {i} |  | unmapped |")

    plan_text = (
        "# Plan\n\n## ADRs\n\n"
        + adr_section
        + "\n## Coverage Matrix\n\n"
        "| # | Gap | Task(s) | Resolution |\n"
        "|---|-----|---------|------------|\n"
        + "\n".join(rows)
        + "\n"
    )
    with example_dir() as workdir:
        plan = workdir / "synth.md"
        plan.write_text(plan_text, encoding="utf-8")

        report = run_structural(plan, RUBRIC, THRESHOLDS, structural_only=True)
        # Score range
        assert 0.0 <= report.final_score_after_caps <= 100.0
        assert 0.0 <= report.completeness_score <= 100.0
        assert 0.0 <= report.structural_risk_score <= 100.0
        # Verdict in allowed set
        assert report.verdict in VALID_VERDICTS
        # JSON serialization works
        d = asdict(report)
        d["reasons"] = {k: [asdict(m) for m in v] for k, v in report.reasons.items()}
        json.dumps(d)  # raises if not serializable
        # If verdict is INVALID, must have hard cap OR composite < 50
        if report.verdict == "INVALID" and not report.hard_caps_triggered:
            assert report.final_score_after_caps < 50, (
                f"INVALID without hard cap requires score<50, got {report.final_score_after_caps}"
            )


# ---------------------------------------------------------------------------
# Invariant 5: hard caps are MONOTONIC — adding more violations never improves score
# ---------------------------------------------------------------------------

def test_hard_cap_monotonicity(tmp_path: Path) -> None:
    """Plan with coverage cap should never score higher than same plan without cap."""
    # Plan A: coverage 100%, no cap
    plan_a = tmp_path / "a.md"
    plan_a.write_text(
        "# Plan\n\n## ADRs\n\n### D1 — toy\n- Rationale: alternativa rejeitada.\n\n"
        "## Coverage Matrix\n\n"
        "| # | Gap | Task(s) | Resolution |\n"
        "|---|-----|---------|------------|\n"
        "| 1 | gap | T1.1 | done |\n",
        encoding="utf-8",
    )
    # Plan B: same but one unmapped gap added (cap fires)
    plan_b = tmp_path / "b.md"
    plan_b.write_text(
        "# Plan\n\n## ADRs\n\n### D1 — toy\n- Rationale: alternativa rejeitada.\n\n"
        "## Coverage Matrix\n\n"
        "| # | Gap | Task(s) | Resolution |\n"
        "|---|-----|---------|------------|\n"
        "| 1 | gap | T1.1 | done |\n"
        "| 2 | bad |  | unmapped |\n",
        encoding="utf-8",
    )
    report_a = run_structural(plan_a, RUBRIC, THRESHOLDS, structural_only=True)
    report_b = run_structural(plan_b, RUBRIC, THRESHOLDS, structural_only=True)
    assert report_b.final_score_after_caps <= report_a.final_score_after_caps, (
        f"adding cap raised score: a={report_a.final_score_after_caps} b={report_b.final_score_after_caps}"
    )
    assert "coverage_lt_100" in report_b.hard_caps_triggered
    assert "coverage_lt_100" not in report_a.hard_caps_triggered


# ---------------------------------------------------------------------------
# Invariant 6: idempotency — same input ALWAYS produces same output
# ---------------------------------------------------------------------------

@given(content=markdown_text)
@settings(
    max_examples=30,
    deadline=None,  # see the note above: the deadline measured machine load, not the code
    suppress_health_check=[HealthCheck.too_slow],
)
def test_smell_idempotent(content: str) -> None:
    with example_dir() as workdir:
        plan = workdir / "i.md"
        plan.write_text(content, encoding="utf-8")
        r1 = check_spec_smells(plan, RUBRIC)
        r2 = check_spec_smells(plan, RUBRIC)
        assert r1 == r2
