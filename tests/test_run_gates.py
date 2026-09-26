"""Gates in parallel, with a ceiling, because a 20-minute pre-push gets skipped.

Measured on a consumer on 2026-09-02: 51 gates in one Taskfile `cmds:` list.
`cmds:` is sequential by definition, so the wall-clock is their SUM and the
pre-push hook inherits it — pushes there ran past twenty minutes. The operator's
rule is ten, and the arithmetic agrees from the other side: a ceiling nobody can
meet is a ceiling that gets bypassed rather than met.

The temptation this file exists to refuse is making the suite fast by running
less of it. Nothing here skips, reorders by importance, or downgrades a gate to a
warning. What changes is that the wall-clock becomes the slowest gate rather than
the sum, and one hang can no longer eat the budget of the other fifty.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_RUNNER = (Path(__file__).resolve().parent.parent / "mechanisms" / "cycle"
           / "run_gates.sh")


def _run(tmp_path: Path, gates: list[str], **flags: object) -> subprocess.CompletedProcess:
    listing = tmp_path / "gates.txt"
    listing.write_text("\n".join(gates) + "\n", encoding="utf-8")
    argv = ["bash", str(_RUNNER), "--list", str(listing)]
    for key, value in flags.items():
        argv += [f"--{key.replace('_', '-')}", str(value)]
    return subprocess.run(argv, capture_output=True, text=True, timeout=180, check=False)


def test_gates_run_concurrently_not_in_sequence(tmp_path: Path) -> None:
    """Three two-second gates take about two seconds, not six. That difference is
    the whole reason this file exists."""
    done = _run(tmp_path, ["sleep 2"] * 3, jobs=3, timeout=30, budget=60)

    assert done.returncode == 0, done.stdout + done.stderr
    # The CLAIM, not the clock. Three 2-second gates at jobs=3 have to finish in well
    # under the 6 seconds running them one after another would take — that inequality
    # is what this runner exists to deliver. Asserting "wall 2s or wall 3s" pinned two
    # exact readings with a one-second tolerance, so the test went red on a loaded
    # machine for a runner that was working perfectly.
    wall = re.search(r"wall (\d+)s", done.stdout)
    assert wall, done.stdout
    assert int(wall.group(1)) < 6, f"no parallelism: {done.stdout}"
    assert "sequential would be 6s" in done.stdout, \
        "the sequential cost must be printed — it is the argument for this runner"


def test_a_gate_that_hits_the_ceiling_is_its_own_finding(tmp_path: Path) -> None:
    """Exit 2, not exit 1. "Slow" and "broken" are different problems and a
    timeout hides which one it was — a gate killed at the ceiling never reported
    whether it would have passed."""
    done = _run(tmp_path, ["sleep 1", "sleep 40"], jobs=2, timeout=3, budget=60)

    assert done.returncode == 2, f"expected the timeout code, got {done.returncode}"
    assert "TIMEOUT" in done.stdout
    assert "slow is a finding, not a pass" in done.stderr


def test_one_hang_does_not_consume_the_budget_of_the_others(tmp_path: Path) -> None:
    """The per-gate timeout, stated as behaviour: the fast gates still report."""
    done = _run(tmp_path, ["sleep 40", "echo alpha", "echo beta"],
                jobs=3, timeout=3, budget=60)

    assert done.returncode == 2
    assert "wall 3s" in done.stdout or "wall 4s" in done.stdout, done.stdout


def test_a_failing_gate_is_reported_with_its_output(tmp_path: Path) -> None:
    """A red gate whose output was swallowed sends the reader back to run it by
    hand, which is most of the cost of a red gate."""
    done = _run(tmp_path, ["echo alpha", "echo 'the reason it failed' >&2; exit 1"],
                jobs=2, timeout=30, budget=60)

    assert done.returncode == 1
    assert "FAIL" in done.stdout
    assert "the reason it failed" in done.stdout


def test_an_empty_list_is_refused_rather_than_passed(tmp_path: Path) -> None:
    """A gate runner that sweeps nothing and reports success is the exact defect
    this kit keeps finding in its own checks."""
    listing = tmp_path / "gates.txt"
    listing.write_text("# only a comment\n\n", encoding="utf-8")

    done = subprocess.run(["bash", str(_RUNNER), "--list", str(listing)],
                          capture_output=True, text=True, timeout=60, check=False)

    assert done.returncode == 64
    assert "not the same as everything passing" in done.stderr


def test_passing_but_over_budget_is_reported_and_not_silently_accepted(tmp_path: Path) -> None:
    """Every gate green and the run still too slow is a real state, and it needs
    its own exit code — otherwise the ceiling is advisory."""
    done = _run(tmp_path, ["sleep 3", "sleep 3"], jobs=2, timeout=30, budget=1)

    assert done.returncode == 3
    assert "against a 1s budget" in done.stderr
    assert "running fewer gates is not a fix" in done.stderr


@pytest.mark.parametrize("word", ["skip", "reorder", "downgrade"])
def test_the_runner_says_what_it_refuses_to_do_to_go_faster(word: str) -> None:
    """The cheapest way to make a suite fast is to run less of it, and a runner
    that does not say so invites exactly that on the next slow day."""
    text = _RUNNER.read_text(encoding="utf-8").lower()

    assert word in text, f"the header does not rule out {word}"


def test_a_quoted_argument_survives_the_dispatcher(tmp_path: Path) -> None:
    """The dispatcher interpolated each gate into `line="{}"` inside `xargs -I{}`, so
    the command text was re-parsed by the shell and its quoting was lost.

    Measured: a gate `grep -q "two words" file` over a file containing exactly that
    became `grep -q two words file`, which printed
    `bash: words <file>: No such file or directory` — AND the runner then printed
    "all 1 gate(s) passed" and exited 0, because the mangled worker never wrote its
    `.rc` and the tally counted only the results that appeared. Two failures in one
    line: a gate that did not run, reported as a gate that passed.
    """
    hay = tmp_path / "hay.txt"
    hay.write_text("two words\n", encoding="utf-8")

    done = _run(tmp_path, [f'grep -q "two words" {hay}'], jobs=1, timeout=30, budget=60)

    assert "No such file" not in done.stdout + done.stderr, (
        "the quoting was lost before the gate ran:\n" + done.stdout + done.stderr)
    assert done.returncode == 0, done.stdout + done.stderr


def test_a_gate_whose_pattern_is_absent_still_fails(tmp_path: Path) -> None:
    """The quoting fix must not make every gate pass."""
    hay = tmp_path / "hay.txt"
    hay.write_text("something else\n", encoding="utf-8")

    done = _run(tmp_path, [f'grep -q "two words" {hay}'], jobs=1, timeout=30, budget=60)

    assert done.returncode != 0, done.stdout + done.stderr


def test_a_gate_that_left_no_result_is_not_counted_as_passing(tmp_path: Path) -> None:
    """The runner compared nothing. A gate whose `.rc` never appeared simply vanished
    from the tally, and the summary reported on the gates that DID report."""
    done = _run(tmp_path, ['echo one', 'echo two', 'echo three'],
                jobs=3, timeout=30, budget=60)

    assert done.returncode == 0, done.stdout + done.stderr
    assert "3 gate(s)" in done.stdout
    # The reconciliation is the proof the runner counted what it DISPATCHED, not what
    # happened to report back. Without it a worker that died left no `.rc` and simply
    # vanished from the tally.
    assert "3 result(s)" in done.stdout, done.stdout
