r"""A start that died is not the item being worked, and every reader must agree.

MEASURED ON A CONSUMER, 2026-09-21. The board's headline read `WORKING B-184 —
implement started and has not ended · 20h ago`, while the session driving that
repository had spent the day closing B-220, B-221 and B-222 and its most recent commit
was `a726b476c docs(adr): … (B-222)`, four minutes old. The stream:

    B-184  implement start  02:28:18      <- and never closed
    ───────────────────────  26 events, 4 other items
    B-185  implement end    14:01:52      IMPLEMENTATION_COMPLETE

The same page also printed, in its own notices panel: *"phase never closed: implement
opened on B-184 19.9h ago … It is not counted as work in flight."* One screen, one
event, two contradictory claims — and the wrong one in the headline.

WHY IT SURVIVED THREE FIXES

The lesson has been learned three times, in three consumers, and never at the source:

  1. `_phases_running` learned to close an orphan start when the SAME item ends a later
     phase. Its docstring records B-001 running `plan` for four days. That defence
     cannot fire when the item never emits anything again, which is B-184.
  2. `_wip` learned `ABANDON_AFTER_HOURS`, with the note *"`_wip` did not inherit the
     lesson"* written into the test that fixed it.
  3. `_working_item` never learned it at all.

Eleven readers consume `running_phase` — two in `board_state.py` and nine in
`board.html`. Any of them could be the fourth. So the window is applied where the field
is BUILT: a start past the window is not reported as running to anyone, and no consumer
can disagree because none of them is asked.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from board_state import ABANDON_AFTER_HOURS, build_state  # after the bootstrap above

_BACKLOG = (
    "# BACKLOG\n\n## Items\n\n"
    "## B-184 — The one with the dead start   [ ]\n\ndomain: a\nrepo: r\n"
    "suggested_mode: review\nsource: human\nevidence: measured\nwhy_now: x\n"
    "status: planned\n\n"
    "## B-185 — The one that finished   [ ]\n\ndomain: a\nrepo: r\n"
    "suggested_mode: review\nsource: human\nevidence: measured\nwhy_now: x\n"
    "status: planned\n"
)


def _at(hours: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat().replace(
        "+00:00", "Z")


def _state(tmp_path: Path, events: list[dict]) -> dict:
    (tmp_path / "BACKLOG.md").write_text(_BACKLOG, encoding="utf-8")
    records = tmp_path / ".squad" / "records"
    records.mkdir(parents=True)
    (records / "cycle-events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return build_state(tmp_path)


#: The consumer's stream, reduced to what produced the wrong headline.
_THE_CONSUMER_CASE = [
    {"type": "cycle:phase:start", "cycle": "plan", "slug": "B-184", "timestamp": _at(20.1)},
    {"type": "cycle:phase:end", "cycle": "plan", "slug": "B-184",
     "timestamp": _at(20.0), "verdict": "SHIPPABLE"},
    {"type": "cycle:phase:start", "cycle": "implement", "slug": "B-184", "timestamp": _at(20.0)},
    {"type": "cycle:phase:start", "cycle": "implement", "slug": "B-185", "timestamp": _at(9.0)},
    {"type": "cycle:phase:end", "cycle": "implement", "slug": "B-185",
     "timestamp": _at(8.0), "verdict": "IMPLEMENTATION_COMPLETE"},
]


def test_a_dead_start_is_not_the_working_item(tmp_path: Path) -> None:
    """The headline itself, which is what a reader acts on."""
    working = _state(tmp_path, _THE_CONSUMER_CASE).get("working")

    assert not (working and working.get("item") == "B-184"), (
        f"the board claims work on an item whose phase died 20h ago: {working}"
    )


def test_no_reader_is_told_the_dead_phase_is_running(tmp_path: Path) -> None:
    """The field itself, because eleven readers consume it and any could be the next."""
    items = {i["id"]: i for i in _state(tmp_path, _THE_CONSUMER_CASE)["items"]}

    assert items["B-184"].get("running_phase") is None, (
        "running_phase still names a phase that died; every consumer of the field "
        "inherits the claim"
    )
    assert items["B-184"].get("running_since") is None


def test_the_page_does_not_contradict_itself(tmp_path: Path) -> None:
    """The invariant that makes a fourth instance impossible to ship quietly.

    An item cannot be the one being worked AND be listed as an abandoned start. The
    consumer's board asserted both about B-184 on the same screen.
    """
    state = _state(tmp_path, _THE_CONSUMER_CASE)
    working = (state.get("working") or {}).get("item")
    abandoned = {row["slug"] for row in state["wip"].get("abandoned_detail", [])}

    assert working not in abandoned, (
        f"{working} is the headline AND in the abandoned list — the same contradiction, "
        f"in a different consumer"
    )


def test_a_start_inside_the_window_is_still_running(tmp_path: Path) -> None:
    """The guard must not widen: a phase legitimately runs for hours."""
    fresh = [{"type": "cycle:phase:start", "cycle": "implement", "slug": "B-184",
              "timestamp": _at(ABANDON_AFTER_HOURS - 1)}]

    state = _state(tmp_path, fresh)
    items = {i["id"]: i for i in state["items"]}

    assert items["B-184"].get("running_phase") == "implement"
    assert (state.get("working") or {}).get("item") == "B-184"


def test_the_window_is_the_one_the_kit_already_declared(tmp_path: Path) -> None:
    """One number, not a second threshold that drifts from the first."""
    assert ABANDON_AFTER_HOURS == 4
