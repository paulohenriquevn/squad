#!/usr/bin/env python3
"""When did this tree last verify itself, and does the answer still apply?

    python3 mechanisms/gates/check_verification_freshness.py
    python3 mechanisms/gates/check_verification_freshness.py --root . --json

## The question that cost fifteen minutes to ask

`run_slice_tests.sh` printed its verdict and exited. Nothing on disk said the suite had ever
run, on which commit, or with what result — so the only way to answer *is it green?* was to
run it again. Measured 2026-09-22: one session ran it four times in one day to answer that,
and two of the four answered about a tree that had moved underneath them.

The runner now writes `.squad/records/verification/last-run.json`. This reads it.

## It does not run the suite

A gate that verifies by verifying takes fifteen minutes and cannot be asked casually — which
is the property that made the question go unasked in the first place. This opens one file.

## Four states, and the last two are why it exists

    verified        the record names HEAD and nothing failed
    stale           the record is real and names a commit this tree has moved past
    failing         the record names HEAD and something failed
    interrupted     suites ended without reporting a failing test — a stopped run
    unattributable  the runner itself said the tree moved during that run
    never           no record — the suite has not run here since this gate existed
    unreadable      a record that cannot be parsed

`never` is NOT `failing`. A fresh clone has not verified itself and is not broken; a tree
whose last run failed is a different fact and a different action. Collapsing them would fire
on every new checkout, and a signal that always fires is the same as no signal.

`interrupted` is NOT `failing` either, and the distinction was measured on this tree: a
killed run left `failed_suites: 31, passed: 0, failed: 0`, and reporting that as `failing`
produced the detail "0 test(s) in 31 suite(s) failed" — self-contradictory, and read as
total breakage by anyone who does not stop on the zero. A suite counted as failed while
reporting no failing test did not fail; it did not finish.

`unattributable` exists because `tree_moved` is the runner saying its own result is about no
single state of the repository. Reading it as green would launder exactly what that flag
prevents.

Exit codes:
  0 — verified
  1 — stale, failing, interrupted, or unattributable: a result that does not apply, or
      applies and is red, or is not a result at all
  2 — never or unreadable: not measured, which is neither passing nor failing
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        sys.path.insert(0, str(_up))
        break

from squad.paths import write_records_dir  # noqa: E402 — post-bootstrap import

RECORD = "last-run.json"


def record_path(root: Path) -> Path:
    """Asked of the owner. A second spelling of where records live is a second place to
    get it wrong, and `squad.paths` is where the write root is decided."""
    return write_records_dir(root, "verification") / RECORD


def _head(root: Path) -> str | None:
    try:
        proc = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=False, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def check(root: Path) -> tuple[int, dict]:
    """The state of this tree's last recorded verification."""
    path = record_path(root)
    if not path.is_file():
        # Leads with "nothing" on purpose. `test_an_empty_tree_produces_a_report_that_
        # says_it_was_empty` reads this line, and its argument is the one this gate is
        # built on: a reader must be able to tell an empty sweep from a clean one, and a
        # message naming only the missing FILE reads like a path problem.
        return 2, {"state": "never", "detail":
                   f"nothing has been verified here — no {path.name} under {path.parent}. "
                   "The suite has not run in this tree since the record existed, which is "
                   "not the same as having run and failed"}
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return 2, {"state": "unreadable", "detail": f"{path}: {exc}"}

    recorded = str(rec.get("head") or "")
    head = _head(root)
    common = {"recorded_head": recorded, "head": head, "at": rec.get("at"),
              "passed": rec.get("passed"), "failed": rec.get("failed")}

    if rec.get("tree_moved"):
        return 1, {**common, "state": "unattributable", "detail":
                   "the runner recorded that HEAD or the working tree changed during that "
                   "run, so its result is about no single state of this repository"}
    if head is not None and recorded and recorded != head:
        return 1, {**common, "state": "stale", "detail":
                   f"the last run verified {recorded[:12]} and this tree is at "
                   f"{head[:12]}. What it proved is true of a commit that is not this one"}
    # A suite counted as failed while reporting no failing TEST did not fail — it did
    # not finish. Measured 2026-09-24 after a full run was killed externally: the record
    # read `failed_suites: 31, passed: 0, failed: 0`, and this reported `failing` with
    # the detail "0 test(s) in 31 suite(s) failed" — self-contradictory, and read as
    # total breakage by anyone who does not stop on the zero.
    #
    # Same argument as `unattributable` above: a run that says nothing about a single
    # state of the repository is not a verdict, and must not wear the vocabulary of the
    # one state a reader has to act on. Not a pass either — nothing was proved.
    _dead = int(rec.get("failed_suites") or 0)
    if _dead and not rec.get("failed"):
        return 1, {**common, "state": "interrupted", "detail":
                   f"{_dead} of {rec.get('suites')} suite(s) ended without reporting a "
                   "single failing test, which is what a stopped run looks like — not a "
                   "failing one. Nothing was proved about this tree; run the suite again"}
    if rec.get("failed") or rec.get("failed_suites"):
        return 1, {**common, "state": "failing", "detail":
                   f"{rec.get('failed')} test(s) in {rec.get('failed_suites')} suite(s) "
                   "failed on the last run, and this tree is still at that commit"}
    return 0, {**common, "state": "verified", "detail":
               f"{rec.get('passed')} test(s) passed at {recorded[:12] or 'an unrecorded head'}"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    code, report = check(args.root.resolve())
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{report['state'].upper()}: {report['detail']}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
