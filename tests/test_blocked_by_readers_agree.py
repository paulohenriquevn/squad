"""Three scripts read `blocked_by`, and today they disagreed four times.

`select_backlog_item.py` decides whether an item may be worked on.
`check_backlog_structure.py` decides whether the registry is well formed.
`backlog_status.py` decides whether the writer may advance an item to shipped.
They parse the same field, deliberately without sharing code — the gate must be
able to review a registry written by anything, so it cannot import the writer
and inherit its assumptions.

The cost of that choice is that a rule can be fixed in one copy and stay broken
in the other, and on 2026-09-02 that happened three times in one day:

  - the self-mention filter lived in the selector; the gate lacked it and
    reported 28 false blockers, refusing every push to a consumer
  - the prose-outlives-the-edge rule lived in the gate; the selector lacked it
    and handed the queue an item a person still owed a decision on
  - a stage list lived in the spawner; its test kept a copy that went stale

An audit on 2026-09-03 found a fourth: the writer parsed `blocked_by` at
`mechanisms/cycle/backlog_status.py:100` and refused a `shipped` transition on
the id list unfiltered — no self-mention drop, no `carries_prose` check. A
single line of prose naming the item itself deadlocked its ship: the writer
refused because the item blocked itself, the item stayed open because the
writer refused, and no consumer could ship a fix for the state.

These assertions do not merge the readers. They pin the invariants that must
hold across all three, so the next divergence fails here instead of in a
consumer.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "backlog-review" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from check_backlog_structure import (  # noqa: E402
    Item,
    carries_prose,
    declares_impediment,
    impediment_edges,
)
from select_backlog_item import live_blockers  # noqa: E402
from backlog_status import live_blockers as writer_live_blockers  # noqa: E402

#: Real shapes, taken from a consumer's registry rather than invented. The prose
#: ones are the majority: when the field was first measured, seven of eight items
#: named a sponsor decision or an external action and only one named an item.
VALUES = [
    "",
    "none",
    "B-075",
    "B-075, B-076",
    "aguardando decisao do sponsor",
    "aguardando B-075 aterrissar antes de medir de novo",
    "aguardando disposicao: bala 2 movida para B-061 (shipped). Vide report B-060.",
    "blocked on an external vendor; see B-061 (shipped) for the history",
    "B-060",
]


def _item(raw: str, item_id: str = "B-060") -> Item:
    it = Item(item_id=item_id, title="t", line=1)
    it.fields["blocked_by"] = raw
    it.fields["status"] = "triaged"
    return it


@pytest.mark.parametrize("raw", VALUES, ids=range(len(VALUES)))
def test_a_stated_reason_is_never_read_as_no_impediment_by_one_and_an_impediment_by_the_other(
        raw: str) -> None:
    """The invariant the selector broke: when the value states a reason, the
    repository cannot know the reason is discharged, so the item is not free.

    B-060 read "bala 2 movida para B-061 (shipped) ... Vide report B-060". The
    selector lifted both ids, dropped the self-mention, found B-061 shipped, and
    returned NOT BLOCKED — handing the queue an item whose status disposition a
    person still owed. The gate had held the opposite rule for `stale_block` all
    along.
    """
    statuses = {"B-060": "triaged", "B-061": "shipped", "B-075": "triaged",
                "B-076": "shipped"}
    blockers = live_blockers(_item(raw), statuses)

    if declares_impediment(raw) and carries_prose(raw):
        assert blockers is not None, (
            f"the selector calls {raw!r} free while the gate reads a stated reason "
            f"in it; nothing in the repository can tell whether that reason is "
            f"discharged")


@pytest.mark.parametrize("raw", VALUES, ids=range(len(VALUES)))
def test_neither_reader_ever_treats_an_item_as_its_own_blocker(raw: str) -> None:
    """The invariant the gate broke: prose about an item mentions that item.

    "Vide report /idea-to-release B-060 de 2026-08-31" made B-060 its own
    impediment, then a ring of one. 28 false blockers, every push refused.
    """
    statuses = {"B-060": "triaged", "B-061": "shipped", "B-075": "triaged"}

    from_gate = impediment_edges(raw, "B-060")
    from_selector = live_blockers(_item(raw), statuses) or []

    if carries_prose(raw):
        assert "B-060" not in from_gate, "the gate holds it against itself"
    assert "B-060" not in from_selector, "the selector holds it against itself"


@pytest.mark.parametrize("raw", VALUES, ids=range(len(VALUES)))
def test_the_selector_never_names_a_blocker_the_gate_does_not_see(raw: str) -> None:
    """Extraction may differ in what it FILTERS, never in what it FINDS. A
    blocker only one of them can see is a divergence in the parse itself, which
    is the class of bug neither script's own tests can catch."""
    statuses = {"B-060": "triaged", "B-061": "shipped", "B-075": "triaged",
                "B-076": "shipped"}

    from_selector = set(live_blockers(_item(raw), statuses) or [])
    from_gate = set(impediment_edges(raw, "B-060"))

    assert from_selector <= from_gate, (
        f"{raw!r}: selector sees {sorted(from_selector - from_gate)} and the gate "
        f"does not")


