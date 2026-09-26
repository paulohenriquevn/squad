"""Empty and absent are different failures and need different actions.

The checker returned a bool and printed "is empty or absent". One verdict carrying two
states tells a reader either to go add a heading that may already exist, or to fill one
that may not — and only one of those is the job in front of them.

The same conflation cost a consumer real time elsewhere in this kit on 2026-09-16, where
`approved` meant both "no plan was written" and "the plan exists and nothing advanced
the status", and the tool told 34 items holding finished plans to go write one.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SCRIPT = (Path(__file__).resolve().parents[1] / "scripts"
           / "changelog_section_nonempty.py")

_BODY = """# Changelog

## [Unreleased]

## [1.0.0] - 2026-01-01

### Added
- a thing
"""


def _run(tmp_path: Path, section: str) -> subprocess.CompletedProcess:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(_BODY, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--changelog", str(changelog),
         "--section", section],
        capture_output=True, text=True, timeout=120,
     check=False)


def test_a_present_but_empty_section_says_so(tmp_path: Path) -> None:
    result = _run(tmp_path, "Unreleased")
    assert result.returncode == 1
    assert "EMPTY" in result.stderr
    assert "ABSENT" not in result.stderr, "the reader is sent to add a heading that exists"


def test_an_absent_section_says_so(tmp_path: Path) -> None:
    result = _run(tmp_path, "9.9.9")
    assert result.returncode == 1
    assert "ABSENT" in result.stderr
    assert "EMPTY" not in result.stderr


def test_a_section_with_entries_passes(tmp_path: Path) -> None:
    assert _run(tmp_path, "1.0.0").returncode == 0


def test_a_missing_changelog_is_a_third_thing(tmp_path: Path) -> None:
    """Exit 2, not 1: the file is not there to have a section at all."""
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--changelog", str(tmp_path / "nope.md"),
         "--section", "Unreleased"],
        capture_output=True, text=True, timeout=120,
     check=False)
    assert result.returncode == 2
