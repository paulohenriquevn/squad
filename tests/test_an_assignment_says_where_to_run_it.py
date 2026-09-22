"""A commissioned audit says which directory its commands must run from.

WHY THIS EXISTS
---------------
`select_auditors.py` emits an ABSOLUTE `--output-dir` under the project's write root,
because the report has to land where `check_auditor_coverage.py` will look for it.
Every `loop-*` plugin confines `--output-dir` under its own working directory —
`scripts/lib/path_safety.py`, a path-traversal fix.

Both halves are right. The join holds only when the command runs from the project
root, and measured 2026-09-22 nothing on either side said so: `skills/review/SKILL.md`
said "Run each command the assignment prints, exactly as printed", and the plugin's
refusal reads `--output-dir is unsafe (escapes current directory)` — which names the
flag, not the directory the reader is standing in.

That misdirection is the expensive half. Acting on it means changing the output
directory, and the output directory is the one thing that must not change: this kit
derives it and will look for the report exactly there.

WHAT THIS DOES NOT CLAIM
------------------------
That the agent obeys. Nothing here executes the commands. It asserts the assignment
CARRIES the premise — the prose and the JSON both — so an agent following it, and a
person reading it afterwards, have the fact in front of them.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SELECT = REPO / "mechanisms" / "cycle" / "select_auditors.py"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SELECT), *args],
                          capture_output=True, text=True, check=False, cwd=REPO)


def test_the_json_assignment_names_the_directory_to_run_from() -> None:
    proc = _run("--slug", "run-from-probe", "--domains", "security", "--json")
    payload = json.loads(proc.stdout)
    assert payload.get("run_from") == str(REPO), (
        "the assignment must name the directory its commands run from — every "
        f"plugin confines --output-dir under its own CWD.\n{proc.stdout}")


def test_the_printed_assignment_says_it_too() -> None:
    proc = _run("--slug", "run-from-probe", "--domains", "security")
    assert "run from" in proc.stdout.lower(), (
        "the human-readable assignment is what an agent reads; the premise has to be "
        f"in it, not only in the JSON.\n{proc.stdout}\n{proc.stderr}")
    assert str(REPO) in proc.stdout, proc.stdout


def test_a_project_with_no_auditor_declares_nothing_to_run_from() -> None:
    """No auditors, no commands — the field would be a claim about work nobody does.

    Asserted so the line above cannot become boilerplate printed on every path,
    including the ones where there is nothing to run.
    """
    proc = _run("--slug", "run-from-probe", "--domains", "security",
                "--project", "/nonexistent-project-for-this-test", "--json")
    payload = json.loads(proc.stdout or "{}")
    assert payload.get("status") != "selected"
    assert "run_from" not in payload, payload
