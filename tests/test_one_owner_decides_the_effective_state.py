"""Two implementations of "is this item blocked", and only one had a caller.

`backlog_status.effective_state` and `effective_state_of` compute the derived `blocked`
state the module docstring calls its central idea. Nothing in the running system called
either: the one production consumer, `check_backlog_structure._effective_counts`,
reimplemented the rule inline.

The rule is not trivial — a blocker that shipped or was killed stops blocking, and a
prose impediment naming no item holds until a human removes the line. Two copies of that
is two places for it to drift, and the copy with no caller is the one that drifts
unnoticed while its own tests keep passing.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "mechanisms" / "cycle"))
sys.path.insert(0, str(_ROOT / "skills" / "backlog-review" / "scripts"))

import backlog_status  # noqa: E402 — post-bootstrap import
import check_backlog_structure  # noqa: E402 — post-bootstrap import


def test_the_counter_delegates_to_the_owner(monkeypatch) -> None:
    """Not "they agree today" — that the counter ASKS rather than recomputing."""
    calls: list[tuple] = []
    real = backlog_status.effective_state

    def _spy(status: str, blockers: list[str], statuses: dict[str, str]) -> str:
        calls.append((status, tuple(blockers)))
        return real(status, blockers, statuses)

    monkeypatch.setattr(check_backlog_structure, "effective_state", _spy)
    items = [
        check_backlog_structure.Item("B-001", "a title", {"status": "triaged", "blocked_by": "B-002"}, line=1),
        check_backlog_structure.Item("B-002", "a title", {"status": "triaged", "blocked_by": ""}, line=2),
    ]

    check_backlog_structure._effective_counts(items)

    assert calls, "the counter still computes the rule itself"


def test_a_blocker_that_shipped_no_longer_blocks() -> None:
    items = [
        check_backlog_structure.Item("B-001", "a title", {"status": "triaged", "blocked_by": "B-002"}, line=1),
        check_backlog_structure.Item("B-002", "a title", {"status": "shipped", "blocked_by": ""}, line=2),
    ]

    counts = check_backlog_structure._effective_counts(items)

    assert counts.get("blocked", 0) == 0, counts


def test_an_open_blocker_still_blocks() -> None:
    items = [
        check_backlog_structure.Item("B-001", "a title", {"status": "triaged", "blocked_by": "B-002"}, line=1),
        check_backlog_structure.Item("B-002", "a title", {"status": "triaged", "blocked_by": ""}, line=2),
    ]

    assert check_backlog_structure._effective_counts(items).get("blocked") == 1


def test_a_prose_impediment_holds_with_no_item_to_resolve_it() -> None:
    """"awaiting the sponsor's decision" names no id; only a human clears it."""
    items = [check_backlog_structure.Item(
        "B-001", "a title",
        {"status": "triaged", "blocked_by": "awaiting the sponsor's decision"}, line=1)]

    assert check_backlog_structure._effective_counts(items).get("blocked") == 1
