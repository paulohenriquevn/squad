#!/usr/bin/env python3
"""PreToolUse — refuse writes into the read-only zone and into an installed kit.

Two boundaries, one hook, because both answer the same question about one path:

  the study zone   `study-material/**` holds third-party material. A literal copy
                   carries its licence into this repository, which is a legal
                   problem rather than a stylistic one (`rules/reference-provenance.md`).
  the installed kit  under a copy install the kit sits in a writable directory
                   inside the project, so the project's agent edits it. Those
                   edits protect exactly one machine and the next install erases
                   them — measured in `check_install_drift.py`: twenty-two kit
                   fixes spent weeks inside one consumer's `.claude/`.

The kit boundary does NOT apply in the kit's own repository, which is the one
place those files are meant to be edited.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from squad import PreToolUseContext, create_context  # noqa: E402
from squad.layout import resolve  # noqa: E402

#: `rules/reference-provenance.md` § 1. `records/references/` was retired on
#: 2026-09-01 with the practice that filled it; the rule records what that costs.
ZONE_RE = re.compile(r"(^|/)(\.claude/)?study-material/")

#: Paths inside an installed kit that belong to the PROJECT, not the kit. A
#: consumer tunes these, and the installer preserves them.
PROJECT_OWNED = (
    re.compile(r"^rules/[^/]+\.txt$"),
    re.compile(r"^agents/"),
    re.compile(r"^records/"),
    re.compile(r"^settings\.json$"),
    re.compile(r"^\.kit-manifest\.txt$"),
    re.compile(r"^\.install-backups/"),
)

ZONE_REASON = (
    "BOUNDARY VIOLATION: study-material/ holds third-party material we depend on "
    "and is read-only. Never edit or create files there — a literal copy carries "
    "its licence into this repository. Capture findings in "
    "records/discoveries/blueprints/."
)


def kit_reason(rel: str) -> str:
    return (
        f"BOUNDARY VIOLATION: {rel} belongs to the installed Squad kit, which is "
        f"read-only here. A fix written inside an installed kit protects exactly "
        f"one machine and is erased by the next install. Send it to the kit's own "
        f"repository instead. Project-owned paths under the same tree stay "
        f"writable: rules/*.txt (config), agents/ (your domain specialists), "
        f"records/ (cycle output) and settings.json."
    )


def is_project_owned(rel: str, kit_dir: Path) -> bool:
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


def main() -> None:
    c = create_context(PreToolUseContext)
    raw = c.tool_input.get("file_path") or c.tool_input.get("filePath")
    if not raw:
        return

    if ZONE_RE.search(raw):
        c.output.exit_block(ZONE_REASON)

    layout = resolve()
    if layout is None or layout.kind == "standalone":
        # No kit, or the kit's own repository — where these files ARE the work.
        return

    target = Path(raw)
    if not target.is_absolute():
        target = layout.project_dir / target
    try:
        rel = str(target.resolve().relative_to(layout.kit_dir.resolve()))
    except (ValueError, OSError):
        return  # outside the kit: not this boundary's business

    if is_project_owned(rel, layout.kit_dir):
        return
    c.output.exit_block(kit_reason(rel))


if __name__ == "__main__":
    main()
