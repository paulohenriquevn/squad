"""Reading a project's DECLARED workspace members.

Extracted from `typescript.py` 2026-09-19 (B-194), for the reason the sibling helpers
`_arch.py`, `_wiring.py` and `_mutation.py` are separate: one responsibility, and the
detector that consumes it stays under its row budget without the reasoning being cut to
fit. The measurements behind every decision here are in the docstrings, deliberately —
they are what a reader needs to know why the standard library is not used directly.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


#: Directories a workspace walk never enters. `node_modules` is the one that matters:
#: `Path.glob("components/**/package.json")` descends it, so every installed dependency would
#: register as a workspace member and D2 would stop reporting anything as fabricated. Pruning
#: during the walk rather than filtering after is also where the cost lives — measured on the
#: largest tree this kit audits, 750 directories pruned against 10,920 unpruned.
_WALK_PRUNE = frozenset({"node_modules", ".git"})


def manifests_under(root: Path) -> list[Path]:
    """Every `package.json` under `root`, pruning `_WALK_PRUNE` as the walk descends."""
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _WALK_PRUNE]
        if "package.json" in filenames:
            found.append(Path(dirpath) / "package.json")
    return found


def _yaml_packages(path: Path) -> list[str]:
    """`packages:` from a pnpm workspace file, or `[]` when it declares none.

    The import is GUARDED because PyYAML sits under `[project.optional-dependencies]`: an
    install without the extra has no parser. Returning `[]` there is deliberate and is NOT the
    same as "no members" — the caller falls back to the pre-2026-09 fixed globs, which is the
    behaviour that predates this fix rather than a claim that the workspace is empty.

    A hand-rolled line parser was rejected: it passes this item's own fixture, which writes
    plain `  - 'x'` lines, and mis-reads the kit's real `pnpm-workspace.yaml`, which interleaves
    comment blocks and carries a second top-level key. A parser that passes the test and fails
    the repository is the vacuous assertion this whole change exists to remove.
    """
    try:
        import yaml  # noqa: PLC0415 — optional dependency, guarded on purpose
    except ImportError:
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, Exception):  # noqa: BLE001 — a malformed file is not a crash of the audit
        return []
    if not isinstance(data, dict):
        return []
    packages = data.get("packages")
    if not isinstance(packages, list):
        return []
    return [p for p in packages if isinstance(p, str) and p.strip()]


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """One workspace glob as a regex over a POSIX-relative directory path.

    Written here rather than taken from the standard library because neither candidate can
    execute this dialect, measured on Python 3.10.12:

      * `fnmatch.translate` renders `*` as `.*`, which CROSSES `/` — so `packages/*` matches
        `packages/a/node_modules/dep`;
      * `Path.glob` raises `ValueError` on `!**/test/**` and has no notion of negation at all.

    `*` is within one segment, `**` spans any number of them, and everything else is literal.
    """
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:[^/]+/)*")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile(f"^{''.join(out)}$")


def declared(rel_dir: str, patterns: list[str]) -> bool:
    """Is `rel_dir` a member, under the declared pattern SET?

    Positives include, negations exclude, and the result does NOT depend on their order — which
    is what "as a set" means, verified against `tinyglobby` 0.2.17, the matcher the
    `@manypkg/tools` resolver behind `changesets` uses. A negation wins over every positive, so
    `['packages/*', '!**/test/**']` and its reverse agree, and neither re-includes.

    That is deliberately NOT the gitignore rule. `pathspec` implements gitignore's
    last-match-wins, under which two of pnpm's four documented rows re-include — adopting it
    would have swapped a matcher that crashes on the dialect for one that silently disagrees.
    """
    if rel_dir in ("", "."):
        return False
    included = False
    for pattern in patterns:
        if pattern.startswith("!"):
            if _glob_to_regex(pattern[1:]).match(rel_dir):
                return False
        elif _glob_to_regex(pattern).match(rel_dir):
            included = True
    return included


def find_workspace_roots(changed_files: list[Path]) -> set[Path]:
    """Walk up from each changed file to the first plausible workspace root.

    `.git`, or a workspace file whose declaration is PRESENT and non-empty. The filename
    alone is not enough: pnpm 10 moved non-workspace settings into `pnpm-workspace.yaml`,
    and a settings-only file stopping the walk would leave the collector reading a root
    that declares nothing — the same 98 findings by a second route, created by this very
    fix. `@manypkg/tools` guards on `manifest.packages` being truthy for the same reason.
    """
    roots: set[Path] = set()
    for src_file in changed_files:
        try:
            cur = src_file.resolve().parent if src_file.exists() else Path.cwd()
        except OSError:
            continue
        for parent in [cur, *cur.parents]:
            if (parent / ".git").exists() or read_workspace_declaration(parent):
                roots.add(parent)
                break
    return roots


def read_workspace_declaration(root: Path) -> list[str] | None:
    """The declared member patterns, or None when this directory declares none.

    Four shapes, because four package managers spell it differently and two of them accept
    an object where the others take a list — `data.get("workspaces")` read as a list yields
    NOTHING, silently, on the yarn/bun object form.
    """
    pnpm = root / "pnpm-workspace.yaml"
    if pnpm.is_file():
        declared = _yaml_packages(pnpm)
        if declared:
            return declared
    pkg = root / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        ws = data.get("workspaces")
        if isinstance(ws, list) and ws:
            return [p for p in ws if isinstance(p, str)]
        if isinstance(ws, dict):
            packages = ws.get("packages")
            if isinstance(packages, list) and packages:
                return [p for p in packages if isinstance(p, str)]
    deno = root / "deno.json"
    if deno.is_file():
        try:
            members = json.loads(deno.read_text(encoding="utf-8")).get("workspace")
        except (json.JSONDecodeError, OSError):
            members = None
        if isinstance(members, list) and members:
            return [p for p in members if isinstance(p, str)]
    return None
