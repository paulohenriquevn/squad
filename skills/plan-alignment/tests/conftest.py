"""The slice's own `sys.path` bootstrap, in the one place every module sees.

`test_needs_split_verdict.py` did `from score_alignment import score_alignment` at
module scope and inserted nothing into `sys.path`. It imported successfully only
because pytest collects `test_alignment_depth.py` first — alphabetical order — and that
module extends the path at import time. Run the file alone and it died on
ModuleNotFoundError, so the slice had a test that passed as a group and failed as a
file. A conftest is where the bootstrap belongs; the per-module copies are harmless
now, and this is what makes any ONE of them runnable.
"""
from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
