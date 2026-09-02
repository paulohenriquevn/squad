#!/usr/bin/env python3
"""SessionStart — put the chain, the roles and the current state in front of the agent.

A fresh session knows nothing about where the work stands. This injects the small
set of facts every later decision rests on: which branch, whether the tree is
dirty, which plan is active, and the shape of the cycle it is inside.

The map itself lives in `rules/squad-map.md`, and this points at it rather than
restating it — two copies of one map drift, and the copy injected at SessionStart
is the one nobody notices going stale. `check_squad_map.py` compares that file to
the directory; nothing could compare a here-document to anything.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from squad import SessionStartContext, create_context  # noqa: E402
from squad.layout import Layout, resolve  # noqa: E402
from squad.plan import resolve as resolve_plan  # noqa: E402


def _git(*args: str) -> str | None:
    try:
        done = subprocess.run(["git", *args], capture_output=True, text=True,  # noqa: PLW1510
                              timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def git_line() -> str | None:
    if not Path(".git").is_dir():
        return None
    branch = _git("branch", "--show-current") or "(detached)"
    porcelain = _git("status", "--porcelain")
    if porcelain is None:
        return None
    dirty = len([ln for ln in porcelain.splitlines() if ln.strip()])
    ahead = _git("rev-list", "--count", "@{upstream}..HEAD") or "0"
    state = "clean" if dirty == 0 else f"{dirty} uncommitted files"
    return f"Git: branch={branch} ({state}, {ahead} ahead of upstream)"


def plan_line(eco: Path) -> str | None:
    """The active plan, saying WHICH way it was found — pinned is a decision,
    newest-by-mtime is a guess that happens to be usually right."""
    active = resolve_plan(eco)
    if active is None:
        return None
    if active.how == "pinned":
        return (f"Active plan: {active.slug} ({active.path}) "
                f"— pinned via {eco}/.active_plan")
    return f"Active plan: {active.slug} (resolved by mtime — set {eco}/.active_plan to pin)"


def loop_line(eco: Path) -> str | None:
    marker = eco / "ralph-loop.local.md"
    if not marker.is_file():
        return None
    fields = {}
    for line in marker.read_text(encoding="utf-8", errors="replace").splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    if fields.get("active") != "true":
        return None
    return (f"ralph-loop: ACTIVE (iter {fields.get('iteration', '?')}) — if stale "
            f"(>24h, no progress), cancel via /ralph-loop:cancel-ralph or delete the file")


def chain_lines(eco: Path) -> list[str]:
    return [
        "",
        f"SQUAD — the chain, and who decides (full map: {eco}/rules/squad-map.md)",
        "  BRAINSTORM -> BACKLOG -> DISCOVER -> PLAN -> IMPLEMENT -> CODE-QUALITY -> "
        "REVIEW -> RELEASE -> ACCEPTANCE",
        "  BRAINSTORM is the ONLY phase that requires a person; everything after it "
        "runs unattended, merge included.",
        "  ITEM_KILLED ends the chain and is a SUCCESSFUL outcome.",
        "  Roles: kairos=what work exists & in what order | iris=what the user "
        "experiences | daedalus=one item's technical path | hermes=flow & halts",
        "  Domain specialists are the PROJECT's, never the kit's. Reach them with "
        "mechanisms/cycle/route_domain.py <repo>;",
        "    exit 3 (BROKEN ROUTE) means the domain names a specialist nobody wrote "
        "— stop, do NOT stand in for them.",
        "  No verdict is asserted in prose: a script computes it. Read the cycle rule "
        "before running a phase.",
        "",
        "Unbreakable principles apply (see ~/.claude/CLAUDE.md): 95% confidence, "
        "TDD-first, no commits to main, CHANGELOG discipline.",
    ]


def build_context(layout: Layout) -> str:
    lines = [line for line in (git_line(), plan_line(layout.eco), loop_line(layout.eco))
             if line]
    lines.extend(chain_lines(layout.eco))
    return "\n".join(lines) + "\n"


def main() -> None:
    c = create_context(SessionStartContext)
    layout = resolve()
    if layout is None:
        # No kit here, or a broken install that already said so. Injecting the
        # chain into a project that does not run it would be noise.
        return
    c.output.add_context(build_context(layout))


if __name__ == "__main__":
    main()
