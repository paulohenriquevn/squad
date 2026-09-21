"""`status_contradicts_body` must be answerable by the author, and only deliberately.

The finding asserts that "a reader has two answers and no way to choose" — its own words. That
is true of a block whose prose says `**closed in code.**` and whose status says `planned`, and it
is NOT true of a block that carries a dated note saying which of the two halves is superseded:
such a reader has one answer and a record of the other.

Nor is it true of a block whose subject IS this detector. Measured on a consumer 2026-09-21: the
item filed to fix this false positive was itself flagged by it, because describing the problem
requires writing the words the matcher looks for. That is the shape `rules/english-only.md`
already solved — *"a detector naming what it detects"* is one of its three legitimate exemptions,
and it is honoured there by a line-level marker with a mandatory reason.

`check_backlog_structure.py` had no such marker: `grep -niE 'backlog-structure:'` returned zero
across the kit. So the only way to clear the finding was to delete prose that was true.

## Why a marker and not a looser matcher

A matcher that stops firing on "resolved" or "superseded" can be disarmed by ordinary prose, and a
check that ordinary prose disarms is worse than no check — it reports clean while the condition
holds. The marker is the opposite: nobody writes `<!-- backlog-structure: ... -->` by accident, it
carries a date, and it names which half lost. That is the second Definition-of-done bullet of the
item this closes, in its own terms.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "backlog-review" / "scripts"))

from check_backlog_structure import check_backlog  # noqa: E402 — post-bootstrap import

_HEAD = """# BACKLOG

## Items

## B-001 — An item whose prose and status disagree   [ ]

domain: alpha
repo: alpha-repo
suggested_mode: review
source: human
evidence: measured somewhere real
why_now: something changed here
status: planned
"""

_CLOSED_PROSE = "remeasured 2026-09-20: **closed in code.** the behaviour is in the tree\n"

_DOD = """dod:
  - the endpoint answers within a stated budget, proved by a failing-first test
"""


def _registry(tmp_path: Path, extra: str = "") -> Path:
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "domain-routing.txt").write_text(
        "alpha | alpha-repo | agents/alpha.md\n", encoding="utf-8"
    )
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "alpha.md").write_text("# alpha\n", encoding="utf-8")
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(_HEAD + _CLOSED_PROSE + extra + _DOD, encoding="utf-8")
    return backlog


def _kinds(report: dict) -> list[str]:
    return [f["check"] if isinstance(f, dict) else f.check for f in report["findings"]]


def test_an_unmarked_contradiction_still_fires() -> None:
    """The counter-case, asserted FIRST so the marker cannot be 'made to work' by weakening the
    finding out of existence."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        report = check_backlog(_registry(Path(d)))

    assert "status_contradicts_body" in _kinds(report), (
        "prose declaring closure with an open status must still raise the finding"
    )


def test_a_dated_marker_naming_the_superseded_half_clears_it() -> None:
    import tempfile

    marker = (
        "<!-- backlog-structure: status_contradicts_body 2026-09-21 — the note above was true on "
        "2026-08-21 and the status field is what answers today -->\n"
    )
    with tempfile.TemporaryDirectory() as d:
        report = check_backlog(_registry(Path(d), extra=marker))

    assert "status_contradicts_body" not in _kinds(report), (
        "a dated marker naming which half is superseded leaves the reader one answer, "
        "which is what the finding asserts is missing"
    )


def test_a_marker_without_a_reason_does_not_count() -> None:
    """A silent opt-out is the thing being prevented, so an opt-out that says nothing is refused
    exactly like the contradiction it was trying to clear. Same rule `english-only.md` states."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        report = check_backlog(
            _registry(Path(d), extra="<!-- backlog-structure: status_contradicts_body -->\n")
        )

    assert "status_contradicts_body" in _kinds(report), (
        "a marker with no date and no reason is an opt-out that explains nothing"
    )
