"""The catch-up rebuilds a session's picture of the world from git. A silent failure
there is a confident wrong answer at exactly the moment nobody can check it.

`run()` returned bare stdout and answered `""` for a timeout, a missing binary and a
non-zero exit alike — its own docstring said "swallow errors". Every caller read the
empty string as a fact: `git status --short` that could not run printed "working tree
clean", and an unreadable `git log` printed no recent commits at all.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_FLEET = Path(__file__).resolve().parents[1] / "mechanisms" / "fleet"
sys.path.insert(0, str(_FLEET))

from session_catchup import Ran, out_or_note, run  # noqa: E402 — post-bootstrap import


def test_a_command_that_is_not_installed_is_not_an_empty_answer(tmp_path: Path) -> None:
    ran = run(["a-binary-that-is-not-here"], tmp_path)

    assert ran.ok is False
    assert ran.out == ""
    assert "not installed" in ran.why


def test_a_command_that_failed_is_not_an_empty_answer(tmp_path: Path) -> None:
    ran = run(["git", "status", "--short"], tmp_path)  # not a repository

    assert ran.ok is False
    assert "exited" in ran.why


def test_a_command_that_worked_carries_its_output(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)

    ran = run(["git", "status", "--short"], tmp_path)

    assert ran.ok is True
    assert ran.why == ""


def test_the_reader_is_told_why_there_is_no_output(capsys) -> None:
    assert out_or_note(Ran(False, "", "`git log` timed out after 10s"), "recent commits") == ""
    assert "could not be read" in capsys.readouterr().out


def test_a_clean_tree_is_not_claimed_when_git_could_not_be_asked(tmp_path: Path) -> None:
    """The headline case, through the entry point."""
    done = subprocess.run(
        [sys.executable, str(_FLEET / "session_catchup.py"), str(tmp_path)],
        capture_output=True, text=True, timeout=120, check=False)
    out = done.stdout + done.stderr

    assert "working tree clean" not in out, (
        f"a directory that is not a repository was reported as a clean tree:\n{out[:800]}")
    assert "could not be read" in out


def test_the_catchup_reads_the_paths_the_hook_writes(tmp_path: Path) -> None:
    """Both lookups targeted directories the kit stopped writing to.

    `precompact-preserve.py` writes snapshots to `write_state_dir(project, SNAPSHOTS)`
    and the progress log to `write_state_dir(project, SESSION_STATE)`. This read
    `<eco>/.compaction-snapshots/` — a name `squad/paths.py` lists under
    LEGACY_STATE_NAMES — and `write_records_dir(<eco>, "progress")`. Different root,
    different leaf, different anchor: every snapshot written since the move was
    invisible, and the catch-up reported there were none.
    """
    from squad.paths import SESSION_STATE, SNAPSHOTS, write_state_dir

    snaps = write_state_dir(tmp_path, SNAPSHOTS)
    snaps.mkdir(parents=True)
    (snaps / "2026-09-17-session.md").write_text("snapshot", encoding="utf-8")

    done = subprocess.run(
        [sys.executable, str(_FLEET / "session_catchup.py"), str(tmp_path)],
        capture_output=True, text=True, timeout=120, check=False)

    assert "found 1 snapshot" in done.stdout, (
        f"a snapshot at the path the hook writes was not found:\n{done.stdout[-900:]}")
    assert str(SESSION_STATE)  # the leaf the progress file uses, imported above
