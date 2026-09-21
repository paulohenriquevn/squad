"""B-182 — the next id must come from every id ever spent, not from the file's own contents.

`BACKLOG.md` is unversioned by policy, so a checkout can hold a registry that lost blocks another
checkout still has. Observed 2026-09-18 in a consumer: a second session registered `B-016`, an id
that registry had already spent.

## Why the RED comes from a fixture and not from a live registry

Measured 2026-09-21 on the consumer where the defect was reported: `max(blocks) + 1` and
`max(spent) + 1` were BOTH B-232, because B-231 was the highest of both sets. A test asserting on a
live registry would pass for the wrong reason and keep passing after a regression. The fixture is a
registry truncated below its real maximum — the shape the observed collision actually had.

## Why git is the discriminator

An id that was ever spent HAD a block; a placeholder, a fixture or a documented example never did.
Run over the 138 unreachable ids on that consumer, `git log -S "## B-NNN " -- BACKLOG.md` split them
exactly 135 spent / 3 examples, and the 3 were precisely the template placeholder, the test fixture
and the prose example. A path heuristic would have missed the third.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from next_backlog_id import Allocation, next_backlog_id  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _registry(ids: list[int]) -> str:
    return "\n\n".join(f"## B-{n:03d} — item {n}\n\nstatus: shipped" for n in ids) + "\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A registry whose history holds blocks the working copy has lost."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    _git(tmp_path, "config", "user.name", "t")
    registry = tmp_path / "BACKLOG.md"
    registry.write_text(_registry(list(range(1, 232))), encoding="utf-8")
    _git(tmp_path, "add", "BACKLOG.md")
    _git(tmp_path, "commit", "-q", "-m", "every block")
    # The state the defect was observed in: the top blocks are gone from the working copy.
    registry.write_text(_registry(list(range(1, 39))), encoding="utf-8")
    return tmp_path


def test_a_truncated_registry_does_not_hand_out_a_spent_id(repo: Path) -> None:
    """The case a live registry cannot produce, and the whole reason this exists."""
    result = next_backlog_id(repo / "BACKLOG.md")
    assert result.next_id == "B-232", (
        "the working copy stops at B-038, so reading the file alone says B-039 — an id already "
        f"spent. Got {result.next_id} with {result.recovered} recovered from history."
    )
    assert result.present == 38
    assert result.recovered > 0, "history held blocks the working copy lost; none were recovered"


def test_an_id_that_never_had_a_block_is_rejected(repo: Path) -> None:
    """A placeholder, a fixture or a documented example must not inflate the allocation."""
    # Under a real search root — a loose file at the repository root is not where citations live,
    # and a fixture that cites from nowhere tests the fixture rather than the code.
    (repo / "docs").mkdir()
    (repo / "docs" / "lineage.md").write_text(
        "see B-999 for the shape of a lineage pointer\n", encoding="utf-8"
    )
    result = next_backlog_id(repo / "BACKLOG.md")
    assert "B-999" in result.rejected, (
        "an id cited only in prose must be REPORTED as rejected, so somebody adding a fourth "
        f"example sees it named. Got rejected={result.rejected}"
    )
    assert result.next_id == "B-232", f"B-999 inflated the allocation to {result.next_id}"


def test_without_history_it_falls_back_and_says_so(tmp_path: Path) -> None:
    """A fresh checkout must still allocate, and must not report the fallback as a recovery."""
    (tmp_path / "BACKLOG.md").write_text(_registry([1, 2, 3]), encoding="utf-8")
    result = next_backlog_id(tmp_path / "BACKLOG.md")
    assert result.next_id == "B-004"
    assert result.history_available is False
    assert result.recovered == 0, "no history means nothing was recovered, not that nothing existed"


def test_the_allocation_reports_the_three_counts(repo: Path) -> None:
    """The id it prints is auditable rather than asserted."""
    result = next_backlog_id(repo / "BACKLOG.md")
    assert isinstance(result, Allocation)
    assert result.present + result.recovered > 0
    assert isinstance(result.rejected, list)
