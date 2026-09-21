"""A detector that ran and found nothing is not a detector that did not run.

THE DEFECT THIS CLOSES
----------------------
Measured 2026-09-21 on a repository with a committed orphan function, `vulture`
installed and D1 clean at its default threshold:

    findings_by_detector: {'d3_orphan_export_skipped': …, 'd4_mutation': …,
                           'd2_symbol_fab': …, 'd5_architecture': …}
    skip_reasons: {}

**D1 appears nowhere** — not in the findings, not in the skips, not in
`languages_skipped`. The detector the golden rule lists first ran, found nothing, and
the report is indistinguishable from one where it never ran. Same defect this session
fixed in `/implement`, where SKIP meant two opposite things.

AND WHAT D1 DOES NOT SEE AT ITS DEFAULT
---------------------------------------
The golden rule defines D1 as *"No exported symbol unreachable from a caller or a
test"*. `vulture` scores exactly that class at 60% confidence, and the default is
`min_confidence=80`. Measured on the same file:

    min_confidence=80 → 0 findings
    min_confidence=60 → 2 findings, HARD, "unused function 'orphan_never_called'"

The default is deliberate — the golden rule argues that turning D1 up before the debt
is paid "is how a gate becomes something people work around" — so this does not change
it. What it changes is that the run says what the threshold is hiding, instead of
reporting a clean D1 and leaving the reader to assume there is nothing there.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNNER = REPO / "skills" / "code-quality" / "scripts" / "run_code_quality.py"


def _project(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "thing.py").write_text(
        "def orphan_never_called():\n    return 1\n\n\ndef main():\n    return 2\n",
        encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n', encoding="utf-8")
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "code-quality-languages.txt").write_text(
        (REPO / "rules" / "code-quality-languages.txt").read_text(encoding="utf-8"),
        encoding="utf-8")
    for cmd in (["git", "init", "-q", "."], ["git", "config", "user.email", "t@t"],
                ["git", "config", "user.name", "t"], ["git", "add", "-A"],
                ["git", "commit", "-qm", "seed"]):
        subprocess.run(cmd, cwd=tmp_path, capture_output=True)
    return tmp_path


def _run(root: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(RUNNER), "--repo-root", str(root),
         "--no-audit-write", "--no-network"],
        capture_output=True, text=True)
    return json.loads(proc.stdout[proc.stdout.index("{"):])


def test_every_detector_that_ran_is_named_in_the_report(tmp_path: Path) -> None:
    report = _run(_project(tmp_path))

    ran = report.get("detectors_run") or {}
    assert "d1_dead_code" in ran, (
        "D1 ran and found nothing, and the report does not say it ran — which reads "
        "exactly like a detector that did not")


def test_the_report_says_which_threshold_it_applied(tmp_path: Path) -> None:
    """"D1 clean" is only a complete claim with the number it was clean AT.

    An orphan function is visible to `vulture` at 60% confidence and not counted at the
    default 80, so a clean D1 with no threshold beside it lets the reader assume there
    is nothing there. Counting the below-threshold findings would mean running the
    detector twice; stating the threshold costs nothing and answers the same question.
    """
    report = _run(_project(tmp_path))

    applied = report.get("thresholds_applied") or {}
    assert "vulture.min_confidence" in applied
    assert int(applied["vulture.min_confidence"]) == 80


def test_the_verdict_is_unchanged_by_the_disclosure(tmp_path: Path) -> None:
    """Reporting is not scoring. Below-threshold findings must not move the verdict."""
    report = _run(_project(tmp_path))

    assert "dead_code_unallowlisted_python" not in str(report.get("hard_caps_triggered", []))
