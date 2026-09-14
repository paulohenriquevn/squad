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

#: Who ticked. Same marker and same convention as `score_alignment.py`: `human/paulo`,
#: `judge/alignment-judge`. Captures to the closing marker so the ROUTE survives —
#: `human/paulo (approved in session)` says more than `human`.
SIGNED_BY_RE = re.compile(r"<!--\s*signed-by:\s*([^>]+?)\s*-->")


def signature(text: str) -> tuple[bool, str]:
    """(ticked, signer) for the sign-off section. `signer` is "" when unattributed.

    Only the section AFTER the heading counts: the item list above it is full of boxes,
    and reading one of those as the signature would let a single ticked item authorise
    the whole brief.
    """
    match = SIGNOFF_RE.search(text)
    if not match:
        return False, ""
    tail = text[match.end():]
    line = re.search(r"^-\s*\[[xX]\].*$", tail, re.M)
    if not line:
        return False, ""
    signer = SIGNED_BY_RE.search(line.group(0))
    return True, signer.group(1).strip() if signer else ""


def signer_is_human(signer: str) -> bool:
    """A NAMED human is still a human — same rule as `score_alignment.py`.

    `human`, or anything under `human/`. Everything else is an agent, and an
    UNATTRIBUTED tick is refused here rather than read as a person's.

    That last part differs from `score_alignment.py` on purpose, and the difference is
    the point of this gate. There, an unattributed tick predates provenance and reading
    it as a human's preserves history. Here, the entire mechanism is that a PERSON chose
    this work: a brief is generated, ticked and signed in one session, so an
    unattributed tick is not history — it is an agent that did not say who it was.
    """
    return signer == "human" or signer.startswith("human/")


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

    ticked_off, signer = signature(text)
    if not ticked_off:
        print("REFUSED: the brief is not signed.")
        print(f"  {len(ticked)} item(s) are ticked, and ticks without a signature are "
              "reading notes, not a decision.")
        print(f"  sign it first:  /sign {brief}")
        return 1

    # The gate that was missing, and it was missing in the one place it is the whole
    # point. `_signed()` checked THAT the box was ticked and never WHO ticked it, so
    # `/sign --despite-authorship` from an agent passed — the mechanism built to require
    # a person did not require a person.
    #
    # This is the mirror of the correction `alignment-threshold.md` made on 2026-09-01.
    # There, "must be human" was doing two jobs and only one was the argument, so a judge
    # was allowed to sign an item's brief. Here there is only one job and it IS the
    # argument: `approved` means somebody decided this is the work they want, and an
    # agent deciding that on the owner's behalf is the thing the status was created to
    # record. `cycle-backlog.md` calls it a commitment.
    if not signer_is_human(signer):
        print("REFUSED: this brief was signed by " + (f"`{signer}`" if signer
                                                      else "nobody who said who they were")
              + ".")
        print("  `approved` records that a PERSON decided this is the work they want.")
        print("  An agent may sign an item's alignment brief — it did not write that brief")
        print("  and it reads the evidence. It may not make this decision, because there")
        print("  is no evidence that answers it: the question is what you want built.")
        print(f"  a person signs with:  /sign {brief} --as <name>")
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

    because = f"approved in {brief.name} by {signer}"
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
