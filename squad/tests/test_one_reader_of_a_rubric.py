"""`load_rubric` was byte-identical in three skills, differing only in a docstring.

One of those docstrings said so: "Copied as-is from plan-confidence/scripts/
_rubric_loader.py — same YAML-in-markdown convention." Three readings of one convention
is three places for it to drift, and the drift would be silent — a rubric whose fence
one copy stopped finding would raise in one skill and score in the other two.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from squad.rubric import load_rubric  # noqa: E402 — post-bootstrap import

_COPIES = sorted((_ROOT / "skills").glob("*/scripts/_rubric_loader.py"))


def test_no_skill_carries_its_own_implementation() -> None:
    assert _COPIES, "the re-export shims are gone; this test lost its subject"

    for copy in _COPIES:
        source = copy.read_text(encoding="utf-8")
        assert "from squad.rubric import load_rubric" in source, (
            f"{copy.relative_to(_ROOT)} does not delegate to the owner")
        assert "yaml.safe_load" not in source, (
            f"{copy.relative_to(_ROOT)} reads the YAML itself — that is the copy again")


def test_every_shim_reaches_the_same_function() -> None:
    import importlib.util

    for copy in _COPIES:
        spec = importlib.util.spec_from_file_location(f"shim_{copy.parts[-3]}", copy)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert module.load_rubric is load_rubric, copy


def test_a_rubric_block_is_parsed(tmp_path: Path) -> None:
    rubric = tmp_path / "rubric.md"
    rubric.write_text("# A rubric\n\n```yaml\ndimensions:\n  - name: coverage\n```\n",
                      encoding="utf-8")

    assert load_rubric(rubric) == {"dimensions": [{"name": "coverage"}]}


def test_an_absent_block_raises_naming_the_file(tmp_path: Path) -> None:
    """Not a silent `{}`: a rubric that did not parse is not a rubric with no criteria."""
    rubric = tmp_path / "rubric.md"
    rubric.write_text("# A rubric with no block\n", encoding="utf-8")

    with pytest.raises(ValueError, match="rubric.md"):
        load_rubric(rubric)


def test_an_unclosed_block_raises_naming_the_file(tmp_path: Path) -> None:
    rubric = tmp_path / "rubric.md"
    rubric.write_text("# A rubric\n\n```yaml\ndimensions: []\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unclosed"):
        load_rubric(rubric)
