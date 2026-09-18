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

import os
import subprocess
from pathlib import Path

_SCRIPT = (Path(__file__).resolve().parent.parent / "mechanisms" / "fleet"
           / "run_remote.sh")


def _run(*argv: str, **kw: object) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(_SCRIPT), *argv],
                          capture_output=True, text=True, timeout=90, check=False, **kw)


def test_an_unreachable_runner_fails_loudly_and_does_not_run_locally(tmp_path: Path) -> None:
    """A fallback to local is how the work comes home without anyone deciding it
    should — which is exactly how this session drifted back to the workstation
    after being corrected.

    The unreachable host is now a STUB `ssh` on PATH that exits non-zero, not a real
    connection to 203.0.113.1. That address is in the documentation range and is not
    routable, but the test still opened an outbound socket from the root suite and
    waited on it — so the suite's runtime depended on the network stack of whatever
    machine ran it, and in a sandbox with no egress it hung to the 90s timeout. What
    is under test is the SCRIPT's refusal to fall back, and a stub exercises that
    exactly, in milliseconds, with no network at all.
    """
    stub = tmp_path / "bin"
    stub.mkdir()
    (stub / "ssh").write_text(
        '#!/bin/sh\necho "ssh: connect to host: No route to host" >&2\nexit 255\n',
        encoding="utf-8")
    (stub / "ssh").chmod(0o755)
    env = {**os.environ, "PATH": f"{stub}:{os.environ['PATH']}"}

    done = _run("--host", "nobody@a-host-that-does-not-resolve", "--in", "/tmp",
                "--", "echo", "ran-anyway", env=env)

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


# ── the arguments reach the runner as they were written ──────────────────────
#
# `_cmd="$*"` flattened them into one string that the remote LOGIN shell re-parsed,
# so quoting did not survive: `-- grep "foo bar" .` ran `grep foo bar .` there, and
# any `;`, `|`, backtick or `$(...)` in an argument was executed as shell syntax.
# This script is driven programmatically by the fleet, so the arguments are not
# always a human's.


def _captured_ssh(tmp_path: Path, *argv: str) -> str:
    """Run with a stub `ssh` that records the command string it was handed."""
    stub = tmp_path / "bin"
    stub.mkdir(exist_ok=True)
    record = tmp_path / "handed-to-ssh.txt"
    (stub / "ssh").write_text(
        f'#!/bin/sh\nfor a in "$@"; do printf "%s\\n" "$a"; done > "{record}"\nexit 0\n',
        encoding="utf-8")
    (stub / "ssh").chmod(0o755)
    env = {**os.environ, "PATH": f"{stub}:{os.environ['PATH']}"}

    _run("--host", "someone@a-runner", "--in", "/work", "--", *argv, env=env)
    return record.read_text(encoding="utf-8") if record.exists() else ""


def test_a_quoted_argument_stays_one_argument(tmp_path: Path) -> None:
    handed = _captured_ssh(tmp_path, "grep", "foo bar", ".")

    assert "'foo bar'" in handed, handed


def test_shell_metacharacters_are_not_executed_remotely(tmp_path: Path) -> None:
    handed = _captured_ssh(tmp_path, "echo", "a; rm -rf /tmp/nothing")

    assert "'a; rm -rf /tmp/nothing'" in handed, handed


def test_an_apostrophe_survives(tmp_path: Path) -> None:
    handed = _captured_ssh(tmp_path, "echo", "it's here")

    assert "rm" not in handed
    assert "it" in handed and "here" in handed, handed


# ── no runner is nobody's machine, not one person's ──────────────────────────
#
# The default was `paulo@165.227.121.20`: one account on one host, versioned in a
# kit that ships to other repositories. Every consumer got the string and none of
# them get the host, so the failure was an ssh attempt against somebody else's
# server rather than a usage message.


def test_no_runner_is_a_usage_error_not_a_default() -> None:
    done = _run("--in", "/tmp", "--", "echo", "hi",
                env={k: v for k, v in os.environ.items() if k != "SQUAD_RUNNER"})

    assert done.returncode == 64, done.stderr
    assert "no runner" in done.stderr
    assert "SQUAD_RUNNER" in done.stderr, "the reader is not told how to set one"


def test_no_versioned_file_names_a_runner_account() -> None:
    """A user@host in the kit is a machine every consumer is pointed at and none owns."""
    import re as _re
    import subprocess as _sp

    root = Path(__file__).resolve().parents[1]
    listed = _sp.run(["git", "-C", str(root), "ls-files"],
                     capture_output=True, text=True, check=True).stdout.split()
    account = _re.compile(r"\b[a-z][a-z0-9._-]*@(?:\d{1,3}\.){3}\d{1,3}\b")

    offenders: list[str] = []
    for relative in listed:
        if relative == "CHANGELOG.md" or relative.startswith("tests/"):
            continue
        try:
            body = (root / relative).read_text(encoding="utf-8", errors="replace")
        except (OSError, IsADirectoryError):
            continue
        if account.search(body):
            offenders.append(relative)

    assert offenders == [], f"these name a specific account on a specific host: {offenders}"
