"""The consolidated report names the auditors it could not read, and where it looked.

THE DEFECTS THIS CLOSES
-----------------------
1. `_read_findings_file` returns `None` for a malformed file and its docstring promises
   the caller "lists the file under `unreadable`, by name, **in the report and in the
   JSON**". Measured 2026-09-21 with three findings files, one carrying broken YAML:

       JSON:      unreadable: ['perf-auditor.yaml']
                  agents_run: ['quiet-auditor', 'security-auditor']
       report.md: "**Reviewers (spawned agents):** 2 (quiet-auditor, security-auditor)"
                  grep -ci "unreadable|perf-auditor" -> 0

   The JSON kept the promise and the markdown did not — and the markdown is the phase's
   declared Output. A reader concludes two auditors ran; three wrote and one could not
   be read.

2. `check_upstream_gate` interpolates `records_dir()` straight into a BLOCKER's evidence,
   and that helper returns `None` when the directory is absent:

       - **Evidence:**  looked in None for `demo-code-quality-*.md`

   "Looked in None" tells nobody where it looked, and it conflates two different facts:
   the audit is missing from a records directory that exists, and there is no records
   directory to look in. The sibling BLOCKER in the same report — `check_auditor_coverage`
   — writes the honest form: "the gate was pointed at the wrong tree — it has NOT
   established that no audit is required".
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONSOLIDATE = REPO / "skills" / "review" / "scripts" / "consolidate_findings.py"

GOOD = """agent: security-auditor
findings:
  - severity: HIGH
    file: src/auth.py
    line: 42
    title: token compared with ==
    detail: use a constant-time comparison
"""

BROKEN = """agent: perf-auditor
findings:
  - severity: MEDIUM
     file: src/slow.py
    line: 7
"""


def _consolidate(tmp_path: Path) -> tuple[dict, str]:
    findings = tmp_path / "findings"
    findings.mkdir()
    (findings / "security-auditor.yaml").write_text(GOOD, encoding="utf-8")
    (findings / "perf-auditor.yaml").write_text(BROKEN, encoding="utf-8")
    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, capture_output=True, check=False)
    report = tmp_path / "report.md"
    proc = subprocess.run(
        [sys.executable, str(CONSOLIDATE), "--findings-dir", str(findings),
         "--output", str(report), "--slug", "demo", "--repo-root", str(tmp_path)],
        capture_output=True, text=True, check=False)
    return json.loads(proc.stdout[proc.stdout.index("{"):]), report.read_text(encoding="utf-8")


def test_the_json_still_names_the_unreadable_file(tmp_path: Path) -> None:
    """Guards the half that already worked."""
    data, _ = _consolidate(tmp_path)

    assert data["unreadable"] == ["perf-auditor.yaml"]


def test_the_markdown_names_the_unreadable_file(tmp_path: Path) -> None:
    _, markdown = _consolidate(tmp_path)

    assert "perf-auditor.yaml" in markdown, (
        "the report is what a person reads; an auditor whose file could not be parsed "
        "vanishes from it while the JSON records the gap")


def test_the_reviewer_count_does_not_read_as_the_whole_roster(tmp_path: Path) -> None:
    """Two ran and three wrote. The line saying "2" must not be the only thing there."""
    _, markdown = _consolidate(tmp_path)

    header = markdown.split("## ")[0]
    assert "unreadable" in header.lower() or "could not be read" in header.lower()


def test_a_missing_records_dir_is_named_rather_than_printed_as_none(tmp_path: Path) -> None:
    _, markdown = _consolidate(tmp_path)

    assert "looked in None" not in markdown, (
        "`records_dir()` returns None when the directory is absent, and the evidence "
        "interpolated it — a BLOCKER whose evidence says where it looked, except it does not")
