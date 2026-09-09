"""The agenda reports what stalled for want of a person — and reports nothing else.

Two properties matter more than the collection itself:

  - it never writes. An agenda that could act would be a second writer racing
    `backlog_status.py`, and one writer owning the status line is what makes a
    transition refusable at all.
  - it says what it could NOT read. A missing `BACKLOG.md` must not render as an
    empty agenda, or "nothing is waiting on you" becomes a claim nothing checked.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_agenda import build, render

ROUTING = "web | web-console | agents/web.md\napi | search-api | agents/api.md\n"


def _project(tmp_path: Path, backlog: str = "", *, routing: str = ROUTING,
             objectives: str = "") -> Path:
    (tmp_path / "rules").mkdir(parents=True, exist_ok=True)
    (tmp_path / "rules" / "domain-routing.txt").write_text(routing, encoding="utf-8")
    (tmp_path / "records").mkdir(parents=True, exist_ok=True)
    if backlog:
        (tmp_path / "BACKLOG.md").write_text(backlog, encoding="utf-8")
    if objectives:
        d = tmp_path / "wiki" / "product"
        d.mkdir(parents=True, exist_ok=True)
        (d / "objectives.md").write_text(objectives, encoding="utf-8")
    return tmp_path


def _item(item_id: str, **fields: str) -> str:
    body = "\n".join(f"{k}: {v}" for k, v in fields.items())
    return f"## {item_id} — Title for {item_id}   [ ]\n\n{body}\ndod:\n  - something checkable\n\n"


def test_a_missing_backlog_is_a_note_not_an_empty_agenda(tmp_path: Path) -> None:
    """"Nothing is waiting on you" must never be said about a file nobody read."""
    ag = build(_project(tmp_path))
    assert any("no BACKLOG.md" in n for n in ag.notes)
    assert "What could not be read" in render(ag)


def test_a_prose_blocker_is_collected_and_an_item_edge_is_not(tmp_path: Path) -> None:
    """`blocked_by: B-100` resolves itself when B-100 ships. A sponsor decision does not."""
    backlog = (
        _item("B-001", domain="web", repo="web-console", status="triaged", blocked_by="B-002")
        + _item("B-002", domain="web", repo="web-console", status="raw")
        + _item("B-003", domain="api", repo="search-api", status="planned",
                blocked_by="the sponsor must pick the cell map")
    )
    ag = build(_project(tmp_path, backlog))
    assert [b["item"] for b in ag.prose_blockers] == ["B-003"]


def test_an_approved_item_still_carries_its_wall_to_the_session(tmp_path: Path) -> None:
    """The status added to the contract on 2026-09-04, exercised rather than assumed.

    This module decides by the TERMINAL set, negatively — `status not in {shipped,
    killed}` — which is why `approved` needed no edit here while five other readers
    did. That shape is the reason, so it is what this pins: rewrite the check as a
    positive list of open statuses and a wall on an approved item goes silent, which
    is the failure mode `approved` already caused everywhere it WAS enumerated.

    Behavioural on purpose. Asserting the file does not contain a positive set would
    pin the spelling; asserting the wall arrives pins the thing that matters.
    """
    backlog = _item("B-005", domain="api", repo="search-api", status="approved",
                    blocked_by="the sponsor must choose between the two vendors")
    ag = build(_project(tmp_path, backlog))
    assert [b["item"] for b in ag.prose_blockers] == ["B-005"]


def test_a_closed_item_does_not_carry_its_blocker_into_the_session(tmp_path: Path) -> None:
    """`cycle-backlog.md` calls a stale `blocked_by` on a closed item an anti-pattern:
    the registry then tells everyone after you that finished work is stuck."""
    backlog = _item("B-004", domain="web", repo="web-console", status="shipped",
                    blocked_by="the sponsor must decide", traces_to="OBJ-1")
    ag = build(_project(tmp_path, backlog))
    assert ag.prose_blockers == []


def test_an_item_in_no_registered_domain_is_unroutable(tmp_path: Path) -> None:
    backlog = _item("B-005", domain="mobile", repo="ios-app", status="raw")
    ag = build(_project(tmp_path, backlog))
    assert [u["item"] for u in ag.unroutable] == ["B-005"]


def test_a_domain_no_item_ever_cited_is_reported_as_unswept(tmp_path: Path) -> None:
    backlog = _item("B-006", domain="web", repo="web-console", status="raw")
    ag = build(_project(tmp_path, backlog))
    assert ag.unswept_domains == ["api"]


def test_an_objective_nothing_serves_is_an_orphan(tmp_path: Path) -> None:
    objectives = (
        "## OBJ-1 — Served objective\nmetric: 10 things\nhorizon: 2026-Q4\n\n"
        "## OBJ-2 — Nobody works on this\nmetric: 5 things\nhorizon: 2027-Q1\n"
    )
    backlog = _item("B-007", domain="web", repo="web-console", status="raw", traces_to="OBJ-1")
    ag = build(_project(tmp_path, backlog, objectives=objectives))
    assert [o["id"] for o in ag.orphan_objectives] == ["OBJ-2"]


def test_shipped_work_tracing_to_no_objective_is_surfaced(tmp_path: Path) -> None:
    """The cheap half of the question `current-constraint.md` says it cannot ask."""
    backlog = (
        _item("B-008", domain="web", repo="web-console", status="shipped", traces_to="OBJ-1")
        + _item("B-009", domain="api", repo="search-api", status="shipped")
    )
    ag = build(_project(tmp_path, backlog))
    assert [p["item"] for p in ag.purposeless_shipped] == ["B-009"]


def test_a_blocked_report_on_disk_becomes_a_halt(tmp_path: Path) -> None:
    root = _project(tmp_path, _item("B-010", domain="web", repo="web-console", status="planned"))
    (root / "records" / "B-010-BLOCKED.md").write_text("halted", encoding="utf-8")
    ag = build(root)
    assert [h["item"] for h in ag.halts] == ["B-010"]


def test_a_killed_item_is_offered_as_signal_not_as_failure(tmp_path: Path) -> None:
    backlog = _item("B-011", domain="web", repo="web-console", status="killed",
                    kill_reason="p95 measured at 120ms; the hypothesis said 900ms")
    ag = build(_project(tmp_path, backlog))
    assert ag.recent_kills[0]["kill_reason"].startswith("p95 measured")
    assert "successful outcome" in render(ag)


def test_a_truncated_kill_list_says_so(tmp_path: Path) -> None:
    """A silent cap reads as 'that was all of them'."""
    backlog = "".join(
        _item(f"B-{i:03d}", domain="web", repo="web-console", status="killed",
              kill_reason=f"reason {i}")
        for i in range(1, 15)
    )
    ag = build(_project(tmp_path, backlog))
    assert len(ag.recent_kills) == 10
    assert any("not listed" in n for n in ag.notes)


def test_building_the_agenda_writes_nothing(tmp_path: Path) -> None:
    """The property that keeps it from racing `backlog_status.py`."""
    root = _project(tmp_path, _item("B-012", domain="web", repo="web-console", status="raw"))
    before = {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}
    build(root)
    after = {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}
    assert before == after
