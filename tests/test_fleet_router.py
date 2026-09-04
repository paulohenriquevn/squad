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

#: Any absolute path will do; it must not be one that exists on a single machine.
#: `test_no_origin_ecosystem_leak` fails a versioned file carrying a workstation
#: path, because every consumer gets the string and none of them get the directory.
_REPO = "/srv/example/kit"
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
                              repo=_REPO)
    assert "19" in text
    for forbidden in ("--no-verify", "--force", "Co-Authored-By", "threshold"):
        assert forbidden in text, f"the brief does not forbid {forbidden}"
    assert "FAILING TEST FIRST" in text.upper()


def test_the_brief_isolates_the_lane_in_its_own_worktree() -> None:
    text = fleet_router.brief(fleet_router.Unit("kit#19", "a defect", "kit"),
                              repo=_REPO)
    assert "worktree add" in text
    assert _REPO in text


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


# ── work a lane abandoned must come back ──────────────────────────────────────
# The log holds an assignment until something releases it, and nothing did. A
# lane that dies mid-unit, or is cleared by a person, leaves its unit assigned
# forever — the router will never offer it again and no lane is working it. That
# is the fleet's 10h33m idle failure rebuilt one level up: correct-looking state
# over work nobody is doing.
#
# Three facts have to hold together before a unit is called abandoned, because
# each alone is normal: the lane is free, no branch exists, and enough time has
# passed that a lane which merely had not started yet would have.


def test_a_unit_whose_lane_died_is_released(tmp_path: Path) -> None:
    log = tmp_path / "a.jsonl"
    fleet_router.record(log, "assigned", unit="kit#19", lane="squad1",
                        at_epoch=1000.0)
    released = fleet_router.reap(log, lanes={"squad1": "free"}, branches=set(),
                                 now=1000.0 + fleet_router.GRACE + 1)
    assert released == ["kit#19"]
    assert fleet_router.in_flight(log) == {}


def test_a_unit_still_inside_the_grace_period_is_left_alone(tmp_path: Path) -> None:
    log = tmp_path / "a.jsonl"
    fleet_router.record(log, "assigned", unit="kit#19", lane="squad1", at_epoch=1000.0)
    assert fleet_router.reap(log, lanes={"squad1": "free"}, branches=set(),
                             now=1000.0 + 10) == []


def test_a_unit_on_a_busy_lane_is_never_reaped(tmp_path: Path) -> None:
    """The commonest case is a lane taking a long time, and reaping that would
    hand the same unit to a second lane while the first is still writing."""
    log = tmp_path / "a.jsonl"
    fleet_router.record(log, "assigned", unit="kit#19", lane="squad1", at_epoch=1000.0)
    assert fleet_router.reap(log, lanes={"squad1": "busy"}, branches=set(),
                             now=1000.0 + fleet_router.GRACE * 10) == []


def test_a_unit_that_produced_a_branch_is_not_abandoned(tmp_path: Path) -> None:
    """The lane did the work and stopped, which is what a lane is supposed to do.
    Landing it is the lander's job, not the reaper's."""
    log = tmp_path / "a.jsonl"
    fleet_router.record(log, "assigned", unit="kit#19", lane="squad1", at_epoch=1000.0)
    assert fleet_router.reap(log, lanes={"squad1": "free"},
                             branches={"fix/kit19-readonly-zone"},
                             now=1000.0 + fleet_router.GRACE * 10) == []


def test_a_unit_on_a_lane_of_unknown_state_is_not_reaped(tmp_path: Path) -> None:
    """`unknown` means the check did not run. Acting on it would be deciding from
    an absent measurement, which is the defect this kit finds most."""
    log = tmp_path / "a.jsonl"
    fleet_router.record(log, "assigned", unit="kit#19", lane="squad1", at_epoch=1000.0)
    assert fleet_router.reap(log, lanes={"squad1": "unknown"}, branches=set(),
                             now=1000.0 + fleet_router.GRACE * 10) == []


# ── when nothing is owed, the fleet goes looking ──────────────────────────────
# With the consumer walled and the kit's tracker empty, the correct answer used
# to be "idle" — and it was correct, which is why it went unexamined for a day.
# The kit HAS a way to find work it does not know about yet: kit_audit_workflow
# hunts the patterns it has shipped more than once, and every claim meets an
# agent whose job is to refute it. Nothing ever ran it.
#
# It is the LAST source on purpose. A fleet that prefers auditing itself to
# shipping the product is worse than an idle one — it looks busy — and a fleet
# that audits on every pass produces a tracker nobody reads.


