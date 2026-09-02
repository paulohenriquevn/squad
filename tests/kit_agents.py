"""Which agents belong to the KIT rather than to a consumer's domains.

Read from the installer that copies them, never restated. Three tests need this list
— the manifest gate, the clean-install gate and the routing gate — and a list written
in four places is the exact shape of the blocking-verdicts defect this repository
already paid for once: two copies of one fact, drifting, each confidently wrong about
the other's case.

Not in `conftest.py` because the repository has two of those, and the root one wins
the import.
"""
from __future__ import annotations

from pathlib import Path

#: The loop in `install.sh` that copies them. If it is renamed, this returns only the
#: README and the three gates tighten rather than loosen — the safe direction.
_MARKER = "for kit_agent in "


def kit_agents() -> set[str]:
    install = Path(__file__).resolve().parents[1] / "mechanisms" / "dist" / "install.sh"
    body = install.read_text(encoding="utf-8")
    if _MARKER not in body:
        return {"README.md"}
    names = body.split(_MARKER, 1)[1].split(";", 1)[0].split()
    return {"README.md", *names}
