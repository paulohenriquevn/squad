#!/usr/bin/env python3
"""Compute the acceptance verdict from the recorded evidence — never from a claim.

The whole point of this cycle is that `[x]` on a roadmap milestone means a human
could have watched the delivered thing work. So the verdict is derived here,
mechanically, from an evidence record; the agent that ran the journeys does not
get to assert it.

The one rule everything else follows from: **a criterion marked `passed` with no
evidence is not a pass.** It is refused as `NOT_VALIDATED`, which is deliberately
a different verdict from `REJECTED` — "we could not check" and "we checked and it
is broken" are different facts, and collapsing them is how a cycle starts lying.

Evidence record (JSON):

    {"milestone_id": "M2",
     "target": {"kind": "web", "url": "https://app.example.com"},
     "results": [
       {"id": "AC1", "status": "passed",
        "evidence": ["records/acceptance/evidence/M2-AC1-checkout.png"],
        "note": "checkout completed, 200 on POST /orders"}
     ],
     "defects": [{"severity": "minor", "summary": "...", "issue": "#412"}]}

`status` ∈ passed | failed | blocked | not_exercised.
`defects[].severity` ∈ blocker | major | minor.

Usage:
    python3 compute_acceptance_verdict.py --criteria criteria.json --evidence evidence.json

Exit codes:
    0 — ACCEPTED or ACCEPTED_WITH_CAVEATS (verdict on stdout)
    1 — REJECTED or NOT_VALIDATED (verdict on stdout, reasons on stderr)
    2 — file not found / malformed input
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VALID_STATUSES = {"passed", "failed", "blocked", "not_exercised"}
VALID_SEVERITIES = {"blocker", "major", "minor"}

ACCEPTED = "ACCEPTED"
ACCEPTED_WITH_CAVEATS = "ACCEPTED_WITH_CAVEATS"
REJECTED = "REJECTED"
NOT_VALIDATED = "NOT_VALIDATED"

#: Verdicts that allow cycle-roadmap to flip the milestone checkbox to [x].
#: Every exit derives `flip_allowed` from this set rather than restating it, so
#: adding a verdict here cannot leave a stale literal answering the old way.
FLIP_ALLOWED = {ACCEPTED, ACCEPTED_WITH_CAVEATS}


class MalformedEvidence(Exception):
    """The evidence record cannot be interpreted at all."""


def _cited_paths(result: dict) -> list[str]:
    evidence = result.get("evidence") or []
    if isinstance(evidence, str):
        evidence = [evidence]
    return [str(item).strip() for item in evidence if str(item).strip()]


def _has_evidence(result: dict) -> bool:
    return bool(_cited_paths(result))


def _unresolved_evidence(result: dict, root: Path | None) -> list[str]:
    """Cited paths that are not a readable, non-empty file under `root`.

    WHY THIS EXISTS. The rule's phase-contract table gates the `record` phase on
    "evidence files exist at the cited paths", and the skill repeats "the paths must
    resolve". Nothing resolved anything: `_has_evidence` asked whether the list held a
    non-empty STRING, so `evidence=["e/x.png"]` returned ACCEPTED with no such file.
    The one gate the rule says the whole cycle rests on was satisfied by typing a
    plausible filename.

    A zero-byte file counts as unresolved. A failed screen capture leaves one, and it
    reads as a successful capture to everything downstream — the shape of "an inability
    to measure reported as a measurement" that this cycle exists to refuse.
    """
    if root is None:
        return []
    unresolved = []
    for cited in _cited_paths(result):
        candidate = Path(cited)
        if not candidate.is_absolute():
            candidate = root / candidate
        try:
            if not candidate.is_file() or candidate.stat().st_size == 0:
                unresolved.append(cited)
        except OSError:
            unresolved.append(cited)
    return unresolved


def _validate_shapes(results: list[dict], defects: list[dict]) -> None:
    for result in results:
        if "id" not in result:
            raise MalformedEvidence(f"a result has no `id`: {result!r}")
        status = result.get("status")
        if status not in VALID_STATUSES:
            raise MalformedEvidence(
                f"{result['id']}: status {status!r} is not one of {sorted(VALID_STATUSES)}."
            )
    for defect in defects:
        severity = defect.get("severity")
        if severity not in VALID_SEVERITIES:
            raise MalformedEvidence(
                f"defect severity {severity!r} is not one of {sorted(VALID_SEVERITIES)}."
            )


def compute(criteria: list[dict], results: list[dict], defects: list[dict],
            evidence_root: Path | None = None) -> dict:
    """Return {verdict, reasons, flip_allowed} for the criteria/evidence pair.

    `evidence_root` is where cited paths are resolved from. `None` means the caller
    could not say — the paths are then checked for presence only, and the caller is
    responsible for reporting that it did not verify them.
    """
    _validate_shapes(results, defects)

    if not criteria:
        # NOT_VALIDATED, never ACCEPTED. With no criteria the function fell through to
        # the final return and announced "all 0 criteria exercised and evidenced in the
        # live system" — a sentence that is true and means nothing, attached to the
        # verdict that flips the milestone checkbox. A release nobody wrote criteria for
        # has not been accepted; it has not been checked. `NOT_VALIDATED` already exists
        # for exactly this and is outside `FLIP_ALLOWED`.
        return {"verdict": NOT_VALIDATED,
                "reasons": ["no acceptance criteria were supplied, so nothing was "
                            "validated. This is not an acceptance: it is the absence "
                            "of one."],
                "flip_allowed": NOT_VALIDATED in FLIP_ALLOWED}

    by_id = {result["id"]: result for result in results}
    reasons: list[str] = []

    missing = [c["id"] for c in criteria if c["id"] not in by_id]
    unexercised = [
        c["id"]
        for c in criteria
        if by_id.get(c["id"], {}).get("status") in {"not_exercised", "blocked"}
    ]
    unevidenced = [
        c["id"]
        for c in criteria
        if by_id.get(c["id"], {}).get("status") == "passed" and not _has_evidence(by_id[c["id"]])
    ]

    for criterion_id in missing:
        reasons.append(f"{criterion_id}: no result recorded — the criterion was never exercised.")
    for criterion_id in unexercised:
        status = by_id[criterion_id]["status"]
        reasons.append(f"{criterion_id}: {status} — the live system was not exercised for it.")
    unresolved = {
        c["id"]: _unresolved_evidence(by_id[c["id"]], evidence_root)
        for c in criteria
        if by_id.get(c["id"], {}).get("status") == "passed" and _has_evidence(by_id.get(c["id"], {}))
    }
    unresolved = {cid: paths for cid, paths in unresolved.items() if paths}

    for criterion_id in unevidenced:
        reasons.append(
            f"{criterion_id}: marked passed with no evidence — an asserted pass is not a pass."
        )
    for criterion_id, paths in unresolved.items():
        reasons.append(
            f"{criterion_id}: cited evidence does not resolve to a readable, non-empty "
            f"file: {', '.join(paths)} — a path is not a capture."
        )

    if missing or unexercised or unevidenced or unresolved:
        return {"verdict": NOT_VALIDATED, "reasons": reasons,
                "flip_allowed": NOT_VALIDATED in FLIP_ALLOWED}

    failed = [c["id"] for c in criteria if by_id[c["id"]]["status"] == "failed"]
    blocker_defects = [d for d in defects if d.get("severity") == "blocker"]

    if failed:
        for criterion_id in failed:
            note = by_id[criterion_id].get("note", "")
            reasons.append(f"{criterion_id}: failed in the live system. {note}".strip())
    for defect in blocker_defects:
        reasons.append(f"blocker defect: {defect.get('summary', '(no summary)')}")

    if failed or blocker_defects:
        return {"verdict": REJECTED, "reasons": reasons,
                "flip_allowed": REJECTED in FLIP_ALLOWED}

    if defects:
        for defect in defects:
            reasons.append(
                f"{defect.get('severity')} defect: {defect.get('summary', '(no summary)')} "
                f"[{defect.get('issue', 'NO ISSUE FILED')}]"
            )
        return {"verdict": ACCEPTED_WITH_CAVEATS, "reasons": reasons,
                "flip_allowed": ACCEPTED_WITH_CAVEATS in FLIP_ALLOWED}

    return {
        "verdict": ACCEPTED,
        "reasons": [f"all {len(criteria)} criteria exercised and evidenced in the live system."],
        "flip_allowed": ACCEPTED in FLIP_ALLOWED,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--criteria", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument(
        "--evidence-root", type=Path, default=None,
        help="directory the cited evidence paths resolve against "
             "(default: the evidence record's own directory)")
    parser.add_argument(
        "--milestone", default="",
        help="milestone id (M<N>) recorded on the phase event; optional, and "
             "deliberately not derived from the criteria filename — guessing an "
             "identifier is how a record ends up pointing at the wrong milestone",
    )
    args = parser.parse_args()

    # Begun once the inputs are known to exist. Before that a missing file is a bad
    # invocation, not a phase — and a start recorded for a run that never had anything
    # to read would leave an open phase nothing can close.
    _emit_phase_start(args.criteria, cycle="acceptance", slug=args.milestone or "")

    for path in (args.criteria, args.evidence):
        if not path.exists():
            print(f"file not found: {path}", file=sys.stderr)
            return 2

    try:
        criteria_doc = json.loads(args.criteria.read_text(encoding="utf-8"))
        evidence_doc = json.loads(args.evidence.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"malformed JSON: {exc}", file=sys.stderr)
        return 2

    # A JSON document of the wrong SHAPE is not malformed JSON, and it used to raise
    # `AttributeError: 'list' object has no attribute 'get'` — a traceback, which reads
    # as "this tool is broken" when the honest answer is "your file is a list and this
    # expects an object". The two need different actions from whoever runs the phase.
    #
    # This kit has met the same failure before: `select_backlog_item` answered every
    # `--check` against an approved item with a KeyError, and the comment there says it
    # exactly — a traceback is the wrong silence.
    for name, doc, key in (("--criteria", criteria_doc, "criteria"),
                           ("--evidence", evidence_doc, "results")):
        if not isinstance(doc, dict):
            print(f"malformed {name} document: expected a JSON object with a"
                  f" {key!r} key, got {type(doc).__name__}", file=sys.stderr)
            return 2

    criteria = criteria_doc.get("criteria", [])
    if not criteria:
        print("NOT_VALIDATED cycle-acceptance: no criteria to validate.", file=sys.stderr)
        return 1

    try:
        # Default to the record's own directory: a record cites its evidence relative
        # to itself, and resolving against the process's cwd would pass or fail
        # depending on where the script was invoked from.
        root = args.evidence_root or args.evidence.resolve().parent
        if not root.is_dir():
            print("NOT_VALIDATED", flush=True)
            print(f"evidence root {root} is not a directory, so no cited path could be "
                  f"checked. An inability to verify evidence is not a verified pass.",
                  file=sys.stderr)
            return 1
        outcome = compute(criteria, evidence_doc.get("results", []),
                          evidence_doc.get("defects", []), evidence_root=root)
    except MalformedEvidence as exc:
        print(f"malformed evidence record: {exc}", file=sys.stderr)
        return 2

    print(outcome["verdict"])
    for reason in outcome["reasons"]:
        print(f"  - {reason}", file=sys.stderr)

    # Rooted at the criteria file, not cwd: the phase belongs to the project
    # whose milestone was graded, whatever directory the caller ran from.
    _emit_phase_end(
        args.criteria, cycle="acceptance", slug=args.milestone or "",
        verdict=outcome["verdict"], flip_allowed=outcome["flip_allowed"],
    )

    return 0 if outcome["flip_allowed"] else 1


def _emit_phase_start(project_root, *, cycle: str, slug: str) -> None:
    """Record that the phase began. Same contract as `_emit_phase_end`: bookkeeping
    never fails the phase, and an ImportError is reported rather than swallowed into a
    silence that looks like a phase nobody ran.

    Emitted BEFORE the work. A run that dies mid-phase then leaves a start with no end,
    which is what an interrupted phase is; recording it only on success would draw the
    stream as though nothing had been attempted.
    """
    from pathlib import Path as _Path
    tooling = _Path(__file__).resolve().parents[3] / "mechanisms" / "cycle"
    if str(tooling) not in sys.path:
        sys.path.insert(0, str(tooling))
    try:
        from cycle_events import emit_phase_start, project_root_for
    except ImportError as error:
        print(f"cycle-events: emitter unavailable ({error})", file=sys.stderr)
        return
    emit_phase_start(project_root_for(project_root), cycle=cycle, slug=slug)


def _emit_phase_end(project_root, *, cycle: str, slug: str, verdict, **extra) -> None:
    """Record the phase transition; never let bookkeeping fail the phase.

    `scripts/` resolves against THIS FILE, not the audited project: in a plugin
    install the kit lives under `.claude/` while the project is elsewhere.
    `ImportError` is caught alone — a bare `except Exception` would swallow a
    real emitter bug into a silence indistinguishable from a phase that never
    ran, which is the defect the stream exists to remove.
    """
    from pathlib import Path as _Path
    tooling = _Path(__file__).resolve().parents[3] / "mechanisms" / "cycle"
    if str(tooling) not in sys.path:
        sys.path.insert(0, str(tooling))
    try:
        from cycle_events import emit_phase_end, project_root_for
    except ImportError as error:
        print(f"cycle-events: emitter unavailable ({error})", file=sys.stderr)
        return
    emit_phase_end(project_root_for(project_root), cycle=cycle, slug=slug,
                   verdict=verdict, **extra)


if __name__ == "__main__":
    sys.exit(main())
