"""`NOTHING_TO_ADVANCE` reads as "the registry agrees with its records".

`advance_items` closes one hop: `planned -> shipped`, from a RELEASED event. The
registry can also be behind in the MIDDLE — an item whose IMPLEMENT record exists while
its status is still `approved`, because `planned` is written by the stage that STARTS
work and a lane that halted walked it back without walking it forward.

Measured on a consumer 2026-09-16: this printed `NOTHING_TO_ADVANCE` while SELECT
reported one item under `approved_implemented` and twenty-five under `plan_written`.
Twenty-six divergences, and the only mechanism that reconciles anything said there was
nothing to do.

A mechanism that examined one direction must not report on all of them.

REPORTED, never advanced. Inferring "work started" from an artefact is a guess, and the
hop it would write is the one saying a lane owns the item. `backlog_status.py --to
planned` is the writer, and the lane that knows why is the one that should run it.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "mechanisms" / "cycle" / "advance_items.py"


def _registry(tmp_path: Path, *, with_plan: bool) -> Path:
    (tmp_path / "BACKLOG.md").write_text(
        "# Backlog\n\n## B-001 — an item\nstatus: approved\n", encoding="utf-8")
    records = tmp_path / ".squad" / "records"
    (records / "plans").mkdir(parents=True)
    (records / "cycle-events.jsonl").write_text("", encoding="utf-8")
    if with_plan:
        (records / "plans" / "B-001-plan.md").write_text("# a plan\n", encoding="utf-8")
    return tmp_path


def _run(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(_SCRIPT), str(root)],
                          capture_output=True, text=True, timeout=600, check=False)


def test_it_names_the_divergence_it_cannot_close(tmp_path: Path) -> None:
    out = _run(_registry(tmp_path, with_plan=True)).stdout
    assert "NOTHING_TO_ADVANCE" in out
    assert "NOT EXAMINED HERE" in out, \
        "'nothing to advance' was left to read as 'the registry agrees'"
    assert "B-001" in out
    flat = " ".join(out.replace("`", "").split())
    assert "backlog_status.py <ITEM> --to planned" in flat, \
        "the report names no writer for the hop it refuses to make"


def test_a_registry_that_truly_agrees_says_only_that(tmp_path: Path) -> None:
    """The report must not fire where there is nothing behind — an empty section on
    every clean run is how a reader learns to skip it."""
    out = _run(_registry(tmp_path, with_plan=False)).stdout
    assert "NOTHING_TO_ADVANCE" in out
    assert "NOT EXAMINED HERE" not in out


def test_the_report_never_writes(tmp_path: Path) -> None:
    """Advancing on inference is the thing being avoided: the artefact says work exists,
    not that a lane owns it."""
    root = _registry(tmp_path, with_plan=True)
    before = (root / "BACKLOG.md").read_text(encoding="utf-8")
    _run(root)
    assert (root / "BACKLOG.md").read_text(encoding="utf-8") == before


def test_a_broken_selector_does_not_fail_the_verdict(tmp_path: Path) -> None:
    """A report beside a verdict must never turn a clean run into a failed one."""
    root = _registry(tmp_path, with_plan=True)
    (root / "BACKLOG.md").write_text("not a backlog at all\n", encoding="utf-8")
    result = _run(root)
    assert result.returncode == 0, result.stderr
