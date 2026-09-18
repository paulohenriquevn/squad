"""The premise that makes the chain runnable, checked at intake instead of discovered last.

`rules/autonomy-envelope.md` floor 2 (2026-09-08): merging to the trunk is the system's,
and a remote whose branch protection requires a human reviewer does not narrow the
envelope — it makes the chain unrunnable.

The failure this gate exists to prevent is not a wrong merge. It is a run in which every
item completes DISCOVER, PLAN, IMPLEMENT, CODE-QUALITY, REVIEW and RELEASE, parks at an
open PR, and the queue drains into a pile of branches nobody merges. Announcing that at
intake costs one API call; discovering it per-item costs the whole run.

The three exit codes are three different facts and are deliberately not collapsed:

    0  the premise holds
    1  the premise is violated — a reviewer is required
    2  the premise could not be checked — which is NOT the same as holding
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "mechanisms" / "gates"))

from check_merge_autonomy import (
    PremiseResult,
    check_merge_autonomy,
    check_merge_autonomy_detail,
)


def _gh(payload: object, *, returncode: int = 0, stderr: str = "") -> object:
    """A fake `gh` that answers once with `payload`."""

    def run(_args: list[str]) -> tuple[int, str, str]:
        body = payload if isinstance(payload, str) else json.dumps(payload)
        return returncode, body, stderr

    return run


def test_no_required_reviewers_satisfies_the_premise() -> None:
    """Branch protection may exist — and should: it is what makes the PR mandatory.

    What it may not do is require a human approval the system cannot supply.
    """
    result = check_merge_autonomy(
        trunk="main",
        gh=_gh({"required_pull_request_reviews": {"required_approving_review_count": 0}}),
    )

    assert result is PremiseResult.HOLDS
    assert result.exit_code == 0


def test_a_required_approving_review_violates_the_premise() -> None:
    result = check_merge_autonomy(
        trunk="main",
        gh=_gh({"required_pull_request_reviews": {"required_approving_review_count": 1}}),
    )

    assert result is PremiseResult.VIOLATED
    assert result.exit_code == 1


def test_an_absent_protection_block_satisfies_the_premise() -> None:
    """`gh` returns 404 for an unprotected branch. Nothing blocks the merge, so the
    premise holds — whether the PR itself is enforced is a different rule's business."""
    result = check_merge_autonomy(
        trunk="main",
        gh=_gh("Branch not protected", returncode=1, stderr="HTTP 404"),
    )

    assert result is PremiseResult.HOLDS


def test_protection_without_a_review_requirement_satisfies_the_premise() -> None:
    """Status checks, linear history and force-push bans are all compatible with the
    envelope — floor 3 wants them. Only a required human approval is not."""
    result = check_merge_autonomy(
        trunk="main",
        gh=_gh({"required_status_checks": {"strict": True}, "allow_force_pushes": {"enabled": False}}),
    )

    assert result is PremiseResult.HOLDS


def test_an_unauthenticated_gh_is_unchecked_not_satisfied() -> None:
    """The distinction the exit codes exist for.

    Reporting HOLDS here would be the exact defect the kit names elsewhere: a gate that
    looks, sees nothing, and approves produces confidence where there was no verification.
    """
    result = check_merge_autonomy(
        trunk="main",
        gh=_gh("", returncode=4, stderr="gh: To get started with GitHub CLI, please run: gh auth login"),
    )

    assert result is PremiseResult.UNCHECKED
    assert result.exit_code == 2


def test_a_missing_gh_binary_is_unchecked() -> None:
    def absent(_args: list[str]) -> tuple[int, str, str]:
        raise FileNotFoundError("gh")

    assert check_merge_autonomy(trunk="main", gh=absent) is PremiseResult.UNCHECKED


def test_unparseable_output_is_unchecked_rather_than_assumed() -> None:
    result = check_merge_autonomy(trunk="main", gh=_gh("<!DOCTYPE html> a proxy error page"))

    assert result is PremiseResult.UNCHECKED


@pytest.mark.parametrize("count", [1, 2, 6])
def test_any_positive_review_count_violates(count: int) -> None:
    result = check_merge_autonomy(
        trunk="main",
        gh=_gh({"required_pull_request_reviews": {"required_approving_review_count": count}}),
    )

    assert result is PremiseResult.VIOLATED


