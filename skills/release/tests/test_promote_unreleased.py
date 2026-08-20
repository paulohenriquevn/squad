"""B-046 — a CHANGELOG with two `## [Unreleased]` sections must stop the release, not be promoted around.

Measured on this repository: `grep -n "^## \\[Unreleased\\]" CHANGELOG.md` returns lines 6 and 610.
The second sits between `## [0.52.0]` and `## [0.51.0]` and duplicates, byte for byte, an entry
already correctly filed under 0.52.0 — residue of an old promote that copied instead of moving.

`promote_unreleased.py` matches the FIRST heading and stops, so the second is not skipped with a
warning: it is never seen. Both releases cut this session ran past it in silence.

The refusal names BOTH line numbers, because a message that says only "duplicate found" announces a
problem without pointing at it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "promote_unreleased.py"

WELL_FORMED = """# Changelog

## [Unreleased]

### Added

- A thing that has not shipped.

## [0.1.0] - 2026-01-01

### Added

- The first thing.
"""

TWO_SECTIONS = """# Changelog

## [Unreleased]

### Added

- A thing that has not shipped.

## [0.2.0] - 2026-02-01

### Added

- **A published thing.**

## [Unreleased]

### Added

- **A published thing.**

## [0.1.0] - 2026-01-01

### Added

- The first thing.
"""


def _run(changelog: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--changelog", str(changelog),
         "--version", "9.9.9", "--date", "2026-08-18"],
        capture_output=True, text=True, check=False,
    )


def test_two_unreleased_sections_are_refused(tmp_path: Path) -> None:
    # Arrange — the shape this repository actually carries: a stale section BELOW a released one.
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(TWO_SECTIONS, encoding="utf-8")
    before = changelog.read_text(encoding="utf-8")

    # Act
    result = _run(changelog)

    # Assert — refused, with both locations named, and the file left untouched. Merging or picking
    # one would move a RELEASED entry back into the unreleased set and re-announce it; which section
    # is correct is a judgement about what shipped, and the tool cannot make it.
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "3" in output and "15" in output, output
    assert changelog.read_text(encoding="utf-8") == before


def test_a_well_formed_changelog_still_promotes(tmp_path: Path) -> None:
    # The control. A refusal that fired on everything would satisfy the test above.
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(WELL_FORMED, encoding="utf-8")

    result = _run(changelog)

    assert result.returncode == 0, result.stdout + result.stderr
    promoted = changelog.read_text(encoding="utf-8")
    assert "## [9.9.9] - 2026-08-18" in promoted
