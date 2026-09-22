"""`lead_time_p50_hours` was `None` with a comment saying the item carries no entry date.

It carries one. `check_backlog_structure._parse_items` reads `Registrado YYYY-MM-DD` /
`registered YYYY-MM-DD` out of the block body into `Item.registered_on`, and the board
imports that exact parser. What it did NOT do was carry the field through `_board_items`,
which builds the dicts `_delivery` then measures — so the fact existed two calls upstream
and was discarded on the way down.

The comment was therefore right about `_delivery`'s INPUTS and wrong about the item, and
the difference is the whole defect: a reader of that line concluded the registry had no
entry timestamp and that adding one was a schema change.

WHY DAYS AND NOT HOURS. `registered_on` is a DATE — midnight. The end is a real timestamp,
so the arithmetic is exact and the INPUT is not: every figure carries ±1 day from the start
side. Reporting hours would put three significant figures on that. Days with a stated
uncertainty is the honest shape; rounding to whole days would hide the arithmetic without
removing the uncertainty, which is worse.

COVERAGE TRAVELS WITH THE NUMBER. Most items predate the convention and carry no
registration line, so a p50 over "the ones that had a date" is a p50 over a subset. The
payload says which subset, and `None` still means nothing could be measured — never zero.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from board_state import _delivery  # noqa: E402

NOW = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)


def _item(iid: str, *, status: str, registered: date | None) -> dict:
    return {"id": iid, "status": status,
            "registered_on": registered.isoformat() if registered else None}


def _event(iid: str, *, days_ago: float) -> dict:
    stamp = NOW - timedelta(days=days_ago)
    return {"slug": iid, "timestamp": stamp.isoformat().replace("+00:00", "Z"),
            "kind": "phase_end", "verdict": "RELEASED"}


def test_one_shipped_item_with_a_date_yields_its_own_lead_time() -> None:
    items = [_item("B-001", status="shipped", registered=date(2026, 9, 12))]
    events = [_event("B-001", days_ago=0), _event("B-002", days_ago=8)]

    out = _delivery(items, events, NOW)

    # 2026-09-12T00:00 (the date, at midnight) to the event at 2026-09-22T12:00.
    assert out["lead_time_p50_days"] == 10.5


def test_the_median_is_the_median_and_not_the_mean() -> None:
    items = [_item(f"B-00{n}", status="shipped", registered=date(2026, 9, d))
             for n, d in ((1, 21), (2, 20), (3, 2))]
    events = [_event("B-001", days_ago=0), _event("B-002", days_ago=0),
              _event("B-003", days_ago=0)]

    out = _delivery(items, events, NOW)

    # spans 1.5 · 2.5 · 20.5 — the median is the middle one, not the mean.
    assert out["lead_time_p50_days"] == 2.5, "a 20-day outlier must not move the median"


def test_coverage_travels_with_the_number(tmp_path: Path) -> None:
    """A p50 over the items that happened to carry a date is a p50 over a subset."""
    items = [_item("B-001", status="shipped", registered=date(2026, 9, 12)),
             _item("B-002", status="shipped", registered=None),
             _item("B-003", status="shipped", registered=None)]
    events = [_event(i, days_ago=0) for i in ("B-001", "B-002", "B-003")]

    out = _delivery(items, events, NOW)

    assert out["lead_time_measured_over"] == 1
    assert out["lead_time_terminal_total"] == 3


def test_no_item_with_a_date_reports_none_not_zero() -> None:
    """The distinction `_delivery` already makes for throughput, kept here."""
    items = [_item("B-001", status="shipped", registered=None)]
    events = [_event("B-001", days_ago=0)]

    out = _delivery(items, events, NOW)

    assert out["lead_time_p50_days"] is None
    assert out["lead_time_measured_over"] == 0


def test_an_item_with_a_date_and_no_event_is_not_measured() -> None:
    """Half a measurement is not a measurement: the end has to be on the record too."""
    items = [_item("B-001", status="shipped", registered=date(2026, 9, 12))]
    events = [_event("B-999", days_ago=1)]

    out = _delivery(items, events, NOW)

    assert out["lead_time_p50_days"] is None
    assert out["lead_time_measured_over"] == 0


def test_a_killed_item_is_not_delivery() -> None:
    """`cycle-backlog.md`: killing one is the cycle working, and nobody received anything.

    `_delivery` already counts `killed` apart from `shipped`; a lead time that folded it
    in would time how long the system took to abandon something and call it delivery.
    """
    items = [_item("B-001", status="killed", registered=date(2026, 9, 2))]
    events = [_event("B-001", days_ago=0)]

    out = _delivery(items, events, NOW)

    assert out["lead_time_p50_days"] is None


def test_the_hours_field_is_gone_rather_than_left_lying() -> None:
    """A field whose unit no longer matches its data is a field that misleads."""
    items = [_item("B-001", status="shipped", registered=date(2026, 9, 12))]

    assert "lead_time_p50_hours" not in _delivery(items, [_event("B-001", days_ago=0)], NOW)
