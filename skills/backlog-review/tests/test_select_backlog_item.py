"""The selection the maintenance chain specified and nothing implemented.

`cycle-maintenance.md § Chain` carried the filter and the ranking — with a section
justifying both — since it was written. No code read it, so the order was a paragraph
an agent was asked to remember, and the only runner carried a literal list of ids.
"""
from __future__ import annotations

from pathlib import Path

from backlog_fixtures import item_block

from select_backlog_item import live_blockers, rank, select
from check_backlog_structure import _parse_items


def _backlog(*blocks: str) -> str:
    return "# Backlog\n\n## Itens\n\n" + "".join(blocks)


# ── the ranking the contract justifies ────────────────────────────────────────


def test_triaged_outranks_raw() -> None:
    """A triaged item carries measured evidence; its cost to finish is known."""
    text = _backlog(item_block("B-001", status="raw"), item_block("B-002", status="triaged"))
    assert select(text).item_id == "B-002"


def test_oldest_first_within_a_status() -> None:
    """Ids are monotonic and never reused, so a lower number was registered earlier."""
    text = _backlog(item_block("B-009", status="triaged"), item_block("B-003", status="triaged"))
    assert select(text).item_id == "B-003"


def test_rank_puts_every_triaged_before_every_raw() -> None:
    text = _backlog(item_block("B-001", status="raw"), item_block("B-002", status="triaged"),
                    item_block("B-003", status="raw"), item_block("B-004", status="triaged"))
    assert [i.item_id for i in rank(_parse_items(text))] == ["B-002", "B-004", "B-001", "B-003"]


def test_planned_is_not_selectable() -> None:
    """It is open, but it already has a plan — SELECT hands out work, not plans."""
    text = _backlog(item_block("B-001", status="planned"))
    assert select(text).verdict == "BACKLOG_EMPTY"


def test_closed_items_are_not_selectable() -> None:
    text = _backlog(item_block("B-001", status="shipped"), item_block("B-002", status="killed"))
    assert select(text).verdict == "BACKLOG_EMPTY"


# ── eligibility, which the filter alone no longer decides ─────────────────────


def test_a_blocked_item_is_skipped_for_the_next_one() -> None:
    """The chain's `status in {raw, triaged}` predates impediments."""
    text = _backlog(item_block("B-001", status="triaged", extra="blocked_by: B-100\n"),
                    item_block("B-002", status="triaged"),
                    item_block("B-100", status="raw"))
    assert select(text).item_id == "B-002"


def test_an_item_blocked_by_prose_is_skipped() -> None:
    text = _backlog(item_block("B-001", status="triaged", extra="blocked_by: the sponsor must decide\n"),
                    item_block("B-002", status="triaged"))
    assert select(text).item_id == "B-002"


def test_a_resolved_blocker_frees_the_item_with_no_second_edit() -> None:
    text = _backlog(item_block("B-001", status="triaged", extra="blocked_by: B-100\n"),
                    item_block("B-100", status="shipped"))
    assert select(text).item_id == "B-001"


def test_everything_blocked_is_not_an_empty_backlog() -> None:
    """"Run a sweep" would add items beside a wall instead of clearing it."""
    text = _backlog(item_block("B-001", status="triaged", extra="blocked_by: B-100\n"),
                    item_block("B-100", status="planned"))
    result = select(text)
    assert result.verdict == "BACKLOG_BLOCKED"
    assert result.walls == {"B-001": ["B-100"]}


def test_an_empty_backlog_is_distinguished_from_a_blocked_one() -> None:
    assert select(_backlog(item_block("B-001", status="shipped"))).verdict == "BACKLOG_EMPTY"


def test_live_blockers_separates_prose_from_not_blocked() -> None:
    """[] and None mean different things: blocked-by-a-decision, and not blocked."""
    text = _backlog(item_block("B-001", status="triaged", extra="blocked_by: a decision\n"),
                    item_block("B-002", status="triaged"))
    items = {i.item_id: i for i in _parse_items(text)}
    assert live_blockers(items["B-001"], {}) == []
    assert live_blockers(items["B-002"], {}) is None


# ── the narrow question ───────────────────────────────────────────────────────


def test_asking_about_a_blocked_item_is_refused() -> None:
    text = _backlog(item_block("B-001", status="triaged", extra="blocked_by: B-100\n"),
                    item_block("B-100", status="raw"))
    result = select(text, requested="B-001")
    assert result.verdict == "BACKLOG_BLOCKED"
    assert "B-100" in result.reason


