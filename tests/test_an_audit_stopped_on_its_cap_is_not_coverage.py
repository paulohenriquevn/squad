"""An auditor that stopped on its iteration cap did not cover the change.

A `loop-*` run that hits its cap ends through the plugins' shared termination guard
(`terminal_report.py guard` → `render_fallback`), which writes an honest report:
`Status: INCOMPLETE`, a `## Verdict` that opens with `INCOMPLETE`, and every severity
subsection `_(not enumerated …)_`. That report satisfies the plugin's own structural
checker — reproduced 2026-09-25 against loop-code-review 0.6.4: `{"ok": true}`, exit 0
— and structural validity was the only test this gate applied, so the audit was
recorded `covered` and produced no finding.

It is not a rare path. `rules/review-auditors.txt` sets `max_iterations = 40`, below
every plugin's own default, so the cap is the expected end of a non-trivial audit.

The fixture beside this file is that guard's real output, generated with
`terminal_report.py guard --output-dir … --plugin loop-code-review --phase 2
--phase-name sweep --reason max_global_iterations --attempts 5 --max-attempts 3`.
It is checked in rather than regenerated so the test does not depend on what
happens to be installed.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "tests"))
sys.path.insert(0, str(_REPO / "mechanisms" / "gates"))

from check_auditor_coverage import (  # noqa: E402
    NOT_COVERED,
    auditor_coverage_findings,
    check,
    severity_counts,
)
from test_check_auditor_coverage import _config, _plugin, _project  # noqa: E402

STOPPED = (_REPO / "tests" / "fixtures" / "auditor_report_stopped_on_its_cap.md").read_text(
    encoding="utf-8")


def test_a_report_stopped_on_its_cap_is_incomplete_not_covered(tmp_path: Path) -> None:
    code, result = check("B-014", project=_project(tmp_path, report=STOPPED),
                         config_dir=_config(tmp_path, _plugin(tmp_path, "loop-code-review")))

    assert code == NOT_COVERED
    assert result["auditors"][0]["state"] == "incomplete"


def test_it_is_incomplete_even_when_the_plugin_checker_rejects_it(tmp_path: Path) -> None:
    """Three plugins reject the fallback today over its numeric Scoring Card, and the
    finding then blamed a malformed report. Fixing that plugin-side would silently turn
    them into `covered`; the stop condition is the fact, whatever the checker says."""
    code, result = check(
        "B-014", project=_project(tmp_path, report=STOPPED),
        config_dir=_config(tmp_path, _plugin(tmp_path, "loop-code-review", accepts=False)))

    assert code == NOT_COVERED
    assert result["auditors"][0]["state"] == "incomplete"


def test_an_incomplete_audit_is_a_blocker_naming_what_stopped_it(tmp_path: Path) -> None:
    findings = auditor_coverage_findings(
        _project(tmp_path, report=STOPPED), "B-014",
        config_dir=_config(tmp_path, _plugin(tmp_path, "loop-code-review")))

    assert [f["severity"] for f in findings] == ["BLOCKER"]
    assert "max_global_iterations" in findings[0]["evidence"]
    assert "What Was NOT Analyzed" in findings[0]["remediation"]


def test_a_stopped_report_carries_no_severity_signal() -> None:
    """`_(not enumerated …)_` is the fallback's empty-subsection sentinel. Read as a
    finding, it labelled a report that enumerated nothing with all five severities."""
    assert not any(severity_counts(STOPPED).values())
