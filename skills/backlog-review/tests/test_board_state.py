"""The board's model: where each item sits, and whether that was measured or inferred.

The distinction is the point. A board that shows an inference and a measurement in the
same typeface is asserting knowledge it does not have — and the stream is empty in
every fresh clone, so the inferred case is the one most viewers see first.
"""
from __future__ import annotations

import re
import json
from pathlib import Path

import pytest

from backlog_fixtures import item_block

from board_state import PHASES, build_state, read_events


def _project(tmp_path: Path, *blocks: str, events: list[dict] | None = None) -> Path:
    (tmp_path / "BACKLOG.md").write_text("# Backlog\n\n" + "".join(blocks), encoding="utf-8")
    # The blocking list is a rule file both the board and the drift checker read.
    # A fixture that omitted it would test a board with no gates at all.
    (tmp_path / "rules").mkdir(exist_ok=True)
    (tmp_path / "rules" / "blocking-verdicts.txt").write_text(
        "INVALID\nFAIL\nFAIL_HARD\nNEEDS_FIXES\nNOT_VALIDATED\n", encoding="utf-8")
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
    ("shipped", "done"), ("killed", "killed"),
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


def test_an_ended_phase_places_the_item_THERE_not_in_the_next_one(tmp_path: Path) -> None:
    """Ending a phase is a fact; entering the next one is a guess.

    It used to advance. Measured on 2026-08-31: an item had sixteen events, all `end`,
    with `code-quality` appearing TEN times — it was iterating against that gate, not
    moving past it. The board put it in `review`, which it had never entered, and the
    operator read the column as where the work was.
    """
    project = _project(tmp_path, item_block("B-001", status="triaged"),
                       events=[_end("implement", "B-001", "VALIDATED")])
    item = _by_id(build_state(project))["B-001"]
    assert item["phase"] == "implement"
    assert item["position_from"] == "stream"


def test_the_stream_outranks_the_status(tmp_path: Path) -> None:
    """The registry records where an item got to; the stream records what ran."""
    project = _project(tmp_path, item_block("B-001", status="raw"),
                       events=[_end("review", "B-001", "READY_TO_MERGE")])
    assert _by_id(build_state(project))["B-001"]["phase"] == "review"


def test_the_last_phase_observed_wins_not_the_furthest(tmp_path: Path) -> None:
    """"Furthest wins" assumes the cycle only moves forward, and it does not.

    Measured on 2026-08-31: an item's last event was `implement FAIL` and the board
    showed `code-quality`, because code-quality sits later in the sequence. The item
    had gone BACK — a plan review rejects returns, and an implementation that fails its
    own gate is worked again. Hiding that is the same defect as predicting the next
    phase, one step removed.
    """
    project = _project(tmp_path, item_block("B-001", status="triaged"),
                       events=[_end("code-quality", "B-001"), _end("implement", "B-001", "FAIL")])
    item = _by_id(build_state(project))["B-001"]
    assert item["phase"] == "implement"
    assert item["last_verdict"] == "FAIL"


def test_going_forward_still_works(tmp_path: Path) -> None:
    """The fix must not turn every stream into a walk backwards."""
    project = _project(tmp_path, item_block("B-001", status="triaged"),
                       events=[_end("plan", "B-001"), _end("implement", "B-001", "VALIDATED")])
    assert _by_id(build_state(project))["B-001"]["phase"] == "implement"


def test_the_last_verdict_is_carried(tmp_path: Path) -> None:
    project = _project(tmp_path, item_block("B-001", status="triaged"),
                       events=[_end("implement", "B-001", "VALIDATED")])
    assert _by_id(build_state(project))["B-001"]["last_verdict"] == "VALIDATED"


def test_finishing_the_last_phase_leaves_the_item_in_it(tmp_path: Path) -> None:
    """There is no `done` column any more: the item is where it was last observed."""
    project = _project(tmp_path, item_block("B-001", status="shipped"),
                       events=[_end(PHASES[-1], "B-001", "ACCEPTED")])
    assert _by_id(build_state(project))["B-001"]["phase"] == PHASES[-1]


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


# ── two slug conventions, both correct ────────────────────────────────────────
#
# Measured on the first real run: 12 events, 6 of them plan slugs, and every one of
# those six invisible on the board — half the execution missing from the view built
# to show it.


