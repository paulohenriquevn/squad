#!/usr/bin/env python3
"""Refuse to advance a DISCOVER or PLAN document the panel did not approve.

    python3 mechanisms/gates/check_panel_approval.py --slug B-014 --phase discover

## Why this is a gate and not a step inside the phase

`cycle_events.py` records that a phase ended and says so in its own docstring: it is
NOT a judge, and it swallows environmental errors on purpose, because bookkeeping that
fails must not fail the work. A block placed there would be a judge folded into a
record — the exact shape the kit argues lets a declared plan and its execution drift
with nobody noticing.

So the refusal lives here, where a gate is allowed to say no.

## Absence is not approval

The single most important line in this file is that a MISSING record fails. A phase
that never convened its panel is indistinguishable, from the outside, from one whose
reviewers all approved — unless the missing record is treated as what it is. This is
the kit's governing sentence applied to its own governance: an inability to measure
must never become a passing measurement.

That is not hypothetical here. `review_panel.py` shipped with a rule, a tally, an
intake premise and 377 lines of tests, and for a day nothing convened a panel while
`rules/cycle-discover.md` stated the phase advanced on 2 of 3 signed approvals
(issue #65). Every DISCOVER and PLAN in that window passed a gate nobody ran.

## Three outcomes, deliberately not two

  approved      the majority carried it — advance
  returned      the panel judged and did not carry it — NEEDS_REVISION, a real verdict
  did not convene   nobody judged. Not a rejection: an absent reviewer is an `access`
                impediment for `halt_disposition.py`, and sending the author to rewrite
                a document nobody found fault with would be the wrong action entirely.

Exit codes:
  0  approved, or the phase is not one a panel gates
  1  not approved — returned by the panel, or no record at all
  2  the roster or the record could not be read; nothing was checked, and that is
     not a pass
  3  the panel did not convene validly — read the message before acting
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cycle"))

from convene_panel import assignment_path, panels_dir, repo_root
from review_panel import (
    PanelInvalid,
    PanelOutcome,
    load,
    parse_panel_phases,
)

APPROVED, NOT_APPROVED, UNCHECKED, DID_NOT_CONVENE = 0, 1, 2, 3


def default_panel_path() -> Path:
    return repo_root() / "rules" / "review-panel.txt"


def record_path(project: Path, slug: str, phase: str) -> Path:
    # Same resolution as the writer — see `convene_panel.panels_dir`.
    return panels_dir(project) / f"{slug}-{phase}.json"


def check(
    slug: str,
    phase: str,
    *,
    project: Path | None = None,
    panel_path: Path | None = None,
) -> tuple[int, dict]:
    project = project or repo_root()
    panel_path = panel_path or default_panel_path()
    phase = phase.lower()

    try:
        gated = parse_panel_phases(panel_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return UNCHECKED, {"status": "unchecked", "detail": f"cannot read the roster: {exc}"}

    if phase not in gated:
        return APPROVED, {"status": "not_gated", "slug": slug, "phase": phase,
                          "detail": f"no panel gates `{phase}`"}

    rec = record_path(project, slug, phase)
    if not rec.is_file():
        return NOT_APPROVED, {
            "status": "no_record", "slug": slug, "phase": phase,
            "expected": str(rec),
            "detail": "no panel record. An absent record is NOT an approval: a phase "
                      "that never convened its panel would otherwise be "
                      "indistinguishable from one every reviewer approved. Run "
                      "`convene_panel.py`, invoke the assigned agents, and write their "
                      "votes here",
        }

    try:
        panel = load(rec)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return UNCHECKED, {"status": "unchecked", "slug": slug, "phase": phase,
                           "detail": f"cannot read the record {rec}: {exc}"}

    # The record must be checkable against who was actually convened, and that list
    # comes from the assignment on disk — never from the record, which would let a
    # document supply the very list it is checked against.
    #
    # A missing assignment is therefore not a soft spot to shrug at: it means no
    # panel was ever convened for this artifact, so there is nothing the votes can
    # be verified against and the votes could name anyone.
    assign = assignment_path(project, slug, phase)
    if not assign.is_file():
        return DID_NOT_CONVENE, {
            "status": "did_not_convene", "slug": slug, "phase": phase,
            "expected": str(assign),
            "detail": "votes exist but no panel was convened: there is no assignment "
                      "to check them against, so any three names would pass. Run "
                      "`convene_panel.py --write` before collecting votes",
        }
    try:
        panel.assigned = json.loads(assign.read_text(encoding="utf-8"))["assigned"]
    except (OSError, ValueError, KeyError) as exc:
        return UNCHECKED, {"status": "unchecked", "slug": slug, "phase": phase,
                           "detail": f"cannot read the assignment {assign}: {exc}"}

    try:
        outcome = panel.tally()
    except PanelInvalid as exc:
        return DID_NOT_CONVENE, {"status": "did_not_convene", "slug": slug,
                                 "phase": phase, "detail": str(exc)}

    body = panel.record()
    if outcome is PanelOutcome.APPROVED:
        return APPROVED, {"status": "approved", **body}
    return NOT_APPROVED, {"status": "returned", **body,
                          "detail": "the panel judged this document and did not carry "
                                    "it. NEEDS_REVISION"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--phase", required=True)
    ap.add_argument("--project", type=Path, default=None)
    ap.add_argument("--panel", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    code, result = check(args.slug, args.phase, project=args.project,
                         panel_path=args.panel)
    if args.json:
        print(json.dumps(result, indent=2))
        return code

    status = result["status"]
    if status in ("approved", "not_gated"):
        if status == "approved":
            print(f"panel APPROVED {args.slug} {args.phase} "
                  f"({result['approvals']}/{result['panel_size']}, "
                  f"families: {', '.join(result['families'])})")
            if result.get("dissent"):
                print(f"  dissent, kept on purpose: {', '.join(result['dissent'])}")
        else:
            print(result["detail"])
        return code

    print(f"{status.upper()}: {args.slug} {args.phase}", file=sys.stderr)
    print(f"  {result['detail']}", file=sys.stderr)
    if status == "returned":
        for v in result["votes"]:
            print(f"  {v['verdict']:<8} {v['reviewer']}: {v['reason'][:90]}",
                  file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
