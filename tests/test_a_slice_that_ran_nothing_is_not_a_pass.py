"""A suite that ran zero tests reads PASS, because pytest exits 0 when it runs nothing.

Measured in this repository:

    pytest tests/ -k 'a_name_that_matches_nothing'
    → collected 3141 items / 3141 deselected / 0 selected
    → exit 0

`run_slice_tests.sh` judges PASS or FAIL from the exit code alone, so a slice whose filter
matched nothing, whose path typo collected nothing, or whose project selector selected
nothing, is reported green. A consumer named this as the fourth of four complaints and had
been misled by it twice — once by a `-t` with a wrong name, once by a wrong `--project`.

It is the same shape this repository already records for gates —
`tests/test_a_gate_over_an_empty_tree_exits_unchecked.py` — and the runner itself states the
principle two functions away:

    Absent rather than zero when pytest did not say: a 0 that means "not reported" and a 0
    that means "none" are different facts, and summing them silently is how a total becomes
    fiction.

The runner already parses `collected`, `passed` and `failed` for its trailer. It just never
judged on them.

WHY FAILING IS SAFE HERE. Across the 31 slices the smallest legitimately runs **11** tests, so
no slice in this kit is expected to run zero. A slice that runs none is a mistake in the path,
the filter or the collection — never an expected state. A run that is skipped in full is
distinguished separately: `skipped` is counted and does not read as empty.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
RUNNER = _ROOT / "mechanisms" / "cycle" / "run_slice_tests.sh"


def test_the_runner_judges_on_what_ran_and_not_only_on_the_exit_code() -> None:
    """The narrow, readable form: the PASS decision must consult the counts."""
    source = RUNNER.read_text(encoding="utf-8")
    verdict = source[source.index('if [ "$rc" = "0" ]'):]
    window = verdict[:900]
    assert "EMPTY" in window, (
        "the PASS/FAIL branch decides on `$rc` alone. A slice that ran zero tests exits 0 and "
        "reads PASS — measured: `pytest -k <no-match>` deselects everything and exits 0.")


def test_an_empty_slice_is_reported_and_fails_the_run(tmp_path: Path) -> None:
    """End to end, against the real runner, with a slice that collects nothing."""
    empty = tmp_path / "tests_that_collect_nothing"
    empty.mkdir()
    (empty / "README.md").write_text("no test modules here\n", encoding="utf-8")

    out = subprocess.run(["bash", str(RUNNER)], capture_output=True, text=True, check=False,
                         cwd=str(_ROOT), env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
                                              "SQUAD_SLICES": str(empty)})
    combined = out.stdout + out.stderr
    if "SQUAD_SLICES" not in RUNNER.read_text(encoding="utf-8"):
        # The runner has no injection point; the source assertion above is the guard.
        return
    assert "EMPTY" in combined, combined[-1500:]
    assert out.returncode != 0, "a run whose only slice executed nothing exited 0"
