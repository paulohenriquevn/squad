"""`--version` took one semver, and a monorepo cuts three packages at once.

Measured 2026-09-22 promoting a release that published three packages together.
`promote_unreleased.py --version 'create-theokit 3.0.2, @theokit/http 2.3.0, theokit
0.69.0'` refused with *not a semver version ... Expected MAJOR.MINOR.PATCH*, while the
three sections below the one being written read:

    ## [create-theokit 3.0.1, @theokit/http 2.2.0, theokit 0.68.0] - 2026-09-21
    ## [theokit 0.67.0] - 2026-09-18
    ## [@theokit/agents 15.0.0, @theokit/presenter 0.10.0, theokit 0.66.1] - 2026-09-18

So the mechanism could not perform the promotion its own cycle rule prescribes
(`cycle-release.md` — "The CHANGELOG moves once, at the final") for the shape that
repository releases in most of the time. The promotion was done by hand, and the heading
was read off the file rather than invented — which is the only reason it stayed consistent.

Every component is still VALIDATED. The point was never that the heading is free text: a
typo lands in a record nobody edits again, and `render_release_notes.py` looks the section
up by exact string. What changes is that "one version" stops being the only shape a
release can have.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from squad.semver import parse_release  # noqa: E402


def test_a_bare_semver_is_one_unnamed_component() -> None:
    """THE CONTROL — the single-package path must not change."""
    parsed = parse_release("1.2.0")

    assert parsed is not None
    assert [(name, str(v)) for name, v in parsed] == [(None, "1.2.0")]


def test_three_packages_parse_in_the_order_written() -> None:
    parsed = parse_release("create-theokit 3.0.2, @theokit/http 2.3.0, theokit 0.69.0")

    assert parsed is not None
    assert [(n, str(v)) for n, v in parsed] == [
        ("create-theokit", "3.0.2"),
        ("@theokit/http", "2.3.0"),
        ("theokit", "0.69.0"),
    ]


def test_one_bad_component_refuses_the_whole_line() -> None:
    """Partial acceptance would write a heading with a typo in one of three packages.

    That heading is never edited again, and the reader who later cannot find the section
    is told their argument is wrong rather than that the record is.
    """
    assert parse_release("theokit 0.69.0, @theokit/http 2.3.O") is None


def test_a_leading_v_is_refused_here_as_everywhere() -> None:
    assert parse_release("theokit v0.69.0") is None
    assert parse_release("v1.2.0") is None


def test_a_component_with_no_version_is_refused() -> None:
    assert parse_release("theokit, @theokit/http 2.3.0") is None


def test_empty_is_refused_rather_than_read_as_zero_packages() -> None:
    assert parse_release("") is None
    assert parse_release("  ,  ") is None


def test_a_prerelease_component_is_parsed_and_left_for_the_caller_to_refuse() -> None:
    """Parsing and policy are separate: `promote_unreleased` owns the rc refusal.

    Putting it here would stop `render_release_notes.py`, which legitimately reads an rc
    heading, from using the same reader.
    """
    parsed = parse_release("theokit 1.2.0-rc.1")

    assert parsed is not None
    assert parsed[0][1].is_prerelease


# ── the mechanism, not only the reader ───────────────────────────────────────

import subprocess  # noqa: E402

PROMOTE = _ROOT / "skills" / "release" / "scripts" / "promote_unreleased.py"

CHANGELOG = """# Changelog

## [Unreleased]

### Added

- a thing (#1)

## [theokit 0.67.0] - 2026-09-18

### Fixed

- an older thing (#0)
"""


def _promote(tmp_path: Path, version: str) -> tuple[int, str, str]:
    path = tmp_path / "CHANGELOG.md"
    path.write_text(CHANGELOG, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(PROMOTE), "--changelog", str(path),
         "--version", version, "--date", "2026-09-22"],
        capture_output=True, text=True, check=False,
    )
    return proc.returncode, proc.stderr, path.read_text(encoding="utf-8")


def test_a_multi_package_promotion_writes_the_heading_it_was_given(tmp_path: Path) -> None:
    line = "create-theokit 3.0.2, @theokit/http 2.3.0, theokit 0.69.0"

    code, err, body = _promote(tmp_path, line)

    assert code == 0, err
    assert f"## [{line}] - 2026-09-22" in body
    assert "- a thing (#1)" in body


def test_a_single_package_promotion_is_unchanged(tmp_path: Path) -> None:
    code, err, body = _promote(tmp_path, "1.2.0")

    assert code == 0, err
    assert "## [1.2.0] - 2026-09-22" in body


def test_one_bad_component_refuses_and_leaves_the_file_alone(tmp_path: Path) -> None:
    code, err, body = _promote(tmp_path, "theokit 0.69.0, @theokit/http 2.3.O")

    assert code == 2
    assert "not a release line this kit cuts" in err
    assert "## [Unreleased]" in body, "a refusal must not half-promote"


def test_a_prerelease_in_any_component_refuses_the_line(tmp_path: Path) -> None:
    """Promoting at rc empties [Unreleased] for every package in the heading."""
    code, err, body = _promote(tmp_path, "theokit 0.69.0, @theokit/http 2.3.0-rc.1")

    assert code == 2
    assert "refusing to promote under a pre-release" in err
    assert "## [Unreleased]" in body