@pytest.mark.parametrize("slug, expected", [
    ("b033-prometheus-url-dev-public", "B-033"),   # the plan slug an artefact carries
    ("B-033", "B-033"),                            # the item id the registry keys on
    ("b-014-trace-p95", "B-014"),
    ("B-167", "B-167"),
])
def test_both_slug_conventions_reach_the_same_item(slug, expected) -> None:
    from board_state import item_id_of

    assert item_id_of(slug) == expected


def test_a_slug_naming_no_item_is_left_alone() -> None:
    """Not every event belongs to a backlog item; inventing one would be worse."""
    from board_state import item_id_of

    assert item_id_of("smoke-run") == "SMOKE-RUN"


def test_a_plan_slug_positions_its_item(tmp_path: Path) -> None:
    project = _project(tmp_path, item_block("B-033", status="triaged"),
                       events=[{"type": "cycle:phase:end", "cycle": "implement",
                                "slug": "b033-prometheus-url-dev-public",
                                "verdict": "VALIDATED", "timestamp": "2026-08-31T12:00:00Z"}])
    item = _by_id(build_state(project))["B-033"]
    assert item["position_from"] == "stream"
    assert item["phase"] == "implement"


# ── the supervisor rail ───────────────────────────────────────────────────────
#
# The board showed every item and not whether anything was moving. A session had
# handed its turn back and sat still for two hours, and the only way to find out was
# to attach to a tmux pane and read it.


