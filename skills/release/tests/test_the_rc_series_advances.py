r"""The release cycle must be able to read the releases it cut itself.

`cycle-release.md` makes `--pre` the default because most cuts are pre-releases. Until
this file existed, the first step of the chain could not see one: `detect_current_version`
matched `^v?(\d+)\.(\d+)\.(\d+)$`, so every `-rc.N` tag it had cut was reported as "not
semver" and skipped. Measured on a repository holding `v0.2.0`, `v0.3.0-rc.1`, `v0.3.0-rc.2`:

    detect_current_version  ->  0.2.0        ("note: 2 tag(s) not semver, skipped")
    compute --mode pre      ->  0.3.0-rc.1   — a tag that already exists

The series never reached `rc.3`, and a repository whose ONLY tags were rc was refused
outright as having "no semver tag" — a release cycle blind to its own output.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _repo(tmp_path: Path, tags: list[str]) -> Path:
    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=a@b", "-c", "user.name=a",
         "commit", "-q", "--allow-empty", "-m", "x"],
        cwd=tmp_path, check=True,
    )
    for tag in tags:
        subprocess.run(["git", "tag", "-a", tag, "-m", tag], cwd=tmp_path, check=True)
    return tmp_path


def _detect(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "detect_current_version.py"), *args],
        cwd=root, capture_output=True, text=True,
        check=False,
    )


def test_a_pre_release_tag_is_a_version_the_chain_can_read(tmp_path: Path) -> None:
    """The rc the chain cut last time is the current version, not a skipped line."""
    root = _repo(tmp_path, ["v0.2.0", "v0.3.0-rc.1", "v0.3.0-rc.2"])

    result = _detect(root)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0.3.0-rc.2"
    assert "not semver" not in result.stderr


def test_a_repository_with_only_pre_releases_can_still_cut(tmp_path: Path) -> None:
    """Refusing this repository stopped a project that had only ever cut rc tags."""
    root = _repo(tmp_path, ["v1.0.0-rc.1"])

    result = _detect(root)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "1.0.0-rc.1"


def test_the_series_advances_instead_of_recomputing_rc_1(tmp_path: Path) -> None:
    """End to end: detect feeds compute, and the next cut is rc.3 — a free tag."""
    root = _repo(tmp_path, ["v0.2.0", "v0.3.0-rc.1", "v0.3.0-rc.2"])
    current = _detect(root).stdout.strip()

    computed = subprocess.run(
        [sys.executable, str(SCRIPTS / "compute_next_version.py"),
         "--current", current, "--bump", "minor", "--mode", "pre"],
        cwd=root, capture_output=True, text=True,
        check=False,
    )

    assert computed.returncode == 0, computed.stderr
    assert computed.stdout.strip() == "0.3.0-rc.3"
    existing = subprocess.run(["git", "tag"], cwd=root, capture_output=True, text=True, check=False)
    assert f"v{computed.stdout.strip()}" not in existing.stdout.split()


def test_a_final_outranks_its_own_pre_releases(tmp_path: Path) -> None:
    """`0.3.0` supersedes `0.3.0-rc.9`; ordering them the other way cuts backwards."""
    root = _repo(tmp_path, ["v0.3.0-rc.9", "v0.3.0"])

    assert _detect(root).stdout.strip() == "0.3.0"


def test_a_pre_release_identifier_the_kit_cannot_order_is_named_honestly(
    tmp_path: Path,
) -> None:
    """`-beta.1` is valid semver the kit does not cut, and the note must not lie."""
    root = _repo(tmp_path, ["v0.2.0", "v0.3.0-beta.1"])

    result = _detect(root)

    assert result.stdout.strip() == "0.2.0"
    assert "not semver" not in result.stderr, (
        "0.3.0-beta.1 IS semver — the kit simply does not cut it, and the skipped-tag "
        "note has to say which of the two it means"
    )
