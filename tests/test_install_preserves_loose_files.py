"""A file sitting directly in `skills/` was deleted; a directory beside it survived.

`--force` deletes `skills/` and copies a fresh one, and the preservation pass
walks `$ECO/skills/*/` — a glob that matches DIRECTORIES. A project that keeps a
`SKILLS.md` index next to its skill folders therefore lost it, silently, on every
reinstall.

Measured on 2026-08-29 in `speculative`: `SKILLS.md`, 207 versioned lines,
removed by a reinstall. It was recovered with `git restore` only because that
repository versions `.claude/`; the projects that follow the policy of not
versioning it would have lost the file outright.

This is the sixth face of one defect. The preservation rule has been stated once
and implemented for one shape at a time: the routing table, then `rules/*.txt`,
then `settings.json` by key, then project skill directories, then
`an adopter.md`, and now loose files. Each fix was correct and none of
them generalised, which is why this test asserts the RULE — anything the source
kit does not ship is the project's — rather than one more shape.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "mechanisms" / "distribution" / "install.sh"


#: A project skill has to look like one. The Cycle's `verify_ecosystem.py`
#: validates frontmatter across EVERY skill it finds, the project's included, and
#: the install refuses when one is malformed — so a fixture skill without
#: frontmatter fails the install for a reason that has nothing to do with what
#: this file tests.
_PROJECT_SKILL = """---
name: their-skill
version: 0.1.0
description: A skill the project wrote, used here to prove it survives a reinstall.
---

