"""Which directory a verb should look in — the kit's, or the project's.

In this repository those are the same directory, so a CLI that confuses them works
perfectly here and breaks on every consumer. That is the exact shape this kit keeps
finding: `route_domain.py` resolved its root from its own file and read the kit's empty
table instead of the consumer's (kit#37), and `attest_plan.sh` and `squad/plan.py`
resolved two different roots, so plan tamper detection was inert (kit#36).

The split that matters for `sq`:

    kit      where the MECHANISMS are — `mechanisms/`, `skills/`, `hooks/`.
             Under a copy install this is `<project>/.claude`.
    project  where the PROJECT is — `.github/workflows/`, the git repository.
             Under a copy install this is `<project>`.

`squad.layout.resolve()` already computes this and the hooks already use it. This is a
thin adapter so each verb states which of the two it means, instead of every verb
deriving `parents[2]` and being right only in the standalone case.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from squad.layout import resolve

#: The name of a kit's directory inside a consumer, for the fallback below.
_INSTALLED_DIR = ".claude"


@dataclass(frozen=True)
class Roots:
    """The two directories a verb can mean, never conflated."""

    kit: Path
    project: Path

    def workflow(self) -> Path | None:
        """The CI workflow, or None — never a path that does not exist.

        Returning a guess would point a gate at a tree that is not there, and the
        caller would report on nothing while looking like it reported on something.
        """
        candidate = self.project / ".github" / "workflows" / "ci.yml"
        return candidate if candidate.is_file() else None


def resolve_roots(kit_dir: Path) -> Roots:
    """Both roots, given where the kit's code is.

    The structural rule comes FIRST and is unambiguous: a kit sitting in
    `<project>/.claude` means the project is its parent. Asking
    `squad.layout.resolve(project_dir=kit_dir)` first does not work — handed `.claude`
    it finds a kit right there and reports both roots as the same directory, which is
    the conflation this module exists to prevent.

    `resolve()` is still consulted for the PLUGIN case, where `$CLAUDE_PLUGIN_ROOT`
    puts the kit outside the project entirely and no path walk from the kit could find
    the project. It is asked without a `project_dir` so it reads the environment, and
    only its answer for `project_dir` is used.
    """
    if kit_dir.name == _INSTALLED_DIR:
        return Roots(kit=kit_dir, project=kit_dir.parent)

    layout = resolve(warn=False)
    if layout is not None and layout.kind == "plugin" and layout.kit_dir == kit_dir:
        return Roots(kit=kit_dir, project=layout.project_dir)

    # Standalone: the kit IS the project, and this is the case in this repository.
    return Roots(kit=kit_dir, project=kit_dir)
