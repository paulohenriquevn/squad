"""Heavy work belongs on the runner, and this is a mechanism because intent failed.

Measured on 2026-09-02, mid-session: 15 heavy processes on the workstation at
load 18.9 across 12 cores, and ZERO on the runner at load 8.0 across 8, with four
Claude sessions idle there. Four pipeline runs, a 23-agent audit, a 7-way parallel
repair and several full suites had all been run locally, on the machine that was
not bought for it.

The operator had corrected this once already and it recurred within hours. What
recurs after a correction is not an intent problem, so it gets a script.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

_SCRIPT = (Path(__file__).resolve().parent.parent / "mechanisms" / "fleet"
           / "run_remote.sh")


def _run(*argv: str, **kw: object) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(_SCRIPT), *argv],
                          capture_output=True, text=True, timeout=90, check=False, **kw)


def test_an_unreachable_runner_fails_loudly_and_does_not_run_locally() -> None:
    """A fallback to local is how the work comes home without anyone deciding it
    should — which is exactly how this session drifted back to the workstation
    after being corrected."""
    done = _run("--host", "nobody@203.0.113.1", "--in", "/tmp", "--", "echo", "ran-anyway")

    assert done.returncode == 69, done.stderr
    assert "NOT falling back to local" in done.stderr
    assert "ran-anyway" not in done.stdout, "it ran the command here"


def test_a_command_is_required() -> None:
    done = _run("--in", "/tmp")

    assert done.returncode == 64
    assert "no command after --" in done.stderr


def test_a_directory_is_required() -> None:
    """Running in whatever directory ssh lands in is how a command touches the
    wrong checkout."""
    done = _run("--", "echo", "x")

    assert done.returncode == 64
    assert "usage:" in done.stderr


def test_the_reason_it_exists_is_recorded_where_it_is_read() -> None:
    """A rule with its measurement attached survives a rewrite; one without it is
    trimmed as boilerplate on the next pass."""
    text = _SCRIPT.read_text(encoding="utf-8")

    assert "load 18.9" in text and "ZERO on the runner" in text
    assert "not an intention problem" in text
