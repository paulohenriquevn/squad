"""The status writer: legal transitions, refused ones, and impediment edges.

These assert over the CONTENT the writer produces and the exceptions it raises,
never over the wording of a message — `check_prose_tests.py` exists because the
opposite habit pins prose that is free to change.
"""
from __future__ import annotations

import pytest
from backlog_status import (
    Refused,
    _blocks,
    _status_of,
    advance,
    block,
    blocked_by_of,
    effective_state,
    parse_blocked_by,
    unblock,
)


def _backlog(*items: tuple[str, str, str]) -> str:
    """Build a backlog from (id, status, extra) triples."""
    out = ["# BACKLOG\n"]
    for item_id, status, extra in items:
        out.append(
            f"## {item_id} — Something measurable   [ ]\n\n"
            f"domain: platform\nrepo: engine-go\nsuggested_mode: review\n"
            f"source: human\nevidence: none-yet\nwhy_now: the window widened\n"
            f"status: {status}\n{extra}"
            "dod:\n  - p95 below 800ms\n\n"
        )
    return "".join(out)


def _status(content: str, item_id: str) -> str:
    start, end = _blocks(content)[item_id]
    return _status_of(content[start:end])


def _blockers(content: str, item_id: str) -> list[str]:
    start, end = _blocks(content)[item_id]
    return blocked_by_of(content[start:end])


# ── the transition the measurement found missing ──────────────────────────────

def test_triaged_advances_to_approved_and_not_straight_to_planned():
    """The step that never happened in any install now has TWO halves.

    `triaged -> planned` was one move answering two questions: is the hunch real,
    and are we doing it? That is what let one registry hold 174 items and exactly
    2 `planned` — the measurement happened and the decision never had a place to
    be recorded. `approved` is that place.
    """
    content = _backlog(("B-001", "triaged", ""))
    assert _status(advance(content, "B-001", "approved"), "B-001") == "approved"

    with pytest.raises(Refused, match="not a legal transition"):
        advance(content, "B-001", "planned")


def test_approved_advances_to_planned():
    """Once the decision is recorded, the plan is the next step."""
    content = _backlog(("B-001", "approved", ""))
    assert _status(advance(content, "B-001", "planned"), "B-001") == "planned"


def test_raw_cannot_jump_to_planned():
    """Contract: nothing reaches a plan without passing DISCOVER's measurement."""
    with pytest.raises(Refused):
        advance(_backlog(("B-001", "raw", "")), "B-001", "planned")


def test_planned_is_sent_back_to_approved_not_to_triaged():
    """The send-back lands where plans are produced, not where decisions are.

    A plan that failed review did not un-decide the work. Sending it to `triaged`
    would discard the approval along with the plan, and someone would have to
    approve the same item twice for one bad draft.

    The reason is passed because a backward move is a withdrawal and
    `cycle-maintenance.md § Rollback` says it is never silent. What this test pins
    is the DESTINATION, which the note does not change.
    """
    content = _backlog(("B-001", "planned", ""))
    sent_back = advance(content, "B-001", "approved",
                        withdraw_reason="Paulo withdrew the plan: the measurement changed")
    assert _status(sent_back, "B-001") == "approved"

    with pytest.raises(Refused, match="not a legal transition"):
        advance(content, "B-001", "triaged")


def test_approved_can_be_sent_back_to_triaged():
    """Withdrawing the decision itself, before any plan existed, is a real move.

    It now carries its reason: the move IS a withdrawal, and the rule has always
    said a withdrawal is recorded. What this test pins is that the move exists.
    """
    content = _backlog(("B-001", "approved", ""))
    withdrawn = advance(content, "B-001", "triaged",
                        withdraw_reason="Paulo reversed the approval: the driver moved")
    assert _status(withdrawn, "B-001") == "triaged"


def test_shipped_is_terminal():
    with pytest.raises(Refused):
        advance(_backlog(("B-001", "shipped", "")), "B-001", "triaged")