def _lead_log(tmp_path: Path, *entries: dict) -> Path:
    import json as _json

    path = tmp_path / "lead.jsonl"
    path.write_text("".join(_json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return path


def test_the_decisions_come_back_newest_first(tmp_path: Path) -> None:
    """The question of a supervisor's log is always "what just happened"."""
    from board_state import read_lead

    log = _lead_log(tmp_path,
                    {"event": "confirm", "item": "B-001", "at": "2026-08-31T10:00:00+00:00"},
                    {"event": "stalled", "item": "", "at": "2026-08-31T12:00:00+00:00"})
    assert [d["event"] for d in read_lead(log, None)["decisions"]] == ["stalled", "confirm"]


def test_the_marker_says_how_long_the_session_has_been_quiet(tmp_path: Path) -> None:
    import os
    import time as _time

    from board_state import read_lead

    marker = tmp_path / "run.log"
    marker.write_text("x", encoding="utf-8")
    old = _time.time() - 600
    os.utime(marker, (old, old))
    lead = read_lead(None, marker)
    assert lead["watching"] is True
    assert 590 <= lead["idle_seconds"] <= 610


def test_no_supervisor_yields_empty_fields_not_missing_ones(tmp_path: Path) -> None:
    """The page renders one way; a board with no lead is the normal case."""
    from board_state import read_lead

    lead = read_lead(None, None)
    assert lead == {"decisions": [], "idle_seconds": None, "watching": False}


def test_an_absent_marker_is_not_watching(tmp_path: Path) -> None:
    from board_state import read_lead

    assert read_lead(None, tmp_path / "nope.log")["watching"] is False


def test_a_truncated_last_decision_does_not_break_the_rail(tmp_path: Path) -> None:
    """The log is appended to while the board reads it."""
    from board_state import read_lead

    log = _lead_log(tmp_path, {"event": "confirm", "item": "B-001"})
    log.write_text(log.read_text(encoding="utf-8") + '{"event": "sta', encoding="utf-8")
    assert len(read_lead(log, None)["decisions"]) == 1


def test_the_rail_reaches_the_board_state(tmp_path: Path) -> None:
    project = _project(tmp_path, item_block("B-001", status="raw"))
    log = _lead_log(tmp_path, {"event": "confirm", "item": "B-001", "at": "2026-08-31T10:00:00+00:00"})
    state = build_state(project, log, None)
    assert state["lead"]["decisions"][0]["item"] == "B-001"


def test_a_board_without_a_backlog_still_reports_the_lead(tmp_path: Path) -> None:
    """The error path renders the same page, so it needs the same fields."""
    log = _lead_log(tmp_path, {"event": "stalled", "at": "2026-08-31T12:00:00+00:00"})
    state = build_state(tmp_path / "nowhere", log, None)
    assert "error" in state and state["lead"]["decisions"]


# ── work happening now, not work that finished ────────────────────────────────
#
# The board could only draw what had ended. Measured on 2026-08-31: seventeen
# `phase:end` events and one `phase:start`, so an item under active work showed the
# verdict of a phase already over, and nothing on the page said anything was running.


def _start(cycle: str, slug: str) -> dict:
    return {"type": "cycle:phase:start", "cycle": cycle, "slug": slug,
            "timestamp": "2026-08-31T13:00:00Z"}


def test_a_started_phase_with_no_end_is_running(tmp_path: Path) -> None:
    project = _project(tmp_path, item_block("B-001", status="triaged"),
                       events=[_start("implement", "B-001")])
    item = _by_id(build_state(project))["B-001"]
    assert item["running_phase"] == "implement"
    assert item["phase"] == "implement"
    assert item["position_from"] == "running"


def test_the_matching_end_clears_it(tmp_path: Path) -> None:
    project = _project(tmp_path, item_block("B-001", status="triaged"),
                       events=[_start("implement", "B-001"),
                               _end("implement", "B-001", "VALIDATED")])
    assert _by_id(build_state(project))["B-001"]["running_phase"] is None


def test_an_end_for_a_different_phase_does_not_clear_it(tmp_path: Path) -> None:
    """Phases overlap in the stream; only the matching end means this one finished."""
    project = _project(tmp_path, item_block("B-001", status="triaged"),
                       events=[_start("implement", "B-001"), _end("plan", "B-001")])
    assert _by_id(build_state(project))["B-001"]["running_phase"] == "implement"


def test_a_plan_slug_starts_the_right_item(tmp_path: Path) -> None:
    project = _project(tmp_path, item_block("B-033", status="planned"),
                       events=[_start("review", "b033-prometheus-url-dev-public")])
    assert _by_id(build_state(project))["B-033"]["running_phase"] == "review"


def test_running_items_are_listed_at_the_top_level(tmp_path: Path) -> None:
    project = _project(tmp_path, item_block("B-001", status="raw"),
                       item_block("B-002", status="raw"),
                       events=[_start("discover", "B-001")])
    assert build_state(project)["running"] == ["B-001"]


def test_nothing_running_is_an_empty_list_not_a_missing_key(tmp_path: Path) -> None:
    project = _project(tmp_path, item_block("B-001", status="raw"), events=[])
    assert build_state(project)["running"] == []


def test_blockers_survive_the_running_lookup(tmp_path: Path) -> None:
    """A regression guard: the first version shadowed the `live` blockers variable and
    silently emptied every blockers list on the board."""
    project = _project(tmp_path, item_block("B-001", status="triaged", extra="blocked_by: B-002\n"),
                       item_block("B-002", status="raw"),
                       events=[_start("discover", "B-002")])
    item = _by_id(build_state(project))["B-001"]
    assert item["blockers"] == ["B-002"]


# ── a stall the session recovered from is history, not news ───────────────────


def _marker(tmp_path: Path, seconds_ago: float) -> Path:
    import os
    import time as _time

    m = tmp_path / "run.log"
    m.write_text("x", encoding="utf-8")
    when = _time.time() - seconds_ago
    os.utime(m, (when, when))
    return m


def test_a_recovered_stall_is_dropped_from_the_board(tmp_path: Path) -> None:
    """It stays in the log — that file is the audit trail — but a resolved stall shown
    beside a live decision says the opposite of the truth."""
    from board_state import read_lead

    log = _lead_log(tmp_path,
                    {"event": "stalled", "at": "2026-08-31T12:00:00+00:00"},
                    {"event": "confirm", "item": "B-001", "at": "2026-08-31T13:00:00+00:00"})
    lead = read_lead(log, _marker(tmp_path, 30))
    assert [d["event"] for d in lead["decisions"]] == ["confirm"]


def test_a_live_stall_is_kept(tmp_path: Path) -> None:
    from board_state import read_lead

    log = _lead_log(tmp_path, {"event": "stalled", "at": "2026-08-31T12:00:00+00:00"})
    lead = read_lead(log, _marker(tmp_path, 4000))
    assert [d["event"] for d in lead["decisions"]] == ["stalled"]


def test_an_unknown_idle_keeps_the_stall(tmp_path: Path) -> None:
    """Dropping it would assert a recovery nobody observed."""
    from board_state import read_lead

    log = _lead_log(tmp_path, {"event": "stalled", "at": "2026-08-31T12:00:00+00:00"})
    assert read_lead(log, None)["decisions"][0]["event"] == "stalled"


def test_other_decisions_survive_recovery(tmp_path: Path) -> None:
    """Only stalls expire; a confirm is a fact about what was done."""
    from board_state import read_lead

    log = _lead_log(tmp_path,
                    {"event": "confirm", "item": "B-001", "at": "2026-08-31T12:00:00+00:00"},
                    {"event": "escalate", "item": "B-002", "at": "2026-08-31T12:30:00+00:00"})
    assert len(read_lead(log, _marker(tmp_path, 30))["decisions"]) == 2


def test_the_rail_is_capped_at_a_screenful(tmp_path: Path) -> None:
    from board_state import read_lead

    log = _lead_log(tmp_path, *[{"event": "confirm", "item": f"B-{i:03d}"} for i in range(40)])
    assert len(read_lead(log, None)["decisions"]) == 12


# ── the item panel: what is being done INSIDE an item ─────────────────────────
#
# The board answers "where is each item". This answers "what is happening in it",
# which is where the work is: a plan's phases, its tasks, the artefacts each cycle
# phase left, and every verdict rather than only the last.


def _with_records(tmp_path: Path, slug: str) -> Path:
    (tmp_path / ".claude" / "rules").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".claude" / "rules" / "blocking-verdicts.txt").write_text(
        "INVALID\nFAIL\nFAIL_HARD\nNEEDS_FIXES\nNOT_VALIDATED\n", encoding="utf-8")
    recs = tmp_path / ".claude" / "records"
    for sub in ("plans", "implementations", "audits", "reviews", "alignment"):
        (recs / sub).mkdir(parents=True, exist_ok=True)
    (recs / "plans" / f"{slug}-plan.md").write_text(
        "# Plan\n\n## Phase 1: Write the failing test\n\n## Phase 2: Make it pass\n",
        encoding="utf-8")
    (recs / "implementations" / f".progress-{slug}.json").write_text(json.dumps({
        "slug": slug,
        "tasks": [
            {"id": "T1.1", "phase": "1", "status": "done", "files": ["a_test.sh"]},
            {"id": "T2.1", "phase": "2", "status": "pending", "files": ["b.yaml"]},
        ],
    }), encoding="utf-8")
    (recs / "audits" / f"{slug}-code-quality-2026-08-31.md").write_text("x", encoding="utf-8")
    return tmp_path


def test_the_slug_is_found_from_what_is_on_disk(tmp_path: Path) -> None:
    """Only the phase that wrote the artefact knows the words after the number."""
    from board_state import item_detail

    root = _with_records(tmp_path, "b033-prometheus-url-dev-public")
    assert item_detail(root, "B-033")["slug"] == "b033-prometheus-url-dev-public"


def test_the_plans_phases_and_tasks_come_back(tmp_path: Path) -> None:
    from board_state import item_detail

    d = item_detail(_with_records(tmp_path, "b033-x"), "B-033")
    assert [p["key"] for p in d["phases"]] == ["1", "2"]
    assert [t["id"] for t in d["tasks"]] == ["T1.1", "T2.1"]
    assert d["tasks"][0]["status"] == "done"


def test_artefacts_are_grouped_by_the_phase_that_wrote_them(tmp_path: Path) -> None:
    from board_state import item_detail

    d = item_detail(_with_records(tmp_path, "b033-x"), "B-033")
    phases = {a["phase"] for a in d["artefacts"]}
    assert "plan" in phases and "code-quality" in phases


def test_every_verdict_is_kept_not_only_the_last(tmp_path: Path) -> None:
    """A single last verdict hides iteration: one item ended code-quality ten times."""
    from board_state import item_detail

    root = _with_records(tmp_path, "b033-x")
    (root / ".claude" / "records" / "cycle-events.jsonl").write_text(
        "".join(json.dumps(_end("code-quality", "B-033", v)) + "\n"
                for v in ("INVALID", "INVALID", "FAIL_SOFT")), encoding="utf-8")
    d = item_detail(root, "B-033")
    assert [v["verdict"] for v in d["verdicts"]] == ["INVALID", "INVALID", "FAIL_SOFT"]


def test_a_gate_a_later_run_cleared_is_not_reported_as_blocking(tmp_path: Path) -> None:
    """Listing a cleared INVALID would report a gate that is open as shut."""
    from board_state import item_detail

    root = _with_records(tmp_path, "b033-x")
    (root / ".claude" / "records" / "cycle-events.jsonl").write_text(
        json.dumps(_end("plan", "B-033", "INVALID")) + "\n"
        + json.dumps(_end("plan", "B-033", "SHIPPABLE")) + "\n", encoding="utf-8")
    assert item_detail(root, "B-033")["blocking"] == []


def test_a_gate_still_failing_is_reported(tmp_path: Path) -> None:
    from board_state import item_detail

    root = _with_records(tmp_path, "b033-x")
    (root / ".claude" / "records" / "cycle-events.jsonl").write_text(
        json.dumps(_end("code-quality", "B-033", "INVALID")) + "\n", encoding="utf-8")
    blocking = item_detail(root, "B-033")["blocking"]
    assert [b["phase"] for b in blocking] == ["code-quality"]


def test_an_item_with_nothing_on_disk_returns_empty_fields(tmp_path: Path) -> None:
    """The panel renders one way; an item nobody has worked is the common case."""
    from board_state import item_detail

    (tmp_path / ".claude" / "records").mkdir(parents=True)
    d = item_detail(tmp_path, "B-999")
    assert d["slug"] is None and d["tasks"] == [] and d["artefacts"] == []


def test_progress_is_counted_from_task_status(tmp_path: Path) -> None:
    """The only place that knows. A status nobody has seen must not round up."""
    from board_state import item_detail

    root = _with_records(tmp_path, "b033-x")
    prog = root / ".claude" / "records" / "implementations" / ".progress-b033-x.json"
    prog.write_text(json.dumps({"slug": "b033-x", "tasks": [
        {"id": "T1.1", "phase": "1", "status": "committed"},
        {"id": "T2.1", "phase": "2", "status": "committed"},
        {"id": "T2.2", "phase": "2", "status": "pending"},
        {"id": "T3.1", "phase": "3", "status": "unknown-to-us"},
    ]}), encoding="utf-8")
    assert item_detail(root, "B-033")["done_ratio"] == 0.5


def test_no_tasks_means_no_ratio_rather_than_zero(tmp_path: Path) -> None:
    """Zero percent and "nothing to measure" are different claims."""
    from board_state import item_detail

    (tmp_path / ".claude" / "records").mkdir(parents=True)
    assert item_detail(tmp_path, "B-999")["done_ratio"] is None


def test_the_specialist_comes_from_the_items_domain(tmp_path: Path) -> None:
    from board_state import item_detail

    root = _with_records(tmp_path, "b033-x")
    (root / "BACKLOG.md").write_text(
        "## B-033 — thing   [ ]\n\ndomain: engine-go\nstatus: triaged\n", encoding="utf-8")
    (root / ".claude" / "agents").mkdir(parents=True, exist_ok=True)
    (root / ".claude" / "agents" / "engine-go.md").write_text("# spec\n", encoding="utf-8")
    d = item_detail(root, "B-033")
    assert d["domain"] == "engine-go"
    assert d["specialist"].endswith("engine-go.md")


def test_a_domain_with_no_specialist_file_still_reports_the_domain(tmp_path: Path) -> None:
    """Naming the domain is honest; inventing a file that is not there is not."""
    from board_state import item_detail

    root = _with_records(tmp_path, "b033-x")
    (root / "BACKLOG.md").write_text(
        "## B-033 — thing   [ ]\n\ndomain: nowhere\nstatus: raw\n", encoding="utf-8")
    d = item_detail(root, "B-033")
    assert d["domain"] == "nowhere" and d["specialist"] is None


def test_the_commit_sha_reaches_the_task(tmp_path: Path) -> None:
    from board_state import item_detail

    root = _with_records(tmp_path, "b033-x")
    prog = root / ".claude" / "records" / "implementations" / ".progress-b033-x.json"
    prog.write_text(json.dumps({"slug": "b033-x", "tasks": [
        {"id": "T1.1", "phase": "1", "status": "committed", "commit_sha": "49194f08b"},
    ]}), encoding="utf-8")
    assert item_detail(root, "B-033")["tasks"][0]["commit"] == "49194f08b"


# ── an outcome is not a position ─────────────────────────────────────────────


def test_finished_work_does_not_sit_in_the_release_phase(tmp_path: Path) -> None:
    """`shipped` is where the work ENDED UP, not a phase it is waiting inside.

    Measured on 2026-08-31: 133 of 170 items carried `shipped` and every one of them
    was drawn in `release`, while `done` — a column the page renders — held nobody.
    One column carried 78% of the board and the operator could not read it.
    """
    project = _project(tmp_path, item_block("B-001", status="shipped"))
    item = _by_id(build_state(project))["B-001"]
    assert item["phase"] == "done"
    assert item["phase"] != "release"


def test_a_stream_still_outranks_the_outcome_a_status_implies(tmp_path: Path) -> None:
    """The change moves where a status POINTS; it does not let a status outvote a
    measurement. An observed phase remains the position, exactly as before."""
    project = _project(tmp_path, item_block("B-001", status="shipped"),
                       events=[_end("review", "b001-thing", "NEEDS_FIXES")])
    item = _by_id(build_state(project))["B-001"]
    assert item["phase"] == "review"
    assert item["position_from"] == "stream"


# ── which items have an implementation to show ───────────────────────────────


def test_an_item_with_a_plan_on_disk_carries_its_slug(tmp_path: Path) -> None:
    project = _project(tmp_path, item_block("B-033", status="planned"))
    plans = project / ".claude" / "records" / "plans"
    plans.mkdir(parents=True, exist_ok=True)
    (plans / "b033-prometheus-url-dev-public-plan.md").write_text("## Phase 1: x\n",
                                                                  encoding="utf-8")
    item = _by_id(build_state(project))["B-033"]
    assert item["plan_slug"] == "b033-prometheus-url-dev-public"


def test_an_item_with_no_plan_says_so_rather_than_guessing_a_slug(tmp_path: Path) -> None:
    """The implementation view only shows what was written. A constructed slug would
    put an item on a board of steps it has never had."""
    project = _project(tmp_path, item_block("B-001", status="triaged"))
    assert _by_id(build_state(project))["B-001"]["plan_slug"] is None


def test_a_progress_file_alone_is_enough_to_find_the_plan(tmp_path: Path) -> None:
    """The tasks live in the progress file, and an item can be mid-implementation
    before anything else is on disk."""
    project = _project(tmp_path, item_block("B-044", status="planned"))
    impl = project / ".claude" / "records" / "implementations"
    impl.mkdir(parents=True, exist_ok=True)
    (impl / ".progress-b044-the-thing.json").write_text('{"slug": "b044-the-thing", "tasks": []}',
                                                        encoding="utf-8")
    assert _by_id(build_state(project))["B-044"]["plan_slug"] == "b044-the-thing"


# ── one repository, one answer ───────────────────────────────────────────────


def test_the_board_and_the_drift_checker_read_the_same_blocking_list() -> None:
    """They each kept a copy, and the copies disagreed.

    Measured on 2026-08-31 against the theo stream: the drift checker reported
    `implement` ending in FAIL as a verdict that forbids advancing, while the board's
    item panel — reading its own list, which omitted FAIL — said "no gate is holding
    this item" about the very same event.
    """
    import sys
    kit = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(kit / "scripts"))
    from check_phase_drift import load_blocking_verdicts

    from board_state import blocking_verdicts

    assert load_blocking_verdicts(kit) == blocking_verdicts(kit)
    assert "FAIL" in blocking_verdicts(kit)


