#!/usr/bin/env python3
"""Session catchup — rebuild context after /clear or fresh session.

Adapted from planning-with-files v2.43.0's session_catchup.py pattern. Reads:

- git status + git diff --stat (what changed since last known commit)
- Active plan file (via the pointer `squad.paths.active_plan_pointer` names, or newest)
- Recent progress.md entries (if convention is in use)
- Recent compaction snapshots
- Active ralph-loop state (if any)

Supports dual-mode layouts:
  - Standalone — the ecosystem repo itself (skills/+rules/+hooks/ direct).
  - Plugin install — <root>/.claude/ or <root>/.claude/plugins/cycle/.

Usage:
  python3 mechanisms/fleet/session_catchup.py [project_dir]

Exit codes:
  0 — catchup report printed (may be empty if no signals found)
  1 — error (project dir doesn't exist, etc.)
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# The family this file lives in, plus `lib/` — the import namespace stayed flat
# when `scripts/` became `mechanisms/<family>/`, so a sibling family is reached
# by path rather than by package.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "conventions"))

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap
from pathlib import Path as _Path_bootstrap

from ecosystem_utils import (
    resolve_ecosystem_dir as _resolve_ecosystem_dir,
)

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.paths import (  # noqa: E402 — post-bootstrap import
    SESSION_STATE,
    SNAPSHOTS,
    active_plan_pointer,
    write_records_dir,
    write_state_dir,
)


@dataclass(frozen=True)
class Ran:
    """What a command produced, and whether it ran at all.

    The same shape `fleet_lander.py` and `issue_lifecycle.py` use in this directory. It
    exists here because `run()` used to return bare stdout and answer `""` for a timeout,
    a missing binary and a non-zero exit alike — and every caller reads an empty string as
    a FACT about the repository. A `git status --short` that could not run printed
    "working tree clean"; an unreadable `git log` printed no recent commits. The catch-up
    exists to rebuild a session's picture of the world, so a silent failure here is a
    confident wrong answer at exactly the moment nobody can check it.
    """

    ok: bool
    out: str
    why: str = ""


def run(cmd: list[str], cwd: Path) -> Ran:
    """Run a command and report BOTH what it printed and whether it worked."""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=10, check=False)
    except subprocess.TimeoutExpired:
        return Ran(False, "", f"`{' '.join(cmd)}` timed out after 10s")
    except FileNotFoundError:
        return Ran(False, "", f"`{cmd[0]}` is not installed here")
    except OSError as exc:
        return Ran(False, "", f"`{' '.join(cmd)}` could not be run: {exc}")
    if result.returncode != 0:
        return Ran(False, result.stdout,
                   f"`{' '.join(cmd)}` exited {result.returncode}: "
                   f"{(result.stderr or '').strip()[:160]}")
    return Ran(True, result.stdout)


def out_or_note(ran: Ran, subject: str) -> str:
    """The output, or the empty string after printing why there is none.

    A caller that prints a conclusion from `ran.out` calls this first, so "could not be
    read" reaches the reader instead of the conclusion an empty string would produce.
    """
    if ran.ok:
        return ran.out
    print(f"{subject}: could not be read — {ran.why}")
    return ""


def section(title: str) -> str:
    return f"\n=== {title} ==="


def _say_git_state(project_dir: Path) -> None:
    """Git state

    Extracted from `main`, which measured cyclomatic complexity 33 across 146 lines
    holding six numbered steps. Pure code movement: the block below is the block that
    was there, printing the same lines in the same order.
    """
    # 1. Git state
    print(section("git state"))
    branch = out_or_note(run(["git", "branch", "--show-current"], project_dir), "branch").strip()
    if branch:
        print(f"branch: {branch}")
    status_ran = run(["git", "status", "--short"], project_dir)
    status = status_ran.out.strip()
    if status:
        lines = status.splitlines()
        print(f"untracked/modified: {len(lines)} files")
        # Show first 20 lines
        for line in lines[:20]:
            print(f"  {line}")
        if len(lines) > 20:
            print(f"  ... ({len(lines) - 20} more)")
    elif status_ran.ok:
        print("working tree clean")
    else:
        print(f"working tree: could not be read — {status_ran.why}")

    diff_stat = out_or_note(run(["git", "diff", "--stat", "HEAD"], project_dir),
                            "git diff --stat HEAD").strip()
    if diff_stat:
        print(section("git diff --stat HEAD (unstaged changes)"))
        # Show last 15 lines (file summary + totals)
        diff_lines = diff_stat.splitlines()
        for line in diff_lines[-15:]:
            print(line)


def _say_recent_commits(project_dir: Path) -> None:
    """Recent commits

    Extracted from `main`, which measured cyclomatic complexity 33 across 146 lines
    holding six numbered steps. Pure code movement: the block below is the block that
    was there, printing the same lines in the same order.
    """
    # 2. Recent commits
    print(section("recent commits"))
    log = out_or_note(run(["git", "log", "--oneline", "-10"], project_dir),
                      "recent commits").strip()
    if log:
        print(log)


def _say_active_plan(project_dir: Path) -> Path | None:
    """Active plan

    Extracted from `main`, which measured cyclomatic complexity 33 across 146 lines
    holding six numbered steps. Pure code movement: the block below is the block that
    was there, printing the same lines in the same order.
    """
    # 3. Active plan
    print(section("active plan"))
    active_plan = None
    # Anchored on the PROJECT, like every other resolution in this function. Passing
    # `ecosystem_dir` is right only in a standalone checkout, where the two coincide;
    # under a plugin install it resolves to `<project>/.claude/.squad/…`, which is the
    # split write root `records-location.md` names and which nothing ever writes to.
    plans_dir = write_records_dir(project_dir, "plans")

    active_pointer = active_plan_pointer(project_dir)
    if active_pointer.is_file():
        slug = active_pointer.read_text().strip()
        candidate = plans_dir / f"{slug}-plan.md"
        if candidate.is_file():
            active_plan = candidate
            # The path RESOLVED, not a hand-written legacy spelling. This printed
            # `{eco_rel}/.active_plan` while `active_plan_pointer` had returned
            # `.squad/active-plan` — so the report named a file the code never
            # looked at, and a reader who went to check found nothing there.
            print(f"pointer: {active_pointer} -> {slug}")

    if active_plan is None and plans_dir.is_dir():
        plans = sorted(plans_dir.glob("*-plan.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if plans:
            active_plan = plans[0]
            print(f"newest: {active_plan.relative_to(project_dir)}")

    if active_plan and active_plan.is_file():
        text = active_plan.read_text()
        # Show version + goal section
        for line in text.splitlines()[:10]:
            if line.startswith(("# Plan:", "> **Version", "## Goal")):
                print(f"  {line}")
        # Find goal text
        in_goal = False
        for line in text.splitlines():
            if line.strip().startswith("## Goal"):
                in_goal = True
                continue
            if in_goal:
                if line.startswith("## "):
                    break
                if line.strip().startswith(">"):
                    print(f"  GOAL: {line.strip().lstrip('>').strip()}")
                    break
    else:
        print("no active plan found")
    return active_plan


def _say_recent_progress(project_dir: Path, active_plan: Path | None) -> None:
    """Recent progress.md entries

    Extracted from `main`, which measured cyclomatic complexity 33 across 146 lines
    holding six numbered steps. Pure code movement: the block below is the block that
    was there, printing the same lines in the same order.
    """
    # 4. Recent progress.md entries
    print(section("recent progress"))
    if active_plan:
        slug = active_plan.name.removesuffix("-plan.md")
        # Resolved exactly as `precompact-preserve.py` WRITES it: `write_state_dir` on
        # the PROJECT, leaf `SESSION_STATE`. This read `write_records_dir` on the
        # ECOSYSTEM with leaf "progress" — a different root, a different leaf and a
        # different anchor, so it reported "no progress file" for every session that had
        # one. The reader and the writer must resolve through the same owner.
        progress_file = write_state_dir(project_dir, SESSION_STATE) / f"{slug}-progress.md"
        if progress_file.is_file():
            lines = progress_file.read_text().splitlines()
            # Show last 20 lines
            print(f"file: {progress_file.relative_to(project_dir)} ({len(lines)} lines)")
            for line in lines[-20:]:
                print(f"  {line}")
        else:
            print(f"no progress file at {progress_file}")


def _say_ralph_state(ecosystem_dir: Path) -> None:
    """Ralph-loop state

    Extracted from `main`, which measured cyclomatic complexity 33 across 146 lines
    holding six numbered steps. Pure code movement: the block below is the block that
    was there, printing the same lines in the same order.
    """
    # 5. Ralph-loop state
    print(section("ralph-loop state"))
    ralph_state = ecosystem_dir / "ralph-loop.local.md"
    if ralph_state.is_file():
        for line in ralph_state.read_text().splitlines()[:10]:
            print(f"  {line}")
    else:
        print("no active ralph-loop")


def _say_compaction_snapshots(project_dir: Path) -> None:
    """Compaction snapshots

    Extracted from `main`, which measured cyclomatic complexity 33 across 146 lines
    holding six numbered steps. Pure code movement: the block below is the block that
    was there, printing the same lines in the same order.
    """
    # 6. Compaction snapshots
    print(section("recent compaction snapshots"))
    # Same correction as the progress file above: `precompact-preserve.py` writes to
    # `write_state_dir(project, SNAPSHOTS)`, and this read `<eco>/.compaction-snapshots/`
    # — a name `squad/paths.py` lists under LEGACY_STATE_NAMES. Every snapshot the kit
    # has written since the move was invisible here, and the catch-up said there were none.
    snap_dir = write_state_dir(project_dir, SNAPSHOTS)
    if snap_dir.is_dir():
        snaps = sorted(snap_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if snaps:
            print(f"found {len(snaps)} snapshot(s); most recent: {snaps[0].name}")
        else:
            print("no compaction snapshots")
    else:
        print("no compaction-snapshots directory")

    print("\n[session-catchup] Done. Read the active plan file + tail of progress.md to fully resume.")
    return 0


def main() -> int:
    project_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    if not project_dir.is_dir():
        print(f"ERROR: {project_dir} is not a directory", file=sys.stderr)
        return 1

    ecosystem_dir = _resolve_ecosystem_dir(project_dir)
    if ecosystem_dir is None:
        print(f"[session-catchup] WARN: no ecosystem layout found under {project_dir}; "
              "git state only.")
        ecosystem_dir = project_dir
    eco_rel = ecosystem_dir.relative_to(project_dir) if ecosystem_dir != project_dir else Path(".")

    print("[session-catchup] Rebuilding context from disk + git.")
    print(f"[session-catchup] Ecosystem dir: {eco_rel}/")

    _say_git_state(project_dir)
    _say_recent_commits(project_dir)
    active_plan = _say_active_plan(project_dir)
    _say_recent_progress(project_dir, active_plan)
    _say_ralph_state(ecosystem_dir)
    _say_compaction_snapshots(project_dir)



if __name__ == "__main__":
    sys.exit(main())
