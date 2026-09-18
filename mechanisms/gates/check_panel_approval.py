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

## What a signature can and cannot prove

This verifies that the record matches the assignment, that every voter is distinct and
reasoned, that the approving majority spans two families, and that the artifact still
hashes to what the panel voted on.

It does **not** prove a model was called. The record is written by the session that was
meant to collect the votes, so a session that fabricated three votes produces a file
this gate accepts. `alignment_judge.py` says the same of itself: *"It takes its verdict
on the command line. It does not read the evidence itself."* Building a panel on top did
not remove that — it made the ceremony more elaborate.

Closing it needs a signature the executor cannot mint: a transcript id, a provider
response id. Until that exists this is a check on FORM and on BINDING, and the reader is
told so in `not_checked` rather than left to infer independence from the word "panel".

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
import hashlib
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


def default_panel_path(project_dir: Path | None = None) -> Path:
    """Delegated: see `squad.layout.roster_path` for why this is not `repo_root()`.

    This function used to answer for itself and answered wrong, while a function of
    the same name two directories away had the fix written into its docstring.
    """
    from squad.layout import roster_path

    return roster_path(project_dir)


def record_path(project: Path, slug: str, phase: str) -> Path:
    # Same resolution as the writer — see `convene_panel.panels_dir`.
    return panels_dir(project) / f"{slug}-{phase}.json"


def _artifact_drifted(project: Path, record: Path) -> str:
    """Empty when the artifact still hashes to what was voted on, else why not.

    An absent hash is NOT drift: records written before this check existed cannot be
    retro-fitted, and refusing them would fail every panel that already ran. What is
    unverifiable is reported as unverified rather than asserted either way.
    """
    try:
        data = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    claimed, relative = data.get("artifact_sha256"), data.get("artifact") or ""
    if not claimed or not relative:
        return ""
    target = Path(relative)
    if not target.is_absolute():
        target = project / relative
    if not target.is_file():
        return (f"the panel voted on {relative}, which is no longer on disk. An "
                "approval of a document nobody can produce is not an approval")
    actual = hashlib.sha256(target.read_bytes()).hexdigest()
    if actual == claimed:
        return ""
    return (f"{relative} changed after the panel voted (recorded {claimed[:12]}, now "
            f"{actual[:12]}). Editing an artifact after its approval is the cheapest "
            "way to launder a rewrite past a panel")


def check(
    slug: str,
    phase: str,
    *,
    project: Path | None = None,
    panel_path: Path | None = None,
) -> tuple[int, dict]:
    project = project or repo_root()
    # Resolved against the project the CALLER named, not the process cwd. They are
    # usually the same and the gate is run from elsewhere often enough — by the
    # installer's post-install validation, among others — that the difference is
    # the roster being found or reported missing.
    panel_path = panel_path or default_panel_path(project)
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

    # The votes must be about THIS document.
    drifted = _artifact_drifted(project, rec)
    if drifted:
        return NOT_APPROVED, {"status": "stale", "slug": slug, "phase": phase,
                              "detail": drifted}

    try:
        outcome = panel.tally()
    except PanelInvalid as exc:
        return DID_NOT_CONVENE, {"status": "did_not_convene", "slug": slug,
                                 "phase": phase, "detail": str(exc)}

    body = panel.record()
    body["not_checked"] = [
        "WHETHER A MODEL WAS CALLED. The record is written by the session that was "
        "meant to collect the votes, so three fabricated votes produce a file this "
        "gate accepts. What is checked is form and binding, never independence",
        "WHETHER A REASON IS TRUE. The floor is 15 words saying what was checked "
        "against which evidence; nothing confronts that claim with the evidence",
    ]
    if not json.loads(rec.read_text(encoding="utf-8")).get("artifact_sha256"):
        body["not_checked"].append(
            "WHETHER THE ARTIFACT IS THE ONE VOTED ON — this record carries no "
            "`artifact_sha256`, so the binding could not be verified")
    if outcome is PanelOutcome.APPROVED:
        return APPROVED, {"status": "approved", **body}
    return NOT_APPROVED, {"status": "returned", **body,
                          "detail": "the panel judged this document and did not carry "
                                    "it. NEEDS_REVISION"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--phase", required=True)
    ap.add_argument(
        "--root", "--project", dest="root", type=Path, default=None)
    ap.add_argument("--panel", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    code, result = check(args.slug, args.phase, project=args.root,
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
            for d in result.get("dissent", []):
                # Printed under an APPROVAL on purpose: the reader who advances this
                # artifact is the one who must see what the losing vote objected to.
                print(f"  DISSENT ({d['family']}) {d['reviewer']}: {d['reason'][:160]}")
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
