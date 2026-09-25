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
  NESTED        a write root inside the write root. No migration makes one; a writer
                that took the write root for a project does
  INSIDE_KIT    data written into the installed kit, which the next install deletes
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

#: Findings from loudest to quietest; the overall state is the first one present.
_SEVERITY = ("INSIDE_KIT", "NESTED", "SPLIT", "UNMIGRATED")

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

    # Data written INSIDE the installed kit, which this gate could not see.
    #
    # Measured on a consumer 2026-09-16: `convene_panel.py` resolved its project as
    # `parents[2]`, which is `.claude/` in a plugin install, and `write_records_dir`
    # produced `.claude/.squad/records/panels/` — six files, two of them discover
    # assignments no later run regenerates. This gate reported SPLIT for two other paths
    # and said nothing about the one a kit script was actively writing to.
    #
    # It is worse than SPLIT and gets its own state. `.claude/` is gitignored AND replaced
    # wholesale by the installer: the records reach nobody and are scheduled for deletion,
    # while a reader resolving the write root reports absence. `records-location.md` names
    # this blind spot in its own words — "a writer whose destination never passes through
    # `squad.paths` — taken from argv, joined onto the installed kit, handed down by a
    # caller."
    # `DATA_DIRNAME`, not the literal. `squad.paths` owns every data-root spelling and
    # this is the third time in two days I have written one outside it — the gate that
    # refuses the literal caught all three, which is the only reason the count is three
    # rather than unknown.
    for kit in (root / ".claude", root / DATA_DIRNAME / "kit"):
        if not kit.is_dir():
            continue
        # `DATA_DIRNAME` only. `.claude/records` is the DOCUMENTED legacy plugin layout
        # and is already classified above as UNMIGRATED or SPLIT; sweeping it here too
        # reclassified correct findings and broke two existing tests — the scan deciding
        # what it was looking at instead of measuring, third time today in this session.
        for inner in (DATA_DIRNAME,):
            stranded = kit / inner
            files = len(_documents(stranded))
            if not files:
                continue
            reports.append(RootReport(
                str(stranded.relative_to(root)), files, "INSIDE_KIT",
                f"{files} file(s) written into the installed kit. The kit tree is "
                f"gitignored and replaced wholesale on the next install, so these reach "
                f"nobody and are scheduled for deletion — while a reader resolving the "
                f"write root reports absence. A writer resolved the project as the kit "
                f"directory it lives in."))

    # A write root nested inside the write root. No migration produces it; a writer that
    # took `.squad` for a project does. SPLIT compares the write root with roots BESIDE
    # it, so this copy was invisible here — measured on a consumer 2026-09-25 with 39
    # cycle events in the nested stream against 763 in the real one, and nothing said so.
    nested = data_root(root) / DATA_DIRNAME
    files = len(_documents(nested))
    if files:
        reports.append(RootReport(
            str(nested.relative_to(root)), files, "NESTED",
            f"{files} file(s) in a write root inside the write root. No migration "
            f"produces this; a writer resolved {DATA_DIRNAME}/ itself as the project. "
            f"No reader resolves it, so this copy is unreachable"))

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
    worst = next((s for s in _SEVERITY if any(r.state == s for r in reports)),
                 reports[0].state)

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
