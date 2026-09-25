#!/usr/bin/env python3
"""PreCompact — write the plan and progress to disk before the context is cut.

Compaction discards the turn-by-turn context. Whatever the session needs after
it must already be on disk, so this snapshots the active plan AND the progress
log, then surfaces the goal plus recent progress into the summary Claude keeps.

The closing lines name only what was actually copied. They are read after the
context is gone, when the session cannot check them against anything it
remembers, so a file named there and absent from disk is worse than silence.

It never blocks: refusing a compaction strands the session with a full context
window and nothing gained.
"""
from __future__ import annotations

import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from squad import PreCompactContext, create_context
from squad.layout import resolve
from squad.paths import (
    SESSION_STATE,
    SNAPSHOTS,
    write_records_dir,
    write_state_dir,
)
from squad.plan import goal_line, resolve as resolve_plan

TAG = "[precompact-preserve]"


def main() -> None:
    create_context(PreCompactContext)
    print(f"{TAG} Context compaction about to occur. Preserving state.")

    layout = resolve()
    if layout is None:
        # No kit, or a broken install that already said so on stderr. Either way
        # there is nothing of ours to preserve.
        return
    eco = layout.eco
    # State the system writes goes under the project's write root, never beside the
    # installed kit. `layout.eco` is where the KIT is.
    project = layout.project_dir

    active = resolve_plan(eco)
    snapshots = write_state_dir(project, SNAPSHOTS)
    preserved: list[str] = []
    if active is not None:
        plan = active.path
        # The slug comes from `ActivePlan`, not from slicing the filename again.
        # Three hooks resolving one plan by hand is what `squad/plan.py` exists
        # to have ended, and this was the copy that survived it.
        progress = write_state_dir(project, SESSION_STATE) / f"{active.slug}-progress.md"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        # The progress log is snapshotted too, and that is the point of the hook
        # rather than a nicety: the plan is a stable document that survives on
        # its own, while the progress log is the record of THIS session and the
        # thing compaction is about to make unreproducible.
        for kind, source in (("plan", plan), ("progress", progress)):
            if not source.is_file():
                continue
            try:
                snapshots.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, snapshots / f"{kind}-{stamp}.md")
            except OSError as error:
                # Say so rather than continuing quietly: the reminder below names
                # what is on disk, and a promise that silently failed is worse
                # than none.
                print(f"{TAG} Could NOT snapshot the {kind} ({error}) — "
                      f"the copy below does not exist", file=sys.stderr)
                continue
            preserved.append(kind)
            print(f"{TAG} {kind.capitalize()} snapshotted: "
                  f"{snapshots / f'{kind}-{stamp}.md'}")

        print(f"{TAG} Active plan: {plan}")
        print(f"{TAG} Plan Goal (first blockquote line after ## Goal):")
        goal = goal_line(plan)
        if goal:
            print(goal)

        if progress.is_file():
            print(f"{TAG} Last 10 progress entries:")
            tail = progress.read_text(encoding="utf-8", errors="replace").splitlines()[-10:]
            for line in tail:
                print(f"  {line}")

    print()
    # Named from what was actually copied. The sentence is read AFTER the context
    # is cut, when the session can no longer check it against anything it
    # remembers — so it may only name files that are there.
    if preserved:
        print(f"{TAG} Post-compaction: {' + '.join(preserved)} are on disk under "
              f"{snapshots}/.")
    else:
        print(f"{TAG} Post-compaction: nothing was snapshotted.")
    print(f"{TAG} Re-read {write_records_dir(project, 'plans')} and "
          f"{write_state_dir(project, SESSION_STATE)} to rebuild context.")


if __name__ == "__main__":
    main()
