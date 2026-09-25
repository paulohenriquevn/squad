#!/usr/bin/env python3
"""Open, refill, inspect and close the active block of work.

    python3 mechanisms/cycle/sprint.py status
    python3 mechanisms/cycle/sprint.py open --id S-001 --goal "the deck's seam is reachable" \\
        --admit B-286,B-288 --by human/paulo [--traces-to OBJ-2]
    python3 mechanisms/cycle/sprint.py admit --item B-290
    python3 mechanisms/cycle/sprint.py close --by human/paulo

## Why this file exists separately from `squad/sprint.py`

The model is shared knowledge and belongs in the package; the invocation belongs here. And
this half is not optional: on 2026-09-24 this repository fixed a reviewer brief that named
`check_evidence_citations.py` and told five readers to run it. That file has no `__main__`,
so running it printed nothing and exited 0 — indistinguishable from a pass. Shipping a
sprint model with no way to open one would be the same defect, one day later.

## Why `close` reads the registry and the library does not

`squad.sprint.close` takes the terminal statuses as an argument. It never parses
`BACKLOG.md`, because a second reader of `status:` is a second answer to what an item's
state is — the failure this kit has now measured three times, most recently in an index
that labelled `approved` items "In flight" while the board computed work-in-flight from the
event stream. So the read happens once, here, through the same parser every other reader
uses.

Exit codes:
  0 — the command did what it says
  1 — refused, with the reason on stderr (no goal, nothing admitted, an unsigned
      signature, a second open sprint, or an admitted item that can still move)
  2 — not measured: no registry to read where one is required
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[2]))
sys.path.insert(0, str(_HERE.parents[2] / "skills" / "backlog-review" / "scripts"))

from squad.sprint import (  # noqa: E402 — post-bootstrap import
    TERMINAL_STATUSES,
    SprintInvalid,
    admit,
    close,
    load,
    open_sprint,
)


def _terminal_statuses(project_root: Path, ids: tuple[str, ...]) -> dict[str, str]:
    """Each admitted id mapped to its registry status, read with the shared parser.

    An id the registry does not define is left OUT rather than defaulted, so `close`
    refuses it by name. Defaulting it to anything would let a sprint close over an item
    that no longer exists, which is the quietest way for work to disappear.
    """
    from check_backlog_structure import (
        _parse_items,
    )

    path = project_root / "BACKLOG.md"
    try:
        items = _parse_items(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise SystemExit(f"cannot read {path}: {exc}")
    by_id = {i.item_id: i.fields.get("status", "") for i in items}
    return {i: by_id[i] for i in ids if i in by_id}


def _render(project_root: Path) -> str:
    s = load(project_root)
    if s is None:
        return ("sprint: NONE\n"
                "  No block is declared, so the queue orders by obligation, unblocking, "
                "status and age — exactly as it did before sprints existed.")
    state = "OPEN" if s.is_open else "CLOSED"
    out = [f"sprint: {s.sprint_id} — {state}",
           f"  goal:      {s.goal}",
           f"  opened by: {s.opened_by}",
           f"  admitted:  {', '.join(s.admitted)}"]
    if s.traces_to:
        out.append(f"  serves:    {', '.join(s.traces_to)}")
    if not s.is_open:
        out.append(f"  closed by: {s.closed_by}")
        for item_id, verdict in (s.verdicts or {}).items():
            out.append(f"    {item_id}: {verdict}")
    else:
        statuses = _terminal_statuses(project_root, s.admitted)
        still = [i for i in s.admitted if statuses.get(i) not in TERMINAL_STATUSES]
        out.append(f"  still moving: {', '.join(still) if still else '(none — it can close)'}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="The active block of work.")
    ap.add_argument("--project", default=".", help="the project root (default: .)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="what block is declared, and whether it can close")

    op = sub.add_parser("open", help="declare a block")
    op.add_argument("--id", required=True)
    op.add_argument("--goal", required=True)
    op.add_argument("--admit", required=True, help="comma-separated item ids")
    op.add_argument("--by", required=True, help="human/<name>")
    op.add_argument("--traces-to", default="", help="comma-separated OBJ-N")

    ad = sub.add_parser("admit", help="add an item to the open block")
    ad.add_argument("--item", required=True)

    cl = sub.add_parser("close", help="close the block, recording every verdict")
    cl.add_argument("--by", required=True, help="human/<name>")

    args = ap.parse_args(argv)
    root = Path(args.project).resolve()

    try:
        if args.cmd == "status":
            print(_render(root))
            return 0
        if args.cmd == "open":
            s = open_sprint(root, sprint_id=args.id, goal=args.goal,
                            admitted=[i for i in args.admit.split(",") if i.strip()],
                            opened_by=args.by,
                            traces_to=[t for t in args.traces_to.split(",") if t.strip()])
            print(f"opened {s.sprint_id}: {s.goal}")
            print(f"  admitted: {', '.join(s.admitted)}")
            return 0
        if args.cmd == "admit":
            s = admit(root, args.item)
            print(f"{s.sprint_id} now admits: {', '.join(s.admitted)}")
            return 0
        if args.cmd == "close":
            current = load(root)
            if current is None or not current.is_open:
                print("no sprint is open", file=sys.stderr)
                return 1
            s = close(root, closed_by=args.by,
                      terminal=_terminal_statuses(root, current.admitted))
            print(f"closed {s.sprint_id}")
            for item_id, verdict in (s.verdicts or {}).items():
                print(f"  {item_id}: {verdict}")
            return 0
    except SprintInvalid as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
