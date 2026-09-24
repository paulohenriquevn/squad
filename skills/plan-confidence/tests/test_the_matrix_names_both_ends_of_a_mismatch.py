"""The artifact's own explanation of a fix re-created the thing it removed.

`_task_criteria` attributes a criterion to a task only from inside that task's own
`#### Acceptance Criteria` block. Correct, and the reason is good. The trap is what happens when a
review asks for a criterion to MOVE between tasks.

Measured on a consumer, three times in one session. The natural edit is to move the bullet and
leave a note saying so — and the most useful place for that note, for a reader, is inside the
block it is about. The parser then reads the note's `**AC-005**` as T1.2 still declaring it, while
the moved bullet, placed under T1.4's `###` heading but above its first `####`, sits in no
subsection and is invisible. Net: `matrix_cites_undeclared_criterion` + `coverage_lt_100`, from
three corrections that were right by eye. Differential proof on a scratch copy — reverting one
row's task id flipped `is_complete` from False back to True.

A panel seat found it by running the scorer. The other two read the plan text, found the move
correct, and closed the objection — a human following the moved bullet DOES find it under T1.4.
Only the mechanism disagreed, and it said so in a message that named neither end.

WHAT THIS FIXES, AND WHAT IT DELIBERATELY DOES NOT. The parser is not made cleverer about prose:
a checker that tried to tell a declaration from a sentence describing one would be guessing, and
that direction ends badly. What changes is the DIAGNOSTIC — it names both ends of the mismatch,
which is what the author needed and what one printed line closes.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SCRIPT = _ROOT / "skills" / "plan-confidence" / "scripts" / "check_coverage_matrix.py"

_PLAN = """# Plan

## Coverage Matrix

| Gap | Description | Task | Criteria |
|---|---|---|---|
| G1 | the thing | T1.4 | AC-005 |

## Phase 1

### T1.2 — the first task

#### Acceptance Criteria
Closes **FR-003**.

**Corrected after review.** This section listed **AC-005** among T1.2's closing criteria while the
test that produces it lives in T1.4. AC-005 moved to T1.4.

- **AC-004** — `bash -c 'true'` exits 0.

#### DoD

- [ ] `bash -c 'true'` exits 0.

### T1.4 — the second task

- **AC-005** — `bash -c 'true'` exits 0.

#### Objective

Do the thing.
"""


@pytest.fixture(scope="module")
def mod():
    sys.path.insert(0, str(_SCRIPT.parent))
    spec = importlib.util.spec_from_file_location(_SCRIPT.stem, _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[_SCRIPT.stem] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def report(mod, tmp_path: Path):
    plan = tmp_path / "x-plan.md"
    plan.write_text(_PLAN, encoding="utf-8")
    return mod.check_coverage_matrix(plan)


def test_the_trap_is_reproduced(report) -> None:
    """The premise. Without the mismatch every assertion below is vacuous."""
    assert report.criteria_not_declared, (
        "the fixture no longer reproduces the mismatch; re-point this test")


def test_the_diagnosis_names_the_task_that_still_declares_it(report) -> None:
    joined = " | ".join(report.criteria_not_declared)

    assert "T1.4" in joined, joined
    assert "T1.2" in joined, (
        "the message says T1.4 does not declare AC-005 and never says T1.2 still does, which is "
        f"the half that closes the diagnosis: {joined}")


def test_the_diagnosis_names_where(report) -> None:
    """A line number turns a search into a jump.

    Asserted as `line <n>` rather than as "contains a digit": the first draft of this passed
    before the fix, on the `1` in the gap id `G1` — a test satisfied by a coincidence in the text
    it was reading.
    """
    import re as _re

    joined = " | ".join(report.criteria_not_declared)

    assert _re.search(r"\bline \d+", joined), f"no line number in: {joined}"


def test_a_criterion_outside_any_subsection_is_reported(report) -> None:
    """It is always a mistake: invisible to every consumer of the block, including the matrix."""
    orphans = getattr(report, "criteria_outside_any_subsection", None)

    assert orphans is not None, "the report has no field for a criterion in no subsection"
    joined = " | ".join(orphans)
    assert "AC-005" in joined and "T1.4" in joined, joined


def test_a_well_formed_plan_reports_neither(mod, tmp_path: Path) -> None:
    """The control. A check that fires on a correct plan is one somebody switches off."""
    good = _PLAN.replace(
        "### T1.4 — the second task\n\n- **AC-005** — `bash -c 'true'` exits 0.\n",
        "### T1.4 — the second task\n\n#### Acceptance Criteria\n\n"
        "- **AC-005** — `bash -c 'true'` exits 0.\n")
    good = good.replace(
        "**Corrected after review.** This section listed **AC-005** among T1.2's closing criteria "
        "while the\ntest that produces it lives in T1.4. AC-005 moved to T1.4.\n\n", "")
    plan = tmp_path / "good-plan.md"
    plan.write_text(good, encoding="utf-8")

    report = mod.check_coverage_matrix(plan)

    assert not report.criteria_not_declared, report.criteria_not_declared
    assert not getattr(report, "criteria_outside_any_subsection", ()), (
        getattr(report, "criteria_outside_any_subsection", ()))
