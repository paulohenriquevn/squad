"""The board knew which plan an item had and not that the plan had been worked.

`planned_items` learned to read the plan body, so B-003 is linked to
`composition-di`. `_phases_reached` and `_phases_running` still resolve a stream slug
through `item_id_of` alone — and `composition-di` carries no item number — so all
twenty-two events under it reach nobody.

The visible symptom is a column of cards that each say `last_at: None`. A board that
cannot date an item cannot say how long it has been sitting, which is the difference
between a queue moving and a queue stopped. On the consumer measured 2026-09-18 every
column read "sem evento" while the stream held 38.

The link already exists in one direction. This carries it the other way: an event under
a plan slug belongs to every item that plan realises.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from board_state import build_state  # after the bootstrap above

_BACKLOG = """# BACKLOG

## Items

## B-003 — First   [ ]

domain: a
repo: r
suggested_mode: review
source: human
evidence: measured
why_now: x
status: planned

## B-011 — Second   [ ]

domain: a
repo: r
suggested_mode: review
source: human
evidence: measured
why_now: x
status: planned

## B-020 — Untouched   [ ]

domain: a
repo: r
suggested_mode: review
source: human
evidence: measured
why_now: x
status: raw
"""

_EVENTS = [
    {"type": "cycle:phase:end", "cycle": "plan", "slug": "composition-di",
     "timestamp": "2026-09-18T18:00:00Z", "verdict": "SHIPPABLE"},
    {"type": "cycle:phase:end", "cycle": "implement", "slug": "composition-di",
     "timestamp": "2026-09-18T19:00:00Z", "verdict": "IMPLEMENTATION_COMPLETE"},
]


def _project(tmp_path: Path) -> Path:
    (tmp_path / "BACKLOG.md").write_text(_BACKLOG, encoding="utf-8")
    records = tmp_path / ".squad" / "records"
    (records / "plans").mkdir(parents=True)
    (records / "plans" / "composition-di-plan.md").write_text(
        "# Composition DI\n\nRealises B-003 and B-011.\n", encoding="utf-8")
    (records / "cycle-events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in _EVENTS), encoding="utf-8")
    return tmp_path


def _by_id(tmp_path: Path) -> dict:
    return {i["id"]: i for i in build_state(_project(tmp_path))["items"]}


def test_an_event_under_a_plan_slug_dates_every_item_the_plan_realises() -> None:
    """Both items the plan names, not just the first."""
    import tempfile
    items = _by_id(Path(tempfile.mkdtemp()))

    for iid in ("B-003", "B-011"):
        assert items[iid].get("last_at") == "2026-09-18T19:00:00Z", (
            f"{iid} has a plan with two events and the board cannot date it: "
            f"{items[iid].get('last_at')!r}")


def test_the_verdict_travels_with_the_date(tmp_path: Path) -> None:
    """A date with no verdict says something happened and not what."""
    items = _by_id(tmp_path)

    assert items["B-003"].get("last_verdict") == "IMPLEMENTATION_COMPLETE"


def test_an_item_with_no_plan_stays_undated(tmp_path: Path) -> None:
    """The half that must not go quiet. Dating an untouched item would make an idle
    registry look busy, which is the failure the whole review was about."""
    items = _by_id(tmp_path)

    assert not items["B-020"].get("last_at"), (
        "an item nothing has happened to was given a date")