def test_a_missing_rule_file_does_not_let_the_board_claim_nothing_is_blocked(
        tmp_path: Path) -> None:
    """The board reports what it can read. An unreadable rule is not evidence that
    every gate is open — the checker raises on it, and the board shows no gates
    because it found none to check, which the empty panel already says."""
    from board_state import blocking_verdicts
    assert blocking_verdicts(tmp_path) == frozenset()


# ── being locked out must not look like being down ───────────────────────────


def test_the_grant_cookie_outlives_the_browser_session() -> None:
    """Without Max-Age this is a session cookie: it dies when the browser closes and
    the next visit to the bare address answers 401.

    Measured on 2026-08-31 — the board was reported as down while the process was up,
    serving and streaming. The operator had simply restarted their browser.
    """
    import board_server
    assert board_server._COOKIE_MAX_AGE >= 7 * 24 * 3600


def test_the_unauthorised_reply_says_the_board_is_running() -> None:
    """A bare line of text on a blank page reads as a dead server. The reply has to
    distinguish "not signed in" from "not there"."""
    import board_server
    page = board_server._UNAUTHORISED_PAGE.decode("utf-8")
    assert page.lstrip().startswith("<!doctype html")
    assert "running" in page
    assert "?t=" in page


def test_the_unauthorised_page_never_prints_the_token() -> None:
    """It is the thing being checked. A page that hands it out authenticates nobody."""
    import board_server
    page = board_server._UNAUTHORISED_PAGE.decode("utf-8")
    # The only `t=` on the page is the placeholder, never a value.
    assert "&lt;token&gt;" in page
    assert not re.search(r"\bt=[0-9a-f]{8,}", page)


