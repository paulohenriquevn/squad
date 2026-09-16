"""An approved item whose plan exists is not an item awaiting a plan.

`approved` carries two states the status alone cannot separate: the plan was never
written, and the plan exists but nothing advanced the status. SELECT claimed the first
for both, because the verdict was a static string keyed on status.

Measured on a consumer 2026-09-16: 35 plans written, 34 belonging to items still
`approved`. `--check B-022` answered "no plan exists yet; run /plan-write to produce it"
against a 79361-byte plan scoring 34/34 aligned. A reader following that instruction
re-plans two days of finished work, and a scheduler reading `awaiting_plan` dispatches
26 items back to the stage that already finished them.

The status is written by the stage that STARTS work, and PLAN is not that stage —
`stage-implement.md` issues `--to planned`. So between PLAN and IMPLEMENT the registry
is silent about every plan that exists. This is the fourth instance of that seam; the
module's own comments walk the first three.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_SCRIPT = (Path(__file__).resolve().parents[1] / "scripts"
           / "select_backlog_item.py")

_BACKLOG = """# Backlog

## B-001 — planned already, no plan file
status: approved

## B-002 — plan written, status never advanced
status: approved
"""


def _registry(tmp_path: Path, with_plan: bool) -> Path:
    (tmp_path / ".git").mkdir()
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(_BACKLOG, encoding="utf-8")
    plans = tmp_path / ".squad" / "records" / "plans"
    plans.mkdir(parents=True)
    if with_plan:
        (plans / "B-002-plan.md").write_text("# a real plan\n", encoding="utf-8")
    return backlog


def _run(backlog: Path, *args: str) -> dict:
    out = subprocess.run(
        [sys.executable, str(_SCRIPT), str(backlog), "--json", *args],
        capture_output=True, text=True, timeout=120,
    ).stdout
    return json.loads(out[out.index("{"):])


def test_an_item_whose_plan_exists_leaves_awaiting_plan(tmp_path: Path) -> None:
    result = _run(_registry(tmp_path, with_plan=True))
    assert result["awaiting_plan"] == ["B-001"], \
        "an item with a finished plan was still reported as awaiting one"
    assert result["plan_written"] == ["B-002"], \
        "the plan exists and no key a scheduler reads names the item"


def test_the_check_verdict_does_not_send_a_reader_to_replan(tmp_path: Path) -> None:
    backlog = _registry(tmp_path, with_plan=True)
    result = _run(backlog, "--check", "B-002")
    assert result["verdict"] == "ITEM_PLAN_WRITTEN"
    assert "no plan exists yet" not in result["reason"]
    assert "IMPLEMENT" in result["reason"], \
        "the verdict names no next step, which is why the old one was followed"


def test_an_item_with_no_plan_still_awaits_one(tmp_path: Path) -> None:
    """The fix must not swallow the state it was distinguishing from."""
    result = _run(_registry(tmp_path, with_plan=False), "--check", "B-002")
    assert result["verdict"] == "ITEM_AWAITING_PLAN"
    assert "/plan-write" in result["reason"]
