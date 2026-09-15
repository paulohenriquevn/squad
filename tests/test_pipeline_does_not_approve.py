"""The pipeline moves items; it does not decide that they will be done.

`approved` is the registry's record that somebody with the authority committed to
the work. A pipeline that writes it turns the state into "the pipeline reached this
item", and the decision the state exists to hold stops existing.

That is not a policy invented here. `rules/decision-delegation.txt` sorts walls into
a delegable set and a retained one, and `governance` — "the item itself names
autonomous execution as the bypass its governance exists to prevent" — is retained.
Approving IS that bypass, so no consumer's delegation file can hand it over: moving
`governance` into the delegated column is the exact move the rule forbids.

The consequence is that the pipeline parks where a person is required. Slower by
design, and the alternative is a registry whose `approved` count measures nothing.

Written for kit#32, which reported the pipeline could not advance past PLAN at all.
It could not, and the fix is not to let it walk through — it is to stop where the
walk requires a decision, and to say so.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mechanisms" / "fleet"))
sys.path.insert(0, str(ROOT / "mechanisms" / "cycle"))

import backlog_status  # noqa: E402
from pipeline_orchestrator import (  # noqa: E402
    STATUS_ON_ENTERING,
    STATUS_ON_SEND_BACK,
    Item,
    Pipeline,
)


def _at(stage: str, status: str | None) -> Pipeline:
    p = Pipeline([Item(slug="b-001", status=status)], lanes=2)
    p.force_stage("b-001", stage)
    p.schedule()
    return p


# ── the decision the pipeline may not make ───────────────────────────────────


def test_finishing_plan_on_a_triaged_item_does_not_write_planned() -> None:
    """The walk `triaged -> planned` skips the decision. It must not happen."""
    p = _at("PLAN", status="triaged")
    p.complete("b-001")
    assert [w.status for w in p.drain_writes()] == []


def test_the_item_parks_naming_the_decision_it_is_missing() -> None:
    """A silent stop is indistinguishable from a stall. It must say why."""
    p = _at("PLAN", status="triaged")
    p.complete("b-001")
    item = p.item("b-001")
    assert item.parked
    assert item.surfaced, "a wall only a person can open has to be visible"
    assert "approved" in item.park_reason
    assert "triaged" in item.park_reason, "the reason names where the item actually is"


def test_it_parks_at_implement_so_unparking_resumes_the_work() -> None:
    """Parking must not throw away the plan that PLAN just finished."""
    p = _at("PLAN", status="triaged")
    p.complete("b-001")
    assert p.item("b-001").stage == "IMPLEMENT"


def test_an_approved_item_walks_into_implement() -> None:
    """The stop is about the missing decision, not about IMPLEMENT."""
    p = _at("PLAN", status="approved")
    p.complete("b-001")
    assert [w.status for w in p.drain_writes()] == ["planned"]
    assert not p.item("b-001").parked


# ── the send-back lands at the decision, not past it ─────────────────────────


def test_a_send_back_returns_a_plan_to_the_decision_that_still_stands() -> None:
    """Review rejected the PLAN, not the commitment.

    Demoting to `triaged` would withdraw the decision and force it to be made
    again — by the pipeline, which is the thing it may not do. `planned -> approved`
    is what the contract prescribes, and it is a different map from the forward one.
    """
    p = _at("REVIEW", status="planned")
    p.send_back("b-001", "PLAN", commit="abc1234")
    assert [w.status for w in p.drain_writes()] == ["approved"]


def test_the_send_back_map_is_not_the_forward_map() -> None:
    """Reusing the forward map is the defect; a shared object would hide it.

    The two are now different in a stronger way than when this was written: the forward
    map has NO entry for PLAN at all. It used to write `triaged` there, which demoted an
    approved item on its way in and made IMPLEMENT unreachable — so the forward
    direction writes nothing and the backward one writes `approved`, which is the state
    a rejected plan returns to with the decision still standing.
    """
    assert "PLAN" not in STATUS_ON_ENTERING, (
        "a forward write on entering PLAN demotes an approved item; that is kit#32's "
        "shape and it made every item park at IMPLEMENT")
    assert STATUS_ON_SEND_BACK["PLAN"] == "approved"


# ── the durable half: no write the pipeline emits can be refused ─────────────


def test_every_status_the_pipeline_writes_is_reachable_under_the_contract() -> None:
    """The class of defect, not the two instances.

    kit#32 and the send-back bug are both one shape: a stage-to-status map written
    when the contract had fewer states, emitting a transition `advance()` refuses.
    This fails whenever a map gains a status no legal transition can reach.
    """
    reachable = {to for froms in backlog_status.ALLOWED.values() for to in froms}
    for name, table in (("STATUS_ON_ENTERING", STATUS_ON_ENTERING),
                        ("STATUS_ON_SEND_BACK", STATUS_ON_SEND_BACK)):
        for stage, status in table.items():
            assert status in backlog_status.LEGAL_STATUS, f"{name}[{stage}] is not a status"
            assert status in reachable, (
                f"{name}[{stage}] = {status!r}, which no transition in "
                f"backlog_status.ALLOWED can reach"
            )


def test_the_send_back_status_is_legal_from_where_the_send_back_starts() -> None:
    """`planned -> approved` has to be in the contract, not just plausible."""
    assert "approved" in backlog_status.ALLOWED["planned"]
    assert "triaged" not in backlog_status.ALLOWED["planned"], (
        "if this ever becomes legal, the send-back choice above needs re-arguing"
    )


# ── the justification has to keep being true ─────────────────────────────────


def test_the_delegation_rule_still_retains_governance() -> None:
    """The code above cites this file. A citation that stopped being true is worse
    than none, because it reads as authority."""
    rule = (ROOT / "rules" / "decision-delegation.txt").read_text(encoding="utf-8")
    retained = next(
        line.split("=", 1)[1] for line in rule.splitlines()
        if line.startswith("retained_classes")
    )
    assert "governance" in retained, (
        "the pipeline refuses to approve BECAUSE governance is retained; "
        "if it moved to the delegated column, that refusal needs a new argument"
    )
