"""A failed packaging run used to leave an unopenable `.skill` at the published path.

The zip was written straight to `skill_filename`, so anything failing mid-loop left a
partial archive at the real name — and the failure path returned None without removing
it. The next reader found a `.skill` file that exists and cannot be opened.

`except Exception` also reported an OSError on a member file, a corrupt-archive error and
a programming mistake inside the loop with one identical line, so the operator could not
tell "this file is unreadable" from "this script has a bug".
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

# BOTH roots: the module imports `scripts.quick_validate`, so the skill directory has to
# be importable as well as its `scripts/`.
_SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SKILL))
sys.path.insert(0, str(_SKILL / "scripts"))

import package_skill  # noqa: E402 — post-bootstrap import


def _skill(tmp_path: Path) -> Path:
    skill = tmp_path / "a-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: a-skill\ndescription: does a thing for a reason\n---\n\nBody.\n",
        encoding="utf-8")
    return skill


def test_a_successful_run_publishes_an_openable_archive(tmp_path: Path) -> None:
    out = tmp_path / "dist"
    result = package_skill.package_skill(_skill(tmp_path), str(out))

    assert result is not None, "packaging failed on a well-formed skill"
    assert zipfile.is_zipfile(result), "the published file is not a readable archive"
    assert not list(out.glob("*.partial")), "the temporary name survived the rename"


def test_a_failed_run_leaves_no_file_at_the_published_path(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "dist"

    real_write = zipfile.ZipFile.write

    def explode(self, filename, arcname=None, **kwargs):
        raise OSError("member file vanished mid-write")

    monkeypatch.setattr(zipfile.ZipFile, "write", explode)
    result = package_skill.package_skill(_skill(tmp_path), str(out))
    monkeypatch.setattr(zipfile.ZipFile, "write", real_write)

    assert result is None
    assert not (out / "a-skill.skill").exists(), (
        "a half-written archive was left at the published path")
    assert not list(out.glob("*.partial")), "the partial file was not cleaned up"
