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

  COMMITTABLE   the study zone is not ignored by git: third-party material cloned
                where the rule says to put it is one `git add -A` from the history
  CENTRALISED   nothing is left outside the write root
  UNMIGRATED    a legacy root holds data and the write root does not — readers still
                resolve the old one, and nothing else says so
  SPLIT         both hold data. The old copy is unreachable and looks current
  NESTED        a write root inside the write root. No migration makes one; a writer
                that took the write root for a project does
  SHARED        the kit's leaves sit in a bare `wiki/` beside another producer's
                bundle. Readers no longer fall back to it, so they are unreachable
  FOREIGN       a bare `wiki/` holding another producer's bundle and nothing of the
                kit's. Reported so it is not mistaken for Squad data; not a failure
  INSIDE_KIT    data written into the installed kit, which the next install deletes
  EMPTY         neither holds anything

Exit codes:
  0  centralised, or nothing to migrate
  1  a legacy root still holds data, or the study zone can be committed
  2  the tree could not be read; nothing was checked, and that is not a pass
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from squad.paths import (
    DATA_DIRNAME,
    KIT_LOCATED_WIKI_ROOTS,
    LEGACY_RECORDS_ROOTS,
    LEGACY_STATE_NAMES,
    LEGACY_WIKI_ROOTS,
    data_root,
    foreign_wiki_entries,
    is_kit_wiki,
    kit_wiki_leaves_in,
)
from squad.boundaries import STUDY_ZONE

CENTRALISED, UNMIGRATED_CODE, UNCHECKED = 0, 1, 2

#: Findings from loudest to quietest; the overall state is the first one present.
FAILING_STATES = ("COMMITTABLE", "INSIDE_KIT", "NESTED", "SPLIT", "SHARED", "UNMIGRATED")

#: States that describe a directory which is not the kit's data. Printed, never the
#: overall verdict: there is nothing of the kit's in it to move.
_INFORMATIONAL = frozenset({"FOREIGN"})

#: The legacy wiki roots whose location does not vouch for them — the bare `wiki/`
#: two plugins write their own OKF bundle into by default. `squad.paths.wiki_dir` reads
#: one only when it has the kit's shape, and this gate has to classify it the same way
#: or it asks a project to migrate a plugin's output into the kit's write root.
_SHAPE_JUDGED_WIKI_ROOTS = frozenset(LEGACY_WIKI_ROOTS) - KIT_LOCATED_WIKI_ROOTS

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
        if relative in _SHAPE_JUDGED_WIKI_ROOTS and not is_kit_wiki(directory):
            reports.append(_foreign_wiki(relative, directory, files))
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

    zone = _committable_study_zone(root)
    if zone is not None:
        reports.append(zone)

    if not [r for r in reports if r.state not in _INFORMATIONAL]:
        state = "CENTRALISED" if current_has else "EMPTY"
        detail = ("nothing outside the write root" if current_has
                  else "no data anywhere yet — nothing to migrate")
        reports.append(RootReport(DATA_DIRNAME, len(_documents(data_root(root))),
                                  state, detail))
    return reports


def _committable_study_zone(root: Path) -> RootReport | None:
    """The study zone, if git would let it into the index. None when it would not.

    `reference-provenance.md` § 1 keeps third-party material out of the history by
    where it sits — inside the write root, "ignored whole". That held in one repository,
    this kit's own; in a consumer it rested on a `.gitignore` nothing read, because
    `install.sh` leaves `.gitignore` to the consumer and nothing checked what the
    consumer decided.

    Only the zone is probed, never all of `.squad/`: a consumer may version its bundle
    or its records on purpose, and that choice is not the kit's to overrule. A tree
    outside git has no index to protect, so it gets no row.
    """
    inside = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
                            capture_output=True, text=True, check=False)
    if inside.returncode != 0:
        return None
    probe = f"{STUDY_ZONE}/probe/LICENSE"
    ignored = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", probe],
                             capture_output=True, text=True, check=False)
    if ignored.returncode == 0:
        return None
    if ignored.returncode != 1:
        raise RuntimeError(f"git check-ignore could not answer for {root / probe}: "
                           f"exit {ignored.returncode}, {ignored.stderr.strip()!r}")
    return RootReport(
        STUDY_ZONE, len(_documents(root / STUDY_ZONE)), "COMMITTABLE",
        f"git does not ignore {STUDY_ZONE}/, where reference-provenance.md says "
        f"third-party material goes. A clone there is one `git add -A` from this "
        f"history, licence included. Add `{DATA_DIRNAME}/` to .gitignore (or at least "
        f"`{STUDY_ZONE}/`); this script will not edit it")


def _foreign_wiki(relative: str, directory: Path, files: int) -> RootReport:
    """A bare `wiki/` the kit's readers no longer fall back to — FOREIGN or SHARED."""
    foreign = ", ".join(foreign_wiki_entries(directory)) or "OKF reserved files only"
    kit_leaves = kit_wiki_leaves_in(directory)
    if not kit_leaves:
        return RootReport(relative, files, "FOREIGN",
                          f"{files} file(s) in a bundle without the kit's shape "
                          f"({foreign}) — another producer's, by default a loop-* plugin's. "
                          f"No reader resolves it as Squad data; nothing of the kit's to move")
    return RootReport(relative, files, "SHARED",
                      f"the kit's leaves {', '.join(kit_leaves)} share this directory "
                      f"with another producer's bundle ({foreign}). Readers cannot tell "
                      f"whose it is and no longer fall back to it, so those leaves are "
                      f"unreachable. Move them into {DATA_DIRNAME}/wiki/")


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
    worst = next((s for s in FAILING_STATES if any(r.state == s for r in reports)),
                 next(r.state for r in reports if r.state not in _INFORMATIONAL))

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
