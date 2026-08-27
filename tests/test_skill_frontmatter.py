"""Tests that validate frontmatter in ALL SKILL.md files across the ecosystem."""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Ensure scripts/ is importable
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from ecosystem_utils import find_ecosystem_dir  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _get_skill_files() -> list[Path]:
    """Collect all skills/*/SKILL.md files from the ecosystem."""
    eco = find_ecosystem_dir(start=_REPO_ROOT)
    files = sorted((eco / "skills").glob("*/SKILL.md"))
    assert len(files) > 0, "No SKILL.md files found — ecosystem detection may be broken"
    return files


def _parse_frontmatter(path: Path) -> dict[str, str]:
    """Extract YAML-like frontmatter key-value pairs from a SKILL.md file."""
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    result: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result


# Cache skill data once per session to avoid repeated I/O.
_SKILL_DATA: list[tuple[Path, dict[str, str]]] | None = None


def _skill_data() -> list[tuple[Path, dict[str, str]]]:
    global _SKILL_DATA
    if _SKILL_DATA is None:
        _SKILL_DATA = [(p, _parse_frontmatter(p)) for p in _get_skill_files()]
    return _SKILL_DATA


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_all_skills_have_name() -> None:
    """Every SKILL.md must have a name: field in its frontmatter."""
    missing = [str(p) for p, fm in _skill_data() if "name" not in fm]
    assert not missing, "SKILL.md files missing 'name:' frontmatter:\n" + "\n".join(missing)


def test_all_skills_have_description() -> None:
    """Every SKILL.md must have a description: field in its frontmatter."""
    missing = [str(p) for p, fm in _skill_data() if "description" not in fm]
    assert not missing, "SKILL.md files missing 'description:' frontmatter:\n" + "\n".join(missing)


def test_all_skills_have_user_invocable() -> None:
    """Every SKILL.md must have a user-invocable: field in its frontmatter."""
    missing = [str(p) for p, fm in _skill_data() if "user-invocable" not in fm]
    assert not missing, (
        "SKILL.md files missing 'user-invocable:' frontmatter:\n" + "\n".join(missing)
    )


def test_skill_names_unique() -> None:
    """No two SKILL.md files should share the same name: value."""
    seen: dict[str, Path] = {}
    duplicates: list[str] = []
    for path, fm in _skill_data():
        name = fm.get("name", "")
        if not name:
            continue
        if name in seen:
            duplicates.append(f"  '{name}' in {seen[name]} and {path}")
        else:
            seen[name] = path
    assert not duplicates, "Duplicate skill names found:\n" + "\n".join(duplicates)


def test_skill_names_match_directory() -> None:
    """The name: value must match the parent directory name of the SKILL.md."""
    mismatches: list[str] = []
    for path, fm in _skill_data():
        name = fm.get("name", "")
        dir_name = path.parent.name
        if name and name != dir_name:
            mismatches.append(f"  {path}: name='{name}' but dir='{dir_name}'")
    assert not mismatches, "Skill name vs directory mismatches:\n" + "\n".join(mismatches)


def test_skill_count() -> None:
    """Sanity check: we expect exactly 39 SKILL.md files.

    Retired the in-cycle skill-distillation tail (skill-writer + skill-validator
    + skill-register, -3), adopted the standalone official skill-creator (+1),
    added the frontend-design utility skill (+1), the cycle-goal session-binding
    skill (+1), the acceptance cycle skill (+1), and the roadmap-review skill (+1):
    30 -> 28 -> 29 -> 30 -> 31 -> 32.

    Squad: added the BACKLOG intake cycle — backlog-item (phase 0) and
    backlog-init (one-time registry bootstrap): 32 -> 34. Retired the three
    roadmap-* skills (init/feature/review, -3) and added backlog-review (+1):
    34 -> 32. Added the cap-theorem-specialist, backpressure-specialist and
    resilience-specialist auxiliary skills (+3): 32 -> 35. Added arch-check,
    the boundary proposer/verifier that pairs with the D5 detector (+1): 35 -> 36.
    Added the SOP family — sop-author (the static script), sop-run (the judgement
    that ran it) and sop-review (whether either is still true) (+3): 36 -> 39.
    """
    files = _get_skill_files()
    assert len(files) == 39, (
        f"Expected 39 SKILL.md files, found {len(files)}. "
        f"Update this test if skills were added or removed."
    )
