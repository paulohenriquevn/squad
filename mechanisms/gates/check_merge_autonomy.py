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
from pathlib import Path
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
#: The bare string "not found" was the third marker until 2026-09-17. It matched far
#: more than the 404 it was written for: `GraphQL: Could not resolve to a Repository
#: with the name (repository not found)` contains it, so a repository `gh` cannot see
#: AT ALL was classified as a trunk with no protection — the premise the whole autonomy
#: envelope rests on, satisfied by an error message. The two remaining markers are the
#: answers the endpoint actually gives for an unprotected branch.
_UNPROTECTED_MARKERS = ("branch not protected", "http 404")

#: And these when it could not answer at all.
_UNAUTHENTICATED_MARKERS = ("auth login", "authentication", "not logged", "http 401", "bad credentials")

#: Causes that NEVER resolve on their own, and were absent from this gate's stated three.
#:
#: Measured on a consumer 2026-09-16: `gh auth status` logged in, and the endpoint still
#: refused —
#:
#:   HTTP 403  "Upgrade to GitHub Pro or make this repository public"
#:   gh        "none of the git remotes point to a known GitHub host"   (SSH host alias)
#:
#: The stated remediations were "install gh" and "log in", and both were already true. An
#: absent `gh` gets installed and an unauthenticated one logs in; a PRIVATE repository on
#: a plan that does not expose branch protection stays UNCHECKED forever, and so does one
#: reached through an SSH host alias `gh` cannot resolve.
#:
#: It matters beyond the wording. `git-safety.md` says the PR requirement is enforced
#: "server-side, unbypassable" BY branch protection. A 403 on that endpoint is strong
#: evidence the protection is not configured at all — so the repository has the ORIGIN
#: guarantee (the local hook: work was born on `workspace`) and NOT the REVIEW guarantee.
#: That file already names both states as possible; nothing had ever measured which one a
#: given repository is in.
_PERMANENT_MARKERS = (
    ("upgrade to github pro", "this repository's plan does not expose branch protection"),
    ("http 403", "the API refused the protection endpoint (403)"),
    ("known github host", "the git remote is an SSH host alias `gh` cannot resolve"),
)


def _default_runner(args: list[str]) -> tuple[int, str, str]:
    return _runner_in(None)(args)


def _runner_in(root: Path | None) -> GhRunner:
    """A runner that asks about the repository at `root`, not at the shell's cwd.

    `--root` was accepted and then ignored: `gh` inherits the working directory, so
    pointing this gate at an empty tree still questioned whichever repository the
    shell stood in — and printed that answer under the caller's path. Measured
    2026-09-17: `--root <empty tmpdir>` printed `merge autonomy on 'main': HOLDS`.
    """
    def run(args: list[str]) -> tuple[int, str, str]:
        done = subprocess.run(args, capture_output=True, text=True, check=False,
                              cwd=str(root) if root else None)
        return done.returncode, done.stdout, done.stderr
    return run


def detect_trunk(root: Path | None = None) -> str:
    """Whatever the remote calls its default branch, falling back to `main`.

    Mirrors `hooks/validate-command.py § trunks()` on purpose rather than importing it:
    that function answers "which names are trunks" for a guard that must be permissive,
    and this one needs the single name to ASK THE API about. A repo on `master` checked
    for `main` gets a 404 and would read as unprotected.
    """
    done = subprocess.run(
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        capture_output=True, text=True, check=False,
        cwd=str(root) if root else None,
    )
    name = done.stdout.strip().removeprefix("origin/")
    return name or "main"


def check_merge_autonomy(*, trunk: str, gh: GhRunner | None = None) -> PremiseResult:
    """Does the remote let the system merge into `trunk` without a human approval?

    The enum alone, which is what six readers compute from. `check_merge_autonomy_detail`
    is the same walk carrying the permanent cause, and `main` prints it.
    """
    return check_merge_autonomy_detail(trunk=trunk, gh=gh)[0]


