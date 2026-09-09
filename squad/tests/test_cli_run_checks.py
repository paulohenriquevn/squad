"""`sq check` — replaying what CI verifies, and naming what it does not.

The obvious design — glob `mechanisms/gates/check_*.py` and run each — is not
implementable. The root-path flag is not uniform across the 23 gates: eight take
`--root`, four `--repo-root`, three `--project-root`, one `--repo`, one
`--ecosystem-dir`, one a positional, one needs both `--install` and `--kit`, and three
take none. Plus `check_xrefs` passes without `--strict` while printing WARN.

A glob-and-run would therefore carry a list of seven flag conventions — a second list,
which is exactly what the ADR forbids. So the invocations are REPLAYED from `ci.yml`,
and the glob is used only to compute what CI does not reach.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from squad.cli import run_checks  # noqa: E402
from squad.cli.report import UNMEASURED  # noqa: E402

WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def test_the_replayed_commands_come_from_the_workflow() -> None:
    commands = run_checks.gate_commands(WORKFLOW, ROOT)
    assert commands, "no command survived the filter, which cannot be right for this repo"
    joined = [" ".join(c.argv) for c in commands]
    assert any("check_xrefs.py" in c and "--strict" in c for c in joined), (
        "check_xrefs must arrive WITH --strict; without it the gate prints WARN and exits 0"
    )


def test_installs_and_apt_are_not_mistaken_for_gates() -> None:
    """`pip install ruff` is a step; it is not something this repo verifies."""
    joined = [" ".join(c.argv) for c in run_checks.gate_commands(WORKFLOW, ROOT)]
    assert not any("pip" in c or "apt-get" in c for c in joined), joined


def test_a_run_block_step_is_seen() -> None:
    """`run: |` is a multi-line scalar. A line-by-line reader misses it entirely.

    `test_ci_targets_exist.py` reads `run:` lines and therefore cannot see the
    code-quality step; this parses YAML so that it can.
    """
    joined = " ".join(" ".join(c.argv) for c in run_checks.gate_commands(WORKFLOW, ROOT))
    assert "run_code_quality.py" in joined


def test_gates_ci_never_invokes_are_reported_rather_than_omitted() -> None:
    """The whole point: what is NOT checked has to be named."""
    report = run_checks.build_report(ROOT, results=[], unreached=["check_install_drift"])
    assert any("check_install_drift" in item for item in report.not_checked)


def test_an_unreadable_workflow_is_unmeasured_not_a_pass() -> None:
    missing = ROOT / ".github" / "workflows" / "does-not-exist.yml"
    assert run_checks.gate_commands(missing, ROOT) == []


def test_zero_surviving_commands_is_refused(tmp_path: Path) -> None:
    """An empty list is not a pass — `run_gates.sh` carries the same refusal."""
    workflow = tmp_path / "ci.yml"
    workflow.write_text(
        "on: push\njobs:\n  a:\n    steps:\n      - run: pip install ruff\n", encoding="utf-8"
    )
    assert run_checks.gate_commands(workflow, tmp_path) == []
    assert run_checks.main(["--root", str(tmp_path), "--workflow", str(workflow)]) == UNMEASURED


def test_the_gate_inventory_is_globbed_not_listed() -> None:
    """A hard-coded gate list would go stale the day a gate is added."""
    names = run_checks.known_gates(ROOT)
    assert "check_xrefs" in names
    assert "verify_ecosystem" in names
    assert len(names) >= 20, f"only {len(names)} gates found; the glob is wrong"


def test_a_call_site_that_is_a_string_literal_is_still_a_call() -> None:
    """`verify_ecosystem` invokes its siblings by building a path out of strings.

    The first implementation stripped string literals before matching — borrowing the
    lens from `test_every_gate_is_reachable.py`, which strips them for good reason: it
    asks "does anything call this gate", where a mention in prose is a false positive.

    This asks the narrower question "which gates does this script name in code", and
    there the filename in a string IS the answer. Stripping strings hid every call site
    and reported 13 gates as unreached when 8 of them run inside `verify_ecosystem`.
    """
    reached = run_checks.reached_within(ROOT, ["mechanisms/gates/verify_ecosystem.py"])
    assert "check_skill_map" in reached, (
        "verify_ecosystem builds `.../check_skill_map.py` as a string; that is a call"
    )
    assert len(reached) >= 5, f"only {sorted(reached)} — the string lens is too narrow"


def test_a_gate_named_only_in_a_comment_is_not_counted_as_reached() -> None:
    """`ci.yml` mentions check_reference_leakage in a comment and never runs it.

    A mention is not a call. This is the half of the lens that must stay strict.
    """
    joined = " ".join(" ".join(c.argv) for c in run_checks.gate_commands(WORKFLOW, ROOT))
    assert "check_reference_leakage" not in joined


def test_a_failing_line_names_the_step_not_an_argument() -> None:
    """`ruff check mechanisms squad ... conftest.py` is not "conftest.py".

    The first implementation showed the first `.py` token, which for a linter run over
    several trees is the LAST argument. A reader chasing a failure was pointed at a file
    that is not the subject.
    """
    report = run_checks.build_report(
        ROOT,
        results=[
            run_checks.Result(
                run_checks.Command("Python static trajectory-review",
                                   ["ruff", "check", "mechanisms", "conftest.py"]),
                1, "Found 52 errors.",
            )
        ],
        unreached=[],
    )
    body = "\n".join(report.lines)
    assert "Python static trajectory-review" in body, body
    assert not body.strip().endswith("conftest.py"), body


def test_a_single_script_step_still_names_the_script() -> None:
    """When the command IS one script, the script is the most useful label."""
    report = run_checks.build_report(
        ROOT,
        results=[
            run_checks.Result(
                run_checks.Command("Cross-reference validator (strict)",
                                   ["python3", "mechanisms/gates/check_xrefs.py", "--strict"]),
                0, "",
            )
        ],
        unreached=[],
    )
    assert "check_xrefs.py" in "\n".join(report.lines)


def test_a_failing_command_carries_its_whole_output_in_json() -> None:
    """The same lesson as `sq test`, which was fixed there and left broken here.

    `sq test` used to print FAIL and discard the pytest output; that was fixed. This
    command replays `run_slice_tests.sh` as one of its steps, so when a suite fails
    inside it the reason arrives here — and the text renderer showed the last three
    lines, which for a suite failure are the summary and nothing else.

    Truncating for the human is fine. Truncating in `--json` is the false-coverage
    report all over again: a consumer gets a FAIL it cannot act on.
    """
    tail = "\n".join([f"line {i}" for i in range(40)] + ["E   assert 1 == 2"])
    report = run_checks.build_report(
        ROOT,
        results=[run_checks.Result(run_checks.Command("suites", ["bash", "x.sh"]), 1, tail)],
        unreached=[],
    )
    assert "failure_output" in report.detail, "--json must carry the reason, whole"
    # Keyed by the same label the human view shows, so the two halves line up.
    captured = report.detail["failure_output"]["x.sh"]
    assert "assert 1 == 2" in captured
    assert "line 0" in captured, "the head was truncated away"


def test_the_human_view_shows_more_than_three_lines() -> None:
    """Three lines of a pytest failure is the summary and none of the cause."""
    tail = "\n".join([f"line {i}" for i in range(40)])
    report = run_checks.build_report(
        ROOT,
        results=[run_checks.Result(run_checks.Command("suites", ["bash", "x.sh"]), 1, tail)],
        unreached=[],
    )
    shown = [ln for ln in report.lines if "line " in ln]
    assert len(shown) > 3, f"only {len(shown)} lines shown"
