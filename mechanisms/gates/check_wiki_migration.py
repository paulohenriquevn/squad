#!/usr/bin/env python3
"""Report a project still reading its durable knowledge from the old root.

    python3 check_wiki_migration.py [--root .] [--json]

WHY THIS EXISTS
---------------
`rules/records-location.md` and `.squad/wiki/decisions/where-knowledge-lives.md` split
one directory into two kinds of artifact: durable knowledge into the OKF bundle
at `wiki/`, the dated trail left in `records/`. Readers fall back — bundle
first, records second — because a hard cut would break every consumer that
updates the kit without running a migration, and the kit cannot run anything
inside another project's repository.

`tests/test_wiki_fallback.py` states the limit of that tolerance in its own
docstring:

    It is not permanent tolerance for two layouts. `check_wiki_migration.py`
    reports a project still reading from the old root, so the transition stays
    visible instead of becoming the shape of the system.

**That script did not exist.** The sentence describing the mechanism that keeps
the migration visible was the only evidence that nothing kept it visible — the
kit's signature defect, a contract with no mechanism, in the file whose job was
to prevent exactly this. Measured 2026-08-31, four days after the split was
declared: the bundle held 6 files against 4406 lines still in `rules/`, and
`.squad/wiki/opportunities/` was empty in the kit and in all eight consumers. The
migration had not stalled loudly. It had stalled silently, which is worse,
because a fallback that always falls back looks identical to a fallback nobody
needs.

WHAT IT ASSERTS, AND WHAT IT REFUSES TO
---------------------------------------
For each leaf the split declares durable, it answers one question: does this
project's knowledge for that leaf resolve to the bundle, or to the old root?

  MIGRATED     the bundle holds it
  UNMIGRATED   the old root holds it and the bundle does not — the finding
  EMPTY        neither holds anything, so there is nothing to migrate
  SPLIT        both hold files — the worst state, and the loudest

`SPLIT` is reported hardest on purpose. Two directories holding the same kind of
artifact is the failure `records-location.md` was written about: a reader who
checks one reports absence where evidence exists, and nothing errors. A fallback
returns the FIRST hit, so once both exist the old root's copy is unreachable and
silently stale.

It does **not** move anything. A migration this script performed inside a
consumer's repository would be the kit writing to a project it does not own, and
the fallback exists precisely because that is not allowed. It reports; a person
or a cycle moves.

It also does not read file CONTENT. Whether a document is durable knowledge is a
judgement, and `DURABLE_LEAVES` already encodes the answer per leaf — asking
this script to re-decide it per file would be a second source for a fact that
has one.

Exit codes:
    0 — nothing is reading from the old root
    1 — at least one leaf is UNMIGRATED or SPLIT
    2 — the root is not a directory
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

# The family this file lives in, plus `lib/` — the import namespace stayed flat
# when `scripts/` became `mechanisms/<family>/`, so a sibling family is reached
# by path rather than by package.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "conventions"))

from sop_format import DURABLE_LEAVES, knowledge_base_dir, wiki_dir

MIGRATED = "MIGRATED"
UNMIGRATED = "UNMIGRATED"
EMPTY = "EMPTY"
SPLIT = "SPLIT"

#: What counts as content. A directory holding only `.gitkeep` is a scaffold the
#: installer made, not knowledge somebody wrote — counting it as migrated would
#: report every fresh consumer as done on the day it was installed.
_IGNORED = frozenset({".gitkeep", "index.md", "log.md"})


def _documents(directory: Path | None) -> list[str]:
    if directory is None or not directory.is_dir():
        return []
    return sorted(p.name for p in directory.rglob("*.md")
                  if p.is_file() and p.name not in _IGNORED)


@dataclass(frozen=True)
class LeafReport:
    leaf: str
    legacy_leaf: str
    state: str
    in_bundle: int
    in_records: int
    detail: str


def check_leaf(root: Path, leaf: str, legacy_leaf: str) -> LeafReport:
    bundle = _documents(wiki_dir(root, leaf))
    legacy = _documents(knowledge_base_dir(root, legacy_leaf))

    if bundle and legacy:
        state = SPLIT
        detail = (f"both roots hold documents; readers resolve the bundle and "
                  f"the {len(legacy)} under `records/{legacy_leaf}/` are "
                  f"unreachable and cannot be seen to be stale")
    elif legacy:
        state = UNMIGRATED
        detail = (f"{len(legacy)} document(s) still under `records/{legacy_leaf}/` "
                  f"— readers fall back to them, and nothing else says so")
    elif bundle:
        state = MIGRATED
        detail = f"{len(bundle)} document(s) in the bundle"
    else:
        state = EMPTY
        detail = "neither root holds a document — nothing to migrate"
    return LeafReport(leaf, legacy_leaf, state, len(bundle), len(legacy), detail)


def check_project(root: Path) -> list[LeafReport]:
    return [check_leaf(root, leaf, legacy)
            for leaf, legacy in sorted(DURABLE_LEAVES.items())]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not root.is_dir():
        print(f"FATAL: {root} is not a directory", file=sys.stderr)
        return 2

    reports = check_project(root)
    failing = [r for r in reports if r.state in (UNMIGRATED, SPLIT)]

    if args.json:
        print(json.dumps({"root": str(root),
                          "leaves": [asdict(r) for r in reports],
                          "verdict": "UNMIGRATED" if failing else "CLEAN"}, indent=2))
        return 1 if failing else 0

    print(f"wiki migration — {root}")
    for r in reports:
        print(f"  {r.state:<11} {r.leaf:<15} bundle={r.in_bundle} "
              f"legacy {r.legacy_leaf}={r.in_records}")
        print(f"              {r.detail}")
    print()
    if failing:
        print(f"Overall: UNMIGRATED — {len(failing)} leaf/leaves still reading the old root")
        return 1
    print("Overall: CLEAN — no leaf resolves to the old root")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
