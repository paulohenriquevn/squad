"""A verdict scored against hidden cutoffs is a verdict nobody can check.

`DEFAULT_THRESHOLDS` looked only under `.claude/rules/`. In the kit's own checkout the
file is at `rules/plan-confidence-thresholds.txt`, so the path did not exist and line
359 silently substituted hardcoded bands — and nothing in the emitted report said
which source produced the verdict.

The consequence is not academic: a consumer that recalibrates its bands and keeps the
standalone layout is scored against the shipped cutoffs and told nothing. `squad.paths.
rules_dir` already owns this pair of directories; the fix is to ask it, and to record
the answer in the report.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "skills" / "plan-confidence" / "scripts"))
sys.path.insert(0, str(_ROOT))

import run_structural  # noqa: E402 — post-bootstrap import


def test_the_kits_own_thresholds_file_is_found() -> None:
    """It is at `rules/`, not `.claude/rules/`, and the scorer must see it."""
    assert run_structural.DEFAULT_THRESHOLDS.exists(), (
        f"{run_structural.DEFAULT_THRESHOLDS} does not exist, so every run in this "
        f"repository fell back to the built-in bands")


def test_the_report_records_which_source_the_bands_came_from(tmp_path: Path) -> None:
    plan = tmp_path / "a-plan.md"
    plan.write_text("# A plan\n\n## Coverage Matrix\n\nnothing here\n", encoding="utf-8")

    report = run_structural.run_structural(plan, structural_only=True)

    source = report.sub_reports.get("thresholds", {})
    assert source, "the report does not say where its verdict bands came from"
    assert "source" in source and source["source"], source
