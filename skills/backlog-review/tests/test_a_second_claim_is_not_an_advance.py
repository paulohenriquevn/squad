"""A repeated field is an append log, an advance, or two claims. Only the third is a defect.

`duplicate_field` reports `status` and nothing else, and the narrowing is reasoned:
`partial_progress` four times is an append-one-line-per-increment log a team keeps on
purpose, and `evidence: none-yet` followed by a pointer is an item that advanced.
Reporting either teaches people to override the gate, which is how the real one gets
waved through.

That reasoning assumes the second line is about the SAME item. Measured by a consumer
session 2026-09-18, it was not: B-001 carried two `evidence:` lines and two
`blocked_by:` lines, and the second of each described a DIFFERENT item — B-006, its
authorization work, its piece, its line count — while B-006's own block read
`evidence: none-yet, status: raw`. Someone had pasted one block's fields into another.
The checker read 17 blocks and reported `index_stale`, nothing more.

Two costs, both measured:

  * B-001 stood at `triaged` on another item's evidence. With the foreign lines
    removed the checker immediately emitted `triaged_without_evidence` — the honest
    state, and always the state. Every reader takes one of the duplicates; the other
    is invisible.
  * The two extra lines shifted every pointer below them by exactly 2. Three
    `BACKLOG.md:N` citations in a scored opportunity broke, and three reviewers spent
    a round on it.

The distinction this draws, and it is the whole design: a placeholder followed by a
real value is an ADVANCE and stays silent. Two substantive values are two CLAIMS, and
the block does not say which one is the item's. `blocked_by` has no append semantics
at all — it declares a set of edges, and a second line silently drops the first one's,
which is a hole in the dependency graph rather than an untidy block.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SKILL / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_backlog_structure import check_backlog  # noqa: E402
from test_check_backlog_structure import item_block, write_backlog  # noqa: E402


def _dups(report: dict) -> list[dict]:
    return [f for f in report["findings"] if f["check"] == "duplicate_field"]


def test_two_substantive_evidence_lines_are_two_claims(tmp_path: Path) -> None:
    """The measured case: a second `evidence:` describing another item entirely."""
    backlog = write_backlog(tmp_path, item_block(
        "B-001", status="triaged",
        evidence="src/queue/worker.py:41 — retries are unbounded",
        extra="evidence: src/auth/policy.py:88 — authorization is unenforced on 3 routes\n"))
    dups = _dups(check_backlog(backlog))
    assert len(dups) == 1, dups
    assert dups[0]["severity"] == "blocker"
    assert "evidence" in dups[0]["message"]


def test_a_placeholder_followed_by_a_pointer_is_still_silent(tmp_path: Path) -> None:
    """The exemption that was reasoned for, kept intact. This is an item advancing."""
    backlog = write_backlog(tmp_path, item_block(
        "B-001", status="triaged", evidence="none-yet",
        extra="evidence: src/queue/worker.py:41 — retries are unbounded\n"))
    assert _dups(check_backlog(backlog)) == []


def test_an_append_log_is_still_silent(tmp_path: Path) -> None:
    """`partial_progress` per increment is a log a team keeps on purpose."""
    backlog = write_backlog(tmp_path, item_block(
        "B-001", status="triaged",
        extra=("partial_progress: parser done\npartial_progress: writer done\n"
               "partial_progress: gate wired\n")))
    assert _dups(check_backlog(backlog)) == []


def test_a_second_blocked_by_silently_drops_the_first_edges(tmp_path: Path) -> None:
    """No append semantics here: the last line IS the edge set, and the rest vanish."""
    backlog = write_backlog(tmp_path, item_block(
        "B-001", status="triaged", extra="blocked_by: B-004\nblocked_by: B-006\n"))
    dups = _dups(check_backlog(backlog))
    assert len(dups) == 1, dups
    assert "blocked_by" in dups[0]["message"]
    assert dups[0]["severity"] == "blocker"


def test_a_status_duplicate_still_reports_exactly_once(tmp_path: Path) -> None:
    """The check that already existed keeps its wording — it is cited in a test above."""
    backlog = write_backlog(tmp_path, item_block(
        "B-001", status="raw", extra="status: triaged\n"))
    dups = _dups(check_backlog(backlog))
    assert len(dups) == 1
    assert "raw then triaged" in dups[0]["message"]
