"""Where D1 runs knip, and through which package manager.

Split from `typescript.py` for the reason `_workspace.py` was: one responsibility, and the
measurements behind it belong next to the code they justify.

WHY NOT `npx --yes knip` FROM THE ROOT
--------------------------------------
Measured 2026-09-24 on two repositories of one ecosystem, same kit, same detector:

    knip declared in the root package.json     exit 0, 32s, valid JSON
    knip declared in packages/ui only (pnpm)   exit 127 — `sh: 1: knip: not found`

and in the second, `cd packages/ui && pnpm exec knip` exited 0 with zero findings. pnpm
does not hoist a member's devDependency to the root, so the root cannot reach the binary,
and `--yes` does not help: the failing run carried it. The detector then read 127 as
`auditor_unavailable_knip`, a soft cap on a tool that was installed and passing.

So the tool is reached where the project DECLARES it — the root when the root declares it,
otherwise every declared workspace member that does — through the runner the lockfile
names. A repository that declares knip nowhere keeps the old invocation from the root, so a
globally installed knip still counts; failing there is honestly `unavailable`.
"""
from __future__ import annotations

import json
from pathlib import Path

from ._workspace import declared, manifests_under, read_workspace_declaration

#: The runner each lockfile implies, checked in this order. `npx --yes` is the fallback
#: that predates this module, kept for a repository with no lockfile or an npm one.
_RUNNERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("pnpm-lock.yaml", ("pnpm", "exec", "knip")),
    ("yarn.lock", ("yarn", "knip")),
)
_NPX = ("npx", "--yes", "knip")

_DEPENDENCY_FIELDS = ("dependencies", "devDependencies", "optionalDependencies")


def knip_command(root: Path) -> list[str]:
    """The knip invocation the repository's own package manager would use."""
    for lockfile, command in _RUNNERS:
        if (root / lockfile).is_file():
            return list(command)
    return list(_NPX)


def declares_knip(manifest: Path) -> bool:
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return isinstance(data, dict) and any(
        isinstance(data.get(field), dict) and "knip" in data[field]
        for field in _DEPENDENCY_FIELDS)


def knip_locations(root: Path) -> list[Path]:
    """The directories that declare knip: the root alone if it does, else its members.

    An empty list means knip is declared nowhere this repository says it owns.
    """
    if declares_knip(root / "package.json"):
        return [root]
    patterns = read_workspace_declaration(root)
    if not patterns:
        return []
    return sorted(
        manifest.parent for manifest in manifests_under(root)
        if manifest.parent != root
        and declared(manifest.parent.relative_to(root).as_posix(), patterns)
        and declares_knip(manifest))
