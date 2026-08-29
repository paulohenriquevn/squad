"""Measurement-target checker for /discover-plan measurement plans (M2 deterministic).

Replaces the ancestor `check_reference_citations.py`, which verified citations into
`records/references/` -- the prior-art study zone this cycle retired.

A measurement plan names WHAT IT WILL MEASURE, and that is the thing to verify before
anyone spends time measuring. Two target classes:

  1. Path targets    `dir/` or `dir/file.ext` -- resolved on disk.
  2. Live targets    an https:// URL -- checked against `rules/live-target.txt`.

The distinction from the opportunity-side checker is deliberate. There, evidence is
`file:line` and the line must exist, because a measurement already happened. Here the
plan points at what it INTENDS to open, so a directory is a legitimate target and no
line number is expected yet.

A plan that names a path nobody can open is a plan that will produce fabricated
evidence -- caught before the measurement rather than after.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

TARGETS_HEADER_RE = re.compile(r"^##\s+Measurement\s+Questions\s*$", re.MULTILINE | re.IGNORECASE)
# Backticked path: `theo-lens/src/` or `theo-lens/src/trace.ts`. Requires a slash so
# that prose words in backticks are not mistaken for targets.
# `@` belongs inside a target, not outside it. The previous class excluded it, so a scoped npm
# specifier like `@theokit/sdk/server/auth` never matched at all — and passed the gate by ACCIDENT
# while its unscoped sibling `theokit/server/plugins` was scored `fabricated_target`. Two shapes of
# the same thing, treated oppositely, for no reason anyone chose.
PATH_TARGET_RE = re.compile(r"`((?:@?\.?[A-Za-z0-9_.\-]+/)+[A-Za-z0-9_.\-]*)`")
URL_TARGET_RE = re.compile(r"https?://[A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.\-/]*)?")
BLOCKED_MARKER_RE = re.compile(r"<!--\s*BLOCKED:.*?-->", re.IGNORECASE | re.DOTALL)
WORD_RE = re.compile(r"\b\w+\b")


def _find_project_root(start: Path) -> Path:
    current = start.resolve().parent if start.is_file() else start.resolve()
    while current != current.parent:
        if (current / ".claude").exists() or (current / ".git").exists():
            return current
        current = current.parent
    return start.resolve().parent if start.is_file() else start.resolve()


def _target_exists(project_root: Path, target: str) -> bool:
    """Does this path exist, in whichever layout the consumer installed?

    Tried at the project root first, then under `.claude/`. This file already
    resolved `live-target.txt` that way twenty lines above; the measurement-target
    check did not, so a plan citing a kit path was called unresolvable in every
    plugin install — a rule stated once and implemented on one of two paths, which
    is the shape this kit keeps measuring.

    Widening WHERE a target may resolve does not weaken WHETHER it resolves: a
    path nobody wrote is still `path_not_found`.
    """
    return (project_root / target).exists() or (project_root / ".claude" / target).exists()


def _resolves_as_module(project_root: Path, target: str) -> bool:
    """Does `target` name an installed npm module rather than a repo path?

    `theokit/server/plugins` and `@theokit/sdk/server/auth` are module SPECIFIERS: they resolve
    through `node_modules`, not through the repo tree, and they have no extension. Resolving them
    against the project root fails, which used to fire `fabricated_target` — a hard cap — on a
    citation that was correct.

    The distinction is made by RESOLUTION, deliberately, and never by a list of known package
    names: a list needs maintaining, is wrong the moment a consumer adds a dependency, and would
    bake one repository's packages into a kit that others install.

    Only the package part is resolved, not the subpath. A subpath is declared by the package's own
    `exports` map, which this checker has no business parsing — and a plan citing a real package
    with a wrong subpath is a different mistake than citing a package that does not exist.

    pnpm is why the store is walked: it nests the real package under
    `node_modules/.pnpm/<name>@<version>/node_modules/<name>`, so a top-level-only check misses
    every package in a pnpm workspace — which is all of them.
    """
    parts = target.strip("/").split("/")
    if not parts:
        return False
    package = "/".join(parts[:2]) if parts[0].startswith("@") and len(parts) > 1 else parts[0]

    current = project_root.resolve()
    while True:
        modules = current / "node_modules"
        if modules.is_dir():
            if (modules / package).exists():
                return True
            store = modules / ".pnpm"
            if store.is_dir():
                for entry in store.iterdir():
                    if (entry / "node_modules" / package).exists():
                        return True
        if current == current.parent:
            return False
        current = current.parent


def _declared_live_targets(project_root: Path) -> set[str]:
    """Hosts declared in rules/live-target.txt.

    A plan naming a live URL that no domain declares is planning a probe the cycle
    refuses to run (`cycle-discover.md`, gate G-L). Catching it here means the refusal
    lands while the plan is cheap to change.
    """
    for candidate in (
        project_root / "rules" / "live-target.txt",
        project_root / ".claude" / "rules" / "live-target.txt",
    ):
        if candidate.is_file():
            return {
                m.group(1)
                for m in re.finditer(
                    r"^\s*target\s*=\s*https?://([A-Za-z0-9_.\-]+)",
                    candidate.read_text(encoding="utf-8-sig"),
                    re.MULTILINE,
                )
            }
    return set()


def _is_explicitly_blocked(raw: str, match_end: int) -> bool:
    return bool(BLOCKED_MARKER_RE.search(raw[match_end : match_end + 80]))


def check_measurement_targets(plan_path: Path) -> dict[str, Any]:
    raw = plan_path.read_text(encoding="utf-8-sig")
    project_root = _find_project_root(plan_path)
    declared_hosts = _declared_live_targets(project_root)

    verified: set[str] = set()
    fabricated: dict[str, str] = {}
    blocked: set[str] = set()

    for match in PATH_TARGET_RE.finditer(raw):
        target = match.group(1)
        if _is_explicitly_blocked(raw, match.end()):
            blocked.add(target)
            continue
        if _target_exists(project_root, target) or _resolves_as_module(project_root, target):
            verified.add(target)
        else:
            fabricated[target] = "path_not_found"

    undeclared_hosts: list[str] = []
    live_targets: set[str] = set()
    for match in URL_TARGET_RE.finditer(raw):
        url = match.group(0)
        host = re.sub(r"^https?://", "", url).split("/")[0]
        live_targets.add(url)
        if declared_hosts and host not in declared_hosts:
            undeclared_hosts.append(host)

    total = len(verified) + len(fabricated)
    word_count = len(WORD_RE.findall(raw))
    density = ((total + len(live_targets)) * 200 / word_count) if word_count else 0.0

    contributors: list[str] = []
    if verified:
        contributors.append(f"{len(verified)} resolvable path target(s)")
    if live_targets and not undeclared_hosts:
        contributors.append(f"{len(live_targets)} live target(s), all declared")
    if blocked:
        contributors.append(f"{len(blocked)} explicitly BLOCKED target(s) (honest gaps)")

    detractors = [f"Unresolvable target: {t} ({why})" for t, why in sorted(fabricated.items())[:3]]
    detractors.extend(
        f"Live host not declared in rules/live-target.txt: {h}"
        for h in sorted(set(undeclared_hosts))[:2]
    )

    return {
        "total": total,
        "verified": len(verified),
        "fabricated": len(fabricated),
        "fabricated_targets": dict(sorted(fabricated.items())[:10]),
        "explicitly_blocked": len(blocked),
        "blocked_targets": sorted(blocked)[:10],
        "live_targets": sorted(live_targets)[:10],
        "undeclared_live_hosts": sorted(set(undeclared_hosts)),
        "word_count": word_count,
        "target_density_per_200w": round(density, 2),
        "contributors": contributors[:3],
        "detractors": detractors[:3],
    }
