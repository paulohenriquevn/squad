"""Tests for check_tdd_shape.py — /implement Step 2 defense-in-depth gate."""
from __future__ import annotations

from pathlib import Path

import pytest
from check_tdd_shape import (
    _blank_fences,
    _has_assertion_shape,
    _has_gwt_shape,
    _has_test_fn_shape,
    check_tdd_shape,
)

# ---------- axis-level unit tests ----------------------------------------


@pytest.mark.parametrize("text", [
    "assertEquals(result.status, 200)",
    "assert response.body == expected",
    "expect(value).toBe(42)",
    "expect(result).toEqual({ok: true})",
    "result should equal 'OK'",
    "self.assertRaises(ValueError)",
])
def test_assertion_shape_detected(text: str) -> None:
    assert _has_assertion_shape(text) is True


@pytest.mark.parametrize("text", [
    "Make the code pass",
    "Tests should be green",
    "Write a test",
])
def test_no_assertion_shape(text: str) -> None:
    assert _has_assertion_shape(text) is False


@pytest.mark.parametrize("text", [
    "Given a valid token, when the user calls /profile, then 200 is returned",
    "GIVEN an empty cart WHEN the user clicks checkout THEN error 400 is shown",
])
def test_gwt_shape_detected(text: str) -> None:
    assert _has_gwt_shape(text) is True


def test_no_gwt_shape() -> None:
    # Missing "Then"
    assert _has_gwt_shape("Given a token when the user calls /profile") is False


@pytest.mark.parametrize("text", [
    "test_payment_retry_on_502(provider_response='502') -> retried_once",
    "RED: test_user_signup_returns_201",
    "test_token_expiry(now=expired_at) returns 401",
])
def test_test_fn_shape_detected(text: str) -> None:
    assert _has_test_fn_shape(text) is True


# ---------- end-to-end on synthetic plans -------------------------------


def _write_plan(tmp_path: Path, body: str) -> Path:
    plan = tmp_path / "plan.md"
    plan.write_text(body, encoding="utf-8")
    return plan


def test_task_without_tdd_section_is_blocked(tmp_path: Path) -> None:
    body = (
        "## Phase 1\n\n"
        "### T1.1 — Build endpoint\n\n"
        "#### Objective\nBuild it.\n\n"
        "#### Acceptance Criteria\n- works\n"
    )
    plan = _write_plan(tmp_path, body)
    report = check_tdd_shape(plan)
    assert report.total_tasks == 1
    assert report.all_pass is False
    assert report.blocked_tasks[0].task_id == "T1.1"
    assert report.blocked_tasks[0].has_tdd_block is False


def test_task_with_tdd_block_but_no_shape_is_blocked(tmp_path: Path) -> None:
    body = (
        "### T1.1 — Foo\n\n"
        "#### TDD\nWrite some tests. They should be good.\n\n"
        "#### Done\n"
    )
    plan = _write_plan(tmp_path, body)
    report = check_tdd_shape(plan)
    assert report.all_pass is False
    blocked = report.blocked_tasks[0]
    assert blocked.has_tdd_block is True
    assert blocked.has_executable_shape is False


def test_task_with_assertion_shape_passes(tmp_path: Path) -> None:
    body = (
        "### T1.1 — Build endpoint\n\n"
        "#### TDD\nRED:\n```python\ndef test_endpoint_returns_200():\n    "
        "assert response.status_code == 200\n```\n"
    )
    plan = _write_plan(tmp_path, body)
    report = check_tdd_shape(plan)
    assert report.all_pass is True


def test_task_with_gwt_shape_passes(tmp_path: Path) -> None:
    body = (
        "### T1.1 — Checkout flow\n\n"
        "#### TDD\nGiven an empty cart when the user clicks checkout then error 400 "
        "is shown with message 'cart empty'.\n"
    )
    plan = _write_plan(tmp_path, body)
    report = check_tdd_shape(plan)
    assert report.all_pass is True


