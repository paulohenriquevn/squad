"""Two readers of one block, with different ideas of what it says.

`utils.parse_skill_md` matched `name:` and `description:` by line prefix and stripped
one layer of quotes with `.strip('"').strip("'")`. `quick_validate.py`, in the SAME
package, already parsed the same block with `yaml.safe_load`.

So a skill could validate under one reader and be misread by the other — and the
hand-written one did not unescape: a description written `"a \\"quoted\\" word"` came
back carrying the backslashes, and `'it''s'` came back with the doubled apostrophe.
Both are valid YAML. `run_loop` writes the result back into the SKILL.md, so a
misreading becomes the file.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "skills" / "skill-creator"))

from scripts.utils import (  # noqa: E402 — post-bootstrap import
    parse_frontmatter,
    parse_skill_md,
)


def _skill(tmp_path: Path, frontmatter: str) -> Path:
    (tmp_path / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n\n# Body\n",
                                       encoding="utf-8")
    return tmp_path


def test_an_escaped_quote_is_unescaped(tmp_path: Path) -> None:
    path = _skill(tmp_path, 'name: a-skill\ndescription: "a \\"quoted\\" word"')

    _, description, _ = parse_skill_md(path)

    assert description == 'a "quoted" word', description


def test_a_doubled_apostrophe_is_unescaped(tmp_path: Path) -> None:
    path = _skill(tmp_path, "name: a-skill\ndescription: 'it''s here'")

    _, description, _ = parse_skill_md(path)

    assert description == "it's here", description


def test_a_folded_block_still_reads(tmp_path: Path) -> None:
    """The one shape the hand-written reader handled; it must not regress."""
    path = _skill(tmp_path, "name: a-skill\ndescription: >\n  one line\n  and another")

    _, description, _ = parse_skill_md(path)

    assert description == "one line and another", description


def test_the_two_readers_agree(tmp_path: Path) -> None:
    """The point: `quick_validate` and `utils` must read one file the same way."""
    from scripts.quick_validate import validate_skill

    path = _skill(tmp_path, 'name: a-skill\ndescription: "a \\"quoted\\" word"')

    ok, message = validate_skill(path)
    name, description, _ = parse_skill_md(path)

    assert ok, message
    assert name == "a-skill"
    assert description == 'a "quoted" word'


def test_an_absent_opening_fence_names_what_is_missing(tmp_path: Path) -> None:
    (tmp_path / "SKILL.md").write_text("# No frontmatter\n", encoding="utf-8")

    with pytest.raises(ValueError, match="no opening"):
        parse_skill_md(tmp_path)


def test_an_unclosed_block_names_what_is_missing(tmp_path: Path) -> None:
    (tmp_path / "SKILL.md").write_text("---\nname: a-skill\n", encoding="utf-8")

    with pytest.raises(ValueError, match="no closing"):
        parse_skill_md(tmp_path)


def test_malformed_yaml_raises_rather_than_returning_an_empty_mapping() -> None:
    """A block that did not parse is not a block with no keys."""
    with pytest.raises(ValueError, match="not valid YAML"):
        parse_frontmatter("---\nname: [unclosed\n---\n")
