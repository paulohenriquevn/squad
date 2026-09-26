#!/usr/bin/env python3
"""What this system is today, and what it becomes if the open items are done.

    python3 build_gap_analysis.py <project> [--out PATH] [--status triaged] [--md|--json]

## The two halves were already there

A backlog item carries both sides of a gap analysis and nobody had put them side by
side. Measured on a real item:

    evidence:  grep -ci 'cnpg' infra/helmfile/cell.helmfile.yaml.gotmpl -> 0
    dod:       one CNPG instance per cell, declared in the cell composition
               the operator is Ready before any `Cluster` is admitted

The first is the AS-IS, and it is a measurement rather than an opinion. The second is
the TO-BE, and the intake gate already refuses a bullet that cannot fail. So this adds
no field and asks no new question — it projects `evidence` + `why_now` against `dod` in
the three-column shape business analysis has used for decades (BABOK §6.1: analyse
current state, define future state, perform gap analysis between them).

## Why the aggregate view is the point

Per item the gap is obvious to whoever wrote it. What nobody can hold in their head is
the SUM: twenty-three items, each a small promise, and no page saying what the system
looks like once they are all kept. That is the question this answers — *what will we
have, starting from what we have today*.

## Three things it must not claim, and does not

**It does not claim the future state is coherent.** Two items may promise contradictory
things and this cannot tell. It renders both and says so. Reconciling them is design
work, and design is a phase with its own drawings.

**It does not claim the current state is complete.** The AS-IS here is the union of what
the items happened to measure. A part of the system nobody filed an item against is
absent from this page and is not thereby fine. The header states the coverage.

**It does not claim the work is possible.** An item is a hypothesis until DISCOVER
measures it; a `triaged` item has evidence for the problem, never proof that the
solution works.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

_HERE = Path(__file__).resolve()
for _up in _HERE.parents:
    if (_up / "squad" / "paths.py").is_file():
        sys.path.insert(0, str(_up))
        break

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.paths import write_records_dir  # noqa: E402 — post-bootstrap import

#: Reused rather than reimplemented: the parser, the evidence verifier and the objective
#: coverage all already exist one skill over. A second copy of the item parser is how
#: two readers of the same registry start disagreeing about what it says.
sys.path.insert(0, str(_HERE.parents[2] / "backlog-approve" / "scripts"))
import build_approval_brief as brief  # noqa: E402 — post-bootstrap import
from check_objective_coverage import measure as measure_coverage  # noqa: E402


@dataclass
class Row:
    item_id: str
    title: str
    domain: str
    as_is: str
    as_is_verified: str
    why_now: str
    to_be: list = field(default_factory=list)
    blocked_by: str = ""


def rows(project: Path, wanted_status: str | None) -> list[Row]:
    items = brief.parse(project / "BACKLOG.md", project, wanted_status)
    out = []
    for it in items:
        out.append(Row(
            item_id=it.item_id,
            title=it.title,
            domain=it.fields.get("domain") or "(none)",
            as_is=_condense(it.fields.get("evidence") or ""),
            as_is_verified=it.evidence_verdict,
            why_now=_condense(it.fields.get("why_now") or ""),
            to_be=list(it.fields.get("dod") or []),
            blocked_by=(it.fields.get("blocked_by") or "").strip(),
        ))
    return out


def _condense(text: str) -> str:
    """One paragraph, whitespace normalised. The full field stays in BACKLOG.md."""
    return " ".join(text.split())


def render_markdown(data: list[Row], project: Path, wanted_status: str | None) -> str:
    by_domain: dict[str, list[Row]] = {}
    for row in data:
        by_domain.setdefault(row.domain, []).append(row)

    verified = sum(1 for r in data if r.as_is_verified == "checks out")
    unverified = sum(1 for r in data if r.as_is_verified == "does not check out")
    unknown = sum(1 for r in data if r.as_is_verified == "not verifiable")
    promises = sum(len(r.to_be) for r in data)
    blocked = [r for r in data if r.blocked_by and r.blocked_by not in ("none", "-", "—")]

    out = [
        f"# As-is → To-be — {project.name}",
        "",
        f"What this system is today, and what it becomes if the {len(data)} open item(s)"
        + (f" at `{wanted_status}`" if wanted_status else "")
        + f" are done. {promises} promise(s) in total.",
        "",
        "## What this page can and cannot tell you",
        "",
        "| | |",
        "|---|---|",
        f"| **Current state, verified** | {verified} item(s) cite files that are on disk |",
        f"| **Current state, unverifiable** | {unknown} cite no file this checker can test |",
        f"| **Current state, broken pointer** | {unverified} cite a file that is not there |",
        f"| **Items that cannot start yet** | {len(blocked)} are blocked on another item |",
        "",
        "**The current state here is the union of what these items happened to measure.**",
        "A part of the system nobody filed an item against is absent from this page, and is",
        "not thereby fine. **The future state is not checked for coherence** — two items may",
        "promise contradictory things and nothing here can tell. And an item is a hypothesis",
        "until DISCOVER measures it: evidence for the problem is not proof the solution works.",
        "",
    ]

    cov = measure_coverage(project)
    if cov.measurable and cov.unserved:
        out += [
            f"**{len(cov.unserved)} declared objective(s) have no item** "
            + ", ".join(f"`{o}`" for o in cov.unserved)
            + ". The future state below does not reach them, however many items are done.",
            "",
        ]

    out += ["---", ""]
    for domain, group in sorted(by_domain.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        out += [f"## `{domain}` — {len(group)} item(s)", ""]
        for row in group:
            out += [f"### {row.item_id} — {row.title}", ""]
            mark = {"checks out": "measured",
                    "does not check out": "**pointer does not resolve**",
                    "not verifiable": "stated, not file-checkable"}[row.as_is_verified]
            out += [f"**Today** ({mark})", "",
                    f"> {row.as_is or '_no evidence recorded_'}", ""]
            if row.why_now:
                out += [f"**Why it matters now.** {row.why_now}", ""]
            out += ["**After** — what closes it", ""]
            if row.to_be:
                out += [f"- {bullet}" for bullet in row.to_be]
            else:
                out.append("- _nothing stated; this item has no closing criterion_")
            if row.blocked_by and row.blocked_by not in ("none", "-", "—"):
                out += ["", f"**Cannot start:** waiting on {row.blocked_by}"]
            out.append("")
    return "\n".join(out) + "\n"


def as_json(data: list[Row]) -> list[dict]:
    return [{"id": r.item_id, "title": r.title, "domain": r.domain,
             "as_is": r.as_is, "as_is_verified": r.as_is_verified,
             "why_now": r.why_now, "to_be": r.to_be, "blocked_by": r.blocked_by}
            for r in data]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render the open backlog as current state versus future state.")
    parser.add_argument("project", nargs="?", default=".", type=Path)
    parser.add_argument("--status", default="triaged",
                        help="only items at this status (default: triaged); 'any' for all")
    parser.add_argument("--out", type=Path, default=None)
    # Both halves of the documented `[--md|--json]` pair are declared. Markdown is what
    # you get either way when neither is passed, which is exactly why `--md` being
    # undefined went unnoticed: the documented command exits 2 on an argument that
    # looks like it should change nothing.
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--md", action="store_true", help="render markdown (the default)")
    output.add_argument("--json", action="store_true")
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args()

    project = args.project.resolve()
    if not (project / "BACKLOG.md").is_file():
        print(f"NOT MEASURED: no BACKLOG.md under {project}", file=sys.stderr)
        return 2

    wanted = None if args.status == "any" else args.status
    data = rows(project, wanted)
    if not data:
        print(f"NOTHING OPEN: no item at status '{args.status}'")
        return 1

    if args.json:
        print(json.dumps(as_json(data), indent=2, ensure_ascii=False))
        return 0
    body = render_markdown(data, project, wanted)
    if args.stdout:
        print(body)
        return 0
    out = args.out or (write_records_dir(project) / "as-is-to-be.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    print(f"wrote {out}")
    print(f"  {len(data)} item(s) · {sum(len(r.to_be) for r in data)} promise(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
