"""The kit refuses writes to files it never installed.

`boundaries.violation` calls anything under an installed kit "the installed Squad
kit, which is read-only here". Measured on a consumer 2026-09-18, three of the
files it claimed were not the kit's at all — they were another plugin's runtime
state living in the same directory:

    .claude/code-review-loop.local.md        loop-code-review, in progress
    .claude/code-review-loop.completed.md    loop-code-review, finished
    .claude/test-audit-loop.local.md         loop-test-audit

Deleting the first is that plugin's own documented way to cancel a run. The
boundary refused it, and the refusal told the reader something false about who
owns the file. A guard that lies about WHY it refuses teaches people to route
around it, and routed-around is worse than narrow.

`.kit-manifest.txt` already answers this question — its own header says
"Anything not here is the project's" — but `is_project_owned` consulted it for
`skills/` alone. Generalising that read is the whole fix, and it has a
precondition these tests measure first: the manifest must actually list
everything the installer copies. It did not. The installer copies `README.md`,
`HOW-TO-USE.md`, `plugin.json` and `.active_plan.example` into the kit root and
enumerates none of them, so widening the rule without closing that gap would
have handed the kit's own README to the project.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from squad.boundaries import is_project_owned, violation  # noqa: E402
from squad.layout import Layout  # noqa: E402


@pytest.fixture(scope="module")
def installed(tmp_path_factory) -> Path:
    target = tmp_path_factory.mktemp("consumer")
    (target / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    subprocess.run(
        ["bash", str(_REPO / "mechanisms" / "distribution" / "install.sh"), str(target)],
        capture_output=True, text=True, check=True,
    )
    return target


def _listed(kit: Path) -> set[str]:
    return {
        line.split("#", 1)[0].strip()
        for line in (kit / ".kit-manifest.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def test_the_manifest_lists_the_loose_files_the_installer_copies(installed: Path) -> None:
    """The precondition. The header promises no omissions; the root omitted four.

    Enumerated per file rather than by directory: unlike `skills/`, a loose file
    has no unit above itself for a reader to fall back on.
    """
    kit = installed / ".claude"
    listed = _listed(kit)
    for name in ("README.md", "HOW-TO-USE.md", "plugin.json", ".active_plan.example"):
        if not (kit / name).is_file():
            continue  # not shipped by this install; nothing to claim
        assert name in listed, (
            f"the installer copied {name} into the kit and the manifest does not "
            f"name it, so the manifest answers by omission at exactly the level "
            f"where the boundary needs it to answer"
        )


def test_another_plugins_state_file_is_not_the_kits(installed: Path) -> None:
    """The defect. A sibling plugin's file is not the kit's to protect."""
    kit = installed / ".claude"
    layout = Layout(kit_dir=kit, eco=kit, project_dir=installed, kind="plugin")

    for name in ("code-review-loop.local.md",
                 "code-review-loop.completed.md",
                 "test-audit-loop.local.md"):
        state = kit / name
        state.write_text("# loop state\n", encoding="utf-8")
        assert violation(state, layout) is None, (
            f"{name} belongs to another plugin and the kit never installed it; "
            f"claiming it is a false statement about ownership"
        )


def test_the_kits_own_top_level_files_stay_protected(installed: Path) -> None:
    """The regression this fix could easily cause, pinned before it can happen.

    `README.md` and `HOW-TO-USE.md` ARE the kit's. A rule of "absent from the
    manifest means the project's" opens them the moment the manifest under-lists
    — which is why the precondition above is a test and not a comment.
    """
    kit = installed / ".claude"
    layout = Layout(kit_dir=kit, eco=kit, project_dir=installed, kind="plugin")

    for name in ("README.md", "HOW-TO-USE.md", "plugin.json"):
        if not (kit / name).is_file():
            continue
        refusal = violation(kit / name, layout)
        assert refusal is not None, f"{name} is the kit's own and must stay read-only"


def test_a_file_the_manifest_never_named_is_the_projects(installed: Path) -> None:
    """Stated directly against the predicate, without a layout in the way."""
    kit = installed / ".claude"
    assert is_project_owned("code-review-loop.local.md", kit) is True
    assert is_project_owned("some-other-plugin/state.json", kit) is True
    assert is_project_owned("README.md", kit) is False
    assert is_project_owned("mechanisms/gates/check_xrefs.py", kit) is False


def test_without_a_manifest_nothing_is_conceded(installed: Path, tmp_path: Path) -> None:
    """No manifest means the boundary cannot measure ownership — so it holds.

    The opposite default would turn a missing file into a blanket unlock, which
    is the failure this kit names most often: a check that could not measure its
    subject reporting a pass.
    """
    # A COPY of the kit root: deleting from the shared install would decide
    # a later test's outcome by execution order.
    kit = tmp_path / "kit"
    shutil.copytree(installed / ".claude", kit)
    (kit / ".kit-manifest.txt").unlink()
    assert is_project_owned("code-review-loop.local.md", kit) is False
    assert is_project_owned("README.md", kit) is False


def test_an_old_manifest_does_not_unlock_the_trees_it_predates(tmp_path: Path) -> None:
    """The regression this fix nearly shipped, caught by `test_kit_is_read_only`.

    The manifest has not always listed everything. `install.sh` recorded that it
    once "covers only `agents/`, `rules/` and `skills/` — for `hooks/` and
    `scripts/` it is blind, so consulting it would answer by omission". Every
    consumer installed before it widened still holds one of those on disk.

    Reading absence from such a manifest as a concession would hand `hooks/` and
    `mechanisms/` to the project on all of them — a far larger hole than the one
    being closed, opened by the fix for it. So the manifest's authority stops at
    the trees the kit ships whole, where structure answers and no file has to.
    """
    kit = tmp_path / ".claude"
    (kit / "mechanisms" / "gates").mkdir(parents=True)
    (kit / "hooks").mkdir()
    (kit / "skills" / "a-project-skill").mkdir(parents=True)
    (kit / ".kit-manifest.txt").write_text(
        "# an install from before the manifest listed hooks/ or mechanisms/\n"
        "skills/review\nrules/cycle-review.md\n", encoding="utf-8")

    assert is_project_owned("mechanisms/gates/check_xrefs.py", kit) is False
    assert is_project_owned("hooks/stop-validation.py", kit) is False
    assert is_project_owned("commands/plan-goal.md", kit) is False
    assert is_project_owned("rules/cycle-implement.md", kit) is False
    # Still true where the manifest is the ONLY thing that can tell them apart.
    assert is_project_owned("skills/a-project-skill/SKILL.md", kit) is True
    assert is_project_owned("code-review-loop.local.md", kit) is True
