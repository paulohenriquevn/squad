#!/usr/bin/env python3
"""Close the items a release actually shipped, from the stream rather than a guess.

    python3 scripts/advance_items.py [project] [--apply]

ADVANCE is the last unimplemented phase of `cycle-maintenance.md`, and the reason it
waited this long is worth stating: for weeks the thing it consumes did not exist.
Nothing emitted `RELEASED`, so an ADVANCE built then could only have INFERRED the
release from files on disk — and it writes `shipped`, into the one artefact that
outlives the session, where the contract's own anti-pattern is *if nothing was
released, nothing shipped*.

## It runs after the human, not instead of them

Measured on the first autonomous run: the executing session's own plan ends at
`/release (stops at PR_OPEN_AWAITING_APPROVAL)`. A session driving the cycle
unattended will never emit `RELEASED`, by design — the approval, the merge and the
tag are all past a gate it cannot pass. `RELEASED` appears only after a person
approved, which is what makes this safe to automate: by the time it acts, every
judgement it might have needed has already been made by someone else.

So this is not the autonomous loop closing its own items. It is the bookkeeping that
follows a decision, and it decides nothing.

## What it refuses

It moves an item only on an explicit `cycle:phase:end` with `cycle=release` and
`verdict=RELEASED`. It writes through `backlog_status.py`, which refuses an illegal
transition, so an item that is blocked, killed, or already shipped is left alone and
the refusal is reported rather than swallowed. Running it twice changes nothing the
first run already did.

Exit codes: 0 nothing to do or everything applied · 1 at least one write was refused
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import backlog_status as bs  # noqa: E402

#: Where a consumer's stream lives, in the two layouts that exist.
_STREAM_RELATIVE = (".claude/records/cycle-events.jsonl", "records/cycle-events.jsonl")


@dataclass
class Advance:
    shipped: list[str] = field(default_factory=list)
    verified_local: list[str] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)
    already: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        verdict = ("ITEM_SHIPPED" if self.shipped
                   else "ITEM_VERIFIED_LOCAL" if self.verified_local
                   else "NOTHING_TO_ADVANCE")
        return {"verdict": verdict,
                "shipped": self.shipped, "verified_local": self.verified_local,
                "refused": self.refused,
                "already_shipped": self.already, "not_in_registry": self.unknown}



def all_changes_are_untracked(project_root: Path, files: list[str]) -> bool:
    """The mechanical test `cycle-maintenance.md` defines for `ITEM_VERIFIED_LOCAL`.

        git check-ignore -q <every file the fix changed>

    succeeds for ALL of them. If any changed file IS tracked, the item is not in this
    state — it has a release and must take it.

    An empty list is False, deliberately: "changed nothing" is not "changed only
    untracked things", and the state exists for work that was really done.

    This verdict was carried as declared debt with the note that declaring it is
    judgement. The rule says otherwise in its own words — *the test is mechanical, not
    rhetorical* — and the exemption was wrong for three weeks because nobody reread the
    section that defines it.
    """
    if not files:
        return False
    result = subprocess.run(
        ["git", "-C", str(project_root), "check-ignore", "-q", "--", *files],
        capture_output=True, text=True, check=False,
    )
    # 0 = every path is ignored · 1 = at least one is not · other = git failed, and a
    # failure must not read as "all untracked".
    return result.returncode == 0

def stream_path(project_root: Path) -> Path | None:
    for rel in _STREAM_RELATIVE:
        candidate = project_root / rel
        if candidate.is_file():
            return candidate
    return None


def released_items(project_root: Path) -> list[str]:
    """Every item a `RELEASED` event names, oldest first, without repeats.

    The slug is normalised the way the board normalises it, because both slug
    conventions reach the stream and both are correct in their own phase — the item id
    from the maintenance chain, the plan slug from the phases that name an artefact.
    """
    path = stream_path(project_root)
    if path is None:
        return []
    seen: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue  # a half-written last line is normal in an append-only file
        if (event.get("type") == "cycle:phase:end"
                and event.get("cycle") == "release"
                and event.get("verdict") == "RELEASED"):
            item = _item_id(event.get("slug") or "")
            if item and item not in seen:
                seen.append(item)
    return seen


def _item_id(slug: str) -> str:
    import re

    match = re.search(r"\bb-?(\d{3,})\b", slug, re.IGNORECASE)
    return f"B-{match.group(1)}" if match else ""


def advance(backlog: Path, project_root: Path, apply: bool = False) -> Advance:
    result = Advance()
    items = released_items(project_root)
    if not items:
        return result

    content = backlog.read_text(encoding="utf-8")
    spans = bs._blocks(content)

    for item in items:
        if item not in spans:
            result.unknown.append(item)
            continue
        start, end = spans[item]
        if bs._status_of(content[start:end]) == "shipped":
            result.already.append(item)
            continue
        try:
            content = bs.advance(content, item, "shipped")
        except bs.Refused as exc:
            # Reported, never swallowed. A refusal here usually means the registry
            # knows something the stream does not — the item is blocked, or was killed
            # — and that is the registry being right.
            result.refused.append(f"{item}: {exc}")
            continue
        result.shipped.append(item)
        spans = bs._blocks(content)

    if apply and result.shipped:
        backlog.write_text(content, encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project", nargs="?", default=".", type=Path)
    parser.add_argument("--apply", action="store_true",
                        help="write the registry; without it, report and change nothing")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = args.project.resolve()
    backlog = root / "BACKLOG.md"
    if not backlog.is_file():
        print(f"FATAL: no BACKLOG.md under {root}", file=sys.stderr)
        return 1

    result = advance(backlog, root, apply=args.apply)

    if args.json:
        print(json.dumps(result.as_dict(), indent=2, ensure_ascii=False))
    else:
        if stream_path(root) is None:
            print("no event stream — nothing released here yet")
        verb = "shipped" if args.apply else "would ship"
        for item in result.shipped:
            print(f"ITEM_SHIPPED: {item} ({verb})")
        for item in result.already:
            print(f"  already shipped: {item}")
        for item in result.unknown:
            print(f"  released but not in this registry: {item}")
        for line in result.refused:
            print(f"  REFUSED {line}", file=sys.stderr)
        if not (result.shipped or result.already or result.unknown or result.refused):
            print("NOTHING_TO_ADVANCE: no RELEASED event in the stream")
        elif not args.apply and result.shipped:
            print("\n(dry run — pass --apply to write)")

    return 1 if result.refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