def test_killing_without_a_reason_is_refused():
    with pytest.raises(Refused):
        advance(_backlog(("B-001", "raw", "")), "B-001", "killed")


def test_killing_with_a_reason_writes_both_fields():
    content = advance(_backlog(("B-001", "raw", "")), "B-001", "killed", kill_reason="measurement did not support it")
    start, end = _blocks(content)["B-001"]
    body = content[start:end]
    assert _status_of(body) == "killed"
    assert "measurement did not support it" in body


def test_advancing_an_absent_item_is_refused():
    with pytest.raises(Refused):
        advance(_backlog(("B-001", "raw", "")), "B-999", "triaged")


def test_only_the_named_item_moves():
    """A writer that rewrites its neighbours is worse than no writer."""
    content = _backlog(("B-001", "raw", ""), ("B-002", "triaged", ""))
    updated = advance(content, "B-001", "triaged")
    assert _status(updated, "B-002") == "triaged"
    assert updated.count("## B-") == 2


# ── impediments ───────────────────────────────────────────────────────────────

def test_blocking_records_the_edge_on_the_blocked_side():
    content = block(_backlog(("B-001", "planned", ""), ("B-002", "raw", "")), "B-001", ["B-002"])
    assert _blockers(content, "B-001") == ["B-002"]
    assert _blockers(content, "B-002") == []


def test_blocking_on_an_unfiled_item_is_refused():
    """File the item before pointing at it — an edge to nothing never resolves."""
    with pytest.raises(Refused):
        block(_backlog(("B-001", "planned", "")), "B-001", ["B-404"])


def test_an_item_cannot_block_itself():
    with pytest.raises(Refused):
        block(_backlog(("B-001", "planned", "")), "B-001", ["B-001"])


def test_a_cycle_is_refused_at_write_time():
    content = _backlog(("B-001", "planned", ""), ("B-002", "raw", ""))
    content = block(content, "B-002", ["B-001"])
    with pytest.raises(Refused):
        block(content, "B-001", ["B-002"])


def test_a_longer_ring_is_also_refused():
    content = _backlog(("B-001", "planned", ""), ("B-002", "raw", ""), ("B-003", "raw", ""))
    content = block(content, "B-002", ["B-003"])
    content = block(content, "B-003", ["B-001"])
    with pytest.raises(Refused):
        block(content, "B-001", ["B-002"])


def test_blocking_twice_accumulates_without_duplicating():
    content = _backlog(("B-001", "planned", ""), ("B-002", "raw", ""), ("B-003", "raw", ""))
    content = block(content, "B-001", ["B-002"])
    content = block(content, "B-001", ["B-003", "B-002"])
    assert _blockers(content, "B-001") == ["B-002", "B-003"]


def test_unblocking_one_leaves_the_others():
    content = _backlog(("B-001", "planned", ""), ("B-002", "raw", ""), ("B-003", "raw", ""))
    content = block(content, "B-001", ["B-002", "B-003"])
    content = unblock(content, "B-001", ["B-002"])
    assert _blockers(content, "B-001") == ["B-003"]


def test_unblocking_everything_drops_the_line():
    content = _backlog(("B-001", "planned", ""), ("B-002", "raw", ""))
    content = block(content, "B-001", ["B-002"])
    content = unblock(content, "B-001")
    start, end = _blocks(content)["B-001"]
    assert "blocked_by" not in content[start:end]


