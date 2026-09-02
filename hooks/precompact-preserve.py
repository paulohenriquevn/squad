#!/usr/bin/env python3
"""PreCompact — write the plan and progress to disk before the context is cut.

Compaction discards the turn-by-turn context. Whatever the session needs after
it must already be on disk, so this snapshots the active plan and surfaces the
goal plus recent progress into the summary Claude keeps.

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
from squad.plan import goal_line
from squad.plan import resolve as resolve_plan

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

    active = resolve_plan(eco)
    if active is not None:
        plan = active.path
        snapshots = eco / ".compaction-snapshots"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        try:
            snapshots.mkdir(parents=True, exist_ok=True)
            shutil.copy2(plan, snapshots / f"plan-{stamp}.md")
            print(f"{TAG} Plan snapshotted: {snapshots / f'plan-{stamp}.md'}")
        except OSError as error:
            # Say so rather than continuing quietly: the reminder below promises
            # the snapshot is on disk, and a promise that silently failed is
            # worse than none.
            print(f"{TAG} Could NOT snapshot the plan ({error}) — "
                  f"the copy below does not exist", file=sys.stderr)

        print(f"{TAG} Active plan: {plan}")
        print(f"{TAG} Plan Goal (first blockquote line after ## Goal):")
        goal = goal_line(plan)
        if goal:
            print(goal)

        progress = eco / "session-state" / f"{plan.name.removesuffix('-plan.md')}-progress.md"
        if progress.is_file():
            print(f"{TAG} Last 10 progress entries:")
            tail = progress.read_text(encoding="utf-8", errors="replace").splitlines()[-10:]
            for line in tail:
                print(f"  {line}")

    print()
    print(f"{TAG} Post-compaction: plan + progress are on disk under "
          f"{eco}/.compaction-snapshots/.")
    print(f"{TAG} Re-read {eco}/records/plans/ and {eco}/session-state/ to rebuild context.")


if __name__ == "__main__":
    main()
