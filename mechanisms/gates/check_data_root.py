#!/usr/bin/env python3
"""Report a project still holding data outside `<project>/.squad/`.

    python3 mechanisms/gates/check_data_root.py [--root .] [--json]

## Why this reports and does not move

The kit cannot run anything inside another project's repository. A migration this
script performed there would be the kit writing to a repository it does not own, which
is the same line `check_wiki_migration.py` draws for the OKF bundle and for the same
reason. It reports; a person moves.

## Why a legacy root is not a failure

Readers fall back, so a consumer that updated the kit without migrating keeps working.
What it does NOT keep is a single place to look: once the write root has content and a
legacy root still does, a reader resolving the first never sees the second, and the
older copy is silently unreachable rather than merely old.

That state is the loudest thing here, exactly as `SPLIT` is in the wiki migration.

  CENTRALISED   nothing is left outside the write root
  UNMIGRATED    a legacy root holds data and the write root does not — readers still
                resolve the old one, and nothing else says so
  SPLIT         both hold data. The old copy is unreachable and looks current
  EMPTY         neither holds anything

Exit codes:
  0  centralised, or nothing to migrate
  1  a legacy root still holds data
  2  the tree could not be read; nothing was checked, and that is not a pass
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from squad.paths import (
    DATA_DIRNAME,
    LEGACY_RECORDS_ROOTS,
    LEGACY_STATE_NAMES,
    LEGACY_WIKI_ROOTS,
    data_root,
)

CENTRALISED, UNMIGRATED_CODE, UNCHECKED = 0, 1, 2

#: Files a directory carries without being "data" — a scaffold nobody filled.
_IGNORED = frozenset({".gitkeep", ".DS_Store"})


def _documents(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return [p for p in directory.rglob("*")
            if p.is_file() and p.name not in _IGNORED]


@dataclass(frozen=True)
class RootReport:
    relative: str
    files: int
    state: str
    detail: str


def check_project(root: Path) -> list[RootReport]:
    root = Path(root)
    current_has = bool(_documents(data_root(root)))
    reports: list[RootReport] = []

    candidates = [*LEGACY_RECORDS_ROOTS, *LEGACY_WIKI_ROOTS, *LEGACY_STATE_NAMES]
    for relative in candidates:
        directory = root / relative
        files = len(_documents(directory))
        if not files:
            continue
        if current_has:
            state = "SPLIT"
            detail = (f"{files} file(s) here AND content under {DATA_DIRNAME}/. Readers "
                      "resolve the write root, so this copy is unreachable and looks "
                      "current")
        else:
            state = "UNMIGRATED"
            detail = (f"{files} file(s) still here; readers fall back to them, and "
                      "nothing else says so")
        reports.append(RootReport(relative, files, state, detail))

    if not reports:
        state = "CENTRALISED" if current_has else "EMPTY"
        detail = ("nothing outside the write root" if current_has
                  else "no data anywhere yet — nothing to migrate")
        reports.append(RootReport(DATA_DIRNAME, len(_documents(data_root(root))),
                                  state, detail))
    return reports


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = args.root.resolve()
    if not root.is_dir():
        print(f"unchecked: no such tree {root}", file=sys.stderr)
        return UNCHECKED

    reports = check_project(root)
    worst = "SPLIT" if any(r.state == "SPLIT" for r in reports) else (
        "UNMIGRATED" if any(r.state == "UNMIGRATED" for r in reports)
        else reports[0].state)

    if args.json:
        print(json.dumps({
            "root": str(root), "write_root": DATA_DIRNAME, "overall": worst,
            "roots": [{"relative": r.relative, "files": r.files, "state": r.state,
                       "detail": r.detail} for r in reports],
        }, indent=2))
    else:
        print(f"data root — {root}")
        for r in reports:
            print(f"  {r.state:<12} {r.relative:<28} {r.files} file(s)")
            print(f"               {r.detail}")
        print(f"\nOverall: {worst}")
        if worst != "CENTRALISED" and worst != "EMPTY":
            print(f"\nMove what is listed into {DATA_DIRNAME}/. This script will not do "
                  "it: a migration\nrun inside a repository the kit does not own is the "
                  "kit writing to somebody else's project.", file=sys.stderr)

    return CENTRALISED if worst in ("CENTRALISED", "EMPTY") else UNMIGRATED_CODE


if __name__ == "__main__":
    raise SystemExit(main())