# ── evidence the board cannot place must still be counted ────────────────────


def test_events_with_no_item_are_counted_not_dropped(tmp_path: Path) -> None:
    """Measured on 2026-08-31 against theo: 3 of 28 events carried `slug: null` —
    three `code-quality` runs that happened and appeared nowhere. Silence about
    discarded evidence reads as evidence that was never there."""
    project = _project(tmp_path, item_block("B-001", status="triaged"), events=[
        {"type": "cycle:phase:end", "cycle": "code-quality", "slug": None,
         "verdict": "FAIL_SOFT", "timestamp": "2026-08-31T15:27:50Z"},
        _end("discover", "b001-thing", "PASS"),
    ])
    state = build_state(project)
    assert state["unplaced"]["without_item"] == 1
    assert state["unplaced"]["off_chain"] == {}


def test_a_cycle_outside_the_chain_is_named_and_counted(tmp_path: Path) -> None:
    """`deps-audit` runs and emits, and the board draws eight declared phases. The
    event is real; the column for it does not exist. Saying so is the difference
    between a board with a gap and a board that hides one."""
    project = _project(tmp_path, item_block("B-033", status="triaged"), events=[
        _end("deps-audit", "b033-thing", "PASS"),
        _end("implement", "b033-thing", "FAIL"),
    ])
    state = build_state(project)
    assert state["unplaced"]["off_chain"] == {"deps-audit": 1}
    assert state["unplaced"]["without_item"] == 0
    # And the event that DOES place the item still does.
    assert _by_id(state)["B-033"]["phase"] == "implement"


