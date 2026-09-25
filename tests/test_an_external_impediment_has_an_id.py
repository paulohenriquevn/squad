"""An impediment nobody can resolve here still gets a number.

THE GAP THIS CLOSES
-------------------
`blocked_by` is prose that MAY name ids, and `cycle-backlog.md` records what that
measured: *"of the eight items carrying `blocked_by` when it was measured, seven named
a sponsor decision, a ratification, or a revocation in a hosting panel, and exactly one
named an item."* The parser is right to accept prose — demanding `B-NNN` would have
called seven honest impediments malformed — but the consequence is stated in
`parse_blocked_by`'s own words: *"nothing in this repository can tell you whether a
sponsor has decided."*

Seven of eight impediments therefore:

  - resolve only when a human remembers to delete the line,
  - are invisible to G6 and G7, which verify edges,
  - appear in no report as a thing that is itself pending,
  - and hold their item open with nothing tracking the thing doing the holding.

Imported 2026-09-20 from a cross-read of `gringolito/github-backlog-management`, whose
`/add-external-blocker` files the constraint as a stub issue — on the board, never
milestoned, skipped by execution — and registers it as a real `blocked_by` dependency.
The shape travels; the mechanism is ours, because our registry is a file rather than
the GitHub API.

An external blocker here is an ordinary `B-NNN` carrying `source: external-blocker`.
It is a target for `blocked_by`, so the edge is verifiable and resolves itself the
moment the stub closes. It is never selected, because it is not our work: what closes
it is somebody outside this repository acting.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for _rel in ("skills/backlog-review/scripts", "mechanisms/cycle"):
    _path = str(REPO / _rel)
    if _path not in sys.path:
        sys.path.insert(0, _path)

from check_backlog_structure import check_backlog  # noqa: E402
from select_backlog_item import select  # noqa: E402

STUB = """## B-900 — The sponsor must ratify the data-retention change

domain: data-plane-ts
repo: promptly
source: external-blocker
evidence: none-yet
why_now: the retention window cannot change until legal signs the policy off
status: raw
dod:
  - legal has signed the retention policy, or has refused it in writing
"""

BLOCKED_ITEM = """## B-001 — Reduce the retention window to 30 days

domain: data-plane-ts
repo: promptly
suggested_mode: review
source: human
evidence: docs/retention.ts:12
why_now: the window was widened in 2026-07 and storage grew 40%
status: triaged
blocked_by: B-900
dod:
  - the window is 30 days and a test fails on the old value
"""


def _registry(*blocks: str) -> str:
    return "# Backlog\n\n" + "\n".join(blocks)


def test_the_stub_is_never_handed_out_as_work() -> None:
    """It is not our work. What closes it is somebody outside this repository."""
    result = select(_registry(STUB, BLOCKED_ITEM))

    assert result.item_id != "B-900", "an external blocker is not a thing to go and do"


def test_asking_for_the_stub_by_name_says_why_not() -> None:
    """A refusal that names no reason gets re-asked tomorrow."""
    result = select(_registry(STUB, BLOCKED_ITEM), requested="B-900")

    assert result.verdict == "ITEM_EXTERNALLY_BLOCKED"
    assert "outside" in result.reason.lower() or "external" in result.reason.lower()


def test_the_edge_is_verifiable_where_prose_was_not() -> None:
    """`blocked_by: B-900` resolves against a block. `blocked_by: legal must sign`
    resolves against nothing, which is the whole point of giving it a number."""
    report = check_backlog_from(_registry(STUB, BLOCKED_ITEM))

    assert not [f for f in report["findings"] if f["check"] == "blocker_missing"]


def test_the_item_it_holds_is_reported_blocked() -> None:
    result = select(_registry(STUB, BLOCKED_ITEM))

    assert result.item_id != "B-001", "B-900 is open, so B-001 is held"
    assert "B-001" in (result.walls or {})


def test_closing_the_stub_frees_the_item_with_no_second_edit() -> None:
    """The property prose could never have: resolution needs nobody to remember."""
    closed = STUB.replace("status: raw", "status: shipped")

    result = select(_registry(closed, BLOCKED_ITEM))

    assert result.item_id == "B-001"


def test_a_stub_is_not_asked_for_a_mode_or_an_objective(tmp_path: Path) -> None:
    """`suggested_mode` routes an item to DISCOVER and a stub never goes there;
    `traces_to` says which objective the work serves and a stub is not our work."""
    (tmp_path / ".squad" / "wiki" / "product").mkdir(parents=True)
    (tmp_path / ".squad" / "wiki" / "product" / "objectives.md").write_text(
        "# Objectives\n\n## OBJ-1 — Keep storage flat\nmetric: below 2TB\n"
        "horizon: 2026-Q4\n", encoding="utf-8")
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(_registry(STUB), encoding="utf-8")

    report = check_backlog(backlog)
    codes = {(f["check"], f["item"]) for f in report["findings"]}

    assert ("missing_field", "B-900") not in codes
    assert ("objective_link_missing", "B-900") not in codes


def test_an_ordinary_item_is_still_asked_for_both(tmp_path: Path) -> None:
    """The exemption is for the stub and nothing else."""
    (tmp_path / ".squad" / "wiki" / "product").mkdir(parents=True)
    (tmp_path / ".squad" / "wiki" / "product" / "objectives.md").write_text(
        "# Objectives\n\n## OBJ-1 — Keep storage flat\nmetric: below 2TB\n"
        "horizon: 2026-Q4\n", encoding="utf-8")
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(_registry(BLOCKED_ITEM), encoding="utf-8")

    report = check_backlog(backlog)

    assert any(f["check"] == "objective_link_missing" for f in report["findings"])


def check_backlog_from(text: str):
    import tempfile

    directory = Path(tempfile.mkdtemp())
    path = directory / "BACKLOG.md"
    path.write_text(text, encoding="utf-8")
    return check_backlog(path)