def check_merge_autonomy_detail(
        *, trunk: str, gh: GhRunner | None = None) -> tuple[PremiseResult, str | None]:
    """The verdict, and the permanent cause behind an UNCHECKED when there is one.

    The cause used to be promised and not delivered. The loop over `_PERMANENT_MARKERS`
    returned `UNCHECKED` and so did the fall-through directly below it, so the loop could
    not change any observable behaviour, while the comment beside it said "`permanent_cause`
    carries the case, and `main` prints it" — of a field that existed nowhere in the tree.
    A private repository whose plan does not expose branch protection was therefore
    indistinguishable from an absent `gh`, whose stated remediation is to install it.
    """
    runner = gh or _default_runner
    endpoint = f"repos/{{owner}}/{{repo}}/branches/{trunk}/protection"

    try:
        code, out, err = runner(["gh", "api", endpoint])
    except (FileNotFoundError, OSError):
        return PremiseResult.UNCHECKED, None

    haystack = f"{out}\n{err}".lower()

    if code != 0:
        if any(marker in haystack for marker in _UNPROTECTED_MARKERS):
            return PremiseResult.HOLDS, None
        for marker, cause in _PERMANENT_MARKERS:
            if marker in haystack:
                # Still UNCHECKED — the enum stays stable because six readers compute
                # from it, the same reason `no_commit_reason` is a field and not a
                # status. What changes is what the reader is told.
                return PremiseResult.UNCHECKED, cause
        return PremiseResult.UNCHECKED, None

    try:
        protection = json.loads(out)
    except (json.JSONDecodeError, TypeError):
        return PremiseResult.UNCHECKED, None

    if not isinstance(protection, dict):
        return PremiseResult.UNCHECKED, None

    reviews = protection.get("required_pull_request_reviews")
    if not isinstance(reviews, dict):
        # Protection exists and says nothing about reviews — status checks, linear
        # history, a force-push ban. None of those is a person the system cannot be.
        return PremiseResult.HOLDS, None

    required = reviews.get("required_approving_review_count", 0)
    if isinstance(required, int) and required > 0:
        return PremiseResult.VIOLATED, None

    return PremiseResult.HOLDS, None


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
        "\n"
        "\nSome causes NEVER resolve, and the two remediations above do not reach them: a "
        "PRIVATE repository on a plan that does not expose branch protection (HTTP 403, "
        "\"Upgrade to GitHub Pro\"), and a remote reached through an SSH host alias `gh` "
        "cannot resolve. Both were measured on a consumer whose `gh auth status` was "
        "already logged in."
        "\n"
        "\nWhen the cause is the 403: `git-safety.md` enforces the PR requirement "
        "\"server-side, unbypassable\" BY branch protection, so an API that forbids "
        "reading it is strong evidence the protection is not configured. That repository "
        "has the ORIGIN guarantee — the local hook, work born on `workspace` — and not "
        "the REVIEW guarantee. Both states are named in that file as possible; this is "
        "the first thing that measures which one you are in."
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
    # `--root`, per the contract in `_contract.py`: a caller that does not know
    # which gate it is talking to passes this and it works. This gate resolved the
    # tree implicitly from the working directory, so it could not be pointed at one.
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true", help="emit the result as JSON")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not root.is_dir():
        print(f"UNCHECKED: {root} is not a directory — nothing was asked of any "
              f"remote. This is not a pass.", file=sys.stderr)
        return PremiseResult.UNCHECKED.exit_code

    trunk = args.trunk or detect_trunk(root)
    result, cause = check_merge_autonomy_detail(trunk=trunk, gh=_runner_in(root))

    if args.json:
        print(json.dumps({
            "trunk": trunk,
            "result": result.value,
            "permanent_cause": cause,
            "message": _MESSAGES[result],
        }, indent=2))
    else:
        print(f"merge autonomy on '{trunk}' (remote of {root}): "
              f"{result.value.upper()}")
        if cause:
            print(f"  cause (permanent, does not resolve on its own): {cause}")
        print(_MESSAGES[result])

    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