def test_an_audit_is_offered_only_when_both_real_sources_are_empty(tmp_path: Path) -> None:
    log = tmp_path / "a.jsonl"
    assert fleet_router.audit_unit(log, has_work=True, now=0.0) is None
    assert fleet_router.audit_unit(log, has_work=False, now=0.0) is not None


def test_a_second_audit_waits_out_the_cooldown(tmp_path: Path) -> None:
    """Otherwise every idle pass files another sweep, and the tracker fills with
    the same claims until nobody reads it."""
    log = tmp_path / "a.jsonl"
    first = fleet_router.audit_unit(log, has_work=False, now=0.0)
    assert first is not None
    fleet_router.record(log, "assigned", unit=first.slug, lane="squad1", at_epoch=0.0)
    assert fleet_router.audit_unit(log, has_work=False, now=10.0) is None
    assert fleet_router.audit_unit(
        log, has_work=False, now=fleet_router.AUDIT_COOLDOWN + 1) is not None


def test_the_audit_brief_says_to_file_only_what_survived_refutation() -> None:
    unit = fleet_router.Unit("kit-audit", "sweep the kit", "audit")
    text = fleet_router.brief(unit, repo="/srv/example/kit")
    assert "kit_audit_workflow" in text
    assert "file_findings" in text
    assert "refut" in text.lower()
    # The word may appear — the brief says there is no worktree because there is
    # nothing to write. What must not appear is the INSTRUCTION to make one.
    assert "worktree add" not in text, "a sweep writes no code and needs no worktree"
    assert "Write NO code" in text


def test_a_consumer_backlog_unit_is_not_briefed_as_a_kit_issue() -> None:
    """A consumer item is not a kit issue, and the two briefs are not variants.

    Measured 2026-09-04 (kit#27): B-165 was dispatched with the kit-repair
    template, which told the lane to work in the kit repository and run
    a `gh issue view B-165` against the kit tracker. Neither resolves —
    B-165 lives in the consumer's BACKLOG.md, and the kit's registry is GitHub
    issues, which cannot hold a B-NNN id. The lane halted rather than guess,
    so every consumer item dispatched this way costs a pass and lands nothing.
    """
    unit = fleet_router.Unit("B-165", "an environment lost its edge", "backlog")
    text = fleet_router.brief(unit, repo="/kit", project="/consumer")

    # It must not send the lane to the kit, nor to a registry that cannot hold it.
    # A mention of `gh issue view` as a WARNING is fine and wanted; what must not
    # appear is the instruction form, which carries `--repo <tracker>`.
    assert "--repo" not in text
    assert "Read the issue first" not in text
    assert "/kit" not in text
    # It must name the consumer and the cycle a consumer item actually runs through.
    assert "/consumer" in text
    assert "B-165" in text


def test_a_kit_unit_still_gets_the_repair_brief() -> None:
    """The consumer branch must not disturb the path that already worked."""
    unit = fleet_router.Unit("kit#19", "a title", "kit")
    text = fleet_router.brief(unit, repo="/kit", project="/consumer")
    assert "gh issue view" in text
    assert "worktree" in text


def test_the_consumer_brief_does_not_prescribe_one_cycle_for_every_item() -> None:
    """A consumer registry carries a `suggested_mode` per item, and the modes
    enter the cycle at different points.

    Measured 2026-09-04: the first version of this brief hard-coded
    `/idea-to-release`, and a lane picking up an item whose bullets were all
    terminal or deferred halted rather than run it — correctly. Its words:
    *"What would /plan-write plan? Bullet 1 is deferred... A plan for 'no work'
    is fabrication."* The brief must send the lane to the item's own mode, and
    must say that an item with no code-shaped work left is a real answer.
    """
    unit = fleet_router.Unit("B-067", "gates nobody runs", "backlog")
    text = fleet_router.brief(unit, repo="/kit", project="/consumer")

    assert "suggested_mode" in text
    # No single cycle command may be prescribed as the only path.
    assert "/idea-to-release {slug}" not in text
    # Reporting that nothing is code-shaped must be named as a valid outcome.
    assert "fabricat" in text.lower()
