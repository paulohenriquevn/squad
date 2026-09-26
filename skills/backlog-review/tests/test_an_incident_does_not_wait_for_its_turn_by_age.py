"""A production incident entered the queue by age, behind everything older than it.

`rank()` ordered on `(does not unblock a halt, status rank, item number)`. Age decides
among equals, which is right — it is the one signal an agent that wants to proceed cannot
inflate. What it could not express is that some items are not equals for a reason that has
nothing to do with when they were filed.

`source: live-incident` is already in the schema (`cycle-backlog.md § Item schema`) and
already means what it says: the item exists because something is wrong in the running
system NOW. Every hour it waits is an hour the system stays wrong, and that cost does not
depend on the item's age — it depends on the incident's.

SCOPE, STATED SO THE CLAIM STOPS AT WHAT IS MEASURED. The band covers `live-incident` and
nothing else. A security finding, a legal obligation and an SLA breach belong in the same
band by every argument above, and the registry has NO FIELD for them — so they are not
covered, and this file says so rather than letting the name `obligation` imply they are.
When a field exists, the band widens and this docstring changes with it.

ABOVE THE UNBLOCKING RULE, and the two never competed before. An item that unblocks a halt
turns a stopped item into a moving one; an incident is costing while it waits. Both beat
age; between them, the one already burning wins.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from select_backlog_item import Item, rank  # noqa: E402


def _item(number: int, *, status: str = "triaged", source: str = "human") -> Item:
    return Item(item_id=f"B-{number:03d}", title=f"item {number}",
                fields={"status": status, "source": source})


def _ids(items: list[Item]) -> list[str]:
    return [i.item_id for i in items]


def test_an_incident_outranks_older_items_of_the_same_status() -> None:
    older = [_item(n) for n in (1, 2, 3)]
    incident = _item(90, source="live-incident")

    assert _ids(rank([*older, incident]))[0] == "B-090"


def test_an_incident_outranks_an_unblocking_item() -> None:
    """Both beat age. Between them, the one already burning wins."""
    unblocker = _item(5)
    incident = _item(90, source="live-incident")

    order = _ids(rank([unblocker, incident], unblocking=frozenset({"B-005"})))

    assert order == ["B-090", "B-005"]


def test_two_incidents_are_still_ordered_by_age() -> None:
    """The band changes who is compared, never how. Age decides inside it."""
    late = _item(90, source="live-incident")
    early = _item(40, source="live-incident")

    assert _ids(rank([late, early])) == ["B-040", "B-090"]


def test_an_incident_still_loses_to_status_inside_its_own_band() -> None:
    """`triaged` before `raw` holds: an incident nobody measured is not ready to work.

    Promoting a raw incident over a triaged one would put the chain on an item whose
    evidence is `none-yet`, which is the state G5 exists to hold.
    """
    raw_incident = _item(10, status="raw", source="live-incident")
    triaged_incident = _item(80, status="triaged", source="live-incident")

    assert _ids(rank([raw_incident, triaged_incident])) == ["B-080", "B-010"]


def test_the_ordinary_order_is_unchanged_when_no_incident_is_present() -> None:
    """THE CONTROL. A queue with no incident must rank exactly as it did before."""
    items = [_item(30), _item(10), _item(20, status="raw")]

    order = _ids(rank(items, unblocking=frozenset({"B-030"})))

    assert order == ["B-030", "B-010", "B-020"]


def test_a_source_that_merely_mentions_an_incident_is_not_one() -> None:
    """The band is a field value, not a substring. `discover-live-test` is not it."""
    plain = _item(5, source="discover-live-test")
    older = _item(1)

    assert _ids(rank([plain, older])) == ["B-001", "B-005"]
