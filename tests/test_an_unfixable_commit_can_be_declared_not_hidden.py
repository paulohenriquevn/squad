"""A violation on a pushed commit can be declared — and only while it is unfixable.

Measured on this tree 2026-09-24. Commit `4b7c637` carries `fix(panel, install)` where
the convention it ships says comma-separated with no space, `fix(gates,board)`. The
rule is right, the commit is wrong, the commit is on the upstream, and this repository
forbids force-pushing a shared branch. So the standalone audit is correctly red and
there is no permitted action that clears it.

`check_contribution_conventions` already reasoned about this for the PRE-PUSH caller
and gave it `--introduced`. It deliberately did NOT give it to the standalone audit,
whose docstring says grading history IS the point. Both are right, which is why the
answer is neither a narrower range nor a weaker assertion: it is a DECLARATION, the
shape this kit already uses for a real finding it cannot fix now.

The safety property is the whole of it: an exemption is honoured only for a commit
already reachable from the upstream. It can never excuse work an author could still
amend, so it cannot become a way to skip the rule on the way in. A declaration for a
fixable commit is an ERROR, not an ignored line — the file says elsewhere that a
silently-dropped override reads as an accepted one.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "mechanisms" / "gates"))

from check_contribution_conventions import check, load_conventions  # noqa: E402


def _repo(tmp_path: Path, *, overrides: str, subject: str,
          push: bool) -> Path:
    """A repo with one bad commit, optionally reachable from an upstream."""
    origin, work = tmp_path / "origin.git", tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True)
    def run(*a):
        return subprocess.run(["git", "-C", str(work), *a], check=True,
                              capture_output=True, text=True)
    run("config", "user.email", "t@t")
    run("config", "user.name", "t")
    (work / "rules").mkdir(parents=True, exist_ok=True)
    (work / "rules" / "contribution-overrides.txt").write_text(overrides, encoding="utf-8")
    (work / "a.txt").write_text("a\n", encoding="utf-8")
    run("add", "-A")
    run("commit", "-qm", f"{subject}\n\nA body, so only the header is under test.\n")
    if push:
        run("push", "-q", "origin", "HEAD:refs/heads/main")
        run("branch", "--set-upstream-to=origin/main")
    return work


_BAD = "fix(panel, install): a header with a space in a two-area scope"
_EXEMPT = "commit_types = fix\npushed_exemptions = {sha} the space was pushed before the rule was read\n"


def test_without_a_declaration_the_audit_is_red(tmp_path: Path) -> None:
    """The control: the finding must be real before an exemption means anything."""
    repo = _repo(tmp_path, overrides="commit_types = fix\n", subject=_BAD, push=True)
    report = check(repo, "-40")
    assert [f.code for f in report.findings] == ["header_shape"], report.findings


def test_a_declaration_for_a_pushed_commit_clears_it(tmp_path: Path) -> None:
    repo = _repo(tmp_path, overrides="commit_types = fix\n", subject=_BAD, push=True)
    sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True).stdout.strip()
    (repo / "rules" / "contribution-overrides.txt").write_text(
        _EXEMPT.format(sha=sha), encoding="utf-8")
    report = check(repo, "-40")
    assert report.findings == [], [f"{f.sha} {f.code}" for f in report.findings]
    assert sha[:9] in " ".join(report.exempted), report.exempted


def test_a_declaration_for_a_commit_an_amend_can_reach_is_refused(tmp_path: Path) -> None:
    """The safety property. Without it this is a way to skip the rule on the way in."""
    repo = _repo(tmp_path, overrides="commit_types = fix\n", subject=_BAD, push=False)
    sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True).stdout.strip()
    (repo / "rules" / "contribution-overrides.txt").write_text(
        _EXEMPT.format(sha=sha), encoding="utf-8")
    report = check(repo, "-40")
    assert any(f.code == "exemption_is_fixable" for f in report.findings), report.findings
    assert any(f.code == "header_shape" for f in report.findings), (
        "the underlying violation must still be reported, not replaced by the meta-finding")


def test_an_exemption_without_a_reason_is_refused(tmp_path: Path) -> None:
    """A bare sha records that somebody waived it, not why."""
    path = tmp_path / "overrides.txt"
    path.write_text("pushed_exemptions = deadbeefdeadbeef\n", encoding="utf-8")
    try:
        load_conventions(path)
    except ValueError as exc:
        assert "reason" in str(exc).lower(), exc
    else:
        raise AssertionError("a sha with no reason was accepted")


def test_an_exemption_outside_the_checked_range_is_still_honoured(tmp_path: Path) -> None:
    """The pushed-ness question is about the repository, not about the range.

    `Report.already_pushed` holds only the shas IN the checked range, by design — it
    exists to tell an author which of the findings in front of them an amend can reach.
    Using it to decide whether an exemption is still needed was the wrong set: under
    `--introduced` on a synced branch the range is empty, so every exemption read as
    covering a fixable commit and `exemption_is_fixable` fired on all of them.

    Found within a minute of shipping it, by running the other of the two routes. The
    audit route was green and the pre-push route was red on the same declaration.
    """
    repo = _repo(tmp_path, overrides="commit_types = fix\n", subject=_BAD, push=True)
    sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True).stdout.strip()
    (repo / "rules" / "contribution-overrides.txt").write_text(
        _EXEMPT.format(sha=sha), encoding="utf-8")
    # An empty range: nothing was introduced, so nothing is in `already_pushed`.
    report = check(repo, "@introduced")
    assert report.commits_checked == 0, report.commits_checked
    assert report.findings == [], [f"{f.sha} {f.code}" for f in report.findings]
