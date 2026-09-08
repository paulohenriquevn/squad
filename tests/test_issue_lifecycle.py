"""The issue lifecycle: label when a fix reaches the integration branch, close on release.

WHAT THESE ASSERT, AND WHY THEY WERE REWRITTEN
-----------------------------------------------
The previous suite asserted that the string `"git"` appears in the module, that
`"tag"` appears in the module, and carried three `pass` bodies under names that
promised behaviour. `mechanisms/gates/check_prose_tests.py` exists because of
exactly that habit. Every defect the module actually had survived it:

  - `branch=` was dead code, so a scan of `develop` returned HEAD's commits;
  - `_run(..., check=False)` never raised, so a failed `gh issue edit` was
    appended to `labeled` and reported as done;
  - `git tag --verify` demands a GPG signature, so in a repository that does not
    sign tags nothing could ever close, and the report was indistinguishable from
    "there was nothing to close".

These tests run against real throwaway git repositories and a substituted command
runner, so they fail when the behaviour is wrong rather than when the wording is.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mechanisms.fleet import issue_lifecycle as il

_REPO = Path(__file__).resolve().parents[1]


# ── helpers ───────────────────────────────────────────────────────────────────

def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=True)
    return done.stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A repository whose HEAD commit closes #42, on a branch that is NOT develop."""
    root = tmp_path / "r"
    root.mkdir()
    _git(root.parent, "init", "-q", str(root))
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    (root / "a.txt").write_text("a", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "fix: thing\n\nCloses #42")
    return root


