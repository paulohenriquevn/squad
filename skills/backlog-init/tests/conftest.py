"""Puts the slice's scripts/ on sys.path, as the other slices do."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
