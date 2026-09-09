#!/usr/bin/env python3
"""Which test suites a set of changed files can affect.

`sq test --touched` exists to turn a nine-minute feedback loop into seconds, and the
only way it can be wrong that MATTERS is by narrowing: a map that misses an edge runs
fewer tests and still reports success. So every rule that cannot resolve a path widens
to everything, and the reason travels with the selection rather than being inferred by
whoever reads it.

This lives in `conventions/` rather than in the CLI because "which suite owns this
path" is a fact about how this repository is laid out, not about how one command
prints things. Anything else that needs the same answer imports it here instead of
deriving a second one.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
No import graph. A file under `mechanisms/` is reachable from most slices — a slice
conftest inserts `mechanisms/` on `sys.path`, and `rules/*.txt` are read by gates the
slices exercise — so the honest answer for those trees is "everything", and computing
a precise one would be a slow way to arrive at the same place most of the time.

Exit codes (when run directly):
    0 — a selection was produced
    2 — the arguments could not be read
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

#: Trees whose tests live in the ROOT suite rather than in any slice.
_ROOT_OWNED = ("tests/", "hooks/", "squad/")

#: Trees that every slice can reach, so a change there is not attributable to one.
_SHARED = ("mechanisms/", "rules/", ".github/")

#: Single files with the same reach as a shared tree.
_SHARED_FILES = ("conftest.py", "pyproject.toml")


@dataclass(frozen=True)
class Selection:
    """What to run, and why — including the case where the map gave up."""

    slices: frozenset[str] = frozenset()
    root_suite: bool = False
    #: True when something could not be attributed and the run must cover everything.
    everything: bool = False
    reasons: tuple[str, ...] = field(default_factory=tuple)


def select(paths: list[str], known_slices: frozenset[str]) -> Selection:
    """Map changed paths onto suites. Unattributable input widens the whole run.

    `known_slices` is passed in rather than globbed here so the caller owns the one
    definition of what a slice is — `run_slice_tests.sh` is that definition, and a
    second glob in this file would be a second answer to the same question.
    """
    if not paths:
        return Selection(reasons=("no changed files — nothing to select",))

    slices: set[str] = set()
    root = False
    widen: list[str] = []

    for raw in sorted(set(paths)):
        # `removeprefix`, not `lstrip`: lstrip strips any leading "." or "/" CHARACTER,
        # so `.claude-plugin/plugin.json` arrived as `claude-plugin/plugin.json` and
        # `.gitattributes` as `gitattributes`. Both still widened — the selection was
        # safe — but the reason named a path nobody could look up.
        path = raw.replace("\\", "/").removeprefix("./")

        if path.startswith(_ROOT_OWNED):
            root = True
            continue

        if path.startswith(_SHARED) or path in _SHARED_FILES:
            widen.append(f"{path} — shared by every slice, so it cannot be attributed to one")
            continue

        if path.startswith("skills/"):
            parts = path.split("/")
            if len(parts) > 1 and parts[1] in known_slices:
                slices.add(parts[1])
            else:
                # A skill with no `tests/` directory is not a slice. Guessing which
                # slice it belongs to would under-run.
                widen.append(f"{path} — under skills/ but not a slice that has tests")
            continue

        widen.append(f"{path} — no rule maps this path, and no match is not no impact")

    if widen:
        return Selection(everything=True, root_suite=True, reasons=tuple(widen))

    reasons = []
    if slices:
        reasons.append(f"{len(slices)} slice(s) selected from {len(set(paths))} changed file(s)")
    if root:
        reasons.append("the root suite owns tests/, hooks/ and squad/")
    return Selection(slices=frozenset(slices), root_suite=root, reasons=tuple(reasons))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("paths", nargs="*", help="changed paths, repo-relative")
    parser.add_argument("--slice", action="append", default=[], dest="known",
                        help="a slice name that exists (repeatable)")
    args = parser.parse_args(argv)

    sel = select(args.paths, frozenset(args.known))
    if sel.everything:
        print("EVERYTHING")
    else:
        for name in sorted(sel.slices):
            print(name)
        if sel.root_suite:
            print("(root suite)")
    for reason in sel.reasons:
        print(f"  {reason}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
