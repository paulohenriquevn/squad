"""How many items are in flight at once, and the smallest number that keeps the flow fed.

WIP is not a count of cards. It is the number of items INSIDE a phase at a moment —
started and not ended — and it was uncomputable here until the emitters recorded starts:
the stream held 37 ends against 1 start, so every instant read as zero in flight.

WHAT `wip.minimum` MEANS, AND WHAT IT DOES NOT

The owner asked for "the minimum WIP that keeps the system from idling". That is a real
quantity and it has a narrow definition: over the measured window, the smallest
concurrency at which no idle gap appears. If the system never idled, the answer is the
lowest concurrency it actually ran at — and raising WIP past that buys nothing.

It is DERIVED, never prescribed. This computes what the stream shows; it does not
recommend a limit, because a limit is a policy and the stream is evidence. An idle gap
caused by four items waiting on a work tenant is not fixed by starting a fifth, and a
number that implied otherwise would be worse than no number.

`observed` is reported beside it for exactly that reason: minimum without the range it
came from is a figure with no way to judge it.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from board_state import build_state  # after the bootstrap above

_BACKLOG = "# BACKLOG\n\n## Items\n" + "".join(
    f"\n## B-{n:03d} — Item {n}   [ ]\n\ndomain: a\nrepo: r\nsuggested_mode: review\n"
    f"source: human\nevidence: measured\nwhy_now: x\nstatus: planned\n"
    for n in (1, 2, 3))


def _at(minutes_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
            ).isoformat().replace("+00:00", "Z")


def _project(tmp_path: Path, events: list[dict]) -> Path:
    (tmp_path / "BACKLOG.md").write_text(_BACKLOG, encoding="utf-8")
    records = tmp_path / ".squad" / "records"
    records.mkdir(parents=True)
    (records / "cycle-events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return tmp_path


def _wip(tmp_path: Path, events: list[dict]) -> dict:
    return build_state(_project(tmp_path, events))["wip"]


def _span(item: str, cycle: str, start: int, end: int | None) -> list[dict]:
    out = [{"type": "cycle:phase:start", "cycle": cycle, "slug": item,
            "timestamp": _at(start)}]
    if end is not None:
        out.append({"type": "cycle:phase:end", "cycle": cycle, "slug": item,
                    "timestamp": _at(end), "verdict": "PASS"})
    return out


def test_two_open_phases_are_two_in_flight(tmp_path: Path) -> None:
    """`current` counts starts with no end, which is what in-flight means."""
    events = _span("B-001", "implement", 30, None) + _span("B-002", "review", 20, None)

    assert _wip(tmp_path, events)["current"] == 2


def test_a_closed_phase_leaves_flight(tmp_path: Path) -> None:
    events = _span("B-001", "implement", 30, 10) + _span("B-002", "review", 20, None)

    assert _wip(tmp_path, events)["current"] == 1


def test_the_peak_is_the_most_that_ever_overlapped(tmp_path: Path) -> None:
    """Three items overlapped for a while, then two closed. `current` is 1 and the
    window saw 3 — reporting only the first would hide what the system has carried."""
    events = (_span("B-001", "implement", 60, 20)
              + _span("B-002", "review", 50, 15)
              + _span("B-003", "plan", 40, None))

    wip = _wip(tmp_path, events)
    assert wip["peak"] == 3, wip
    assert wip["current"] == 1


def test_a_window_with_an_idle_gap_reports_it(tmp_path: Path) -> None:
    """Nothing ran between minute 40 and minute 30. That gap is the whole reason the
    question is asked."""
    events = _span("B-001", "implement", 60, 40) + _span("B-002", "review", 30, None)

    wip = _wip(tmp_path, events)
    assert wip["idle_gaps"] >= 1, wip
    assert wip["minimum"] is None, (
        "a window with an idle gap has no minimum that avoided idling — the honest "
        "answer is that the measurement cannot name one")


def test_a_window_with_no_gap_names_the_minimum(tmp_path: Path) -> None:
    """Continuous work at concurrency 1 then 2: the smallest that kept it fed is 1."""
    events = _span("B-001", "implement", 60, 20) + _span("B-002", "review", 30, None)

    wip = _wip(tmp_path, events)
    assert wip["idle_gaps"] == 0, wip
    assert wip["minimum"] == 1, wip


def test_an_empty_stream_says_it_measured_nothing(tmp_path: Path) -> None:
    """No starts, no series, no number. The state this fix was written to leave
    behind — and it must read as absence, never as zero work in flight."""
    wip = _wip(tmp_path, [])

    assert wip["measured"] is False
    assert wip["current"] == 0
    assert wip["minimum"] is None
