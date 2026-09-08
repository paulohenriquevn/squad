"""Where the kit ends and the project begins — asked once, by both guards.

Two hooks enforce this boundary and they used to know it in one place only.
`boundary-check` refused `Edit`/`Write` into an installed kit; `validate-command`
refused shell writes into `study-material/` and knew nothing about the kit. So
`sed -i` reached the file `Edit` had just been refused, which is the boundary
holding against the careful tool and not against the quick one.

Keeping the answer here rather than in either hook is the rule the kit already
learned twice: a rule living in one file and missing from another is how the gap
reopens (`squad/plan.py`, `_credential_globs`). The two hooks now differ in what
they DO about a violation — one denies a tool call, the other refuses a command —
and not in where they think the line is.
"""
from __future__ import annotations

import re
from pathlib import Path

from .layout import Layout

#: Paths inside an installed kit that belong to the PROJECT, not the kit. A
#: consumer tunes these and the installer preserves them across an update.
PROJECT_OWNED = (
    re.compile(r"^rules/[^/]+\.txt$"),
    re.compile(r"^agents/"),
    re.compile(r"^records/"),
    re.compile(r"^settings\.json$"),
    re.compile(r"^\.kit-manifest\.txt$"),
    re.compile(r"^\.install-backups/"),
)


def is_project_owned(rel: str, kit_dir: Path) -> bool:
    """Is this kit-relative path the consumer's to change?"""
    if any(pattern.search(rel) for pattern in PROJECT_OWNED):
        return True
    # A skill the install manifest does not claim is the project's own, and the
    # kit has no standing to call it read-only.
    if rel.startswith("skills/"):
        manifest = kit_dir / ".kit-manifest.txt"
        if manifest.is_file():
            claimed = {
                line.split("#", 1)[0].strip()
                for line in manifest.read_text(encoding="utf-8-sig",
                                               errors="replace").splitlines()
            }
            return f"skills/{rel.split('/')[1]}" not in claimed
    return False


def kit_relative(target: Path, layout: Layout) -> str | None:
    """This path's location inside the kit, or `None` when it is outside it.

    `None` covers three different situations that need the same answer — the path
    is the project's, the kit is this repository itself, or the path does not
    resolve — because in all three the kit boundary has nothing to say.
    """
    if layout.kind == "standalone":
        return None  # the kit's own repository: these files ARE the work
    if not target.is_absolute():
        target = layout.project_dir / target
    try:
        return str(target.resolve().relative_to(layout.kit_dir.resolve()))
    except (ValueError, OSError):
        return None


def violation(target: Path, layout: Layout) -> str | None:
    """The refusal for writing to `target`, or `None` when the write is fine."""
    rel = kit_relative(target, layout)
    if rel is None or is_project_owned(rel, layout.kit_dir):
        return None
    return (
        f"BOUNDARY VIOLATION: {rel} belongs to the installed Squad kit, which is "
        f"read-only here. A fix written inside an installed kit protects exactly "
        f"one machine and is erased by the next install. Send it to the kit's own "
        f"repository instead. Project-owned paths under the same tree stay "
        f"writable: rules/*.txt (config), agents/ (your domain specialists), "
        f"records/ (cycle output) and settings.json."
    )
