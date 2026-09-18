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

WHAT THIS BOUNDARY IS WORTH: A CONVENTION, NOT A GUARANTEE
-----------------------------------------------------------
This hook reads `tool_input.file_path`, so its reach is exactly the tools that
carry one — `Write`, `Edit`, `NotebookEdit`. A Python heredoc calling
`Path.write_text` reaches the same bytes and this hook never runs. Measured on
2026-09-18: a session edited a file inside an installed kit through a heredoc and
nothing stopped it.

Widening the pattern is not the answer, and `validate-command.py` already made
the argument for the credential deny list one hook over:

    This closes the common door. It does NOT make the deny list a sandbox, and
    saying otherwise would make it the thing it replaces — a guard that reads as
    protection and is not. A determined session reaches the same bytes through
    `python3 -c`, a heredoc, an editor, or a path this pattern does not spell.
    What it stops is the accident and the habit, which is most of what happens.

Chasing `write_text` would add `open(..., "w")`, `shutil.copy`, `tee`, `dd` and a
truncating redirect — each one a door and none of them the last. So the boundary
is stated the way `rules/reference-provenance.md § 6` states its own layers:

    guarantee    nothing. No layer here prevents a write; the kit is not a sandbox
                 and a session with a shell can reach any byte in the tree.
    convention   `Write` / `Edit` / `NotebookEdit` are refused at the boundary, and
                 `validate-command` refuses the shell forms it can spell.

A reader relying on more than that is relying on something nobody built. What the
two hooks together buy is that crossing the boundary has to be DELIBERATE — which
is worth having, and is not the same as impossible.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap
from pathlib import Path as _Path_bootstrap

from squad import PreToolUseContext, create_context
from squad.boundaries import violation
from squad.layout import resolve

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.paths import DATA_DIRNAME, RECORDS  # noqa: E402 — post-bootstrap import

#: `rules/reference-provenance.md` § 1. `records/references/` was retired on
#: 2026-09-01 with the practice that filled it; the rule records what that costs.
ZONE_RE = re.compile(r"(^|/)(\.claude/)?study-material/")

ZONE_REASON = (
    "BOUNDARY VIOLATION: study-material/ holds third-party material we depend on "
    "and is read-only. Never edit or create files there — a literal copy carries "
    "its licence into this repository. Capture findings in "
    f"{DATA_DIRNAME}/{RECORDS}/discoveries/blueprints/."
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
