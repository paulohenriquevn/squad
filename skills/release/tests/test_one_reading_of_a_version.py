r"""Every script in this slice reads a version the same way.

The slice parsed semver in three places, with three regexes that disagreed about the
shape this cycle cuts by default:

    detect_current_version  ^v?(\d+)\.(\d+)\.(\d+)$                  — no pre-release
    compute_next_version    ^v?(\d+)\.(\d+)\.(\d+)(?:-rc\.(\d+))?    — only `-rc.N`
    promote_unreleased      \d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?        — any pre-release

Three readings of one fact is the shape that diverges silently, and this one had: the
strictest reading blinded the chain to its own rc tags (see `test_the_rc_series_advances`),
and the loosest let `promote_unreleased` empty `[Unreleased]` under an rc — which
`cycle-release.md § The CHANGELOG moves once, at the final` forbids in prose and nothing
enforced.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
ROOT = Path(__file__).resolve().parents[3]

CHANGELOG = (
    "# Changelog\n\n## [Unreleased]\n\n### Added\n- a thing (#1)\n\n"
    "## [0.2.0] - 2026-01-01\n\n### Fixed\n- old (#0)\n"
)


def _promote(tmp_path: Path, version: str) -> subprocess.CompletedProcess[str]:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "promote_unreleased.py"),
         "--changelog", str(changelog), "--version", version, "--date", "2026-09-21"],
        capture_output=True, text=True,
        check=False,
    )


def test_the_slice_has_one_semver_reader() -> None:
    """A fourth regex is how the divergence comes back."""
    sources = [p for p in SCRIPTS.glob("*.py")]
    offenders = [
        p.name for p in sources
        if "\\d+)\\.(\\d+)\\.(\\d+" in p.read_text(encoding="utf-8")
        or r"\d+\.\d+\.\d+" in p.read_text(encoding="utf-8")
    ]
    assert offenders == [], (
        f"{offenders} parse a version themselves; import `squad.semver` instead"
    )


def test_promote_refuses_a_pre_release(tmp_path: Path) -> None:
    """Emptying `[Unreleased]` at `-rc.1` leaves rc.2 and the final nothing to publish."""
    result = _promote(tmp_path, "0.3.0-rc.1")

    assert result.returncode == 2, result.stdout
    assert "pre-release" in result.stderr
    assert (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8") == CHANGELOG, (
        "the file must be untouched by a refused promotion"
    )


def test_promote_accepts_a_final(tmp_path: Path) -> None:
    result = _promote(tmp_path, "0.3.0")

    assert result.returncode == 0, result.stderr
    body = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [0.3.0] - 2026-09-21" in body


def test_promote_refuses_an_identifier_the_kit_cannot_order(tmp_path: Path) -> None:
    """`-beta.1` is valid semver; it is not a version this kit cuts or can rank."""
    result = _promote(tmp_path, "0.3.0-beta.1")

    assert result.returncode == 2, result.stdout


def test_compute_and_detect_agree_on_what_a_version_is() -> None:
    """The two ends of the chain must accept the same strings, or one blinds the other."""
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(SCRIPTS))
    import compute_next_version

    from squad.semver import parse

    for version in ("0.3.0", "0.3.0-rc.2", "1.0.0-rc.1+build"):
        assert parse(version) is not None
        assert compute_next_version.parse_semver(version)[:3] == parse(version).core
