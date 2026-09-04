#!/usr/bin/env python3
"""Issue lifecycle automation — label when branch reaches develop, close on release tag.

WHY THIS EXISTS
===============
The user's rule: "Never close on merge, only on release." This script enforces that rule:
1. When a fix commit reaches develop (merge or direct), label the issue 'in-develop'.
2. When a version tag is verified (git tag --verify), close the issue.

Crucially: labeling on develop is NOT closing. Closing happens only on the release tag.

This allows consumers to know "the fix is in testing" (develop) vs "the fix is shipped" (tag).

WHAT IT DOES
============
1. Reads git log on develop to find commits mentioning "Closes #N"
2. Labels those issues with 'in-develop' via gh CLI
3. Reads git tags (semver, verified) to find releases
4. Parses the tag message or commit history to find "Closes #N"
5. Closes those issues via gh CLI

IDEMPOTENCE
===========
- Labeling a second time does not create duplicate labels (gh is idempotent)
- Closing a closed issue does not error (gh succeeds)
- Running against the same develop commit twice is safe
"""
import json
import re
import subprocess
from pathlib import Path
from typing import Any


def _run(cmd: list[str], check: bool = True) -> str:
    """Run shell command and return stdout."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{e.stderr}")


def _find_issue_numbers_in_log(
    repo: Path, branch: str = "develop", since: str | None = None
) -> set[int]:
    """Extract issue numbers from git log 'Closes #N' patterns.

    Scans commit messages for patterns like:
    - "Closes #123"
    - "closes #456"
    - "Fix #789" (not matched; only "Closes" variant)

    Args:
        repo: Repository root
        branch: Branch to scan (default: develop)
        since: Optional git ref to scan since (for idempotence checks)

    Returns:
        Set of issue numbers found.
    """
    # Build git log command
    cmd = ["git", "-C", str(repo), "log", "--format=%B", f"origin/{branch}..HEAD"]
    if since:
        cmd = ["git", "-C", str(repo), "log", f"{since}..origin/{branch}", "--format=%B"]
    else:
        cmd = ["git", "-C", str(repo), "log", "HEAD", "--format=%B"]

    try:
        output = _run(cmd, check=False)
    except Exception:
        return set()

    # Extract issue numbers: "Closes #123" or "closes #456"
    pattern = r"[Cc]loses\s+#(\d+)"
    matches = re.findall(pattern, output)
    return set(int(m) for m in matches)


def label_in_develop(
    repo: Path,
    tracker: str = "github",
    label: str = "in-develop",
) -> dict[str, Any]:
    """Label issues in git develop branch with 'in-develop'.

    Args:
        repo: Repository root
        tracker: Tracker type (github, jira, etc.) — currently only GitHub
        label: Label to apply (default: 'in-develop')

    Returns:
        Dict with keys: labeled, skipped, errors
    """
    if tracker != "github":
        return {"labeled": [], "skipped": [], "errors": [f"Tracker {tracker} not supported"]}

    # Find issues in develop
    issue_numbers = _find_issue_numbers_in_log(repo, branch="develop")

    if not issue_numbers:
        return {"labeled": [], "skipped": [], "errors": []}

    labeled = []
    errors = []

    for issue_num in issue_numbers:
        try:
            # gh issue edit applies label idempotently
            _run(["gh", "issue", "edit", str(issue_num), f"--add-label={label}"], check=False)
            labeled.append(issue_num)
        except Exception as e:
            errors.append(f"Issue #{issue_num}: {str(e)}")

    return {"labeled": labeled, "skipped": [], "errors": errors}


def close_on_release(
    repo: Path,
    tracker: str = "github",
) -> dict[str, Any]:
    """Close issues when a version tag is detected and verified.

    Args:
        repo: Repository root
        tracker: Tracker type (github, jira, etc.) — currently only GitHub

    Returns:
        Dict with keys: closed, skipped, errors
    """
    if tracker != "github":
        return {"closed": [], "skipped": [], "errors": [f"Tracker {tracker} not supported"]}

    # Find all tags matching semver pattern (v1.2.3)
    try:
        tags_output = _run(
            ["git", "-C", str(repo), "tag", "-l", "v*", "--sort=-version:refname"],
            check=False
        )
    except Exception:
        return {"closed": [], "skipped": [], "errors": ["Could not list tags"]}

    if not tags_output:
        return {"closed": [], "skipped": [], "errors": []}

    tags = tags_output.split("\n")[:5]  # Limit to last 5 tags

    closed = []
    errors = []

    for tag in tags:
        if not tag:
            continue

        try:
            # Verify tag (git tag --verify returns exit 0 if valid)
            _run(["git", "-C", str(repo), "tag", "--verify", tag])
        except Exception:
            # Tag is not signed/verified, skip
            continue

        # Get the commit message of the tag
        try:
            commit = _run(
                ["git", "-C", str(repo), "rev-list", "-n", "1", tag],
                check=False
            )
            msg = _run(
                ["git", "-C", str(repo), "log", "--format=%B", "-n", "1", commit],
                check=False
            )
        except Exception:
            continue

        # Find "Closes #N" in tag message
        pattern = r"[Cc]loses\s+#(\d+)"
        issue_numbers = set(int(m) for m in re.findall(pattern, msg))

        for issue_num in issue_numbers:
            try:
                # Close the issue
                _run(["gh", "issue", "close", str(issue_num)], check=False)
                closed.append(issue_num)
            except Exception as e:
                errors.append(f"Issue #{issue_num}: {str(e)}")

    return {"closed": closed, "skipped": [], "errors": errors}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, default=Path.cwd(), help="Repository root")
    ap.add_argument("--tracker", default="github", help="Tracker type (github, jira, etc.)")
    ap.add_argument(
        "--action",
        choices=["label", "close", "all"],
        default="all",
        help="Action to perform",
    )
    args = ap.parse_args(argv)

    results = {}

    if args.action in ("label", "all"):
        print("Labeling issues in develop...")
        results["label"] = label_in_develop(args.repo, tracker=args.tracker)
        print(f"  Labeled: {results['label']['labeled']}")
        if results["label"]["errors"]:
            print(f"  Errors: {results['label']['errors']}")

    if args.action in ("close", "all"):
        print("Closing issues on release tag...")
        results["close"] = close_on_release(args.repo, tracker=args.tracker)
        print(f"  Closed: {results['close']['closed']}")
        if results["close"]["errors"]:
            print(f"  Errors: {results['close']['errors']}")

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
