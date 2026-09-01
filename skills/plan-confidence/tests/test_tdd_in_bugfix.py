"""The TDD-in-bugfix gate, which was the one active checker with no test at all.

`run_structural.py` imports it, calls it at line 304, and turns its ratio into
twenty points of the completeness score. Sixteen checkers ship in this skill and
fifteen were covered; this one was not, so nothing pinned what it detects, what it
ignores, or what it reports when it finds nothing.

Two behaviours below are documented rather than asserted as good — they are the
ones a reader should decide about, and until now nothing made them visible:

  - zero bug-fix tasks yields `coverage_ratio == 1.0`, which `run_structural`
    turns into 20/20 and a reason labelled POSITIVE reading "(0/0)";
  - a task id outside the canonical `T<n>.<n>` shape is not seen at all.

Both are consistent with `check_adr_completeness`, which scores an empty ADR set
the same way, so they read as a rubric decision rather than an accident. The tests
pin them so that changing either is a deliberate act with a failing test attached.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_tdd_in_bugfix import check_tdd_in_bugfix  # noqa: E402

TDD_BLOCK = "#### TDD\n\nRED: a failing test for the reported behaviour\nGREEN: the fix\n"


def _plan(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "p-plan.md"
    path.write_text(f"# Plan\n\n## Tasks\n\n{body}", encoding="utf-8")
    return path


def test_a_bugfix_task_with_a_tdd_block_is_covered(tmp_path: Path) -> None:
    report = check_tdd_in_bugfix(
        _plan(tmp_path, f"### T1.1 — Fix a bug in the parser\n\n{TDD_BLOCK}")
    )
    assert report.total_bugfix_tasks == 1
    assert report.with_tdd == 1
    assert report.coverage_ratio == 1.0
    assert report.missing_tdd == ()


def test_a_bugfix_task_without_tdd_is_named(tmp_path: Path) -> None:
    """The finding has to carry the task id — a count alone is not actionable."""
    report = check_tdd_in_bugfix(
        _plan(tmp_path, "### T1.1 — Fix a bug in the parser\n\nJust patch it.\n")
    )
    assert report.total_bugfix_tasks == 1
    assert report.with_tdd == 0
    assert report.coverage_ratio == 0.0
    assert report.missing_tdd == ("T1.1",)


def test_a_task_that_is_not_a_bugfix_is_not_counted(tmp_path: Path) -> None:
    """The gate is about regressions, not about every task lacking a TDD block."""
    report = check_tdd_in_bugfix(
        _plan(tmp_path, "### T1.1 — Add a new endpoint\n\nJust build it.\n")
    )
    assert report.total_bugfix_tasks == 0
    assert report.missing_tdd == ()


def test_each_bugfix_keyword_is_recognised(tmp_path: Path) -> None:
    """A synonym the list misses is a bug-fix that ships with no regression test."""
    for phrase in ("bug-fix", "bug fix", "bugfix", "regression", "fix a bug",
                   "fix the bug", "resolve a bug", "fix bug", "parser bug"):
        report = check_tdd_in_bugfix(
            _plan(tmp_path, f"### T1.1 — Handle {phrase} in the loader\n\nJust patch it.\n")
        )
        assert report.total_bugfix_tasks == 1, f"{phrase!r} was not recognised as a bug-fix"


def test_only_the_task_own_tdd_block_counts(tmp_path: Path) -> None:
    """A TDD block belonging to the NEXT task must not cover this one.

    The body is delimited by the next task header; without that, one TDD block
    anywhere would mark every preceding bug-fix as covered.
    """
    report = check_tdd_in_bugfix(_plan(
        tmp_path,
        "### T1.1 — Fix a bug in the parser\n\nJust patch it.\n\n"
        f"### T1.2 — Add an endpoint\n\n{TDD_BLOCK}",
    ))
    assert report.missing_tdd == ("T1.1",), "T1.2's TDD block must not cover T1.1"


# ── the two behaviours a reader should decide about ───────────────────────────


def test_no_bugfix_task_scores_as_full_coverage(tmp_path: Path) -> None:
    """DOCUMENTED, not endorsed: nothing found yields a perfect ratio.

    `run_structural.py:197` computes `20.0 * coverage_ratio`, so a plan with no
    detectable bug-fix task takes the full twenty points and line 206 labels the
    reason POSITIVE, reading "TDD in bug-fix (0/0)" — a positive claim about
    something never measured.

    It is consistent with `check_adr_completeness`, which scores an empty ADR set
    the same way, so it reads as a rubric decision: a plan with no bug-fix carries
    no TDD debt. Pinned here so that changing it is deliberate.
    """
    report = check_tdd_in_bugfix(_plan(tmp_path, "### T1.1 — Add an endpoint\n\nBuild it.\n"))
    assert report.total_bugfix_tasks == 0
    assert report.coverage_ratio == 1.0, (
        "vacuous coverage is the current contract — change it deliberately, not by accident"
    )


def test_a_task_id_outside_the_canonical_shape_is_invisible(tmp_path: Path) -> None:
    """DOCUMENTED: the header regex requires `T<n>.<n>`, so `T1` is not seen.

    `plan-template-lite.md` writes `T0.1` and every plan in this repository uses
    the two-part form, and all three task-reading checkers agree on it — so this is
    the format, not a gap. But a hand-written plan using `T1` gets a bug-fix task
    silently excluded from the gate AND a perfect ratio, which is the one
    combination worth knowing about.
    """
    canonical = check_tdd_in_bugfix(
        _plan(tmp_path, "### T1.1 — Fix a bug in the parser\n\nJust patch it.\n"))
    assert canonical.total_bugfix_tasks == 1

    short_form = check_tdd_in_bugfix(
        _plan(tmp_path, "### T1 — Fix a bug in the parser\n\nJust patch it.\n"))
    assert short_form.total_bugfix_tasks == 0
    assert short_form.coverage_ratio == 1.0
