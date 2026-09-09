#!/usr/bin/env python3
"""PostToolUse — report prose that is not English, without blocking the write.

`rules/english-only.md` makes this repository English-only. The gate that sweeps
the whole tree is `mechanisms/gates/check_english_only.py`; this fires after a
single edit and asks the same question of that one file, because scanning the
tree on every keystroke would make each edit pay for the whole history.

It never blocks. The write already happened, and refusing it here would report a
failure about an action that cannot be taken back.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from squad import PostToolUseContext, create_context
from squad.layout import resolve

#: Not ours to rewrite, or not prose at all.
SKIP_DIRS = ("node_modules", ".git", "__pycache__", "study-material", "tools")
SKIP_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf", ".ico",
                 ".woff", ".woff2", ".pyc", ".lock")

MAX_SHOWN = 5


def find_checker() -> Path | None:
    """`check_english_only.py`, in whichever layout this install has.

    `squad.layout` answers for the kit as a whole; this still walks candidates
    because a hook can run from a tree where the kit is present but the gate is
    not — a partial copy — and the honest answer there is to say nothing rather
    than to import something that is not there.
    """
    layout = resolve()
    candidates = []
    if layout is not None:
        candidates.append(layout.kit_dir / "mechanisms" / "gates" / "check_english_only.py")
    candidates.append(Path(__file__).resolve().parent.parent
                      / "mechanisms" / "gates" / "check_english_only.py")
    return next((c for c in candidates if c.is_file()), None)


def should_skip(path: Path) -> bool:
    return (any(part in SKIP_DIRS for part in path.parts)
            or path.suffix.lower() in SKIP_SUFFIXES)


def main() -> None:
    c = create_context(PostToolUseContext)
    raw = c.tool_input.get("file_path") or c.tool_input.get("filePath")
    if not raw:
        return
    target = Path(raw)
    if not target.is_file() or should_skip(target):
        return

    checker = find_checker()
    if checker is None:
        return
    sys.path.insert(0, str(checker.parent))
    try:
        from check_english_only import scan_text
    except ImportError:
        return

    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return

    findings = scan_text(text)
    if not findings:
        return

    print(f"english-only: {len(findings)} line(s) in {target.name} are not in English")
    for line_no, markers in findings[:MAX_SHOWN]:
        print(f"  :{line_no}  {', '.join(sorted(set(markers)))}")
    if len(findings) > MAX_SHOWN:
        print(f"  … and {len(findings) - MAX_SHOWN} more")
    print()
    print("This repository is English-only (rules/english-only.md). Translate the line,")
    print("or — when the Portuguese IS the point, as in a verbatim quote or a fixture")
    print("that must be Portuguese — keep it and say why on the line itself:")
    print("  <text>  # english-only: quoting the tool's own output")


if __name__ == "__main__":
    main()
