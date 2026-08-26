"""Tests for scripts/ecosystem_utils.py — layout detection and directory resolution."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure scripts/ is importable
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from ecosystem_utils import (  # noqa: E402
    find_ecosystem_dir,
    is_ecosystem_layout,
    resolve_ecosystem_dir,
)

# ---------------------------------------------------------------------------
# is_ecosystem_layout
# ---------------------------------------------------------------------------


def test_is_ecosystem_layout_true(tmp_path: Path) -> None:
    """Directory with skills/ + rules/ + hooks/ is a valid ecosystem layout."""
    (tmp_path / "skills").mkdir()
    (tmp_path / "rules").mkdir()
    (tmp_path / "hooks").mkdir()

    assert is_ecosystem_layout(tmp_path) is True


def test_is_ecosystem_layout_false(tmp_path: Path) -> None:
    """Empty directory is not a valid ecosystem layout."""
    assert is_ecosystem_layout(tmp_path) is False


def test_is_ecosystem_layout_partial(tmp_path: Path) -> None:
    """Directory with only skills/ + rules/ (missing hooks/) is not valid."""
    (tmp_path / "skills").mkdir()
    (tmp_path / "rules").mkdir()

    assert is_ecosystem_layout(tmp_path) is False


# ---------------------------------------------------------------------------
# find_ecosystem_dir
# ---------------------------------------------------------------------------


def test_find_ecosystem_dir_standalone(tmp_path: Path) -> None:
    """Standalone layout: skills/ + rules/ + hooks/ at the search root."""
    (tmp_path / "skills").mkdir()
    (tmp_path / "rules").mkdir()
    (tmp_path / "hooks").mkdir()

    result = find_ecosystem_dir(start=tmp_path)

    assert result == tmp_path


def test_find_ecosystem_dir_claude_sub(tmp_path: Path) -> None:
    """User-config layout: ecosystem lives under .claude/."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "skills").mkdir()
    (claude_dir / "rules").mkdir()
    (claude_dir / "hooks").mkdir()

    result = find_ecosystem_dir(start=tmp_path)

    assert result == claude_dir


def test_find_ecosystem_dir_plugin(tmp_path: Path) -> None:
    """Plugin layout: ecosystem lives under .claude/plugins/cycle/."""
    plugin_dir = tmp_path / ".claude" / "plugins" / "cycle"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "skills").mkdir()
    (plugin_dir / "rules").mkdir()
    (plugin_dir / "hooks").mkdir()

    result = find_ecosystem_dir(start=tmp_path)

    assert result == plugin_dir


def test_find_ecosystem_dir_not_found_require(tmp_path: Path) -> None:
    """require=True (default) raises FileNotFoundError when no layout found."""
    with pytest.raises(FileNotFoundError):
        find_ecosystem_dir(start=tmp_path)


def test_find_ecosystem_dir_not_found_optional(tmp_path: Path) -> None:
    """require=False returns None when no layout found."""
    result = find_ecosystem_dir(start=tmp_path, require=False)

    assert result is None


# ---------------------------------------------------------------------------
# resolve_ecosystem_dir
# ---------------------------------------------------------------------------


def test_resolve_ecosystem_dir_with_knowledge_base(tmp_path: Path) -> None:
    """Prefers candidate that has knowledge-base/ even over standalone layout."""
    # Standalone layout at root (no knowledge-base)
    (tmp_path / "skills").mkdir()
    (tmp_path / "rules").mkdir()
    (tmp_path / "hooks").mkdir()

    # .claude/ layout WITH knowledge-base
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "skills").mkdir()
    (claude_dir / "rules").mkdir()
    (claude_dir / "hooks").mkdir()
    (claude_dir / "knowledge-base").mkdir()

    result = resolve_ecosystem_dir(tmp_path)

    assert result == claude_dir


def test_resolve_ecosystem_dir_fallback(tmp_path: Path) -> None:
    """Falls back to skills/rules/hooks layout when no knowledge-base/ exists."""
    (tmp_path / "skills").mkdir()
    (tmp_path / "rules").mkdir()
    (tmp_path / "hooks").mkdir()

    result = resolve_ecosystem_dir(tmp_path)

    assert result == tmp_path


def test_resolve_ecosystem_dir_none(tmp_path: Path) -> None:
    """Returns None when no candidate matches."""
    result = resolve_ecosystem_dir(tmp_path)

    assert result is None
