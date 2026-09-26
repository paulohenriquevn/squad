"""The board reported 1 in flight and nothing was being worked.

A `brainstorm` phase opened on 2026-09-17 at 21:14 and never emitted an end. Twenty-two
hours later `_wip` still counted it as work in flight, and the owner asking *which item
is being worked* got no item back — because the slug was `theoclaw`, a scope, and no card
carries it.

Two readings of the same fact, and the page picked one with nothing to support it:

    a phase genuinely running for 22 hours
    a phase that died without emitting its end

`_phases_running` already knows this. Its docstring records the earlier instance —
*"B-001 opened `plan` on 09-12 and never closed it… Four days later the board still
reported `running plan`, and the owner read the column as where the work was"* — and it
learned to close an orphan start when a later phase ends. `_wip` did not inherit the
lesson: it counted raw starts, so every abandoned phase inflated the figure permanently.

WHAT THIS SEPARATES

    in flight    a start with no end, inside the window where work still emits
    abandoned    a start with no end, past it — the phase died without saying so

Both are facts about the stream. Only the first is work, and calling the second WIP
makes the number grow monotonically as lanes die — the opposite of what it measures.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from board_state import build_state  # after the bootstrap above

_BACKLOG = ("# BACKLOG\n\n## Items\n\n## B-001 — Item   [ ]\n\ndomain: a\nrepo: r\n"
            "suggested_mode: review\nsource: human\nevidence: measured\nwhy_now: x\n"
            "status: planned\n")


def _at(hours: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat().replace(
        "+00:00", "Z")


def _wip(tmp_path: Path, events: list[dict]) -> dict:
    (tmp_path / "BACKLOG.md").write_text(_BACKLOG, encoding="utf-8")
    records = tmp_path / ".squad" / "records"
    records.mkdir(parents=True)
    (records / "cycle-events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return build_state(tmp_path)["wip"]


def test_a_start_that_never_closed_is_abandoned_not_in_flight(tmp_path: Path) -> None:
    """The consumer's exact shape: opened 22 hours ago, no end, nothing since."""
    wip = _wip(tmp_path, [
        {"type": "cycle:phase:start", "cycle": "brainstorm", "slug": "theoclaw",
         "timestamp": _at(22)}])

    assert wip["current"] == 0, (
        f"a phase abandoned 22 hours ago was counted as work in flight: {wip}")
    assert wip["abandoned"] == 1, wip


def test_a_recent_start_is_still_in_flight(tmp_path: Path) -> None:
    """The half that must not go quiet: work that started minutes ago IS in flight, and
    a fix that swallowed it would leave the board unable to show anything running."""
    wip = _wip(tmp_path, [
        {"type": "cycle:phase:start", "cycle": "implement", "slug": "B-001",
         "timestamp": _at(0.2)}])

    assert wip["current"] == 1, wip
    assert wip["abandoned"] == 0, wip


def test_the_abandoned_phase_is_named(tmp_path: Path) -> None:
    """A count is not actionable. The reader's next move is to go and close it, which
    needs the slug and the phase."""
    wip = _wip(tmp_path, [
        {"type": "cycle:phase:start", "cycle": "brainstorm", "slug": "theoclaw",
         "timestamp": _at(22)}])

    stale = wip["abandoned_detail"]
    assert stale and stale[0]["slug"] == "theoclaw", stale
    assert stale[0]["cycle"] == "brainstorm"
    assert stale[0]["hours"] >= 21


def test_peak_does_not_count_abandoned_phases(tmp_path: Path) -> None:
    """Peak is the most that ever overlapped. A lane that died and was never closed
    would otherwise raise the ceiling forever."""
    wip = _wip(tmp_path, [
        {"type": "cycle:phase:start", "cycle": "brainstorm", "slug": "theoclaw",
         "timestamp": _at(30)},
        {"type": "cycle:phase:start", "cycle": "implement", "slug": "B-001",
         "timestamp": _at(0.2)}])

    assert wip["peak"] == 1, (
        f"an abandoned phase inflated the peak: {wip}")
