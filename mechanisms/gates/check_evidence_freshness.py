#!/usr/bin/env python3
"""How old is each open item's evidence, and does every pointer it cites still resolve?

    python3 mechanisms/gates/check_evidence_freshness.py
    python3 mechanisms/gates/check_evidence_freshness.py --root . --all

## Two things a single "staleness" number conflates

  - **old** — the measurement was taken a while ago. NOT a defect. A thirty-day-old
    measurement of something nobody has touched is still true, and failing on age trains
    people to re-measure on a calendar rather than on a reason.
  - **wrong** — the evidence cites a path that no longer resolves. That IS a defect: the
    next reader follows the pointer, finds nothing, and cannot tell whether the finding
    moved or was never real.

So age is REPORTED and a dead pointer FAILS.

## Where this came from

Written by a consumer session on 2026-09-21 while closing its own B-231, and
routed here because the subject is the kit: `hooks/boundary-check.py` had refused to let
it write into the installed kit, in exactly these terms — *"A fix written inside an
installed kit protects exactly one machine and is erased by the next install."* It lived
in that project's gitignored `.squad/tools/`, which is the condition the refusal
describes.

Ported rather than reimplemented. Three of its decisions came from measurement and do
not follow from the contract, and rewriting from the description would have thrown them
away:

  1. **A path resolves against SEVERAL roots.** Items cite `adapters/agent-mount.js`,
     relative to a package source root. The repository root alone reported 41 dead
     pointers where 22 were dead.
  2. **No `\b` before a path.** A word boundary does not match before a leading dot, so
     a path like `.claude/rules/<name>.md` would be read without its leading dot and resolve against
     nothing.
  3. **The date read is the LATEST in the block, not the first.** An item re-measured
     yesterday carries its original `evidence:` date above a `REMEASURED` note; reading
     the first reports 30 days where there is 1.

## Scope of the failure is deliberately narrow

Only `triaged` and `approved` items can fail — they are the ones about to be planned
against. A `shipped` or `killed` item's pointers are history, and history may reference a
tree that has since moved; failing on it would make the check red forever and therefore
ignored.
"""
from __future__ import annotations

import argparse
import glob
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        sys.path.insert(0, str(_up))
        break
from _contract import add_root  # noqa: E402 — sibling module, path set above
from squad.paths import data_root  # noqa: E402 — post-bootstrap import

CITED_PATH = re.compile(
    r"`((?:\.?[\w.-]+/)+[\w.-]+\.(?:ts|tsx|js|mjs|cjs|py|md|json|txt|yml|yaml|sh))(?::\d+)?`"
)
ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
BLOCK_START = re.compile(r"(?m)^## (B-\d+)\b(.*)$")
STATUS_LINE = re.compile(r"(?m)^status:\s*(\w+)\s*$")

OPEN_STATUSES = frozenset({"triaged", "approved"})

# Cited strings that are not repository paths and must not be reported as dead pointers.
NOT_A_PATH = ("...", ".vite/", "node_modules/")

# An item whose SUBJECT is a retired path cites a dead pointer ON PURPOSE — B-233 is literally
# "nineteen kit files still cite the routing table's retired path". Reporting those would make the
# check red on exactly the items that exist to remove them, and a check that is red forever is a
# check somebody disables.
#
# The exemption is per LINE and carries a reason, copying `check_english_only.py`'s proven shape
# rather than inventing a second convention. A marker with nothing after the colon does not count:
# a silent opt-out is the thing being prevented, so an opt-out that says nothing is refused exactly
# like the dead pointer it was covering.
DEAD_POINTER_OK = re.compile(r"<!--\s*dead-pointer-ok:\s*(\S.*?)-->")


@dataclass
class Item:
    item_id: str
    title: str
    status: str
    latest_date: date | None
    dead: list[str] = field(default_factory=list)
    cited: int = 0

    @property
    def age_days(self) -> int | None:
        return None if self.latest_date is None else (date.today() - self.latest_date).days


def resolution_roots(project: Path) -> list[Path]:
    """Every root a cited path may legitimately be relative to.

    The write root comes from `squad.paths`, which owns every spelling of it. The ported
    original wrote the literal here and `check_write_containment` refused it within the
    hour — correctly, and for the reason that module exists: a second place that spells
    the data root is a second place that has to be found when it moves.
    """
    roots = [project, project / ".claude", data_root(project)]
    for pattern in ("packages/*/src", "apps/*/src", "packages/*", "apps/*"):
        roots += [Path(p) for p in sorted(glob.glob(str(project / pattern))) if Path(p).is_dir()]
    return roots


def split_blocks(text: str) -> list[tuple[str, str, str]]:
    """Return (item_id, title, body) per `## B-NNN` block, body running to the next one."""
    marks = list(BLOCK_START.finditer(text))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((m.group(1), m.group(2).strip(), text[m.end() : end]))
    return out


