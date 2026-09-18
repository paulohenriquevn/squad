#!/usr/bin/env python3
"""Prose that instructs a write names `.squad/`, like the code that performs it.

    python3 mechanisms/gates/check_prose_write_paths.py [--root .] [--json]

## The hole this closes

`check_write_containment.py` proves that no module outside `squad/paths.py` can spell a
data root, so every path a WRITER builds came from the owner. It strips prose before
matching, deliberately and correctly: the kit argues in prose about the very
directories it forbids in code.

A `SKILL.md` is not that kind of prose. It is an instruction an agent executes, and an
agent following `Persist to records/brainstorms/{date}-session.md` creates a legacy
root as surely as a `Path.write_text` would — while never consulting the owner, because
a human recipe has no import statement.

Measured 2026-09-10, when a live session hit it: **164 legacy-root instructions across
49 files**, 19 of them `SKILL.md`. `rules/records-location.md` had said the opposite
since 2026-09-09 — *"`<project>/.squad/` is the one write root. Always, in every
layout."* Two contracts disagreed and the one an agent reads at execution time won.

## Exemption

Prose that genuinely discusses a legacy root marks itself, the way
`rules/english-only.md` exempts a Portuguese quotation:

    <!-- write-path: readers fall back to this root -->

An exemption with no reason after the colon does not count. A silent opt-out is the
thing being prevented, so one that says nothing is refused exactly like the path it
was trying to keep.

## What it deliberately does not do

It does not read `rules/` or `docs/`. Those argue; they do not instruct. Widening the
scan there would flag `records-location.md` for stating the very rule this enforces —
the shape `check_english_only.py` avoids by scoping to what is executed rather than
what is discussed.

Exit codes:
  0  no executable prose instructs a legacy root
  1  at least one does
  2  the tree could not be read; nothing was checked, and that is not a pass
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from squad.paths import LEGACY_RECORDS_ROOTS, LEGACY_WIKI_ROOTS

CLEAN, INSTRUCTED, UNCHECKED = 0, 1, 2

#: Prose an agent EXECUTES. `rules/` and `docs/` argue instead, and are not scanned.
SCANNED_DIRS: tuple[str, ...] = ("skills", "commands", "agents", "hooks")

#: Bare roots only — a legacy root that is already a subpath (".claude/records") is
#: unreachable from a project-relative instruction, so matching it would flag prose
#: about an install layout rather than a write.
_BARE = sorted(
    {r for r in (*LEGACY_RECORDS_ROOTS, *LEGACY_WIKI_ROOTS) if "/" not in r},
    key=len,
    reverse=True,
)

#: A root followed by a leaf. The lookbehind is what lets `.squad/records/x` pass:
#: any preceding "/", "." or word character means this is not a project-relative root.
_PATTERN = re.compile(
    r"(?<![\w./-])(" + "|".join(re.escape(r) for r in _BARE) + r")/[a-z][a-z0-9._-]*"
)

#: Same shape as the english-only marker, and refused for the same reason when empty.
_EXEMPT = re.compile(r"<!--\s*write-path:\s*\S+.*?-->")


def sweep(root: Path | str) -> tuple[list[dict], int]:
    """The findings, and how many files were read to reach them.

    The count is not decoration. A clean verdict over zero files is indistinguishable
    from a clean verdict over the whole kit unless the report says which it was, and
    the second is the one people act on.
    """
    base = Path(root)
    findings: list[dict] = []
    read = 0
    for name in SCANNED_DIRS:
        directory = base / name
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.md")):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            read += 1
            for number, line in enumerate(text.splitlines(), start=1):
                if _EXEMPT.search(line):
                    continue
                for match in _PATTERN.finditer(line):
                    findings.append(
                        {
                            "file": str(path.relative_to(base)),
                            "line": number,
                            "path": match.group(0),
                        }
                    )
    return findings, read


def scan(root: Path | str) -> list[dict]:
    """The findings alone, for callers that do not report coverage."""
    return sweep(root)[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"UNCHECKED  {root} is not a directory", file=sys.stderr)
        return UNCHECKED

    findings, read = sweep(root)

    # Zero files read is not a clean tree. This file already owns the word for it —
    # UNCHECKED, used two lines above — and the branch below used to print CLEAN and
    # fall through to a 0. A gate whose glob stops matching goes silent rather than
    # red, which is the failure this repository names in other people's code.
    if not read:
        where = ", ".join(f"{d}/" for d in SCANNED_DIRS)
        message = f"UNCHECKED  nothing swept: no markdown under {where}"
        if args.json:
            print(json.dumps({"findings": [], "count": 0, "files_read": 0,
                              "unchecked_because": message}, indent=2))
        else:
            print(message, file=sys.stderr)
        return UNCHECKED

    if args.json:
        print(json.dumps(
            {"findings": findings, "count": len(findings), "files_read": read},
            indent=2,
        ))
    elif findings:
        print(f"INSTRUCTED  {len(findings)} legacy-root write instruction(s)\n")
        for f in findings:
            print(f"  {f['file']}:{f['line']}  {f['path']}  ->  .squad/{f['path']}")
        print("\nWriters only ever produce `.squad/` (rules/records-location.md).")
        print("Prose that discusses a legacy root marks itself:")
        print("  <!-- write-path: reason -->")
    else:
        print(f"CLEAN  {read} file(s) swept; no legacy-root instruction")
    return INSTRUCTED if findings else CLEAN


if __name__ == "__main__":
    raise SystemExit(main())
