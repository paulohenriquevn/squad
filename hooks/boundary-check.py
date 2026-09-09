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

WHERE THE LINE IS LIVES IN `squad.boundaries`
----------------------------------------------
This hook decides what to DO about a violation; it does not decide where the
boundary runs. `validate-command` refuses the same writes arriving through the
shell, and while each kept its own answer the boundary held against `Edit` and
not against `sed -i`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from squad import PreToolUseContext, create_context
from squad.boundaries import violation
from squad.layout import resolve

#: `rules/reference-provenance.md` § 1. `records/references/` was retired on
#: 2026-09-01 with the practice that filled it; the rule records what that costs.
ZONE_RE = re.compile(r"(^|/)(\.claude/)?study-material/")

ZONE_REASON = (
    "BOUNDARY VIOLATION: study-material/ holds third-party material we depend on "
    "and is read-only. Never edit or create files there — a literal copy carries "
    "its licence into this repository. Capture findings in "
    "records/discoveries/blueprints/."
)


def main() -> None:
    c = create_context(PreToolUseContext)
    raw = c.tool_input.get("file_path") or c.tool_input.get("filePath")
    if not raw:
        return

    if ZONE_RE.search(raw):
        c.output.exit_block(ZONE_REASON)

    layout = resolve()
    if layout is None:
        return  # no kit here: nothing of ours to protect

    reason = violation(Path(raw), layout)
    if reason:
        c.output.exit_block(reason)


if __name__ == "__main__":
    main()
