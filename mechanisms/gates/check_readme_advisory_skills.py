#!/usr/bin/env python3
"""Gate: Verify README/HOW-TO-USE advisory skills table matches disk.

WHY THIS EXISTS
===============
e5527e6 deleted three advisory specialists (cap-theorem, backpressure, resilience)
because "a fixed specialist asserts domain knowledge about repositories it has
never read" — the deletion was documented and deliberate. However, the README.md
table was never updated to reflect the removal. This gate catches that drift in ONE
direction: a document cites a skill that does not exist on disk (broken promise).

The reverse — "skills exist on disk but aren't mentioned in README" — was claimed here
and implemented nowhere, in both this module and its test file. It is not a scoping
oversight: the README table enumerates the ADVISORY skills and never claimed to
enumerate the other thirty. Unscoped, the missing direction would report three quarters
of the kit as documentation rot. The claim is deleted rather than implemented, and
`main` now prints what each document contributed so a half that compares nothing is
visible instead of silent.

WHAT IT ASSERTS
===============
After a `Skill.md` is created or deleted, the README.md "Advisory skills" table
and HOW-TO-USE.md "Commands" table must stay in sync with the actual directory
structure under skills/.

EXIT CODES
==========
0 — every citation names a skill that exists on disk.
1 — a document cites a skill that is not on disk.
2 — NOT CHECKED: neither document is present, so nothing was compared. This used to
    be 0, and the exit code is the only part `verify_ecosystem` reads — so the
    paragraph saying "it is NOT a pass" reached a human and never reached the chain.
"""
import re
from pathlib import Path
from typing import Any

#: Neither document is here, so nothing was compared. Distinct from 0 on purpose:
#: the exit code is the only part `verify_ecosystem` reads.
NOT_CHECKED = 2

#: Regex to extract skill names from backtick-quoted names in markdown table cells.
#: Example: "| `cap-theorem-specialist` | Consistency vs availability | "
#: Captures: "cap-theorem-specialist"
#: A skill name starts with a letter or digit. The character class allowed `-` in
#: first position, so a flag written in backticks — `--yes`, `--strict` — read as a
#: skill name and the gate reported a missing `--yes/SKILL.md`. Prose about a skill's
#: flags is the most natural thing to write in a section about skills, so the class
#: had to stop matching it rather than the prose being rewritten around the check.
_SKILL_NAME_RE = re.compile(r"`([a-z0-9][a-z0-9-]*(?:-specialist)?)`", re.IGNORECASE)


README_HEADINGS = ("## Advisory skills",)
HOW_TO_USE_HEADINGS = ("## Advisory skills", "## Skills", "## Commands")


def _section_start(text: str, headings: tuple[str, ...]) -> int | None:
    for heading in headings:
        at = text.find(heading)
        if at != -1:
            return at
    return None


def _names_in_section(doc: Path, headings: tuple[str, ...]) -> set[str]:
    """The skill names a document's section carries. Empty when there is no section."""
    if not doc.is_file():
        return set()
    text = doc.read_text(encoding="utf-8")
    start = _section_start(text, headings)
    if start is None:
        return set()
    # Up to the next H2, or the end of the document.
    end = text.find("\n## ", start + 1)
    return set(_SKILL_NAME_RE.findall(text[start:end if end != -1 else len(text)]))


def section_present(doc: Path, headings: tuple[str, ...]) -> bool:
    """Whether the document carries a section this gate knows how to read.

    The question `_names_in_section` cannot answer: a document with no section and a
    section naming nothing both return an empty set, so a half of this gate that had
    stopped comparing anything looked exactly like a half that found nothing wrong.
    HOW-TO-USE.md has been in the first state since it was restructured.
    """
    if not doc.is_file():
        return False
    return _section_start(doc.read_text(encoding="utf-8"), headings) is not None


def advisory_skills_in_readme(root: Path) -> set[str]:
    """The skills README.md's "Advisory skills" table names."""
    return _names_in_section(root / "README.md", README_HEADINGS)


def advisory_skills_in_how_to_use(root: Path) -> set[str]:
    """The skills HOW-TO-USE.md's skills/commands table names."""
    return _names_in_section(root / "HOW-TO-USE.md", HOW_TO_USE_HEADINGS)


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
        return NOT_CHECKED

    findings = check(root)
    if args.json:
        import json
        print(json.dumps({"findings": findings}, indent=2))
        return 1 if findings else 0

    cited = advisory_skills_in_readme(root) | advisory_skills_in_how_to_use(root)
    print(f"README advisory skills — {root}")
    # Per DOCUMENT, not summed. A sum cannot show a half that stopped comparing: the
    # HOW-TO-USE side has contributed 0 names since the document was restructured, and
    # the combined count read exactly like a document with nothing wrong in it.
    for label, doc, headings in (("README.md", readme, README_HEADINGS),
                                 ("HOW-TO-USE.md", how_to, HOW_TO_USE_HEADINGS)):
        if not doc.is_file():
            print(f"  {label}: absent")
        elif not section_present(doc, headings):
            print(f"  {label}: present, but carries no skills section this gate reads "
                  f"({' / '.join(headings)}) — 0 name(s) compared")
        else:
            print(f"  {label}: {len(_names_in_section(doc, headings))} name(s) compared")
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
