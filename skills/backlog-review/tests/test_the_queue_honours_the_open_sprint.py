"""The sprint's band, where the queue actually reads it.

`squad/sprint.py` computes the band and `tests/test_a_sprint_is_a_block_with_a_goal_and_a_close.py`
pins it. This file asserts the other half — that `rank()` consults it — because a band
nothing reads is a field, not an order, and the kit has a measured history of exactly that:
a gate declared in two rules and executed by nothing.

The position in the key is the whole design. Focus sorts AFTER the two things that already
outrank everything and BEFORE status:

    1. obligation          `source: live-incident` — costing while it waits, and the cost
                           does not depend on the item's age
    2. unblocks a halt     finishing it turns a stopped item back into a moving one
    3. THE SPRINT          declared focus
    4. status              triaged before raw
    5. age                 the only signal nobody can inflate

Focus does not outrank a live incident, and that ordering is not a preference: an
obligation is costing now, and a sprint is a statement about what matters generally.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from squad.sprint import open_sprint  # noqa: E402

from select_backlog_item import Item, rank  # noqa: E402


def _item(item_id: str, *, status: str = "triaged", source: str = "human") -> Item:
    return Item(item_id=item_id, title=f"title for {item_id}",
                fields={"status": status, "source": source})


def _project(tmp_path: Path) -> Path:
    (tmp_path / ".squad").mkdir(parents=True)
    return tmp_path


def test_an_admitted_item_outranks_an_older_one_outside_the_sprint(tmp_path: Path) -> None:
    root = _project(tmp_path)
    open_sprint(root, sprint_id="S-001", goal="the seam is reachable",
                admitted=["B-300"], opened_by="human/paulo")
    ordered = rank([_item("B-100"), _item("B-300")], project_root=root)
    assert [i.item_id for i in ordered] == ["B-300", "B-100"], (
        "age still decided over declared focus")


def test_an_obligation_still_outranks_the_sprint(tmp_path: Path) -> None:
    """An incident costs while it waits; a sprint says what matters generally."""
    root = _project(tmp_path)
    open_sprint(root, sprint_id="S-001", goal="a goal", admitted=["B-300"],
                opened_by="human/paulo")
    ordered = rank([_item("B-300"), _item("B-400", source="live-incident")],
                   project_root=root)
    assert [i.item_id for i in ordered] == ["B-400", "B-300"]


def test_an_unblocker_still_outranks_the_sprint(tmp_path: Path) -> None:
    root = _project(tmp_path)
    open_sprint(root, sprint_id="S-001", goal="a goal", admitted=["B-300"],
                opened_by="human/paulo")
    ordered = rank([_item("B-300"), _item("B-500")],
                   unblocking=frozenset({"B-500"}), project_root=root)
    assert [i.item_id for i in ordered] == ["B-500", "B-300"]


def test_status_still_decides_inside_the_sprint(tmp_path: Path) -> None:
    """The band is a band. Inside it, nothing changed."""
    root = _project(tmp_path)
    open_sprint(root, sprint_id="S-001", goal="a goal", admitted=["B-300", "B-301"],
                opened_by="human/paulo")
    ordered = rank([_item("B-300", status="raw"), _item("B-301", status="triaged")],
                   project_root=root)
    assert [i.item_id for i in ordered] == ["B-301", "B-300"]


def test_with_no_sprint_the_order_is_exactly_what_it_was(tmp_path: Path) -> None:
    root = _project(tmp_path)
    ordered = rank([_item("B-300"), _item("B-100")], project_root=root)
    assert [i.item_id for i in ordered] == ["B-100", "B-300"], "age must still decide"


def test_rank_without_a_project_root_still_works(tmp_path: Path) -> None:
    """Every existing caller passes no root, and none of them may break."""
    ordered = rank([_item("B-300"), _item("B-100")])
    assert [i.item_id for i in ordered] == ["B-100", "B-300"]
