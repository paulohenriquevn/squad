#!/usr/bin/env python3
"""Record one reviewer's vote, refusing the ones a tally would reject later.

    python3 mechanisms/cycle/cast_vote.py --slug theo --phase design \
        --reviewer vera-technical-arbiter --model claude-opus-5 \
        --verdict return --reason "D4 asserts durability whose evidence is in another repo"

## Why votes are cast one at a time

`review_panel.py` validates a COMPLETE panel and refuses it whole: an author on their
own panel, a duplicate reviewer, a reason under fifteen words, a voter the assignment
never named. Refusing whole is right at tally time and useless while collecting — the
session learns its first vote was invalid after spending three invocations.

This applies the same rules to one vote, at the moment it is cast, against the
assignment on disk. Same refusals, three invocations earlier.

## What it does NOT establish

**That a model was called.** This writes what the caller passes. A session that
fabricates three votes produces a file the tally accepts and this cannot tell the
difference — `check_panel_approval.py` states the same limit about the record as a
whole, and nothing here narrows it. What is checked is form and standing, never
independence.

Exit codes:
  0  recorded
  1  refused — the reason names which rule
  2  no assignment; nothing was recorded
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        sys.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad import shared_file  # noqa: E402 — post-bootstrap import
from squad.paths import (  # noqa: E402 — post-bootstrap import
    confined,
    records_dir,
    safe_segment,
    write_records_dir,
)

VERDICTS = ("approve", "return", "abstain")
MIN_REASON_WORDS = 15


def panels_dir(project: Path, *, write: bool = False) -> Path:
    if write:
        return write_records_dir(project, "panels")
    return records_dir(project, "panels") or write_records_dir(project, "panels")


def refuse(reason: str) -> None:
    print(f"REFUSED: {reason}", file=sys.stderr)
    raise SystemExit(1)


def _artifact_digest(project: Path, relative: str) -> str:
    """The sha256 of the artifact as assigned, or "" when there is nothing to hash."""
    if not relative:
        return ""
    target = Path(relative)
    if not target.is_absolute():
        target = project / relative
    try:
        return hashlib.sha256(target.read_bytes()).hexdigest()
    except OSError:
        return ""


def _open_round(panel: dict, project: Path, *, reviewer: str, already: bool) -> None:
    """Archive the verdicts on the previous text, then rebind the record to the new one.

    `cycle-plan.md` has always described the loop — return, revise, re-score — and the
    only mechanism for the third step refused it. Sessions ran it by hand and left
    `<slug>-plan.roundN.json` files behind; a convention that exists solely as filenames
    somebody chose is one the next session re-derives.

    The shape is `/review`'s, for the same problem: a BLOCKER that is fixed and
    re-verified is marked CLOSED, keeping its severity, rather than deleted. A panel that
    hides having returned a document once destroys the record that the correction
    happened — which is the only evidence the revision was not cosmetic.

    Votes from seats that did NOT ask for a change are carried, because a reviewer who
    approved a document does not have to re-approve corrections they never objected to.
    They are carried MARKED: `carried_from_round` says which text that approval was
    about, so a tally cannot read three seats agreeing about one document when they
    agreed about two.

    The round boundary is the ARTIFACT CHANGING, not the flag. Superseding text that
    nobody touched is refused — otherwise the flag is the duplicate refusal with an extra
    argument, and a verdict somebody dislikes can be overwritten by re-casting it.
    """
    if not already:
        refuse(f"`{reviewer}` has not voted, so there is nothing to supersede. Cast the "
               "vote without `--supersede`")
    digest = _artifact_digest(project, panel.get("artifact", ""))
    recorded = panel.get("artifact_sha256")
    if recorded and digest and recorded == digest:
        refuse("the artifact has not changed since this panel voted, so a second "
               "verdict on identical text is the duplicate the tally refuses rather "
               "than a revision. Revise the document, then supersede")

    rounds = panel.setdefault("rounds", [])
    number = len(rounds) + 1
    rounds.append({"round": number, "artifact_sha256": recorded,
                   "votes": panel["votes"]})
    if digest:
        panel["artifact_sha256"] = digest
    else:
        panel.pop("artifact_sha256", None)
    panel["votes"] = [
        {**v, "carried_from_round": v.get("carried_from_round", number)}
        for v in rounds[-1]["votes"] if v.get("reviewer") != reviewer
    ]


def cast(project: Path, slug: str, phase: str, reviewer: str, model: str,
         verdict: str, reason: str, *, supersede: bool = False) -> dict:
    # `slug` and `phase` arrive from the CLI and become part of a filename that is
    # `mkdir -p`'d. `../` in either escaped the write root and created the directories on
    # the way. `safe_segment` refuses the spelling; `confined` refuses the result, so a
    # caller composing the name some other way is still held. See `squad/paths.py`.
    safe_segment(slug, what="--slug")
    safe_segment(phase, what="--phase")
    _panels = panels_dir(project)
    apath = confined(_panels / f"{slug}-{phase}.assignment.json", _panels,
                     what="the assignment")
    if not apath.is_file():
        print(f"no assignment at {apath} — nothing was recorded. A vote with no "
              "assignment behind it is a vote the tally refuses, and refusing it here "
              "costs one invocation instead of three.", file=sys.stderr)
        raise SystemExit(2)

    assignment = json.loads(apath.read_text(encoding="utf-8"))
    assigned = assignment.get("assigned", [])
    author = assignment.get("author", "")

    if verdict not in VERDICTS:
        refuse(f"`{verdict}` is not one of {', '.join(VERDICTS)}")
    if reviewer not in assigned:
        refuse(f"`{reviewer}` is not on this panel. Assigned: {', '.join(assigned)}. "
               "A vote from an unassigned reviewer is one the tally drops, and a panel "
               "short one vote is incomplete rather than approved")
    if author and reviewer == author:
        refuse(f"`{reviewer}` wrote this artifact. An author grading their own form is "
               "the failure the whole panel exists to prevent")
    if len(reason.split()) < MIN_REASON_WORDS:
        refuse(f"the reason is {len(reason.split())} word(s); the floor is "
               f"{MIN_REASON_WORDS}. Name WHAT you checked against WHICH evidence — "
               "a vote nobody can argue with is a vote nobody can overturn")

    _write_panels = panels_dir(project, write=True)
    record_path = confined(_write_panels / f"{slug}-{phase}.json", _write_panels,
                           what="the panel record")
    record_path.parent.mkdir(parents=True, exist_ok=True)

    # The read, the duplicate refusal and the write are ONE transaction. They were not:
    # the record was read, `panel["votes"]` inspected for this reviewer, and the whole
    # file rewritten — with nothing serialising the three. The panel seats THREE
    # reviewers whose invocations a session can issue at once, so two votes read the same
    # `votes` list and the second rewrite dropped the first vote. A panel short one vote
    # is incomplete, which is precisely what the refusal three lines down protects.
    with shared_file.locked(record_path):
        if record_path.is_file():
            panel = json.loads(record_path.read_text(encoding="utf-8"))
        else:
            relative = assignment.get("artifact", "")
            panel = {"slug": slug, "phase": phase, "author": author,
                     "artifact": relative,
                     "assigned": assigned, "votes": []}
            # WHICH VERSION, not just which file. `check_panel_approval._artifact_drifted`
            # compares this against the bytes on disk and treats its ABSENCE as "cannot
            # verify" — a deliberate allowance for records written before the field
            # existed. Nothing wrote it, so every record the mechanisms produced joined
            # that class and the closed set of legacy files kept growing. Measured
            # 2026-09-20: a record written at 13:09 approved a plan last edited at 20:04,
            # and the gate printed APPROVED with nothing a reader could act on.
            #
            # Written ONCE, when the record is created, because the hash belongs to the
            # PANEL and not to a seat: re-hashing on each vote would bind the approval to
            # the text only the last reviewer saw. An artifact edited mid-panel is drift,
            # which is the gate's finding to make and not this script's to repair.
            #
            # An absent path or an absent file yields NO key rather than a hash of
            # nothing: a record that looks bound and binds to nothing is worse than one
            # that admits it cannot be checked.
            digest = _artifact_digest(project, relative)
            if digest:
                panel["artifact_sha256"] = digest

        already = any(v.get("reviewer") == reviewer for v in panel["votes"])
        if already and not supersede:
            refuse(f"`{reviewer}` already voted. A second vote from one seat is a "
                   "duplicate the tally refuses. If the document was RETURNED and has "
                   "since been corrected, re-cast with `--supersede`, which opens a "
                   "round instead of overwriting the record")
        if supersede:
            _open_round(panel, project, reviewer=reviewer, already=already)

        panel["votes"].append({
            "reviewer": reviewer, "model": model, "verdict": verdict,
            "reason": reason.strip(),
            "cast_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        shared_file.write_atomic(record_path, json.dumps(panel, indent=2) + "\n")

    remaining = [a for a in assigned if a not in {v["reviewer"] for v in panel["votes"]}]
    return {"record": str(record_path), "votes": len(panel["votes"]),
            "of": len(assigned), "remaining": remaining}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--phase", required=True)
    ap.add_argument("--reviewer", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--verdict", required=True)
    ap.add_argument("--reason", required=True)
    ap.add_argument("--project", type=Path, default=Path("."))
    ap.add_argument(
        "--supersede", action="store_true",
        help="re-cast this seat's verdict on a CORRECTED artifact. Archives the "
             "verdicts on the previous text as a round rather than overwriting "
             "them, and is refused if the artifact has not changed")
    args = ap.parse_args(argv)

    out = cast(args.project.resolve(), args.slug, args.phase, args.reviewer,
               args.model, args.verdict, args.reason,
               supersede=args.supersede)
    print(f"recorded {out['votes']}/{out['of']} — {out['record']}")
    if out["remaining"]:
        print("  still to vote: " + ", ".join(out["remaining"]))
    else:
        print("  panel complete. Tally it:")
        print(f"    python3 mechanisms/cycle/review_panel.py --record {out['record']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
