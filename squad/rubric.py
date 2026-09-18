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
