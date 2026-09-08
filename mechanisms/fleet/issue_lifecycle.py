#!/usr/bin/env python3
"""Issue lifecycle: label when a fix reaches the integration branch, close on release.

WHY THIS EXISTS
===============
The rule it enforces: **never close on merge, only on release.** A fix that
merged is a fix somebody can validate; a fix that shipped is a fix the person
blocked by the bug can finally use. Those are different claims, and closing on
the first tells the second person the problem is over while their install still
carries it.

So there are two moments and two acts:

1. a commit closing an issue reaches the integration branch → label `in-develop`
2. a release tag ships that commit                          → close the issue

WHAT IT REFUSES, AND WHY EACH REFUSAL IS HERE
=============================================
Every refusal below replaced a defect measured on 2026-09-08 (#39). They are
listed with what they cost, because each one reported success while doing
nothing:

- **A command that failed is never reported as done.** `_run` used to take
  `check=False`, which made it swallow the exit status and return the failed
  command's output; the `except` clauses guarding it were unreachable, and the
  caller appended to `labeled`/`closed` unconditionally. Reproduced in a
  repository with no remote: `gh issue edit` exited non-zero and the report came
  back `{'labeled': [42], 'errors': []}`. `_run` now returns `Ran`, the shape
  `fleet_lander.py` already uses in this directory, and nothing is recorded as
  done without `ok`.

- **"I could not look" never reads as "there is nothing there."** The scan took a
  `branch` argument it then overwrote, twice, ending at `git log HEAD` — so a
  scan of `develop` returned whatever branch happened to be checked out, in a
  repository that had no `develop` at all. The branch is used, and a branch that
  does not resolve raises `LookupFailed` rather than returning an empty set.

- **An unsigned tag is a tag, not an absence.** Closing was gated on
  `git tag --verify`, which succeeds only for a GPG-signed tag. This repository
  does not sign tags, so every tag was skipped by a bare `continue` and
  `close_on_release` returned `{"closed": [], "errors": []}` — byte-identical to
  the answer for a repository with nothing to close. Signature verification is
  now opt-in (`--require-signature`), and when it refuses a tag it says so in
  `skipped`.

- **A release is a range, not a commit.** `Closes #N` was read from the message of
  the commit the tag points at. A release cut as a `develop → main` pull request
  plus a semver tag carries its references in the commits of the range, and the
  tagged commit is usually a merge with none. The scan is now
  `<previous tag>..<tag>`, plus the annotation on the tag itself.

IDEMPOTENCE
===========
`gh issue edit --add-label` and `gh issue close` are both idempotent, so a second
pass over the same range relabels and recloses without duplicating anything.

Exit codes: 0 — every action either succeeded or had nothing to do
            1 — at least one action failed (the reasons are in `errors`)
            2 — invocation error
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: `Closes #N`, the only spelling this module acts on. `Fixes`/`Resolves` are
#: deliberately absent: GitHub honours them on merge, and honouring them here
#: would close on merge, which is the one thing this module exists to prevent.
_CLOSES_RE = re.compile(r"[Cc]loses\s+#(\d+)")

#: `v1.2.3`, with an optional pre-release suffix. Shape only — a tag's existence
#: is a fact, and whether it was signed is a separate question asked separately.
_SEMVER_TAG_RE = re.compile(r"^v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")

#: How many releases back to sweep. A closed issue re-closed costs nothing, so
#: the window only has to cover the releases a run might have missed.
_TAG_WINDOW = 5


class LookupFailed(RuntimeError):
    """The thing to scan could not be read.

    Distinct from "the scan found nothing", and the distinction is the point: one
    of them means the caller learned something.
    """


@dataclass(frozen=True)
class Ran:
    """A command that ran, and whether it worked. Same shape as `fleet_lander.Ran`."""

    ok: bool
    stdout: str = ""
    stderr: str = ""

    @property
    def text(self) -> str:
        return f"{self.stdout}\n{self.stderr}".strip()


def _run(cmd: list[str], *, timeout: int = 120) -> Ran:
    """Run a command and report whether it worked.

    A command that could not start is `ok=False` with the reason, never an empty
    success — the caller must not be able to tell "it worked and printed nothing"
    from "it never ran".
    """
    try:
        done = subprocess.run(  # noqa: PLW1510 — the returncode is the verdict
            cmd, capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return Ran(False, stderr=f"{cmd[0]} did not finish within {timeout}s")
    except (OSError, subprocess.SubprocessError) as exc:
        return Ran(False, stderr=f"{cmd[0]} could not be run: {exc}")
    return Ran(done.returncode == 0, (done.stdout or "").strip(),
               (done.stderr or "").strip())


def _resolve(repo: Path, ref: str) -> str | None:
    """The ref as git sees it, preferring the remote-tracking copy.

    `origin/develop` is what a supervisor on a workstation actually has; the local
    `develop` may be stale or absent. Both are tried, and neither existing is a
    fact the caller has to hear about.
    """
    for candidate in (f"origin/{ref}", ref):
        if _run(["git", "-C", str(repo), "rev-parse", "--verify", "--quiet",
                 f"{candidate}^{{commit}}"]).ok:
            return candidate
    return None


def find_issue_numbers(
    repo: Path, branch: str = "develop", since: str | None = None
) -> set[int]:
    """Issue numbers closed by commits on `branch` (optionally only after `since`).

    Raises `LookupFailed` when `branch` does not resolve. Returning an empty set
    there is what let a scan of a non-existent `develop` report "no issues" — the
    caller cannot act on an answer that means two things.
    """
    resolved = _resolve(repo, branch)
    if resolved is None:
        raise LookupFailed(
            f"`{branch}` does not resolve in {repo} (tried `origin/{branch}` and "
            f"`{branch}`). Nothing was scanned, which is not the same as finding "
            f"nothing."
        )

    span = f"{since}..{resolved}" if since else resolved
    log = _run(["git", "-C", str(repo), "log", span, "--format=%B"])
    if not log.ok:
        raise LookupFailed(f"`git log {span}` failed: {log.text[:200]}")
    return {int(n) for n in _CLOSES_RE.findall(log.stdout)}


#: Kept as the previous name so a caller written against it keeps working.
_find_issue_numbers_in_log = find_issue_numbers


def label_in_develop(
    repo: Path,
    tracker: str = "github",
    label: str = "in-develop",
    branch: str = "develop",
) -> dict[str, Any]:
    """Label every issue whose fix reached `branch`. Never closes anything."""
    if tracker != "github":
        return {"labeled": [], "skipped": [], "errors": [f"tracker {tracker} not supported"]}

    try:
        issue_numbers = find_issue_numbers(repo, branch=branch)
    except LookupFailed as exc:
        return {"labeled": [], "skipped": [], "errors": [str(exc)]}

    labeled: list[int] = []
    errors: list[str] = []
    for issue_num in sorted(issue_numbers):
        ran = _run(["gh", "issue", "edit", str(issue_num), f"--add-label={label}"])
        if ran.ok:
            labeled.append(issue_num)
        else:
            errors.append(f"issue #{issue_num}: could not label — {ran.text[:200]}")
    return {"labeled": labeled, "skipped": [], "errors": errors}


def _release_tags(repo: Path) -> list[str]:
    """The most recent semver tags, newest first. Shape-checked, not signature-checked."""
    listed = _run(["git", "-C", str(repo), "tag", "-l", "v*",
                   "--sort=-version:refname"])
    if not listed.ok or not listed.stdout:
        return []
    tags = [t.strip() for t in listed.stdout.splitlines() if _SEMVER_TAG_RE.match(t.strip())]
    return tags[:_TAG_WINDOW]


def _previous_tag(repo: Path, tag: str) -> str | None:
    """The release before `tag`, so the range is what this release shipped."""
    described = _run(["git", "-C", str(repo), "describe", "--tags", "--abbrev=0",
                      "--match", "v*", f"{tag}^"])
    return described.stdout.strip() if described.ok and described.stdout.strip() else None


def _issues_in_release(repo: Path, tag: str) -> set[int]:
    """`Closes #N` anywhere in what this release shipped.

    The RANGE since the previous tag, plus the tag's own annotation. Reading only
    the tagged commit's message finds nothing for the ordinary release, whose
    tagged commit is the merge and whose references are in the commits behind it.
    """
    previous = _previous_tag(repo, tag)
    span = f"{previous}..{tag}" if previous else tag
    found: set[int] = set()

    log = _run(["git", "-C", str(repo), "log", span, "--format=%B"])
    if log.ok:
        found |= {int(n) for n in _CLOSES_RE.findall(log.stdout)}

    annotation = _run(["git", "-C", str(repo), "tag", "-l", tag, "--format=%(contents)"])
    if annotation.ok:
        found |= {int(n) for n in _CLOSES_RE.findall(annotation.stdout)}
    return found


def close_on_release(
    repo: Path,
    tracker: str = "github",
    require_signature: bool = False,
) -> dict[str, Any]:
    """Close the issues each recent release shipped.

    `require_signature` reinstates the old `git tag --verify` gate for a project
    that signs its tags. It is off by default because it used to be mandatory and
    silent: an unsigned tag was skipped by a bare `continue`, so a project that
    does not sign got the same answer as a project with nothing to close. When it
    is on and a tag fails, the tag lands in `skipped` with its reason.
    """
    if tracker != "github":
        return {"closed": [], "skipped": [], "errors": [f"tracker {tracker} not supported"]}

    closed: list[int] = []
    skipped: list[str] = []
    errors: list[str] = []

    for tag in _release_tags(repo):
        if require_signature:
            verified = _run(["git", "-C", str(repo), "tag", "--verify", tag])
            if not verified.ok:
                skipped.append(f"{tag}: signature not verified — {verified.text[:120]}")
                continue

        for issue_num in sorted(_issues_in_release(repo, tag)):
            if issue_num in closed:
                continue
            ran = _run(["gh", "issue", "close", str(issue_num),
                        "--reason", "completed",
                        "--comment", f"Shipped in {tag}."])
            if ran.ok:
                closed.append(issue_num)
            else:
                errors.append(f"issue #{issue_num} ({tag}): could not close — "
                              f"{ran.text[:200]}")

    return {"closed": closed, "skipped": skipped, "errors": errors}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", type=Path, default=Path.cwd(), help="repository root")
    ap.add_argument("--branch", default="develop",
                    help="the integration branch to scan for the label step")
    ap.add_argument("--label", default="in-develop")
    ap.add_argument("--require-signature", action="store_true",
                    help="only close on a GPG-verified tag; skips are reported")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not (args.repo / ".git").exists():
        print(f"{args.repo} is not a git repository")
        return 2

    labelled = label_in_develop(args.repo, label=args.label, branch=args.branch)
    released = close_on_release(args.repo, require_signature=args.require_signature)
    report = {"labeled": labelled, "released": released}

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"labelled `{args.label}`: "
              f"{', '.join(f'#{n}' for n in labelled['labeled']) or 'nothing'}")
        print(f"closed on release: "
              f"{', '.join(f'#{n}' for n in released['closed']) or 'nothing'}")
        for note in released["skipped"]:
            print(f"  skipped {note}")
        for problem in labelled["errors"] + released["errors"]:
            print(f"  ERROR {problem}")

    return 1 if (labelled["errors"] or released["errors"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
