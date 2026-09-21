#!/usr/bin/env python3
"""The next free `B-NNN`, computed from every id ever spent rather than from the registry's contents.

## Why reading the file is not enough

`skills/backlog-item/SKILL.md` § Step 3 used to say it plainly: *"Extract every `## B-(\\d+)` from
`BACKLOG.md`, take `max(N) + 1`"*. `BACKLOG.md` is unversioned by policy — see
`rules/records-location.md` — so a checkout can hold a registry that lost blocks another checkout
still has, and `max(N) + 1` then hands out an id somebody already used.

Observed in a consumer on 2026-09-18: a second session registered a finding as `B-016`, an id that
registry had already spent. Measured there on 2026-09-21: 93 blocks present, 195 distinct ids cited
across the tree, **138 cited with no block**.

## Why `max(everything cited) + 1` is also wrong

Measured, not feared: it yields **B-1000**, because three of the cited ids are not spent ids. A
template placeholder, a test fixture and a documented example in prose all look exactly like a spent
id to a grep.

## The discriminator is a fact, not a heuristic

An id that was ever spent HAD a block. An example never did, and git records the difference:

    git log --oneline -S "## B-NNN " --all -- BACKLOG.md

Run over all 138 unreachable ids on that consumer it separated them exactly — **135 spent, 3
examples** — and the 3 were precisely the placeholder, the fixture and the prose example.

A path rule was considered and rejected: excluding `templates/` and `tests/` catches two of the three
and misses the one cited in `rules/cycle-backlog.md` prose. A discriminator whose blind spot points
at "looks spent" hands out a live id, which is the failure this exists to prevent.

## What it does when it cannot ask

With no git, or a repository with no commits, it falls back to the present blocks and REPORTS
`history unavailable`. It does not report zero recoveries, because "nothing was recovered" and
"nothing could be asked" are different claims and only one of them is true.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from squad.paths import DATA_DIRNAME  # noqa: E402 — after the path bootstrap above

#: A block header. The trailing space matters for the history query — `## B-016 ` cannot match
#: `## B-0161`, and an id is three digits by convention everywhere this runs.
BLOCK_RE = re.compile(r"^## B-(\d{3})\b", re.MULTILINE)

#: Any citation of an id, anywhere. Deliberately loose: the git question decides what counts.
CITATION_RE = re.compile(r"\bB-(\d{3})\b")

#: Where a citation may live. Narrower than the whole tree, because `node_modules` and build output
#: carry no decisions and searching them costs minutes.
#:
#: The data root is asked of `squad.paths` rather than spelled here. `check_write_containment.py`
#: refused the literal and it was right to: a second module that can spell a root is how six lists in
#: four different orders happened, and with a copy in play no scan can prove where the writers write.
SEARCH_ROOTS = (DATA_DIRNAME, "docs", ".claude", "packages", "apps", "CHANGELOG.md")


@dataclass(frozen=True)
class Allocation:
    """The next id, and the three counts that make it auditable rather than asserted."""

    next_id: str
    present: int
    recovered: int
    rejected: list[str] = field(default_factory=list)
    history_available: bool = True


def present_ids(registry: Path) -> set[int]:
    """Every id with a block in the registry as this checkout holds it."""
    return {int(n) for n in BLOCK_RE.findall(registry.read_text(encoding="utf-8", errors="replace"))}


def cited_ids(root: Path) -> set[int]:
    """Every id written anywhere under the search roots, spent or not."""
    targets = [str(root / p) for p in SEARCH_ROOTS if (root / p).exists()]
    if not targets:
        return set()
    proc = subprocess.run(
        ["grep", "-rhoE", r"\bB-[0-9]{3}\b", *targets],
        capture_output=True,
        text=True,
        check=False,
    )
    return {int(m[2:]) for m in proc.stdout.split()}


def _git(repo: Path, *args: str) -> str | None:
    """`git` output, or `None` when the question could not be asked.

    One wrapper for both queries below. Each used to carry its own `try/except OSError` and its own
    returncode check — two occurrences of the same tolerated-failure shape, found by the audit of
    this change and deleted rather than rearranged.

    `None` is not an empty result. It says git was absent or the command failed, which the caller
    reports as `history unavailable` rather than as `0 recovered`.
    """
    try:
        proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    except OSError:
        return None
    return proc.stdout if proc.returncode == 0 else None


def ids_ever_blocked(repo: Path, registry_name: str) -> set[int] | None:
    """Every id that ever had a block, read from the registry's whole history in ONE call.

    The first version asked `git log -S` once per CITED id, and a test found the hole: an id that
    was spent and is cited NOWHERE is invisible to a citation scan, so it was never a candidate and
    never recovered. On the fixture that left `recovered=0` where 193 blocks existed in history.

    Reading every added block header answers the question directly, and costs one `git log` instead
    of one per candidate — which also removes the plan's MEDIUM risk about a registry with thousands
    of spent ids.
    """
    out = _git(repo, "log", "--all", "-p", "--unified=0", "--format=", "--", registry_name)
    if out is None:
        return None
    return {int(n) for n in re.findall(r"^\+## B-(\d{3})\b", out, re.MULTILINE)}


def _has_history(repo: Path) -> bool:
    """Is there a commit to read at all?

    NOT redundant with `ids_ever_blocked` returning `None`, and the difference was measured: in a
    repository with 0 commits `git log` exits 0 with EMPTY output, so the recovery would report
    `0 recovered` — "git looked and found nothing" — where the truth is "git could not be asked".
    Outside a repository `git log` exits 128. Only `rev-parse HEAD` separates the two.
    """
    return _git(repo, "rev-parse", "HEAD") is not None


def next_backlog_id(registry: Path) -> Allocation:
    """The next free id, and how it was decided."""
    registry = registry.resolve()
    root = registry.parent
    present = present_ids(registry)
    unreachable = sorted(cited_ids(root) - present)

    if not _has_history(root):
        highest = max(present) if present else 0
        return Allocation(f"B-{highest + 1:03d}", len(present), 0, [], history_available=False)

    blocked_ever = ids_ever_blocked(root, registry.name)
    if blocked_ever is None:
        highest = max(present) if present else 0
        return Allocation(f"B-{highest + 1:03d}", len(present), 0, [], history_available=False)

    recovered = blocked_ever - present
    # Cited, never blocked: a placeholder, a fixture, or an example in prose. Reported so the
    # allocation can be audited, and so somebody adding a fourth example sees it named.
    rejected = [f"B-{n:03d}" for n in unreachable if n not in blocked_ever]

    highest = max(present | recovered) if (present or recovered) else 0
    return Allocation(f"B-{highest + 1:03d}", len(present), len(recovered), rejected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("registry", type=Path, help="path to BACKLOG.md")
    parser.add_argument("--json", action="store_true", help="emit the allocation as JSON")
    args = parser.parse_args()

    if not args.registry.is_file():
        print(f"no registry at {args.registry}", file=sys.stderr)
        return 2

    result = next_backlog_id(args.registry)
    if args.json:
        print(json.dumps({
            "next_id": result.next_id,
            "present": result.present,
            "recovered": result.recovered,
            "rejected": result.rejected,
            "history_available": result.history_available,
        }, indent=2))
        return 0

    print(result.next_id)
    recovered = (
        f"{result.recovered} recovered" if result.history_available else "history unavailable"
    )
    print(f"  {result.present} present, {recovered}, {len(result.rejected)} rejected")
    if result.rejected:
        print(f"  rejected (never had a block): {', '.join(result.rejected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
