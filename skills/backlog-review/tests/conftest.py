"""Shared pytest fixtures for backlog-review tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from backlog_fixtures import (  # noqa: E402 — post-bootstrap import
    item_block,
    write_backlog,
)


@pytest.fixture
def clean_backlog(tmp_path: Path) -> Path:
    """A registry with nothing wrong — the baseline negative tests break in one way."""
    return write_backlog(
        tmp_path,
        item_block("B-001"),
        item_block(
            "B-002",
            "Corrigir exit code do deploy parcial",
            domain="platform-cli",
            repo="cli-tool",
            suggested_mode="bug",
            status="triaged",
            evidence="src/deploy.ts:88",
            dod=["`theo deploy` returns exit != 0 when a step fails"],
        ),
    )
