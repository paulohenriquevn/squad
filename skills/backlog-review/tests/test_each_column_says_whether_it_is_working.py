"""A column with cards in it is not a column where work is happening.

The board drew ten lanes and the reader inferred activity from card count. On the
consumer measured 2026-09-18 that inference was wrong in the direction that matters:
`plan` held four cards and nothing had touched them in over two hours. "There is work in
plan" and "plan is where the work is" are different claims, and the page only supported
the first while looking like it supported the second.

FOUR STATES, AND WHY NOT TWO

    working   a phase started here and has not ended — someone is in it now
    queued    items are here, none running, and something moved recently
    stalled   items are here, none running, and nothing has moved in a while
    empty     no items

`queued` and `stalled` are the same fact read against a clock, and the distinction is the
question the owner asked five times in one afternoon: *is it stuck?* Collapsing them into
`idle` answers "no work is running", which was never in doubt, and drops the only part
that was.

WORK WITH NO CARD COUNTS

A slug the stream records under no item still marks its column `working`. Ignoring it
would rebuild, one layer up, the defect this review began with — a board reporting an
idle system while the system is working.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from board_state import build_state  # after the bootstrap above

_ITEM = """
## {id} — An item   [ ]

domain: a
repo: r
suggested_mode: review
source: human
evidence: measured
why_now: x
status: {status}
"""


def _ago(minutes: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat().replace(
        "+00:00", "Z")


def _project(tmp_path: Path, items: list[tuple[str, str]], events: list[dict]) -> Path:
    body = "# BACKLOG\n\n## Items\n" + "".join(
        _ITEM.format(id=i, status=s) for i, s in items)
    (tmp_path / "BACKLOG.md").write_text(body, encoding="utf-8")
    records = tmp_path / ".squad" / "records"
    records.mkdir(parents=True)
    (records / "cycle-events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return tmp_path


def _columns(tmp_path: Path, items, events) -> dict:
    state = build_state(_project(tmp_path, items, events))
    return {c["phase"]: c for c in state["columns"]}


def test_a_phase_that_started_and_has_not_ended_is_working(tmp_path: Path) -> None:
    cols = _columns(
        tmp_path, [("B-001", "planned")],
        [{"type": "cycle:phase:start", "cycle": "implement", "slug": "B-001",
          "timestamp": _ago(3)}])

    assert cols["implement"]["activity"] == "working"


def test_items_with_recent_movement_are_queued(tmp_path: Path) -> None:
    """Nothing running, but the queue is moving — not the same as stopped."""
    cols = _columns(
        tmp_path, [("B-001", "planned")],
        [{"type": "cycle:phase:end", "cycle": "plan", "slug": "B-001",
          "timestamp": _ago(5), "verdict": "SHIPPABLE"}])

    assert cols["plan"]["activity"] == "queued", cols["plan"]


def test_items_untouched_for_long_enough_are_stalled(tmp_path: Path) -> None:
    """The state the whole review was about."""
    cols = _columns(
        tmp_path, [("B-001", "planned")],
        [{"type": "cycle:phase:end", "cycle": "plan", "slug": "B-001",
          "timestamp": _ago(90), "verdict": "SHIPPABLE"}])

    assert cols["plan"]["activity"] == "stalled", cols["plan"]
    assert cols["plan"]["idle_minutes"] >= 89


def test_items_with_no_event_at_all_are_stalled(tmp_path: Path) -> None:
    """Undated is not recent. Treating "never moved" as fresh would mark a registry
    nobody has touched as a queue in flight."""
    cols = _columns(tmp_path, [("B-001", "raw")], [])

    assert cols["backlog"]["activity"] == "stalled"
    assert cols["backlog"]["idle_minutes"] is None


def test_a_phase_with_no_items_is_empty(tmp_path: Path) -> None:
    cols = _columns(tmp_path, [("B-001", "raw")], [])

    assert cols["release"]["activity"] == "empty"
    assert cols["release"]["items"] == 0


def test_work_with_no_card_marks_its_column_working(tmp_path: Path) -> None:
    """A slug under no item is still the cycle running."""
    cols = _columns(
        tmp_path, [("B-001", "raw")],
        [{"type": "cycle:phase:end", "cycle": "discover", "slug": "channel-loop-assembly",
          "timestamp": _ago(2), "verdict": "AWAITING_REVIEW"}])

    assert cols["discover"]["activity"] == "working", cols["discover"]
    assert cols["discover"]["uncarded"] == 1


def test_stale_work_with_no_card_does_not_claim_working(tmp_path: Path) -> None:
    """The half that keeps the previous test honest: an orphan event from last week is
    not somebody working now."""
    cols = _columns(
        tmp_path, [("B-001", "raw")],
        [{"type": "cycle:phase:end", "cycle": "discover", "slug": "channel-loop-assembly",
          "timestamp": _ago(600), "verdict": "AWAITING_REVIEW"}])

    assert cols["discover"]["activity"] != "working", cols["discover"]
