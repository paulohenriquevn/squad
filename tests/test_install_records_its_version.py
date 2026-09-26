"""An installed kit must be able to say which version it is.

The manifest recorded `# kit-source: <path>` — where the copy came from — and nothing
recorded WHAT it was. `sync_consumers.py` needs exactly that as its `--base`, and with
no marker the operator has to guess a sha for the whole fleet at once.

Measured 2026-09-16 across 55 consumers: three distinct contents of one file, and NONE
of them matched any commit in the kit's history. Every install had come from a dirty
working tree. With one `--base` for all of them the only reachable classification was
LOCAL_CHANGE, so the sync tool refused all 55 — correctly, and uselessly.

The dirty flag is recorded rather than refused. Installing from a working tree is how
this kit is developed, and forbidding it would stop the loop that finds the defects;
saying so is what lets the sync tool tell a fossil from a release.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_KIT / "mechanisms" / "distribution"))


def _install(tmp_path: Path) -> str:
    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True, timeout=120)
    subprocess.run(["bash", str(_KIT / "mechanisms" / "distribution" / "install.sh"),
                    str(tmp_path)], check=True, timeout=900,
                   capture_output=True, text=True)
    return (tmp_path / ".claude" / ".kit-manifest.txt").read_text(encoding="utf-8")


def test_the_manifest_records_the_commit_not_only_the_path(tmp_path: Path) -> None:
    manifest = _install(tmp_path)
    lines = [ln for ln in manifest.splitlines() if ln.startswith("# kit-commit:")]
    assert lines, "an installed kit cannot say which version it is"
    value = lines[0].split(":", 1)[1].strip()
    assert value, "the marker is present and empty, which answers nothing"


def test_an_install_from_a_dirty_tree_says_so(tmp_path: Path) -> None:
    """A sha alone would claim a version this copy does not match."""
    dirty = bool(subprocess.run(
        ["git", "-C", str(_KIT), "status", "--porcelain", "--untracked-files=no"],
        capture_output=True, text=True, timeout=120, check=False).stdout.strip())
    manifest = _install(tmp_path)
    line = next(ln for ln in manifest.splitlines() if ln.startswith("# kit-commit:"))
    if dirty:
        assert "dirty" in line, \
            "installed from uncommitted changes and claimed the commit anyway"
    else:
        assert "dirty" not in line


def test_the_sync_tool_refuses_a_dirty_marker_as_a_base(tmp_path: Path) -> None:
    """A dirty install has no commit that describes it. Comparing against the sha it
    was built near is how a fossil gets classified as a release."""
    from sync_consumers import base_from_manifest

    claude = tmp_path / ".claude"
    claude.mkdir()
    marker = claude / ".kit-manifest.txt"
    marker.write_text("# kit-commit: abc123 (dirty — this install does not match that"
                      " commit)\n", encoding="utf-8")
    assert base_from_manifest(tmp_path) is None
    marker.write_text("# kit-commit: abc123\n", encoding="utf-8")
    assert base_from_manifest(tmp_path) == "abc123"
