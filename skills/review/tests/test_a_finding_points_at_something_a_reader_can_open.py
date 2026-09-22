"""A BLOCKER cited `src/this/path/does/not/exist.py:42` and nothing said the path was gone.

`consolidate_findings` carries each finding's `file`, dedupes on `(file, line, …)`, renders
it in the report and computes the verdict from the set. It never opens the path. Probed
2026-09-22: one BLOCKER at a path that exists nowhere produced `NEEDS_FIXES` with no field,
line or heading saying so.

The argument for why that matters is already written in this repository, one gate over, for
the backlog's evidence pointers — `check_evidence_freshness`:

    the evidence cites a path that no longer resolves. That IS a defect: the next reader
    follows the pointer, finds nothing, and cannot tell whether the finding moved or was
    never real.

It applies verbatim to a review finding and was applied to neither. Same shape as the
Coverage Matrix counting a row without opening the task it named: **an identifier counted
rather than resolved.**

WHY IT REPORTS AND DOES NOT BLOCK, which is where this differs from the backlog gate. A
backlog item's evidence points at something that WAS measured, so a dead pointer means the
measurement cannot be re-read. A review finding may legitimately cite a path that does not
exist — *the file is missing* is a defect somebody can report. So the pointer is resolved,
the unresolved ones are named above the findings, and the verdict is left to the caller who
can tell the two apart.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCRIPT = _ROOT / "skills" / "review" / "scripts" / "consolidate_findings.py"

FINDING = """agent: domain-reviewer
findings:
  - id: F1
    severity: {severity}
    title: the thing is broken
    file: {file}
    line: 42
    summary: a defect a reader would go and look at
"""


def _run(tmp_path: Path, *, file: str, severity: str = "BLOCKER") -> tuple[dict, str]:
    findings = tmp_path / "findings"
    findings.mkdir(parents=True)
    (findings / "domain.yml").write_text(
        FINDING.format(file=file, severity=severity), encoding="utf-8")
    (findings / ".upstream-ok").write_text("", encoding="utf-8")
    out = tmp_path / "report.md"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--findings-dir", str(findings),
         "--output", str(out), "--slug", "probe", "--repo-root", str(_ROOT)],
        capture_output=True, text=True, check=False)
    payload: dict = {}
    if "{" in proc.stdout:
        try:
            payload = json.loads(proc.stdout[proc.stdout.index("{"):])
        except json.JSONDecodeError:
            payload = {}
    return payload, out.read_text(encoding="utf-8") if out.is_file() else ""


def test_a_finding_at_a_path_that_does_not_resolve_is_named(tmp_path: Path) -> None:
    payload, _ = _run(tmp_path, file="src/this/path/does/not/exist.py")

    assert payload["unresolved_pointers"] == [
        {"agent": "domain-reviewer", "id": "F1",
         "file": "src/this/path/does/not/exist.py"}
    ], payload


def test_a_finding_at_a_real_path_is_silent(tmp_path: Path) -> None:
    """THE CONTROL. A signal that fires on every review is the same as no signal."""
    payload, _ = _run(tmp_path, file="mechanisms/gates/check_xrefs.py")

    assert "unresolved_pointers" not in payload, payload


def test_a_finding_with_no_file_is_not_an_unresolved_one(tmp_path: Path) -> None:
    """Absent and dead are different answers. A finding about the change as a whole
    carries no path, and reporting it here would make the signal noise."""
    payload, _ = _run(tmp_path, file="")

    assert "unresolved_pointers" not in payload, payload


def test_the_notice_comes_before_the_findings(tmp_path: Path) -> None:
    _, report = _run(tmp_path, file="src/gone.py")

    assert "could not be opened" in report, report
    assert report.index("could not be opened") < report.index("Findings summary by severity")


def test_an_unresolved_pointer_does_not_change_the_verdict(tmp_path: Path) -> None:
    """*The file is missing* is a defect somebody can legitimately report.

    The backlog gate FAILS on a dead pointer because its evidence points at something
    that WAS measured. A review finding may point at what should exist and does not, so
    the caller — who can tell the two apart — keeps the judgement.
    """
    gone, _ = _run(tmp_path / "a", file="src/gone.py", severity="BLOCKER")
    real, _ = _run(tmp_path / "b", file="mechanisms/gates/check_xrefs.py",
                   severity="BLOCKER")

    assert gone["verdict"] == real["verdict"]
