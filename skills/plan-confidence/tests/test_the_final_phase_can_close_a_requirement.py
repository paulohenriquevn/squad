"""Five plans close a requirement in the Final Phase, and the matrix could not say so.

`TASK_ID_RE` is `T\\d+\\.\\d+`, and no plan in any repository gives its Final Phase a task
id — the heading is `## Final Phase: Integration Validation` in all of them, an H2 rather
than a task. A matrix row citing `Final Phase` therefore matched nothing and was counted
as a requirement closed by no task. Measured 2026-09-21, once the shape fix made ten
matrices readable: 19 rows closed nothing, and 11 of the 19 had this structural cause
rather than an authoring one.

The mapping was not missing from those plans, only unexpressible. One of them closes
NFR-002 by name in its Final Phase acceptance criteria — *"Production dependency count
<= 3 (NFR-002)"* — while its matrix row could only say `Final Phase`.

THE DECISION, and why the other option was refused. The Final Phase does NOT get a task
id; the parser accepts it by name. Giving it `T\\d+\\.\\d+` would make it a task to every
other reader of that pattern — `check_tdd_in_bugfix.py:16` matches `### T<n>.<n>` headers
and requires a RED-test shape per bugfix task, and `check_concurrency_tests.py:181` reads
the same shape. The Final Phase is integration validation over work already done; forcing
a RED test onto it satisfies a regex and describes nothing. One id would have propagated a
requirement through three gates to fix a citation in one.

The citation is checked, not merely recognised: a row may cite the Final Phase only if the
plan HAS one. Otherwise the fix would let a requirement be closed by a section nobody
wrote, which is the shape of every dead pointer this kit refuses elsewhere.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))

MATRIX = """| # | Gap / Requirement | Task(s) | Resolution |
|---|---|---|---|
| 1 | NFR-002 dependency ceiling | {task} | validated end to end |
"""

FINAL_PHASE = """
## Final Phase: Integration Validation (MANDATORY)

- Production dependency count <= 3 (NFR-002)
"""


def _plan(tmp_path: Path, task: str, *, final_phase: bool = True) -> Path:
    body = (
        "# Plan\n\n## Tasks\n\n### T1.1 Do the thing\n\n"
        "## Coverage Matrix\n\n" + MATRIX.format(task=task) + "\n"
        + (FINAL_PHASE if final_phase else "## Something else\n\nnothing\n")
    )
    path = tmp_path / "plan.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_a_requirement_closed_by_the_final_phase_is_mapped(tmp_path: Path) -> None:
    from check_coverage_matrix import check_coverage_matrix

    report = check_coverage_matrix(_plan(tmp_path, "Final Phase"))

    assert (report.total_gaps, report.mapped_gaps) == (1, 1), (
        "the plan closes this requirement and the matrix had no way to say so"
    )
    assert report.is_complete


def test_the_citation_is_case_and_wording_tolerant(tmp_path: Path) -> None:
    from check_coverage_matrix import check_coverage_matrix

    for cited in ("final phase", "Final Phase: Integration Validation", "**Final Phase**"):
        report = check_coverage_matrix(_plan(tmp_path, cited))
        assert report.mapped_gaps == 1, cited


def test_citing_a_final_phase_the_plan_does_not_have_closes_nothing(tmp_path: Path) -> None:
    """A section nobody wrote is a dead pointer, whatever the row claims."""
    from check_coverage_matrix import check_coverage_matrix

    report = check_coverage_matrix(_plan(tmp_path, "Final Phase", final_phase=False))

    assert report.mapped_gaps == 0
    assert report.unmapped_gaps, "it must be reported, not silently dropped"


def test_a_numbered_task_still_maps(tmp_path: Path) -> None:
    """THE CONTROL — the thirteen plans that avoided this must not change verdict."""
    from check_coverage_matrix import check_coverage_matrix

    report = check_coverage_matrix(_plan(tmp_path, "T1.1"))

    assert (report.total_gaps, report.mapped_gaps) == (1, 1)


def test_an_em_dash_still_closes_nothing(tmp_path: Path) -> None:
    """The other eight of the nineteen. This fix must not absorb them."""
    from check_coverage_matrix import check_coverage_matrix

    report = check_coverage_matrix(_plan(tmp_path, "—"))

    assert report.mapped_gaps == 0
    assert report.unmapped_gaps


def test_the_final_phase_is_not_counted_as_a_task_elsewhere(tmp_path: Path) -> None:
    """The risk the report named, pinned: accepting the NAME must not create an ID.

    `check_tdd_in_bugfix` reads `### T<n>.<n>` headings. If this fix had worked by giving
    the Final Phase a task id, that reader would have acquired a task demanding a RED-test
    shape for a phase that validates work already done.
    """
    from check_tdd_in_bugfix import check_tdd_in_bugfix

    report = check_tdd_in_bugfix(_plan(tmp_path, "Final Phase"))

    assert report.total_bugfix_tasks == 0
