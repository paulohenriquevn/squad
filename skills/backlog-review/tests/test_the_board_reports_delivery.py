"""The board said where everything was and never whether anything had shipped.

A reader could see ten lanes, eight blockers and a WIP figure, and still not answer the
question the person paying for the work actually has: *are we delivering?* On the
consumer measured 2026-09-18 the answer was **nothing, in twenty-two hours** — fifteen
items, zero shipped — and no field on the page said so. Absence read as an empty column,
which looks the same as a column nobody has got to yet.

THROUGHPUT AND LEAD TIME, AND THE HONESTY EACH ONE NEEDS

    shipped        items that reached a terminal status
    throughput     those per day over the measured window
    lead_time_p50  registry entry to terminal, median

None of the three is computable from an empty set, and each returns None rather than a
zero. `0 items/day` is a measurement — it says the system ran and delivered nothing.
`None` says nothing has finished yet, which on a registry three days old is a different
and less alarming fact. Collapsing them would make a young project look like a failing
one, and a failing one look measured.

The window is stated with the number. A throughput figure with no window attached is
arithmetic, not evidence.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from board_state import build_state  # after the bootstrap above

_ITEM = ("\n## {id} — Item   [ ]\n\ndomain: a\nrepo: r\nsuggested_mode: review\n"
         "source: human\nevidence: measured\nwhy_now: x\nstatus: {status}\n")


def _at(days: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace(
        "+00:00", "Z")


def _delivery(tmp_path: Path, items, events) -> dict:
    (tmp_path / "BACKLOG.md").write_text(
        "# BACKLOG\n\n## Items\n" + "".join(
            _ITEM.format(id=i, status=s) for i, s in items), encoding="utf-8")
    records = tmp_path / ".squad" / "records"
    records.mkdir(parents=True)
    (records / "cycle-events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return build_state(tmp_path)["delivery"]


def test_nothing_shipped_reports_none_not_zero(tmp_path: Path) -> None:
    """The distinction the whole strip exists for. `0/day` says the system delivered
    nothing; `None` says nothing has finished yet, and a three-day-old registry is not
    a failing one."""
    d = _delivery(tmp_path, [("B-001", "raw"), ("B-002", "planned")], [])

    assert d["shipped"] == 0
    assert d["throughput_per_day"] is None, d
    assert d["lead_time_p50_hours"] is None, d


def test_shipped_items_are_counted(tmp_path: Path) -> None:
    d = _delivery(
        tmp_path, [("B-001", "shipped"), ("B-002", "shipped"), ("B-003", "raw")], [])

    assert d["shipped"] == 2


def test_throughput_is_per_day_over_a_stated_window(tmp_path: Path) -> None:
    """Two items over four days is half an item a day, and the window travels with it —
    a rate with no window attached is arithmetic, not evidence."""
    events = [
        {"type": "cycle:phase:end", "cycle": "release", "slug": "B-001",
         "timestamp": _at(4), "verdict": "RELEASED"},
        {"type": "cycle:phase:end", "cycle": "release", "slug": "B-002",
         "timestamp": _at(0.5), "verdict": "RELEASED"},
    ]
    d = _delivery(tmp_path, [("B-001", "shipped"), ("B-002", "shipped")], events)

    assert d["window_days"] is not None and d["window_days"] >= 3, d
    assert d["throughput_per_day"] is not None
    assert 0.3 <= d["throughput_per_day"] <= 1.0, d


def test_a_killed_item_counts_as_finished_not_shipped(tmp_path: Path) -> None:
    """`cycle-backlog.md`: "killing one is the cycle working". It leaves the queue, and
    counting it as delivery would inflate the number with work nobody received."""
    d = _delivery(tmp_path, [("B-001", "killed"), ("B-002", "shipped")], [])

    assert d["shipped"] == 1, d
    assert d["killed"] == 1, d


def test_the_page_renders_delivery(tmp_path: Path) -> None:
    html = (Path(__file__).resolve().parents[1] / "scripts" / "board.html").read_text(
        encoding="utf-8")

    assert "delivery" in html, "delivery is computed and the page does not show it"
