"""Read a rubric's YAML block out of the markdown document that carries it.

WHY THIS EXISTS
===============
`_rubric_loader.py` was byte-identical in three skills — `plan-confidence`,
`discover-confidence` and `discover-plan-confidence` — differing only in a docstring,
one of which said so out loud: "Copied as-is from plan-confidence/scripts/
_rubric_loader.py — same YAML-in-markdown convention."

Three copies of one parse is three places for the convention to drift, and the drift
would be silent: a rubric whose fence the reader cannot find raises `ValueError` here
and would raise it in one skill while the other two carried on. The skills already
import `squad.paths` for the same reason, so this is the place they can all reach.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_FENCE = "```yaml"

#: The bar a rubric score is held to, as a percentage. Stated ONCE, here, for the
#: reason the docstring above gives about the parse: three copies of one convention
#: are three places for it to drift, and the drift is silent.
#:
#: It had three statements and no reuse. Measured 2026-09-19:
#:
#:     skills/_kit-rules/alignment-threshold.md              prose, the reasoning
#:     plan-alignment/scripts/score_alignment.py:80          THRESHOLD = 0.90
#:     brainstorm-pieces/.../score_product_alignment.py:67   FLOOR_PCT = 90.0
#:
#: Not even the same type — a fraction against a percentage — so a change to one
#: could not be made mechanically in the other and nothing would report the
#: disagreement. `cycle-brainstorm.md` G-B4 already claimed this worked: "this
#: cycle reuses them rather than choosing a second number for the same purpose."
#: It did not; the numbers agreed by coincidence.
#:
#: WHAT DID NOT MOVE. `alignment-threshold.md` keeps the REASONING — why 90, and
#: why a score at all. A constant cannot hold an argument and a rule file cannot be
#: imported, so each keeps the half it can carry.
ALIGNMENT_FLOOR_PCT = 90.0

#: The same bar as a ratio, DERIVED rather than written again — the two spellings
#: existed in the two scorers and that is how a fraction and a percentage came to
#: be maintained separately.
ALIGNMENT_FLOOR_RATIO = ALIGNMENT_FLOOR_PCT / 100



def load_rubric(rubric_path: Path) -> dict[str, Any]:
    """Extract the ```yaml block from a rubric `.md` and parse it.

    Raises `ValueError` naming the file when the block is absent or unclosed. Not a
    silent `{}`: a rubric that did not parse is not a rubric with no criteria, and
    every caller here scores against what this returns.
    """
    content = rubric_path.read_text(encoding="utf-8-sig")
    start = content.find(_FENCE)
    if start == -1:
        raise ValueError(f"No {_FENCE} block found in {rubric_path}")
    end = content.find("```", start + len(_FENCE))
    if end == -1:
        raise ValueError(f"Unclosed {_FENCE} block in {rubric_path}")
    parsed: dict[str, Any] = yaml.safe_load(content[start + len(_FENCE):end].strip())
    return parsed
