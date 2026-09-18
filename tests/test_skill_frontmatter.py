"""Tests that validate frontmatter in ALL SKILL.md files across the ecosystem."""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Ensure scripts/ is importable
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "mechanisms" / "gates"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from ecosystem_utils import find_ecosystem_dir  # noqa: E402 — post-bootstrap import

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


def test_every_skill_directory_carries_exactly_one_manifest() -> None:
    """The invariant, instead of a count nobody can keep true.

    This asserted `len(files) == 39` under a docstring that opened "we expect exactly
    27 SKILL.md files" and then ran an arithmetic log of every addition and retirement
    — `30 -> 28 -> 29 -> 30 -> 31 -> 32 ... 34 -> 27` — terminating at 27 and never
    reaching 39. One function, two answers, and a failure message that told the next
    reader to bump the number rather than look at what changed.

    A hardcoded total measures nothing about the skills: adding one and deleting one
    keeps it green. What is worth pinning is that every skill directory has exactly one
    manifest and none is orphaned, which stays true at any count.
    """
    eco = find_ecosystem_dir(start=_REPO_ROOT)
    manifests = _get_skill_files()
    directories = sorted(d for d in (eco / "skills").iterdir()
                         if d.is_dir() and not d.name.startswith((".", "_")))

    without = [d.name for d in directories if not (d / "SKILL.md").is_file()]
    assert without == [], f"skill directories with no SKILL.md: {without}"
    assert len(manifests) == len(directories), (
        f"{len(manifests)} manifests over {len(directories)} directories")
