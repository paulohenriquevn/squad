"""The cycle did not notice a gate run again and again on the same input.

Measured on a consumer session: four identical runs in 36 seconds with no edit between
them, and 16 `FAIL_SOFT` for one slug in 12 minutes. Each refusal was honest; nothing
said that the same artifact had been refused the same way several times, which is the
point at which rerunning stops being work (#139).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "mechanisms" / "cycle"))

from cycle_events import emit_phase_end, read_events, unchanged_repeats  # noqa: E402 — post-bootstrap import

_CLI = REPO_ROOT / "mechanisms" / "cycle" / "cycle_events.py"


def _project(tmp_path: Path) -> tuple[Path, Path]:
    (tmp_path / ".squad").mkdir()
    artifact = tmp_path / "plan.md"
    artifact.write_text("# plan\n", encoding="utf-8")
    return tmp_path, artifact


def _end(root: Path, artifact: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_CLI), "end", "--cycle", "plan-confidence", "--slug", "demo",
         "--verdict", "FAIL_SOFT", "--artifact", str(artifact), "--project-root", str(root)],
        capture_output=True, text=True, check=True)


def test_an_end_event_records_the_artifact_it_judged(tmp_path: Path) -> None:
    root, artifact = _project(tmp_path)

    emit_phase_end(root, cycle="plan-confidence", slug="demo", verdict="FAIL_SOFT",
                   artifact=artifact)

    assert len(read_events(root)[-1]["artifact_sha256"]) == 64


def test_the_third_identical_verdict_on_an_unchanged_artifact_is_said(tmp_path: Path) -> None:
    root, artifact = _project(tmp_path)

    first, second, third = _end(root, artifact), _end(root, artifact), _end(root, artifact)

    assert "unchanged" not in first.stderr + second.stderr
    assert "3 times" in third.stderr
    assert "unchanged" in third.stderr


def test_an_edit_between_runs_is_not_repetition(tmp_path: Path) -> None:
    root, artifact = _project(tmp_path)

    _end(root, artifact)
    _end(root, artifact)
    artifact.write_text("# plan, edited\n", encoding="utf-8")
    after_edit = _end(root, artifact)

    assert "unchanged" not in after_edit.stderr
    assert unchanged_repeats(read_events(root), cycle="plan-confidence", slug="demo") == 1


def test_an_end_without_an_artifact_is_never_counted_as_unchanged(tmp_path: Path) -> None:
    """No hash is not the same hash. Treating two unknowns as equal would report
    repetition that nobody measured."""
    root, _ = _project(tmp_path)
    for _ in range(3):
        emit_phase_end(root, cycle="plan-confidence", slug="demo", verdict="FAIL_SOFT")

    assert unchanged_repeats(read_events(root), cycle="plan-confidence", slug="demo") == 0
