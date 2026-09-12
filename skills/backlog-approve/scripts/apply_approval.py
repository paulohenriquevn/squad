#!/usr/bin/env python3
"""Turn a signed brief into the status nobody was writing.

    python3 apply_approval.py <project> <brief.md> [--dry-run]

The brief is the decision; this is the only thing that records it. It reads which items
a person ticked, and moves exactly those to `approved` — through `backlog_status.py`,
which is the single writer of a status line in this ecosystem and stays that way.

## Three refusals, each for a different lie

**An unsigned brief writes nothing.** Ticks without a signature are someone's reading
notes. Treating them as a decision would put `approved` — which the contract calls a
commitment — on work nobody committed to.

**A signed brief with nothing ticked writes nothing, and says so.** That state is almost
certainly a mistake: either the reader ticked in a copy, or signed before reading. The
one thing it is not is a decision to approve nothing, and silently succeeding would look
identical to having approved something.

**An item that is not at `triaged` is skipped and named.** `backlog_status.py` owns
which transitions are legal and will refuse an illegal one; this reports the skip rather
than letting a refusal scroll past as an error nobody reads.

## Why it shells out instead of editing the file

`rules/cycle-backlog.md` records what happened the last time transitions were written by
hand: `planned` sat in the contract and in zero items everywhere, because *"every
transition was a human editing a line, and the middle one quietly stopped happening."*
A second writer here would reopen exactly that, for exactly the same reason.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

#: An item the reader committed to. The id must be bold, as the brief renders it, so a
#: mention of `B-012` inside someone's prose note cannot be read as a tick.
TICKED_RE = re.compile(r"^-\s*\[[xX]\]\s*\*\*(B-\d+)\*\*", re.M)
UNTICKED_RE = re.compile(r"^-\s*\[\s*\]\s*\*\*(B-\d+)\*\*", re.M)
SIGNOFF_RE = re.compile(r"^##+\s+Sign-off\s*$", re.M)


def _signed(text: str) -> bool:
    """True when the box in the sign-off section is ticked.

    Only the section AFTER the heading counts: the item list above it is full of boxes,
    and reading one of those as the signature would let a single ticked item authorise
    the whole brief.
    """
    match = SIGNOFF_RE.search(text)
    if not match:
        return False
    tail = text[match.end():]
    return bool(re.search(r"^-\s*\[[xX]\]", tail, re.M))


def _status_writer(project: Path) -> Path | None:
    """Find `backlog_status.py`, installed copy or checkout, without guessing."""
    for base in (project / ".claude", project, *Path(__file__).resolve().parents):
        candidate = base / "mechanisms" / "cycle" / "backlog_status.py"
        if candidate.is_file():
            return candidate
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Move the items a signed brief ticked to `approved`.")
    parser.add_argument("project", type=Path)
    parser.add_argument("brief", type=Path)
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would be written, write nothing")
    args = parser.parse_args()

    project = args.project.resolve()
    brief = args.brief.resolve()
    if not brief.is_file():
        print(f"NOT MEASURED: no brief at {brief}", file=sys.stderr)
        return 2
    backlog = project / "BACKLOG.md"
    if not backlog.is_file():
        print(f"NOT MEASURED: no BACKLOG.md under {project}", file=sys.stderr)
        return 2

    text = brief.read_text(encoding="utf-8-sig")
    ticked = TICKED_RE.findall(text)
    untouched = UNTICKED_RE.findall(text)

    if not _signed(text):
        print("REFUSED: the brief is not signed.")
        print(f"  {len(ticked)} item(s) are ticked, and ticks without a signature are "
              "reading notes, not a decision.")
        print(f"  sign it first:  /sign {brief}")
        return 1

    if not ticked:
        print("REFUSED: the brief is signed and nothing is ticked.")
        print(f"  {len(untouched)} item(s) remain unticked, so this would approve "
              "nothing while reporting success.")
        print("  tick what you want done, or leave the backlog as it is.")
        return 1

    writer = _status_writer(project)
    if writer is None:
        print("NOT MEASURED: backlog_status.py not found — it is the only writer of a "
              "status line, and this refuses to become a second one.", file=sys.stderr)
        return 2

    because = f"approved in {brief.name}"
    moved, skipped = [], []
    for item in ticked:
        cmd = [sys.executable, str(writer), str(backlog), item,
               "--to", "approved", "--because", because]
        if args.dry_run:
            cmd.append("--dry-run")
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode == 0:
            moved.append(item)
        else:
            reason = (proc.stderr or proc.stdout or "").strip().splitlines()
            skipped.append((item, reason[-1] if reason else "no reason given"))

    verb = "would move" if args.dry_run else "moved"
    print(f"{verb} {len(moved)} item(s) to approved: {', '.join(moved) or '—'}")
    if skipped:
        print(f"  {len(skipped)} refused by backlog_status.py:")
        for item, reason in skipped:
            print(f"    {item}  {reason[:120]}")
    if untouched:
        print(f"  {len(untouched)} left at their current status, deliberately: "
              f"{', '.join(untouched[:8])}"
              + (" …" if len(untouched) > 8 else ""))
        print("    Unticked is not rejected. Nothing was written for these.")
    return 1 if skipped else 0


if __name__ == "__main__":
    raise SystemExit(main())
