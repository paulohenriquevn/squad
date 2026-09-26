"""Re-export of the one spec-smell detector, so this skill's scripts keep their import.

The implementation moved to `squad/spec_smells.py`. It existed three times — here,
``plan-confidence` and `discover-plan-confidence`` — and the three syntax trees differed in **four lines of 89, all of them the
name of one parameter**. Each copy said "same algorithm" in its own header, and nothing
made that true; a smell fixed in one scorer left the other two detecting the old shape.

Same move `_rubric_loader.py` made when it became `squad/rubric.py`. What stays local is
the RUBRIC this skill reads — `rubric-opportunity.md` — because the categories, patterns and penalties
are the skill's. Only the scan is shared.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
for _up in _HERE.parents:
    if (_up / "squad" / "spec_smells.py").is_file():
        sys.path.insert(0, str(_up))
        break

# Import below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` is importable only after sys.path is extended.
from squad.spec_smells import (  # noqa: E402 — post-bootstrap import
    CONTEXT_WINDOW,
    SmellHit,
    SmellReport,
    check_spec_smells,
)

__all__ = ["check_spec_smells", "SmellReport", "SmellHit", "CONTEXT_WINDOW"]
