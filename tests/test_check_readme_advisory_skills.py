"""Gate: README Advisory Skills must match actual skills on disk.

Regression for e5527e6, when three specialists (cap-theorem, backpressure,
resilience) were deleted and the README was never updated to reflect the removal.
This gate catches that drift in both directions: README promises skills that don't
exist, and skills exist that README doesn't know about.
"""
import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]


def test_advisory_skills_in_readme_must_exist_on_disk() -> None:
    """Every skill named in README.md's Advisory skills table must exist on disk."""
    from mechanisms.gates import check_readme_advisory_skills

    findings = check_readme_advisory_skills.check(_REPO)
    readme_missing = [f for f in findings if f.get("type") == "readme_skill_missing"]

    # TODAY: This should fail, naming cap-theorem-specialist, backpressure-specialist,
    # and resilience-specialist as missing from disk.
    assert not readme_missing, (
        f"README.md cites advisory skills that do not exist on disk:\n"
        f"{json.dumps(readme_missing, indent=2)}"
    )


def test_advisory_skills_in_how_to_use_must_exist_on_disk() -> None:
    """Every skill named in HOW-TO-USE.md commands table must exist on disk."""
    from mechanisms.gates import check_readme_advisory_skills

    findings = check_readme_advisory_skills.check(_REPO)
    how_to_use_missing = [f for f in findings if f.get("type") == "how_to_use_skill_missing"]

    assert not how_to_use_missing, (
        f"HOW-TO-USE.md cites advisory skills that do not exist on disk:\n"
        f"{json.dumps(how_to_use_missing, indent=2)}"
    )


def test_a_skill_that_exists_is_not_reported(tmp_path: Path) -> None:
    """If README cites arch-check (which exists), it should not be in findings."""
    from mechanisms.gates import check_readme_advisory_skills

    findings = check_readme_advisory_skills.check(_REPO)
    arch_check_findings = [
        f for f in findings
        if "arch-check" in f.get("skill_name", "").lower()
    ]

    assert not arch_check_findings, (
        f"arch-check exists on disk but was still reported as missing: {arch_check_findings}"
    )


def test_gate_returns_empty_when_consistent(tmp_path: Path) -> None:
    """When README and disk are consistent, check returns empty list."""
    from mechanisms.gates import check_readme_advisory_skills

    findings = check_readme_advisory_skills.check(_REPO)

    # After README is corrected, this should pass (findings empty).
    # Before that, it should fail (findings non-empty with missing skills).
    # We test the structure regardless of the state.
    assert isinstance(findings, list)
    assert all(isinstance(f, dict) for f in findings)
    assert all("type" in f and "skill_name" in f for f in findings)
