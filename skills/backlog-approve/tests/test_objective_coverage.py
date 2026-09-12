"""What a registry cannot say about itself: which of its goals nothing serves.

Reading items answers "do I want each of these". It cannot answer "is anything I want
missing", because an item nobody wrote is invisible to a report rendered from items.
Every test here guards one of the three states the `traces_to` link makes visible.
"""
from __future__ import annotations

from pathlib import Path

import check_objective_coverage as cov

OBJECTIVES = """# Objectives — scope

## OBJ-1 — Tenants are isolated
metric: a tenant pod cannot reach an unapproved address
horizon: 2026-Q4
why: the platform protects itself and not the customer

## OBJ-2 — Self-host without our registry
metric: zero images pulled from our registry
horizon: 2026-Q4
why: the build path does it today
"""


def _project(tmp_path: Path, items: list[tuple[str, str]],
             objectives: str | None = OBJECTIVES) -> Path:
    blocks = []
    for item_id, traces in items:
        trace_line = f"traces_to: {traces}\n" if traces else ""
        blocks.append(f"## {item_id} — a title   [ ]\n\ndomain: api\nrepo: api\n"
                      f"{trace_line}status: triaged\n")
    (tmp_path / "BACKLOG.md").write_text(
        "# Backlog\n\n## Index\n\n(table)\n\n## Items\n\n" + "\n".join(blocks),
        encoding="utf-8")
    if objectives is not None:
        target = tmp_path / cov.OBJECTIVES_REL
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(objectives, encoding="utf-8")
    return tmp_path


# ── the three states the link makes visible ─────────────────────────────────

def test_an_objective_nothing_serves_is_the_gap(tmp_path):
    """The finding no amount of reading the items would ever produce."""
    result = cov.measure(_project(tmp_path, [("B-001", "OBJ-1")]))
    assert result.unserved == ["OBJ-2"]
    assert result.served["OBJ-1"] == ["B-001"]


def test_an_item_serving_no_objective_is_the_drift(tmp_path):
    result = cov.measure(_project(tmp_path, [("B-001", "OBJ-1"), ("B-002", "")]))
    assert result.untraced == ["B-002"]


def test_a_citation_to_a_missing_objective_is_the_rot(tmp_path):
    """Objective ids are never reused, so a dangling citation means the objective was
    withdrawn — and the item still claims to serve it."""
    result = cov.measure(_project(tmp_path, [("B-001", "OBJ-9")]))
    assert result.dangling == [("B-001", "OBJ-9")]
    assert result.untraced == []


def test_one_item_may_serve_two_objectives(tmp_path):
    result = cov.measure(_project(tmp_path, [("B-001", "OBJ-1, OBJ-2")]))
    assert result.unserved == []
    assert result.served["OBJ-1"] == ["B-001"] and result.served["OBJ-2"] == ["B-001"]


def test_a_fully_covered_registry_reports_nothing(tmp_path):
    result = cov.measure(_project(tmp_path, [("B-001", "OBJ-1"), ("B-002", "OBJ-2")]))
    assert not (result.unserved or result.untraced or result.dangling)


# ── the honest refusal ──────────────────────────────────────────────────────

def test_no_objectives_document_is_not_measured_rather_than_all_orphans(tmp_path):
    """A project that never ran `/brainstorm-objectives` has nothing to trace to.

    Reporting its items as orphans would invent a standard it never adopted — the
    ecosystem-wide rule that an inability to measure must not become a measurement,
    applied to the case that would otherwise produce the loudest false finding.
    """
    result = cov.measure(_project(tmp_path, [("B-001", ""), ("B-002", "")],
                                  objectives=None))
    assert result.measurable is False
    assert result.untraced == []
    assert result.items_total == 2
    assert cov.OBJECTIVES_REL in result.reason


def test_a_stub_objectives_document_says_which_shape_is_missing(tmp_path):
    result = cov.measure(_project(tmp_path, [("B-001", "")], objectives="# Objectives\n"))
    assert result.measurable is False
    assert "declares no `## OBJ-N` heading" in result.reason


def test_a_missing_registry_is_not_measured(tmp_path):
    assert cov.measure(tmp_path).measurable is False


# ── what the reader is shown ────────────────────────────────────────────────

def test_the_unmeasured_render_names_what_would_make_it_answerable(tmp_path):
    text = cov.render(cov.measure(_project(tmp_path, [("B-001", "")], objectives=None)))
    assert "NOT MEASURED" in text
    assert "/brainstorm-objectives" in text


def test_the_gap_is_marked_in_the_rendered_table(tmp_path):
    text = cov.render(cov.measure(_project(tmp_path, [("B-001", "OBJ-1")])))
    assert "GAP " in text
    assert "— nothing" in text


def test_exit_two_means_could_not_measure_never_nothing_wrong(tmp_path, monkeypatch, capsys):
    """A 0 here would have claimed a clean registry on a project with no objectives."""
    project = _project(tmp_path, [("B-001", "")], objectives=None)
    monkeypatch.setattr("sys.argv", ["check_objective_coverage.py", str(project)])
    assert cov.main() == 2


def test_exit_one_means_findings_and_zero_means_covered(tmp_path, monkeypatch):
    covered = _project(tmp_path, [("B-001", "OBJ-1"), ("B-002", "OBJ-2")])
    monkeypatch.setattr("sys.argv", ["check_objective_coverage.py", str(covered)])
    assert cov.main() == 0
