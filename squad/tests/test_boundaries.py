"""Where the installed kit ends — the question, asked of the module that answers it.

Two hooks enforce this boundary and they used to know it separately, which is how
it came to hold against `Edit` and not against `sed -i`. Now they both ask here,
so this is where the line is pinned. The hooks' own tests exercise what each does
with the answer; these exercise the answer.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from squad.boundaries import is_project_owned, kit_relative, violation
from squad.layout import Layout


def _layout(tmp_path: Path, kind: str = "plugin") -> Layout:
    kit, project = tmp_path / "kit", tmp_path / "project"
    for tree in ("skills", "rules", "hooks"):
        (kit / tree).mkdir(parents=True, exist_ok=True)
    project.mkdir(exist_ok=True)
    return Layout(kit_dir=kit, eco=project, project_dir=project, kind=kind)


@pytest.mark.parametrize("rel", [
    "rules/domain-routing.txt",
    "rules/live-target.txt",
    "agents/api-domain.md",
    "records/audits/2026-09-08.md",
    "settings.json",
    ".kit-manifest.txt",
    ".install-backups/settings.json",
])
def test_what_the_consumer_calibrates_stays_theirs(rel: str, tmp_path: Path) -> None:
    """These are what an install PRESERVES. Calling them read-only would refuse a
    consumer the only files the kit expects them to change."""
    assert is_project_owned(rel, _layout(tmp_path).kit_dir)


@pytest.mark.parametrize("rel", [
    "rules/architecture.md",      # a contract, not configuration
    "skills/implement/SKILL.md",
    "mechanisms/gates/check_xrefs.py",
    "hooks/stop-validation.py",
    "CHANGELOG.md",
])
def test_what_the_kit_ships_is_not(rel: str, tmp_path: Path) -> None:
    assert not is_project_owned(rel, _layout(tmp_path).kit_dir)


def test_a_rule_file_is_config_by_its_EXTENSION_not_by_its_directory(
        tmp_path: Path) -> None:
    """`rules/` holds both: `.txt` is what a project tunes, `.md` is the contract
    the kit ships. The distinction is the whole reason the installer can update
    one without destroying the other."""
    kit = _layout(tmp_path).kit_dir
    assert is_project_owned("rules/thresholds.txt", kit)
    assert not is_project_owned("rules/cycle-plan.md", kit)


def test_a_skill_the_manifest_does_not_claim_belongs_to_the_project(
        tmp_path: Path) -> None:
    """The kit has no standing to call a skill read-only when it did not ship it."""
    layout = _layout(tmp_path)
    (layout.kit_dir / ".kit-manifest.txt").write_text(
        "# what this install shipped\nskills/implement\nskills/review\n",
        encoding="utf-8")

    assert not is_project_owned("skills/implement/SKILL.md", layout.kit_dir)
    assert is_project_owned("skills/our-own-thing/SKILL.md", layout.kit_dir)


def test_with_no_manifest_every_skill_is_treated_as_the_kits(tmp_path: Path) -> None:
    """Absent evidence, the safe answer is the one that can be argued with — a
    refusal names the file, while a silent allow edits a kit nobody meant to."""
    assert not is_project_owned("skills/anything/SKILL.md", _layout(tmp_path).kit_dir)


def test_the_kits_own_repository_is_where_these_files_are_edited(tmp_path: Path) -> None:
    layout = _layout(tmp_path, kind="standalone")
    assert kit_relative(layout.kit_dir / "rules" / "architecture.md", layout) is None
    assert violation(layout.kit_dir / "rules" / "architecture.md", layout) is None


def test_a_path_outside_the_kit_is_not_this_boundarys_business(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    assert kit_relative(layout.project_dir / "src" / "main.py", layout) is None
    assert violation(layout.project_dir / "src" / "main.py", layout) is None


def test_a_relative_path_is_resolved_against_the_project(tmp_path: Path) -> None:
    """A tool hands over what the user typed, which is often relative."""
    layout = _layout(tmp_path)
    assert kit_relative(Path("src/main.py"), layout) is None


def test_the_refusal_names_the_file_and_where_the_fix_belongs(tmp_path: Path) -> None:
    """A boundary that only says no teaches nothing. This one has somewhere to
    send the work, and that is the difference between a wall and a route."""
    layout = _layout(tmp_path)
    reason = violation(layout.kit_dir / "rules" / "architecture.md", layout)

    assert reason
    assert "rules/architecture.md" in reason
    assert "repository" in reason, "it does not say where the fix should go"
