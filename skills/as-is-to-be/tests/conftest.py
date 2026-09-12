"""Put this skill's scripts, and the ones it reuses, on the path."""
from __future__ import annotations

import sys
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(SKILL.parent / "backlog-approve" / "scripts"))
