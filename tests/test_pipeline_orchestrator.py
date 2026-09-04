"""The scheduler that keeps items moving while one of them waits.

Every test here maps to an acceptance criterion of the alignment brief that took
this component to 91%, after an alignment judge REFUSED an earlier draft. The brief
was a run record and run records are not carried in this repository's index, so its
three findings are pinned below — a defect a reviewer caught once is a defect that
returns, and the pin is what survives the record:

  - the chain is SEVEN stages; a five-stage draft schedules work that never runs
  - backward propagation carries a COMMIT, not a task (FR-006)
  - the lane budget is DERIVED: min(16, cpus-2) minus REVIEW's fan-out (NFR-001)

The orchestrator does not reimplement any phase. It decides WHICH item may enter
WHICH stage and WHEN — the phases keep their own gates and verdicts, and a
pipeline that could change a verdict would be a pipeline that routes around them.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mechanisms" / "fleet"))

from pipeline_orchestrator import STAGES, Item, Pipeline, lane_budget


def _pipeline(*items: str, lanes: int = 3) -> Pipeline:
    return Pipeline([Item(slug=s) for s in items], lanes=lanes)


# ── AC-001 — many items, one stage each ─────────────────────────────────────

def test_three_items_occupy_three_lanes_concurrently() -> None:
    p = _pipeline("b-014", "b-022", "b-033")
    running = p.schedule()
    assert len(running) == 3
    assert {r.slug for r in running} == {"b-014", "b-022", "b-033"}
    assert all(r.stage == STAGES[0] for r in running)


def test_one_item_never_occupies_two_stages() -> None:
    """The unit of the pipeline is the ITEM, and an item is in one place."""
    p = _pipeline("b-014")
    p.schedule()
    p.complete("b-014")
    running = p.schedule()
    assert len(running) == 1 and running[0].stage == STAGES[1]


# ── AC-002 — the parked item costs one lane, not the line ───────────────────

def test_a_parked_item_does_not_stop_the_others() -> None:
    """The argument for the whole thing. If this fails, sequential is simpler."""
    p = _pipeline("b-014", "b-022", "b-033")
    p.schedule()
    p.park("b-022", reason="AWAITING_REVIEW")

    running = p.schedule()
    assert "b-022" not in {r.slug for r in running}
    assert {"b-014", "b-033"} <= {r.slug for r in running} | {i.slug for i in p.running}


def test_a_parked_item_resumes_where_it_stopped() -> None:
    """Not at the start. Re-running DISCOVER on a signed item wastes the wait."""
    p = _pipeline("b-014")
    p.schedule()
    p.complete("b-014")          # DISCOVER done, now at PLAN
    p.schedule()
    p.park("b-014", reason="AWAITING_REVIEW")
    p.unpark("b-014")
    assert p.item("b-014").stage == STAGES[1]


# ── AC-003 — isolation ──────────────────────────────────────────────────────

def test_isolation_every_running_lane_gets_its_own_worktree() -> None:
    """Six agents on ONE tree filed a false BLOCKER on the B-025 run."""
    p = _pipeline("b-014", "b-022", "b-033")
    running = p.schedule()
    trees = [r.worktree for r in running]
    assert len(set(trees)) == len(trees), f"lanes share a worktree: {trees}"
    assert all(t for t in trees)


def test_isolation_a_finished_lane_releases_its_worktree_before_reuse() -> None:
    """NFR-002 — bounded by the LANE, not by a timer that could fire mid-stage."""
    p = _pipeline("b-014", "b-022", lanes=1)
    # Capture the NAME, not the item: releasing clears the field, so reading it
    # afterwards asks whether None was released.
    tree = p.schedule()[0].worktree
    p.complete("b-014")
    assert tree in p.released_worktrees
    assert len(p.live_worktrees) <= 1, "a released worktree is still live"


# ── AC-004 — batch consumption ──────────────────────────────────────────────

def test_a_batch_stage_takes_everything_queued_at_it() -> None:
    """swarm-forge's cleaner/architect/QA take batches: reviewing five slices
    together costs less than reviewing five slices five times."""
    p = _pipeline("b-014", "b-022", "b-033", lanes=3)
    for slug in ("b-014", "b-022", "b-033"):
        p.force_stage(slug, "CODE-QUALITY")
    taken = p.take_batch("CODE-QUALITY")
    assert len(taken) == 3


def test_a_task_stage_takes_one() -> None:
    p = _pipeline("b-014", "b-022", lanes=2)
    for slug in ("b-014", "b-022"):
        p.force_stage(slug, "IMPLEMENT")
    assert len(p.take_batch("IMPLEMENT")) == 1


# ── AC-005 — the pipeline schedules, it never overrides a gate ──────────────

def test_the_gate_verdict_is_obeyed_not_reinterpreted() -> None:
    p = _pipeline("b-014")
    p.schedule()
    p.complete("b-014", verdict="BLOCKED")
    assert p.item("b-014").parked
    assert p.item("b-014").stage == STAGES[0], "a BLOCKED item advanced anyway"


# ── AC-006 — backward propagation (the judge caught its absence) ────────────

def test_a_backward_handoff_carries_a_commit_not_a_task() -> None:
    p = _pipeline("b-014")
    p.force_stage("b-014", "REVIEW")
    p.send_back("b-014", to="IMPLEMENT", commit="abc1234")
    item = p.item("b-014")
    assert item.stage == "IMPLEMENT"
    assert item.merge_only == "abc1234"
    assert not item.parked, "a merge-only hop is not new work and must not park"


# ── AC-007 — one retry, then park AND surface ──────────────────────────────

def test_a_failure_retries_once_then_parks_and_surfaces() -> None:
    """cycle-idea-to-release.md:80 halts and asks. The pipeline parks and
    surfaces; it does not silently swap a judge in for that human."""
    p = _pipeline("b-014")
    p.schedule()
    p.fail("b-014", reason="validation red")
    assert not p.item("b-014").parked, "parked on the first failure — no retry"
    p.fail("b-014", reason="validation red again")
    item = p.item("b-014")
    assert item.parked and item.surfaced
    assert "validation red again" in item.park_reason


# ── AC-008 — the lane budget is derived, not asserted ──────────────────────

@pytest.mark.parametrize("cpus,fanout,expected", [
    (12, 7, 3),    # this machine: min(16,10) - 7 = 3
    (4, 7, 1),     # min(16,2)=2 - 7 < 1, floors at 1
    (64, 7, 9),    # min(16,62)=16 - 7 = 9
])
def test_the_lane_budget_reserves_one_review_fanout(cpus, fanout, expected) -> None:
    """The judge refused `8` because 8 lanes with one REVIEW needs 8+7=15
    against a cap of 10 — it deadlocks on the limit the brief itself cited."""
    assert lane_budget(cpus=cpus, review_fanout=fanout) == expected


def test_at_most_one_item_is_in_review() -> None:
    """Two concurrent reviews need 14 agents against a cap of 10."""
    p = _pipeline("b-014", "b-022", lanes=3)
    for slug in ("b-014", "b-022"):
        p.force_stage(slug, "REVIEW")
    assert len(p.take_batch("REVIEW")) == 1


# ── the chain itself ───────────────────────────────────────────────────────

def test_the_chain_is_the_seven_stages_the_cycle_declares() -> None:
    """The judge refused a five-stage draft: a pipeline missing CODE-QUALITY and
    ACCEPTANCE schedules work that never runs."""
    assert STAGES == ("DISCOVER", "PLAN", "IMPLEMENT", "CODE-QUALITY",
                      "REVIEW", "RELEASE", "ACCEPTANCE")


# ── the registry write-back ───────────────────────────────────────────────────
#
# Measured on 2026-08-30: the pipeline's item state had no mapping to BACKLOG.md's
# `status:` field at all, so an item parked in a lane still read `triaged` on disk —
# and the disk is the only copy that outlives the session.

from pipeline_orchestrator import (  # noqa: E402 — imported here, beside the behaviour it covers; the comment above says which
    StatusWrite,
    apply_writes,
)


def _one(slug: str = "b-001") -> Pipeline:
    return Pipeline(items=[Item(slug=slug)], lanes=4)


def test_finishing_discover_records_triaged():
    p = _one()
    p.schedule()
    p.complete("b-001")
    assert [(w.slug, w.status) for w in p.drain_writes()] == [("b-001", "triaged")]


def test_finishing_plan_records_planned():
    """The transition that was in the contract and in zero items anywhere."""
    p = _one()
    p.force_stage("b-001", "PLAN")
    p.schedule()
    p.complete("b-001")
    assert [w.status for w in p.drain_writes()] == ["planned"]


def test_finishing_the_last_stage_records_shipped():
    p = _one()
    p.force_stage("b-001", STAGES[-1])
    p.schedule()
    p.complete("b-001")
    assert [w.status for w in p.drain_writes()] == ["shipped"]


def test_stages_that_do_not_move_the_registry_write_nothing():
    p = _one()
    p.force_stage("b-001", "IMPLEMENT")
    p.schedule()
    p.complete("b-001")
    assert p.drain_writes() == []


def test_draining_twice_yields_nothing_the_second_time():
    p = _one()
    p.schedule()
    p.complete("b-001")
    p.drain_writes()
    assert p.drain_writes() == []


def test_a_send_back_demotes_the_registry():
    """An item whose plan review rejected is no longer `planned`."""
    p = _one()
    p.force_stage("b-001", "REVIEW")
    p.schedule()
    p.send_back("b-001", "PLAN", commit="abc1234")
    assert [w.status for w in p.drain_writes()] == ["triaged"]


# ── the impediment ────────────────────────────────────────────────────────────


def test_blocking_frees_the_lane_and_records_the_edge():
    p = _one()
    p.force_stage("b-001", "IMPLEMENT")
    p.schedule()
    assert p.running
    p.block("b-001", ["B-100"])
    assert p.running == []
    write = p.drain_writes()[0]
    assert write.block_on == ["B-100"]


def test_a_blocked_item_keeps_its_stage():
    """The stage is exactly the fact needed to resume; a status would destroy it."""
    p = _one()
    p.force_stage("b-001", "IMPLEMENT")
    p.schedule()
    p.block("b-001", ["B-100"])
    assert p.item("b-001").stage == "IMPLEMENT"


def test_a_blocked_item_is_surfaced():
    p = _one()
    p.force_stage("b-001", "IMPLEMENT")
    p.block("b-001", ["B-100"])
    assert p.item("b-001").surfaced is True


def test_a_blocked_item_holds_no_lane():
    p = Pipeline(items=[Item(slug="b-001"), Item(slug="b-002")], lanes=1)
    p.schedule()
    p.block("b-001", ["B-100"])
    assert [i.slug for i in p.schedule()] == ["b-002"]


def test_blocking_on_a_reason_with_no_item_is_allowed():
    p = _one()
    p.block("b-001", note="the sponsor must decide")
    assert p.drain_writes()[0].note == "the sponsor must decide"


def test_blocking_on_neither_is_refused():
    with pytest.raises(ValueError):
        _one().block("b-001")


# ── applying the writes ───────────────────────────────────────────────────────


def _backlog(tmp_path, *rows):
    body = "# BACKLOG\n\n"
    for item_id, status in rows:
        body += (f"## {item_id} — Thing   [ ]\n\ndomain: p\nrepo: r\nsuggested_mode: review\n"
                 f"source: human\nevidence: none-yet\nwhy_now: x\nstatus: {status}\n"
                 "dod:\n  - measurable\n\n")
    path = tmp_path / "BACKLOG.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_apply_writes_moves_the_status_on_disk(tmp_path):
    backlog = _backlog(tmp_path, ("B-001", "raw"))
    assert apply_writes(backlog, [StatusWrite("b-001", status="triaged")]) == []
    assert "status: triaged" in backlog.read_text(encoding="utf-8")


def test_apply_writes_records_the_impediment_on_disk(tmp_path):
    backlog = _backlog(tmp_path, ("B-001", "planned"), ("B-100", "raw"))
    assert apply_writes(backlog, [StatusWrite("b-001", block_on=["B-100"])]) == []
    assert "blocked_by: B-100" in backlog.read_text(encoding="utf-8")


def test_an_illegal_transition_is_returned_not_raised(tmp_path):
    backlog = _backlog(tmp_path, ("B-001", "raw"))
    refusals = apply_writes(backlog, [StatusWrite("b-001", status="planned")])
    assert len(refusals) == 1 and refusals[0].startswith("b-001:")


def test_one_refusal_does_not_abort_the_others(tmp_path):
    """A run that learns three things and can record two should record two."""
    backlog = _backlog(tmp_path, ("B-001", "raw"), ("B-002", "approved"))
    refusals = apply_writes(backlog, [
        StatusWrite("b-001", status="planned"),   # illegal: raw -> planned
        StatusWrite("b-002", status="planned"),   # legal: approved -> planned
    ])
    assert len(refusals) == 1
    assert backlog.read_text(encoding="utf-8").count("status: planned") == 1


# ── eligibility comes from the registry, not from memory ──────────────────────
#
# The write-back landed before the read-back: `block()` recorded an impediment and
# nothing consumed one. A restarted session rebuilt its queue from a literal list and
# scheduled an item the registry already said could not move.

from pipeline_orchestrator import from_selection  # noqa: E402


def test_a_blocked_item_is_never_scheduled():
    """Defence in depth: the queue already excludes them, hand-built pipelines do not."""
    p = Pipeline(items=[Item(slug="b-001", blocked_by=["B-100"]), Item(slug="b-002")], lanes=4)
    assert [i.slug for i in p.schedule()] == ["b-002"]


def test_an_empty_blocker_list_still_blocks():
    """[] is "blocked by a decision with no item"; only None means not blocked."""
    p = Pipeline(items=[Item(slug="b-001", blocked_by=[])], lanes=4)
    assert p.schedule() == []


def test_none_is_the_only_unblocked_value():
    assert Item(slug="b-001").blocked is False
    assert Item(slug="b-001", blocked_by=[]).blocked is True
    assert Item(slug="b-001", blocked_by=["B-100"]).blocked is True


def test_blocking_mid_flight_marks_the_item_the_same_way():
    """An impediment discovered during a run must behave like one that arrived with it."""
    p = Pipeline(items=[Item(slug="b-001")], lanes=4)
    p.schedule()
    p.block("b-001", ["B-100"])
    assert p.item("b-001").blocked_by == ["B-100"]
    assert p.schedule() == []


def test_unparking_clears_the_impediment():
    """Otherwise an item freed by hand stays ineligible forever."""
    p = Pipeline(items=[Item(slug="b-001")], lanes=4)
    p.block("b-001", ["B-100"])
    p.unpark("b-001")
    assert [i.slug for i in p.schedule()] == ["b-001"]


# ── the bridge from the selector ──────────────────────────────────────────────


def test_from_selection_schedules_the_queue_in_order():
    p = from_selection({"queue": ["B-022", "B-033"], "walls": {}}, lanes=4)
    assert [i.slug for i in p.schedule()] == ["B-022", "B-033"]


def test_from_selection_carries_blocked_items_without_scheduling_them():
    """Carried, so the pipeline can say why an item is not running and unpark it."""
    p = from_selection({"queue": ["B-022"], "walls": {"B-001": ["B-100"]}}, lanes=4)
    assert [i.slug for i in p.schedule()] == ["B-022"]
    assert p.item("B-001").blocked is True


def test_a_carried_blocked_item_can_be_unparked_later():
    p = from_selection({"queue": [], "walls": {"B-001": ["B-100"]}}, lanes=4)
    p.unpark("B-001")
    assert [i.slug for i in p.schedule()] == ["B-001"]


def test_a_prose_wall_carries_an_empty_list_not_none():
    p = from_selection({"queue": [], "walls": {"B-001": []}}, lanes=4)
    assert p.item("B-001").blocked_by == []
    assert p.schedule() == []


def test_an_empty_selection_yields_an_empty_pipeline():
    assert from_selection({"queue": [], "walls": {}}).items == []
