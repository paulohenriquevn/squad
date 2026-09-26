"""Shared utilities for skill-creator scripts."""

import re
from pathlib import Path
from typing import Any

import yaml

#: The frontmatter block: `---` on the first line, `---` on a line of its own after it.
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---(?:\n|\Z)", re.DOTALL)


def parse_frontmatter(content: str) -> dict[str, Any]:
    """The SKILL.md frontmatter, parsed as YAML — because it IS YAML.

    This was a hand-written reader that matched `name:` and `description:` by line
    prefix and stripped one layer of quotes with `.strip('"').strip("'")`. Two
    consequences, both silent:

      * Quoting was not unescaped. A description written `"a \\"quoted\\" word"` came
        back with the backslashes in it, and one written `'it''s'` came back with the
        doubled apostrophe — both valid YAML, both wrong once read.
      * `quick_validate.py`, in this same package, already used `yaml.safe_load` on the
        same block. So the kit held TWO readers of one file with different ideas of
        what it says, and a skill could validate under one and be misread by the other.

    Raises `ValueError` naming what is missing rather than returning `{}`: a file whose
    frontmatter did not parse is not a file with no frontmatter, and every caller here
    writes the result back into a SKILL.md.
    """
    match = _FRONTMATTER_RE.match(content)
    if match is None:
        opening = content.startswith("---")
        raise ValueError(
            "SKILL.md missing frontmatter (no closing ---)" if opening
            else "SKILL.md missing frontmatter (no opening ---)")
    try:
        parsed = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise ValueError(f"SKILL.md frontmatter is not valid YAML: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(
            f"SKILL.md frontmatter parsed as {type(parsed).__name__}, not a mapping")
    return parsed


def parse_skill_md(skill_path: Path) -> tuple[str, str, str]:
    """Parse a SKILL.md file, returning (name, description, full_content)."""
    content = (skill_path / "SKILL.md").read_text()
    frontmatter = parse_frontmatter(content)
    return (str(frontmatter.get("name", "") or ""),
            str(frontmatter.get("description", "") or ""),
            content)
