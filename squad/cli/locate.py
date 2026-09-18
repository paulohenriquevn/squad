"""`sq where` and `sq run` — reaching a mechanism by name instead of by path.

The tree is organised by who OWNS a file (`rules/README.md`), which is right for the
disk and unsearchable by task. Two measured frictions came straight from that: guessing
the wrong directory twice, and guessing the wrong argument form twice — the second
costing an extra call each time, because the usage text only arrives after `exit 2`.

So `sq where` answers both halves at once: the path, what the file says it is for, and
the invocation block it documents.

WHAT THIS INDEX DOES NOT COVER
------------------------------
It globs THREE trees, and `_TREES` below is the list:

  `mechanisms/*/*.py`      kept honest by `check_mechanisms_inventory`
  `hooks/*.py`             covered by no inventory gate — read straight off disk
  `skills/*/scripts/*.py`  covered by no inventory gate — read straight off disk

This overstated its own coverage until 2026-09-17: it claimed a tree count of four and
three gates keeping them honest, and named
`check_skill_map` and `check_squad_map` among the three. Those two check the SKILL and
the MAP, not this index's script glob, and `hooks/` — which really has no inventory —
was not the tree the disclaimer named. The section the whole CLI prints as its honesty
statement overstated its own coverage.
Every report says how many entries carry no description, because an index that answers
confidently about the files it happens to know is the failure this CLI exists to
prevent.

Exit codes:
    0 — the name resolved
    1 — the name is ambiguous; both paths are named and neither is chosen
    2 — the name is unknown, or the tree could not be read
"""
from __future__ import annotations

import argparse
import difflib
import re
import subprocess
import sys
from pathlib import Path

from squad.cli.provenance import describe
from squad.cli.render import emit
from squad.cli.report import FINDING, UNMEASURED, Report

#: Where a runnable mechanism can live. Ordered, so the report can say which tree an
#: entry came from without a second lookup.
_TREES: tuple[tuple[str, str], ...] = (
    ("mechanisms", "*/*.py"),
    ("hooks", "*.py"),
    ("skills", "*/scripts/*.py"),
)

#: The first line of a module docstring, which is the closest thing the house has to a
#: one-line purpose. Matched loosely because a shebang may precede it.
_DOCSTRING_RE = re.compile(r'"""(.*?)(?:\n|""")', re.S)

#: The block a script uses to document how it is invoked. Both spellings appear.
_USAGE_RE = re.compile(r"^(Usage:|Exit codes:)\s*$(.*?)(?=^\S|\Z)", re.M | re.S)


def build_index(root: Path) -> dict[str, list[Path]]:
    """Bare module name -> the file(s) that carry it, sorted for determinism."""
    index: dict[str, list[Path]] = {}
    for tree, pattern in _TREES:
        base = root / tree
        if not base.is_dir():
            continue
        for path in sorted(base.glob(pattern)):
            if path.name.startswith("_") or "__pycache__" in path.parts:
                continue
            index.setdefault(path.stem, []).append(path)
    return index


def _purpose(path: Path) -> str:
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:2000]
    except OSError:
        return ""
    match = _DOCSTRING_RE.search(head)
    return match.group(1).strip() if match else ""


