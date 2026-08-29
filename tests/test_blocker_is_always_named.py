"""A BLOCKER that fails the review and does not say what it is.

`check_upstream_gate` injects BLOCKERs when no `/code-quality` verdict can be
found for the slug. That is fail-closed and correct: without proof the upstream
gate passed, a review cannot approve. But those findings carry `title` /
`evidence` / `remediation`, while the renderer reads `file` / `line` / `summary`
— so the report prints `## BLOCKER findings (1)` and then nothing.

Measured on 2026-08-29, reported by a consumer session as "consolidate_findings
exits 1 with empty stderr". Two separate faults sat behind that description:

  1. The verdict JSON goes to STDOUT. A caller that redirects stdout — which the
     project's own smoke validator does — is left with an exit code and silence.
  2. The finding that caused the failure is counted, is decisive, and is not
     rendered. Even reading stdout, a person cannot learn what blocked them.

The second is the one that matters. A gate whose reason cannot be read is a gate
people route around, and this kit has now measured that outcome five times.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "review" / "scripts" / "consolidate_findings.py"


def _run(tmp_path: Path) -> tuple[int, str, str, str]:
    findings = tmp_path / "f"
    findings.mkdir()
    (findings / "smoke.yml").write_text("agent: smoke\nfindings: []\n", encoding="utf-8")
    out = tmp_path / "report.md"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--findings-dir", str(findings),
         "--output", str(out), "--edge-case-coverage-ratio", "1.0"],
        capture_output=True, text=True, cwd=tmp_path,
    )
    return proc.returncode, proc.stdout, proc.stderr, out.read_text(encoding="utf-8")


def test_every_counted_blocker_appears_in_the_report(tmp_path: Path) -> None:
    """The count and the list must agree. A finding nobody can read is a verdict
    nobody can act on."""
    _, stdout, _, report = _run(tmp_path)
    counted = json.loads(stdout)["findings_by_severity"]["BLOCKER"]
    if counted == 0:
        return

    section = report.split("## BLOCKER findings", 1)[1]
    section = section.split("\n## ", 1)[0]
    body = [l for l in section.splitlines()[1:] if l.strip()]
    assert body, (
        f"the report counts {counted} BLOCKER(s) and lists none — "
        f"the section is a heading with nothing under it")

    # And each entry must be NAMED. The gate's findings carry `title`; the
    # renderer read `summary`, so the heading came out as `### : ` — present,
    # counted, decisive, and anonymous. Evidence without a name makes a reader
    # reconstruct the finding from its remediation text.
    headings = [l for l in body if l.startswith("### ")]
    assert headings, "no finding heading under the BLOCKER section"
    for h in headings:
        assert h.strip(" #:").strip(), f"a BLOCKER is rendered with no title: {h!r}"


def test_a_non_zero_exit_says_why_on_stderr(tmp_path: Path) -> None:
    """Exit 1 with empty stderr is indistinguishable from a crash.

    That is exactly how this reached the consumer session that reported it.
    """
    rc, _, stderr, _ = _run(tmp_path)
    if rc == 0:
        return
    assert stderr.strip(), f"exit {rc} with nothing on stderr"
    assert "BLOCKER" in stderr or "verdict" in stderr.lower(), stderr
