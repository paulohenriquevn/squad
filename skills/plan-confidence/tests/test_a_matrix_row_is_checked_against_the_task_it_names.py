"""The matrix said a task closes a gap, and nothing opened the task to see.

`check_coverage_matrix` reads each row, finds the `T{N}.{M}` in its task column, and
counts the gap as mapped. It also reports ORPHAN TASKS — a `### T{N}.{M}` heading no row
cites. Both directions of the TASK relation are covered.

What was covered in neither direction is the rest of the row. A row saying
`| G1 | something | T1.1 | AC-999 |` counts as mapped when `AC-999` is declared nowhere in
the plan, and the report comes back `coverage_ratio: 1.0, is_complete: True`.

Reported 2026-09-22 by the session that hit it, with the consequence measured rather than
imagined: a reviewer found `AC-004` orphaned — the row said `T2.1`, and `T2.1`'s own block
declared something else. A three-line cross-check written by hand then found **five more**
divergences the gate was approving as complete. And the orphaned criterion was the one that
would have caught the plan's shape defect: *the gate that exists to prove coverage approved
away the gap that mattered.*

WHAT THIS DOES AND DOES NOT ASSERT. It compares the identifiers a row CITES against the
identifiers the named task's `#### Acceptance Criteria` block DECLARES, and reports both
directions. It does not decide whether a criterion is any good — `check_criterion_executability`
owns that — and it does not invent a requirement that rows must carry criteria at all: a row
citing none is silent here, because the template's fourth column is `Resolution` and prose
belongs in it.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from check_coverage_matrix import check_coverage_matrix  # noqa: E402

HEAD = """# Plan

## Tasks

### T1.1 — the real one

#### Acceptance Criteria

- AC-001: the thing happens.

"""

MATRIX = """## Coverage Matrix

| # | Gap / Requirement | Task(s) | Resolution |
|---|---|---|---|
| G1 | something | T1.1 | {cell} |

## Global Definition of Done
"""


def _plan(tmp_path: Path, cell: str, head: str = HEAD) -> Path:
    path = tmp_path / "plan.md"
    path.write_text(head + MATRIX.format(cell=cell), encoding="utf-8")
    return path


def test_a_row_citing_a_criterion_no_task_declares_is_reported(tmp_path: Path) -> None:
    report = check_coverage_matrix(_plan(tmp_path, "AC-999"))

    assert report.criteria_not_declared == ("G1 cites AC-999, which T1.1 does not declare",), (
        "the row named a criterion that exists nowhere and the gap counted as mapped"
    )
    assert not report.is_complete, "a matrix citing what no task declares is not complete"


def test_a_row_citing_a_criterion_the_task_declares_is_silent(tmp_path: Path) -> None:
    """THE CONTROL. A check that fires on the conforming case reports nothing."""
    report = check_coverage_matrix(_plan(tmp_path, "AC-001"))

    assert report.criteria_not_declared == ()
    assert report.is_complete


def test_a_row_with_prose_in_the_resolution_column_is_silent(tmp_path: Path) -> None:
    """The template's fourth column is `Resolution`, and prose belongs in it.

    Demanding a criterion in every row would invent a requirement the template does not
    make — and a check that invents its own contract is one people learn to route around.
    """
    report = check_coverage_matrix(_plan(tmp_path, "built in T1.1"))

    assert report.criteria_not_declared == ()
    assert report.is_complete


def test_a_criterion_a_task_declares_and_no_row_cites_is_reported_apart(
    tmp_path: Path,
) -> None:
    """The other direction, kept as its own field.

    `matrix − block` and `block − matrix` are different findings: the first is a row
    pointing at nothing, the second is work a task promises that no gap asked for.
    Collapsing them would make one number out of two questions.
    """
    head = HEAD.replace("- AC-001: the thing happens.\n",
                        "- AC-001: the thing happens.\n- AC-002: and the other thing.\n")

    report = check_coverage_matrix(_plan(tmp_path, "AC-001", head=head))

    assert report.criteria_not_cited == ("T1.1 declares AC-002, which no matrix row cites",)
    assert report.criteria_not_declared == ()


def test_an_uncited_criterion_does_not_fail_the_matrix(tmp_path: Path) -> None:
    """A task may legitimately carry a criterion the matrix does not index.

    Reported so a reader can see it; not a cap, because the matrix maps GAPS to tasks and
    a task is free to promise more than the gap asked.
    """
    head = HEAD.replace("- AC-001: the thing happens.\n",
                        "- AC-001: the thing happens.\n- AC-002: and the other thing.\n")

    assert check_coverage_matrix(_plan(tmp_path, "AC-001", head=head)).is_complete


def test_a_row_naming_a_task_with_no_criteria_block_is_silent(tmp_path: Path) -> None:
    """Absent is not wrong. A task with no `#### Acceptance Criteria` declares nothing,
    and a row citing no criterion asks for nothing; neither is a divergence."""
    head = "# Plan\n\n## Tasks\n\n### T1.1 — bare\n\nbody\n\n"

    report = check_coverage_matrix(_plan(tmp_path, "built in T1.1", head=head))

    assert report.criteria_not_declared == ()
    assert report.criteria_not_cited == ()
