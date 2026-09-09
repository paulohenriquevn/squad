"""`sq test` — and the report that names what it did not run.

The friction this closes is not slowness. On 2026-09-09 a session reported
"1894 passed" as full coverage while 152 tests collected nowhere and 22 slice suites
had not run, because nothing on screen said the other half existed.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from squad.cli import run_suites  # noqa: E402
from squad.cli.report import OK, UNMEASURED  # noqa: E402


def test_slice_discovery_matches_the_runner_that_ci_uses() -> None:
    """One definition of "the suites". A second glob would be a second answer.

    `run_slice_tests.sh` is the definition; this asserts the CLI agrees with it rather
    than maintaining its own list, which is the ADR's central constraint.
    """
    from_cli = run_suites.discover_slices(ROOT)
    script = (ROOT / "mechanisms" / "cycle" / "run_slice_tests.sh").read_text(encoding="utf-8")
    assert "skills/*/tests" in script, "the runner changed how it globs; this test is stale"
    on_disk = {p.parent.name for p in sorted(ROOT.glob("skills/*/tests")) if p.is_dir()}
    assert from_cli == on_disk


def test_the_root_suite_is_every_declared_testpath() -> None:
    """1742 vs 1894 was the whole of kit#58, and it came from one missing path."""
    assert run_suites.root_paths(ROOT) == ["tests", "hooks/tests", "squad/tests"]


def test_parsing_the_runner_trailer() -> None:
    output = (
        "::group::pytest tests\nnoise\n::endgroup::\n"
        "\nSUITE\ttests\t0\t1894\t-\t1894\n"
        "SUITE\tskills/review/tests\t1\t90\t4\t94\n\nALL SUITES GREEN\n"
    )
    rows = run_suites.parse_trailer(output)
    assert len(rows) == 2
    assert rows[0].path == "tests" and rows[0].passed == 1894 and rows[0].rc == 0
    assert rows[1].failed == 4 and rows[1].rc == 1


def test_an_absent_count_stays_none_rather_than_zero() -> None:
    """`-` means pytest did not say. Reading it as 0 makes a total into fiction."""
    rows = run_suites.parse_trailer("SUITE\ttests\t2\t-\t-\t-\n")
    assert rows[0].passed is None
    assert rows[0].rc == 2


def test_a_run_of_the_root_alone_names_the_slices_it_skipped() -> None:
    """The load-bearing property, on the verb that made it necessary."""
    report = run_suites.build_report(
        ROOT,
        rows=[run_suites.SuiteRow("tests", 0, 1894, None, 1894)],
        selected=None,
        skipped_slices=sorted(run_suites.discover_slices(ROOT)),
        base=None,
    )
    assert report.not_checked, "a partial run that claims to have missed nothing"
    joined = " ".join(report.not_checked)
    assert "slice" in joined
    assert report.exit_code == OK


def test_a_failing_suite_makes_the_report_a_finding() -> None:
    report = run_suites.build_report(
        ROOT,
        rows=[run_suites.SuiteRow("skills/review/tests", 1, 90, 4, 94)],
        selected={"review"},
        skipped_slices=[],
        base=None,
    )
    assert report.exit_code != OK


def test_nothing_collected_is_unmeasured_not_a_failure() -> None:
    """pytest 5 means the set was empty, which is not the same as tests failing.

    Collapsing the two is what the runner used to do by writing "0"/"1" instead of $?.
    """
    report = run_suites.build_report(
        ROOT,
        rows=[run_suites.SuiteRow("skills/review/tests", 5, None, None, 0)],
        selected={"review"},
        skipped_slices=[],
        base=None,
    )
    assert report.exit_code == UNMEASURED
    assert any("collected" in line.lower() for line in report.lines + report.not_checked)


def test_a_full_run_still_states_that_it_skipped_nothing() -> None:
    """Silence would read as an omission. An empty answer is spoken."""
    report = run_suites.build_report(
        ROOT,
        rows=[run_suites.SuiteRow("tests", 0, 1894, None, 1894)],
        selected=None,
        skipped_slices=[],
        base=None,
    )
    assert report.not_checked, "even a complete run must say that it was complete"
