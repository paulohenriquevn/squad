"""Where the kit's CODE is, and where the cycle's DATA goes. They are not the same.

This replaced `hooks/environment/detect-layout.sh`, and the distinction it
draws is the whole reason it exists:

  kit_dir  the kit's code (skills/, rules/, hooks/). Read-only for the consumer.
           Under the native plugin layout it lives OUTSIDE the project.
  eco      the cycle's data (records/, .active_plan, .attestations). Always
           inside the project, always writable.

Until 2026-08-26 one path answered for both. That works only while the kit lives
inside the project, and the cost is on record in `check_install_drift.py`:
twenty-two kit fixes spent weeks inside one consumer's gitignored `.claude/` and
nowhere else. A writable kit inside a project gets edited by that project's
agent — not a bug to fix, the design's expected behaviour.

THREE OUTCOMES, AND WHY ONLY ONE OF THEM IS SILENT
---------------------------------------------------
`resolve()` returns a `Layout`, returns `None`, or reports a broken install.

  found          the three trees are there. Work.
  absent (None)  no kit anywhere. A project that does not use this should hear
                 NOTHING — silence is correct, and the hook exits 0.
  broken         `CLAUDE_PLUGIN_ROOT` is set and does not contain the kit. This
                 is NOT the same as "nobody installed it", and treating it as
                 such is a measured failure: on 2026-08-26 two hooks exited 0
                 without a word, so every gate was off while the session looked
                 protected. It warns on stderr and still exits 0, because a
                 corrupt install must not also make the session unusable.

Absent is silent; broken is loud. Neither is the payload-unreadable case, which
blocks — see `squad/__init__.py`.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

#: The three trees that make a directory the kit.
_KIT_TREES = ("skills", "rules", "hooks")


@dataclass(frozen=True)
class Layout:
    kit_dir: Path
    eco: Path
    project_dir: Path
    #: `plugin` · `copy` · `standalone` — which of the three shapes was found.
    kind: str


def roster_path(project_dir: Path | str | None = None) -> Path:
    """Where the panel roster lives, resolved against the KIT, not the project.

    `install.sh` copies `rules/` into `<target>/.claude/`, so in a plugin install
    the roster is at `<project>/.claude/rules/review-panel.txt` and
    `<project>/rules/review-panel.txt` does not exist. A reader resolving against
    the project root finds nothing and has no way to tell that from a project with
    no roster.

    It lives HERE because it has been answered twice and only one of the two was
    right. `convene_panel.default_panel_path()` was fixed, with this reasoning
    written into it; `check_panel_approval.default_panel_path()` carried the same
    NAME and the unfixed body. Measured by a consumer 2026-09-18 on a panel that
    had convened, voted and returned unanimously:

        UNCHECKED: cannot read the roster: .../apps/theoclaw/rules/review-panel.txt

    `UNCHECKED` reaches the opportunity scorer as `ITEM_IN_FLIGHT` — "the panel
    could not convene" — so a panel that ran was indistinguishable from one that
    never did, on every plugin install.

    The standalone branch is the shape where kit and project coincide, which is
    how this repository tests itself.
    """
    layout = resolve(project_dir, warn=False)
    if layout is not None:
        return layout.kit_dir / "rules" / "review-panel.txt"
    root = Path(project_dir) if project_dir else Path.cwd()
    return root / "rules" / "review-panel.txt"


def has_kit(directory: Path) -> bool:
    return all((directory / tree).is_dir() for tree in _KIT_TREES)


def resolve(project_dir: Path | str | None = None, *,
            warn: bool = True) -> Layout | None:
    """Find the kit, or return None when there is none to find.

    `warn` exists for the tests, not for callers: a hook that silences the
    broken-install warning reproduces the exact failure the warning was added
    for.
    """
    root = Path(project_dir or os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
    try:
        root = root.resolve(strict=True)
    except OSError:
        return None

    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        kit = Path(plugin_root)
        if has_kit(kit):
            # The data stays in the project: `.claude/` when it exists, to match
            # the layout copy installs already use; the root otherwise.
            eco = root / ".claude" if (root / ".claude").is_dir() else root
            return Layout(kit_dir=kit, eco=eco, project_dir=root, kind="plugin")
        if warn:
            print(f"[squad] CLAUDE_PLUGIN_ROOT={plugin_root} does not contain "
                  f"{', '.join(t + '/' for t in _KIT_TREES)}.", file=sys.stderr)
            print("[squad] Incomplete install — the gates are NOT active in this session.",
                  file=sys.stderr)
        return None

    if has_kit(root / ".claude"):
        # What install.sh writes. Code and data coincide, as they always did.
        return Layout(kit_dir=root / ".claude", eco=root / ".claude",
                      project_dir=root, kind="copy")
    if has_kit(root):
        # The kit's own repository, opened in Claude Code.
        return Layout(kit_dir=root, eco=root, project_dir=root, kind="standalone")
    return None
