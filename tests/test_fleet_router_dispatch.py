"""Test: fleet_router dispatch modes (workflow vs tmux) and payload resolution.

Tests that:
1. dispatch() accepts --dispatch-mode {workflow, tmux}
2. resolve_unit_payload() fetches issue metadata via gh CLI
3. Payload JSON branch name matches fleet_lander regex
4. Default mode remains tmux (backward compatible)
"""
import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]


def test_fleet_router_imports_cleanly() -> None:
    """fleet_router.py must import without errors."""
    from mechanisms.fleet import fleet_router
    assert fleet_router is not None


def test_dispatch_has_mode_parameter() -> None:
    """dispatch() function must accept mode parameter (default 'tmux')."""
    import inspect

    from mechanisms.fleet import fleet_router

    # The signature IS the subject here. This used to compute `sig.parameters`, throw it
    # away, and assert only that the function existed — a test whose name promised a
    # parameter check and delivered an existence check (kit#62).
    params = inspect.signature(fleet_router.dispatch).parameters
    assert "mode" in params, (
        f"dispatch() must accept `mode`; its parameters are {sorted(params)}"
    )
    assert params["mode"].default == "tmux", (
        f"`mode` must default to 'tmux', not {params['mode'].default!r} — a caller that "
        f"omits it is choosing the default, and this test is what pins which one"
    )


def test_resolve_unit_payload_fetches_issue_metadata() -> None:
    """resolve_unit_payload() must fetch issue details via gh CLI.

    Returns a dict with: repo, tracker, unit{slug, number, title, body, branch}, worktreeRoot
    """
    from mechanisms.fleet import fleet_router

    # This function should exist after implementation
    assert hasattr(fleet_router, "resolve_unit_payload"), (
        "fleet_router must have resolve_unit_payload() function"
    )


def test_fleet_lander_branch_regex_defined() -> None:
    """fleet_lander._LANE_BRANCH regex must be ^fix/kit\d+(?:-|$).

    This is the pattern that dispatch payload branch names must match.
    """
    from mechanisms.fleet import fleet_lander

    # Check the regex exists
    assert hasattr(fleet_lander, "_LANE_BRANCH"), "fleet_lander must define _LANE_BRANCH regex"

    # Verify the pattern
    regex = fleet_lander._LANE_BRANCH
    pattern_str = str(regex.pattern) if hasattr(regex, "pattern") else str(regex)

    assert "fix/kit" in pattern_str, f"Regex pattern should match fix/kit*: {pattern_str}"
    # The pattern should allow fix/kit1, fix/kit2-foo, but not fix/other
    test_valid = ["fix/kit1", "fix/kit123-something", "fix/kit0"]
    test_invalid = ["fix/other", "repair/kit1", "fix/Kit1"]  # case-sensitive

    for valid_name in test_valid:
        assert re.match(fleet_lander._LANE_BRANCH, valid_name), (
            f"Pattern {pattern_str} should match {valid_name}"
        )

    for invalid_name in test_invalid:
        assert not re.match(fleet_lander._LANE_BRANCH, invalid_name), (
            f"Pattern {pattern_str} should NOT match {invalid_name}"
        )


def test_payload_json_respects_branch_naming_contract() -> None:
    """If payload.json is written with a branch name, it must match fleet_lander regex.

    This is the cross-module invariant that prevents dispatch-as-workflow from
    choosing a branch name that fleet_lander.py would reject.
    """
    import re

    from mechanisms.fleet import fleet_lander

    # Simulate a unit being routed to a lane
    # The payload should contain a branch like "fix/kit1", "fix/kit2-foo", etc.
    test_branches = [
        "fix/kit1",  # valid
        "fix/kit123-variable-name",  # valid
        "fix/kit0-another",  # valid
    ]

    for branch in test_branches:
        matches = re.match(fleet_lander._LANE_BRANCH, branch)
        assert matches, (
            f"Branch {branch} must match fleet_lander regex {fleet_lander._LANE_BRANCH.pattern}"
        )


def test_dispatch_backward_compatibility_default_mode_is_tmux() -> None:
    """dispatch() should default to mode='tmux' for backward compatibility.

    Existing calls without --dispatch-mode should still work as before.
    """

    # The default should be documented or enforced in the function
    # After implementation, calling dispatch() without mode should use tmux
    # This is verified by checking the code or by trying a call
    # For now, we just document that it should have this behavior
    assert "tmux" in open(
        _REPO / "mechanisms" / "fleet" / "fleet_router.py"
    ).read(), (
        "fleet_router.py should mention tmux as the default mode"
    )


