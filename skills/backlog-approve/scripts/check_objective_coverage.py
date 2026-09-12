#!/usr/bin/env python3
"""The two questions a backlog cannot answer about itself.

    python3 check_objective_coverage.py <project> [--json]

A brief rendered from a registry shows what somebody wrote down. It cannot show what
nobody wrote down, and that is the half of "can I trust this backlog" that reading the
items will never reach. An item you did not want is visible and can be struck; an item
nobody thought of is invisible, and no amount of careful reading surfaces it.

Linking each item to the objective it serves makes both directions computable:

    objective with no item     a goal nobody is working toward     ← the gap
    item with no objective     work serving nothing declared       ← the drift
    item citing a missing id   a link to something that is gone    ← the rot

## Why this was possible to write and still did not exist

`traces_to` has been in the kit since the brainstorm phase shipped. `build_agenda.py`
reads it; `agents/kairos-product-owner.md` describes it; `.squad/wiki/product/
objectives.md` produces the `OBJ-N` ids it points at. But `rules/cycle-backlog.md` never
listed it among an item's fields and `/backlog-item` never asked for it, so it was
written zero times in 651 items across ten registries — which `build_agenda.py` reports
as a schema gap in its own output rather than as 243 defective items (#82).

A field read by one consumer and written by no producer is not a schema; it is a plan
somebody had.

## What "no objectives declared" means here

**Not a failure.** A project that has not run `/brainstorm-objectives` has no objectives
document, and every item is correctly unlinked. Reporting 28 orphans there would be
inventing a standard the project never adopted. The check reports `NOT MEASURED` for the
coverage question and says which document would make it answerable.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        sys.path.insert(0, str(_up))
        break
from squad.paths import DATA_DIRNAME, WIKI  # noqa: E402

#: Where `/brainstorm-objectives` writes. Named once here; the message that tells a
#: reader what is missing quotes this same constant.
OBJECTIVES_REL = f"{DATA_DIRNAME}/{WIKI}/product/objectives.md"

OBJECTIVE_RE = re.compile(r"^##\s+(OBJ-\d+)\s*[—-]\s*(.*?)\s*$", re.M)
ITEM_RE = re.compile(r"^##\s+(B-\d+)\s*[—-]\s*(.*?)\s*(?:\[[ x]\])?\s*$", re.M)
TRACES_RE = re.compile(r"OBJ-\d+")


@dataclass
class Coverage:
    measurable: bool
    reason: str = ""
    objectives: dict = field(default_factory=dict)      # id -> title
    served: dict = field(default_factory=dict)          # OBJ-N -> [B-NNN]
    unserved: list = field(default_factory=list)        # OBJ-N with no item
    untraced: list = field(default_factory=list)        # B-NNN with no OBJ
    dangling: list = field(default_factory=list)        # (B-NNN, OBJ-N that is gone)
    items_total: int = 0

    def as_dict(self) -> dict:
        return {"measurable": self.measurable, "reason": self.reason,
                "objectives": self.objectives, "served": self.served,
                "unserved": self.unserved, "untraced": self.untraced,
                "dangling": self.dangling, "items_total": self.items_total}


def read_objectives(project: Path) -> tuple[dict, str]:
    """Return (id -> title, reason-it-is-empty). Both halves matter."""
    path = project / OBJECTIVES_REL
    if not path.is_file():
        return {}, (f"no {OBJECTIVES_REL} — this project has not declared objectives, "
                    "so nothing here can say whether the backlog covers them")
    text = path.read_text(encoding="utf-8-sig")
    found = {m.group(1): m.group(2).strip() for m in OBJECTIVE_RE.finditer(text)}
    if not found:
        return {}, (f"{OBJECTIVES_REL} exists and declares no `## OBJ-N` heading — "
                    "the document is a stub or uses another shape")
    return found, ""


def read_items(backlog: Path) -> list[tuple[str, str, str]]:
    """(id, title, traces_to) for every item, from the `## Items` section only."""
    text = backlog.read_text(encoding="utf-8-sig")
    body = text.split("\n## Items", 1)[-1]
    blocks = re.split(r"\n(?=## B-\d+)", body)
    out = []
    for block in blocks:
        head = ITEM_RE.match(block)
        if not head:
            continue
        traces = re.search(r"^traces_to:\s*(.*)$", block, re.M)
        out.append((head.group(1), head.group(2), traces.group(1).strip() if traces else ""))
    return out


def measure(project: Path) -> Coverage:
    backlog = project / "BACKLOG.md"
    if not backlog.is_file():
        return Coverage(False, f"no BACKLOG.md under {project}")
    objectives, why = read_objectives(project)
    items = read_items(backlog)
    if not objectives:
        # Still worth reporting how many items there are: "23 items and no declared
        # objective" is a finding about the project, not a failure of this checker.
        cov = Coverage(False, why)
        cov.items_total = len(items)
        return cov

    cov = Coverage(True, objectives=objectives, items_total=len(items))
    cov.served = {obj: [] for obj in objectives}
    for item_id, _title, traces in items:
        cited = TRACES_RE.findall(traces)
        if not cited:
            cov.untraced.append(item_id)
            continue
        for obj in cited:
            if obj in cov.served:
                cov.served[obj].append(item_id)
            else:
                cov.dangling.append((item_id, obj))
    cov.unserved = sorted(obj for obj, serving in cov.served.items() if not serving)
    return cov


def render(cov: Coverage) -> str:
    if not cov.measurable:
        return (f"NOT MEASURED: {cov.reason}\n"
                f"  {cov.items_total} item(s) read. Run `/brainstorm-objectives` to "
                "declare what this work is for, and coverage becomes answerable.\n")
    lines = [f"{len(cov.objectives)} objective(s) · {cov.items_total} item(s)", ""]
    for obj, title in sorted(cov.objectives.items(), key=lambda kv: _num(kv[0])):
        serving = cov.served.get(obj, [])
        mark = "GAP " if not serving else "    "
        lines.append(f"  {mark}{obj}  {title[:64]}")
        lines.append(f"        served by: {', '.join(serving) if serving else '— nothing'}")
    if cov.untraced:
        lines += ["", f"  {len(cov.untraced)} item(s) serve no declared objective:",
                  "    " + ", ".join(cov.untraced[:14])
                  + (" …" if len(cov.untraced) > 14 else "")]
        lines.append("    Either the objective was never declared, or the item should "
                     "not exist. Neither is neutral.")
    if cov.dangling:
        lines += ["", f"  {len(cov.dangling)} citation(s) point at an objective that is "
                  "not declared:"]
        for item_id, obj in cov.dangling[:8]:
            lines.append(f"    {item_id} → {obj}")
    if not cov.unserved and not cov.untraced and not cov.dangling:
        lines += ["", "  every objective is served and every item serves one"]
    return "\n".join(lines) + "\n"


def _num(obj_id: str) -> int:
    match = re.search(r"(\d+)", obj_id)
    return int(match.group(1)) if match else 1 << 30


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report objectives with no item, and items serving no objective.")
    parser.add_argument("project", nargs="?", default=".", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    cov = measure(args.project.resolve())
    if args.json:
        print(json.dumps(cov.as_dict(), indent=2, ensure_ascii=False))
    else:
        print(render(cov), end="")
    if not cov.measurable:
        # 2 across this kit means "could not measure" — never confused with "nothing
        # wrong", which is what a 0 here would have claimed.
        return 2
    return 1 if (cov.unserved or cov.untraced or cov.dangling) else 0


if __name__ == "__main__":
    raise SystemExit(main())
