"""The scheduler that keeps items moving while one of them waits.

Every test here maps to an acceptance criterion in
`records/alignment/pipeline-orchestrator-alignment.md`, which is ALIGNED at 91%
after an alignment judge REFUSED an earlier draft. Three of its findings are
pinned below, because a defect a reviewer caught once is a defect that returns:

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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from pipeline_orchestrator import (  # noqa: E402
    STAGES, Item, Pipeline, lane_budget,
)


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
    p.schedule(); p.complete("b-014")          # DISCOVER done, now at PLAN
    p.schedule(); p.park("b-014", reason="AWAITING_REVIEW")
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
