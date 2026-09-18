"""Work that never lands fills the fleet and stops it.

A lane commits on its branch and stops — correctly: pushing and merging are not
its call. So a person pushed the branch, merged it, and freed the lane. Measured
2026-09-03: five repairs completed by lanes, five landed by hand, and the router
that now hands work out would fill every lane and then have nowhere to put the
sixth.

The lander closes that end. What it will not do is the point:

- it never pushes a red tree, and never decides a suite is green from an exit
  code it did not read;
- it merges in a scratch worktree cut from `origin/workspace`, so a merge that
  turns out red is discarded rather than left in anyone's working tree;
- it does not open a PR to `develop` and does not close an issue. Both are the
  operator's, and the rules say so.
"""
from __future__ import annotations

import sys
from pathlib import Path

_FLEET = Path(__file__).resolve().parents[1] / "mechanisms" / "fleet"
if str(_FLEET) not in sys.path:
    sys.path.insert(0, str(_FLEET))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
import fleet_lander  # noqa: E402 — post-bootstrap import


def _c(ok: bool, out: str = "", err: str = "") -> fleet_lander.Ran:
    return fleet_lander.Ran(ok=ok, stdout=out, stderr=err)


# ── what it refuses ───────────────────────────────────────────────────────────


def test_a_branch_whose_suite_fails_is_not_landed() -> None:
    verdict = fleet_lander.assess(branch="fix/kit19-x", suite=_c(False, "3 failed"),
                                  merge=_c(True), after=_c(True))
    assert not verdict.land
    assert "3 failed" in verdict.reason


def test_a_merge_that_conflicts_is_not_forced() -> None:
    verdict = fleet_lander.assess(branch="fix/kit19-x", suite=_c(True, "1300 passed"),
                                  merge=_c(False, err="CONFLICT (content)"), after=_c(True))
    assert not verdict.land
    assert "CONFLICT" in verdict.reason


def test_a_merge_that_goes_red_after_merging_is_discarded_not_pushed() -> None:
    """Two green branches can merge into a red tree. The scratch worktree exists
    for exactly this, and the answer is to throw the merge away."""
    verdict = fleet_lander.assess(branch="fix/kit19-x", suite=_c(True, "1300 passed"),
                                  merge=_c(True), after=_c(False, "1 failed"))
    assert not verdict.land
    assert "after the merge" in verdict.reason


def test_a_green_branch_that_merges_clean_and_stays_green_lands() -> None:
    verdict = fleet_lander.assess(branch="fix/kit19-x", suite=_c(True, "1300 passed"),
                                  merge=_c(True), after=_c(True, "1305 passed"))
    assert verdict.land


# ── a suite result is read, never assumed ─────────────────────────────────────


def test_a_suite_that_could_not_be_run_is_not_a_pass() -> None:
    verdict = fleet_lander.assess(branch="fix/kit19-x", suite=None,
                                  merge=_c(True), after=_c(True))
    assert not verdict.land
    assert "not run" in verdict.reason.lower()


def test_a_suite_reporting_zero_tests_is_not_a_pass() -> None:
    """`pytest` exits 5 on an empty collection, and a wrapper that only checks
    for a non-zero code reads that as success. This kit's most-found defect."""
    verdict = fleet_lander.assess(branch="fix/kit19-x", suite=_c(True, "no tests ran"),
                                  merge=_c(True), after=_c(True))
    assert not verdict.land
    assert "no tests" in verdict.reason.lower()


# ── what it will not decide ───────────────────────────────────────────────────


def test_it_never_closes_the_issue() -> None:
    source = (_FLEET / "fleet_lander.py").read_text(encoding="utf-8")
    assert "issue close" not in source, (
        "closing an issue asserts the fix is available to whoever is blocked by "
        "it, and a merge to the working branch is not availability")


def test_it_never_opens_a_pull_request_to_develop() -> None:
    source = (_FLEET / "fleet_lander.py").read_text(encoding="utf-8")
    assert "pr create" not in source


#: A bypass skips a check, or discards work somebody else did. Named as pairs
#: rather than as bare flags on purpose: `worktree remove --force` deletes a
#: scratch directory this module created three lines earlier and bypasses
#: nothing, while `push --force` overwrites a branch other people are on. A
#: substring ban could not tell them apart and flagged the first, so the rule is
#: stated at the precision the distinction actually has.
_BYPASSES = ("--no-verify", "--skip-checks", "--allow-dirty-tree",
             "push --force", "push -f", "reset --hard", "reset --mixed",
             "git checkout", "git revert")


