"""CI must fail what the gates fail.

THE DEFECT THIS FIXES
---------------------
`check_xrefs.py` has two modes. Without `--strict`, a WARN-severity finding is
printed and the process exits 0 — the literal output carries the WARN line and,
right
below it, `Overall: PASS`. With `--strict`, the same finding exits 1.

`mechanisms/dist/install.sh` always called it with `--strict`. The workflow called it
without. The result, measured 2026-08-26: an installation from a clean clone was
born with `rules/cycle-maintenance.md` pointing at an `agents/README.md`
that did not exist, the installer said `check_xrefs.py: FAIL`, and the CI of the
same commit went green. The gate looked, saw, and approved.

WHY THE TEST READS THE WORKFLOW'S COMMAND INSTEAD OF LOOKING FOR THE FLAG
--------------------------------------------------------------------------
A test doing `assert "--strict" in ci_yml` would match the flag written anywhere
in the file — in a comment, in a disabled step, in a job that does not run. It
would assert about the workflow's TEXT, not about what the
workflow faz.

So this module extracts each step's exact command and RUNS it against a
deliberately corrupted tree. What is asserted is behaviour: given a real defect,
the command CI runs must exit non-zero. That keeps holding if someone replaces
`--strict` with another mechanism — which is exactly what a behaviour test should
allow.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"


def _steps() -> list[dict]:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    out: list[dict] = []
    for job in doc.get("jobs", {}).values():
        out.extend(job.get("steps", []) or [])
    return out


def _step_running(fragment: str) -> dict:
    matches = [s for s in _steps() if fragment in (s.get("run") or "")]
    assert matches, f"no CI step runs {fragment!r} — the gate left the workflow"
    assert len(matches) == 1, f"{fragment!r} aparece em {len(matches)} passos; esperado 1"
    return matches[0]


@pytest.fixture()
def broken_kit(versioned_kit: Path, tmp_path: Path) -> Path:
    """A copy of the kit with exactly the defect that passed green.

    `agents/README.md` is cited by `rules/cycle-maintenance.md`. Removing it
    reproduces the state every clean clone was born in before the fix.
    """
    kit = tmp_path / "broken-kit"
    shutil.copytree(versioned_kit, kit)
    readme = kit / "agents" / "README.md"
    assert readme.is_file(), (
        "agents/README.md is not versioned — this test cannot reproduce the "
        "defect, and the kit is already broken for another reason."
    )
    readme.unlink()
    return kit


def test_ci_xref_step_rejects_a_broken_reference(broken_kit: Path):
    """CI's cross-reference command, run against a broken tree, must fail."""
    run = _step_running("check_xrefs.py")["run"].strip()
    proc = subprocess.run(run, shell=True, cwd=broken_kit, capture_output=True, text=True)  # noqa: PLW1510
    assert proc.returncode != 0, (
        "CI's cross-reference step approved a broken reference.\n"
        f"command: {run}\n"
        f"output:\n{proc.stdout}\n{proc.stderr}"
    )


def test_ci_xref_step_accepts_the_healthy_kit(versioned_kit: Path):
    """And it must approve the intact tree — otherwise the test above would pass by accident."""
    run = _step_running("check_xrefs.py")["run"].strip()
    proc = subprocess.run(run, shell=True, cwd=versioned_kit, capture_output=True, text=True)  # noqa: PLW1510
    assert proc.returncode == 0, (
        f"CI fails the intact kit:\n{proc.stdout}\n{proc.stderr}"
    )


def test_ci_runs_the_install_contract(_broken: None = None):
    """The clean-install regression must be in the workflow, not only on disk.

    `tests/test_clean_install.py` is the only test that sees what another machine
    would receive. If it does not run in CI, it goes back to being a file that
    passed once.
    """
    runs = " ".join((s.get("run") or "") for s in _steps())
    assert "run_slice_tests.sh" in runs or "test_clean_install" in runs, (
        "no CI step runs the suite containing the installation contract"
    )


def _jobs() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8")).get("jobs", {})


def test_the_root_suite_is_not_run_twice_in_the_same_job():
    """Running the same suite twice measures nothing more — it only costs double.

    The main job ran `run_slice_tests.sh` (which already runs `tests`) and, in the
    next step, `pytest tests` again with coverage. Measured 2026-08-26: 45s
    duplicated per run. Coverage is now computed in the single run, with the same
    threshold enforced.
    """
    for name, job in _jobs().items():
        runs = [(s.get("run") or "") for s in (job.get("steps") or [])]
        slice_runner = [r for r in runs if "run_slice_tests.sh" in r]
        if not slice_runner:
            continue
        standalone_root = [
            r for r in runs
            if "run_slice_tests.sh" not in r
            and "pytest" in r
            and " tests" in r
        ]
        assert not standalone_root, (
            f"job {name!r} runs the root suite twice: {standalone_root}"
        )


def test_coverage_threshold_survives_the_deduplication():
    """The de-duplication must not have taken the coverage threshold with it."""
    runs = " ".join((s.get("run") or "") for s in _steps())
    env = " ".join(
        f"{k}={v}"
        for job in _jobs().values()
        for step in (job.get("steps") or [])
        for k, v in (step.get("env") or {}).items()
    )
    assert "cov-fail-under" in runs or "ROOT_SUITE_COV" in runs + env, (
        "no CI step enforces a coverage threshold"
    )


def test_python_setup_caches_dependencies():
    """Four jobs reinstalling the same dependencies on every run is pure cost."""
    missing = []
    for name, job in _jobs().items():
        for step in job.get("steps") or []:
            if str(step.get("uses", "")).startswith("actions/setup-python"):
                if not (step.get("with") or {}).get("cache"):
                    missing.append(name)
    assert not missing, f"setup-python without dependency cache in jobs: {missing}"
