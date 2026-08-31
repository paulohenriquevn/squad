"""NEEDS_SPLIT: a reviewer's judgement the scorer transports, never infers.

The verdict was in SKILL.md's table and in no code path. An item that needed
splitting came out `BLOCKED`, which sends the reviewer to close gaps that no amount
of writing can close — the gaps are a consequence of two items sharing one brief.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from score_alignment import score_alignment


def _brief(tmp_path: Path, extra: str = "") -> Path:
    path = tmp_path / "brief.md"
    path.write_text(f"# Brief\n\n## Problem\n\nSomething measurable.\n{extra}", encoding="utf-8")
    return path


def test_a_marked_brief_reports_needs_split(tmp_path: Path) -> None:
    report = score_alignment(_brief(tmp_path, "\n<!-- verdict: NEEDS_SPLIT -->\n"))
    assert report.verdict == "NEEDS_SPLIT"


def test_the_marker_wins_over_a_low_score(tmp_path: Path) -> None:
    """A split item scores low BECAUSE it is two items. Reporting the score hides why."""
    report = score_alignment(_brief(tmp_path, "\n<!-- verdict: NEEDS_SPLIT -->\n"))
    assert report.meets_machine_threshold is False
    assert report.verdict == "NEEDS_SPLIT"


def test_an_unmarked_brief_is_unaffected(tmp_path: Path) -> None:
    report = score_alignment(_brief(tmp_path))
    assert report.needs_split is False
    assert report.verdict == "BLOCKED"


def test_a_reason_is_carried_through(tmp_path: Path) -> None:
    marker = "\n<!-- verdict: NEEDS_SPLIT: ingest and query are separate subsystems -->\n"
    report = score_alignment(_brief(tmp_path, marker))
    assert "separate subsystems" in report.split_reason


def test_a_marker_without_a_reason_leaves_it_empty(tmp_path: Path) -> None:
    report = score_alignment(_brief(tmp_path, "\n<!-- verdict: NEEDS_SPLIT -->\n"))
    assert report.split_reason == ""


def test_a_split_brief_never_counts_as_aligned(tmp_path: Path) -> None:
    report = score_alignment(_brief(tmp_path, "\n<!-- verdict: NEEDS_SPLIT -->\n"))
    assert report.aligned is False


@pytest.mark.parametrize("flag", [[], ["--machine-only"]])
def test_the_cli_refuses_on_either_flag(tmp_path: Path, flag: list[str]) -> None:
    """`--machine-only` lets the agent iterate; a split is what iteration cannot fix."""
    from score_alignment import main

    brief = _brief(tmp_path, "\n<!-- verdict: NEEDS_SPLIT -->\n")
    assert main([str(brief), *flag]) != 0