def test_clearing_one_id_keeps_the_stated_reason_beside_it():
    """The prose outlives the id edge, and `unblock` has to honour that too.

    `live_blockers` states the rule: "the ids in it are context, the reason is
    the barrier, and nothing in this repository can tell whether the reason is
    discharged." `advance` implements it — it refuses to ship while the line says
    anything. `unblock` did not: removing the named id left `remaining` empty and
    dropped the whole field, prose included, so the ship that had just been
    refused was allowed and the registry kept no trace of the impediment.
    """
    content = _backlog(("B-001", "planned", ""), ("B-002", "shipped", ""))
    content = block(content, "B-001", ["B-002"], "awaiting the sponsor's decision on hosting")
    with pytest.raises(Refused):
        advance(content, "B-001", "shipped")

    content = unblock(content, "B-001", ["B-002"])

    start, end = _blocks(content)["B-001"]
    body = content[start:end]
    assert "B-002" not in body
    assert "awaiting the sponsor's decision on hosting" in body
    with pytest.raises(Refused):
        advance(content, "B-001", "shipped")


def test_clearing_one_of_two_ids_keeps_both_the_other_id_and_the_reason():
    content = _backlog(("B-001", "planned", ""), ("B-002", "raw", ""), ("B-003", "raw", ""))
    content = block(content, "B-001", ["B-002", "B-003"], "and the sponsor has to sign")

    content = unblock(content, "B-001", ["B-002"])

    start, end = _blocks(content)["B-001"]
    body = content[start:end]
    assert _blockers(content, "B-001") == ["B-003"]
    assert "and the sponsor has to sign" in body


def test_clearing_every_id_of_a_pure_id_edge_still_drops_the_line():
    """No prose to keep means nothing to keep. The field goes."""
    content = _backlog(("B-001", "planned", ""), ("B-002", "raw", ""))
    content = block(content, "B-001", ["B-002"])

    content = unblock(content, "B-001", ["B-002"])

    start, end = _blocks(content)["B-001"]
    assert "blocked_by" not in content[start:end]


def test_unblocking_an_unblocked_item_is_refused():
    with pytest.raises(Refused):
        unblock(_backlog(("B-001", "planned", "")), "B-001")


def test_a_blocked_item_cannot_ship():
    content = _backlog(("B-001", "planned", ""), ("B-002", "raw", ""))
    content = block(content, "B-001", ["B-002"])
    with pytest.raises(Refused):
        advance(content, "B-001", "shipped")


def test_shipping_the_blocker_frees_the_blocked_item():
    """Resolution needs no second edit: the edge is read against live status."""
    content = _backlog(("B-001", "planned", ""), ("B-002", "planned", ""))
    content = block(content, "B-001", ["B-002"])
    content = advance(content, "B-002", "shipped")
    assert _status(advance(content, "B-001", "shipped"), "B-001") == "shipped"


# ── the derived state ─────────────────────────────────────────────────────────

def test_effective_state_is_blocked_only_while_a_blocker_is_open():
    assert effective_state("planned", ["B-002"], {"B-002": "raw"}) == "blocked"
    assert effective_state("planned", ["B-002"], {"B-002": "shipped"}) == "planned"
    assert effective_state("planned", ["B-002"], {"B-002": "killed"}) == "planned"


def test_effective_state_needs_only_one_open_blocker():
    assert effective_state("triaged", ["B-002", "B-003"], {"B-002": "shipped", "B-003": "raw"}) == "blocked"


def test_a_closed_item_is_never_reported_as_blocked():
    assert effective_state("shipped", ["B-002"], {"B-002": "raw"}) == "shipped"


def test_no_blockers_means_the_stage_stands():
    assert effective_state("triaged", [], {}) == "triaged"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("", []),
        ("none", []),
        ("B-002", ["B-002"]),
        ("B-002, B-003", ["B-002", "B-003"]),
        ("B-002  B-003", ["B-002", "B-003"]),
    ],
)
def test_blocked_by_parsing(raw, expected):
    assert parse_blocked_by(raw) == expected


# ── the field as it was already being used ────────────────────────────────────
#
# Eight items in one install carried `blocked_by` before it was specified, and seven
# of them named no item at all. These pin that the writer serves that usage.

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from backlog_status import (  # noqa: E402 — imported here, beside the behaviour it covers; the comment above says which
    blocked_by_raw,
    declares_impediment,
    effective_state_of,
)