# their-skill
"""


def _consumer(tmp_path: Path) -> Path:
    root = tmp_path / "consumer"
    skill = root / ".claude" / "skills" / "their-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(_PROJECT_SKILL, encoding="utf-8")
    (root / ".claude" / "rules").mkdir(parents=True)
    (root / ".claude" / "agents").mkdir(parents=True)
    return root


#: What a validation failure over a PROJECT skill looks like. The Cycle validates
#: with `check_xrefs --strict`, where "skill X is referenced by no cycle rule" is
#: a WARN that fails the run — and a project's own skill is referenced by no cycle
#: rule by definition. So a consumer with a skill of its own cannot complete an
#: install there. That is a real defect in that kit and it is not this file's
#: subject; recorded rather than worked around silently.
_PROJECT_SKILL_WARNS = ("no_orphan_skills", "skill_has_cycle_contract", "check_xrefs")


def _install(root: Path) -> None:
    """Run the installer and assert the DISK, not the exit code.

    This file is about what survives `--force`, which is a question about files.
    Coupling it to the installer's overall verdict would make it fail for reasons
    that have nothing to do with preservation — and it did, on the sibling kit,
    for the strict-validation reason above.
    """
    result = subprocess.run(["bash", str(INSTALL), str(root), "--force"],  # noqa: PLW1510 — returncode is read below
                            capture_output=True, text=True)
    if result.returncode != 0:
        combined = result.stdout + result.stderr
        assert any(w in combined for w in _PROJECT_SKILL_WARNS), \
            combined[-2000:]
    # Either way the copy must have happened, or nothing below means anything.
    assert (root / ".claude" / "skills").is_dir(), combined[-2000:] if result.returncode else ""


@pytest.mark.parametrize("rel", [
    "skills/SKILLS.md",          # the measured casualty
    "skills/NOTES.md",
    "skills/.skillsrc",
    "agents/TEAM.md",
])
def test_a_loose_file_the_kit_does_not_ship_survives(tmp_path: Path, rel: str) -> None:
    """The rule: anything the SOURCE kit does not ship belongs to the project."""
    root = _consumer(tmp_path)
    target = root / ".claude" / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("written by the project\n", encoding="utf-8")

    _install(root)

    assert target.is_file(), f"{rel} was deleted by --force"
    assert target.read_text(encoding="utf-8") == "written by the project\n", \
        f"{rel} survived but its contents were replaced"


def test_a_project_skill_directory_still_survives(tmp_path: Path) -> None:
    """The fix already in place must not regress while a new shape is added."""
    root = _consumer(tmp_path)
    skill = root / ".claude" / "skills" / "their-skill" / "SKILL.md"

    _install(root)

    assert skill.is_file(), "the project's skill directory was deleted"
    assert skill.read_text(encoding="utf-8") == _PROJECT_SKILL, \
        "the directory survived but its contents were replaced"


def test_a_file_the_kit_DOES_ship_is_refreshed(tmp_path: Path) -> None:
    """Preservation must not become staleness.

    The mirror defect: a kit file kept because the consumer edited it is a gate
    running last month's rules. Ownership is decided by the SOURCE kit, so a name
    the kit ships is the kit's and gets overwritten.
    """
    root = _consumer(tmp_path)
    shipped = next(p for p in (ROOT / "rules").glob("*.md"))
    stale = root / ".claude" / "rules" / shipped.name
    stale.write_text("stale copy\n", encoding="utf-8")

    _install(root)

    assert stale.read_text(encoding="utf-8") != "stale copy\n", \
        f"{shipped.name} is the kit's and was not refreshed"

# ── the seventh face: whole directories with no preservation at all ──────────

#: Every directory `--force` deletes and re-copies. The preservation rule applies
#: to all of them; until 2026-08-29 it was implemented for two.
_COPIED_ITEMS = ("skills", "rules", "hooks", "commands", "scripts", "agents")


@pytest.mark.parametrize("rel", [
    "hooks/delivery-gate.sh",
    "hooks/lib/detect-layout.sh",
    "mechanisms/check-allowlist-sunsets.py",
    "mechanisms/gates/test_e2e_smoke.py",
    "commands/their-command.md",
])
def test_project_files_survive_in_every_copied_directory(tmp_path: Path, rel: str) -> None:
    """`hooks/` and the mechanisms directory had NO preservation pass, not a narrow one.

    Measured by a consumer session on 2026-08-29 in `platform`: the installer
    removed four files that do not exist in the source kit at all —
    `hooks/delivery-gate.sh`, `hooks/lib/detect-layout.sh`,
    `scripts/check-allowlist-sunsets.py`, `scripts/test_e2e_smoke.py`. Not kit
    parts being retired; the kit never had them. Two of the four were gates that
    repository's pre-push depends on.

    Seventh face of one defect, and the first where the answer was not "widen a
    glob" but "this directory was never covered". The parametrisation runs over
    the copied set so the next directory added to `_COPIED_ITEMS` inherits the
    rule instead of waiting to be discovered by a consumer.
    """
    root = _consumer(tmp_path)
    target = root / ".claude" / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("written by the project\n", encoding="utf-8")

    _install(root)

    assert target.is_file(), f"{rel} was deleted by --force"
    assert target.read_text(encoding="utf-8") == "written by the project\n"


def test_the_manifest_does_not_claim_more_than_it_covers(tmp_path: Path) -> None:
    """The header says "Anything not here is the project's" — for three prefixes.

    Measured: 92 entries, all under `agents/`, `rules/` and `skills/`; zero for
    `hooks/` or `scripts/`. A consumer trusting that sentence draws the wrong
    conclusion in both directions, and the peer session that reported this defect
    said it had done exactly that — marking four files as the project's by
    ABSENCE of coverage rather than by decision.

    A manifest that answers by omission is worse than one that does not answer.
    Either it covers every copied directory, or it stops claiming to.
    """
    root = _consumer(tmp_path)
    _install(root)

    manifest = root / ".claude" / ".kit-manifest.txt"
    if not manifest.is_file():
        pytest.skip("this kit writes no manifest, so it makes no claim to check — "
                    "ownership there is decided by presence in the source kit alone")
    text = manifest.read_text(encoding="utf-8")
    header = "\n".join(line for line in text.splitlines() if line.startswith("#"))
    covered = {line.split("/")[0] for line in text.splitlines()
               if line and not line.startswith("#") and "/" in line}

    if "Anything not here is the project's" in header:
        missing = [i for i in _COPIED_ITEMS
                   if (Path(__file__).resolve().parents[1] / i).is_dir() and i not in covered]
        assert not missing, (
            f"the header makes a claim the manifest does not support: no entries for "
            f"{missing}. Cover them, or narrow the sentence.")


def test_the_legacy_scripts_directory_is_migrated_and_project_files_kept(tmp_path: Path) -> None:
    """A consumer installed before the rename carries `.claude/scripts/`.

    Leaving it beside `mechanisms/` is not harmless: `hooks/` resolves through a
    fallback chain that still lists `.claude/scripts/`, so a hook would keep
    firing the OLD gate and reporting its verdict as current — the drift
    `check_install_drift.py` exists to name, arriving through the installer.

    So the stale directory goes. What must NOT go is a file the project put
    there: the kit never shipped it and has no standing to delete it. It is
    moved aside, under a name that says what it is, and the installer prints
    where.
    """
    root = _consumer(tmp_path)
    legacy = root / ".claude" / "scripts"
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "check_xrefs.py").write_text("the kit's old copy\n", encoding="utf-8")
    (legacy / "their-own-audit.py").write_text("written by the project\n", encoding="utf-8")

    _install(root)

    assert not legacy.exists(), "the stale directory must not survive beside mechanisms/"
    kept = root / ".claude" / "scripts.project-files" / "their-own-audit.py"
    assert kept.is_file(), "a file the kit never shipped may not be deleted"
    assert kept.read_text(encoding="utf-8") == "written by the project\n"
    assert (root / ".claude" / "mechanisms" / "gates" / "check_xrefs.py").is_file()
