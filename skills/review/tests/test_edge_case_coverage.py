"""B-018 — the analyzer whose ratio gates a release, and which had no test at all.

Measured 2026-08-19 before this file existed:

    b001-usage-panel-plan.md   declares 4 cases, reported 13, ratio 0.385
    b025-silent-guards-plan.md declares 7 cases, reported 27, ratio 0.222

Both below the 0.80 that `consolidate_findings.py` turns into NEEDS_DEEPER. Three defects:
the same bullet counted twice (stripped and prefixed), every keyword-bearing bullet anywhere in
the document counted as an edge case, and a matcher demanding all five longest words co-occur in
one file — which missed three cases whose named tests exist.

Most fixtures are written into `tmp_path`, so the suite pins the BEHAVIOUR. Two tests read this
repo's own plans and say so: they are the item's evidence, and a regression against them is the
regression the item reports.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "edge_case_coverage.py"
REPO = Path(__file__).resolve().parents[3]


def run(plan: Path, tests_dir: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--plan", str(plan), "--tests-dir", str(tests_dir)],
        capture_output=True, text=True, check=False,
    )
    assert "{" in result.stdout, result.stderr
    return json.loads(result.stdout[result.stdout.index("{"):])


PLAN = """# Plan: fixture

## Baseline Context

- `src/thing.ts:40` — this module already handles an invalid, empty and missing input, and the
  concurrent retry path has a timeout.

## Unresolved Questions

- Whether the maximum boundary should be configurable.

## Phase 1

### T1.1 — do the thing

#### Deep Dives
- Edge case: an empty order list renders nothing at all.
- Edge case: a non-positive window throws a typed error.
- Negative case: a malformed payload is refused with a typed error.

#### TDD
RED: test_an_empty_order_list_renders_nothing — asserts the frame is empty.
RED: test_a_non_positive_window_throws — asserts the typed error.

#### Acceptance Criteria
- [ ] `npx tsc --noEmit` exits 0 with no missing types
- [ ] the maximum retry limit is respected
"""


def _fixture(tmp_path: Path, plan_text: str = PLAN, test_body: str = "") -> tuple[Path, Path]:
    plan = tmp_path / "fixture-plan.md"
    plan.write_text(plan_text, encoding="utf-8")
    tests = tmp_path / "src"
    tests.mkdir(exist_ok=True)
    (tests / "thing.test.ts").write_text(test_body, encoding="utf-8")
    return plan, tests


def test_a_plan_declaring_three_cases_reports_three(tmp_path: Path) -> None:
    # The count IS the defect: today the same bullets are extracted twice (stripped and prefixed)
    # and the prose bullets above are swept in as well.
    plan, tests = _fixture(tmp_path)

    report = run(plan, tests)

    assert report["edge_cases_found_in_plan"] == 3


def test_prose_bullets_outside_deep_dives_are_not_counted(tmp_path: Path) -> None:
    # A Baseline Context citation and an Unresolved Question are not behaviours. No test can ever
    # cover them, so counting them drives the ratio down forever.
    plan, tests = _fixture(tmp_path)

    report = run(plan, tests)

    descriptions = " | ".join(i["description"] for i in report["items"])
    assert "src/thing.ts:40" not in descriptions
    assert "configurable" not in descriptions
    assert "npx tsc" not in descriptions


def test_a_negative_case_is_a_declared_case_too(tmp_path: Path) -> None:
    # rules/testing.md § 4.1 — edge cases and negative cases are distinct lenses and both count.
    plan, tests = _fixture(tmp_path)

    report = run(plan, tests)

    assert any(i["description"].startswith("Negative case:") for i in report["items"])


def test_no_two_items_differ_only_by_the_edge_case_prefix(tmp_path: Path) -> None:
    plan, tests = _fixture(tmp_path)

    report = run(plan, tests)

    stripped = [
        i["description"].split(":", 1)[-1].strip() for i in report["items"]
    ]
    assert len(stripped) == len(set(stripped))


def test_a_case_is_covered_when_the_task_names_a_test_that_exists(tmp_path: Path) -> None:
    # The plan's own #### TDD block names the test. That claim is checkable by identifier, where
    # keyword matching guesses at vocabulary — and got 3 of 5 wrong on a plan whose tests all exist.
    plan, tests = _fixture(
        tmp_path,
        test_body="it('test_an_empty_order_list_renders_nothing', () => {});\n",
    )

    report = run(plan, tests)

    empty = next(i for i in report["items"] if "empty order list" in i["description"])
    assert empty["status"] == "covered"
    assert empty.get("matched_test") == "test_an_empty_order_list_renders_nothing"


def test_a_named_test_that_does_not_exist_does_not_count_as_coverage(tmp_path: Path) -> None:
    # Naming a test does not make it exist. Without this, the fix would be a way to declare
    # coverage by writing a plan.
    plan, tests = _fixture(tmp_path, test_body="it('something_else', () => {});\n")

    report = run(plan, tests)

    empty = next(i for i in report["items"] if "empty order list" in i["description"])
    assert empty["status"] != "covered"


def test_the_fallback_does_not_demand_every_keyword(tmp_path: Path) -> None:
    # A case whose task names no test falls back to keywords. The old matcher required ALL five
    # longest words in one file; a near-verbatim test name fails that.
    plan_text = PLAN.replace(
        "RED: test_an_empty_order_list_renders_nothing — asserts the frame is empty.\n"
        "RED: test_a_non_positive_window_throws — asserts the typed error.\n",
        "prose only, no identifiers here\n",
    )
    plan, tests = _fixture(
        tmp_path,
        plan_text=plan_text,
        test_body="it('a_malformed_payload_is_refused_with_a_typed_error', () => {});\n",
    )

    report = run(plan, tests)

    malformed = next(i for i in report["items"] if "malformed" in i["description"])
    assert malformed["route"] == "keyword-fallback"
    assert malformed["status"] == "partial"


# --- The counts and statuses, against fixtures this repository carries. ---
#
# Three tests here read `.claude/records/plans/b025-...` and `b001-...` and each began
# `if not plan.exists(): return`. `.claude/` is never versioned, so in any clone those
# files are absent and all three returned before reaching an assertion — three green
# results asserting nothing, in the file that measures whether coverage is real.
# A `return` is not a skip: pytest reports it as a pass. The fixtures now live here.

_SEVEN_CASE_PLAN = """# Plan: seven

