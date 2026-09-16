#!/usr/bin/env python3
"""The tracker's half of the picture: what is filed, what is fixed, and what shipped.

    python3 skills/backlog-review/scripts/board_issues.py [project] [--repo OWNER/NAME]

`BACKLOG.md` says what this project decided to do. The issue tracker says what the
people using it ran into. The board showed the first and not the second, so a reader
watching the cycle advance had no way to see that fourteen reports were sitting open
against the very code the cycle was advancing.

## Why the stages here are labels rather than a state field

GitHub has two states: OPEN and CLOSED. That is not enough to see a fix travel, because
the interesting gap is between "the fix is merged" and "the fix is installable" — a
window in which the issue must stay open, since closing it tells whoever is blocked that
the problem is over while `npm install` still hands them the bug.

So the stages are read from labels, which is where that distinction is already recorded:

    filed         open, no stage label   nobody has claimed it yet
    in-workspace  merged to the working branch, not integrated
    in-develop    merged to the integration branch — validate here
    released      closed, naming the version it went out in

A project using different label names gets `filed` for everything, which is wrong but
honest: it under-claims rather than inventing a position. `STAGE_LABELS` is the one
place to change.

## What this module refuses to do

It never reports zero when it could not look. `gh` missing, `gh` unauthenticated, a
remote that is not a known GitHub host, a timeout, no network — each returns `ok=False`
carrying the reason and, where one exists, the flag that fixes it. An empty tracker and
an unreachable tracker render differently on the board, because they are different
facts, and the ecosystem-wide rule is that an inability to measure must never become a
passing measurement.

It also never reads issue bodies. The board already serves an unreleased roadmap to
whoever holds the token; issue bodies would widen that surface for nothing the board
displays. Titles, labels, numbers and timestamps are the whole payload.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path

#: Stage order, and the label that puts an issue in each. The first entry is the
#: fallback for an open issue carrying none of the others; the last is every closed
#: issue regardless of labels. Order is the order a fix travels, which is the order
#: the board draws the lanes in.
STAGE_LABELS: tuple[tuple[str, str | None], ...] = (
    ("filed", None),
    ("in-workspace", "in-workspace"),
    ("in-develop", "in-develop"),
    ("released", None),
)

STAGES = tuple(name for name, _ in STAGE_LABELS)

#: The fields asked of `gh`. Deliberately no `body`: see the module docstring.
_FIELDS = "number,title,state,labels,url,updatedAt,assignees"

#: Anything that looks like a GitHub credential, should one ever reach stderr. The
#: board renders `reason` verbatim, so a token echoed by a failing subprocess would be
#: published to the page. Cheap to strip, expensive to discover in a screenshot.
_SECRETISH = re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{20,})")

#: How much of a failure to keep. Enough to name the cause, short enough that the
#: board stays a board.
_REASON_MAX = 400


def _clean(text: str) -> str:
    return _SECRETISH.sub("<redacted>", " ".join(text.split()))[:_REASON_MAX]


def _diagnose(stderr: str) -> tuple[str, str]:
    """Turn `gh`'s stderr into (reason, remedy) a reader can act on.

    The remedy half is why this is not just a passthrough. "none of the git remotes
    configured for this repository point to a known GitHub host" is a true sentence
    that leaves the reader nowhere; it is produced by an SSH host alias, and the fix is
    one flag away. Measured against a real project whose remote is
    an SSH host alias (`git@<alias>:<owner>/<repo>.git`), where every unaided `gh` call
    fails this way.
    """
    low = stderr.lower()
    if "none of the git remotes" in low or "not a git repository" in low:
        return (_clean(stderr),
                "name the repository explicitly: --issues-repo OWNER/NAME")
    if "gh auth login" in low or "authentication" in low or "http 401" in low:
        return _clean(stderr), "authenticate the CLI: gh auth login"
    if "could not resolve" in low or "dial tcp" in low or "network" in low:
        return _clean(stderr), "the tracker was unreachable; the board keeps the last good read"
    if "http 404" in low:
        return (_clean(stderr),
                "the repository does not exist or the token cannot see it")
    return _clean(stderr) or "gh failed without writing a reason", ""


def _stage(issue: dict) -> str:
    if (issue.get("state") or "").upper() == "CLOSED":
        return "released"
    names = {(lab.get("name") or "") for lab in issue.get("labels") or []}
    # Latest stage wins: an issue labelled both `in-workspace` and `in-develop` has
    # travelled to develop, and drawing it in the earlier lane would report the fix as
    # less far along than it is.
    for name, label in reversed(STAGE_LABELS):
        if label and label in names:
            return name
    return "filed"


def fetch(project: Path, repo: str | None = None, limit: int = 200,
          timeout: float = 25.0) -> dict:
    """Read the tracker once. Never raises — every failure becomes `ok=False`."""
    cmd = ["gh", "issue", "list", "--state", "all",
           "--limit", str(limit), "--json", _FIELDS]
    # An explicit `--issues-repo` wins. Otherwise scope the call when the remote is a
    # GitHub URL `gh` cannot parse for itself — an SSH host alias. Without this the whole
    # panel went dark against a repository that was on GitHub the entire time, and the
    # remedy printed in its place asked the operator to retype what the remote already
    # said. Derived is better than demanded when the answer is on disk.
    repo = repo or _owner_repo_from_remote(project)
    if repo:
        cmd += ["--repo", repo]
    started = time.time()
    try:
        # check=False deliberately: a non-zero exit is the interesting case here,
        # diagnosed into a reason the board can render rather than raised.
        proc = subprocess.run(cmd, cwd=str(project), capture_output=True,
                              text=True, timeout=timeout, check=False)
    except FileNotFoundError:
        return _failed(repo, "the GitHub CLI is not installed",
                       "install `gh`, or start the board with --no-issues")
    except subprocess.TimeoutExpired:
        return _failed(repo, f"gh did not answer within {timeout:.0f}s",
                       "raise --issues-timeout, or start the board with --no-issues")
    except OSError as exc:  # pragma: no cover - platform-specific
        return _failed(repo, _clean(str(exc)), "")
    if proc.returncode != 0:
        reason, remedy = _diagnose(proc.stderr or "")
        return _failed(repo, reason, remedy)
    try:
        raw = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as exc:
        return _failed(repo, f"gh returned output that is not JSON: {_clean(str(exc))}", "")

    issues = []
    for item in raw:
        issues.append({
            "number": item.get("number"),
            "title": item.get("title") or "",
            "state": (item.get("state") or "").upper(),
            "labels": sorted((lab.get("name") or "") for lab in item.get("labels") or []),
            "url": item.get("url") or "",
            "updated_at": item.get("updatedAt") or "",
            "assignees": sorted((a.get("login") or "")
                                for a in item.get("assignees") or []),
            "stage": _stage(item),
        })
    issues.sort(key=lambda d: -(d["number"] or 0))
    counts = {stage: sum(1 for i in issues if i["stage"] == stage) for stage in STAGES}
    return {
        "ok": True,
        "reason": "",
        "remedy": "",
        "repo": repo or _repo_of(project),
        "stages": list(STAGES),
        "issues": issues,
        "counts": counts,
        "open": sum(1 for i in issues if i["state"] == "OPEN"),
        "fetched_at": time.time(),
        "took_seconds": round(time.time() - started, 2),
    }


def _failed(repo: str | None, reason: str, remedy: str) -> dict:
    """A read that did not happen, shaped like one that did.

    Same keys, empty collections, `ok=False`. The board branches on `ok` and never has
    to ask whether a missing key means zero issues or no answer.
    """
    return {"ok": False, "reason": reason, "remedy": remedy, "repo": repo or "",
            "stages": list(STAGES), "issues": [], "counts": {s: 0 for s in STAGES},
            "open": 0, "fetched_at": time.time(), "took_seconds": 0.0}


def _owner_repo_from_remote(project: Path) -> str:
    """`owner/name` read from the push remote URL, when `gh` cannot resolve it.

    `gh` refuses an SSH host alias: a remote spelled `github-alias:acme/product.git`
    — a `Host` entry in `~/.ssh/config` — is a GitHub repository that `gh repo view`
    reports as *"none of the git remotes point to a known GitHub host"*. Measured on a
    consumer 2026-09-16, where the board's whole issues panel was dark for that reason
    while the repository sat on GitHub the entire time.

    The remedy the failure names — pass `OWNER/NAME` explicitly — works and requires the
    operator to read the remote and retype what is already there. Deriving it is the
    same parse `mechanisms/cycle/promote_to_develop.py` already does for `gh -R`, for
    the same alias, found the same week.

    Both URL shapes carry the slug in the same place: `git@host:owner/repo.git` and
    `https://host/owner/repo.git`. The parse is the tail, not the host.
    """
    try:
        proc = subprocess.run(["git", "remote", "get-url", "origin"],
                              cwd=str(project), capture_output=True, text=True,
                              timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    stripped = re.sub(r"^[a-z][a-z0-9+.-]*://", "", proc.stdout.strip(),
                      flags=re.IGNORECASE)
    head, _, rest = stripped.partition("/")
    owner = head.rpartition(":")[2] if ":" in head else ""
    name = rest.rpartition("/")[2] if rest else ""
    if not owner or not name:
        return ""
    return f"{owner}/{name[:-4] if name.endswith('.git') else name}"


def _repo_of(project: Path) -> str:
    """Best effort, for display only. An empty string is an acceptable answer."""
    try:
        proc = subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner",
                               "-q", ".nameWithOwner"],
                              cwd=str(project), capture_output=True, text=True,
                              timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return _owner_repo_from_remote(project)
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip()
    # `gh` said no. That is not the same as "there is no repository", and the alias case
    # is exactly where the two diverge.
    return _owner_repo_from_remote(project)


def digest(snapshot: dict) -> tuple:
    """What must change before the board is told anything changed.

    Deliberately excludes `fetched_at` and `took_seconds`. Including them would make
    every poll a change, waking every connected browser once a minute to re-render an
    identical page.
    """
    return (snapshot.get("ok"), snapshot.get("reason"), snapshot.get("repo"),
            tuple((i["number"], i["stage"], i["state"], i["title"],
                   tuple(i["labels"])) for i in snapshot.get("issues", [])))


def main() -> int:
    parser = argparse.ArgumentParser(description="Read the tracker the board renders.")
    parser.add_argument("project", nargs="?", default=".", type=Path)
    parser.add_argument("--repo", default=None, help="OWNER/NAME; inferred when omitted")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()
    snapshot = fetch(args.project.resolve(), args.repo, args.limit)
    print(json.dumps(snapshot, indent=2, ensure_ascii=False))
    # 1 rather than 2: this is a read that failed, which the caller may retry. Exit 2
    # across this kit is reserved for "could not measure" as a terminal condition.
    return 0 if snapshot["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
