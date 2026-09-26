"""A REVIEW does not grade a change whose required independent audits did not happen.

The load-bearing tests are `test_a_required_audit_with_no_report_blocks` and
`test_a_project_declaring_no_auditor_is_not_blocked`. Together they are the whole
design: absence of a REQUIRED audit blocks, and absence of a REQUIREMENT does not.

Every test builds its own plugin, including the checker the gate delegates to. Reading
the real one would make these pass or fail on what happens to be installed — and the
delegation itself is what is under test, not any particular plugin's contract.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mechanisms" / "gates"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mechanisms" / "cycle"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mechanisms" / "conventions"))

from check_auditor_coverage import (
    COVERED,
    NOT_COVERED,
    NOT_INSTALLED,
    UNCHECKED,
    auditor_coverage_findings,
    check,
    section,
    severity_counts,
)

REGISTRY = "auditor = always | loop-code-review | analysis-scoped\n"

#: A report the fake checker accepts, carrying the two sections that must travel.
GOOD_REPORT = """# Fake Report — .

- **Plugin:** loop-code-review v1.0.0

## Verdict

READY: 0 blockers across 3 findings.

## Findings by Severity

### Critical

_(none)_

### High

| # | Title |
|---|---|
| 1 | something real |

## What Was NOT Analyzed

The vendored tree under `third_party/`, which nobody owns here.

## Scope & Methodology