def test_the_trunk_is_asked_about_by_name() -> None:
    """A repo on `master`, or on whatever `origin/HEAD` points at, must be checked on ITS
    trunk. Asking about `main` on a `master` repo returns 404 and would read as HOLDS."""
    seen: list[str] = []

    def spy(args: list[str]) -> tuple[int, str, str]:
        seen.append(" ".join(args))
        return 0, json.dumps({}), ""

    check_merge_autonomy(trunk="master", gh=spy)

    assert any("master" in call for call in seen), seen
    assert not any("/main/" in call for call in seen), seen


def test_the_permanent_causes_are_named() -> None:
    """The gate stated three causes — `gh` absent, unauthenticated, or unparseable — and
    all three resolve: an absent `gh` gets installed and an unauthenticated one logs in.

    Measured on a consumer 2026-09-16 whose `gh auth status` was already logged in: a
    PRIVATE repository on a plan that does not expose branch protection returns HTTP 403
    "Upgrade to GitHub Pro", and a remote reached through an SSH host alias returns "none
    of the git remotes point to a known GitHub host". Neither was in the list, and neither
    ever resolves on its own — so that repository stays UNCHECKED forever while the
    remediation tells it to do two things it has already done.

    The consequence is bigger than the wording. `git-safety.md` enforces the PR
    requirement "server-side, unbypassable" BY branch protection, so an API forbidding the
    read is strong evidence the protection is not configured — the repository has the
    ORIGIN guarantee and not the REVIEW one. That file names both states as possible and
    nothing had ever measured which one a given repository is in.
    """
    source = (Path(__file__).resolve().parents[1] / "mechanisms" / "gates"
              / "check_merge_autonomy.py").read_text(encoding="utf-8")
    # The whole file, not a slice. Slicing at `"),"` cut the message mid-string because
    # the text itself contains that pair — the second time in one batch that a test read a
    # region not containing what it asserted about. A region chosen by a delimiter the
    # content also uses is not a region.
    for phrase in ("NEVER resolve", "Upgrade to GitHub Pro", "SSH host alias",
                   "ORIGIN guarantee"):
        assert phrase in source, f"the UNCHECKED message does not name: {phrase}"


def test_a_repository_gh_cannot_resolve_is_not_read_as_an_unprotected_trunk() -> None:
    """The third marker was the bare string "not found", which matches far more than 404.

    Measured by injecting a runner: `GraphQL: Could not resolve to a Repository with the
    name (repository not found)` contains it, so a repository `gh` cannot see at all was
    classified as a trunk with no protection — HOLDS, exit 0, the premise the whole
    envelope rests on satisfied by an error message.
    """
    unresolvable = _gh(
        "", returncode=1,
        stderr="GraphQL: Could not resolve to a Repository with the name "
               "'acme/private' (repository not found)")

    assert check_merge_autonomy(trunk="main", gh=unresolvable) is PremiseResult.UNCHECKED


def test_a_trunk_with_no_protection_still_satisfies_the_premise() -> None:
    """The narrowing must not cost the case the markers exist for."""
    unprotected = _gh("", returncode=1, stderr="Branch not protected (HTTP 404)")

    assert check_merge_autonomy(trunk="main", gh=unprotected) is PremiseResult.HOLDS


def test_a_permanent_cause_reaches_the_reader_instead_of_a_bare_unchecked() -> None:
    """The loop over `_PERMANENT_MARKERS` returned what the fall-through returned.

    Both arms answered UNCHECKED, so the loop could not change any observable behaviour,
    and the comment beside it named a `permanent_cause` field that existed nowhere in the
    repository. The two causes the constant was added for — a private repo whose plan
    does not expose branch protection, and an SSH host alias — were indistinguishable
    from "gh is not installed", whose stated remediation is to install it.
    """
    private = _gh("", returncode=1,
                  stderr="HTTP 403: Upgrade to GitHub Pro or make this repository public")

    result, cause = check_merge_autonomy_detail(trunk="main", gh=private)

    assert result is PremiseResult.UNCHECKED
    assert cause and "plan does not expose branch protection" in cause


def test_an_ordinary_unchecked_carries_no_cause() -> None:
    absent = _gh_absent()

    result, cause = check_merge_autonomy_detail(trunk="main", gh=absent)

    assert result is PremiseResult.UNCHECKED
    assert cause is None


def _gh_absent():
    def run(_args: list[str]) -> tuple[int, str, str]:
        raise FileNotFoundError("gh")
    return run
