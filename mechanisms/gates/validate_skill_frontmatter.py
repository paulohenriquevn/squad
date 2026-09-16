#!/usr/bin/env python3
"""Validate SKILL.md frontmatter conformance across all skills.

Checks that every skills/*/SKILL.md has the required frontmatter fields,
that names are unique, and that names match their parent directory.

Usage:
    python3 mechanisms/gates/validate_skill_frontmatter.py          # validate all
    python3 mechanisms/gates/validate_skill_frontmatter.py --strict  # exit 1 on warnings too

Exit codes:
  0 — All skills valid
  1 — At least one validation error (or warning in --strict mode)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# The family this file lives in, plus `lib/` — the import namespace stayed flat
# when `scripts/` became `mechanisms/<family>/`, so a sibling family is reached
# by path rather than by package.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "conventions"))

from ecosystem_utils import find_ecosystem_dir

REQUIRED_FIELDS = {"name", "description", "user-invocable"}
OPTIONAL_FIELDS = {"version", "requires", "allowed-tools", "argument-hint", "paths"}

# Regex for YAML-like frontmatter between --- markers
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
FIELD_RE = re.compile(r"^([a-z][a-z0-9_-]*):\s*(.+)$", re.MULTILINE)


class UnparseableFrontmatter(ValueError):
    """The block exists and no YAML parser can read it."""


def parse_frontmatter(content: str) -> dict[str, str]:
    """Extract frontmatter fields from SKILL.md content.

    The regex extraction stays — it is what tolerates the fields this validator
    cares about — but the block is first handed to a real YAML parser, because
    the regex happily reads a block Claude Code cannot load.

    Found 2026-08-27: a `description:` containing an unquoted colon passed here
    ("39 skills, 0 errors") while `verify_ecosystem.py`, which uses `yaml.safe_load`
    on the same block, reported `mapping values are not allowed here`. Two
    validators over one artifact, disagreeing about whether it is readable at
    all — and the one named after the job was the blind one. A consumer running
    it and seeing green has a skill that will not load.
    """
    match = FRONTMATTER_RE.match(content)
    if not match:
        return {}

    block = match.group(1)
    try:
        import yaml
    except ImportError:  # pyyaml genuinely absent — report inability, not absence
        pass
    else:
        try:
            yaml.safe_load(block)
        except yaml.YAMLError as error:
            raise UnparseableFrontmatter(str(error).splitlines()[0]) from error

    return {m.group(1): m.group(2).strip() for m in FIELD_RE.finditer(block)}


def validate_all(ecosystem_dir: Path, strict: bool = False) -> int:
    """Validate all SKILL.md files. Returns exit code."""
    skills_dir = ecosystem_dir / "skills"
    if not skills_dir.is_dir():
        # Phrased so a reader — and the empty-sweep roster — can tell this apart
        # from a clean run. "not found" alone described the path, never the sweep.
        print(f"ERROR: no skills were validated — {skills_dir} is absent, so this"
              f" run examined nothing", file=sys.stderr)
        return 1

    errors: list[str] = []
    warnings: list[str] = []
    names_seen: dict[str, str] = {}  # name -> directory

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            warnings.append(f"WARN: {skill_dir.name}/ has no SKILL.md")
            continue

        content = skill_md.read_text(encoding="utf-8")
        try:
            fields = parse_frontmatter(content)
        except UnparseableFrontmatter as error:
            errors.append(
                f"ERROR: {skill_dir.name}/SKILL.md YAML frontmatter is invalid: {error}"
            )
            continue

        if not fields:
            errors.append(f"ERROR: {skill_dir.name}/SKILL.md has no frontmatter (missing --- markers)")
            continue

        # Check required fields
        for field in REQUIRED_FIELDS:
            if field not in fields:
                errors.append(f"ERROR: {skill_dir.name}/SKILL.md missing required field: {field}")

        # Check name matches directory
        if "name" in fields:
            name = fields["name"]
            if name != skill_dir.name:
                errors.append(
                    f"ERROR: {skill_dir.name}/SKILL.md name '{name}' "
                    f"does not match directory name '{skill_dir.name}'"
                )
            # Check uniqueness
            if name in names_seen:
                errors.append(
                    f"ERROR: duplicate name '{name}' in "
                    f"{skill_dir.name}/ and {names_seen[name]}/"
                )
            names_seen[name] = skill_dir.name

    # Print results
    for w in warnings:
        print(w)
    for e in errors:
        print(e, file=sys.stderr)

    total_skills = len(names_seen)
    print(f"\nValidated {total_skills} skills: {len(errors)} errors, {len(warnings)} warnings")

    if errors:
        return 1
    if strict and warnings:
        return 1
    if total_skills == 0:
        # `skills/` present and empty is not a clean ecosystem; it is a sweep that found
        # nothing. The line above already said "Validated 0 skills", and the exit code
        # said PASS anyway — so a consumer whose skills directory emptied, or whose glob
        # lost its reach, got a green gate with the evidence printed right above it.
        #
        # Measured 2026-09-16: `--ecosystem-dir <dir with an empty skills/>` exited 0.
        # The `skills/` MISSING case already returned 1 (line 79); present-and-empty
        # slipped between the two.
        print("ERROR: no skills were validated — `skills/` is present and empty, so"
              " this run examined nothing and cannot report that everything conforms.",
              file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ecosystem-dir", type=Path, default=None,
        help="the ecosystem to validate. Without it the root is resolved from the "
             "cwd — which is how `check_xrefs.py` used to audit whichever project "
             "the shell happened to sit in and print ITS verdict under another "
             "project's name.",
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    eco = args.ecosystem_dir or find_ecosystem_dir(require=True)
    return validate_all(eco, strict=args.strict)  # type: ignore[arg-type]


if __name__ == "__main__":
    sys.exit(main())
