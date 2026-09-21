"""`<!-- BLOCKED: … -->` — what it excuses, and how close it has to be.

WHY THIS EXISTS
===============
The marker says a pointer or a measurement target could not be resolved, and that the
author knows: a documented gap rather than a fabrication. Three modules read it and each
carried its own copy of the rule — `check_evidence_pointers`, `check_measurement_targets`
(a character-for-character copy of the same helper) and `apply_opportunity_fixes` (the same window,
inlined).

The rule was "within ~80 characters after the match", and that window crosses newlines.
A Corner 1 is written as a list, so a marker on one item absolved the item ABOVE it.
Measured 2026-09-21:

    src/real/thing.ts:3  alone                       -> verified=1
    the same, with a BLOCKED item on the next line   -> verified=0, blocked=2
    the same, with 100 chars of prose between them   -> verified=1, blocked=1

It fires in both directions: a verified pointer demoted to a gap, and an unmarked
fabrication absolved by its neighbour. The fix landed in one of the three, which is
exactly how a convention with no owner drifts — so the convention has an owner now.

THE RULE
========
**The marker excuses what is on its own line.** That is the only proximity a writer can
hold in their head, and the only one that cannot leak into the entry above.
"""
from __future__ import annotations

import re

#: `<!-- BLOCKED: reason -->`, in any case, spanning lines if the reason wraps.
BLOCKED_MARKER_RE = re.compile(r"<!--\s*BLOCKED:.*?-->", re.IGNORECASE | re.DOTALL)


def is_blocked_at(text: str, match_end: int) -> bool:
    """Does a BLOCKED marker follow `text[:match_end]` on the SAME line?

    `match_end` is the offset just past the pointer or target being judged.
    """
    line_end = text.find("\n", match_end)
    rest_of_line = text[match_end:] if line_end == -1 else text[match_end:line_end]
    return bool(BLOCKED_MARKER_RE.search(rest_of_line))


def strip_markers(text: str) -> str:
    """`text` with every BLOCKED marker removed — for callers that scan the prose
    around a marker and must not match the marker itself."""
    return BLOCKED_MARKER_RE.sub("", text)
