"""The knob audit grades the kit's thresholds file, never a project's preserved copy.

`test_every_undocumented_knob_is_marked_as_unread` cross-checks
`rules/code-quality-thresholds.txt` against `skills/code-quality/scripts/`. In the kit's
own tree both are the kit's. In a copy install they are not: `install.sh` REPLACES
`skills/` on every run and PRESERVES `rules/*.txt`, because that file is the project's
tuning. Measured 2026-09-24 in a consumer: the test file was byte-identical to upstream,
upstream passed 13, the consumer failed 1 — its preserved copy predated the 13
`NOT READ` marks, so the assertion listed 12 keys the consumer's code had nothing to do
with. Every promotion from that consumer then read `verification: FAILING`.

A preserved project file is not what the kit ships, so in an install the knob tests have
no subject. The same treatment `squad/tests/conftest.py` gives every other test whose
subject does not install: skip, and say why — here, naming the stale keys, because the
drift is real and belongs to the project that owns the file.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_SKILL_ROOT = Path(__file__).resolve().parents[1]

#: A thresholds file as a consumer install preserved it before the kit marked any knob
#: `NOT READ`: keys documented, none marked. Written inline rather than derived from
#: `rules/`, because in an install that directory is the project's and this test would
#: be grading it again.
_STALE_PROJECT_THRESHOLDS = """\
vulture.min_confidence = 80
# knip.exit_code = strict
# coverage.min_percent = 80
"""


def _install_into(project: Path) -> Path:
    """Lay the kit out the way `install.sh` does: code under `.claude/`, project's rules."""
    kit = project / ".claude"
    shutil.copytree(_SKILL_ROOT, kit / "skills" / "code-quality",
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "fixtures"))
    (kit / "rules").mkdir(parents=True)
    (kit / "rules" / "code-quality-thresholds.txt").write_text(
        _STALE_PROJECT_THRESHOLDS, encoding="utf-8")
    return kit


def _run_knob_tests(kit: Path) -> subprocess.CompletedProcess[str]:
    test_file = (kit / "skills" / "code-quality" / "tests"
                 / "test_every_finding_can_be_allowlisted.py")
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-rs", "-q",
         "--rootdir", str(kit), str(test_file), "-k", "knob"],
        cwd=kit, capture_output=True, text=True, timeout=120, check=False)


def test_the_fixture_is_actually_stale() -> None:
    """Guard the premise: without a missing mark the test below proves nothing."""
    assert "NOT READ" not in _STALE_PROJECT_THRESHOLDS
    assert "knip.exit_code" in _STALE_PROJECT_THRESHOLDS


@pytest.fixture(scope="module")
def installed_run(tmp_path_factory: pytest.TempPathFactory) -> subprocess.CompletedProcess[str]:
    """One install, one run: both assertions below read the same outcome."""
    return _run_knob_tests(_install_into(tmp_path_factory.mktemp("consumer")))


def test_a_projects_stale_thresholds_do_not_fail_the_installed_suite(
        installed_run: subprocess.CompletedProcess[str]) -> None:
    assert installed_run.returncode == 0, installed_run.stdout + installed_run.stderr
    assert "failed" not in installed_run.stdout


def test_the_skip_names_the_keys_the_project_copy_left_unmarked(
        installed_run: subprocess.CompletedProcess[str]) -> None:
    """The drift is not the kit's to fail on, and not something to hide either."""
    assert "SKIPPED" in installed_run.stdout, installed_run.stdout
    assert "knip.exit_code" in installed_run.stdout
