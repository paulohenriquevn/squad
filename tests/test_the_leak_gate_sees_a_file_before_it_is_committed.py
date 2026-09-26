"""The origin-name gate reads what a commit WOULD carry, not only what one already did.

`_versioned_files()` enumerated `git ls-files` — tracked paths only — so a file
that does not exist in the index yet was invisible to it. Somebody writing a new
test in this kit got a pass at exactly the moment they made the mistake, and the
finding arrived one commit later, on a branch two sessions share.

Measured 2026-09-19: a peer session wrote a new test carrying ten occurrences of a
consumer's app and scope names, ran this gate, and it passed. The file was `??`.

The cost objection is real and it is answered by `--exclude-standard` rather than
by leaving the window open. Measured in this repository at the same moment:

    git ls-files --others --exclude-standard      1 file — the one about to land
    git ls-files --others                     2277 files — scratch, caches, venvs

`.gitignore` already draws the line this gate needs, so honouring it costs one
path and nothing else. Scanning everything untracked would have been the expensive
answer, and it was never the only one.

WHY NOT JUST THE STAGED SET. `--cached` would see the file one step later, at
`git add`, which is still after the author has stopped looking at it. The useful
moment is while the file is open, and the useful question is "would a commit from
this tree carry the name" — which is tracked plus untracked-not-ignored.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "tests"))

from test_no_origin_ecosystem_leak import committable_files  # noqa: E402


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(tmp_path), *args],
                       capture_output=True, text=True, check=True)

    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (tmp_path / ".gitignore").write_text("scratch/\n*.log\n", encoding="utf-8")
    (tmp_path / "committed.md").write_text("# committed\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "init")
    return tmp_path


def _names(repo: Path) -> set[str]:
    return {p.relative_to(repo).as_posix() for p in committable_files(repo)}


def test_a_tracked_file_is_still_read(repo: Path) -> None:
    """The behaviour that already worked, pinned before widening it."""
    assert "committed.md" in _names(repo)


def test_a_file_not_yet_added_is_read(repo: Path) -> None:
    """The window: the author is still looking at it, and the gate was not."""
    (repo / "brand-new.md").write_text("# new\n", encoding="utf-8")
    assert "brand-new.md" in _names(repo), (
        "a file a commit from this tree would carry was invisible to the gate")


def test_an_ignored_file_is_not_read(repo: Path) -> None:
    """The cost objection, answered by `.gitignore` rather than by a new list.

    A second list of what to skip would be a second place for the convention to
    live, and the repository already declares it in the one place every tool reads.
    """
    (repo / "scratch").mkdir()
    (repo / "scratch" / "notes.md").write_text("# scratch\n", encoding="utf-8")
    (repo / "debug.log").write_text("noise\n", encoding="utf-8")
    found = _names(repo)
    assert "scratch/notes.md" not in found, found
    assert "debug.log" not in found, found


def test_a_deleted_file_is_not_read(repo: Path) -> None:
    """Tracked and gone from disk. Reading it would be reading nothing."""
    (repo / "committed.md").unlink()
    assert "committed.md" not in _names(repo)


def test_the_real_repository_is_read_without_arguments() -> None:
    """The default still answers for this kit, which is how the gate calls it."""
    found = committable_files()
    assert len(found) > 500, len(found)
    assert any(p.name == "CHANGELOG.md" for p in found)