## Phase 1

### T1.1 — render the frame

#### Deep Dives
- Edge case: a physical line longer than the frame is truncated, not wrapped.
- Edge case: ESC yields no raw control byte in the output.
- Edge case: a handler returning `false` counts a loss, not a no-op.
- Edge case: an empty input renders the frame and nothing else.
- Edge case: a non-positive width throws a typed error.
- Edge case: two writers on one frame serialise.
- Edge case: a resize mid-render redraws once, not twice.

#### TDD
RED: test_a_physical_line_longer_than_the_frame_is_truncated — asserts the truncation.
RED: test_esc_yields_no_raw_control_byte — asserts the escaping.
RED: test_a_handler_returning_false_counts_a_loss — asserts the tally.
"""

_FOUR_CASE_PLAN = """# Plan: four

## Phase 1

### T1.1 — render the order list

#### Deep Dives
- Edge case: an empty order list renders nothing.
- Edge case: a non-positive window throws a typed error.
- Edge case: a duplicate id is refused.
- Edge case: a missing total is not zero.
"""


def _plan(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "a-plan.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_a_plan_declaring_seven_cases_reports_seven(tmp_path: Path) -> None:
    report = run(_plan(tmp_path, _SEVEN_CASE_PLAN), tmp_path / "tests")

    assert report["edge_cases_found_in_plan"] == 7


def test_a_plan_declaring_four_cases_reports_four(tmp_path: Path) -> None:
    report = run(_plan(tmp_path, _FOUR_CASE_PLAN), tmp_path / "tests")

    assert report["edge_cases_found_in_plan"] == 4


def test_cases_whose_named_tests_exist_are_covered_not_partial(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_frame.py").write_text(
        "def test_a_physical_line_longer_than_the_frame_is_truncated(): pass\n"
        "def test_esc_yields_no_raw_control_byte(): pass\n"
        "def test_a_handler_returning_false_counts_a_loss(): pass\n", encoding="utf-8")

    report = run(_plan(tmp_path, _SEVEN_CASE_PLAN), tests)

    for fragment in ("physical line", "ESC yields no raw control byte",
                     "returning `false` counts a loss"):
        item = next(i for i in report["items"] if fragment in i["description"])
        assert item["status"] == "covered", f"{fragment}: {item}"


# --- The four behaviours a first pass left unpinned. Each was found by a surviving mutant. ---

def test_a_declared_case_outside_deep_dives_is_not_counted(tmp_path: Path) -> None:
    # The prefix alone does the extraction on every plan measured (5 of 5 give identical counts
    # with and without the section scoping), so nothing forced the scoping to stay correct. A plan
    # QUOTING a case in its Baseline Context or Prior Art must not have it counted as declared.
    plan_text = PLAN.replace(
        "## Baseline Context\n",
        "## Baseline Context\n\n- Edge case: a quoted case from another plan, cited as prior art.\n",
    )
    plan, tests = _fixture(tmp_path, plan_text=plan_text)

    report = run(plan, tests)

    assert report["edge_cases_found_in_plan"] == 3
    assert all("prior art" not in i["description"] for i in report["items"])


def test_the_same_case_declared_in_two_tasks_counts_once(tmp_path: Path) -> None:
    # The original defect was a double count. Nothing pinned the dedup once extraction was scoped,
    # so removing it was invisible.
    plan_text = PLAN + """
### T1.2 — do it again

#### Deep Dives
- Edge case: an empty order list renders nothing at all.
"""
    plan, tests = _fixture(tmp_path, plan_text=plan_text)

    report = run(plan, tests)

    assert report["edge_cases_found_in_plan"] == 3


def test_a_plan_may_write_test_x_while_the_suite_declares_x(tmp_path: Path) -> None:
    # Measured on b001: the plan names `test_omits_the_cost_meter_...` and the suite declares
    # `it("omits_the_cost_meter_...")`. Requiring the literal string dropped all four of that
    # plan's cases to the keyword fallback.
    plan, tests = _fixture(
        tmp_path,
        test_body="it('an_empty_order_list_renders_nothing', () => {});\n",
    )

    report = run(plan, tests)

    empty = next(i for i in report["items"] if "empty order list" in i["description"])
    assert empty["route"] == "named-test"
    assert empty["status"] == "covered"


def test_one_shared_word_is_not_enough_to_name_a_test(tmp_path: Path) -> None:
    # A task's tests are a list, not an ordered mapping onto its cases. With no floor, ties at one
    # shared word broke alphabetically and a case was attributed to a test that does not cover it.
    plan_text = """# Plan: fixture

### T1.1 — do the thing

#### Deep Dives
- Edge case: a malformed payload is refused with a typed error.

#### TDD
RED: test_an_empty_order_list_renders_nothing — shares only "payload"? no: shares nothing but length.
"""
    plan, tests = _fixture(
        tmp_path,
        plan_text=plan_text,
        test_body="it('test_an_empty_order_list_renders_nothing', () => {});\n",
    )

    report = run(plan, tests)

    case = report["items"][0]
    assert case["route"] != "named-test", case
