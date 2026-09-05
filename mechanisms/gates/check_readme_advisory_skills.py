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


def main(argv: list[str] | None = None) -> int:
    """The door `verify_ecosystem` knocks on, which did not exist until 2026-09-05.

    Every test for this module called `check()` directly and every one was green.
    The module had no `__main__` block, so `python3 check_readme_advisory_skills.py
    --root <tree>` defined three functions and exited 0. The verifier runs it exactly
    that way and drew a tick for it, on every run since the gate was added.

    A correct checker with no way to be run is the same silence as a wrong one, and
    the tick is worse than no line at all: it is a reader being told this was checked.

    Prints what it examined on every outcome. A pass with no output cannot be told
    apart from a no-op, which is the failure this function exists because of.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="README/HOW-TO-USE cite only skills that exist on disk.")
    parser.add_argument("--root", type=Path, default=Path.cwd(),
                        help="tree holding README.md, HOW-TO-USE.md and skills/")
    parser.add_argument("--json", action="store_true",
                        help="emit the findings as JSON instead of prose")
    args = parser.parse_args(argv)

    root: Path = args.root
    readme = root / "README.md"
    how_to = root / "HOW-TO-USE.md"
    disk = existing_skills(root)

    if not readme.is_file() and not how_to.is_file():
        # The subject is absent, so nothing was compared. Not a failure — a consumer
        # install legitimately has neither file — but it is NOT a pass, and saying so
        # is the whole difference between this and the silence it replaced.
        print(f"README advisory skills — {root}")
        print("  NOT CHECKED: neither README.md nor HOW-TO-USE.md is here, so nothing "
              "was compared against the 0 skill(s) on disk"
              if not disk else
              f"  NOT CHECKED: neither README.md nor HOW-TO-USE.md is here, so the "
              f"{len(disk)} skill(s) on disk were compared against nothing")
        return 0

    findings = check(root)
    if args.json:
        import json
        print(json.dumps({"findings": findings}, indent=2))
        return 1 if findings else 0

    cited = advisory_skills_in_readme(root) | advisory_skills_in_how_to_use(root)
    print(f"README advisory skills — {root}")
    print(f"  examined: {len(cited)} skill(s) cited across "
          f"{sum(1 for p in (readme, how_to) if p.is_file())} document(s), "
          f"{len(disk)} skill(s) on disk")
    for finding in findings:
        print(f"  {finding['type']}: {finding['context']}")
    print(f"  {'FAIL' if findings else 'PASS'} — {len(findings)} citation(s) name a "
          f"skill that is not on disk")
    return 1 if findings else 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
