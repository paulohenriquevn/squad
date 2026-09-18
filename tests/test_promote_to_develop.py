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

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
import promote_to_develop as promote  # noqa: E402 — post-bootstrap import


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


def test_an_untracked_file_does_not_refuse_a_promotion(tmp_path: Path) -> None:
    """A promotion is a MERGE OF COMMITS. An untracked file is in no commit, so it cannot
    affect what this gate guards — and counting it refuses on a condition that cannot
    occur.

    Measured on a consumer 2026-09-16, holding the first item ever to cross the whole
    chain: twelve entries from `git status --porcelain`, ALL of them `??`, and
    `--untracked-files=no` returning nothing.

    Among the twelve was `.squad/wiki/decisions/...`, and `.gitignore` un-ignores
    `.squad/wiki/` ON PURPOSE — `records-location.md` calls it durable knowledge that
    should be versioned. So the kit's own designed output directory made the kit's own
    promotion gate refuse, and every consumer that has written one wiki document hits it
    on its first promotion, forever, told their tree "promotes a state nobody reviewed".

    The caution is not worthless and is kept as a WARNING: an untracked file may be work
    somebody forgot to add. What was wrong is that the reason did not describe the
    trigger.
    """
    source = (Path(__file__).resolve().parents[1] / "mechanisms" / "cycle"
              / "promote_to_develop.py").read_text(encoding="utf-8")
    # Every `git status --porcelain` in this file must carry the flag. Slicing at the
    # first `REFUSED` was the first version of this assertion and it cut before the call,
    # because an earlier refusal (the branch check) comes first — the test reading a
    # region that did not contain what it was asserting about.
    calls = [line for line in source.splitlines()
             if '"status", "--porcelain"' in line and not line.lstrip().startswith("#")]
    assert calls, "no `git status --porcelain` call found at all"
    for line in calls:
        assert "--untracked-files=no" in line, \
            f"this call still counts untracked files as uncommitted changes: {line.strip()}"
    assert "WARNING:" in source and "ls-files" in source, \
        "untracked files are no longer reported at all — the caution was lost with the bug"


def test_the_refusal_says_it_means_tracked_files() -> None:
    """`12 uncommitted change(s)` over twelve untracked files was true of nothing. The
    message now says which set it counted."""
    source = (Path(__file__).resolve().parents[1] / "mechanisms" / "cycle"
              / "promote_to_develop.py").read_text(encoding="utf-8")
    assert "to TRACKED files" in source


def test_the_repository_is_named_rather_than_inferred_by_gh() -> None:
    """An SSH host alias — `host:owner/repo.git`, what anyone with two GitHub identities
    on one machine ends up with — defeats every unaided `gh` call with "none of the git
    remotes point to a known GitHub host".

    Measured on a consumer 2026-09-16, holding the first item ever to cross the whole
    chain, one flag from `develop`: `gh pr list -R <owner>/<repo>` answered correctly in
    the same minute the unaided call refused. And the remediation compounded it, telling
    a reader to run `gh auth login` while `gh auth status` reported them logged in — the
    third gate that day whose remedy could not work for the case it fired on.

    The kit had already solved this once: `board_issues.py` takes `--issues-repo
    OWNER/NAME` for exactly this cause, in exactly these words. The promotion inferred
    where the board declares, and they are the same repository.
    """
    source = (Path(__file__).resolve().parents[1] / "mechanisms" / "cycle"
              / "promote_to_develop.py").read_text(encoding="utf-8")
    for call in ('"pr", "list"', '"pr", "create"'):
        line = next(ln for ln in source.splitlines() if call in ln)
        assert "*scoped" in line, f"this gh call is still unscoped: {line.strip()}"


def test_every_remote_shape_yields_the_slug() -> None:
    """The host part is everything before the first `/`; a `:` in it means the slug starts
    after it. The first version keyed on `@`, and the consumer's remote has the user in
    ssh config — `alias-host:owner/repo.git` — so it parsed the alias as the slug.
    """
    from promote_to_develop import _owner_repo

    for url, expected in (
        ("alias-host:owner/repo.git", "owner/repo"),
        ("git@github.com:owner/repo.git", "owner/repo"),
        ("https://github.com/owner/repo.git", "owner/repo"),
        ("ssh://git@github.com:22/owner/repo.git", "owner/repo"),
        ("git@github.com:owner/repo", "owner/repo"),
    ):
        assert _owner_repo(lambda _b, _a, u=url: (0, u, ""), "git") == expected, url


def test_an_unparseable_remote_leaves_the_call_unscoped() -> None:
    """None rather than a guess: the call stays exactly as it was, which is the behaviour
    before this existed."""
    from promote_to_develop import _owner_repo

    assert _owner_repo(lambda _b, _a: (1, "", "no such remote"), "git") is None
    assert _owner_repo(lambda _b, _a: (0, "not-a-url", ""), "git") is None


def test_a_drift_gate_that_could_not_be_loaded_is_not_reported_as_no_reviews(tmp_path, monkeypatch) -> None:
    """`[], 0` on ImportError made the caller print a specific, false cause.

    "review drift: 0 record(s) examined — no `*-review-*.json` on disk" is a claim about
    the repository. What actually happened was that the gate module did not import, and
    the two shared a return value so nothing downstream could tell them apart.
    """
    import promote_to_develop as ptd

    monkeypatch.setitem(sys.modules, "check_review_binding", None)

    drifted, examined, why = ptd._reviews_that_drifted(tmp_path)

    assert drifted == []
    assert examined == ptd.UNCHECKED
    assert "could not be loaded" in why


def test_a_pr_whose_number_cannot_be_read_is_not_handed_to_merge() -> None:
    """`gh pr create` succeeding with unparseable output produced the literal `"?"`.

    That string went into `report.detail["pr"]` and then into `gh pr merge ?`, whose
    failure lands in the AWAITING branch — which tells the operator to wait for checks on
    a PR whose number nothing knows. The PR exists; what failed is reading its number,
    and that is what the operator has to be told.
    """
    report = promote.promote(ROOT, git=_git(), gh=_gh({
        "pr list": (0, "[]", ""),
        "pr create": (0, "created, but not a URL\n", ""),
        "pr merge": (0, "", ""),
    }))

    assert report.exit_code == promote.UNMEASURED, report.lines
    joined = "\n".join(report.lines)
    assert "number could not be read" in joined, joined
    assert "?" not in report.detail.get("pr", ""), report.detail


def test_a_pr_whose_number_reads_is_still_merged() -> None:
    """The refusal must be about the unreadable output, not about opening a PR."""
    report = promote.promote(ROOT, git=_git(), gh=_gh({
        "pr list": (0, "[]", ""),
        "pr create": (0, "https://github.com/o/r/pull/12\n", ""),
        "pr merge": (0, "", ""),
    }))

    assert "opened PR #12" in "\n".join(report.lines)
