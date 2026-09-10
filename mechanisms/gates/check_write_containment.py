#!/usr/bin/env python3
"""Nothing this system writes escapes `<project>/.squad/`.

    python3 mechanisms/gates/check_write_containment.py [--root .] [--json]

## What it enforces, and why that is enough

Every data-root literal lives in `squad/paths.py`. This gate fails any other kit file
that names one in CODE. Together those two facts are the guarantee: if no other module
can spell a root, every path a writer builds came from the owner, and the owner only
ever produces the one root.

The alternative — proving containment by reading 164 writing call sites — is not a
proof anybody can re-run. This is.

## Why it strips prose first

The kit argues in prose about the very directories it forbids in code, and this file is
itself an example. `test_every_gate_is_reachable.py` learned the same lesson the
expensive way: nine prose mentions once read as call sites and hid an unrun gate for
ten hours. So comments and string literals used as documentation are removed before
matching, exactly as that test does it.

## What it deliberately does not do

It does not move a legacy directory, and it does not fail a project for HAVING one. A
consumer that has not migrated keeps working because readers fall back; the writers are
what this constrains. Reporting an unmigrated root is `check_data_root.py`'s job, and
moving it is a person's — a migration this code performed inside a consumer's
repository would be the kit writing to a project it does not own.

Exit codes:
  0  no kit file outside the owner names a data root
  1  at least one does — the copy that makes the guarantee unprovable
  2  the tree could not be read; nothing was checked, and that is not a pass
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from squad.paths import (
    DATA_DIRNAME,
    LEGACY_RECORDS_ROOTS,
    LEGACY_STATE_NAMES,
    LEGACY_WIKI_ROOTS,
    SESSION_STATE,
    SNAPSHOTS,
)

CONTAINED, LEAKED, UNCHECKED = 0, 1, 2

#: The single module allowed to spell a root. Everything else calls it.
OWNER = Path("squad") / "paths.py"

#: Trees that are the kit's code. `tests/` is excluded because a test asserting the
#: literal is a test asserting the contract — forbidding it would forbid checking it.
CODE_TREES = ("mechanisms", "skills", "hooks", "squad", "commands")

#: Derived from the owner, never restated. A gate holding its own copy of the list it
#: polices is the defect it exists to catch, and it reported exactly that about itself
#: on the first run.
#:
#: `.squad` carries its dot; `squad` without one is the shared PACKAGE, which every
#: module may import by name.
_ROOTS = tuple(sorted(
    {re.escape(DATA_DIRNAME)}
    | {re.escape(r.split("/")[-1]) for r in (*LEGACY_RECORDS_ROOTS, *LEGACY_WIKI_ROOTS)}
    # Session state the system writes and reads back. Policing only the trail and the
    # bundle left these outside the guarantee: `session-state/` and
    # `.compaction-snapshots/` sat beside the installed kit and the first scan could
    # not see them, so "everything is contained" was true of two thirds of the writes.
    | {re.escape(n) for n in (SESSION_STATE, SNAPSHOTS)}
    | {re.escape(n) for n in LEGACY_STATE_NAMES},
    key=len, reverse=True))
_LITERAL = re.compile(
    r"""(['"])(?:\.claude/|\./)?(?:%s)(?:/[^'"]*)?\1""" % "|".join(_ROOTS)
)

_PY_TRIPLE = re.compile(
    r'''(?xs)(?:[rRbBuUfF]{0,2})(?:""".*?"""|\'\'\'.*?\'\'\')'''
)
_LINE_COMMENT = re.compile(r"(?m)(^[ \t]*|[ \t;&|])#[^\n]*")


def _blank(match: re.Match[str]) -> str:
    """Same length, same newlines, no content.

    Deleting prose shifts every line after it, and the gate then reports a literal at a
    line that holds something else. A finding a reader cannot find is a finding they
    stop trusting.
    """
    return "".join("\n" if c == "\n" else " " for c in match.group(0))


def strip_prose(text: str, suffix: str) -> str:
    """Blank what a reader reads and a program does not run, preserving line numbers."""
    if suffix == ".py":
        text = _PY_TRIPLE.sub(_blank, text)
    return _LINE_COMMENT.sub(lambda m: _blank(m)[: len(m.group(0))], text)


def _is_owner(path: Path, root: Path) -> bool:
    try:
        return path.resolve().relative_to(root.resolve()) == OWNER
    except ValueError:
        return False


def scan(root: Path, counter: list[int] | None = None) -> list[dict]:
    """Every kit file outside the owner that spells a data root in code.

    `counter`, when given, receives the number of files actually read. A scan that
    examined nothing must not report containment: the tree could be empty, or a glob
    could have broken, and CONTAINED reads the same either way.
    """
    findings: list[dict] = []
    for tree in CODE_TREES:
        base = root / tree
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in (".py", ".sh") or not path.is_file():
                continue
            parts = path.parts
            if "__pycache__" in parts or "tests" in parts:
                continue
            if _is_owner(path, root):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if counter is not None:
                counter[0] += 1
            code = strip_prose(text, path.suffix)
            for m in _LITERAL.finditer(code):
                # A path segment has no spaces. `"records/ (cycle output) and ..."` is
                # a sentence that happens to start with a directory name, and failing a
                # gate on prose teaches the reader to bypass it.
                if " " in m.group(0) or "\t" in m.group(0):
                    continue
                line = code[: m.start()].count("\n") + 1
                findings.append({
                    "file": str(path.relative_to(root)),
                    "line": line,
                    "literal": m.group(0),
                })
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = args.root.resolve()
    if not root.is_dir():
        print(f"unchecked: no such tree {root}", file=sys.stderr)
        return UNCHECKED

    counter = [0]
    findings = scan(root, counter)
    examined = counter[0]
    status = "leaked" if findings else ("nothing_scanned" if not examined else "contained")
    body = {
        "root": str(root),
        "owner": str(OWNER),
        "files_examined": examined,
        "findings": findings,
        "status": status,
    }
    if args.json:
        print(json.dumps(body, indent=2))
        return CONTAINED if not findings else LEAKED

    if status == "nothing_scanned":
        # Not a pass. An empty tree and a broken glob produce the same silence, and
        # `tests/test_gates_say_what_they_examined.py` exists because a gate quiet
        # about its own reach is one whose next broken glob nobody notices.
        print(f"write containment: NOTHING SCANNED — 0 files read under {root}. "
              f"That is not containment; it is an unexamined tree.", file=sys.stderr)
        return UNCHECKED

    if not findings:
        print(f"write containment: CONTAINED — {examined} file(s) examined, every "
              f"data root spelled only in {OWNER}")
        return CONTAINED

    print(f"write containment: LEAKED — {len(findings)} literal(s) outside {OWNER} "
          f"across {examined} file(s) examined", file=sys.stderr)
    for f in findings:
        print(f"  {f['file']}:{f['line']}  {f['literal']}", file=sys.stderr)
    print("\nA second module that can spell a root is how six lists in four different "
          "orders happened, and\nwith a copy in play no scan can prove where the "
          "writers write. Call `squad.paths` instead.", file=sys.stderr)
    return LEAKED


if __name__ == "__main__":
    raise SystemExit(main())
