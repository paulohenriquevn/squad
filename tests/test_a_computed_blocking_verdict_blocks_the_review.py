"""A verdict a plugin's script computed as blocking reaches the review as a BLOCKER.

`read_verdict()` read `verdict.json`, stored it as `verdict_record`, and nothing
downstream consulted it: `gateable` was assigned and never branched on. A plugin whose
script counted ten blocking findings produced a review indistinguishable from one whose
script counted none — the contract existed and had no reader that acted on it.

The line this draws is the one `read_verdict` already draws:

    source: computed, blocking_count > 0   a script counted blocking findings — BLOCKER
    source: derived-by-agent                a model derived it — carried, never gated
    blocking_count null                     the plugin has no notion of blocking — not
                                            read as "none blocking", and not gated on

Coverage stays a separate fact. The audit ran and reported, so the state stays
`covered`; what it FOUND is what blocks, and it travels as its own finding.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "tests"))
sys.path.insert(0, str(_REPO / "mechanisms" / "gates"))

from check_auditor_coverage import auditor_coverage_findings, check  # noqa: E402
from test_check_auditor_coverage import _config, _plugin, _project  # noqa: E402

_COMPUTED = {"schema": 1, "verdict": "INSUFFICIENT", "source": "computed",
             "by": "scripts/devops_database.py:compute_verdict",
             "blocking_count": 10, "generated_at": "2026-09-22T11:34:59Z"}


def _with_verdict(tmp_path: Path, payload: dict) -> tuple[Path, Path]:
    project = _project(tmp_path)
    out = project / ".squad" / "records" / "audits" / "loop-code-review"
    (out / "verdict.json").write_text(json.dumps(payload), encoding="utf-8")
    return project, _config(tmp_path, _plugin(tmp_path, "loop-code-review"))


def test_a_computed_verdict_with_blocking_findings_is_a_blocker(tmp_path: Path) -> None:
    project, cfg = _with_verdict(tmp_path, _COMPUTED)

    findings = auditor_coverage_findings(project, "B-014", config_dir=cfg)

    assert [f["severity"] for f in findings] == ["BLOCKER"]
    assert "INSUFFICIENT" in findings[0]["evidence"]
    assert "10" in findings[0]["evidence"]


def test_the_audit_still_counts_as_covered(tmp_path: Path) -> None:
    """It ran and reported. What it found is a separate fact from whether it ran."""
    project, cfg = _with_verdict(tmp_path, _COMPUTED)

    _, result = check("B-014", project=project, config_dir=cfg)

    assert result["auditors"][0]["state"] == "covered"
    assert result["auditors"][0]["blocking_verdict"] is True


def test_an_agent_derived_blocking_verdict_is_carried_not_gated(tmp_path: Path) -> None:
    project, cfg = _with_verdict(tmp_path, dict(_COMPUTED, source="derived-by-agent",
                                                by="agents/report-writer.md"))

    assert auditor_coverage_findings(project, "B-014", config_dir=cfg) == []


def test_a_computed_verdict_with_no_blocking_findings_adds_nothing(tmp_path: Path) -> None:
    project, cfg = _with_verdict(tmp_path, dict(_COMPUTED, verdict="PASS", blocking_count=0))

    assert auditor_coverage_findings(project, "B-014", config_dir=cfg) == []


def test_no_notion_of_blocking_is_not_gated_on(tmp_path: Path) -> None:
    """`blocking_count: null` is a plugin that does not count blocking findings. Reading
    a block out of its token would be parsing another tool's vocabulary."""
    project, cfg = _with_verdict(tmp_path, dict(_COMPUTED, blocking_count=None))

    assert auditor_coverage_findings(project, "B-014", config_dir=cfg) == []