def latest_date_in(body: str) -> date | None:
    """The MOST RECENT date in the block, not the first.

    A block carries its original `evidence:` date and any later `REMEASURED YYYY-MM-DD` note.
    Reading the first reports an item re-measured yesterday as a month old — measured on this
    registry, where three of the five items an audit called stale already carried one.
    """
    found = []
    for y, mo, d in ISO_DATE.findall(body):
        try:
            found.append(date(int(y), int(mo), int(d)))
        except ValueError:
            continue
    return max(found) if found else None


def dead_pointers(body: str, roots: list[Path]) -> tuple[list[str], int]:
    """Cited paths that resolve nowhere, minus the ones a line exempts with a reason.

    The scan is per line rather than per block: an item may deliberately cite one retired path
    and accidentally cite another, and a block-level exemption would hide the second.
    """
    cited: set[str] = set()
    exempt: set[str] = set()
    for line in body.splitlines():
        found = set(CITED_PATH.findall(line))
        if not found:
            continue
        cited |= found
        marker = DEAD_POINTER_OK.search(line)
        if marker:
            # A marker MAY name the path it covers. One line can cite a retired path and its
            # replacement — measured on B-233, whose evidence says the table "moved to
            # `.squad/…` … 19 files still name `rules/…`" in a single sentence. Exempting the
            # whole line would hide the replacement's status too, which is the coarseness this
            # scan is per-line to avoid in the first place.
            reason = marker.group(1)
            named = {c for c in found if c in reason}
            exempt |= named if named else found
    cited = {c for c in cited if not any(skip in c for skip in NOT_A_PATH)}
    dead = [c for c in sorted(cited - exempt) if not any((r / c).exists() for r in roots)]
    return dead, len(cited)


def collect(registry: Path, project: Path) -> list[Item]:
    text = registry.read_text(encoding="utf-8")
    roots = resolution_roots(project)
    items = []
    for item_id, title, body in split_blocks(text):
        st = STATUS_LINE.search(body)
        status = st.group(1) if st else "unknown"
        dead, cited = dead_pointers(body, roots)
        items.append(Item(item_id, title, status, latest_date_in(body), dead, cited))
    return items


def render(items: list[Item], show_all: bool) -> int:
    open_items = [i for i in items if i.status in OPEN_STATUSES]
    failing = [i for i in open_items if i.dead]

    dated = [i for i in open_items if i.age_days is not None]
    dated.sort(key=lambda i: i.age_days or 0, reverse=True)

    print(f"open items ({'/'.join(sorted(OPEN_STATUSES))}): {len(open_items)}")
    if dated:
        ages = [i.age_days or 0 for i in dated]
        median = sorted(ages)[len(ages) // 2]
        print(f"evidence age: median {median}d, oldest {ages[0]}d, undated {len(open_items) - len(dated)}")
        print("\n age  item     cited  status     title")
        rows = dated if show_all else dated[:10]
        for i in rows:
            print(f"{i.age_days:>4}d  {i.item_id}  {i.cited:>5}  {i.status:<9}  {i.title[:50]}")
        if not show_all and len(dated) > len(rows):
            print(f"      … {len(dated) - len(rows)} more (use --all)")

    print()
    if not failing:
        print("PASS — every pointer cited by an open item resolves")
        return 0

    print(f"FAIL — {len(failing)} open item(s) cite a pointer that is gone:")
    for i in failing:
        age = "undated" if i.age_days is None else f"evidence {i.age_days}d old"
        print(f"\n  {i.item_id} ({i.status}, {age})")
        for d in i.dead:
            print(f"      {d}")
    print(
        "\nA dead pointer is not an old measurement — it is one nobody can follow."
        "\nRe-measure the item, or correct the path if the file only moved."
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    # `--root`, per `mechanisms/gates/_contract.py`: a caller that does not know which
    # gate it is talking to passes this and it works. `--project` survives as an alias
    # so the consumer's own invocations keep running.
    add_root(ap)
    ap.add_argument("registry", nargs="?", default=None)
    ap.add_argument("--project", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--all", action="store_true", help="print every dated item, not the ten oldest")
    args = ap.parse_args(argv)

    # `--root` is the contract's name for the tree; `--project` was this script's own
    # and still answers. The registry defaults to BACKLOG.md under whichever was given.
    project = Path(args.project) if args.project else Path(args.root)
    registry = Path(args.registry) if args.registry else project / "BACKLOG.md"
    if not registry.is_file():
        # UNCHECKED, and it says so: no registry means nothing was swept, which is a
        # different fact from a registry whose pointers all resolve. This kit's own
        # repository is the case — `BACKLOG.md` is never versioned here — so the gate
        # runs in a CONSUMER, invoked by `/backlog-review`, and not in the kit's CI
        # where it could only ever report this.
        print(f"UNCHECKED: no registry at {registry}, so no item was examined and "
              f"nothing was swept. An absent registry is not a clean one.",
              file=sys.stderr)
        return 2
    try:
        items = collect(registry, project)
    except OSError as exc:
        print(f"cannot read the registry: {exc}", file=sys.stderr)
        return 2
    return render(items, args.all)


if __name__ == "__main__":
    raise SystemExit(main())
