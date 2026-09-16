"""Two readers of "does this item have a record", each knowing one spelling.

`board_state._slug_for` matched `b022-descriptive-words-plan.md` and missed
`B-022-plan.md`. `select_backlog_item` took the filename prefix and matched
`B-022-plan.md` while missing the descriptive form. The mirror of one defect, in two
modules, found four hours apart.

Measured on a consumer 2026-09-16: the first reported `phases: []` for all 35 items
holding a plan and drew a list of empty blocks; the second reported an item whose plan
was on disk as `awaiting_plan`, which sends a reader to write a plan that exists.

Both now call `squad_boss.records_by_item`, and this asserts they AGREE — not that each
one works, which is what they each already believed.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from board_state import stage_on_disk  # noqa: E402

_SPELLINGS = ("B-022-plan.md", "b022-delete-the-unwired-package-plan.md")


def _registry(tmp_path: Path, filename: str) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "BACKLOG.md").write_text(
        "# Backlog\n\n## B-022 — an item\nstatus: approved\n", encoding="utf-8")
    plans = tmp_path / ".squad" / "records" / "plans"
    plans.mkdir(parents=True)
    (plans / filename).write_text("# a plan\n", encoding="utf-8")
    return tmp_path


def _selector(root: Path) -> dict:
    out = subprocess.run(
        [sys.executable, str(_SCRIPTS / "select_backlog_item.py"),
         str(root / "BACKLOG.md"), "--json"],
        capture_output=True, text=True, timeout=180).stdout
    return json.loads(out[out.index("{"):])


def test_the_selector_sees_both_spellings(tmp_path: Path) -> None:
    for i, spelling in enumerate(_SPELLINGS):
        root = _registry(tmp_path / f"r{i}", spelling)
        result = _selector(root)
        assert result["plan_written"] == ["B-022"], \
            f"{spelling} was not recognised as a plan on disk"
        assert result["awaiting_plan"] == [], \
            f"{spelling} exists and the item was sent to write one"


def test_the_board_sees_both_spellings(tmp_path: Path) -> None:
    for i, spelling in enumerate(_SPELLINGS):
        root = _registry(tmp_path / f"b{i}", spelling)
        assert stage_on_disk(root) == {"B-022": "plan"}, \
            f"{spelling} was not recognised by the board"


def test_the_two_readers_agree(tmp_path: Path) -> None:
    """The property that was false: each believed it worked, and they disagreed."""
    for i, spelling in enumerate(_SPELLINGS):
        root = _registry(tmp_path / f"a{i}", spelling)
        assert set(_selector(root)["plan_written"]) == set(stage_on_disk(root)), spelling