def test_task_with_test_fn_shape_passes(tmp_path: Path) -> None:
    body = (
        "### T1.1 — Token expiry\n\n"
        "#### TDD\nRED: test_token_expired_returns_401\nGREEN: validate exp claim\n"
    )
    plan = _write_plan(tmp_path, body)
    report = check_tdd_shape(plan)
    assert report.all_pass is True


def test_multiple_tasks_one_blocked(tmp_path: Path) -> None:
    body = (
        "### T1.1 — Good task\n\n"
        "#### TDD\nRED: test_happy_path\nGREEN: impl\n\n"
        "### T1.2 — Bad task\n\n"
        "#### TDD\nWill be tested somehow.\n"
    )
    plan = _write_plan(tmp_path, body)
    report = check_tdd_shape(plan)
    assert report.total_tasks == 2
    assert report.tasks_with_shape == 1
    assert report.all_pass is False
    assert [b.task_id for b in report.blocked_tasks] == ["T1.2"]


def test_a_plan_with_no_tasks_does_not_pass(tmp_path: Path) -> None:
    """This asserted `all_pass is True` until 2026-09-16, which encoded the defect.

    With zero tasks there are no BLOCKED tasks, so `all_pass` was vacuously true and the
    gate exited 0. Measured on a consumer that day: 6 of 25 dispatchable plans parsed to
    zero tasks and passed — the largest 1239 lines, its `## Tasks` section organised one
    heading level below what the parser matches. IMPLEMENT would have run on all six
    with no TDD verification.

    A plan with no tasks cannot be implemented, and a plan the checker cannot read has
    not been checked. Neither is a pass.
    """
    body = "# Plan\n\n## Context\nNo tasks here.\n"
    plan = _write_plan(tmp_path, body)
    report = check_tdd_shape(plan)
    assert report.total_tasks == 0
    assert report.all_pass is False


