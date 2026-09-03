"""Nothing ever routed work to a lane. That is why the fleet is a 2.

Every unit of work this fleet has completed was typed in by a person. The parts
existed and were correct in isolation — `select_backlog_item.py` names what may
start, `kit_issues.py` names what the kit owes, `session_ready.py` says which
lane can take something, `dispatch_to_lane.sh` hands it over — and the segment
between them was a person reading one output and composing the next input.

Measured 2026-09-03: three lanes idle for 10h33m with four actionable kit issues
open. Not one component was broken. The wiring did not exist.

The router is that wiring, and it is deliberately not a decision-maker: it routes
units the sources already declared startable. It never invents work, never
overrides a hold, and never treats an unreadable source as an empty one.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_FLEET = Path(__file__).resolve().parents[1] / "mechanisms" / "fleet"
if str(_FLEET) not in sys.path:
    sys.path.insert(0, str(_FLEET))

import fleet_router  # noqa: E402
from kit_issues import Issue, Unavailable  # noqa: E402


def _issue(n: int, title: str = "a defect") -> Issue:
    return Issue(number=n, title=title, labels=(), url=f"https://x/{n}")


# ── it does not assign what cannot be taken ───────────────────────────────────


def test_a_busy_lane_is_never_assigned_to(tmp_path: Path) -> None:
    plan = fleet_router.plan(
        units=[fleet_router.Unit("kit#19", "a defect", "kit")],
        lanes={"squad1": "busy"}, log=tmp_path / "a.jsonl", branches=set())
    assert plan.assignments == []
    assert "squad1" in plan.idle_reason


def test_a_lane_holding_unsent_text_is_not_free(tmp_path: Path) -> None:
    """It looks exactly like an idle one, which is how three lanes sat holding
    work for forty minutes."""
    plan = fleet_router.plan(
        units=[fleet_router.Unit("kit#19", "a defect", "kit")],
        lanes={"squad1": "holding"}, log=tmp_path / "a.jsonl", branches=set())
    assert plan.assignments == []


def test_free_lanes_take_units_one_each(tmp_path: Path) -> None:
    plan = fleet_router.plan(
        units=[fleet_router.Unit(f"kit#{n}", "t", "kit") for n in (19, 20, 21)],
        lanes={"squad1": "free", "squad2": "free"}, log=tmp_path / "a.jsonl", branches=set())
    assert [(a.lane, a.unit.slug) for a in plan.assignments] == [
        ("squad1", "kit#19"), ("squad2", "kit#20")]
    assert plan.unassigned == ["kit#21"]


# ── the state that survives a restart ─────────────────────────────────────────


def test_a_unit_already_in_flight_is_not_assigned_again(tmp_path: Path) -> None:
    log = tmp_path / "a.jsonl"
    fleet_router.record(log, "assigned", unit="kit#19", lane="squad1")
    plan = fleet_router.plan(
        units=[fleet_router.Unit("kit#19", "t", "kit"), fleet_router.Unit("kit#20", "t", "kit")],
        lanes={"squad2": "free"}, log=log, branches=set())
    assert [a.unit.slug for a in plan.assignments] == ["kit#20"]


def test_a_released_unit_becomes_assignable_again(tmp_path: Path) -> None:
    log = tmp_path / "a.jsonl"
    fleet_router.record(log, "assigned", unit="kit#19", lane="squad1")
    fleet_router.record(log, "released", unit="kit#19", lane="squad1", reason="lane died")
    plan = fleet_router.plan(
        units=[fleet_router.Unit("kit#19", "t", "kit")],
        lanes={"squad2": "free"}, log=log, branches=set())
    assert [a.unit.slug for a in plan.assignments] == ["kit#19"]


def test_state_replays_from_the_log_not_from_memory(tmp_path: Path) -> None:
    """The lead lost everything when it died. An append-only log is the whole
    reason a restart resumes instead of re-assigning."""
    log = tmp_path / "a.jsonl"
    fleet_router.record(log, "assigned", unit="kit#19", lane="squad1")
    assert fleet_router.in_flight(log) == {"kit#19": "squad1"}


def test_a_corrupt_log_line_is_reported_not_skipped(tmp_path: Path) -> None:
    log = tmp_path / "a.jsonl"
    fleet_router.record(log, "assigned", unit="kit#19", lane="squad1")
    log.write_text(log.read_text() + "{not json\n", encoding="utf-8")
    with pytest.raises(fleet_router.StateUnreadable):
        fleet_router.in_flight(log)


# ── absence is never a measurement ────────────────────────────────────────────


def test_an_unreadable_source_is_not_an_empty_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """`gh` missing must not tell an idle fleet the kit has no known defects."""
    def boom(_repo: str, **_kw: object) -> object:
        raise Unavailable("`gh` is not installed")
    monkeypatch.setattr(fleet_router.kit_issues, "fleet_work", boom)
    units, note = fleet_router.kit_units("owner/repo")
    assert units == []
    assert "not installed" in note
    assert "no known defects" not in note.lower()


def test_an_empty_registry_says_so_in_its_own_words(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fleet_router.kit_issues, "fleet_work", lambda *_a, **_k: ([], []))
    units, note = fleet_router.kit_units("owner/repo")
    assert units == []
    assert "readable" in note


def test_held_issues_are_named_rather_than_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fleet_router.kit_issues, "fleet_work",
                        lambda *_a, **_k: ([_issue(19)], [_issue(30)]))
    units, note = fleet_router.kit_units("owner/repo")
    assert [u.slug for u in units] == ["kit#19"]
    assert "kit#30" in note, "an issue nobody can see is an issue nobody decides"


# ── the brief it writes ───────────────────────────────────────────────────────


def test_the_brief_names_the_unit_and_forbids_the_bypasses() -> None:
    text = fleet_router.brief(fleet_router.Unit("kit#19", "a defect", "kit"),
                              repo="/home/paulo/dev/squad")
    assert "19" in text
    for forbidden in ("--no-verify", "--force", "Co-Authored-By", "threshold"):
        assert forbidden in text, f"the brief does not forbid {forbidden}"
    assert "FAILING TEST FIRST" in text.upper()


def test_the_brief_isolates_the_lane_in_its_own_worktree() -> None:
    text = fleet_router.brief(fleet_router.Unit("kit#19", "a defect", "kit"),
                              repo="/home/paulo/dev/squad")
    assert "worktree add" in text
    assert "/home/paulo/dev/squad" in text


# ── memory is not the only evidence of work in flight ─────────────────────────
# The router's log knows only what the router did. Measured on its first live run
# 2026-09-03: it offered kit#19, #20, #21 and #22 — two already committed on
# branches, one in flight in a lane, one fixed and awaiting a push — because a
# person had dispatched them by hand and the log had never heard of them.
#
# A branch is an observable fact rather than a memory, and it survives the router
# crashing between dispatching and recording, which is the window where memory
# alone loses a unit and hands it to a second lane.


def test_a_unit_with_a_branch_already_open_is_not_offered(tmp_path: Path) -> None:
    plan = fleet_router.plan(
        units=[fleet_router.Unit("kit#19", "t", "kit"), fleet_router.Unit("kit#26", "t", "kit")],
        lanes={"squad1": "free", "squad2": "free"}, log=tmp_path / "a.jsonl",
        branches={"fix/kit19-readonly-zone", "workspace"})
    assert [a.unit.slug for a in plan.assignments] == ["kit#26"]
    assert any("kit#19" in note and "branch" in note for note in plan.notes)


def test_a_branch_for_another_unit_does_not_hold_this_one(tmp_path: Path) -> None:
    """`fix/kit2-...` must not hold kit#21 — a prefix match would silently
    starve the queue and look like an empty backlog."""
    plan = fleet_router.plan(
        units=[fleet_router.Unit("kit#21", "t", "kit")],
        lanes={"squad1": "free"}, log=tmp_path / "a.jsonl",
        branches={"fix/kit2-something"})
    assert [a.unit.slug for a in plan.assignments] == ["kit#21"]


def test_branches_that_could_not_be_listed_are_not_an_empty_set(tmp_path: Path) -> None:
    """`None` is not `set()`. Reading "no branches exist" off a git call that
    failed would re-offer every unit already in flight."""
    with pytest.raises(fleet_router.StateUnreadable):
        fleet_router.plan(
            units=[fleet_router.Unit("kit#19", "t", "kit")],
            lanes={"squad1": "free"}, log=tmp_path / "a.jsonl", branches=None)


def test_a_unit_a_commit_already_closes_is_not_offered(tmp_path: Path) -> None:
    """The branch guard misses work done straight on the working branch.

    Measured 2026-09-03: kit#22 and kit#25 were fixed as commits on `workspace`
    with no `fix/kit*` branch, and the router offered both back. A commit saying
    `Closes #22` is the same kind of evidence as a branch — observable, and not a
    memory the router has to keep.
    """
    plan = fleet_router.plan(
        units=[fleet_router.Unit("kit#22", "t", "kit"), fleet_router.Unit("kit#26", "t", "kit")],
        lanes={"squad1": "free", "squad2": "free"}, log=tmp_path / "a.jsonl",
        branches=set(), closed={"22"})
    assert [a.unit.slug for a in plan.assignments] == ["kit#26"]
    assert any("kit#22" in n and "commit" in n for n in plan.notes)


def test_closed_defaults_to_empty_because_absent_history_is_not_a_hold(tmp_path: Path) -> None:
    """Unlike `branches`, an empty `closed` set is safe: it can only cause a unit
    to be OFFERED, and the tracker is the authority on whether it is open. The
    asymmetry is deliberate and is why only one of the two raises on None."""
    plan = fleet_router.plan(
        units=[fleet_router.Unit("kit#22", "t", "kit")],
        lanes={"squad1": "free"}, log=tmp_path / "a.jsonl", branches=set())
    assert [a.unit.slug for a in plan.assignments] == ["kit#22"]
