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

Measured on this repository on 2026-09-09, before this file existed: **349 commits on
`workspace`, zero tags.** Work that was finished, reviewed and verified sat unreachable,
and 45 issues were closed against the kit's own lifecycle rule because there was no
version to name in the closing note.

That backlog of commits was promoted the same day, by this mechanism, in one command and
without cutting a version — which is the whole argument for the split, exercised once.

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
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from squad.paths import records_dir

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


def _reviews_that_drifted(project: Path) -> tuple[list[str], int]:
    """Slugs whose review examined files that changed after it ran.

    Empty when nothing drifted AND when nothing can be checked — an absent review
    record is `check_review_binding`'s own `UNCHECKED`, and promotion is not the place
    to invent a review requirement the cycle does not state. What this refuses is a
    review that exists and no longer describes the branch.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gates"))
    try:
        from check_review_binding import DRIFTED, check
    except ImportError:  # pragma: no cover - environment, not logic
        return [], 0

    directory = records_dir(project, "reviews")
    if directory is None:
        return [], 0
    drifted: list[str] = []
    records = sorted(directory.glob("*-review-*.json"))
    for record in records:
        slug = record.name.split("-review-")[0]
        if slug in drifted:
            continue
        code, _ = check(slug, project=project)
        if code == DRIFTED:
            drifted.append(slug)
    return drifted, len(records)



def _owner_repo(call, git) -> str | None:
    """`owner/name` from the push remote, for `gh -R`.

    Reads the URL rather than asking `gh`, because asking `gh` is the thing that fails:
    it cannot resolve an SSH host alias, and the alias is exactly the case this exists
    for. Both URL shapes carry the slug in the same place —
    `git@host:owner/repo.git` and `https://host/owner/repo.git` — so the parse is the
    tail, not the host.

    None when the remote is absent or shaped like neither, which leaves the call unscoped
    and the behaviour exactly as it was.
    """
    result = call(git, ["remote", "get-url", "origin"])
    if result is None or result[0] != 0:
        return None
    url = result[1].strip()
    # The host part is everything before the first `/`. If it carries a `:`, the slug
    # starts after it — that covers `git@host:owner/repo`, `host:owner/repo` (an alias
    # with the user in ssh config, which is the shape measured on the consumer) and
    # `ssh://host:22/owner/repo`. An `https://` URL has `:` in the scheme, so the scheme
    # is stripped first or the parse would start after `//`.
    stripped = re.sub(r"^[a-z][a-z0-9+.-]*://", "", url, flags=re.IGNORECASE)
    head, _, rest = stripped.partition("/")
    tail = (head.split(":", 1)[1] + "/" + rest) if ":" in head else stripped
    tail = tail.rstrip("/").removesuffix(".git")
    parts = [p for p in tail.split("/") if p]
    return "/".join(parts[-2:]) if len(parts) >= 2 else None


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

    # `--untracked-files=no`. A promotion is a MERGE OF COMMITS, and an untracked file is
    # in no commit — so it cannot affect what this gate guards, and counting it refuses on
    # a condition that cannot occur.
    #
    # Measured on a consumer 2026-09-16, holding the first item ever to cross the whole
    # chain: 12 entries from `git status --porcelain`, ALL of them `??`, and
    # `--untracked-files=no` returning nothing. Among the twelve was
    # `.squad/wiki/decisions/...` — and `.gitignore` un-ignores `.squad/wiki/` ON PURPOSE,
    # because `records-location.md` calls it durable knowledge that should be versioned.
    #
    # So the kit's own designed output directory made the kit's own promotion gate refuse,
    # and every consumer that has written one wiki document hits it on its first
    # promotion, forever, told that their tree "promotes a state nobody reviewed".
    status = call(git, ["status", "--porcelain", "--untracked-files=no"])
    if status is None or status[0] != 0:
        report.exit_code = UNMEASURED
        report.lines.append("git could not report the working tree state")
        return report
    if status[1].strip():
        n = len(status[1].strip().splitlines())
        report.exit_code = REFUSED
        report.lines.append(
            f"{n} uncommitted change(s) to TRACKED files: a dirty tree promotes a state "
            f"nobody reviewed"
        )
        return report

    # Untracked files are still worth SAYING — one may be work somebody forgot to add —
    # but a warning is what that is, not a refusal. The caution and the trigger are
    # separate facts and the old message merged them.
    untracked = call(git, ["ls-files", "--others", "--exclude-standard"])
    if untracked is not None and untracked[0] == 0 and untracked[1].strip():
        paths = untracked[1].strip().splitlines()
        shown = ", ".join(paths[:4]) + ("…" if len(paths) > 4 else "")
        report.lines.append(
            f"WARNING: {len(paths)} untracked file(s) will not travel with this "
            f"promotion — {shown}. Not a refusal: a merge carries commits, and these are "
            f"in none. Check whether any is work you meant to add."
        )

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

    # Promotion is where reviewed work leaves the branch, so it is where a review that
    # no longer describes the branch has to be caught. A commit landing after
    # consolidation would otherwise travel to `develop` on an approval that never saw
    # it — the approval was bound to a NAME, not to a CONTENT.
    drifted, reviews_examined = _reviews_that_drifted(Path.cwd())
    if not reviews_examined:
        # Say it rather than let silence read as "the reviews were fine".
        report.lines.append(
            "review drift: 0 record(s) examined — no `*-review-*.json` on disk, so no "
            "review was bound to a commit. Not a refusal; the cycle does not require "
            "one here. It is also not a check that passed.")
    if drifted:
        report.exit_code = REFUSED
        report.lines.append(
            f"{len(drifted)} review(s) no longer describe this branch: "
            + ", ".join(drifted)
        )
        report.lines.append(
            "Re-review the slice, or record a new review bound to the tip. Promoting "
            "would carry an approval about a state that is not what ships."
        )
        return report

    # `-R OWNER/NAME`, derived from the remote rather than inferred by `gh`.
    #
    # An SSH host alias — `git@<alias>:<owner>/<repo>.git`, what anyone with two GitHub
    # identities on one machine ends up with — defeats every unaided `gh` call with "none
    # of the git remotes point to a known GitHub host". Measured on a consumer 2026-09-16,
    # holding the first item ever to cross the whole chain, one flag from `develop`:
    # `gh pr list -R <owner>/<repo>` answered correctly in the same minute the unaided
    # call refused.
    #
    # The kit already solved this once. `board_issues.py` takes `--issues-repo OWNER/NAME`
    # for exactly this cause and says so in its own words — "it is produced by an SSH host
    # alias, and the fix is one flag away". The promotion inferred where the board
    # declares, and the two are the same repository.
    repo_slug = _owner_repo(call, git)
    scoped = ["-R", repo_slug] if repo_slug else []

    existing = call(gh, ["pr", "list", *scoped, "--base", TARGET, "--head", SOURCE,
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
        created = call(gh, ["pr", "create", *scoped, "--base", TARGET, "--head", SOURCE,
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