def _invocation(root: Path, path: Path) -> list[str]:
    """The `Usage:` / `Exit codes:` block the file documents, if it has one."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:4000]
    except OSError:
        return []
    lines: list[str] = []
    for match in _USAGE_RE.finditer(text):
        block = match.group(2).strip("\n").rstrip()
        if block:
            lines.append(f"  {match.group(1)}")
            lines.extend(f"  {ln}" for ln in block.splitlines())
    return lines


def _undescribed(index: dict[str, list[Path]]) -> int:
    return sum(1 for paths in index.values() for p in paths if not _purpose(p))


def where(root: Path, name: str) -> Report:
    index = build_index(root)
    report = Report(verb="where", observed=[f"{len(index)} mechanisms", *describe(root)])

    blank = _undescribed(index)
    report.not_checked.append(
        f"{blank} indexed file(s) state no purpose in a docstring — the name resolves, "
        f"the description does not"
        if blank
        else "nothing — every indexed file states a purpose"
    )
    report.not_checked.append(
        "skills/*/scripts/ has no inventory gate; it is read from disk, so a script "
        "moved without updating anything is still found here but nowhere verified"
    )

    paths = index.get(name)

    if not paths:
        close = difflib.get_close_matches(name, index, n=3, cutoff=0.6)
        report.exit_code = UNMEASURED
        report.lines.append(f"no mechanism named {name!r}")
        if close:
            report.lines.append("did you mean:")
            report.lines.extend(f"  {c}" for c in close)
        else:
            report.lines.append("  sq where --list  for everything the index holds")
        return report

    if len(paths) > 1:
        report.exit_code = FINDING
        report.lines.append(f"{name!r} is ambiguous across {len(paths)} files:")
        report.lines.extend(f"  {p.relative_to(root)}" for p in paths)
        report.lines.append("name the tree to disambiguate; this command will not choose")
        return report

    path = paths[0]
    rel = path.relative_to(root)
    report.detail["path"] = str(rel)
    report.lines.append(str(rel))
    purpose = _purpose(path)
    if purpose:
        report.lines.append(f"  {purpose}")
    report.lines.append(f"  run: python3 {rel}")
    report.lines.extend(_invocation(root, path))
    return report


def _repo_root() -> Path:
    # From `Path(__file__)`, never from cwd: `check_xrefs.py` carries the argument for
    # why, and a root taken from cwd silently points a default at the wrong tree.
    return Path(__file__).resolve().parents[2]


def main_where(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sq where", description=__doc__.split("\n")[0])
    parser.add_argument("name", nargs="?", help="the bare module name, e.g. check_xrefs")
    parser.add_argument("--list", action="store_true", help="every name the index holds")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--root", type=Path, default=_repo_root())
    args = parser.parse_args(argv)

    if args.list:
        index = build_index(args.root)
        report = Report(verb="where", observed=[f"{len(index)} mechanisms", *describe(args.root)])
        report.lines = [
            f"{name}  {paths[0].relative_to(args.root)}" for name, paths in sorted(index.items())
        ]
        report.not_checked.append(
            "nothing — this is the whole index, which is what --list means"
        )
        return emit(report, as_json=args.json)

    if not args.name:
        parser.print_usage(sys.stderr)
        print("sq where: a name is required, or --list", file=sys.stderr)
        return UNMEASURED

    return emit(where(args.root, args.name), as_json=args.json)


def main_run(argv: list[str] | None = None) -> int:
    """Run a mechanism by name. Only names the index holds, never a path.

    A CLI that executes whatever path it is handed is a hole
    `hooks/validate-command.py` cannot see: that hook fires on the Bash tool, and
    `sq run` would be the payload rather than the subject.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("sq run: a mechanism name is required", file=sys.stderr)
        print("    sq where --list  for the names", file=sys.stderr)
        return UNMEASURED

    # `router.py` prints "sq <verb> --help  the options for one verb" as the last line of
    # its verb list, and four of five verbs honour it through argparse. This one read
    # argv[0] straight into the index lookup, so `sq run --help` searched for a mechanism
    # named `--help`, failed, and suggested close matches — a documented flag answered
    # with "no mechanism named '--help'".
    if argv[0] in ("-h", "--help"):
        print(main_run.__doc__ or "sq run <mechanism> [args...]")
        print("\n    sq where --list   the names this verb accepts")
        return 0

    name, forwarded = argv[0], argv[1:]
    root = _repo_root()
    paths = build_index(root).get(name)

    if not paths:
        close = difflib.get_close_matches(name, build_index(root), n=3, cutoff=0.6)
        print(f"sq run: no mechanism named {name!r}", file=sys.stderr)
        if close:
            print(f"    did you mean: {', '.join(close)}", file=sys.stderr)
        return UNMEASURED

    if len(paths) > 1:
        print(f"sq run: {name!r} is ambiguous:", file=sys.stderr)
        for p in paths:
            print(f"    {p.relative_to(root)}", file=sys.stderr)
        return FINDING

    done = subprocess.run(
        [sys.executable, str(paths[0]), *forwarded]
    , check=False)
    return done.returncode


if __name__ == "__main__":
    raise SystemExit(main_where())
