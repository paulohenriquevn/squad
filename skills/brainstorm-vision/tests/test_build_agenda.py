"""The agenda reports what stalled for want of a person — and reports nothing else.

Two properties matter more than the collection itself:

  - it never writes. An agenda that could act would be a second writer racing
    `backlog_status.py`, and one writer owning the status line is what makes a
    transition refusable at all.
  - it says what it could NOT read. A missing `BACKLOG.md` must not render as an
    empty agenda, or "nothing is waiting on you" becomes a claim nothing checked.
"""
from __future__ import annotations

import sys as _s
from pathlib import Path as _P

for _up in _P(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _s.path.insert(0, str(_up))
        break
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

from squad.paths import write_records_dir, write_wiki_dir  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_agenda import build, render  # noqa: E402

ROUTING = "web | web-console | agents/web.md\napi | search-api | agents/api.md\n"


def _project(tmp_path: Path, backlog: str = "", *, routing: str = ROUTING,
             objectives: str = "") -> Path:
    (tmp_path / "rules").mkdir(parents=True, exist_ok=True)
    (tmp_path / "rules" / "domain-routing.txt").write_text(routing, encoding="utf-8")
    write_records_dir(tmp_path).mkdir(parents=True, exist_ok=True)
    if backlog:
        (tmp_path / "BACKLOG.md").write_text(backlog, encoding="utf-8")
    if objectives:
        d = write_wiki_dir(tmp_path, "product")
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
    (write_records_dir(root) / "B-010-BLOCKED.md").write_text("halted", encoding="utf-8")
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


# ------------------------------------------------------------------ #82


def _traces_registry(tmp_path, items: str, *, objectives: str = "## OBJ-1 — ship it\n\nmetric: 1 by Q4\n"):
    (tmp_path / ".squad" / "wiki" / "product").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".squad" / "wiki" / "product" / "objectives.md").write_text(
        f"# Objectives\n\n{objectives}", encoding="utf-8")
    (tmp_path / "BACKLOG.md").write_text(
        f"# Backlog\n\n## Index\n\n## Items\n\n{items}", encoding="utf-8")
    return tmp_path


def _traces_item(n: int, *, status: str = "shipped", traces: str = "") -> str:
    extra = f"traces_to: {traces}\n" if traces else ""
    return (f"## B-{n:03d} — an item   [x]\n\ndomain: core\nrepo: r\n"
            f"suggested_mode: review\nsource: human\nevidence: measured\n"
            f"why_now: it mattered\nstatus: {status}\n{extra}dod:\n- [x] done\n\n")


def test_a_field_nobody_writes_is_one_finding_not_one_per_item(tmp_path) -> None:
    """#82. `traces_to` is read here and by nothing else — `cycle-backlog.md` declares
    itself the item schema's source of truth and does not list it, and `/backlog-item`
    never asks. So `not traces` was unconditionally true.

    Measured on a consumer: 243 rows, one per shipped item, in a registry where no item
    COULD have traced. And it lands in the one cycle a person attends, which
    `cycle-brainstorm.md` promises will show them "what the machine already knows needs
    you".
    """
    root = _traces_registry(tmp_path, "".join(_traces_item(n) for n in range(1, 11)))

    agenda = build(root)

    assert agenda.purposeless_shipped == [], "one gap must not be reported ten times"
    assert len(agenda.schema_gaps) == 1
    assert agenda.schema_gaps[0]["field"] == "traces_to"


def test_with_no_objectives_the_finding_blames_neither_the_items_nor_the_kit(tmp_path) -> None:
    """Nothing to trace to is not a gap in any item.

    Before 2026-09-11 this said the field was written by nothing, which was true then
    and became false the moment `/backlog-item` grew Q5. What an empty field means now
    depends on whether the project declared objectives at all.
    """
    root = _traces_registry(tmp_path, "".join(_traces_item(n) for n in range(1, 4)))
    # The shared fixture ships an objectives document; this case is the project that
    # never ran the phase, so the document has to go.
    (root / ".squad" / "wiki" / "product" / "objectives.md").unlink()

    gap = build(root).schema_gaps[0]

    assert "never adopted" in gap["why"]
    assert "/brainstorm-objectives" in gap["why"]


def test_with_objectives_declared_an_unlinked_registry_is_a_real_finding(tmp_path) -> None:
    """Here the link WAS available and nobody made it, which is worth saying."""
    root = _traces_registry(tmp_path, "".join(_traces_item(n) for n in range(1, 4)))

    gap = build(root).schema_gaps[0]

    assert gap["written_by"] == "/backlog-item Q5"
    assert "leaves uncovered" in gap["why"]
    # Still one finding about the registry, never one row per shipped item.
    assert build(root).purposeless_shipped == []


def test_a_real_gap_is_still_reported_item_by_item(tmp_path) -> None:
    """The check must keep working where it was right: when SOME items carry the field,
    the ones without it are a real gap and each is actionable on its own."""
    items = _traces_item(1, traces="OBJ-1") + _traces_item(2) + _traces_item(3)
    root = _traces_registry(tmp_path, items)

    agenda = build(root)

    assert agenda.schema_gaps == [], "the field IS written here"
    assert {r["item"] for r in agenda.purposeless_shipped} == {"B-002", "B-003"}


def test_an_objective_that_is_traced_is_not_orphaned(tmp_path) -> None:
    """The other half of the same field: `served` feeds the orphan-objective section."""
    root = _traces_registry(tmp_path, _traces_item(1, traces="OBJ-1"))

    assert build(root).orphan_objectives == []
