#!/usr/bin/env python3
"""Close the items a release actually shipped, from the stream rather than a guess.

    python3 mechanisms/cycle/advance_items.py [project] [--apply]

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

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap
from pathlib import Path as _Path_bootstrap

import backlog_status as bs

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
from squad.paths import DATA_DIRNAME, LEGACY_RECORDS_ROOTS  # noqa: E402

#: Where a consumer's stream lives: the one write root, then the legacy roots a
#: project may not have migrated. Readers fall back; writers never do.
_STREAM_RELATIVE = tuple(
    f"{base}/cycle-events.jsonl"
    for base in (f"{DATA_DIRNAME}/records", *LEGACY_RECORDS_ROOTS)
)


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



def _statuses_behind_their_records(project_root: Path) -> list[tuple[str, str]]:
    """Items whose artefacts on disk are further along than their status line.

    Through SELECT, which already computes this: `approved_implemented` is an item whose
    IMPLEMENT record exists while its status says the decision was only taken. Reading
    it here rather than scanning again keeps one reader of that question, which is the
    shape this kit keeps restoring.

    Empty on any failure: this is a report beside a verdict, and a report that cannot be
    produced must not turn a clean run into a failed one.
    """
    import json as _json  # noqa: PLC0415
    import subprocess as _sp  # noqa: PLC0415
    selector = None
    for up in Path(__file__).resolve().parents:
        candidate = up / "skills" / "backlog-review" / "scripts" / "select_backlog_item.py"
        if candidate.is_file():
            selector = candidate
            break
    backlog = project_root / "BACKLOG.md"
    if selector is None or not backlog.is_file():
        return []
    try:
        out = _sp.run([sys.executable, str(selector), str(backlog), "--json"],
                      capture_output=True, text=True, timeout=300).stdout
        data = _json.loads(out[out.index("{"):])
    except Exception:  # noqa: BLE001 - a report must never fail the verdict
        return []
    behind = [(i, "an IMPLEMENT record exists; status is still `approved`")
              for i in (data.get("approved_implemented") or [])]
    behind += [(i, "a plan exists on disk; status is still `approved`")
               for i in (data.get("plan_written") or [])]
    return behind


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
            # And say what this did NOT look at, because "nothing to advance" reads as
            # "the registry agrees with its records" and this examined ONE transition.
            #
            # `planned -> shipped` is the only hop here. The registry can also be behind
            # in the middle — an item whose IMPLEMENT record exists while its status is
            # still `approved`, because `planned` is written by the stage that STARTS
            # work and a lane that halted walked it back without walking it forward.
            #
            # Measured on a consumer 2026-09-16: this printed NOTHING_TO_ADVANCE while
            # SELECT reported an item under `approved_implemented` and twenty-five under
            # `plan_written`. A mechanism that examined one direction must not report on
            # all of them.
            #
            # REPORTED, never advanced. Inferring "work started" from an artefact on disk
            # is a guess, and the hop it would write is the one that says a lane owns the
            # item. `backlog_status.py --to planned` is the writer, and the lane that
            # knows why is the one that should run it.
            behind = _statuses_behind_their_records(root)
            if behind:
                print(f"\nNOT EXAMINED HERE: {len(behind)} item(s) whose records are "
                      f"ahead of their status:")
                for item, why in behind[:10]:
                    print(f"  {item}: {why}")
                if len(behind) > 10:
                    print(f"  ... and {len(behind) - 10} more")
                print("  This tool advances `planned -> shipped` only. Those are"
                      " `approved -> planned`, written by"
                      " `backlog_status.py <ITEM> --to planned --because ...` —"
                      " and the lane that knows why is the one that should run it.")
        elif not args.apply and result.shipped:
            print("\n(dry run — pass --apply to write)")

    return 1 if result.refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
