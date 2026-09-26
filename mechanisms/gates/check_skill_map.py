#!/usr/bin/env python3
"""`skills/map.md` must list every skill on disk, and only those.

    python3 check_skill_map.py [--root .] [--json]

WHY THIS EXISTS
---------------
The index this map replaces went stale twice, and the second time is recorded in
the CHANGELOG:

    the old `README.md` under `skills/`: it said 35 skills, there are 36, and the table omitted 7

Four of those omitted skills had **zero mentions in any entry point** — they
existed on disk, passed every validator, and were unreachable by any discovery
path. When the map was written on 2026-08-31 the same file claimed 36 skills
against 34 on disk and listed 29, with `shared-understanding` among the missing
(renamed `plan-alignment` later the same day):
the alignment gate that is unbreakable for every item coming from `BACKLOG.md`.

Twice is a pattern, and the pattern is not carelessness. An index is the one
document nothing forces you to open when you add a file, so it drifts by default
and the drift is invisible — the file still reads as complete.

WHAT IT ASSERTS
---------------
Three things, and the second is the one the CHANGELOG says was missed:

    missing_from_map   a skill directory with no row here
    absent_from_disk   a row for a skill that no longer exists
    count_disagrees    the prose says N skills and the directory holds M
    missing_sop        a skill with no `SOP.md` beside its `SKILL.md`

The fourth clause is the same defect one level down. `SKILL.md` is the contract
the agent executes; `SOP.md` is what a person needs to run the phase and act on
what comes back — measured 2026-08-31, only 6 of 34 skills answered "it returned
X, now what". A skill that ships without one is reachable and not operable, and
nothing else would say so.

It does not check what a row SAYS. Whether "Do NOT" is the right prohibition is
judgement, and a checker claiming to verify that would be asserting a review
nobody performed. What it buys is that the map cannot silently stop being a map.

Exit codes:
    0 — the map and the directory agree
    1 — they disagree
    2 — the map or the skills directory is unreadable
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from squad.paths import is_cycle_generated_skill

#: The first cell of a table row, and every skill named in it. A row may name two
#: (`backlog-init`, `backlog-review`) where one line covers both.
_ROW_RE = re.compile(r"^\|\s*((?:`[a-z0-9-]+`(?:\s*,\s*)?)+)[^|]*\|", re.MULTILINE)
_NAME_RE = re.compile(r"`([a-z0-9-]+)`")
_COUNT_RE = re.compile(r"\*\*(\d+) skills\.\*\*")


def listed_skills(map_path: Path) -> set[str]:
    text = map_path.read_text(encoding="utf-8", errors="replace")
    names: set[str] = set()
    for cell in _ROW_RE.findall(text):
        names.update(_NAME_RE.findall(cell))
    return names


def claimed_count(map_path: Path) -> int | None:
    found = _COUNT_RE.search(map_path.read_text(encoding="utf-8", errors="replace"))
    return int(found.group(1)) if found else None


def declared_by_project(root: Path) -> set[str]:
    """Skills the CONSUMER declares as its own, in `rules/auxiliary-skills.txt`.

    `map.md` is the KIT's inventory: it lists what the kit ships and cannot know
    what a project wrote for itself. Without reading this file the checker asks a
    consumer's domain skills for a row in a map they do not belong in, and every
    finding it produces is about that project's own design.

    `check_xrefs.py` has read this file since the day it was added, and this one
    did not — a HALF exemption, which is the shape `_is_auto_generated`'s own
    docstring warns about: the first version of that fix exempted one check and
    left its sibling charging, traded 26 WARN for 3, and looked like a fix.
    Measured here on 2026-09-02: a consumer with three domain skills got
    `missing_from_map` ×3, `missing_sop` ×3 and `count_disagrees`, none of them
    about the kit.
    """
    declared = root / "rules" / "auxiliary-skills.txt"
    if not declared.is_file():
        return set()
    return {
        line.split("#", 1)[0].strip()
        for line in declared.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        if line.split("#", 1)[0].strip()
    }


def check(root: Path) -> list[str]:
    skills_dir = root / "skills"
    map_path = skills_dir / "map.md"
    if not map_path.is_file():
        return [f"missing_map: {map_path} does not exist"]

    #: The project's own skills leave the comparison entirely: they are not in the
    #: kit's map, they owe it no row, and the count is the kit's count.
    project_owned = declared_by_project(root)
    #: What the CYCLES wrote leaves the comparison too, and for a different reason
    #: than the project's own skills: these are output. The exemption is imported
    #: rather than spelled — `check_xrefs.py` has had it since the day it hoisted
    #: the predicate out of an inline check, closing with "One definition, two
    #: consumers: that is what stops the next half from escaping." This gate was
    #: the next half, and warned about that exact shape in `declared_by_project`
    #: while being it.
    on_disk = {p.parent.name for p in skills_dir.glob("*/SKILL.md")
               if not is_cycle_generated_skill(p.parent.name)} - project_owned
    listed = listed_skills(map_path)

    findings = []
    for name in sorted(on_disk - listed):
        findings.append(
            f"missing_from_map: `{name}` is a skill on disk with no row in map.md — "
            f"it is reachable only by someone who already knows it is there")
    for name in sorted(listed - on_disk):
        findings.append(
            f"absent_from_disk: map.md has a row for `{name}`, which no longer exists")

    for name in sorted(on_disk):
        if not (skills_dir / name / "SOP.md").is_file():
            findings.append(
                f"missing_sop: `{name}` has no SOP.md — the contract is there and "
                f"the procedure for operating it is not")

    claimed = claimed_count(map_path)
    if claimed is not None and claimed != len(on_disk):
        findings.append(
            f"count_disagrees: map.md says {claimed} skills; the directory holds "
            f"{len(on_disk)}")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not (root / "skills").is_dir():
        print(f"FATAL: {root}/skills is not a directory", file=sys.stderr)
        return 2

    findings = check(root)
    if args.json:
        print(json.dumps({"root": str(root), "findings": findings,
                          "verdict": "FAIL" if findings else "PASS"}, indent=2))
        return 1 if findings else 0

    print(f"skill map — {root / 'skills' / 'map.md'}")
    for finding in findings:
        print(f"  {finding}")
    print()
    if findings:
        print(f"Overall: FAIL — {len(findings)} disagreement(s) with the directory")
        return 1
    print("Overall: PASS — the map lists every skill on disk and only those")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
