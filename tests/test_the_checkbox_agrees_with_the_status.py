"""B-200 — the `[x]` on a `## B-NNN` heading looked like state and was not.

Nothing reads it. Measured across the kit 2026-09-19: a grep over every `.py`/`.sh`/`.ts` returns
only alignment-brief sign-off checkboxes, never this one. `status:` is what every mechanism reads.

Two representations of one fact, and only one of them maintained, so they diverged: measured on a
consumer 2026-09-21, **46 of 95** headings contradicted their own status line — items filed
`shipped` and `killed` still carrying `[ ]`.

A marker that looks like state and is not is worse than no marker, because a reader who trusts it
reads the OPPOSITE of the truth. This makes it derived: the checkbox is a rendering of `status:`,
a gate reports the drift, and the index generator normalises it when it writes.

## Why derived rather than removed

Removing it is the other half of the item's either/or and it is the better end state — one fact,
one representation. It also edits `rules/cycle-backlog.md § Item schema`, which `rules/README.md`
marks LOCKED: "changes require team discussion". Deriving needs no schema change and makes the
marker honest today; removing stays available to whoever holds that decision.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "backlog-review" / "scripts"))

from check_backlog_structure import check_backlog  # noqa: E402 — post-bootstrap import


def _registry(tmp_path: Path, heading: str, status: str) -> Path:
    (tmp_path / "rules").mkdir(parents=True)
    (tmp_path / "rules" / "domain-routing.txt").write_text(
        "alpha | alpha-repo | agents/alpha.md\n", encoding="utf-8")
    (tmp_path / "agents").mkdir(parents=True)
    (tmp_path / "agents" / "alpha.md").write_text("# alpha\n", encoding="utf-8")
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(
        f"# BACKLOG\n\n## Items\n\n{heading}\n\n"
        "domain: alpha\nrepo: alpha-repo\nsuggested_mode: review\nsource: human\n"
        "evidence: measured somewhere real\nwhy_now: something changed here\n"
        f"status: {status}\napproved_by: human/someone\nkill_reason: measured and did not hold\n"
        "dod:\n  - the endpoint answers within a stated budget, proved by a failing-first test\n",
        encoding="utf-8")
    return backlog


def _kinds(report: dict) -> list[str]:
    return [f["check"] if isinstance(f, dict) else f.check for f in report["findings"]]


def test_an_unticked_box_on_a_shipped_item_is_reported(tmp_path: Path) -> None:
    report = check_backlog(_registry(tmp_path, "## B-001 — A closed item   [ ]", "shipped"))
    assert "checkbox_contradicts_status" in _kinds(report), (
        "an item filed `shipped` still carrying `[ ]` reads as open to anyone who trusts the marker"
    )


def test_a_ticked_box_on_an_open_item_is_reported(tmp_path: Path) -> None:
    """The other direction, which is the worse one: it reads as DONE."""
    report = check_backlog(_registry(tmp_path, "## B-001 — An open item   [x]", "triaged"))
    assert "checkbox_contradicts_status" in _kinds(report)


def test_a_box_that_agrees_is_not_reported(tmp_path: Path) -> None:
    """The counter-case, so the finding cannot be satisfied by firing on everything."""
    for heading, status in (("## B-001 — A closed item   [x]", "killed"),
                            ("## B-001 — An open item   [ ]", "triaged")):
        report = check_backlog(_registry(tmp_path / f"case-{status}", heading, status))
        assert "checkbox_contradicts_status" not in _kinds(report), (heading, status)


def test_a_heading_with_no_box_is_not_reported(tmp_path: Path) -> None:
    """The schema shows a box and a registry may predate it. Absence is not disagreement, and
    reporting it would push authors to add a marker this item exists to distrust."""
    report = check_backlog(_registry(tmp_path, "## B-001 — No box at all", "shipped"))
    assert "checkbox_contradicts_status" not in _kinds(report)
