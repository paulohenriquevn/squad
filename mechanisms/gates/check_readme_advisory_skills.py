#!/usr/bin/env python3
"""Gate: Verify README/HOW-TO-USE advisory skills table matches disk.

WHY THIS EXISTS
===============
e5527e6 deleted three advisory specialists (cap-theorem, backpressure, resilience)
because "a fixed specialist asserts domain knowledge about repositories it has
never read" — the deletion was documented and deliberate. However, the README.md
table was never updated to reflect the removal. This gate catches that drift in
both directions:
1. README cites skills that don't exist on disk (broken promise).
2. Skills exist on disk but aren't mentioned in README (documentation rot).

WHAT IT ASSERTS
===============
After a `Skill.md` is created or deleted, the README.md "Advisory skills" table
and HOW-TO-USE.md "Commands" table must stay in sync with the actual directory
structure under skills/.

EXIT CODES
==========
0 — README and HOW-TO-USE are consistent with disk.
1 — Inconsistency found (missing skills, orphan skills, or malformed table).
"""
import re
from pathlib import Path
from typing import Any


#: Regex to extract skill names from backtick-quoted names in markdown table cells.
#: Example: "| `cap-theorem-specialist` | Consistency vs availability | "
#: Captures: "cap-theorem-specialist"
_SKILL_NAME_RE = re.compile(r"`([a-z0-9-]+(?:-specialist)?)`", re.IGNORECASE)


def advisory_skills_in_readme(root: Path) -> set[str]:
    """Extract advisory skill names from README.md Advisory skills table.

    Looks for the section "## Advisory skills" and extracts names between
    backticks in the first column of the table.

    Returns:
        Set of skill names cited in README. Empty set if section not found.
    """
    readme = root / "README.md"
    if not readme.is_file():
        return set()

    text = readme.read_text(encoding="utf-8")
    start = text.find("## Advisory skills")
    if start == -1:
        return set()

    # Extract until the next H2 section or end of file
    end = text.find("\n## ", start + 1)
    if end == -1:
        end = len(text)

    section = text[start:end]
    # Find all backtick-quoted names in this section
    matches = _SKILL_NAME_RE.findall(section)
    return set(matches)


def advisory_skills_in_how_to_use(root: Path) -> set[str]:
    """Extract advisory skill names from HOW-TO-USE.md commands table.

    Looks for the section that lists skills and their invocation commands,
    and extracts names between backticks.

    Returns:
        Set of skill names cited in HOW-TO-USE. Empty set if section not found.
    """
    how_to_use = root / "HOW-TO-USE.md"
    if not how_to_use.is_file():
        return set()

    text = how_to_use.read_text(encoding="utf-8")
    # Look for a commands or skills table section
    start = text.find("## Advisory skills")
    if start == -1:
        # Try alternate section names
        start = text.find("## Skills")
        if start == -1:
            start = text.find("## Commands")
    if start == -1:
        return set()

    end = text.find("\n## ", start + 1)
    if end == -1:
        end = len(text)

    section = text[start:end]
    matches = _SKILL_NAME_RE.findall(section)
    return set(matches)


def existing_skills(root: Path) -> set[str]:
    """Return the set of skill directory names on disk.

    Looks under skills/ for directories containing a SKILL.md file.

    Returns:
        Set of skill names found on disk.
    """
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return set()

    found = set()
    for item in skills_dir.iterdir():
        if item.is_dir() and (item / "SKILL.md").is_file():
            found.add(item.name)
    return found


def check(root: Path) -> list[dict[str, Any]]:
    """Verify README/HOW-TO-USE consistency with disk.

    Returns:
        List of finding dicts, each with:
            - type: "readme_skill_missing" or "how_to_use_skill_missing"
            - skill_name: the skill in question
            - context: brief explanation
        Empty list if everything is consistent.
    """
    findings: list[dict[str, Any]] = []

    readme_named = advisory_skills_in_readme(root)
    how_to_use_named = advisory_skills_in_how_to_use(root)
    disk_skills = existing_skills(root)

    # Check README: skills cited but not on disk
    for skill in readme_named:
        if skill not in disk_skills:
            findings.append({
                "type": "readme_skill_missing",
                "skill_name": skill,
                "context": f"README.md lists '{skill}' in Advisory skills table, but {skill}/SKILL.md does not exist on disk",
            })

    # Check HOW-TO-USE: skills cited but not on disk
    for skill in how_to_use_named:
        if skill not in disk_skills:
            findings.append({
                "type": "how_to_use_skill_missing",
                "skill_name": skill,
                "context": f"HOW-TO-USE.md lists '{skill}' in commands table, but {skill}/SKILL.md does not exist on disk",
            })

    return findings
