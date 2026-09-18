"""The orchestrator's entire public surface was reachable only from its tests.

`schedule`, `take_batch`, `complete`, `fail`, `park`, `unpark`, `block`, `send_back`,
`force_stage`, `drain_writes`, `from_selection` and `apply_writes` were called from
exactly two places in the tree, both test files. `skills/pipeline/SKILL.md` names
`from_selection()` in prose and gives no command that reaches it, and `StatusWrite`'s
docstring says its writes are "to be applied by mechanisms/cycle/backlog_status.py" —
by a runner that does not exist.

So the registry write-back, the scheduler and the stage machinery were a library
nothing outside the suite could call: a module that passes its tests and runs nowhere.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "mechanisms" / "fleet" / "pipeline_orchestrator.py"

_REGISTRY = """# Backlog

## B-001

- status: approved
- title: the first thing
- domain: core

## B-002

- status: approved
- title: the second thing
- domain: core
"""


def _run(tmp_path: Path, *extra: str) -> tuple[int, dict]:
    selection = tmp_path / "selection.json"
    selection.write_text(json.dumps({"queue": ["B-001", "B-002"], "walls": {}}),
                         encoding="utf-8")
    (tmp_path / "BACKLOG.md").write_text(_REGISTRY, encoding="utf-8")

    done = subprocess.run(
        [sys.executable, str(_SCRIPT), "--selection", str(selection),
         "--backlog", str(tmp_path / "BACKLOG.md"), "--json", *extra],
        cwd=tmp_path, capture_output=True, text=True, timeout=180, check=False)
    payload = json.loads(done.stdout[done.stdout.index("{"):]) if "{" in done.stdout else {}
    return done.returncode, payload


def test_a_selection_becomes_a_schedule(tmp_path: Path) -> None:
    code, out = _run(tmp_path)

    assert code == 0, out
    assert out["scheduled"], "the queue produced no schedule"


def test_the_batch_at_a_stage_is_reportable(tmp_path: Path) -> None:
    _, out = _run(tmp_path, "--stage", "plan")

    assert out["stage"] == "plan"
    assert "batch" in out


def test_the_pending_writes_can_be_drained(tmp_path: Path) -> None:
    """`--apply` is the runner `StatusWrite`'s docstring promised and nothing was."""
    code, out = _run(tmp_path, "--apply")

    assert out["applied"] is True
    assert code in (0, 1), out
    assert isinstance(out["refusals"], list), "refusals are returned, never raised"


def test_an_unreadable_selection_is_an_exit_two(tmp_path: Path) -> None:
    (tmp_path / "BACKLOG.md").write_text(_REGISTRY, encoding="utf-8")
    bad = tmp_path / "selection.json"
    bad.write_text("{not json", encoding="utf-8")

    done = subprocess.run(
        [sys.executable, str(_SCRIPT), "--selection", str(bad)],
        cwd=tmp_path, capture_output=True, text=True, timeout=180, check=False)

    assert done.returncode == 2, done.stdout + done.stderr
    assert "could not read" in done.stderr
