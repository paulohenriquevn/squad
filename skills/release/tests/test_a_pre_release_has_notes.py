r"""A pre-release publishes the notes the rule says it publishes.

`cycle-release.md` is explicit: *"an rc reads `[Unreleased]` for its release notes and
leaves it in place; the final promotes it."* Nothing implemented the first half. The
chain rendered notes with `--version "$NEXT_VERSION"`, and on an rc no such section
exists — `promote_unreleased.py` has not run and must not. Measured:

    $ render_release_notes.py --changelog CHANGELOG.md --version 0.3.0-rc.1
    version section [0.3.0-rc.1] not found in CHANGELOG.md
    exit=1   RELEASE_NOTES=[]

stderr, not stdout — so `RELEASE_NOTES=$(...)` captured the empty string, the shell did
not abort, and every rc opened its PR and its GitHub release with an EMPTY body. The
failure was silent in exactly the place a reader goes to find out what shipped.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"

CHANGELOG = (
    "# Changelog\n\n## [Unreleased]\n\n### Added\n- streaming responses (#12)\n\n"
    "## [0.2.0] - 2026-01-01\n\n### Fixed\n- old (#0)\n"
)


def _render(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "render_release_notes.py"),
         "--changelog", str(changelog), *args],
        capture_output=True, text=True,
    )


def test_a_pre_release_renders_the_unreleased_body(tmp_path: Path) -> None:
    result = _render(tmp_path, "--version", "0.3.0-rc.1")

    assert result.returncode == 0, result.stderr
    assert "streaming responses (#12)" in result.stdout
    assert result.stdout.strip() != ""


def test_the_pre_release_notes_say_they_are_provisional(tmp_path: Path) -> None:
    """A reader must not mistake an accumulating section for a finished release."""
    result = _render(tmp_path, "--version", "0.3.0-rc.1")

    assert "Unreleased" in result.stdout, (
        "the rc publishes a section that is still open and will keep growing; saying so "
        "is the difference between notes and a claim"
    )


def test_a_final_still_reads_its_own_versioned_section(tmp_path: Path) -> None:
    """The final promoted first, so its section exists and is what must be published."""
    result = _render(tmp_path, "--version", "0.2.0")

    assert result.returncode == 0, result.stderr
    assert "old (#0)" in result.stdout
    assert "streaming responses" not in result.stdout


def test_a_final_with_no_section_still_fails_loudly(tmp_path: Path) -> None:
    """The fallback is for pre-releases ONLY.

    A final whose section is missing means `promote_unreleased.py` did not run or wrote
    a malformed heading. Falling back to `[Unreleased]` there would publish the right
    text under a version whose record was never written — hiding the broken step.
    """
    result = _render(tmp_path, "--version", "9.9.9")

    assert result.returncode == 1
    assert "not found" in result.stderr


def test_empty_notes_are_refused_rather_than_printed(tmp_path: Path) -> None:
    """An empty body is the failure this test file exists for; it must exit non-zero."""
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## [Unreleased]\n\n## [0.2.0] - 2026-01-01\n\n- x\n",
                         encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "render_release_notes.py"),
         "--changelog", str(changelog), "--version", "0.3.0-rc.1"],
        capture_output=True, text=True,
    )

    assert result.returncode == 1, result.stdout
    assert "empty" in result.stderr.lower()
