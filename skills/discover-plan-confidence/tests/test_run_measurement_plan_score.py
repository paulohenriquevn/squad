"""The citation dimension must not reward a plan that cited nothing.

`run_measurement_plan_score` awarded `reference_citations` a flat 100.0 when
`check_measurement_targets` resolved zero targets — 0.30 of the weighted score — and no
hard cap fired for it. A measurement plan whose `## Measurement targets` section named no
path and no live URL therefore scored exactly like one whose every citation resolved.
"""
from __future__ import annotations

from pathlib import Path


def test_a_plan_citing_nothing_scores_zero_on_the_citation_dimension(tmp_path) -> None:
    """`total == 0` was awarded a flat 100.0 — 0.30 of the weighted score.

    No cap fired for it either, so a measurement plan whose `## Measurement targets`
    section named no path and no live URL was rewarded exactly like one whose every
    citation resolved. The dimension is called reference_citations; zero citations is the
    worst case it can measure, not the best.
    """
    import run_measurement_plan_score as scorer

    empty = {"total": 0, "verified": 0, "fabricated": 0, "live_targets": []}
    assert scorer._citation_score(empty) == 0.0


def test_a_plan_measuring_only_a_live_system_still_scores_full(tmp_path) -> None:
    """The one honest 100: a plan measuring a running system cites hosts, not paths."""
    import run_measurement_plan_score as scorer

    live_only = {"total": 0, "verified": 0, "fabricated": 0,
                 "live_targets": ["app.example.test"]}
    assert scorer._citation_score(live_only) == 100.0


# ── gate G-L: measured by the checker, consumed by no cap ────────────────────
#
# `check_measurement_targets` computes `undeclared_live_hosts` and its docstring
# states the consequence: "A plan naming a live URL that no domain declares is
# planning a probe the cycle refuses to run (cycle-discover.md, gate G-L). Catching
# it here means the refusal lands while the plan is cheap to change." The scorer that
# owns the caps never read the key — so the refusal DID land, at `/discover-execute`,
# after the plan was written, reviewed and approved.


def _scored(tmp_path: Path, declared: str) -> dict:
    """Run the scorer over a plan probing `app.example.com`."""
    import json
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[3]
    script = root / "skills" / "discover-plan-confidence" / "scripts" / "run_measurement_plan_score.py"

    (tmp_path / ".git").touch()
    (tmp_path / "rules").mkdir(parents=True, exist_ok=True)
    (tmp_path / "rules" / "live-target.txt").write_text(declared, encoding="utf-8")
    plans = tmp_path / "plans"
    plans.mkdir(parents=True, exist_ok=True)
    plan = plans / "p.md"
    plan.write_text(
        "# Measurement plan\n\n## Measurement targets\n\n"
        "Probe `https://app.example.com/api/traces` and record the status.\n",
        encoding="utf-8")

    done = subprocess.run([sys.executable, str(script), str(plan), "--no-warn"],
                          cwd=tmp_path, capture_output=True, text=True,
                          timeout=180, check=False)
    assert "{" in done.stdout, done.stdout + done.stderr
    return json.loads(done.stdout[done.stdout.index("{"):])


def test_an_undeclared_live_host_caps_the_plan(tmp_path: Path) -> None:
    report = _scored(tmp_path, "# nothing declared\n")

    assert "undeclared_live_host" in report.get("hard_caps_triggered", []), report
    assert report["final_score_after_caps"] <= 70


def test_a_declared_live_host_does_not_cap(tmp_path: Path) -> None:
    report = _scored(tmp_path, "target = https://app.example.com\n")

    assert "undeclared_live_host" not in report.get("hard_caps_triggered", []), report
