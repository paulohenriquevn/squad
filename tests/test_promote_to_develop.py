"""Promotion is not a release, and until now there was no way to do one without the other.

`git-safety.md` § 1: `develop` advances ONLY by promoting `workspace` through a PR. The
only place in the kit that opened that PR was the middle of `/release`'s chain, between
the version bump and the tag — so integrating required versioning, and a project that did
not want to cut a version simply did not integrate.

Measured on this repository on 2026-09-09: **349 commits on `workspace`, zero tags**. The
work was finished, verified and unreachable, and 45 issues were closed against the kit's
own rule because there was no version to name.

This module is the promotion alone. It moves no version, writes no CHANGELOG, cuts no tag.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mechanisms" / "cycle"))

import promote_to_develop as promote  # noqa: E402


def _gh(responses: dict[str, tuple[int, str, str]]):
    """A fake `gh`, keyed by a fragment of the command. No network, no token."""

    def run(argv: list[str]) -> tuple[int, str, str]:
        joined = " ".join(argv)
        for fragment, response in responses.items():
            if fragment in joined:
                return response
        return 1, "", f"unexpected gh call: {joined}"

    return run


def _git(branch: str = "workspace", dirty: str = "", ahead: str = "3"):
    def run(argv: list[str]) -> tuple[int, str, str]:
        joined = " ".join(argv)
        if "rev-parse --abbrev-ref" in joined:
            return 0, branch + "\n", ""
        if "status --porcelain" in joined:
            return 0, dirty, ""
        if "rev-list --count" in joined:
            return 0, ahead + "\n", ""
        return 0, "", ""

    return run


def test_a_clean_workspace_ahead_of_develop_is_promotable() -> None:
    report = promote.promote(ROOT, git=_git(), gh=_gh({
        "pr list": (0, "[]", ""),
        "pr create": (0, "https://github.com/o/r/pull/12\n", ""),
        "pr merge": (0, "", ""),
    }))
    assert report.exit_code == promote.OK
    assert "12" in " ".join(report.lines)


def test_it_refuses_from_a_branch_that_is_not_workspace() -> None:
    """`develop` integrates, it never originates — promoting from it would author on it."""
    report = promote.promote(ROOT, git=_git(branch="develop"), gh=_gh({}))
    assert report.exit_code == promote.REFUSED
    assert any("workspace" in line for line in report.lines)


def test_it_refuses_a_dirty_tree() -> None:
    """Promoting uncommitted work sends develop a state nobody reviewed or tested."""
    report = promote.promote(ROOT, git=_git(dirty=" M squad/cli/router.py\n"), gh=_gh({}))
    assert report.exit_code == promote.REFUSED
    assert any("dirty" in line.lower() or "uncommitted" in line.lower() for line in report.lines)


def test_nothing_to_promote_is_an_answer_not_a_failure() -> None:
    """develop already carries everything. That is a fact, and facts exit 0."""
    report = promote.promote(ROOT, git=_git(ahead="0"), gh=_gh({}))
    assert report.exit_code == promote.OK
    assert any("nothing" in line.lower() for line in report.lines)


def test_an_existing_pr_is_reused_rather_than_duplicated() -> None:
    existing = '[{"number": 11, "url": "https://github.com/o/r/pull/11"}]'
    report = promote.promote(ROOT, git=_git(), gh=_gh({
        "pr list": (0, existing, ""),
        "pr merge": (0, "", ""),
    }))
    assert report.exit_code == promote.OK
    assert any("11" in line for line in report.lines)


def test_a_blocked_merge_leaves_the_pr_open_and_says_so() -> None:
    """Branch protection demanding a reviewer is a premise, not a per-run failure.

    `cycle-release.md` already answers this for the release PR with
    PR_OPEN_AWAITING_APPROVAL; the promotion behaves the same way rather than inventing
    a second convention.
    """
    report = promote.promote(ROOT, git=_git(), gh=_gh({
        "pr list": (0, "[]", ""),
        "pr create": (0, "https://github.com/o/r/pull/12\n", ""),
        "pr merge": (1, "", "GraphQL: At least 1 approving review is required"),
    }))
    assert report.exit_code == promote.AWAITING
    assert any("approv" in line.lower() for line in report.lines)


def test_gh_absent_is_unmeasured_not_a_refusal() -> None:
    """2 is could-not-measure. Reporting it as a refusal would blame the branch state."""

    def missing(argv: list[str]) -> tuple[int, str, str]:
        raise FileNotFoundError("gh")

    report = promote.promote(ROOT, git=_git(), gh=missing)
    assert report.exit_code == promote.UNMEASURED


def test_dry_run_opens_nothing() -> None:
    calls: list[str] = []

    def recording(argv: list[str]) -> tuple[int, str, str]:
        calls.append(" ".join(argv))
        return 0, "[]", ""

    report = promote.promote(ROOT, git=_git(), gh=recording, dry_run=True)
    assert report.exit_code == promote.OK
    assert not any("pr create" in c or "pr merge" in c for c in calls), calls


def test_it_never_touches_a_version() -> None:
    """The whole point. A promotion that bumps is a release wearing another name."""
    source = (ROOT / "mechanisms" / "cycle" / "promote_to_develop.py").read_text(encoding="utf-8")
    code = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )
    for forbidden in ("bump_version", "compute_next_version", "promote_unreleased", "git tag"):
        assert forbidden not in code, f"promotion must not reach for {forbidden}"
