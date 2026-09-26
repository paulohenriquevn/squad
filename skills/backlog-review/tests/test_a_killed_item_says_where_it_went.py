"""`supersedes` resolved backwards only, so a dead item could not name its replacement.

The edge is written on the NEW item — `B-201` declares `supersedes: B-014` — and
`check_backlog_structure` validates it in that direction: the target must exist and must
be `killed`. A reader who arrives at `B-014` finds `status: killed`, a `kill_reason`, and
no way to discover that the question was re-asked and answered.

That is the whole cost of the gap, and it is the shape this session has spent the day on:
a fact that exists in one direction only. The registry HOLDS the answer — every edge is in
the same file — and nothing exposed it.

DERIVED, NEVER STORED. A `superseded_by` field written on the killed item would be a second
copy of an edge the file already carries, and two copies of one fact drift the moment
somebody edits one of them. `cycle-backlog.md § Lineage` keeps `supersedes` as the single
authority; the reverse edge is computed on read.

WHAT THIS DOES NOT ADD. There is still no `pivot` status. An item whose QUESTION was wrong
is killed and re-filed, exactly as one whose hypothesis was refuted — the two are
distinguished only by what `kill_reason` says, in prose. Adding a status would change a
vocabulary every reader in the kit shares, for a distinction a sentence already carries.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from check_backlog_structure import (  # noqa: E402 — post-bootstrap import
    _parse_items as parse_registry,
    lineage_successors,
)

REGISTRY = """# Backlog

## B-014 — The agent endpoint resumes any conversation by id

domain: platform
repo: core
suggested_mode: review
source: human
evidence: measured 2026-08-01 against the running service
why_now: it changed under us
status: killed
kill_reason: the measurement did not support the hypothesis
dod:
- [ ] a test that fails on the current state

## B-201 — The endpoint authorises before it resumes

domain: platform
repo: core
suggested_mode: review
source: human
evidence: measured 2026-09-01 against the running service
why_now: the earlier question was the wrong one
status: triaged
supersedes: B-014
dod:
- [ ] a test that fails on the current state
"""


def _items(text: str = REGISTRY):
    return parse_registry(text)


def test_a_killed_item_names_the_item_that_replaced_it() -> None:
    successors = lineage_successors(_items())

    assert successors["B-014"] == ["B-201"], (
        "the registry holds the edge and nothing exposed it in the direction a reader "
        "arriving at the dead item actually needs"
    )


def test_an_item_nothing_replaced_is_absent_rather_than_empty() -> None:
    """Absent and "replaced by nothing" are different answers to a reader.

    An empty list under every id would make "this one was superseded" indistinguishable
    from "this one is in the map because the map covers everything".
    """
    assert "B-201" not in lineage_successors(_items())


def test_two_items_superseding_one_are_both_named() -> None:
    """A question split in two is still an answer to the first one."""
    text = REGISTRY + """
## B-202 — The endpoint rejects a resumed id from another tenant

domain: platform
repo: core
suggested_mode: review
source: human
evidence: measured 2026-09-02 against the running service
why_now: the split half nobody covered
status: triaged
supersedes: B-014
dod:
- [ ] a test that fails on the current state
"""

    assert lineage_successors(parse_registry(text))["B-014"] == ["B-201", "B-202"]


def test_a_regression_resolves_the_same_way() -> None:
    """`regression_of` is the other lineage edge and has the same blind spot."""
    text = REGISTRY.replace("status: killed", "status: shipped").replace(
        "kill_reason: the measurement did not support the hypothesis\n", ""
    ).replace("supersedes: B-014", "regression_of: B-014")

    assert lineage_successors(parse_registry(text))["B-014"] == ["B-201"]


def test_an_edge_naming_nothing_produces_no_successor() -> None:
    """Prose in the field is already a `lineage_missing` finding; it must not also
    invent an edge here."""
    text = REGISTRY.replace("supersedes: B-014", "supersedes: the earlier attempt")

    assert lineage_successors(parse_registry(text)) == {}
