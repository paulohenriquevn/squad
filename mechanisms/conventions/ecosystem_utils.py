"""Shared ecosystem layout detection utilities.

Provides canonical functions for locating the Cycle ecosystem directory
across the three supported layouts:
  1. Standalone — the plan/ repo itself (skills/ + rules/ + hooks/ at root)
  2. User config — installed under <project>/.claude/
  3. Plugin install — installed under <project>/.claude/plugins/cycle/

Every script and test that needs to find the ecosystem directory should
import from here instead of duplicating the detection logic.
"""
from __future__ import annotations

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap
from pathlib import Path, Path as _Path_bootstrap

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break


def is_ecosystem_layout(d: Path) -> bool:
    """A directory is an ecosystem layout if it has skills/ + rules/ + hooks/ directly."""
    return (d / "skills").is_dir() and (d / "rules").is_dir() and (d / "hooks").is_dir()


def find_ecosystem_dir(start: Path | None = None, *, require: bool = True) -> Path | None:
    """Locate the ecosystem directory by probing upward from *start*.

    At each level (from *start* upward, max 20 levels):
      1. Standalone — ``current/`` itself has ``skills/ + rules/ + hooks/``.
      2. User config — ``current/.claude/`` has them.
      3. Plugin install — ``current/.claude/plugins/cycle/`` has them.

    Parameters
    ----------
    start : Path or None
        Starting directory for the search.  Defaults to ``Path.cwd()``.
    require : bool
        If True (default), raises ``FileNotFoundError`` when no layout is found.
        If False, returns ``None`` instead.

    Returns
    -------
    Path or None
        The ecosystem directory, or None if *require* is False and not found.
    """
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent

    for _ in range(20):
        if is_ecosystem_layout(current):
            return current
        claude_sub = current / ".claude"
        if is_ecosystem_layout(claude_sub):
            return claude_sub
        plugin_sub = current / ".claude" / "plugins" / "cycle"
        if is_ecosystem_layout(plugin_sub):
            return plugin_sub
        if current == current.parent:
            break
        current = current.parent

    if require:
        raise FileNotFoundError(
            "Ecosystem directory not found. Expected one of: "
            "<cwd>/{skills,rules,hooks}, <cwd>/.claude/{skills,rules,hooks}, "
            "or <cwd>/.claude/plugins/cycle/{skills,rules,hooks}."
        )
    return None


def resolve_ecosystem_dir(project_dir: Path) -> Path | None:
    """Find ecosystem directory anchored at *project_dir* (no upward walk).

    Probes three candidate locations under *project_dir* only:
      1. ``project_dir/`` itself
      2. ``project_dir/.claude/``
      3. ``project_dir/.claude/plugins/cycle/``

    Returns the first candidate holding ``skills/ + rules/ + hooks/``. Returns None
    if nothing matches.

    It used to prefer a candidate containing ``records/``, and that signal died when
    the write root moved out: the ecosystem directory holds the installed KIT, and
    everything the system writes now lives at ``<project>/.squad/``. Probing for a
    directory that is no longer there made this resolve one level too high — it
    returned the project instead of ``.claude/``. The kit trees are what "this
    directory is the kit" actually means, and it is the test every hook already uses.
    """
    # `.claude/` FIRST. When both it and the root hold the kit trees, the install is
    # what should win. The test is whether a directory HOLDS the kit trees rather than
    # whether it exists — the same test `cycle_events._holds_the_kit` applies, though
    # NOT the same order: `cycle_events.project_root_for` tries the candidate before
    # `candidate/.claude`, because it is answering a different question (which project
    # is this) and the project is the outer directory either way.
    #
    # This comment used to cite `cycle_events._is_standalone`, a symbol that has never
    # existed in this repository, and to attribute this order to it. A citation that
    # resolves to nothing cannot be checked, and this one was wrong in both halves.
    # The records probe used to break the tie; it moved out, so the order carries it.
    candidates = [
        project_dir / ".claude",
        project_dir,
        project_dir / ".claude" / "plugins" / "cycle",
    ]
    for c in candidates:
        if c.is_dir() and is_ecosystem_layout(c):
            return c
    return None