def test_a_fully_placeable_stream_reports_nothing_unplaced(tmp_path: Path) -> None:
    project = _project(tmp_path, item_block("B-001", status="triaged"),
                       events=[_end("discover", "b001-thing", "PASS")])
    unplaced = build_state(project)["unplaced"]
    assert unplaced == {"without_item": 0, "off_chain": {}}


def test_a_start_the_board_cannot_place_is_counted_too(tmp_path: Path) -> None:
    """A phase that BEGAN and cannot be placed is work the board shows nobody doing.
    Measured on theo: `idea-to-release` opened and no card ever moved."""
    project = _project(tmp_path, item_block("B-033", status="triaged"), events=[
        {"type": "cycle:phase:start", "cycle": "idea-to-release",
         "slug": "b033-thing", "timestamp": "2026-08-31T15:00:00Z"},
    ])
    assert build_state(project)["unplaced"]["off_chain"] == {"idea-to-release": 1}


# ── a phase that stopped and said why ────────────────────────────────────────


def test_a_blocked_report_marks_the_item_halted(tmp_path: Path) -> None:
    """`/implement` writes `{slug}-BLOCKED.md` when it stops and needs a person.

    Measured on 2026-08-31: B-033 had one, naming three pre-existing test failures it
    cannot fix and three paths for a sponsor to choose between. The board listed the
    file among seven artefacts and said nothing, and the item sat 85 minutes while
    the page showed a verdict token.
    """
    project = _project(tmp_path, item_block("B-033", status="triaged"))
    impl = project / ".claude" / "records" / "implementations"
    impl.mkdir(parents=True, exist_ok=True)
    (impl / "b033-thing-BLOCKED.md").write_text(
        "# BLOCKED report\n\n**Emitted by:** /implement halt-loop driver (env missing)\n",
        encoding="utf-8")
    assert _by_id(build_state(project))["B-033"]["halted"] is True