def test_prose_impediments_yield_no_edges_but_still_block():
    """"awaiting the sponsor's decision" is an impediment with nothing to point at."""
    raw = "decisão do patrocinador, nomeada no próprio código"
    assert parse_blocked_by(raw) == []
    assert declares_impediment(raw) is True


def test_ids_are_extracted_from_prose():
    # The value this parser must handle is the one somebody actually wrote.
    raw = "B-075 — e o bloqueio foi CONFIRMADO por medição em 2026-08-12"  # english-only: verbatim from B-075 in a real registry
    assert parse_blocked_by(raw) == ["B-075"]


def test_none_spellings_declare_no_impediment():
    for raw in ("", "  ", "none", "-", "nothing"):
        assert declares_impediment(raw) is False


def test_a_prose_blocked_item_cannot_ship():
    content = _backlog(("B-001", "planned", "blocked_by: awaiting the sponsor\n"))
    with pytest.raises(Refused):
        advance(content, "B-001", "shipped")


def test_a_prose_impediment_can_be_cleared():
    """Otherwise the item is stuck forever, and it was.

    The two readers of `blocked_by` disagreed about what counts. `advance` asks
    `blocked_by_raw` and refuses to ship while the line says anything; `unblock`
    asked `blocked_by_of`, which extracts item ids, and refused with "is not
    blocked" when the line held prose. So an item blocked by a decision — the
    shape `--because` exists to write — could neither ship nor be cleared.

    Measured 2026-09-05 on a real registry: B-168 declared "fix estrutural
    pertence ao repo do kit", the fix landed and was verified, and the item could
    not be moved by the mechanism at all. Hand-editing the file is what this
    module exists to prevent, so the deadlock had no legitimate exit.
    """
    content = _backlog(("B-001", "planned", "blocked_by: awaiting the sponsor\n"))
    cleared = unblock(content, "B-001")
    assert "blocked_by" not in cleared
    # And the point of clearing it: the item can now finish.
    assert "status: shipped" in advance(cleared, "B-001", "shipped")


def test_clearing_named_blockers_still_refuses_when_the_item_has_none():
    """The refusal is right when the caller NAMES ids that are not there; it was
    only wrong for the bare `--unblock`, which means "clear whatever is there"."""
    content = _backlog(("B-001", "planned", "blocked_by: awaiting the sponsor\n"))
    with pytest.raises(Refused):
        unblock(content, "B-001", ["B-002"])


def test_effective_state_of_reads_prose_as_blocked():
    content = _backlog(("B-001", "planned", "blocked_by: awaiting the sponsor\n"))
    start, end = _blocks(content)["B-001"]
    assert effective_state_of(content[start:end], {}) == "blocked"


def test_effective_state_of_resolves_id_edges_against_live_status():
    content = _backlog(("B-001", "planned", "blocked_by: B-002\n"), ("B-002", "shipped", ""))
    start, end = _blocks(content)["B-001"]
    assert effective_state_of(content[start:end], {"B-002": "shipped"}) == "planned"


def test_blocking_with_a_reason_and_no_id():
    content = block(_backlog(("B-001", "planned", "")), "B-001", [], note="the sponsor must decide")
    start, end = _blocks(content)["B-001"]
    assert "the sponsor must decide" in blocked_by_raw(content[start:end])


def test_blocking_with_neither_an_id_nor_a_reason_is_refused():
    with pytest.raises(Refused):
        block(_backlog(("B-001", "planned", "")), "B-001", [])


def test_an_id_and_a_reason_coexist_in_one_value():
    content = _backlog(("B-001", "planned", ""), ("B-002", "raw", ""))
    content = block(content, "B-001", ["B-002"], note="and the sponsor must ratify it")
    start, end = _blocks(content)["B-001"]
    raw = blocked_by_raw(content[start:end])
    assert parse_blocked_by(raw) == ["B-002"]
    assert "ratify" in raw
