#!/usr/bin/env python3
"""Is the system actually allowed to merge to the trunk? Asked at intake, not at the end.

    python3 mechanisms/gates/check_merge_autonomy.py
    python3 mechanisms/gates/check_merge_autonomy.py --trunk master --json

## The premise this checks

`rules/autonomy-envelope.md` floor 2, as amended 2026-09-08: **merging to the trunk is a
premise of running this kit, not a capability the project may withhold.** A remote whose
branch protection requires a human approving review does not narrow the envelope — it
makes the chain unrunnable.

The failure is not a wrong merge. It is a run in which every item clears DISCOVER, PLAN,
IMPLEMENT, CODE-QUALITY, REVIEW and RELEASE, parks at an open PR, and the queue drains
into a pile of branches nobody merges. That is the failure `autonomy-envelope.md` names
in its own opening, arriving at the last step of every item instead of at the first step
of the run. One API call at intake replaces it with a sentence.

## What it does NOT object to

Branch protection itself, which floor 2 wants: the PR must be mandatory, and protection is
what makes it so on the remote. Required status checks, linear history and a force-push
ban are all compatible — floor 3 asks for them. The single incompatible setting is a
required human approval, because it is the one thing in the list the system cannot be.

## Why UNCHECKED is not HOLDS

A gate that looks, sees nothing and approves produces confidence where there was no
verification — the defect this repository's own CI notes record about `check_xrefs.py`
running without `--strict`. An absent `gh`, an unauthenticated one, or an answer that does
not parse are all *the premise was not tested*, and they exit 2 rather than 0.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from enum import Enum
from typing import Callable

#: Run a `gh` argv and return (returncode, stdout, stderr). Injected so the premise logic
#: is testable without a network, a token, or a repository.
GhRunner = Callable[[list[str]], "tuple[int, str, str]"]


class PremiseResult(Enum):
    """Three different facts, deliberately not collapsed into a boolean."""

    HOLDS = "holds"
    VIOLATED = "violated"
    UNCHECKED = "unchecked"

    @property
    def exit_code(self) -> int:
        return {"holds": 0, "violated": 1, "unchecked": 2}[self.value]


#: `gh` says this when the branch has no protection at all. Nothing then blocks a merge,
#: so the premise holds — whether the PR is enforced is a different rule's business.
_UNPROTECTED_MARKERS = ("branch not protected", "http 404", "not found")

#: And these when it could not answer at all.
_UNAUTHENTICATED_MARKERS = ("auth login", "authentication", "not logged", "http 401", "bad credentials")


def _default_runner(args: list[str]) -> tuple[int, str, str]:
    done = subprocess.run(args, capture_output=True, text=True, check=False)
    return done.returncode, done.stdout, done.stderr


def detect_trunk() -> str:
    """Whatever the remote calls its default branch, falling back to `main`.

    Mirrors `hooks/validate-command.py § trunks()` on purpose rather than importing it:
    that function answers "which names are trunks" for a guard that must be permissive,
    and this one needs the single name to ASK THE API about. A repo on `master` checked
    for `main` gets a 404 and would read as unprotected.
    """
    done = subprocess.run(
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        capture_output=True, text=True, check=False,
    )
    name = done.stdout.strip().removeprefix("origin/")
    return name or "main"


def check_merge_autonomy(*, trunk: str, gh: GhRunner | None = None) -> PremiseResult:
    """Does the remote let the system merge into `trunk` without a human approval?"""
    runner = gh or _default_runner
    endpoint = f"repos/{{owner}}/{{repo}}/branches/{trunk}/protection"

    try:
        code, out, err = runner(["gh", "api", endpoint])
    except (FileNotFoundError, OSError):
        return PremiseResult.UNCHECKED

    haystack = f"{out}\n{err}".lower()

    if code != 0:
        if any(marker in haystack for marker in _UNPROTECTED_MARKERS):
            return PremiseResult.HOLDS
        return PremiseResult.UNCHECKED

    try:
        protection = json.loads(out)
    except (json.JSONDecodeError, TypeError):
        return PremiseResult.UNCHECKED

    if not isinstance(protection, dict):
        return PremiseResult.UNCHECKED

    reviews = protection.get("required_pull_request_reviews")
    if not isinstance(reviews, dict):
        # Protection exists and says nothing about reviews — status checks, linear
        # history, a force-push ban. None of those is a person the system cannot be.
        return PremiseResult.HOLDS

    required = reviews.get("required_approving_review_count", 0)
    if isinstance(required, int) and required > 0:
        return PremiseResult.VIOLATED

    return PremiseResult.HOLDS


_MESSAGES = {
    PremiseResult.HOLDS: (
        "The remote permits the system to merge its own passing PRs. "
        "Branch protection may still enforce the PR itself, which floor 2 wants."
    ),
    PremiseResult.VIOLATED: (
        "PREMISE VIOLATED — branch protection on the trunk requires a human approving "
        "review, so the release chain cannot complete.\n"
        "\n"
        "Every item would clear the whole chain and park at an open PR, and the queue "
        "would drain into a pile of branches nobody merges.\n"
        "\n"
        "  Either drop the required approving review for the account this kit runs as,\n"
        "  or accept that RELEASE ends at PR_OPEN_AWAITING_APPROVAL for every item and\n"
        "  someone merges by hand.\n"
        "\n"
        "rules/autonomy-envelope.md floor 2 records why this is a premise and not a "
        "supported configuration."
    ),
    PremiseResult.UNCHECKED: (
        "NOT CHECKED — `gh` is absent, unauthenticated, or answered something this gate "
        "cannot parse.\n"
        "\n"
        "This is not a pass. The premise may hold or may not; nothing here tested it. "
        "`gh`, authenticated, is a declared requirement of the kit (README § Quick start)."
    ),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that the system may merge to the trunk (envelope floor 2).",
    )
    parser.add_argument(
        "--trunk",
        default=None,
        help="branch to inspect; defaults to whatever origin/HEAD points at",
    )
    parser.add_argument("--json", action="store_true", help="emit the result as JSON")
    args = parser.parse_args(argv)

    trunk = args.trunk or detect_trunk()
    result = check_merge_autonomy(trunk=trunk)

    if args.json:
        print(json.dumps({
            "trunk": trunk,
            "result": result.value,
            "message": _MESSAGES[result],
        }, indent=2))
    else:
        print(f"merge autonomy on '{trunk}': {result.value.upper()}")
        print(_MESSAGES[result])

    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
