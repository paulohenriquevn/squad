"""A board that answers "where is everything" and never "is this going well".

The page opened with ten lanes and a search box. Everything on it was true and none of
it was a conclusion, so the reader had to assemble one: count the amber cards, notice
which lanes had not moved, remember that four items in review with no implement event is
not ordinary. A CTO with four minutes does not assemble; they read the top line and stop.

So the board leads with a headline: one state, one sentence saying why, and the count of
things waiting on a person. It is DERIVED from what is already computed — column
activity, blocked ownership, phases with no record — and asserts nothing the rest of the
page does not already show.

THE ORDER IS THE ARGUMENT

    blocked      something needs a person, and until it arrives nothing downstream moves
    at risk      the record disagrees with itself — a phase produced work nothing logged
    stalled      items are sitting and nobody is working them
    working      a phase is running right now
    idle         nothing is here to do

Read top-down, the first one that matches wins. Ordering by urgency rather than by count
is deliberate: one item waiting on a person outranks nine sitting in backlog, because
the nine will move on their own and the one will not.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from board_state import build_state  # after the bootstrap above

_ITEM = ("\n## {id} — Item   [ ]\n\ndomain: a\nrepo: r\nsuggested_mode: review\n"
         "source: human\nevidence: measured\nwhy_now: x\nstatus: {status}\n{extra}")


def _at(mins: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=mins)).isoformat().replace(
        "+00:00", "Z")


def _project(tmp_path: Path, items, events) -> Path:
    (tmp_path / "BACKLOG.md").write_text(
        "# BACKLOG\n\n## Items\n" + "".join(
            _ITEM.format(id=i, status=s, extra=x) for i, s, x in items),
        encoding="utf-8")
    records = tmp_path / ".squad" / "records"
    records.mkdir(parents=True)
    (records / "cycle-events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return tmp_path


def _headline(tmp_path: Path, items, events) -> dict:
    return build_state(_project(tmp_path, items, events))["headline"]


def test_a_wall_only_a_person_can_clear_leads(tmp_path: Path) -> None:
    """The loudest state, and it outranks any amount of ordinary queue."""
    head = _headline(
        tmp_path,
        [("B-001", "planned", "blocked_by: a work tenant nobody has\n"),
         ("B-002", "raw", ""), ("B-003", "raw", "")],
        [])

    assert head["state"] == "blocked", head
    assert head["needs_person"] == 1
    assert "person" in head["detail"].lower()


def test_a_phase_with_no_record_is_at_risk(tmp_path: Path) -> None:
    """Nothing is waiting on a person, and the record still disagrees with itself."""
    head = _headline(
        tmp_path, [("B-001", "planned", "")],
        [{"type": "cycle:phase:end", "cycle": "review", "slug": "B-001",
          "timestamp": _at(5), "verdict": "PASS"}])

    assert head["state"] == "at_risk", head
    assert "implement" in head["detail"]


def test_a_running_phase_says_working(tmp_path: Path) -> None:
    """The item carries its earlier phases on purpose: without them it is genuinely
    `at_risk`, and `at_risk` outranks `working` — a risk does not resolve itself and
    work in flight does."""
    head = _headline(
        tmp_path, [("B-001", "planned", "")],
        [{"type": "cycle:phase:end", "cycle": "discover", "slug": "B-001",
          "timestamp": _at(40), "verdict": "PASS"},
         {"type": "cycle:phase:end", "cycle": "plan", "slug": "B-001",
          "timestamp": _at(30), "verdict": "SHIPPABLE"},
         {"type": "cycle:phase:start", "cycle": "implement", "slug": "B-001",
          "timestamp": _at(2)}])

    assert head["state"] == "working", head


def test_items_sitting_with_nobody_on_them_is_stalled(tmp_path: Path) -> None:
    head = _headline(tmp_path, [("B-001", "raw", ""), ("B-002", "raw", "")], [])

    assert head["state"] == "stalled", head
    assert head["detail"]


def test_an_empty_registry_is_idle_not_alarming(tmp_path: Path) -> None:
    """No items is not a problem, and a page that shouts about it trains the reader to
    ignore the headline."""
    (tmp_path / "BACKLOG.md").write_text("# BACKLOG\n\n## Items\n", encoding="utf-8")
    (tmp_path / ".squad" / "records").mkdir(parents=True)

    head = build_state(tmp_path)["headline"]

    assert head["state"] == "idle", head


def test_the_headline_is_rendered(tmp_path: Path) -> None:
    html = (Path(__file__).resolve().parents[1] / "scripts" / "board.html").read_text(
        encoding="utf-8")

    assert "headline" in html, "the verdict is computed and the page does not show it"