def test_cli_exit_code_0_when_all_pass(tmp_path: Path) -> None:
    import subprocess
    plan_body = "### T1.1 — Foo\n\n#### TDD\nRED: test_foo_returns_true\n"
    plan = _write_plan(tmp_path, plan_body)
    script = Path(__file__).parent.parent / "scripts" / "check_tdd_shape.py"
    result = subprocess.run(  # noqa: PLW1510
        ["python3", str(script), "--plan", str(plan), "--json"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert '"all_pass": true' in result.stdout


def test_cli_exit_code_1_when_blocked(tmp_path: Path) -> None:
    import subprocess
    plan_body = "### T1.1 — Foo\n\n#### Objective\nDo it.\n"
    plan = _write_plan(tmp_path, plan_body)
    script = Path(__file__).parent.parent / "scripts" / "check_tdd_shape.py"
    result = subprocess.run(  # noqa: PLW1510
        ["python3", str(script), "--plan", str(plan), "--json"],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "blocked_task_ids" in result.stdout
    assert "T1.1" in result.stdout


def test_assertion_over_a_function_call_is_an_executable_shape(tmp_path: Path) -> None:
    """`assert add(1, 2) == 3` is as executable as `assert total == 3`.

    The assertion pattern only accepted `[\\w.\\[\\]]` before the operator, so any
    call expression fell through to "prose only". Found when the shape gate became
    blocking at the end of the run: a perfectly executable plan was rejected.
    """
    plan = tmp_path / "p-plan.md"
    plan.write_text(
        "### T1.1 — sum\n#### TDD\nassert add(1, 2) == 3\n", encoding="utf-8"
    )
    report = check_tdd_shape(plan)
    assert report.tasks_with_shape == 1
    assert report.tasks[0].has_assertion_shape is True


# ── the gate rejected executable code and accepted prose ────────────────────


def _one_task(tdd_body: str) -> str:
    return f"## Tasks\n\n### T1.1 — a task\n\n#### TDD\n\n{tdd_body}\n"


def test_a_native_go_test_is_an_executable_shape(tmp_path):
    """Measured on a consumer: 8 of 19 plans blocked, 42%.

    Probing one task written four ways showed what the gate keyed on — Go native, Go
    testify and Rust all REJECTED; `assert x == y` and a Given/When/Then sentence both
    accepted. So the gate built to catch a plan whose RED is prose accepted a prose
    sentence and rejected executable Go.

    Seven agents hit it across five items and every one refused to rewrite its TDD
    bodies to clear it. One put the reason exactly right: "that changes nothing about
    what is verified while making me the plan's author as well as its implementer."
    """
    plan = tmp_path / "p.md"
    plan.write_text(_one_task(
        "func TestGateRegistry(t *testing.T) {\n"
        "  if got != want { t.Errorf(\"got %v want %v\", got, want) }\n}"),
        encoding="utf-8")
    report = check_tdd_shape(plan)
    assert report.tasks[0].has_executable_shape


def test_testify_and_rust_and_junit_are_executable_shapes(tmp_path):
    """A test function declaration IS the executable shape in a compiled language."""
    for body in ("require.Equal(t, 2, len(got))",
                 "assert_eq!(result, 42);",
                 "@Test public void itFails() { assertEquals(2, n); }"):
        plan = tmp_path / "p.md"
        plan.write_text(_one_task(body), encoding="utf-8")
        assert check_tdd_shape(plan).tasks[0].has_executable_shape, body


def test_a_shell_oracle_with_a_stated_expectation_is_executable(tmp_path):
    """`go test -v | grep -c '^--- PASS:' prints 3` is as executable as an assertion
    and more reproducible than one."""
    plan = tmp_path / "p.md"
    plan.write_text(_one_task(
        "`go test ./... -v | grep -c '^--- PASS:'` prints 3"), encoding="utf-8")
    assert check_tdd_shape(plan).tasks[0].has_executable_shape


def test_vague_prose_is_still_refused(tmp_path):
    """Widening must not turn the gate off. This is what it exists to catch."""
    plan = tmp_path / "p.md"
    plan.write_text(_one_task("the tests should be green after this"), encoding="utf-8")
    assert not check_tdd_shape(plan).tasks[0].has_executable_shape


def test_a_heading_inside_a_fence_does_not_truncate_the_task(tmp_path):
    """A plan quoting a CHANGELOG snippet carried a literal `## [Unreleased]` inside a
    fence; the task body was cut there, hiding that task's own `#### TDD` section and
    failing the plan for a section it had.

    A line inside a fence is data, not document structure.
    """
    plan = tmp_path / "p.md"
    plan.write_text(
        "## Tasks\n\n### T1.1 — write the changelog entry\n\n"
        "The entry looks like this:\n\n"
        "```markdown\n## [Unreleased]\n\n### Added\n- something\n```\n\n"
        "#### TDD\n\nfunc TestEntry(t *testing.T) { t.Errorf(\"missing\") }\n",
        encoding="utf-8")
    report = check_tdd_shape(plan)
    assert report.tasks[0].has_tdd_block, "the fenced heading truncated the task"
    assert report.tasks[0].has_executable_shape


def test_a_real_heading_after_a_fence_still_ends_the_task(tmp_path):
    """Blanking must not make the parser blind to structure that is real."""
    plan = tmp_path / "p.md"
    plan.write_text(
        "## Tasks\n\n### T1.1 — first\n\n```\n## not a heading\n```\n\n"
        "#### TDD\n\nassert a == b\n\n### T1.2 — second\n\n#### TDD\n\nassert c == d\n",
        encoding="utf-8")
    report = check_tdd_shape(plan)
    assert [t.task_id for t in report.tasks] == ["T1.1", "T1.2"]


# ── the gate was matching one house style, not executability ────────────────


def test_a_named_failing_test_is_a_shape_in_any_language(tmp_path):
    """`RED: test_xxx` passed and `RED: TestXxx` did not — the same claim, spelled the
    way Go spells it. The gate had Python's naming convention standing in for the
    definition of "executable"."""
    for body in ("RED: TestFooBar — already fails on 6c22c4e",
                 "`TestPathsResolve` must exist and fail before any edit",
                 "go test -run ^TestClusterScoped -count=1 ./...",
                 "test_the_package_directory_is_gone -> 1, expected 0"):
        plan = tmp_path / "p.md"
        plan.write_text(_one_task(body), encoding="utf-8")
        assert check_tdd_shape(plan).tasks[0].has_executable_shape, body


def test_a_command_with_a_stated_expectation_is_an_oracle(tmp_path):
    """Six consumer plans were blocked whole while running real commands and stating
    what each must print. A grep whose expected count is written down is an assertion;
    what it lacks is only the import of a test framework."""
    for body in ("RED: grep -c 'health' CHANGELOG.md -> expected 0 before the edit",
                 "```bash\ngrep -c 'X-Forwarded-For' docs.md   # today 0 -> after >= 1\n```",
                 "```\n# RED — before writing\ngrep -c 'a heading' runbook.md   # EXPECTED: 0\n```",
                 "cd api && govulncheck ./... # EXPECTED: exit=0"):
        plan = tmp_path / "p.md"
        plan.write_text(_one_task(body), encoding="utf-8")
        assert check_tdd_shape(plan).tasks[0].has_executable_shape, body


def test_a_command_without_an_expectation_is_a_demonstration(tmp_path):
    """The line between the two is the whole point: running something proves nothing
    until you say what it must print."""
    plan = tmp_path / "p.md"
    plan.write_text(_one_task("bash scripts/deploy.sh"), encoding="utf-8")
    assert not check_tdd_shape(plan).tasks[0].has_executable_shape


def test_prose_that_promises_green_is_still_refused(tmp_path):
    """Widening a gate is only safe if what it exists to catch is still caught. These
    are the sentences the gate was built for."""
    for body in ("the tests should be green after this",
                 "we will add tests for this behaviour",
                 "no test needed for this task",
                 "covered by the existing suite",
                 "this task is trivial and needs no verification",
                 "we will go ahead and test it manually later",
                 "the change should not regress anything",
                 "expected to work as before"):
        plan = tmp_path / "p.md"
        plan.write_text(_one_task(body), encoding="utf-8")
        assert not check_tdd_shape(plan).tasks[0].has_executable_shape, body


def test_blanking_fences_preserves_the_length_of_the_document():
    """The boundaries are found in the blanked copy and the body is sliced from the
    original, so the two must index the same. A first attempt preserved the line count
    instead — every offset past the first fence shifted, and 11 of 19 real plans went
    from passing to failing. Length equality is what that bug would have caught."""
    doc = "a\n```go\nfunc T() {}\n```\nb\n~~~\nx\n~~~\nc\n"
    assert len(_blank_fences(doc)) == len(doc)
    assert _blank_fences(doc).count("\n") == doc.count("\n")


def test_the_gate_separates_a_real_plan_from_the_same_plan_with_prose(tmp_path):
    """The property that matters is not that plans pass — it is that the gate can tell
    the two apart. Same document, same tasks, TDD section swapped for a promise."""
    real = ("## Tasks\n\n### T1.1 — a task\n\n#### TDD\n\n"
            "RED: grep -c 'x' f.md   # EXPECTED: 0\n")
    fake = ("## Tasks\n\n### T1.1 — a task\n\n#### TDD\n\n"
            "The tests will be green after this change.\n")
    (tmp_path / "real.md").write_text(real, encoding="utf-8")
    (tmp_path / "fake.md").write_text(fake, encoding="utf-8")
    assert check_tdd_shape(tmp_path / "real.md").all_pass
    assert not check_tdd_shape(tmp_path / "fake.md").all_pass