def test_asking_about_a_shipped_item_is_refused() -> None:
    """Refused, but named: `BACKLOG_BLOCKED` here claimed a wall that did not exist."""
    result = select(_backlog(item_block("B-001", status="shipped")), requested="B-001")
    assert result.verdict == "ITEM_SHIPPED"
    assert result.item_id == "B-001"


def test_asking_about_an_unknown_item_is_refused() -> None:
    assert select(_backlog(item_block("B-001", status="raw")), requested="B-404").verdict == "BACKLOG_BLOCKED"


def test_the_gate_and_the_selector_agree() -> None:
    """Two answers to one question is the defect a second implementation creates."""
    text = _backlog(item_block("B-001", status="raw"), item_block("B-002", status="triaged"))
    picked = select(text).item_id
    assert select(text, requested=picked).verdict == "ITEM_SELECTED"


# ── the batch caller ──────────────────────────────────────────────────────────


def test_the_queue_is_the_full_order_not_just_the_head() -> None:
    """The pipeline fills more than one lane; re-running per lane would be absurd."""
    text = _backlog(item_block("B-003", status="raw"), item_block("B-001", status="triaged"),
                    item_block("B-002", status="triaged"))
    assert select(text).queue == ["B-001", "B-002", "B-003"]


def test_the_queue_excludes_blocked_items() -> None:
    text = _backlog(item_block("B-001", status="triaged", extra="blocked_by: B-100\n"),
                    item_block("B-002", status="triaged"), item_block("B-100", status="raw"))
    assert "B-001" not in select(text).queue


def test_the_wall_is_reported_even_on_success() -> None:
    text = _backlog(item_block("B-001", status="triaged"),
                    item_block("B-002", status="triaged", extra="blocked_by: B-100\n"),
                    item_block("B-100", status="raw"))
    result = select(text)
    assert result.verdict == "ITEM_SELECTED"
    assert result.walls["B-002"] == ["B-100"]


# ── blocked, versus already past this gate ────────────────────────────────────
#
# Found by using the tool: an item that had reached `planned`, whose blocker had
# SHIPPED, came back BACKLOG_BLOCKED. Nothing was blocking it — it was ready for the
# next phase. One verdict was carrying two states, and only one of them is a wall.


def test_a_planned_item_is_in_flight_not_blocked() -> None:
    text = _backlog(item_block("B-001", status="planned"))
    result = select(text, requested="B-001")
    assert result.verdict == "ITEM_IN_FLIGHT"


def test_a_planned_item_whose_blocker_shipped_is_not_reported_as_blocked() -> None:
    """The exact case that surfaced the defect."""
    text = _backlog(item_block("B-001", status="planned", extra="blocked_by: B-002\n"),
                    item_block("B-002", status="shipped"))
    assert select(text, requested="B-001").verdict == "ITEM_IN_FLIGHT"


def test_a_shipped_item_says_so() -> None:
    text = _backlog(item_block("B-001", status="shipped"))
    assert select(text, requested="B-001").verdict == "ITEM_SHIPPED"


def test_a_killed_item_says_so() -> None:
    text = _backlog(item_block("B-001", status="killed", extra="kill_reason: measured otherwise\n"))
    assert select(text, requested="B-001").verdict == "ITEM_KILLED"


def test_a_genuinely_blocked_item_is_still_blocked() -> None:
    """The distinction only helps if the real wall keeps its name."""
    text = _backlog(item_block("B-001", status="triaged", extra="blocked_by: B-002\n"),
                    item_block("B-002", status="raw"))
    assert select(text, requested="B-001").verdict == "BACKLOG_BLOCKED"


def test_an_unknown_status_is_not_silently_called_in_flight() -> None:
    """A status outside the contract means the contract moved; do not guess."""
    text = _backlog(item_block("B-001", status="marinating"))
    assert select(text, requested="B-001").verdict == "BACKLOG_BLOCKED"


def test_none_of_these_are_selectable() -> None:
    for status in ("planned", "shipped", "killed"):
        text = _backlog(item_block("B-001", status=status,
                                   extra="kill_reason: x\n" if status == "killed" else ""))
        assert select(text).verdict != "ITEM_SELECTED"