def test_it_never_reaches_for_a_bypass() -> None:
    source = (_FLEET / "fleet_lander.py").read_text(encoding="utf-8")
    commands = [ln for ln in source.splitlines() if '"git"' in ln or '"push"' in ln
                or "pytest" in ln]
    joined = " ".join(" ".join(ln.replace('"', " ").split()) for ln in commands)
    for forbidden in _BYPASSES:
        assert forbidden not in joined, f"the lander builds a command with {forbidden}"


def test_the_only_force_it_uses_is_on_a_directory_it_made_itself() -> None:
    """Pins the exception the rule above allows, so a second `--force` cannot be
    added later under cover of this one."""
    source = (_FLEET / "fleet_lander.py").read_text(encoding="utf-8")
    forced = [ln.strip() for ln in source.splitlines()
              if "--force" in ln and "run([" in ln]
    assert len(forced) == 1, f"expected exactly one --force, found {len(forced)}: {forced}"
    assert "worktree" in forced[0] and "remove" in forced[0]


# ── a cleanup that fails must say so ──────────────────────────────────────────
# Measured 2026-09-03, on this module's first live run: a scratch worktree
# survived the branch that created it, and WHY could not be answered — the
# `finally` block called `run(...)` and discarded the result. A silent cleanup
# failure leaks a worktree per branch per pass, and over a supervisor loop that
# fills the disk while every report says the branch was assessed cleanly.


def test_a_worktree_that_would_not_be_removed_is_reported() -> None:
    verdict = fleet_lander.assess(branch="fix/kit19-x", suite=_c(True, "1300 passed"),
                                  merge=_c(True), after=_c(True, "1305 passed"),
                                  cleanup=[_c(False, err="fatal: is not a working tree")])
    assert verdict.land, "cleanup must not change whether the code was good"
    assert "not a working tree" in verdict.reason
    assert "leak" in verdict.reason.lower()


def test_a_clean_cleanup_adds_nothing_to_the_reason() -> None:
    verdict = fleet_lander.assess(branch="fix/kit19-x", suite=_c(True, "1300 passed"),
                                  merge=_c(True), after=_c(True, "1305 passed"),
                                  cleanup=[_c(True), _c(True)])
    assert "leak" not in verdict.reason.lower()


def test_a_refusal_still_reports_a_failed_cleanup() -> None:
    """The branch being bad is not a reason to stop reporting a leaked directory."""
    verdict = fleet_lander.assess(branch="fix/kit19-x", suite=_c(False, "3 failed"),
                                  merge=None, after=None,
                                  cleanup=[_c(False, err="fatal: is not a working tree")])
    assert not verdict.land
    assert "3 failed" in verdict.reason
    assert "leak" in verdict.reason.lower()


# ── a long run must not look like a hung one ──────────────────────────────────
# Measured 2026-09-03: the lander ran for 16 minutes across five branches and
# printed nothing, because every verdict was collected first and reported at the
# end. Two full suites per branch is slow by design — what it protects is the
# branch every other lane cuts from — but silence for an hour is the same failure
# as the lead going quiet: a working process and a dead one look identical.


def test_each_verdict_is_reported_as_it_lands(capsys) -> None:
    seen: list[str] = []
    verdicts = {"fix/kit19-a": fleet_lander.Verdict(True, "fix/kit19-a: green"),
                "fix/kit20-b": fleet_lander.Verdict(False, "fix/kit20-b: 3 failed")}

    def fake_land(_repo, branch, **_kw):
        seen.append(branch)
        # by the time the SECOND branch starts, the first must already be printed
        if len(seen) == 2:
            assert "fix/kit19-a" in capsys.readouterr().out, \
                "the first verdict was still being held when the second began"
        return verdicts[branch]

    fleet_lander.report_each(["fix/kit19-a", "fix/kit20-b"], assess_branch=fake_land,
                             repo=Path("/srv/example/kit"), apply=False, timeout=60)


