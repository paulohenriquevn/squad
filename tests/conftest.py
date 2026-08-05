"""Shared fixtures for Cycle ecosystem tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure scripts/ is importable
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture()
def ecosystem_dir() -> Path:
    """Return the real Cycle ecosystem directory (repo root)."""
    from ecosystem_utils import find_ecosystem_dir

    return find_ecosystem_dir(start=REPO_ROOT)
