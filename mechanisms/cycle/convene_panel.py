#!/usr/bin/env python3
"""Assign the reviewers that must judge one DISCOVER or PLAN document.

    python3 mechanisms/cycle/convene_panel.py --slug B-014 --phase discover \
        --author daedalus-tech-lead

## What this is, and what it deliberately is not

`review_panel.py` TALLIES a record. Nothing produced that record, so until this
existed the rule "DISCOVER and PLAN advance on 2 of 3 signed approvals" was a
sentence in `rules/` that no phase enforced (issue #65) — the kit's own governing
failure reached through the governance layer: an inability to measure had become a
passing measurement.

This closes the deterministic half. It resolves WHO must vote, refuses to name a
reviewer the project cannot supply, and writes the assignment. It does **not** vote
and cannot: the judgement a panel exists for is exactly the judgement no script can
make, which is the entire argument for having one.

The other half is conversational. The phase skill reads this assignment, invokes each
named agent, and writes the votes. `check_panel_approval.py` then refuses to let the
phase advance unless the record matches this assignment and carries a majority.

## Why the assignment is written down rather than recomputed

Because the record must be checkable against it. If the panel that voted may differ
from the panel that was convened, convening buys nothing: a document could be routed
to the specialists its content demands and signed off by three others. `Panel.assigned`
carries this list, and `review_panel.py` refuses a record whose voters do not match.

## Why a seat that cannot be filled is not a rejection

An agent this project does not have is an ABSENT reviewer, not a dissenting one. The
panel did not convene, which is a different fact from the document being wrong and
takes a different action — the item returns to the registry with an `access`
impediment (`halt_disposition.py`) and the queue takes the next item. Reporting it as
a rejection would send an author to rewrite a document nobody found fault with.

Exit codes, matching `check_panel_capability.py` so the two read the same:
  0  assigned
  1  the declaration is wrong anywhere — too few seats, or one family only
  2  the roster could not be read or parsed; nothing was checked, and that is not a pass
  3  valid declaration, unfillable HERE — a missing agent or an absent binary
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import sys as _sys_bootstrap
from pathlib import Path as _Path_bootstrap

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conventions"))

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from installed_plugins import resolve as resolve_plugin
from review_panel import (
    HOME_FAMILY,
    PANEL_SIZE,
    Seat,
    parse_panel_phases,
    seats_for,
)

from squad.paths import write_records_dir

OK, INVALID, UNREADABLE, UNFILLABLE = 0, 1, 2, 3


def repo_root() -> Path:
    """The PROJECT whose records this writes, not the kit this file lives in.

    `parents[2]` is correct for the standalone repository and wrong for every plugin
    install: this file sits at `.claude/mechanisms/cycle/`, so two levels up is
    `.claude/` — the installed kit. `write_records_dir` then produced
    `.claude/.squad/records/panels/` on a consumer 2026-09-16, six files deep.

    That is the LOUDEST form of a split write root, not a lesser one: `.claude/` is
    gitignored AND replaced wholesale by the installer, so those records reach nobody and
    are scheduled for deletion, while a reader resolving the write root reports absence.
    Two of the six were discover assignments no later run regenerates, and they are gone.

    `records-location.md` names this exact blind spot in its own words — "a writer whose
    destination never passes through `squad.paths` — taken from argv, JOINED ONTO THE
    INSTALLED KIT, handed down by a caller" — and it arrived here through a correct call
    to a correct function with the wrong project.
    """
    from squad.layout import resolve

    layout = resolve(warn=False)
    if layout is not None:
        return layout.project_dir
    # No kit found: the standalone repository is the only shape left, and there
    # `parents[2]` IS the project root.
    return Path(__file__).resolve().parents[2]


def default_panel_path() -> Path:
    return repo_root() / "rules" / "review-panel.txt"


def agents_dir(project: Path) -> Path:
    """Where this project keeps its specialists.

    A plugin install puts them under `.claude/`; a standalone kit has them at the
    root. Checking both means one flag works in either shape.
    """
    nested = project / ".claude" / "agents"
    return nested if nested.is_dir() else project / "agents"


def resolve_seat(seat: Seat, *, agents: Path, which=shutil.which,
                 config_dir: Path | None = None) -> str:
    """Empty string when the seat is fillable, else why it is not.

    A `plugin:agent` seat used to be accepted WITHOUT verification, and this file said
    so: there is no file for it in this tree, so requiring one would have refused a
    reviewer that works. `rules/review-panel.txt` recorded that closing the hole meant
    asking Claude Code which plugins are installed, "which nothing in this kit does
    yet" — true of the kit and false of the machine. `installed_plugins.py` reads the
    manifest, so the seat is now verified like every other one.

    That matters more than it looks: the largest pool of specialists a project has is
    exactly the one the panel could not check, and accepting a seat on the strength of
    its name is what the rest of this mechanism refuses everywhere else.
    """
    if seat.is_builtin:
        if ":" in seat.agent:
            plugin_name, _, agent_name = seat.agent.partition(":")
            plugin = resolve_plugin(plugin_name, config_dir)
            if plugin is None:
                return f"plugin `{plugin_name}` is not installed"
            if not plugin.has_agent(agent_name):
                return (f"plugin `{plugin_name}` is installed and supplies no agent "
                        f"`{agent_name}`")
            return ""
        if not (agents / f"{seat.agent}.md").is_file():
            return f"no agent `{seat.agent}` in {agents}"
        return ""
    if which(seat.invocation) is None:
        return f"`{seat.invocation}` is not on PATH"
    return ""


def convene(
    slug: str,
    phase: str,
    author: str,
    *,
    panel_path: Path | None = None,
    project: Path | None = None,
    which=shutil.which,
    config_dir: Path | None = None,
) -> tuple[int, dict]:
    """(exit code, the assignment or the reason there is none)."""
    panel_path = panel_path or default_panel_path()
    project = project or repo_root()
    phase = phase.lower()

    try:
        text = panel_path.read_text(encoding="utf-8")
        gated = parse_panel_phases(text)
        seats = seats_for(text, phase)
    except (OSError, ValueError) as exc:
        return UNREADABLE, {"status": "unreadable", "detail": str(exc)}

    if phase not in gated:
        return OK, {"status": "not_gated", "phase": phase,
                    "detail": f"no panel gates `{phase}`; it advances on its own verdict"}

    if len(seats) != PANEL_SIZE:
        return INVALID, {
            "status": "invalid",
            "detail": f"`{phase}` declares {len(seats)} seats, not {PANEL_SIZE}. The "
                      "majority is 2 of 3 over a FULL panel, so a short roster cannot "
                      "reach it and a long one has no defined majority",
        }

    if author and author in {s.agent for s in seats}:
        return INVALID, {
            "status": "invalid",
            "detail": f"the author ({author}) holds a seat on the `{phase}` panel. An "
                      "author approving their own work is not a review",
        }

    families = {s.family for s in seats}
    if not (families - {HOME_FAMILY, "unknown"}):
        return INVALID, {
            "status": "invalid",
            "detail": f"every seat on the `{phase}` panel is {HOME_FAMILY} or an "
                      f"unrecognised model ({sorted(families)}). Correlated models "
                      "share failure modes: a plausible fabrication that survives one "
                      "tends to survive its siblings",
        }

    agents = agents_dir(project)
    unfilled = [(s, why) for s in seats
                if (why := resolve_seat(s, agents=agents, which=which,
                                        config_dir=config_dir))]
    if unfilled:
        return UNFILLABLE, {
            "status": "unfillable",
            "phase": phase,
            "slug": slug,
            "unfilled": [{"agent": s.agent, "reason": why} for s, why in unfilled],
            "detail": "the panel cannot convene here. This is an `access` impediment "
                      "for halt_disposition.py, NOT a returned document",
        }

    return OK, {
        "status": "assigned",
        "slug": slug,
        "phase": phase,
        "author": author,
        "assigned": [s.agent for s in seats],
        "seats": [
            {"agent": s.agent, "model": s.model, "family": s.family,
             "invocation": s.invocation}
            for s in seats
        ],
        "families": sorted(families),
        "panel_size": PANEL_SIZE,
    }


def panels_dir(project: Path) -> Path:
    """Where a panel's assignment and record live: `<project>/.squad/records/panels`.

    This held its own copy of the root list until the roots were centralised. The
    writer and the reader MUST agree — a gate reading the other location would report
    "no record" forever and hold every item permanently — and two copies is exactly how
    they come to disagree.
    """
    return write_records_dir(project, "panels")


def assignment_path(project: Path, slug: str, phase: str) -> Path:
    return panels_dir(project) / f"{slug}-{phase}.assignment.json"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--slug", required=True, help="the item, e.g. B-014")
    ap.add_argument("--phase", required=True, help="discover | plan")
    ap.add_argument("--author", default="", help="who wrote the document under review")
    ap.add_argument("--project", type=Path, default=None)
    ap.add_argument("--panel", type=Path, default=None, help="override the roster path")
    ap.add_argument("--config-dir", type=Path, default=None,
                    help="where Claude Code keeps its plugin manifest")
    ap.add_argument("--write", action="store_true",
                    help="persist the assignment the record will be checked against")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    code, result = convene(args.slug, args.phase, args.author,
                           panel_path=args.panel, project=args.project,
                           config_dir=args.config_dir)

    if code == OK and result["status"] == "assigned" and args.write:
        out = assignment_path(args.project or repo_root(), args.slug, args.phase)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        result["written_to"] = str(out)

    if args.json:
        print(json.dumps(result, indent=2))
        return code

    status = result["status"]
    if status == "assigned":
        print(f"panel convened for {args.slug} {args.phase} "
              f"({', '.join(result['families'])})")
        for s in result["seats"]:
            print(f"  {s['agent']:<28} {s['model']:<16} {s['family']}")
        if "written_to" in result:
            print(f"assignment: {result['written_to']}")
    elif status == "unfillable":
        print(f"panel did NOT convene for {args.slug} {args.phase}:", file=sys.stderr)
        for u in result["unfilled"]:
            print(f"  {u['agent']}: {u['reason']}", file=sys.stderr)
        print(result["detail"], file=sys.stderr)
    elif status == "not_gated":
        # Not an error: this phase advances on its own verdict, so stdout.
        print(f"{status}: {result['detail']}")
    else:
        print(f"{status}: {result['detail']}", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
