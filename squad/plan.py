"""The active plan: which one it is, what it promises, and whether it was altered.

Three hooks need this — `sessionstart-context` announces it, `precompact-preserve`
snapshots it, `userpromptsubmit-inject` points at it every turn. They had three
copies of the same resolution, which is duplicated KNOWLEDGE rather than similar
code: change how a plan is pinned and all three must move together or two of them
start naming a different plan than the third.
"""
from __future__ import annotations

import hashlib
import re

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap
from dataclasses import dataclass
from pathlib import Path
from pathlib import Path as _Path_bootstrap

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
from squad.paths import (  # noqa: E402
    ATTESTATIONS,
    active_plan_pointer,
    write_records_dir,
    write_state_dir,
)

#: A pointer file is data from disk, and a slug is used to build a path. Anything
#: outside this shape is refused rather than joined onto `records/plans/`.
_SLUG_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class ActivePlan:
    path: Path
    slug: str
    #: `pinned` when `.active_plan` named it, `mtime` when it was the newest.
    #: The reader is owed the difference: pinned is a decision, newest is a guess
    #: that is usually right.
    how: str


def _project_of(eco: Path) -> Path:
    """The project that owns this ecosystem directory.

    `eco` is where the KIT is — `<project>/.claude/` in a plugin install, the repo root
    in the standalone kit. The write root hangs off the PROJECT, so joining it to `eco`
    would produce `.claude/.squad/records/` and hide every plan from the hooks that
    read them. Caught by `squad/tests/test_plan.py` the moment the roots centralised.
    """
    return eco.parent if eco.name == ".claude" else eco


def resolve(eco: Path) -> ActivePlan | None:
    pointer = active_plan_pointer(_project_of(eco))
    if pointer.is_file():
        slug = pointer.read_text(encoding="utf-8", errors="replace").strip()
        candidate = write_records_dir(_project_of(eco), "plans") / f"{slug}-plan.md"
        if slug and _SLUG_RE.match(slug) and candidate.is_file():
            return ActivePlan(candidate, slug, "pinned")

    try:
        plans = sorted(write_records_dir(_project_of(eco), "plans").glob("*-plan.md"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return None
    if not plans:
        return None
    return ActivePlan(plans[0], plans[0].name.removesuffix("-plan.md"), "mtime")


def goal_line(plan_path: Path) -> str | None:
    """The first blockquote under `## Goal`, which is where a plan states it."""
    try:
        text = plan_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    in_goal = False
    for line in text.splitlines():
        if line.startswith("## Goal"):
            in_goal = True
            continue
        if in_goal:
            if line.startswith("> "):
                return line
            if line.startswith("## "):
                return None
    return None


@dataclass(frozen=True)
class Attestation:
    expected: str | None
    actual: str | None

    @property
    def tampered(self) -> bool:
        """Only a MISMATCH is tampering.

        No attestation means nobody approved these contents yet, which is a
        different state from approved-and-since-edited. Treating the two alike
        would either cry wolf on every unattested plan or, worse, let an edited
        one through because its attestation was missing.
        """
        return bool(self.expected and self.actual and self.expected != self.actual)


def attestation(eco: Path, plan: ActivePlan) -> Attestation:
    record = write_state_dir(_project_of(eco), ATTESTATIONS) / f"{plan.slug}.sha256"
    expected = None
    if record.is_file():
        expected = record.read_text(encoding="utf-8", errors="replace").strip() or None
    actual = None
    if expected:
        try:
            actual = hashlib.sha256(plan.path.read_bytes()).hexdigest()
        except OSError:
            actual = None
    return Attestation(expected, actual)
