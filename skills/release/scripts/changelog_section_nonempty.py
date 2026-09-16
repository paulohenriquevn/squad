#!/usr/bin/env python3
"""Check that a CHANGELOG section has at least one entry (line starting with '- ').

Usage:
    python3 changelog_section_nonempty.py --section Unreleased [--changelog CHANGELOG.md]

Exit codes:
    0 — section has at least one bullet entry
    1 — section is present and empty, or absent (the message says which)
    2 — file not found / parse error
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def section_state(changelog: Path, section: str) -> str:
    """`has_entries`, `empty`, or `absent` — three states, because two of them need
    different actions from whoever reads the failure.

    This returned a bool and the caller printed "is empty or absent". One verdict
    carrying two states tells a reader to go look for a section that may not exist, or
    to fill one that does — and only one of those is the job in front of them. The same
    conflation cost a consumer a day elsewhere in this kit on 2026-09-16, where
    `approved` meant both "no plan was written" and "the plan exists and nothing
    advanced the status".
    """
    if not changelog.exists():
        print(f"changelog file not found: {changelog}", file=sys.stderr)
        sys.exit(2)

    text = changelog.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^##\s+\[{re.escape(section)}\][^\n]*\n(.*?)(?=^##\s+\[|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return "absent"

    body = match.group(1)
    for line in body.splitlines():
        if line.strip().startswith("- "):
            return "has_entries"
    return "empty"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check that a CHANGELOG section is non-empty.")
    parser.add_argument("--changelog", type=Path, default=Path("CHANGELOG.md"))
    parser.add_argument("--section", required=True, help="Section name (e.g. 'Unreleased' or '1.2.0').")
    args = parser.parse_args()

    state = section_state(args.changelog, args.section)
    if state == "has_entries":
        return 0
    if state == "absent":
        print(f"section [{args.section}] is ABSENT from {args.changelog} —"
              f" add the heading, then the entries", file=sys.stderr)
    else:
        print(f"section [{args.section}] is present and EMPTY in {args.changelog} —"
              f" it has no `- ` entry", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
