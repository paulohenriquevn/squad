"""The board's model: where each item sits, and whether that was measured or inferred.

The distinction is the point. A board that shows an inference and a measurement in the
same typeface is asserting knowledge it does not have — and the stream is empty in
every fresh clone, so the inferred case is the one most viewers see first.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backlog_fixtures import item_block

from board_state import PHASES, build_state, read_events


def _project(tmp_path: Path, *blocks: str, events: list[dict] | None = None) -> Path:
    (tmp_path / "BACKLOG.md").write_text("# Backlog\n\n" + "".join(blocks), encoding="utf-8")
    if events is not None:
        (tmp_path / "records").mkdir(exist_ok=True)
        (tmp_path / "records" / "cycle-events.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return tmp_path


def _by_id(state: dict) -> dict:
    return {i["id"]: i for i in state["items"]}


def _end(cycle: str, slug: str, verdict: str = "PASS") -> dict:
    return {"type": "cycle:phase:end", "cycle": cycle, "slug": slug,
            "verdict": verdict, "timestamp": "2026-08-31T10:00:00Z"}


# ── position without a stream ─────────────────────────────────────────────────


@pytest.mark.parametrize("status, phase", [
    ("raw", "backlog"), ("triaged", "discover"), ("planned", "plan"),
    ("shipped", "release"), ("killed", "killed"),
])
def test_status_implies_a_phase_when_no_stream_exists(tmp_path: Path, status, phase) -> None:
    extra = "kill_reason: measured otherwise\n" if status == "killed" else ""
    state = build_state(_project(tmp_path, item_block("B-001", status=status, extra=extra)))
    assert _by_id(state)["B-001"]["phase"] == phase


def test_a_position_with_no_stream_is_labelled_derived(tmp_path: Path) -> None:
    state = build_state(_project(tmp_path, item_block("B-001", status="triaged")))
    assert _by_id(state)["B-001"]["position_from"] == "derived"
    assert state["has_stream"] is False


# ── position from the stream ──────────────────────────────────────────────────


def test_an_event_moves_the_item_past_the_phase_that_finished(tmp_path: Path) -> None:
    """A `phase:end` says a phase FINISHED, so the item sits in the next one."""
    project = _project(tmp_path, item_block("B-001", status="triaged"),
                       events=[_end("implement", "B-001", "VALIDATED")])
    item = _by_id(build_state(project))["B-001"]
    assert item["phase"] == "code-quality"
    assert item["position_from"] == "stream"


def test_the_stream_outranks_the_status(tmp_path: Path) -> None:
    """The registry records where an item got to; the stream records what ran."""
    project = _project(tmp_path, item_block("B-001", status="raw"),
                       events=[_end("review", "B-001", "READY_TO_MERGE")])
    assert _by_id(build_state(project))["B-001"]["phase"] == "release"


def test_the_furthest_phase_wins_not_the_last_line(tmp_path: Path) -> None:
    """Events can arrive out of order; position is how far it got, not what came last."""
    project = _project(tmp_path, item_block("B-001", status="triaged"),
                       events=[_end("review", "B-001"), _end("discover", "B-001")])
    assert _by_id(build_state(project))["B-001"]["phase"] == "release"


def test_the_last_verdict_is_carried(tmp_path: Path) -> None:
    project = _project(tmp_path, item_block("B-001", status="triaged"),
                       events=[_end("implement", "B-001", "VALIDATED")])
    assert _by_id(build_state(project))["B-001"]["last_verdict"] == "VALIDATED"


def test_an_item_past_the_last_phase_is_done(tmp_path: Path) -> None:
    project = _project(tmp_path, item_block("B-001", status="shipped"),
                       events=[_end(PHASES[-1], "B-001", "ACCEPTED")])
    assert _by_id(build_state(project))["B-001"]["phase"] == "done"


def test_events_for_other_items_do_not_move_this_one(tmp_path: Path) -> None:
    project = _project(tmp_path, item_block("B-001", status="raw"),
                       item_block("B-002", status="raw"),
                       events=[_end("review", "B-002")])
    assert _by_id(build_state(project))["B-001"]["phase"] == "backlog"


# ── impediments, carried through to the card ──────────────────────────────────


def test_a_live_blocker_marks_the_item_impeded(tmp_path: Path) -> None:
    project = _project(tmp_path, item_block("B-001", status="triaged", extra="blocked_by: B-002\n"),
                       item_block("B-002", status="raw"))
    item = _by_id(build_state(project))["B-001"]
    assert item["blocked"] is True
    assert item["blockers"] == ["B-002"]


def test_a_shipped_blocker_frees_the_item(tmp_path: Path) -> None:
    project = _project(tmp_path, item_block("B-001", status="triaged", extra="blocked_by: B-002\n"),
                       item_block("B-002", status="shipped"))
    assert _by_id(build_state(project))["B-001"]["blocked"] is False


def test_a_prose_impediment_is_shown_with_its_text(tmp_path: Path) -> None:
    """Seven of eight real impediments name no item; the note is all a viewer gets."""
    project = _project(tmp_path, item_block("B-001", status="triaged",
                                            extra="blocked_by: the sponsor must decide\n"))
    item = _by_id(build_state(project))["B-001"]
    assert item["blocked"] is True
    assert item["blockers"] == []
    assert "sponsor" in item["blocked_note"]


def test_a_closed_item_is_never_marked_impeded(tmp_path: Path) -> None:
    project = _project(tmp_path, item_block("B-001", status="shipped", extra="blocked_by: B-002\n"),
                       item_block("B-002", status="raw"))
    assert _by_id(build_state(project))["B-001"]["blocked"] is False


# ── robustness ────────────────────────────────────────────────────────────────


def test_a_truncated_last_event_line_does_not_break_the_board(tmp_path: Path) -> None:
    """An append-only file being written right now ends mid-line. Render anyway."""
    project = _project(tmp_path, item_block("B-001", status="raw"), events=[_end("plan", "B-001")])
    stream = project / "records" / "cycle-events.jsonl"
    stream.write_text(stream.read_text(encoding="utf-8") + '{"type": "cycle:phase', encoding="utf-8")
    assert len(read_events(project)) == 1
    assert build_state(project)["items"]


def test_a_missing_backlog_reports_an_error_rather_than_raising(tmp_path: Path) -> None:
    state = build_state(tmp_path)
    assert state["items"] == []
    assert "error" in state


def test_items_come_back_in_id_order(tmp_path: Path) -> None:
    project = _project(tmp_path, item_block("B-010", status="raw"), item_block("B-002", status="raw"))
    assert [i["id"] for i in build_state(project)["items"]] == ["B-002", "B-010"]


# ── serving beyond this machine ───────────────────────────────────────────────
#
# The registry carries unreleased plans, kill reasons and sponsor decisions. The
# machine this was first exposed on had `ufw` inactive and five ports already open to
# the internet, so "add auth later" would have meant serving a roadmap to anyone who
# scanned the host.


def _main(argv: list[str]) -> int:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from board_server import main as server_main

    argv_backup, sys.argv = sys.argv, ["board_server.py", *argv]
    try:
        return server_main()
    finally:
        sys.argv = argv_backup


def test_a_public_host_without_a_token_is_refused(tmp_path: Path, capsys) -> None:
    (tmp_path / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    assert _main([str(tmp_path), "--host", "0.0.0.0", "--port", "0"]) == 1
    assert "token" in capsys.readouterr().err.lower()


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_loopback_needs_no_token(tmp_path: Path, monkeypatch, host) -> None:
    """The default must stay frictionless, or people work around the gate."""
    import board_server

    (tmp_path / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    seen = {}
    monkeypatch.setattr(board_server, "serve",
                        lambda root, port, h="127.0.0.1", t=None: seen.update(host=h, token=t) or 0)
    assert _main([str(tmp_path), "--host", host, "--port", "0"]) == 0
    assert seen["token"] is None


def test_a_missing_backlog_is_refused_before_any_binding(tmp_path: Path) -> None:
    assert _main([str(tmp_path), "--port", "0"]) == 1
