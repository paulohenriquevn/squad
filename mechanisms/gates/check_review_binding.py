#!/usr/bin/env python3
"""Refuse to promote work whose review is about a different commit.

    python3 mechanisms/gates/check_review_binding.py --slug B-014

## The gap this closes

A review verdict says the work was examined. It does not say WHICH work: nothing
recorded the revision the reviewers read, so a commit landing after consolidation
travelled to `develop` carrying an approval that never saw it.

An external reviewer named the general shape: every approval bound to the exact
revision of code, plan, policy and evidence it approved. It is the same defect the panel
had about its artifact, one layer up — the approval was bound to a NAME, not to a
CONTENT.

## What it does, and what it cannot

It compares the commit a review recorded against the branch tip about to be promoted.
Equal is clean. Different is not automatically wrong — a docs-only commit after a review
is usually harmless — so this reports WHAT MOVED and refuses only when the moved files
overlap what the review examined. A gate that blocked on any movement would be bypassed
within a week, and a bypassed gate protects nothing.

It cannot tell you the review was CORRECT, and it cannot see two PRs that pass alone and
fail together — that is a merge-queue property, not a property of one branch. Both are
reported as unchecked rather than implied.

Exit codes:
  0  the review is bound to the tip, or nothing moved that it examined
  1  files the review examined changed after it ran
  2  nothing could be compared; that is not a pass
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from squad.paths import records_dir

BOUND, DRIFTED, UNCHECKED = 0, 1, 2


def _git(*args: str, cwd: Path) -> str | None:
    try:
        done = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                              text=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def _review_record(project: Path, slug: str) -> Path | None:
    directory = records_dir(project, "reviews")
    if directory is None:
        return None
    hits = sorted(directory.glob(f"{slug}-review-*.json"))
    return hits[-1] if hits else None


def check(slug: str, *, project: Path, tip: str = "HEAD") -> tuple[int, dict]:
    record = _review_record(project, slug)
    if record is None:
        return UNCHECKED, {
            "status": "no_record", "slug": slug,
            "detail": "no machine-readable review record, so nothing states which "
                      "revision was reviewed. An approval that names no commit cannot "
                      "be bound to one. NOTE: this reads "
                      "`{slug}-review-*.json` with a `reviewed_sha` field, and NOTHING "
                      "in this kit writes that file — `cycle-release.md` declares the "
                      "audit as `{slug}-review-{date}.md`, the review stage writes "
                      "markdown, and `reviewed_sha` appears nowhere outside this gate. "
                      "So this is not a record somebody forgot to produce: the input "
                      "format is declared only here, and this binding has never held "
                      "for any project. Measured on a consumer 2026-09-16: zero JSON "
                      "review records, a markdown one on disk for the same slug",
        }
    try:
        data = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return UNCHECKED, {"status": "unchecked", "slug": slug,
                           "detail": f"cannot read {record}: {exc}"}

    reviewed = data.get("reviewed_sha")
    examined = set(data.get("examined_files") or [])
    if not reviewed:
        return UNCHECKED, {
            "status": "unbound", "slug": slug, "record": str(record),
            "detail": "the review record carries no `reviewed_sha`. It says work was "
                      "examined and not which work",
        }

    head = _git("rev-parse", tip, cwd=project)
    if head is None:
        return UNCHECKED, {"status": "unchecked", "slug": slug,
                           "detail": f"cannot resolve {tip} in {project}"}
    if head == reviewed:
        return BOUND, {"status": "bound", "slug": slug, "sha": head,
                       "detail": "the tip is the revision the review read"}

    moved_raw = _git("diff", "--name-only", f"{reviewed}..{head}", cwd=project)
    if moved_raw is None:
        return UNCHECKED, {
            "status": "unchecked", "slug": slug,
            "detail": f"the review names {reviewed[:12]}, which this repository cannot "
                      "resolve. A commit nobody can produce is not a binding",
        }
    moved = {p for p in moved_raw.splitlines() if p}
    overlap = sorted(moved & examined) if examined else sorted(moved)

    body = {
        "slug": slug, "reviewed_sha": reviewed, "tip_sha": head,
        "moved": sorted(moved), "overlap": overlap,
        "not_checked": [
            "WHETHER THE REVIEW WAS RIGHT — this compares revisions, never findings",
            "WHETHER TWO BRANCHES PASS ALONE AND FAIL TOGETHER — that is a property of "
            "the integration, not of this branch, and belongs to a merge queue",
        ],
    }
    if not examined:
        body["not_checked"].append(
            "WHICH FILES THE REVIEW EXAMINED — the record lists none, so every moved "
            "file is treated as overlapping rather than assumed harmless")
    if not overlap:
        return BOUND, {**body, "status": "moved_elsewhere",
                       "detail": f"{len(moved)} file(s) changed after the review and "
                                 "none of them are files it examined"}
    return DRIFTED, {**body, "status": "drifted",
                     "detail": f"{len(overlap)} file(s) the review examined changed "
                               "after it ran. The approval is about a state that is no "
                               "longer what would be promoted"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--project", type=Path, default=Path.cwd())
    ap.add_argument("--tip", default="HEAD")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    code, result = check(args.slug, project=args.project, tip=args.tip)
    if args.json:
        print(json.dumps(result, indent=2))
        return code

    status = result["status"]
    stream = sys.stdout if code == BOUND else sys.stderr
    print(f"review binding: {status.upper()} — {result['detail']}", file=stream)
    for f in result.get("overlap", [])[:10]:
        print(f"  changed after the review: {f}", file=stream)
    for n in result.get("not_checked", []):
        print(f"  NOT CHECKED: {n}", file=stream)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
