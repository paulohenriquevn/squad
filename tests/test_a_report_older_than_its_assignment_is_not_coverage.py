"""The gate reported coverage using a report from another run, 2h45 older.

`find_report` globs a directory and takes one hit:

    hits = sorted(base.glob(glob))
    return hits[-1] if hits else None

No mtime, no commit, no diff base — confirmed by grep: `mtime|stale|fresh|sha|
commit|diff_base` appear nowhere in the module. The gate answers *"is there a file
called final_report.md at this path?"* and reports the answer as *"the independent
audit happened for this change"*.

Measured on a consumer 2026-09-18:

    gate said   COVERED — 1 independent audit(s) ran and reported
                verdict: 2 blocking findings

    it read     .squad/records/audits/loop-code-review/final_report.md   14:56
    the run     .squad/records/audits/loop-code-review-b011/…report.md   17:41
                                                                        4 blocking

`cycle-review.md` already names the neighbouring risk in its own words — *"an
independent report about the wrong thing is worse than no report, because it reads as
coverage"*. This is that sentence with the axis swapped: right report, wrong change.

WHAT THIS CHECKS, AND WHY IT IS NOT AN MTIME HEURISTIC

The assignment is written when the audit is COMMISSIONED. A report older than the
assignment cannot be the audit the assignment asked for — it existed before anyone
asked. That is an ordering fact the gate already has both sides of, and it needs no
cooperation from the plugin, whose report contract belongs to the plugin
(`cycle-review.md`) and not here.

It does NOT claim the converse. A report newer than the assignment may still be about
the wrong change, and proving otherwise needs a `diff_base` the plugin would have to
declare. The gate says what it verified and stops, rather than reporting the stronger
claim it cannot support.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "mechanisms" / "gates"))
sys.path.insert(0, str(_ROOT / "mechanisms" / "cycle"))

from check_auditor_coverage import find_report  # noqa: E402 — post-bootstrap


def _aged(path: Path, seconds_ago: int) -> None:
    when = time.time() - seconds_ago
    os.utime(path, (when, when))


def test_a_report_written_before_the_assignment_is_refused(tmp_path: Path) -> None:
    """The consumer's exact shape: a report from an earlier run sitting in the path."""
    out = tmp_path / "audits" / "loop-code-review"
    out.mkdir(parents=True)
    report = out / "final_report.md"
    report.write_text("# from an earlier run\n", encoding="utf-8")
    _aged(report, 9900)          # 2h45 ago

    assignment = tmp_path / "assignment.json"
    assignment.write_text(json.dumps({"slug": "x"}), encoding="utf-8")

    found = find_report(tmp_path, str(out), "final_report.md",
                        commissioned_at=assignment.stat().st_mtime)

    assert found is None, (
        f"a report older than the assignment that commissioned it was accepted as "
        f"coverage: {found}")


def test_a_report_written_after_the_assignment_is_accepted(tmp_path: Path) -> None:
    """The half that must not go quiet. An audit run after being asked for is the
    normal case and has to keep working."""
    out = tmp_path / "audits" / "loop-code-review"
    out.mkdir(parents=True)
    assignment = tmp_path / "assignment.json"
    assignment.write_text(json.dumps({"slug": "x"}), encoding="utf-8")
    _aged(assignment, 600)

    report = out / "final_report.md"
    report.write_text("# from this run\n", encoding="utf-8")

    found = find_report(tmp_path, str(out), "final_report.md",
                        commissioned_at=assignment.stat().st_mtime)

    assert found == report, found


def test_without_a_commission_time_the_behaviour_is_unchanged(tmp_path: Path) -> None:
    """Callers that cannot supply one keep the old contract rather than losing the
    report — a gate that started refusing everything would be routed around."""
    out = tmp_path / "audits" / "loop-code-review"
    out.mkdir(parents=True)
    report = out / "final_report.md"
    report.write_text("# whenever\n", encoding="utf-8")
    _aged(report, 9900)

    assert find_report(tmp_path, str(out), "final_report.md") == report
