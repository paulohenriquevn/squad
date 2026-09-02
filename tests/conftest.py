"""Shared fixtures for Cycle ecosystem tests."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# Ensure scripts/ is importable
REPO_ROOT = Path(__file__).resolve().parent.parent
MECHANISMS = REPO_ROOT / "mechanisms"
#: The import namespace stayed flat when `scripts/` became `mechanisms/<family>/`,
#: so every family goes on the path — a test importing `check_xrefs` must not have
#: to know which drawer it was filed in.
for _family in ("gates", "conventions", "cycle", "fleet", "dist"):
    _d = str(MECHANISMS / _family)
    if _d not in sys.path:
        sys.path.insert(0, _d)


@pytest.fixture()
def ecosystem_dir() -> Path:
    """Return the real Cycle ecosystem directory (repo root)."""
    from ecosystem_utils import find_ecosystem_dir

    return find_ecosystem_dir(start=REPO_ROOT)


@pytest.fixture(scope="session")
def versioned_kit(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The kit holding ONLY what git carries, with the working tree's content.

    It exists because installing from disk measures the machine running the test:
    `.gitignore` hides files present on one machine and on no other, and that is
    how a broken installation stayed green for months. The list comes from
    `git ls-files`; the content comes from disk, so the test keeps guiding the work
    instead of only seeing the last commit.
    """
    src = tmp_path_factory.mktemp("versioned-kit") / "kit"
    src.mkdir()
    listing = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    for rel in filter(None, listing.split("\0")):
        source = REPO_ROOT / rel
        if not source.is_file():  # tracked, but deleted in the working tree
            continue
        dest = src / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(source.read_bytes())
        dest.chmod(source.stat().st_mode & 0o777)
    return src
