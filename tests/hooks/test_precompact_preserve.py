"""What survives a compaction has to be what the hook says survived it.

Two defects, both in the closing lines this hook prints — the ones a session
reads AFTER its context was cut, when it can no longer check them against
anything it remembers.

It announced *"plan + progress are on disk under .compaction-snapshots/"*. Only
the plan was copied there. The progress log stayed in `session-state/`, so a
session following the sentence literally looked for it in a directory that never
held it.

And it derived the progress file's name by slicing the plan's filename by hand,
while holding the `ActivePlan` that already carries the slug. That is the exact
duplication `squad/plan.py` was created to end: *"they had three copies of the
same resolution"*.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path as _P

sys.path.insert(0, str(_P(__file__).resolve().parents[2]))
import sys
from pathlib import Path

from squad.paths import (
    SESSION_STATE,
    SNAPSHOTS,
    active_plan_pointer,
    write_records_dir,
    write_state_dir,
)

REPO = Path(__file__).resolve().parents[2]


def _eco(tmp_path: Path, *, with_progress: bool = True) -> Path:
    for tree in ("skills", "rules", "hooks"):
        (tmp_path / tree).mkdir(parents=True, exist_ok=True)
    plans = write_records_dir(tmp_path, "plans")
    plans.mkdir(parents=True)
    (plans / "b-014-plan.md").write_text(
        "# Plan\n\n## Goal\n\n> Make the gate fire once.\n", encoding="utf-8")
    pointer = active_plan_pointer(tmp_path)
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text("b-014\n", encoding="utf-8")
    if with_progress:
        state = write_state_dir(tmp_path, SESSION_STATE)
        state.mkdir(parents=True)
        (state / "b-014-progress.md").write_text(
            "\n".join(f"- step {n}" for n in range(12)), encoding="utf-8")
    return tmp_path


def _run(eco: Path) -> str:
    import os
    done = subprocess.run(  # noqa: PLW1510 — output is the assertion
        [sys.executable, str(REPO / "hooks" / "precompact-preserve.py")],
        input=json.dumps({"hook_event_name": "PreCompact", "trigger": "auto"}),
        capture_output=True, text=True, cwd=eco,
        env={"PATH": os.environ["PATH"], "HOME": str(eco),
             "CLAUDE_PROJECT_DIR": str(eco)})
    assert done.returncode == 0, done.stderr
    return done.stdout + done.stderr


def test_the_progress_log_is_found_through_the_plan_slug(tmp_path: Path) -> None:
    out = _run(_eco(tmp_path))
    assert "step 11" in out, "the progress tail was not surfaced"


def test_every_file_the_closing_lines_name_is_where_they_say_it_is(
        tmp_path: Path) -> None:
    """The sentence is read after the context is gone. It has to be checkable."""
    eco = _eco(tmp_path)
    out = _run(eco)

    named = [Path(word.rstrip(".,")) for line in out.splitlines()
             for word in line.split()
             if word.startswith(str(eco)) and "/" in word]
    assert named, "the hook named no path at all"
    missing = [p for p in named if not p.exists()]
    assert not missing, f"the hook points the session at paths that do not exist: {missing}"


def test_the_snapshot_holds_what_the_closing_line_says_it_holds(
        tmp_path: Path) -> None:
    """*"plan + progress are on disk under .compaction-snapshots/"* — both of them.

    Only the plan was ever copied there. The progress log stayed where it always
    was, so the one instruction a post-compaction session has to work from sent
    it to a directory that had half of what the sentence promised. And the
    progress log is the half that changes: it is the record of THIS session,
    which is what a snapshot before compaction is for.
    """
    eco = _eco(tmp_path)
    _run(eco)

    snapshots = write_state_dir(eco, SNAPSHOTS)
    kinds = {p.name.split("-")[0] for p in snapshots.iterdir()}
    assert "plan" in kinds
    assert "progress" in kinds, (
        f"the closing line names plan AND progress under {snapshots}; it holds "
        f"{sorted(p.name for p in snapshots.iterdir())}")


def test_with_no_progress_log_the_sentence_does_not_promise_one(
        tmp_path: Path) -> None:
    eco = _eco(tmp_path, with_progress=False)
    out = _run(eco)

    snapshots = write_state_dir(eco, SNAPSHOTS)
    assert not any(p.name.startswith("progress") for p in snapshots.iterdir())
    assert "progress are on disk" not in out, \
        "the hook promised a progress snapshot it had no progress log to make"


def test_a_failed_snapshot_is_not_reported_as_a_snapshot(tmp_path: Path) -> None:
    """A promise that silently failed is worse than none — the hook says so
    itself, and the closing lines must not contradict the failure above them."""
    eco = _eco(tmp_path)
    blocker = write_state_dir(eco, SNAPSHOTS)
    blocker.parent.mkdir(parents=True, exist_ok=True)
    blocker.write_text("not a directory\n", encoding="utf-8")

    out = _run(eco)
    assert "Could NOT snapshot" in out
    assert "snapshotted:" not in out