class _Recorder:
    """Substitutes the tracker, and only the tracker.

    `git` runs for real — the repositories below are real, and faking git would
    turn these into tests of the fake. Only `gh` is stood in for, because it needs
    a GitHub repository that does not exist here, and because making one call fail
    is how the "reported as done" defect is caught.
    """

    def __init__(self, *, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.calls: list[list[str]] = []
        self._real = il._run

    def __call__(self, cmd: list[str], **kwargs: object) -> il.Ran:
        self.calls.append(cmd)
        if cmd and cmd[0] != "gh":
            return self._real(cmd, **kwargs)  # type: ignore[arg-type]
        if self.fail_on and self.fail_on in " ".join(cmd):
            return il.Ran(False, "", "gh: could not resolve to a Repository")
        return il.Ran(True, "", "")


# ── the branch argument ───────────────────────────────────────────────────────

def test_the_branch_argument_selects_the_branch_that_is_scanned(repo: Path) -> None:
    """It did not. Three assignments to `cmd`, the last one `git log HEAD`.

    `label_in_develop` calls this with `branch="develop"` and got whatever HEAD
    happened to be — in a repository with no `develop` branch at all.
    """
    _git(repo, "branch", "release-only")

    assert il.find_issue_numbers(repo, branch="release-only") == {42}


def test_scanning_a_branch_that_does_not_exist_refuses_instead_of_returning_nothing(
    repo: Path,
) -> None:
    """"I could not look" must not read like "there is nothing there"."""
    with pytest.raises(il.LookupFailed):
        il.find_issue_numbers(repo, branch="no-such-branch")


def test_since_narrows_the_scan_to_what_came_after(repo: Path) -> None:
    first = _git(repo, "rev-parse", "HEAD")
    (repo / "b.txt").write_text("b", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "fix: other\n\nCloses #7")

    assert il.find_issue_numbers(repo, branch="HEAD") == {7, 42}
    assert il.find_issue_numbers(repo, branch="HEAD", since=first) == {7}


# ── a command that failed is not a command that worked ────────────────────────

def test_a_failed_label_call_is_reported_as_an_error_not_as_labelled(
    repo: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The defect, in one assertion.

    Reproduced 2026-09-08 in a repository with no remote: `gh issue edit` exited
    non-zero and the report came back `{'labeled': [42], 'errors': []}`.
    """
    _git(repo, "branch", "develop")
    monkeypatch.setattr(il, "_run", _Recorder(fail_on="gh issue edit"))

    result = il.label_in_develop(repo)

    assert result["labeled"] == []
    assert len(result["errors"]) == 1
    assert "42" in result["errors"][0]


def test_a_successful_label_call_is_reported_as_labelled(
    repo: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _git(repo, "branch", "develop")
    recorder = _Recorder()
    monkeypatch.setattr(il, "_run", recorder)

    result = il.label_in_develop(repo)

    assert result["labeled"] == [42]
    assert result["errors"] == []
    assert any("gh" in c[0] and "edit" in c for c in recorder.calls)


def test_an_unreachable_branch_is_an_error_not_an_empty_success(
    repo: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No `develop` branch: nothing is labelled and the reason is stated."""
    monkeypatch.setattr(il, "_run", _Recorder())

    result = il.label_in_develop(repo)

    assert result["labeled"] == []
    assert result["errors"], "an unreadable branch must be reported"


# ── closing on release ────────────────────────────────────────────────────────

def _tagged(repo: Path) -> Path:
    """v0.1.0, then a fix closing #7, then v0.2.0 — an ordinary unsigned release."""
    _git(repo, "tag", "v0.1.0")
    (repo / "c.txt").write_text("c", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "fix: another\n\nCloses #7")
    _git(repo, "tag", "v0.2.0")
    return repo


def test_an_unsigned_tag_still_closes_the_issues_its_range_shipped(
    repo: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`git tag --verify` demands GPG; this repository does not sign tags.

    Every tag was skipped by a bare `continue`, so `close_on_release` returned
    `{"closed": [], "errors": []}` — the same value as "nothing to close".
    """
    _tagged(repo)
    monkeypatch.setattr(il, "_run", _Recorder())

    result = il.close_on_release(repo)

    assert 7 in result["closed"]


def test_it_reads_the_range_since_the_previous_tag_not_the_tagged_commit_alone(
    repo: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A release cut as a merge PR carries `Closes #N` in the commits, not the tag."""
    _git(repo, "tag", "v0.1.0")
    (repo / "d.txt").write_text("d", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "fix: earlier in the range\n\nCloses #9")
    (repo / "e.txt").write_text("e", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "chore: the commit the tag points at")
    _git(repo, "tag", "v0.2.0")
    monkeypatch.setattr(il, "_run", _Recorder())

    assert 9 in il.close_on_release(repo)["closed"]


def test_a_failed_close_call_is_reported_as_an_error_not_as_closed(
    repo: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _tagged(repo)
    monkeypatch.setattr(il, "_run", _Recorder(fail_on="gh issue close"))

    result = il.close_on_release(repo)

    assert result["closed"] == []
    assert result["errors"]


def test_requiring_a_signature_reports_the_skip_instead_of_swallowing_it(
    repo: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Signature verification stays available, and its refusals are visible."""
    _tagged(repo)
    monkeypatch.setattr(il, "_run", _Recorder())

    result = il.close_on_release(repo, require_signature=True)

    assert result["closed"] == []
    assert any("v0.2.0" in s for s in result["skipped"]), result


def test_a_repository_with_no_tags_says_so_and_closes_nothing(
    repo: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(il, "_run", _Recorder())

    result = il.close_on_release(repo)

    assert result["closed"] == []
    assert result["errors"] == []


# ── the rule this module exists to enforce ────────────────────────────────────

def test_reaching_the_integration_branch_labels_and_never_closes(
    repo: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """"Never close on merge, only on release" — enforced, not asserted in prose."""
    _git(repo, "branch", "develop")
    recorder = _Recorder()
    monkeypatch.setattr(il, "_run", recorder)

    il.label_in_develop(repo)

    assert not any("close" in " ".join(c) for c in recorder.calls)


def test_an_unsupported_tracker_is_refused_by_both_entry_points(repo: Path) -> None:
    for result in (il.label_in_develop(repo, tracker="jira"),
                   il.close_on_release(repo, tracker="jira")):
        assert result["errors"]


def test_fleet_supervisor_calls_issue_lifecycle_after_the_lander() -> None:
    """Order: route -> land -> label/close."""
    content = (_REPO / "mechanisms" / "fleet" / "fleet_supervisor.sh").read_text(
        encoding="utf-8"
    )

    assert "issue_lifecycle" in content
    assert content.index("fleet_lander") < content.index("issue_lifecycle")