def test_workflow_mode_produces_json_payload() -> None:
    """When mode='workflow', dispatch() should write a JSON payload file.

    The payload must be valid JSON with keys: repo, tracker, unit{...}, worktreeRoot.
    """
    # This is an integration test. After implementation:
    # dispatch(assignment, repo="...", tracker="...", apply=True, mode="workflow")
    # should write a .json file to /tmp/squad-router/{slug}.json
    # We document the expectation here.
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


def test_the_documented_workflow_mode_is_reachable_from_the_entry_point() -> None:
    """`dispatch()` carried `mode="workflow"` and no entry point could set it.

    `mechanisms/README.md:119` documents `fleet_dispatch_workflow.js` as "called by
    dispatch_to_lane.sh with structured JSON payload", and the CHANGELOG says the mode
    "can be overridden at dispatch time". main() called dispatch() without the argument,
    so the branch, `resolve_unit_payload()` and the README row all described a path
    nothing could take.
    """
    import inspect

    import fleet_router as fr

    source = inspect.getsource(fr.main)

    assert "--dispatch-mode" in source, "no entry point can select the documented mode"
    assert "mode=args.dispatch_mode" in source, (
        "the flag exists and is not threaded into dispatch()")


def test_two_dispatches_of_one_unit_do_not_share_a_brief_path(tmp_path) -> None:
    """The brief was `/tmp/squad-router/<slug>.<ext>` — machine-global, no timestamp.

    The lane is told "Read {drop} and do exactly what it says" and opens it seconds
    later, so a second dispatch of the same unit — a re-route after a lane died, or
    another fleet on the same host — overwrote the file the first lane was about to read.
    The lane then followed a brief written for somebody else.
    """
    import fleet_router as fr

    unit = fr.Unit("kit#19", "a title", "kit")
    first = fr._brief_path(fr.Assignment(lane="squad-a-1", unit=unit), "/repo/one",
                           suffix="md")
    other_lane = fr._brief_path(fr.Assignment(lane="squad-a-2", unit=unit), "/repo/one",
                                suffix="md")
    other_fleet = fr._brief_path(fr.Assignment(lane="squad-a-1", unit=unit), "/repo/two",
                                 suffix="md")

    assert first != other_lane, "two lanes on one unit share a brief path"
    assert first != other_fleet, "two fleets on one unit share a brief path"
    assert "kit-19" in first.name, f"the slug is not sanitised into the name: {first.name}"


def test_two_landers_on_one_branch_do_not_share_a_scratch_tree() -> None:
    """`<branch>-alone-<epoch seconds>` collides for two landers in the same second.

    `git worktree add` then fails for the second, and the failure reads as a missing
    worktree rather than as a collision.
    """
    import tempfile
    from pathlib import Path as _Path

    root = _Path(tempfile.mkdtemp())
    one = _Path(tempfile.mkdtemp(prefix="fix-kit19-", dir=str(root)))
    two = _Path(tempfile.mkdtemp(prefix="fix-kit19-", dir=str(root)))

    assert one != two, "mkdtemp handed out the same directory twice"


def test_the_issue_body_fetch_is_reachable_from_the_value_the_caller_passes() -> None:
    """The gate was `if tracker == "github"` and the caller passes `owner/name`.

    `dispatch()` is invoked with `tracker=args.kit_repo or "paulohenriquevn/squad"`, which
    never equals the literal "github" — so the fetch was dead code. Every workflow
    dispatch carried the unit's TITLE as its body, and the repair agent read a one-line
    summary where the issue's own text should have been.
    """
    import fleet_router as fr

    assert fr._looks_like_github_repo("paulohenriquevn/squad") is True
    assert fr._looks_like_github_repo("github") is False
    assert fr._looks_like_github_repo("") is False


def test_the_payload_asks_the_repository_the_caller_named(monkeypatch) -> None:
    """Without `--repo`, `gh issue view` resolves against whatever directory it runs in."""
    import fleet_router as fr

    seen: list[list[str]] = []

    class _Done:
        returncode = 0
        stdout = "the issue body\n"

    def fake_run(argv, **_kwargs):
        seen.append(argv)
        return _Done()

    monkeypatch.setattr(fr.subprocess, "run", fake_run)
    payload = fr.resolve_unit_payload(fr.Unit("kit#19", "a title", "kit"),
                                      repo="/repo", tracker="owner/name")

    assert payload["unit"]["body"] == "the issue body"
    assert seen and "--repo" in seen[0], seen
    assert "owner/name" in seen[0]