# ── the writer as the third reader ────────────────────────────────────────────
#
# `backlog_status.py` is the WRITER. When advancing an item to `shipped` it
# reads `blocked_by`, extracts ids, and refuses the transition if any named id
# is still open. Until the audit on 2026-09-03 it did the extraction without
# the self-mention filter the selector already carried and without the
# `carries_prose` distinction the gate already carried. A `blocked_by` value
# whose prose named the item itself made the writer deadlock the ship: the
# item cannot ship because it is blocked by itself, and stays open precisely
# because it cannot ship.


@pytest.mark.parametrize("raw", VALUES, ids=range(len(VALUES)))
def test_the_writer_and_the_selector_agree_on_whether_an_item_is_free(raw: str) -> None:
    """A ship the selector would clear must not be a ship the writer refuses.

    The selector holds the queue: its `None` verdict says "this item is not
    blocked, hand it out". The writer holds the terminal transition: its refusal
    stops a ship. If the selector says free and the writer refuses, work that
    passed every gate cannot land, and the item stays open forever because the
    close is exactly what is refused. That was the audit's finding: on B-060's
    `blocked_by` — a sentence naming the item itself — the selector correctly
    said free (self-mention filtered) and the writer refused (self-mention
    kept), and the item deadlocked its own ship.
    """
    statuses = {"B-060": "planned", "B-061": "shipped", "B-075": "triaged",
                "B-076": "shipped"}

    selector_free = live_blockers(_item(raw), statuses) is None
    writer_free = writer_live_blockers(raw, "B-060", statuses) is None

    if selector_free:
        assert writer_free, (
            f"{raw!r}: the selector calls this free and the writer refuses to "
            f"ship it — the item cannot close because closing is what is refused")


@pytest.mark.parametrize("raw", VALUES, ids=range(len(VALUES)))
def test_the_writer_never_treats_an_item_as_its_own_blocker(raw: str) -> None:
    """Prose about an item mentions that item, and the writer must not read
    that as a self-block. The exact defect the gate carried until it was
    fixed: 28 false blockers, every push refused. In the writer the same
    defect is worse — the refusal is terminal, not just noisy."""
    statuses = {"B-060": "planned", "B-061": "shipped", "B-075": "triaged",
                "B-076": "shipped"}

    from_writer = writer_live_blockers(raw, "B-060", statuses) or []

    if carries_prose(raw):
        assert "B-060" not in from_writer, "the writer holds it against itself"


@pytest.mark.parametrize("raw", VALUES, ids=range(len(VALUES)))
def test_a_stated_reason_is_never_read_as_no_impediment_by_the_writer(raw: str) -> None:
    """The prose-outlives-the-edge rule the selector eventually learned: when
    the value states a reason, the repository cannot know the reason is
    discharged, so the writer must refuse the ship even after every named id
    has closed. Without this the writer silently ships past a decision a
    person still owes.
    """
    statuses = {"B-060": "planned", "B-061": "shipped", "B-075": "shipped",
                "B-076": "shipped"}

    writer_verdict = writer_live_blockers(raw, "B-060", statuses)

    if declares_impediment(raw) and carries_prose(raw):
        assert writer_verdict is not None, (
            f"the writer calls {raw!r} free while a stated reason lives in it; "
            f"nothing in the repository can tell whether that reason is discharged")


@pytest.mark.parametrize("raw", VALUES, ids=range(len(VALUES)))
def test_the_writer_never_refuses_on_a_blocker_the_gate_does_not_see(raw: str) -> None:
    """Extraction may differ in what it FILTERS, never in what it FINDS.
    The writer refusing a ship on an id the gate never reports as an edge
    is the class of divergence that produces the same false-blocker deadlock
    that hit the gate on 2026-09-02, arriving through the write path instead
    of the review path.
    """
    statuses = {"B-060": "planned", "B-061": "shipped", "B-075": "triaged",
                "B-076": "shipped"}

    from_writer = set(writer_live_blockers(raw, "B-060", statuses) or [])
    from_gate = set(impediment_edges(raw, "B-060"))

    assert from_writer <= from_gate, (
        f"{raw!r}: writer refuses ship on {sorted(from_writer - from_gate)} "
        f"and the gate does not see it as an edge")
