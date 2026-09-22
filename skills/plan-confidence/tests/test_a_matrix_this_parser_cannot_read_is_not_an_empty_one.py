"""A two-column Coverage Matrix reported as a matrix with no rows, and the cap fired.

`_parse_matrix_rows` dropped every line with fewer than four cells and picked the task
from `cells[2:]` by position. The template declares four columns, so a plan that wrote
two produced ZERO rows — and `CoverageReport(total_gaps=0, mapped_gaps=0)` is exactly what
an empty matrix produces. `run_structural` then fired `coverage_lt_100` at cap 49 and the
plan came back INVALID, with nothing anywhere saying the table had not been read.

Measured 2026-09-20 across twelve plans on disk: seven wrote two columns, two more wrote
`Requirement | Closed by | Verified by` — three columns with the task in `cells[1]`, where
the parser does not look. Nine of twelve plans could not enter `/implement`, and the cause
was a table shape rather than anything about the work they described.

THE CHOICE, since the report offered two and asked that it be written down: the parser
reads the task column BY HEADER NAME, and an unrecognised header is NAMED rather than
silently empty. A strict header check would refuse divergence at authoring time, which
helps the next plan and none of the nine — they would all still be INVALID, for a reason
still not stated. Reading by name accepts the template and the synonyms people actually
wrote, and turns the remaining cases into a finding that says which header it found.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))

PREAMBLE = """# Plan

## Tasks

### T1.1 Do the thing

## Coverage Matrix

"""


def _plan(tmp_path: Path, matrix: str) -> Path:
    path = tmp_path / "plan.md"
    path.write_text(PREAMBLE + matrix + "\n## Next section\n", encoding="utf-8")
    return path


FOUR_COLUMN = """| # | Gap / Requirement | Task(s) | Resolution |
|---|---|---|---|
| 1 | The thing is missing | T1.1 | built in T1.1 |
"""

TWO_COLUMN = """| Requirement | Task(s) |
|---|---|
| The thing is missing | T1.1 |
"""

CLOSED_BY = """| Requirement | Closed by | Verified by |
|---|---|---|
| The thing is missing | T1.1 | the test |
"""

UNRECOGNISED = """| Alpha | Beta |
|---|---|
| something | else |
"""


def test_the_template_shape_still_reads(tmp_path: Path) -> None:
    """THE CONTROL. A fix that changes the answer for a conforming plan is a regression."""
    from check_coverage_matrix import check_coverage_matrix

    report = check_coverage_matrix(_plan(tmp_path, FOUR_COLUMN))

    assert (report.total_gaps, report.mapped_gaps) == (1, 1)
    assert report.is_complete


def test_a_two_column_matrix_is_read_instead_of_dropped(tmp_path: Path) -> None:
    from check_coverage_matrix import check_coverage_matrix

    report = check_coverage_matrix(_plan(tmp_path, TWO_COLUMN))

    assert (report.total_gaps, report.mapped_gaps) == (1, 1), (
        "the row was dropped for having fewer than four cells, and a dropped row is "
        "indistinguishable from a matrix nobody wrote"
    )


def test_the_task_is_found_under_a_synonym_of_the_template_header(tmp_path: Path) -> None:
    from check_coverage_matrix import check_coverage_matrix

    report = check_coverage_matrix(_plan(tmp_path, CLOSED_BY))

    assert (report.total_gaps, report.mapped_gaps) == (1, 1)


def test_a_header_the_parser_does_not_know_is_named_not_counted_as_zero(
    tmp_path: Path,
) -> None:
    """The distinction the whole item is about: unreadable is not empty."""
    from check_coverage_matrix import check_coverage_matrix

    report = check_coverage_matrix(_plan(tmp_path, UNRECOGNISED))

    assert report.header_recognised is False
    assert report.header == ("Alpha", "Beta")
    assert not report.is_complete


def test_a_readable_matrix_says_so(tmp_path: Path) -> None:
    from check_coverage_matrix import check_coverage_matrix

    assert check_coverage_matrix(_plan(tmp_path, FOUR_COLUMN)).header_recognised is True


def test_an_unreadable_header_caps_under_its_own_name(tmp_path: Path) -> None:
    """`coverage_lt_100` on an unread table is a true statement about a false premise.

    The verdict stays INVALID — a plan whose coverage cannot be assessed does not enter
    `/implement`, and L5 is fail-closed. What changes is that the report says which
    header it found, so the author fixes the table instead of hunting for a missing row.
    """
    from check_coverage_matrix import check_coverage_matrix
    from run_structural import _detect_hard_caps

    cov = check_coverage_matrix(_plan(tmp_path, UNRECOGNISED))
    caps = _detect_hard_caps(cov, _empty_adr(), _empty_tdd())

    ids = [c for c, _ in caps]
    assert "coverage_matrix_unreadable" in ids
    assert "coverage_lt_100" not in ids, (
        "two caps for one cause reads as two problems"
    )


def _empty_adr():
    from check_adr_completeness import ADRReport

    return ADRReport(total_adrs=0, with_alternatives=0, completeness_ratio=1.0)


def _empty_tdd():
    from check_tdd_in_bugfix import TDDReport

    return TDDReport(total_bugfix_tasks=0, with_tdd=0, coverage_ratio=1.0)