radon and lizard ran; gocyclo was requested and is not installed.
"""


def _plugin(tmp_path: Path, name: str, *, accepts: bool = True) -> Path:
    """A plugin tree with its OWN report checker, which is what the gate must run."""
    root = tmp_path / "installed" / name
    (root / "scripts" / "lib").mkdir(parents=True, exist_ok=True)
    (root / "rules").mkdir(parents=True, exist_ok=True)
    (root / "rules" / "report-schema.local.txt").write_text("id_pattern = ^X$\n",
                                                            encoding="utf-8")
    verdict = "0" if accepts else "1"
    (root / "scripts" / "lib" / "verify_report_format.py").write_text(
        "import sys\n"
        "print('{\"ok\": %s}')\n"
        "raise SystemExit(%s)\n" % ("true" if accepts else "false", verdict),
        encoding="utf-8")
    return root


def _config(tmp_path: Path, *plugins: Path) -> Path:
    cfg = tmp_path / "claude"
    (cfg / "plugins").mkdir(parents=True, exist_ok=True)
    (cfg / "plugins" / "installed_plugins.json").write_text(json.dumps({
        "version": 2,
        "plugins": {f"{p.name}@m": [{"installPath": str(p), "version": "1.0.0"}]
                    for p in plugins}}), encoding="utf-8")
    return cfg


def _project(tmp_path: Path, *, registry: str = REGISTRY, assignment: bool = True,
             report: str | None = GOOD_REPORT) -> Path:
    root = tmp_path / "proj"
    (root / "rules").mkdir(parents=True, exist_ok=True)
    (root / "rules" / "review-auditors.txt").write_text(registry, encoding="utf-8")
    if assignment:
        d = root / ".squad" / "records" / "audits"
        d.mkdir(parents=True, exist_ok=True)
        (d / "B-014-auditors.json").write_text(json.dumps({
            "status": "selected", "slug": "B-014",
            "scope": {"kind": "change", "diff_base": "develop"},
            "required": [{"plugin": "loop-code-review", "domain": "always",
                          "diff_mode": "analysis-scoped",
                          "output_dir": str(root / ".squad" / "records" / "audits" / "loop-code-review"),
                          "report_glob": "final_report.md"}]}), encoding="utf-8")
    if report is not None:
        out = root / ".squad" / "records" / "audits" / "loop-code-review"
        out.mkdir(parents=True, exist_ok=True)
        (out / "final_report.md").write_text(report, encoding="utf-8")
    return root


def test_a_well_formed_report_covers_the_audit(tmp_path: Path) -> None:
    code, result = check("B-014", project=_project(tmp_path),
                         config_dir=_config(tmp_path, _plugin(tmp_path, "loop-code-review")))

    assert code == COVERED
    assert result["auditors"][0]["state"] == "covered"


def test_a_required_audit_with_no_report_blocks(tmp_path: Path) -> None:
    """The load-bearing one. A review that skipped its auditors must not be
    indistinguishable from one where every auditor came back clean."""
    code, result = check("B-014", project=_project(tmp_path, report=None),
                         config_dir=_config(tmp_path, _plugin(tmp_path, "loop-code-review")))

    assert code == NOT_COVERED
    assert result["auditors"][0]["state"] == "no_report"
    assert "did not run" in result["auditors"][0]["detail"]


def test_the_plugins_own_checker_decides_well_formed(tmp_path: Path) -> None:
    """The contract is the plugin's. A second copy of it would diverge on the day it
    changes, and the kit would accept a shape the plugin itself rejects."""
    code, result = check(
        "B-014", project=_project(tmp_path),
        config_dir=_config(tmp_path, _plugin(tmp_path, "loop-code-review", accepts=False)))

    assert code == NOT_COVERED
    assert result["auditors"][0]["state"] == "malformed"


def test_a_plugin_shipping_no_checker_is_not_trusted(tmp_path: Path) -> None:
    bare = tmp_path / "installed" / "loop-code-review"
    bare.mkdir(parents=True)
    code, result = check("B-014", project=_project(tmp_path),
                         config_dir=_config(tmp_path, bare))

    assert code == NOT_COVERED
    assert "ships no report checker" in result["auditors"][0]["validation"]


def test_an_uninstalled_auditor_is_an_access_gap_not_a_defect(tmp_path: Path) -> None:
    code, result = check("B-014", project=_project(tmp_path), config_dir=_config(tmp_path))

    assert code == NOT_INSTALLED
    assert "access" in result["detail"]


def test_a_project_declaring_no_auditor_is_not_blocked(tmp_path: Path) -> None:
    """The other load-bearing one, and the ordering bug it caught.

    Asking for the assignment BEFORE the registry turned "this project requires no
    independent audit" into "this review skipped one", which would have blocked every
    consumer for a step nobody asked it to take.
    """
    code, result = check("B-014",
                         project=_project(tmp_path, registry="# none\n", assignment=False),
                         config_dir=_config(tmp_path))

    assert code == COVERED
    assert result["status"] == "none_declared"


def test_an_unreadable_registry_is_not_read_as_a_project_declaring_no_auditor(
        tmp_path: Path) -> None:
    """`except OSError: declared = []` made every read failure mean "none declared".

    Absence is one OSError among many. A permission bit, a directory where the file
    should be, an I/O error on the volume — each arrived as an empty list, and the very
    next branch turned an empty list into COVERED with the detail "Stated, never
    inferred from an empty result", which is exactly what it was inferring. The gate
    that exists to prove an audit happened returned "no audit required" the moment it
    could not read the file that says which audits are required.
    """
    project = _project(tmp_path, assignment=False)
    registry = project / "rules" / "review-auditors.txt"
    registry.unlink()
    registry.mkdir()  # a directory where the registry belongs: read_text raises IsADirectoryError

    code, result = check("B-014", project=project, config_dir=_config(tmp_path))

    assert code == UNCHECKED, (
        f"an unreadable registry produced {code}, not 'nothing was verified'"
    )
    assert result["status"] == "unchecked"
    assert "IsADirectoryError" in result["detail"] or "directory" in result["detail"].lower(), (
        f"the detail does not name why the registry could not be read: {result['detail']!r}"
    )


def test_an_absent_registry_is_still_a_project_that_declares_no_auditor(
        tmp_path: Path) -> None:
    """The refusal above must not swallow the case it was built around."""
    project = _project(tmp_path, assignment=False)
    (project / "rules" / "review-auditors.txt").unlink()

    code, result = check("B-014", project=project, config_dir=_config(tmp_path))

    assert code == COVERED
    assert result["status"] == "none_declared"


def test_a_declared_requirement_with_no_assignment_blocks(tmp_path: Path) -> None:
    """Nothing can say an audit happened if nothing said it was required."""
    code, result = check("B-014", project=_project(tmp_path, assignment=False),
                         config_dir=_config(tmp_path, _plugin(tmp_path, "loop-code-review")))

    assert code == UNCHECKED
    assert result["status"] == "no_assignment"


def test_the_coverage_caveat_travels_out_of_the_report(tmp_path: Path) -> None:
    """`## What Was NOT Analyzed` is the single thing that stops partial coverage from
    reading as complete. The seam is where an integration drops it."""
    _, result = check("B-014", project=_project(tmp_path),
                      config_dir=_config(tmp_path, _plugin(tmp_path, "loop-code-review")))

    a = result["auditors"][0]
    assert "third_party" in a["not_analyzed"]
    assert "READY" in a["verdict"]
    assert "gocyclo" in a["methodology"]


def test_severity_is_carried_as_a_signal_and_never_gates(tmp_path: Path) -> None:
    """It is a parse of another tool's markdown. This kit's governing sentence cuts
    both ways: an inability to measure must not become a passing measurement, and it
    must not become a failing one either."""
    code, result = check("B-014", project=_project(tmp_path),
                         config_dir=_config(tmp_path, _plugin(tmp_path, "loop-code-review")))

    assert result["auditors"][0]["severity_signal"] == ["High"]
    assert code == COVERED
    assert any("SEVERITY" in n for n in result["not_checked"])


def test_findings_are_blockers_so_the_verdict_cannot_ignore_them(tmp_path: Path) -> None:
    """The shape `check_upstream_gate.py` established: a pre-condition returned as
    findings means the review verdict cannot be computed while ignoring it."""
    findings = auditor_coverage_findings(
        _project(tmp_path, report=None),
        "B-014",
        _config(tmp_path, _plugin(tmp_path, "loop-code-review")))

    assert [f["severity"] for f in findings] == ["BLOCKER"]
    assert findings[0]["source"] == "check_auditor_coverage"


def test_no_findings_when_the_project_requires_no_audit(tmp_path: Path) -> None:
    findings = auditor_coverage_findings(
        _project(tmp_path, registry="# none\n", assignment=False), "B-014",
        _config(tmp_path))

    assert findings == []


def test_an_empty_subsection_sentinel_reads_as_no_findings() -> None:
    assert severity_counts(GOOD_REPORT)["Critical"] is False
    assert severity_counts(GOOD_REPORT)["High"] is True


def test_an_absent_section_is_none_not_empty_string() -> None:
    """`None` says the header was missing; `''` would say it was there and blank, and
    the plugin's own checker treats those differently."""
    assert section(GOOD_REPORT, "Nothing Like This") is None
    assert section(GOOD_REPORT, "Verdict") is not None
