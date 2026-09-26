"""The walls are the whole registry's, and the label said `blocked:` under one item.

`--check <ITEM>` printed the verdict, then `blocked:` and the global wall map. A reader
takes that as this item's blockers, and the reading is wrong whenever the checked item is
not in the map.

Measured 2026-09-16, and the reader was this kit's own maintainer: `--check B-022`
printed `blocked: B-088 <- a decision` under the verdict, B-022's actual `blocked_by` was
B-034, and the wrong chain was reported to a consumer session as fact. It survived
because the data was right — only the label was silent about whose it was.

`walls` is global on purpose: its docstring says "what else is waiting, and on what" is
the next question, and answering it should not need a second run. The fix is the label,
never the data.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SCRIPT = (Path(__file__).resolve().parents[1] / "scripts"
           / "select_backlog_item.py")

_BACKLOG = """# Backlog

## B-001 — declares no impediment
status: approved

## B-002 — waits on a decision
status: triaged
blocked_by: a decision nobody has taken

## B-003 — waits on an item
status: triaged
blocked_by: B-002
"""


def _check(tmp_path: Path, item: str) -> str:
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(_BACKLOG, encoding="utf-8")
    (tmp_path / ".git").mkdir(exist_ok=True)
    return subprocess.run(
        [sys.executable, str(_SCRIPT), str(backlog), "--check", item],
        capture_output=True, text=True, timeout=180, check=False).stdout


def test_an_unblocked_item_is_told_it_is_unblocked(tmp_path: Path) -> None:
    out = _check(tmp_path, "B-001")
    assert "this item is blocked by: nothing" in out, \
        "the global wall map was left to read as this item's blockers"


def test_a_blocked_item_gets_its_own_blocker_named(tmp_path: Path) -> None:
    out = _check(tmp_path, "B-003")
    assert "this item is blocked by: B-002" in out


def test_the_rest_of_the_registry_is_labelled_as_elsewhere(tmp_path: Path) -> None:
    """The data stays — it is the next question — and the label says whose it is."""
    out = _check(tmp_path, "B-001")
    assert "elsewhere in the registry" in out
    assert "B-002" in out.split("elsewhere in the registry")[1]


def test_an_item_is_not_repeated_under_elsewhere(tmp_path: Path) -> None:
    """Naming it twice would put the same fact in two places with two meanings."""
    out = _check(tmp_path, "B-003")
    tail = out.split("elsewhere in the registry")[1] if "elsewhere" in out else ""
    assert "B-003 <-" not in tail
