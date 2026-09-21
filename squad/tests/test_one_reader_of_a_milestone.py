r"""`squad.roadmap` reads the three fields the acceptance cycle turns on.

The module exists because three scripts parsed `ROADMAP.md` with three regexes that
disagreed — see `tests/test_one_reader_of_the_roadmap.py` for what that cost. These are
the unit-level properties of the reader itself.
"""
from __future__ import annotations

import pytest

from squad.roadmap import CANONICAL_DEPENDS_LABEL, Status, find, parse

ROADMAP = (
    "# Roadmap\n\n"
    "### M0 — [x] Base\n\n**Objective:** base.\n\n"
    "**Definition of done:**\n\n- [x] base works\n\n**Dependencies:** none.\n\n---\n\n"
    "### M1 — [ ] Streaming\n\n**Objective:** sse.\n\n**Depends on:** M0\n\n"
    "**Definition of done (all must hold):**\n\n"
    "- [ ] tokens arrive incrementally\n- [ ] a drop resumes\n\n"
    "**Top risks:**\n\n1. Proxy buffering.\n\n---\n\n"
    "### M2 — [-] Quotas\n\n**Objective:** quota.\n\n"
    "**Definition of done:**\n\n- [ ] quotas enforced\n\n---\n"
)


def test_every_milestone_is_found_in_document_order() -> None:
    assert [m.id for m in parse(ROADMAP)] == ["M0", "M1", "M2"]


@pytest.mark.parametrize(
    ("milestone_id", "status"),
    [("M0", Status.DONE), ("M1", Status.OPEN), ("M2", Status.CANCELLED)],
)
def test_the_three_checkbox_states_are_read(milestone_id: str, status: Status) -> None:
    assert find(ROADMAP, milestone_id).status is status


def test_only_an_open_milestone_is_acceptable() -> None:
    """Done and cancelled are both CLOSED, and neither is acceptable — but they are
    closed for opposite reasons, so a caller refusing one must name which."""
    assert find(ROADMAP, "M1").is_acceptable
    assert not find(ROADMAP, "M0").is_acceptable
    assert not find(ROADMAP, "M2").is_acceptable
    assert find(ROADMAP, "M0").is_closed and find(ROADMAP, "M2").is_closed


def test_the_dod_stops_at_the_next_bold_label() -> None:
    """`**Top risks:**` follows M1's bullets; its numbered list is not a promise."""
    assert find(ROADMAP, "M1").dod == [
        "tokens arrive incrementally", "a drop resumes",
    ]


def test_both_dependency_spellings_are_read_and_the_file_says_which() -> None:
    """The rule taught `Depends on:` for months, and losing it was silent."""
    m1 = find(ROADMAP, "M1")
    assert m1.depends_on == ["M0"]
    assert m1.dependency_label == "Depends on"
    assert find(ROADMAP, "M0").dependency_label == CANONICAL_DEPENDS_LABEL


def test_a_bullet_without_a_checkbox_is_not_a_criterion() -> None:
    """The checkbox is what separates a promise from the prose around it."""
    text = ("### M9 — [ ] Loose\n\n**Definition of done:**\n\n"
            "- a promise with no checkbox\n\n---\n")

    assert find(text, "M9").dod == []


def test_a_milestone_that_is_not_there_is_none_not_an_exception() -> None:
    assert find(ROADMAP, "M9") is None


def test_an_empty_file_has_no_milestones() -> None:
    assert parse("") == []
