"""A gate that examined nothing must not EXIT like a gate that examined everything.

`tests/test_gates_say_what_they_examined.py` holds every root-taking gate to saying so in
its OUTPUT, and that half has been green for weeks. The exit code was never held to the
same standard, and the exit code is the only part `verify_ecosystem` and CI read.

Measured on 2026-09-17, each against an empty directory:

    check_english_only      "english-only: clean"                     exit 0
    check_gate_mechanisms   "swept 0 cycle rule(s)"                   exit 0
    check_phase_numbering   "NOTHING_DECLARED ... This is not a pass"  exit 0
    check_semantic_names    empty report                              exit 0
    check_xrefs             overall PASS over zero skills, zero rules exit 0

Five gates whose prose says one thing and whose code says the other. The prose reaches a
human reading a terminal; the code reaches the chain.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_GATES = Path(__file__).resolve().parent.parent / "mechanisms" / "gates"

#: gate → the flag it takes for the tree it should look at.
UNCHECKED_ON_EMPTY = {
    "check_english_only": "--root",
    "check_gate_mechanisms": "--repo-root",
    "check_phase_numbering": "--root",
    "check_semantic_names": "--repo-root",
    "check_xrefs": "--ecosystem-dir",
}


@pytest.mark.parametrize("gate,flag", sorted(UNCHECKED_ON_EMPTY.items()))
def test_an_empty_tree_does_not_exit_like_a_clean_one(gate: str, flag: str,
                                                      tmp_path: Path) -> None:
    done = subprocess.run(
        [sys.executable, str(_GATES / f"{gate}.py"), flag, str(tmp_path)],
        capture_output=True, text=True, timeout=180, check=False)

    assert done.returncode != 0, (
        f"{gate} exited 0 over a tree it measured nothing in:\n"
        f"{(done.stdout + done.stderr)[:600]}")


@pytest.mark.parametrize("gate,flag", sorted(UNCHECKED_ON_EMPTY.items()))
def test_the_real_repository_still_passes(gate: str, flag: str) -> None:
    """The refusal must be about the EMPTY tree, not about the gate."""
    repo = Path(__file__).resolve().parent.parent
    done = subprocess.run(
        [sys.executable, str(_GATES / f"{gate}.py"), flag, str(repo)],
        capture_output=True, text=True, timeout=300, check=False)

    assert done.returncode == 0, (
        f"{gate} now fails on the repository it ships with:\n"
        f"{(done.stdout + done.stderr)[-1500:]}")


def test_a_git_repository_that_tracks_nothing_is_not_clean_english(tmp_path: Path) -> None:
    """`check_english_only` reached exit 0 by a second route the table above misses.

    `_versioned_files` answers None only when `git ls-files` exits non-zero. A repository
    that TRACKS nothing — a fresh `git init`, a sub-tree passed as `--root`, a worktree
    whose index is not populated — returns an EMPTY LIST, `scan_repository` builds an
    empty report, and the gate printed "english-only: clean". The count was never carried
    out of the scan, so nothing downstream could tell a clean sweep from a sweep of zero.
    """
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)

    done = subprocess.run(
        [sys.executable, str(_GATES / "check_english_only.py"), "--root", str(tmp_path)],
        capture_output=True, text=True, timeout=180, check=False)

    assert done.returncode == 2, (
        f"a repository tracking nothing exited {done.returncode}:\n{done.stdout}{done.stderr}")
    assert "UNCHECKED" in done.stdout + done.stderr


def test_the_clean_line_says_how_many_files_it_read() -> None:
    """A pass that does not say its population cannot be told from a no-op."""
    repo = Path(__file__).resolve().parent.parent
    done = subprocess.run(
        [sys.executable, str(_GATES / "check_english_only.py"), "--root", str(repo)],
        capture_output=True, text=True, timeout=300, check=False)

    assert done.returncode == 0, done.stdout + done.stderr
    assert "tracked file(s) examined" in done.stdout, done.stdout
