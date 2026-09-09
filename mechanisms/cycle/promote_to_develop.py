#!/usr/bin/env python3
"""Promote `workspace` to `develop`, and do nothing else.

WHY THIS EXISTS SEPARATELY FROM `/release`
------------------------------------------
`git-safety.md` § 1 says `develop` advances ONLY by promoting `workspace` through a PR.
Until 2026-09-09 the single place in this kit that opened that PR was the middle of
`cycle-release.md`'s chain — between the version bump and the tag:

    open PR workspace → develop; merge it     <- the promotion
    open PR develop → main                    <- the cut
    create annotated tag                      <- the version

Promotion and cut were one command, so **integrating required versioning**. A project
that did not want to publish a version simply did not integrate.

Measured on this repository: **349 commits on `workspace`, zero tags.** Work that was
finished, reviewed and verified sat unreachable, and 45 issues were closed against the
kit's own lifecycle rule because there was no version to name in the closing note.

Splitting the two is what lets integration be frequent and cheap while a version stays
cadenced — which is the whole argument for the two cuts `cycle-release.md` already
describes (`-rc.N` when the queue dries up, `X.Y.Z` when a milestone closes).

WHAT IT REFUSES TO DO
---------------------
It moves no version, writes no CHANGELOG section and cuts no tag. A promotion that
bumps is a release wearing another name, and `tests/test_promote_to_develop.py` asserts
this file never reaches for those scripts.

Exit codes:
    0 — promoted, or there was nothing to promote (both are answers)
    1 — refused: the branch, the tree or the repository is not in a promotable state
    2 — could not measure: `gh` absent, unauthenticated, or git unreadable
    3 — the PR is open and merging needs a human (branch protection), which is a
        premise reported at intake rather than a per-run failure
"""
from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

Runner = Callable[[list[str]], "tuple[int, str, str]"]

OK = 0
REFUSED = 1
UNMEASURED = 2
AWAITING = 3

#: The two branches this mechanism knows. Taken from `git-safety.md`'s flow rather than
#: made configurable: a kit whose promotion target is a parameter is a kit where the
#: flow it documents is a suggestion.
SOURCE = "workspace"
TARGET = "develop"


@dataclass
class Report:
    lines: list[str] = field(default_factory=list)
    exit_code: int = OK
    detail: dict = field(default_factory=dict)


def _runner(root: Path, program: str) -> Runner:
    def run(argv: list[str]) -> tuple[int, str, str]:
        done = subprocess.run(  # noqa: PLW1510
            [program, *argv], capture_output=True, text=True, cwd=root, timeout=120
        )
        return done.returncode, done.stdout, done.stderr

    return run


def promote(
    root: Path,
    *,
    git: Runner | None = None,
    gh: Runner | None = None,
    dry_run: bool = False,
) -> Report:
    """Open (and try to merge) the promotion PR. Injected runners keep tests offline."""
    git = git or _runner(root, "git")
    gh = gh or _runner(root, "gh")
    report = Report()

    def call(runner: Runner, argv: list[str]) -> tuple[int, str, str] | None:
        try:
            return runner(argv)
        except (OSError, subprocess.SubprocessError) as exc:
            report.lines.append(f"could not run {argv[0] if argv else '?'}: {exc}")
            return None

    branch = call(git, ["rev-parse", "--abbrev-ref", "HEAD"])
    if branch is None or branch[0] != 0:
        report.exit_code = UNMEASURED
        report.lines.append("git could not report the current branch")
        return report

    current = branch[1].strip()
    if current != SOURCE:
        # `develop` integrates and never originates. Promoting from anywhere else would
        # either author on the target or carry work that did not start where the flow says.
        report.exit_code = REFUSED
        report.lines.append(
            f"on {current!r}, and only {SOURCE!r} is promotable — git-safety.md § 1"
        )
        return report

    status = call(git, ["status", "--porcelain"])
    if status is None or status[0] != 0:
        report.exit_code = UNMEASURED
        report.lines.append("git could not report the working tree state")
        return report
    if status[1].strip():
        n = len(status[1].strip().splitlines())
        report.exit_code = REFUSED
        report.lines.append(
            f"{n} uncommitted change(s): a dirty tree promotes a state nobody reviewed"
        )
        return report

    ahead = call(git, ["rev-list", "--count", f"origin/{TARGET}..HEAD"])
    if ahead is None or ahead[0] != 0:
        report.exit_code = UNMEASURED
        report.lines.append(f"could not count commits ahead of origin/{TARGET}")
        return report

    count = ahead[1].strip()
    report.detail["ahead"] = count
    if count == "0":
        # Not a failure: `develop` already carries everything. Saying so is the answer.
        report.lines.append(f"nothing to promote — origin/{TARGET} already has this branch")
        return report

    report.lines.append(f"{count} commit(s) ahead of origin/{TARGET}")

    existing = call(gh, ["pr", "list", "--base", TARGET, "--head", SOURCE,
                         "--state", "open", "--json", "number,url"])
    if existing is None:
        report.exit_code = UNMEASURED
        return report
    if existing[0] != 0:
        report.exit_code = UNMEASURED
        report.lines.append(f"gh refused: {existing[2].strip() or 'no message'}")
        return report

    try:
        open_prs = json.loads(existing[1] or "[]")
    except json.JSONDecodeError:
        report.exit_code = UNMEASURED
        report.lines.append("gh returned output that is not JSON")
        return report

    if dry_run:
        report.lines.append(
            f"--dry-run: would {'reuse PR #' + str(open_prs[0]['number']) if open_prs else 'open a PR'}"
            f" and try to merge it"
        )
        return report

    if open_prs:
        number = open_prs[0]["number"]
        report.lines.append(f"reusing open PR #{number} — a second one would split the review")
    else:
        created = call(gh, ["pr", "create", "--base", TARGET, "--head", SOURCE,
                            "--title", f"promote: {SOURCE} → {TARGET}",
                            "--body", f"Promotion of {count} commit(s). No version is cut "
                                      f"here — see rules/cycle-release.md § Two cuts."])
        if created is None or created[0] != 0:
            report.exit_code = UNMEASURED
            report.lines.append(
                f"could not open the PR: {created[2].strip() if created else 'gh unavailable'}"
            )
            return report
        url = created[1].strip().splitlines()[-1] if created[1].strip() else ""
        number = url.rsplit("/", 1)[-1] if url else "?"
        report.lines.append(f"opened PR #{number}  {url}")

    report.detail["pr"] = str(number)

    merged = call(gh, ["pr", "merge", str(number), "--merge"])
    if merged is None:
        report.exit_code = UNMEASURED
        return report
    if merged[0] != 0:
        # Branch protection wanting a reviewer is a premise about the repository, which
        # `check_merge_autonomy.py` reports at intake. Per-run it is a state, not a fault.
        report.exit_code = AWAITING
        report.lines.append(f"PR #{number} is open and could not be merged automatically")
        report.lines.append(f"  {merged[2].strip() or 'no message from gh'}")
        return report

    report.lines.append(f"merged PR #{number} — {TARGET} now carries this work")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="promote_to_develop", description=__doc__.split("\n")[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would happen without opening or merging anything")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = promote(args.root, dry_run=args.dry_run)
    if args.json:
        print(json.dumps({"exit_code": report.exit_code, "lines": report.lines,
                          **report.detail}, indent=2, ensure_ascii=False))
    else:
        for line in report.lines:
            print(line)
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
