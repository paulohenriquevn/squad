#!/usr/bin/env python3
"""Select the next eligible milestone from ROADMAP.md for cycle-roadmap.

Parses milestone headers (`### M<N> — [<status>] <name>`), extracts each
milestone's objective, definition-of-done bullets, and declared dependencies,
then picks the lowest-N milestone whose status is `[ ]` and whose dependencies
are all `[x]`.

Output is a single JSON line on stdout suitable for piping into the idea-to-release
orchestrator's Step 0.

Usage:
    python3 select_next_milestone.py --roadmap ROADMAP.md --json
    python3 select_next_milestone.py --roadmap ROADMAP.md --prefer M3 --json

Verdicts (in `verdict` field unless a concrete milestone is picked):
    - milestone selected   → returns {"milestone_id", "name", "objective", "dod", "depends_on"}
    - ROADMAP_COMPLETE     → every milestone is [x]
    - ROADMAP_BLOCKED      → [ ] milestones remain but each has an unchecked dep
    - PREFER_NOT_ELIGIBLE  → --prefer was passed but that milestone is not eligible

Exit codes:
    0 — eligible milestone found
    1 — ROADMAP_COMPLETE or ROADMAP_BLOCKED or PREFER_NOT_ELIGIBLE
    2 — file not found / parse error
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "roadmap.py").is_file():
        sys.path.insert(0, str(_up))
        break
# Below the bootstrap: `squad` is importable only after sys.path is extended.
from squad import roadmap as _roadmap  # noqa: E402 — post-bootstrap import

# The header, DoD and dependency patterns used to live here. They were one of three
# copies that disagreed — this one alone could spell `[-]`, and alone knew it meant
# CANCELLED. `squad/roadmap.py` owns them now; `tests/test_one_reader_of_the_roadmap.py`
# records what the disagreement cost the other two.


@dataclass
class Milestone:
    """One parsed milestone block."""

    id: str  # "M0", "M1", …
    n: int  # numeric form for sort
    status: str  # "x" | " " | "-"
    name: str
    objective: str = ""
    dod: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)

    @property
    def done(self) -> bool:
        return self.status == "x"

    @property
    def cancelled(self) -> bool:
        return self.status == "-"

    @property
    def unchecked(self) -> bool:
        return self.status == " "


def parse_roadmap(text: str) -> list[Milestone]:
    """Parse a ROADMAP.md text into an ordered list of Milestone records."""
    parsed = _roadmap.parse(text)
    if not parsed:
        raise ValueError("no milestone headers found (expected `### M<N> — [<status>] <name>`)")

    milestones = [
        Milestone(
            id=m.id,
            n=int(m.id[1:]),
            status=m.status.value,
            name=m.name,
            objective=m.objective,
            dod=list(m.dod),
            # `**Dependencies:** none.` declares the ABSENCE of one, and the shared
            # reader cannot collapse that to `[]` for everyone: a caller may want to
            # tell "declared none" from "declared nothing". This one does not, so the
            # word is dropped here.
            depends_on=[] if m.dependency_label and "none" in _depends_line(m).lower()
            else sorted(set(m.depends_on)),
        )
        for m in parsed
    ]
    milestones.sort(key=lambda m: m.n)
    return milestones


def _depends_line(milestone: "_roadmap.Milestone") -> str:
    match = _roadmap.DEPENDS_RE.search(milestone.body)
    return match.group(2) if match else ""


def select(milestones: list[Milestone], prefer: str | None = None) -> dict:
    """Pick the next eligible milestone, or return a verdict dict."""
    done_ids = {m.id for m in milestones if m.done}
    unchecked = [m for m in milestones if m.unchecked]

    if not unchecked:
        return {"verdict": "ROADMAP_COMPLETE"}

    def is_eligible(m: Milestone) -> bool:
        return all(dep in done_ids for dep in m.depends_on)

    eligible = [m for m in unchecked if is_eligible(m)]

    if prefer:
        target = next((m for m in milestones if m.id == prefer), None)
        if target is None:
            return {"verdict": "PREFER_NOT_ELIGIBLE", "reason": f"{prefer} not present in roadmap"}
        if target.done:
            return {"verdict": "PREFER_NOT_ELIGIBLE", "reason": f"{prefer} already [x]"}
        if target.cancelled:
            return {"verdict": "PREFER_NOT_ELIGIBLE", "reason": f"{prefer} cancelled"}
        if not is_eligible(target):
            missing = [dep for dep in target.depends_on if dep not in done_ids]
            return {
                "verdict": "PREFER_NOT_ELIGIBLE",
                "reason": f"{prefer} depends on unchecked milestone(s): {','.join(missing)}",
            }
        return _to_payload(target)

    if not eligible:
        wall = [
            {"id": m.id, "blocked_by": [dep for dep in m.depends_on if dep not in done_ids]}
            for m in unchecked
        ]
        return {"verdict": "ROADMAP_BLOCKED", "wall": wall}

    return _to_payload(min(eligible, key=lambda m: m.n))


def _to_payload(m: Milestone) -> dict:
    return {
        "milestone_id": m.id,
        "name": m.name,
        "objective": m.objective,
        "dod": m.dod,
        "depends_on": m.depends_on,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roadmap", type=Path, default=Path("ROADMAP.md"))
    parser.add_argument("--prefer", help="Target a specific milestone (e.g. M3); fail if not eligible.")
    parser.add_argument("--json", action="store_true", help="Emit JSON (default; reserved for future formats).")
    args = parser.parse_args()

    if not args.roadmap.exists():
        print(f"file not found: {args.roadmap}", file=sys.stderr)
        return 2

    try:
        milestones = parse_roadmap(args.roadmap.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"parse error: {exc}", file=sys.stderr)
        return 2

    result = select(milestones, prefer=args.prefer)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if "milestone_id" in result else 1


if __name__ == "__main__":
    sys.exit(main())
