"""Where a fleet's time goes, counted so the arithmetic can be checked.

The lead's log answers "what happened". It does not answer "how much of the
window bought nothing", which is the question a stalled fleet raises and the one
this measures.

WHY NOT SUM `idle_seconds`
--------------------------
Every event carries it, and summing is the obvious move. It is also wrong:
consecutive observations OVERLAP, so the total exceeds the window and the error
grows with the poll rate. Measured on a real log, summing gave 45.8 of 56 minutes
— 82%, a number that cannot be checked against anything. The intervals between
consecutive events are disjoint by construction, add up to the window, and the
report prints both totals so a reader can verify the addition.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mechanisms" / "fleet"))

from fleet_idle import measure, read_events, render  # noqa: E402


def _events(*spec: tuple[str, int, str]) -> list[dict]:
    """(event, minute, session) → the shape the lead writes."""
    return [{"at": f"2026-09-02T12:{m:02d}:00+00:00", "event": e, "session": s}
            for e, m, s in spec]


def test_intervals_are_disjoint_and_add_up_to_the_window() -> None:
    """The property that makes the number checkable: if these disagreed, the
    report would be an opinion with decimals."""
    report = measure(_events(("start", 0, "squad1"), ("stalled", 10, ""),
                             ("start", 30, "squad2")))

    assert report.window_seconds == 30 * 60
    assert report.accounted_seconds == report.window_seconds


def test_time_after_a_handout_counts_as_productive() -> None:
    report = measure(_events(("start", 0, "squad1"), ("start", 20, "squad2")))

    assert report.productive_seconds == 20 * 60
    assert report.idle_seconds == 0


def test_time_after_a_stall_or_an_ask_counts_as_idle() -> None:
    """Both are the queue not moving; one of them costs money as well as time."""
    report = measure(_events(("stalled", 0, ""), ("asked", 10, ""), ("start", 25, "squad1")))

    assert report.idle_seconds == 25 * 60
    assert report.productive_seconds == 0
    assert round(report.idle_share, 2) == 1.0


def test_a_session_that_was_never_handed_work_is_named(tmp_path: Path) -> None:
    """Capacity paid for and unused. Invisible from the log alone — a starved
    session and one that does not exist look identical there — so it is only
    reported against the list the lead was watching."""
    report = measure(_events(("start", 0, "squad2"), ("start", 10, "squad3")),
                     watched=["squad1", "squad2", "squad3"])

    assert report.starved_sessions == ["squad1"]
    assert "squad1" in render(report)


def test_without_the_watched_list_no_session_is_called_starved() -> None:
    """Claiming a session was starved when its existence was never established
    would be inventing the finding."""
    report = measure(_events(("start", 0, "squad2"), ("start", 10, "squad3")))

    assert report.starved_sessions == []


def test_one_event_is_reported_as_nothing_to_measure() -> None:
    """Not "0% idle". A window needs two ends, and a report that says 0 here would
    be the failure this kit keeps finding: absence rendered as a measurement."""
    report = measure(_events(("start", 0, "squad1")))

    assert report.window_seconds == 0
    assert "nothing to measure" in report.detail
    assert "not 'no idle time'" in report.detail


def test_non_json_lines_in_the_log_are_skipped(tmp_path: Path) -> None:
    """The lead also prints plain lines — `==> restored 3 claim(s)` — into the same
    stream. A parser that died on those would report on nothing."""
    log = tmp_path / "lead.jsonl"
    log.write_text(
        '==> restored 3 claim(s) from the log\n'
        '{"at": "2026-09-02T12:00:00+00:00", "event": "start", "session": "squad1"}\n'
        'not json at all\n'
        '{"at": "2026-09-02T12:10:00+00:00", "event": "stalled"}\n',
        encoding="utf-8")

    rows = read_events(log)

    assert len(rows) == 2
    assert measure(rows).window_seconds == 600


def test_a_missing_log_is_not_an_idle_fleet(tmp_path: Path) -> None:
    """`read_events` returns nothing, and `measure` says so rather than reporting
    a fleet that spent no time doing anything."""
    report = measure(read_events(tmp_path / "absent.jsonl"))

    assert report.events == 0
    assert "nothing to measure" in report.detail
