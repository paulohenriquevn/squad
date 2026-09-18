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

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from check_tdd_in_bugfix import check_tdd_in_bugfix  # noqa: E402 — post-bootstrap import

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


def test_both_scripts_that_ask_if_a_plan_is_a_bugfix_use_the_same_answer() -> None:
    """`apply_fixes.py` decides whether to INSERT a TDD block; this gate decides
    whether to REQUIRE one. Same question, same plan, two hand-kept lists.

    A keyword in one and not the other means a plan gets a TDD section it is
    never checked for, or is checked for one nothing offered to write. They were
    aligned by hand once — a comment in this file still says so — and had drifted
    by one entry when this was measured on 2026-09-02.

    Read from source rather than imported: the two live in different skill slices
    and `conftest.py` refuses to load slices in one process, because several ship
    modules with the same basename.
    """
    import re
    from pathlib import Path

    def keywords(path: Path) -> set[str]:
        text = path.read_text(encoding="utf-8")
        block = re.search(r"BUGFIX_KEYWORDS\s*=\s*\((.*?)\n\)", text, re.S)
        assert block, f"BUGFIX_KEYWORDS not found in {path}"
        return {m.group(1) for m in re.finditer(r'"([^"]+)"', block.group(1))}

    kit = Path(__file__).resolve().parents[3]
    gate = keywords(kit / "skills" / "plan-confidence" / "scripts" / "check_tdd_in_bugfix.py")
    writer = keywords(kit / "skills" / "plan-improve" / "scripts" / "apply_fixes.py")

    assert gate == writer, (
        f"the gate and the writer disagree about what a bugfix is: {sorted(gate ^ writer)}")


def test_no_keyword_is_a_regex_in_a_list_matched_by_substring() -> None:
    """`"fix.+bug"` sat in the list with a comment admitting it was never used as
    one. It matched nothing, and it would start matching the day someone converts
    the comparison to regex — with no record of what it was for."""
    import re
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "scripts" /
            "check_tdd_in_bugfix.py").read_text(encoding="utf-8")
    block = re.search(r"BUGFIX_KEYWORDS\s*=\s*\((.*?)\n\)", text, re.S).group(1)

    for keyword in re.findall(r'"([^"]+)"', block):
        assert not re.search(r"[.*+?\[\]()|\\^$]", keyword), (
            f"{keyword!r} is a regex in a list compared with `in`")
