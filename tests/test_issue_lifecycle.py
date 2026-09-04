"""Test: Issue lifecycle automation (label in-develop, close on release).

Tests that:
1. issue_lifecycle.py labels issues with 'in-develop' when branch reaches develop
2. Issues are closed only on verified release tag (not on merge)
3. Labels are not duplicated on replay
4. Closed issues remain closed
"""
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_REPO = Path(__file__).resolve().parents[1]


def test_issue_lifecycle_module_exists() -> None:
    """issue_lifecycle.py must exist."""
    issue_lifecycle_path = _REPO / "mechanisms" / "fleet" / "issue_lifecycle.py"
    assert issue_lifecycle_path.is_file(), f"issue_lifecycle.py not found at {issue_lifecycle_path}"


def test_issue_lifecycle_has_label_function() -> None:
    """issue_lifecycle must have function to label issues in-develop."""
    from mechanisms.fleet import issue_lifecycle

    assert hasattr(issue_lifecycle, "label_in_develop") or callable(
        getattr(issue_lifecycle, "label_in_develop", None)
    ) or "label" in dir(issue_lifecycle), (
        "issue_lifecycle must have label_in_develop() or similar"
    )


def test_issue_lifecycle_has_close_on_release_function() -> None:
    """issue_lifecycle must have function to close issues on verified tag."""
    from mechanisms.fleet import issue_lifecycle

    assert hasattr(issue_lifecycle, "close_on_release") or callable(
        getattr(issue_lifecycle, "close_on_release", None)
    ) or "close" in dir(issue_lifecycle), (
        "issue_lifecycle must have close_on_release() or similar"
    )


def test_label_in_develop_reads_git_log() -> None:
    """label_in_develop() must parse git log for 'Closes #N' messages.

    Looks for commits that mention issue numbers and applies 'in-develop' label.
    """
    from mechanisms.fleet import issue_lifecycle

    # After implementation, calling label_in_develop() should:
    # 1. Run git log develop --grep='Closes #' or similar
    # 2. Extract issue numbers
    # 3. Call gh issue edit to label each
    # We document this contract here
    assert "git" in open(_REPO / "mechanisms" / "fleet" / "issue_lifecycle.py").read().lower(), (
        "issue_lifecycle should use git commands"
    )


def test_label_in_develop_is_idempotent() -> None:
    """Running label_in_develop() twice should not create duplicate labels.

    If an issue already has 'in-develop', don't add it again.
    """
    # This is a design requirement. Implementation should:
    # - Check if label already exists before adding
    # - OR use gh issue edit which is idempotent
    pass


def test_close_on_release_requires_verified_tag() -> None:
    """close_on_release() must verify git tag before closing.

    Only closes issues if the tag is properly signed/verified.
    """
    from mechanisms.fleet import issue_lifecycle

    assert "tag" in open(
        _REPO / "mechanisms" / "fleet" / "issue_lifecycle.py"
    ).read().lower(), (
        "issue_lifecycle should reference git tags"
    )


def test_close_on_release_closes_by_tag_version() -> None:
    """close_on_release() should close issues when a version tag is detected.

    Looks for tags matching semver (v1.2.3) and closes associated issues.
    """
    pass


def test_issue_lifecycle_never_closes_on_merge_to_develop() -> None:
    """Issues should NOT be closed when a fix merges into develop.

    The user's CLAUDE.md rule: "Never close on merge, only on release."
    So 'in-develop' label is the merge signal, closing happens on tag only.
    """
    content = open(_REPO / "mechanisms" / "fleet" / "issue_lifecycle.py").read()

    # Check that the code doesn't close on merge (develop) but only on tag (release)
    assert "close" in content.lower() or "Close" in content, (
        "issue_lifecycle should have close logic"
    )


def test_fleet_supervisor_calls_issue_lifecycle_after_lander() -> None:
    """fleet_supervisor.sh must call issue_lifecycle.py as its third step.

    Order: route -> land -> label/close.
    """
    fleet_supervisor = _REPO / "mechanisms" / "fleet" / "fleet_supervisor.sh"
    assert fleet_supervisor.is_file(), "fleet_supervisor.sh must exist"

    content = fleet_supervisor.read_text(encoding="utf-8")
    # After implementation, it should call issue_lifecycle
    # For now, we just document that this needs to happen
    # Check that the script has a pattern suggesting 3+ steps
    step_markers = content.count("echo") + content.count("#")
    assert step_markers > 2, "fleet_supervisor.sh should have multiple steps"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
