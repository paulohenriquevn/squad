"""The skills `/review` generates must pass the gate the kit runs over skills.

`spawn_reviewers.py` writes a paired knowledge skill per reviewer at
`.claude/skills/review-{slug}-{role}-knowledge/SKILL.md`, and all five templates
begin with an `#` heading. There is no frontmatter in any of them.

Two consequences, and the second is the expensive one.

The kit's own `validate_skill_frontmatter.py` requires `name`, `description` and
`user-invocable` between `---` markers, and the installer runs it as post-install
validation. Measured on a consumer 2026-09-18: thirteen generated skills, thirteen
`has no frontmatter` errors, and `=== SOME CHECKS FAILED ===` on an install whose
files were all correct. The gate was right and the kit had produced what it
failed. Every `/review` run adds up to five more, permanently.

The larger one: Claude Code reads a skill's `name` and `description` FROM that
frontmatter. A SKILL.md without it is not discovered, so the "paired knowledge
skill" the template calls *auto-discovered by Claude Code* has never been loadable
by the mechanism it names. The reviewer agent runs; its knowledge layer does not.

Asserted against the gate's own constants rather than a copy of them, so a field
added there is a field this test starts demanding.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "mechanisms" / "gates"))

from validate_skill_frontmatter import (  # noqa: E402
    REQUIRED_FIELDS,
    parse_frontmatter,
)

_TEMPLATES = sorted((_REPO / "skills" / "review" / "templates").glob("skill-*.md"))


def test_the_templates_are_still_where_this_test_looks() -> None:
    """A test that silently examines nothing is the defect this kit hunts most."""
    assert len(_TEMPLATES) == 5, [p.name for p in _TEMPLATES]


@pytest.mark.parametrize("template", _TEMPLATES, ids=lambda p: p.name)
def test_a_generated_skill_carries_the_frontmatter_the_gate_requires(template: Path) -> None:
    content = template.read_text(encoding="utf-8")
    assert content.startswith("---\n"), (
        f"{template.name} has no frontmatter, so the kit's own gate fails the skill "
        f"the kit itself wrote — and Claude Code cannot discover it at all"
    )
    fields = parse_frontmatter(content)
    missing = sorted(REQUIRED_FIELDS - set(fields))
    assert not missing, f"{template.name} is missing {missing}"
    assert fields["description"].strip(), f"{template.name} has an empty description"


@pytest.mark.parametrize("template", _TEMPLATES, ids=lambda p: p.name)
def test_the_name_survives_slug_substitution(template: Path) -> None:
    """The directory is `review-{slug}-{role}-knowledge`; `name` must match it.

    A skill whose frontmatter `name` disagrees with its directory is discovered
    under one identity and referenced under the other — which reads as a missing
    skill, the failure mode with no error message.
    """
    fields = parse_frontmatter(template.read_text(encoding="utf-8"))
    name = fields["name"]
    assert "{SLUG}" in name or "{slug}" in name, (
        f"{template.name} hard-codes the name `{name}`, so every generated copy "
        f"claims the same identity and they collide across slices"
    )
    assert name.startswith("review-") and name.endswith("-knowledge"), name