def test_halted_is_not_folded_into_impeded(tmp_path: Path) -> None:
    """A person declaring an impediment and a phase declaring it stopped are different
    facts with different owners. Counting them as one hides which needs which action."""
    project = _project(tmp_path, item_block("B-033", status="triaged"))
    impl = project / ".claude" / "records" / "implementations"
    impl.mkdir(parents=True, exist_ok=True)
    (impl / "b033-thing-BLOCKED.md").write_text("# BLOCKED\n", encoding="utf-8")
    item = _by_id(build_state(project))["B-033"]
    assert item["halted"] is True
    assert item["blocked"] is False


def test_the_report_reason_is_quoted_from_the_file(tmp_path: Path) -> None:
    from board_state import item_detail
    root = _with_records(tmp_path, "b033-x")
    (root / ".claude" / "records" / "implementations" / "b033-x-BLOCKED.md").write_text(
        "# BLOCKED report\n\n**Emitted by:** /implement halt-loop (pre-existing failures)\n",
        encoding="utf-8")
    halted = item_detail(root, "B-033")["halted"]
    assert halted["phase"] == "implement"
    assert halted["reason"] == "/implement halt-loop (pre-existing failures)"


def test_a_plan_edited_after_attesting_is_reported(tmp_path: Path) -> None:
    """Attesting exists to catch exactly this, and nothing was checking.
    B-033 was implemented against 4c7ae5d5…; the plan on disk is now 88e243ab…."""
    from board_state import item_detail
    root = _with_records(tmp_path, "b033-x")
    recs = root / ".claude" / "records"
    (recs / "implementations" / "b033-x-implementation.md").write_text(
        "# Implementation\n\n**Attest sha:** `" + "a" * 64 + "`\n", encoding="utf-8")
    attest = item_detail(root, "B-033")["attest"]
    assert attest["drifted"] is True
    assert attest["attested"] == "a" * 64


