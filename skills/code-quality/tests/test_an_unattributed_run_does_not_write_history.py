"""A measurement must not mutate the registry it is measuring.

An event with no slug names no item: it cannot be placed on a board, cannot be
attributed to a cycle, and cannot be acted on. Writing one adds a row every reader has
to skip.

Measured on a consumer 2026-09-16: 369 events in the stream and 121 of them — ONE THIRD
— were `code-quality` phase:end with an empty slug, accumulated since 09-12. Every
ad-hoc run of the gate had left one, including the runs made while diagnosing the
registry that morning. The board counts them under `unplaced.without_item`, which is the
honest place for them and still a number nobody can reduce by working.

The run now says on stderr that it was not recorded, and why. Silence would be the other
half of the same defect: a reader who expects a row and finds none needs to know whether
the gate ran.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

_RUN = Path(__file__).resolve().parents[1] / "scripts" / "run_code_quality.py"


def _stream(root: Path) -> Path:
    return root / ".squad" / "records" / "cycle-events.jsonl"


def _project(tmp_path: Path) -> Path:
    """A tree the gate runs all the way THROUGH, not one it exits early from.

    The first draft of this fixture had no languages config, so the gate died on
    `cannot load languages config` before reaching the emitter — and the two
    "no event was written" assertions passed for that reason instead of for the fix.
    A test that passes because the code never ran is the defect this file is about,
    one layer up.
    """
    (tmp_path / ".squad" / "records").mkdir(parents=True)
    _stream(tmp_path).write_text("", encoding="utf-8")
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    # One enabled language with a manifest that exists, so the run reaches the end.
    (tmp_path / "pyproject.toml").write_text("[project]\nname = \"x\"\n",
                                             encoding="utf-8")
    (rules / "code-quality-languages.txt").write_text(
        "python | pyproject.toml | ENABLED\n", encoding="utf-8")
    # A slug binds to a plan on disk (Mode 2), so the attributed case needs one or the
    # gate exits with `plan_not_found` — which would make THAT test pass for the wrong
    # reason in the other direction.
    plans = tmp_path / ".squad" / "records" / "plans"
    plans.mkdir(parents=True)
    (plans / "B-001-plan.md").write_text(
        "# A plan\n\n## Tasks\n\n### T1.1 — a task\n\n#### TDD\nRED: test_x\n",
        encoding="utf-8")
    return tmp_path


def _reached_the_end(result: subprocess.CompletedProcess) -> bool:
    """The gate printed a verdict rather than dying on configuration."""
    for fatal in ("cannot load languages config", "plan_not_found"):
        if fatal in result.stderr:
            return False
    return True


def _run(root: Path, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_RUN), "--repo-root", str(root), "--no-audit-write", *flags],
        capture_output=True, text=True, timeout=900, cwd=str(root))


def test_a_run_naming_no_item_writes_no_event(tmp_path: Path) -> None:
    root = _project(tmp_path)
    assert _reached_the_end(_run(root)), "the gate exited before the emitter"
    rows = [line for line in _stream(root).read_text(encoding="utf-8").splitlines()
            if line.strip()]
    assert rows == [], f"an unattributable row was appended: {rows}"


def test_it_says_it_was_not_recorded(tmp_path: Path) -> None:
    """Silence is the other half of the same defect: a reader who expects a row and
    finds none needs to know whether the gate ran at all."""
    result = _run(_project(tmp_path))
    assert _reached_the_end(result), result.stderr
    assert "not recorded" in result.stderr
    assert "--slug" in result.stderr, "the message names no way to make the run belong"


def test_a_run_that_names_an_item_still_records(tmp_path: Path) -> None:
    """The fix must not silence the case the stream exists for."""
    root = _project(tmp_path)
    assert _reached_the_end(_run(root, "B-001")), "the gate exited before the emitter"
    rows = [json.loads(line) for line
            in _stream(root).read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows, "a run naming an item left no trace"
    assert rows[-1].get("slug") == "B-001"


def test_the_emitter_is_still_called_through_one_path() -> None:
    """Two call sites for one emission is how the slug check gets bypassed later."""
    source = _RUN.read_text(encoding="utf-8")
    assert len(re.findall(r"^\s+_emit_phase_end\(", source, re.M)) == 1
