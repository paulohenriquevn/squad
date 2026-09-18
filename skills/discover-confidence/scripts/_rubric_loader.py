"""Re-export of the one rubric reader, so this skill's scripts keep their import.

The implementation moved to `squad/rubric.py`. It was byte-identical in three skills
and differed only in a docstring — one of which recorded the copy as a copy. Three
readings of one YAML-in-markdown convention is three places for it to drift, silently.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
for _up in _HERE.parents:
    if (_up / "squad" / "rubric.py").is_file():
        sys.path.insert(0, str(_up))
        break

# Import below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` is importable only after sys.path is extended.
from squad.rubric import load_rubric  # noqa: E402 — post-bootstrap import

__all__ = ["load_rubric"]