def test_a_plan_untouched_since_attesting_is_not_reported_as_drifted(tmp_path: Path) -> None:
    import hashlib
    from board_state import item_detail
    root = _with_records(tmp_path, "b033-x")
    recs = root / ".claude" / "records"
    real = hashlib.sha256((recs / "plans" / "b033-x-plan.md").read_bytes()).hexdigest()
    (recs / "implementations" / "b033-x-implementation.md").write_text(
        f"# Implementation\n\n**Attest sha:** `{real}`\n", encoding="utf-8")
    assert item_detail(root, "B-033")["attest"]["drifted"] is False


def test_the_board_draws_the_chain_that_is_declared() -> None:
    """PHASES was a literal tuple and went stale the day the chain grew.

    `cycle-phases.txt` gained `brainstorm` and the tuple did not, so the board drew
    eight columns for a nine-phase chain. Nothing caught it: every other test here
    asserts against `PHASES`, which agrees with itself whatever it says.

    So this one compares it to the DECLARATION — the same file `check_phase_drift.py`
    and `check_squad_map.py` read. Three readers, one source.
    """
    from pathlib import Path

    declared = []
    path = Path(__file__).resolve().parents[3] / "rules" / "cycle-phases.txt"
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line and "|" in line:
            declared.append(line.split("|")[0].strip())

    assert list(PHASES) == declared, (
        "the board's columns and rules/cycle-phases.txt disagree about the chain"
    )


def test_an_item_the_registry_does_not_carry_is_marked_absent(tmp_path) -> None:
    """`item_detail` returned the same all-null shape for an id nobody filed as for
    an item with no records yet, and the server answered 200 to both.

    Found by exercising `board_server.py` for real rather than by reading it: the
    route matched the id FORMAT, never the registry. The board's discipline is not
    presenting inference as observation — answering for an item that does not exist
    is that, at the transport layer.
    """
    from board_state import item_detail

    (tmp_path / "BACKLOG.md").write_text(
        "# Backlog\n\n## B-001 — Real one   [ ]\n\ndomain: web\nrepo: web-console\n"
        "status: raw\n",
        encoding="utf-8",
    )
    assert item_detail(tmp_path, "B-001")["in_registry"] is True
    assert item_detail(tmp_path, "B-999")["in_registry"] is False


def test_no_backlog_at_all_is_absent_not_present(tmp_path) -> None:
    """A missing registry must not read as an item that exists."""
    from board_state import item_detail

    assert item_detail(tmp_path, "B-001")["in_registry"] is False
