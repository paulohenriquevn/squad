"""T1.1 — PythonDetector.detect_dead_code (vulture wrapper) tests.

Per plan v1.3 § T1.1 TDD section: 4 RED tests covering positive/negative
fixture cases plus auditor_unavailable handling plus min-confidence threshold.
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.detectors.python import PythonDetector

pytestmark = pytest.mark.python


def test_python_detector_flags_unused_function(tmp_path: Path, fixtures_dir: Path) -> None:
    """Vulture on the positive fixture MUST report >= 1 dead-code Finding.

    The fixture is COPIED out of the skill tree first, and that is the whole
    point of this test's shape. `.claude` is in `DEFAULT_SKIP_DIRS` on purpose —
    `/code-quality` audits the product, not its own tooling — and the detector
    passes that list to vulture as `--exclude`. In the kit's standalone
    repository the fixture sits at `skills/code-quality/fixtures/...` and is
    scanned; in every consumer the same file sits at
    `.claude/skills/code-quality/fixtures/...` and the exclude swallows it.

    Reported from a consumer on 2026-08-29 as "the detector returns zero on a
    known positive", which reads as the worst kind of defect — green over
    unmeasured. Measured here: vulture reports all three symbols from either
    copy of the file, and the detector reports three from the standalone tree
    and zero from the consumer's. The detector was right both times; the test
    was asking it to scan a directory it is designed to skip.

    Copying to `tmp_path` makes the assertion hermetic in any layout, which is
    what a unit test of a detector should have been from the start.
    """
    src = fixtures_dir / "python" / "dead_code_present"
    target = tmp_path / "dead_code_present"
    shutil.copytree(src, target)

    detector = PythonDetector(min_confidence=60)
    findings = detector.detect_dead_code(target)
    dead_findings = [f for f in findings if f.detector == "d1_dead_code"]
    assert len(dead_findings) >= 1, (
        f"Expected at least 1 dead-code Finding on positive fixture; got {len(dead_findings)}: "
        f"{[f.message for f in findings]}"
    )


def test_python_detector_no_findings_on_clean_fixture(fixtures_dir: Path) -> None:
    """Clean fixture MUST NOT trigger any dead-code Finding (FP guard)."""
    detector = PythonDetector(min_confidence=80)
    findings = detector.detect_dead_code(fixtures_dir / "python" / "clean")
    dead_findings = [f for f in findings if f.detector == "d1_dead_code"]
    assert dead_findings == [], (
        f"Clean fixture must produce zero dead_code Findings; got: "
        f"{[f.message for f in dead_findings]}"
    )


def test_python_detector_emits_auditor_unavailable_when_vulture_missing(
    tmp_path: Path,
) -> None:
    """When the vulture binary is missing, emit auditor_unavailable_vulture SOFT_CAP."""
    detector = PythonDetector()
    with patch("subprocess.run", side_effect=FileNotFoundError("vulture not found")):
        findings = detector.detect_dead_code(tmp_path)
    assert len(findings) == 1
    assert "auditor_unavailable_vulture" in findings[0].allowlist_key
    assert findings[0].severity == "SOFT_CAP"


def test_python_detector_respects_min_confidence_threshold(fixtures_dir: Path) -> None:
    """Setting min_confidence high enough should drop low-confidence findings."""
    detector_low = PythonDetector(min_confidence=60)
    findings_low = detector_low.detect_dead_code(fixtures_dir / "python" / "dead_code_present")

    detector_max = PythonDetector(min_confidence=100)
    findings_max = detector_max.detect_dead_code(fixtures_dir / "python" / "dead_code_present")

    # Higher confidence floor cannot produce MORE findings than lower floor.
    assert len(findings_max) <= len(findings_low)


def test_python_detector_handles_subprocess_timeout(tmp_path: Path) -> None:
    """Subprocess timeout MUST emit a Finding rather than propagating the exception."""
    detector = PythonDetector()
    timeout = subprocess.TimeoutExpired(cmd=["vulture"], timeout=1)
    with patch("subprocess.run", side_effect=timeout):
        findings = detector.detect_dead_code(tmp_path)
    assert len(findings) == 1
    assert "auditor" in findings[0].allowlist_key


@pytest.mark.skipif(
    importlib.util.find_spec("vulture") is None,
    reason="vulture module not importable by the running interpreter",
)
def test_dead_code_is_still_detected_when_no_vulture_binary_is_on_PATH(
    tmp_path: Path, fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D1 must resolve vulture through the interpreter, not through PATH.

    `vulture` ships as a library plus a console script, and only the console
    script lands on PATH. Installing it as a dependency of this skill gives the
    module; whether the `vulture` executable is reachable depends on how the
    install happened (`pip install --user` writes `~/.local/bin`, a venv writes
    its own `bin`, a system package may write neither onto the caller's PATH).

    Measured on a host where the module is importable but no `vulture`
    executable is on PATH: `subprocess.run(["vulture", ...])` raises
    FileNotFoundError, D1 degrades to `auditor_unavailable_vulture` SOFT_CAP,
    and a repository full of dead code audits clean. A gate that reports PASS
    because its auditor never ran is worse than a gate that is absent.

    Emptying PATH is exactly the condition the item was filed on; the module
    stays importable, so a run through `sys.executable -m vulture` is unaffected
    while a bare-name PATH lookup cannot resolve.
    """
    src = fixtures_dir / "python" / "dead_code_present"
    target = tmp_path / "dead_code_present"
    shutil.copytree(src, target)

    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))

    findings = PythonDetector(min_confidence=60).detect_dead_code(target)

    unavailable = [f for f in findings if "auditor_unavailable" in f.allowlist_key]
    assert unavailable == [], (
        "D1 lost its auditor with an empty PATH, so the dead code in the fixture "
        f"went unreported: {[f.message for f in unavailable]}"
    )
    dead_findings = [f for f in findings if f.detector == "d1_dead_code"]
    assert dead_findings, (
        "the positive fixture must still report dead code when PATH carries no "
        "vulture executable"
    )


def test_an_unimportable_vulture_module_caps_the_auditor_instead_of_reporting_clean(
    tmp_path: Path, fixtures_dir: Path
) -> None:
    """Resolving vulture through the interpreter must not trade loud for silent.

    A bare-name PATH lookup that misses raises FileNotFoundError, which D1
    already turns into a SOFT_CAP. `sys.executable -m vulture` against an
    interpreter that cannot import vulture does something worse: it exits 1 with
    the traceback on stderr and NOTHING on stdout, which parses as zero findings
    — a repository of dead code auditing clean with no cap and no warning.

    So the module has to be checked before the run, not inferred from its
    output.
    """
    src = fixtures_dir / "python" / "dead_code_present"
    target = tmp_path / "dead_code_present"
    shutil.copytree(src, target)

    with patch("importlib.util.find_spec", return_value=None):
        findings = PythonDetector(min_confidence=60).detect_dead_code(target)

    assert len(findings) == 1, (
        f"expected exactly one auditor cap; got {[f.message for f in findings]}"
    )
    assert "auditor_unavailable_vulture" in findings[0].allowlist_key
    assert findings[0].severity == "SOFT_CAP"
