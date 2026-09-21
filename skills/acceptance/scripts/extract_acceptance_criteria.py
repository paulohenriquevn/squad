#!/usr/bin/env python3
"""Extract the acceptance criteria a released milestone must satisfy in the live system.

The criteria are NOT invented by this cycle. They are the milestone's own
`**Definition of done (all must hold):**` bullets in `ROADMAP.md` — the
user-facing promise written at roadmap time, and exactly what the `[x]`
checkbox claims once flipped. Deriving them anywhere else would let the
acceptance run grade itself against a target it chose after seeing the result.

Emits JSON on stdout so the verdict step consumes structured criteria rather
than re-parsing prose:

    {"milestone_id": "M2", "milestone_name": "Streaming",
     "criteria": [{"id": "AC1", "source": "roadmap-dod", "text": "..."}]}

Usage:
    python3 extract_acceptance_criteria.py --roadmap ROADMAP.md --milestone M2

Exit codes:
    0 — criteria written to stdout
    1 — gate violation (milestone absent, DoD section absent or empty)
    2 — file not found / bad argument
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "roadmap.py").is_file():
        sys.path.insert(0, str(_up))
        break
# Below the bootstrap: `squad` is importable only after sys.path is extended.
from squad.roadmap import (  # noqa: E402 — post-bootstrap import
    MILESTONE_ID_RE as _MILESTONE_ID_RE,
    Status,
    find as _find_milestone,
    has_dod_heading as _has_dod_heading,
    parse as _parse_roadmap,
)

# The header, the DoD heading and the bullet shape used to live here, in a third copy
# that disagreed with the other two about `[-]`. `squad/roadmap.py` owns them now —
# `tests/test_one_reader_of_the_roadmap.py` records what the disagreement cost.


class GateViolation(Exception):
    """A hard gate refused the extraction."""


def _milestone_block(roadmap_text: str, milestone_id: str) -> tuple[str, str]:
    """Return (milestone_name, block_text) for the requested milestone."""
    milestone = _find_milestone(roadmap_text, milestone_id)
    if milestone is not None and milestone.status is not Status.CANCELLED:
        # `[x]` is read, deliberately. Extraction is not the pre-condition check — the
        # bullet's state is not the verdict, and `test_it_reads_the_definition_of_done_
        # of_an_already_released_milestone` holds that. Whether the checkbox is still
        # open is `cycle-acceptance.md` § Pre-conditions, upstream of here.
        return milestone.name, milestone.body

    if milestone is not None:
        # Named for what it IS. A cancelled milestone was unmatchable by this script's
        # private header pattern, so it came back as "Milestones present: (none)" over
        # a file holding it — sending a reader to look for a section sitting right
        # there. A cancelled milestone has no live promise to exercise.
        raise GateViolation(
            f"{milestone_id} is cancelled (`[-]`) and has no promise left to validate. "
            f"Reopen it to `[ ]` first if the work resumed."
        )

    known = ", ".join(m.id for m in _parse_roadmap(roadmap_text)) or "(none)"
    raise GateViolation(
        f"{milestone_id} is not in the roadmap. Milestones present: {known}."
    )


def extract(roadmap_text: str, milestone_id: str) -> dict[str, object]:
    """Pull the milestone's Definition-of-done bullets as acceptance criteria."""
    if not _MILESTONE_ID_RE.match(milestone_id):
        raise GateViolation(f"invalid milestone id {milestone_id!r} — expected M<N>.")

    name, block = _milestone_block(roadmap_text, milestone_id)

    if not _has_dod_heading(block):
        raise GateViolation(
            f"{milestone_id} has no `**Definition of done:**` section. "
            "Acceptance has nothing to validate against — the milestone's promise was never written. "
            "Add it to ROADMAP.md before releasing."
        )

    bullets = [text.strip() for text in _find_milestone(roadmap_text, milestone_id).dod]
    if not bullets:
        raise GateViolation(
            f"{milestone_id} declares a Definition of done with no `- [ ]` bullets. "
            "An empty promise cannot be accepted or rejected. Each bullet needs the "
            "checkbox:\n\n"
            "    **Definition of done (all must hold):**\n"
            "    - [ ] one user-visible promise, exercisable against the release\n"
        )

    return {
        "milestone_id": milestone_id,
        "milestone_name": name,
        "criteria": [
            {"id": f"AC{index}", "source": "roadmap-dod", "text": text}
            for index, text in enumerate(bullets, start=1)
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roadmap", type=Path, default=Path("ROADMAP.md"))
    parser.add_argument("--milestone", required=True, help="Milestone id, e.g. M2.")
    args = parser.parse_args()

    if not args.roadmap.exists():
        print(f"file not found: {args.roadmap}", file=sys.stderr)
        return 2

    try:
        payload = extract(args.roadmap.read_text(encoding="utf-8"), args.milestone)
    except GateViolation as exc:
        print(f"NOT_VALIDATED cycle-acceptance: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
