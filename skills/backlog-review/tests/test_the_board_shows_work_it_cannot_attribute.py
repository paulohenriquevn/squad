"""Thirty-seven of thirty-eight events were dropped, and the page said nothing.

`item_id_of` resolves a stream slug to `B-NNN` by reading the FILENAME convention
`bNNN-some-name`. A plan named `composition-di-plan.md` carries no item number, so the
slug resolves to `COMPOSITION-DI`, matches no item, and every event under it is
discarded by `_phases_running` and `_phases_reached`.

Measured on one consumer, 2026-09-18:

    38 events in the stream
     1 slug that resolves to an item
    37 invisible — 22 `composition-di`, 14 `ci-coverage`, 1 `channel-loop-assembly`

The owner opened the board while a `review` phase was ending with
`READY_TO_MERGE_WITH_FOLLOWUPS`, and the page showed no work at all. Their words:
*"o board não está exibindo nenhum trabalho."*  english-only: quoting the report verbatim, in the language it was written

`item_id_of`'s own docstring records the smaller version of this from an earlier run —
*"12 events, 6 of them plan slugs, and every one of those six invisible on the board —
half the execution, missing from the view built to show it."* The fix then taught it one
more filename shape. This is the same defect arriving through a shape nobody predicted,
which is the argument against fixing it with a third pattern.

TWO CHANGES, AND THE SECOND IS THE ONE THAT HOLDS

**The link exists in the plan's body.** `composition-di-plan.md` names B-003, B-004 and
B-006. Reading it costs one file per plan and removes the guesswork entirely.

**Work that still cannot be attributed is SHOWN, never dropped.** A board that silently
discards what it cannot place is a board that reports an idle system while the system is
working — the exact failure this kit exists to prevent, rendered in HTML. An
unattributable event is a fact about the STREAM, and the page must say so.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from board_state import build_state  # after the bootstrap above

_BACKLOG = """# BACKLOG

## Items

## B-003 — First item   [ ]

domain: alpha
repo: r
suggested_mode: review
source: human
evidence: measured
why_now: it matters
status: planned

## B-011 — Second item   [ ]

domain: alpha
repo: r
suggested_mode: review
source: human
evidence: measured
why_now: it matters too
status: planned
"""


def _project(tmp_path: Path, *, plan_body: str = "", events: list[dict] | None = None) -> Path:
    (tmp_path / "BACKLOG.md").write_text(_BACKLOG, encoding="utf-8")
    records = tmp_path / ".squad" / "records"
    (records / "plans").mkdir(parents=True)
    (records / "plans" / "composition-di-plan.md").write_text(
        plan_body or "# A plan that names no item\n", encoding="utf-8")
    stream = records / "cycle-events.jsonl"
    stream.write_text(
        "".join(json.dumps(e) + "\n" for e in (events or [])), encoding="utf-8")
    return tmp_path


_WORKING = [
    {"type": "cycle:phase:start", "cycle": "implement", "slug": "composition-di",
     "timestamp": "2026-09-18T19:00:00Z"},
    {"type": "cycle:phase:end", "cycle": "review", "slug": "composition-di",
     "timestamp": "2026-09-18T19:36:00Z", "verdict": "READY_TO_MERGE_WITH_FOLLOWUPS"},
]


def test_a_plan_naming_its_items_in_the_body_is_attributed(tmp_path: Path) -> None:
    """The link is in the file. Reading it is cheaper than guessing from the name."""
    project = _project(
        tmp_path,
        plan_body="# Composition DI\n\nRealises B-003 and B-011.\n",
        events=_WORKING)

    state = build_state(project)
    by_id = {i["id"]: i for i in state["items"]}

    assert by_id["B-003"].get("plan_slug") == "composition-di", (
        f"the plan names B-003 in its body and the board did not link it: "
        f"{by_id['B-003'].get('plan_slug')!r}")


def test_unattributable_work_is_reported_not_dropped(tmp_path: Path) -> None:
    """The half that matters most. A board that drops what it cannot place reports an
    idle system while the system is working."""
    project = _project(tmp_path, events=_WORKING)

    state = build_state(project)

    assert state.get("unattributed"), (
        "events under a slug matching no item vanished; the page has no way to say "
        "that work is happening")


def test_the_unattributed_entry_names_the_slug_and_the_count(tmp_path: Path) -> None:
    """A count with no name is not actionable: the reader's next move is to find out
    WHICH work is invisible."""
    project = _project(tmp_path, events=_WORKING)

    entries = build_state(project)["unattributed"]
    slugs = {e["slug"] for e in entries}

    assert "composition-di" in slugs, f"the slug is not named: {entries}"
    entry = next(e for e in entries if e["slug"] == "composition-di")
    assert entry["events"] == 2, f"the count is wrong: {entry}"
    assert entry.get("last_verdict") == "READY_TO_MERGE_WITH_FOLLOWUPS", (
        f"the most recent verdict is not carried: {entry}")


def test_an_attributed_stream_leaves_the_list_empty(tmp_path: Path) -> None:
    """No false alarm. When every slug resolves, there is nothing unattributed and the
    page must not imply otherwise."""
    project = _project(
        tmp_path,
        plan_body="# Composition DI\n\nRealises B-003 and B-011.\n",
        events=_WORKING)

    assert build_state(project)["unattributed"] == []
