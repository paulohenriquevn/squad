"""Four items sat in `review` and `implement` had never run. The page drew it as normal.

`rules/cycle-phases.txt` states the dependency in its own column:

    review | conditional | absent when implement never ran

On one consumer, 2026-09-18, the stream recorded four phases — code-quality 29, review 7,
brainstorm 1, discover 1 — and **no implement, plan, backlog, release or acceptance at
all**. Four items were positioned in `review`. There is 53 lines of TypeScript on disk,
so code was written; the cycle has no record that it was.

A board that draws that as an ordinary column is a board a CTO reads as "four items are
in review" when the true statement is "four items are in review and the phase that
produces what review reads left no trace". The second is a risk. The first is a status.

WHAT THIS DOES AND DOES NOT CLAIM

It reports what the STREAM shows, and says so. An item may genuinely skip a conditional
phase — `cycle-phases.txt` marks implement "absent for a killed item, and for an item
whose fix is documentation only" — and this cannot tell that from a phase that ran and
emitted nothing. Both are worth surfacing and neither is called a defect here: the
wording is that the stream has no record, which is true in both cases and actionable in
both.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from board_state import build_state  # after the bootstrap above

_ITEM = ("\n## {id} — Item   [ ]\n\ndomain: a\nrepo: r\nsuggested_mode: review\n"
         "source: human\nevidence: measured\nwhy_now: x\nstatus: {status}\n")


def _project(tmp_path: Path, items, events) -> Path:
    (tmp_path / "BACKLOG.md").write_text(
        "# BACKLOG\n\n## Items\n" + "".join(_ITEM.format(id=i, status=s) for i, s in items),
        encoding="utf-8")
    records = tmp_path / ".squad" / "records"
    records.mkdir(parents=True)
    (records / "cycle-events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return tmp_path


def _end(item: str, cycle: str) -> dict:
    return {"type": "cycle:phase:end", "cycle": cycle, "slug": item,
            "timestamp": "2026-09-18T19:00:00Z", "verdict": "PASS"}


def test_an_item_past_a_phase_with_no_record_is_flagged(tmp_path: Path) -> None:
    """The consumer's exact shape: reached review, implement never emitted."""
    state = build_state(_project(
        tmp_path, [("B-001", "planned")],
        [_end("B-001", "code-quality"), _end("B-001", "review")]))

    item = next(i for i in state["items"] if i["id"] == "B-001")
    assert "implement" in (item.get("phases_without_record") or []), (
        f"an item in review with no implement event was drawn as ordinary: "
        f"{item.get('phases_without_record')}")


def test_a_phase_with_a_record_is_not_flagged(tmp_path: Path) -> None:
    """No false alarm: a phase that emitted is a phase that ran."""
    state = build_state(_project(
        tmp_path, [("B-001", "planned")],
        [_end("B-001", "implement"), _end("B-001", "review")]))

    item = next(i for i in state["items"] if i["id"] == "B-001")
    assert "implement" not in (item.get("phases_without_record") or [])


def test_phases_ahead_of_the_item_are_not_flagged(tmp_path: Path) -> None:
    """A phase the item has not reached yet is not a gap. Flagging `release` on an item
    sitting in review would turn every card into a wall of false findings."""
    state = build_state(_project(
        tmp_path, [("B-001", "planned")],
        [_end("B-001", "review")]))

    gaps = next(i for i in state["items"] if i["id"] == "B-001").get("phases_without_record") or []
    assert "release" not in gaps and "acceptance" not in gaps, gaps


def test_an_item_that_never_moved_flags_nothing(tmp_path: Path) -> None:
    """An item still in backlog has skipped nothing."""
    state = build_state(_project(tmp_path, [("B-001", "raw")], []))

    item = next(i for i in state["items"] if i["id"] == "B-001")
    assert not item.get("phases_without_record")


def test_the_page_renders_the_gap(tmp_path: Path) -> None:
    html = (Path(__file__).resolve().parents[1] / "scripts" / "board.html").read_text(
        encoding="utf-8")

    assert "phases_without_record" in html, (
        "the gap is computed and never drawn — the reader still sees an ordinary card")
