"""A `pytest` run spanning two skill slices must say so, not fail three collections.

The slices are import-isolated on purpose: in production each skill runs alone with only its own
`scripts/` on `sys.path`, and several ship modules with the same basename and different contents.
`mechanisms/cycle/run_slice_tests.sh` mirrors that by giving each slice its own process, and it exits 0.

What was missing is what happens when somebody does the obvious thing instead. Measured 2026-08-24:

    $ python3 -m pytest skills/discover-plan-confidence/tests skills/discover-confidence/tests
    ERROR skills/discover-plan-confidence/tests/test_check_corner_coverage.py
    ERROR skills/discover-plan-confidence/tests/test_check_plan_completeness.py
    ERROR skills/discover-plan-confidence/tests/test_threshold_resolution.py
    !!!!!!!! Interrupted: 3 errors during collection !!!!!!!!

Three errors, none of them about the contributor's change, and the natural reading is that they
broke something. B-017 hit exactly this and had to stash its changes to prove otherwise.

Note the cause is NOT pytest's import mode — `pyproject.toml` already sets
`--import-mode=importlib`, which governs how pytest imports TEST files and not how a test's own
`import X` resolves. Each slice's `conftest.py` does `sys.path.insert(0, SCRIPTS_DIR)`, so the first
slice collected wins `sys.modules` for the whole session.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def _run(*paths: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "--collect-only", "-q", *paths],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
     check=False)


def test_two_slices_in_one_run_are_refused_with_the_right_command() -> None:
    result = _run(
        "skills/discover-plan-confidence/tests",
        "skills/discover-confidence/tests",
    )

    assert result.returncode != 0, "two slices collected in one process — they share sys.path"
    combined = result.stdout + result.stderr
    # The command, by name. A refusal that only says "do not do that" leaves the reader where the
    # three collection errors left them.
    assert "run_slice_tests.sh" in combined, combined[-2000:]
    assert "ImportError" not in combined, (
        "the guard fired too late — the point is to refuse BEFORE a slice's module is shadowed"
    )


def test_one_slice_alone_still_runs() -> None:
    # The guard must not make the normal case harder. A single slice is how anyone works on one.
    result = _run("skills/discover-confidence/tests")

    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]


def test_the_root_suite_alone_still_runs() -> None:
    result = _run("tests")

    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