def test_the_stream_says_which_branch_it_is_starting(capsys) -> None:
    """Naming the branch BEFORE the suites run is what tells a reader which of
    the five it is on, twelve minutes in."""
    fleet_lander.report_each(
        ["fix/kit19-a"],
        assess_branch=lambda _r, b, **_k: fleet_lander.Verdict(True, f"{b}: green"),
        repo=Path("/srv/example/kit"), apply=False, timeout=60)
    out = capsys.readouterr().out
    assert out.index("fix/kit19-a") < out.rindex("fix/kit19-a"), \
        "the branch is named once on start and once on verdict"


def test_a_conflicting_merge_is_refused_without_paying_for_a_suite() -> None:
    """The merge check costs seconds; a suite costs minutes. Order matters.

    Measured on the runner 2026-09-04 (kit#26): three branches conflicted on
    CHANGELOG.md, and the lander ran two suites for each before reaching the
    merge that could never apply. Three consecutive passes, ~20 minutes each,
    an hour of fleet time spent proving branches correct that git would not
    let land regardless.
    """
    verdict = fleet_lander.assess(branch="fix/kit19-x", suite=None,
                                  merge=_c(False, "CONFLICT (content): Merge conflict in CHANGELOG.md"),
                                  after=None)
    assert not verdict.land
    # The reason must name the merge, not the unrun suite: an operator reading
    # "the suite was not run" goes looking for a broken test runner.
    assert "merge did not apply" in verdict.reason
    assert "suite was not run" not in verdict.reason


def test_a_branch_listing_that_failed_is_not_an_empty_sweep(tmp_path) -> None:
    """`main`'s own comment: "'nothing to land' and 'I did not look' must not read the
    same, and on this kit they have before."

    `lane_branches` returned `[]` when `git branch -a` failed — git missing, a broken
    repository, a timeout, all folded into `Ran(ok=False)` — and `main` rendered that as
    "swept the repository: no lane branch is ahead of origin/workspace", exit 0.
    """
    import fleet_lander as fl

    not_a_repo = tmp_path / "nothing"
    not_a_repo.mkdir()

    assert fl.lane_branches(not_a_repo) is None


def test_a_fetch_that_failed_stops_the_sweep(tmp_path, monkeypatch) -> None:
    """A sweep over stale remote-tracking refs is not a sweep."""
    import fleet_lander as fl

    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)

    def fake_run(cmd, **kwargs):
        if "fetch" in cmd:
            return fl.Ran(False, "", "fatal: could not read Username for 'https://github.com'")
        return fl.Ran(True, "", "")

    monkeypatch.setattr(fl, "run", fake_run)

    code = fl.main(["--repo", str(repo)])

    assert code == 2


# ── two landers on one branch must not pick the same scratch path ────────────
#
# The names were `<branch>-alone-<epoch seconds>` under a machine-global root, so
# two landers on the same branch within the same second — the supervisor's land
# loop plus an operator's manual `--apply`, or two supervisors — picked the same
# paths. `git worktree add` then failed for the second, and the failure reads as a
# missing worktree rather than as a collision.


def test_two_landings_of_one_branch_get_different_trees(monkeypatch, tmp_path) -> None:
    """The property, exercised rather than asserted about the source."""
    seen: list[str] = []

    def _capture(argv, **_kw):
        if "worktree" in argv and "add" in argv:
            seen.append(argv[argv.index("add") + 2])
        return fleet_lander.Ran(ok=False, stderr="stubbed")

    monkeypatch.setattr(fleet_lander, "run", _capture)
    monkeypatch.setattr(fleet_lander.tempfile, "gettempdir", lambda: str(tmp_path))

    for _ in range(2):
        fleet_lander.land(tmp_path, "fix/kit19-a", apply=False, timeout=5)

    assert len(seen) >= 2, f"no worktree add was attempted: {seen}"
    assert len(set(seen)) == len(seen), f"two landings picked the same path: {seen}"


def test_the_scratch_path_carries_the_branch_name(monkeypatch, tmp_path) -> None:
    """Uniqueness must not cost legibility: an operator reading `ls` needs the branch."""
    seen: list[str] = []

    def _capture(argv, **_kw):
        if "worktree" in argv and "add" in argv:
            seen.append(argv[argv.index("add") + 2])
        return fleet_lander.Ran(ok=False, stderr="stubbed")

    monkeypatch.setattr(fleet_lander, "run", _capture)
    fleet_lander.land(tmp_path, "fix/kit19-a", apply=False, timeout=5)

    assert seen, "no worktree add was attempted"
    assert "fix-kit19-a" in seen[0], seen[0]
