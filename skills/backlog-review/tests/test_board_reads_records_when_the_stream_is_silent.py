"""A record on disk beats a status nobody advanced.

`STATUS_PHASE` maps `approved` to `discover`, which is right until something writes a
plan — and nothing writes the status when that happens. `planned` is issued by the stage
that STARTS work, so between PLAN and IMPLEMENT the registry says nothing about a plan
that exists.

Measured honestly on a consumer 2026-09-16, and the measurement corrected the guess that
prompted this: 35 items carry a record, and the event stream already placed 34 of them
at `code-quality` — further along than the records could prove. The 82 items the board
drew in `discover` are exactly the ones with no plan and no implementation. **The board
was already right about every item in that registry.**

So this is a safety net, not a repair, and it fires on zero items there. It matters
because the stream is the one source that can go silent: a stage that runs without
emitting an event leaves an item drawn at a status the registry never advanced, and that
is the same blind spot that hid 34 finished plans from the scheduler in the same week.
`position_from` says `disk` rather than `derived`, so a reader can always tell a
position read off a file from one inferred from a status field.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from board_state import build_state, stage_on_disk


def _registry(tmp_path: Path, *records: tuple[str, str]) -> Path:
    (tmp_path / "BACKLOG.md").write_text(
        "# Backlog\n\n## B-001 — an item\nstatus: approved\n", encoding="utf-8")
    for base, name in records:
        directory = tmp_path / ".squad" / "records" / base
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_text("x\n", encoding="utf-8")
    return tmp_path


def test_a_plan_on_disk_places_the_item_at_plan(tmp_path: Path) -> None:
    state = build_state(_registry(tmp_path, ("plans", "B-001-plan.md")))
    item = state["items"][0]
    assert item["phase"] == "plan", \
        "an approved item holding a plan was drawn at the phase it had left"
    assert item["position_from"] == "disk"


def test_an_implementation_beats_a_plan(tmp_path: Path) -> None:
    state = build_state(_registry(tmp_path,
                                  ("plans", "B-001-plan.md"),
                                  ("implementations", "B-001-implementation.md")))
    assert state["items"][0]["phase"] == "implement"


def test_an_item_with_no_record_still_reads_its_status(tmp_path: Path) -> None:
    """The net must not move an item that genuinely has not started."""
    item = build_state(_registry(tmp_path))["items"][0]
    assert item["phase"] == "discover"
    assert item["position_from"] == "derived", \
        "a position inferred from status must not claim to come from a record"


def test_the_ladder_stops_where_filenames_stop_meaning_one_thing(tmp_path: Path) -> None:
    """`reviews/` holds `{ITEM}-{phase}-{date}.md`. Reading one as "REVIEW finished"
    assigns a meaning the filename does not carry, so the ladder does not try."""
    reached = stage_on_disk(_registry(
        tmp_path, ("reviews", "B-001-implement-validate-2026-09-15.md")))
    assert reached == {}
