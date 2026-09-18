"""The kit boundary is a boundary, or it is only a boundary against `Edit`.

`boundary-check` refuses `Edit`/`Write` into an installed kit, for a reason that
says nothing about which tool does the writing: *"a fix written inside an
installed kit protects exactly one machine and is erased by the next install"*.
Measured cost on record in `check_install_drift.py` — twenty-two kit fixes spent
weeks inside one consumer's `.claude/`.

`sed -i` reached the same file through `Bash` and nothing looked at it. The other
read-only zone in this kit, `study-material/`, has had a shell-side guard since
the beginning (`ZONE_WRITE_RE`); the kit tree never got one, so the protection
existed for the tool an agent uses when it is being careful and not for the one
it reaches for when it is being quick.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _kit(tmp_path: Path) -> tuple[Path, Path]:
    """An installed kit outside the project — the `plugin` layout."""
    kit = tmp_path / "kit"
    for tree in ("skills", "rules", "hooks", "mechanisms"):
        (kit / tree).mkdir(parents=True, exist_ok=True)
    (kit / "rules" / "architecture.md").write_text("# rules\n", encoding="utf-8")
    (kit / "rules" / "domain-routing.txt").write_text("api=api-domain\n", encoding="utf-8")
    (kit / "agents").mkdir(exist_ok=True)
    (kit / "agents" / "api-domain.md").write_text("# specialist\n", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    return kit, project


def _run(command: str, kit: Path, project: Path) -> int:
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
               "tool_input": {"command": command}}
    import os
    return subprocess.run(  # noqa: PLW1510 — returncode is the assertion
        [sys.executable, str(REPO / "hooks" / "validate-command.py")],
        input=json.dumps(payload), capture_output=True, text=True, cwd=project,
        env={"PATH": os.environ["PATH"], "HOME": str(project),
             "CLAUDE_PROJECT_DIR": str(project),
             "CLAUDE_PLUGIN_ROOT": str(kit)}).returncode


#: The SPELLING of the target, not only the verb. Every case below built
#: `kit / "rules" / "architecture.md"`, which is always an ABSOLUTE tmp_path, and
#: `check_kit_boundary` collected candidates with a pattern matching `/…`, `./…` and
#: `../…` only. `sed -i s/a/b/ .claude/rules/architecture.md` — the most natural way to
#: type it from the project root — was therefore never examined by any test here.
_SPELLINGS = ("absolute", "dot-relative", "bare-relative")


def _nested_kit(tmp_path: Path) -> tuple[Path, Path]:
    """A kit INSIDE the project — the copy install, where a relative path can reach it.

    `_kit` above builds the two as siblings, so no relative spelling from the project
    could ever name a kit file. That is precisely why the hole survived: the layout the
    tests used could not express the case.
    """
    project = tmp_path / "project"
    kit = project / ".claude"
    for tree in ("skills", "rules", "hooks", "mechanisms"):
        (kit / tree).mkdir(parents=True, exist_ok=True)
    (kit / "rules" / "architecture.md").write_text("# rules\n", encoding="utf-8")
    return kit, project


@pytest.mark.parametrize("spelling", _SPELLINGS)
def test_the_boundary_holds_however_the_path_is_spelled(spelling: str, tmp_path: Path) -> None:
    kit, project = _nested_kit(tmp_path)
    absolute = kit / "rules" / "architecture.md"
    relative = absolute.relative_to(project)
    target = {
        "absolute": str(absolute),
        "dot-relative": f"./{relative}",
        "bare-relative": str(relative),
    }[spelling]

    assert _run(f"sed -i s/a/b/ {target}", kit, project) == 2, (
        f"the {spelling} spelling of a kit-owned file reached the tool: {target}")


@pytest.mark.parametrize("verb", [
    "sed -i s/a/b/ {target}",
    "echo x > {target}",
    "echo x >> {target}",
    "rm {target}",
    "cp /etc/hostname {target}",
    "mv {target} /tmp/x",
    "tee {target}",
])
def test_a_shell_command_cannot_write_where_edit_is_refused(verb: str, tmp_path: Path) -> None:
    kit, project = _kit(tmp_path)
    assert _run(verb.format(target=kit / "rules" / "architecture.md"), kit, project) == 2


def test_reading_the_kit_stays_allowed(tmp_path: Path) -> None:
    """The boundary is about writing. An agent that cannot READ its own contracts
    cannot follow them."""
    kit, project = _kit(tmp_path)
    assert _run(f"cat {kit / 'rules' / 'architecture.md'}", kit, project) == 0
    assert _run(f"grep -rn foo {kit / 'skills'}", kit, project) == 0


def test_the_project_owned_paths_inside_the_kit_stay_writable(tmp_path: Path) -> None:
    """`rules/*.txt`, `agents/` and `records/` are what a consumer calibrates.
    `boundary-check` already exempts them; the shell guard must agree or the two
    halves of one boundary disagree about where it is."""
    kit, project = _kit(tmp_path)
    assert _run(f"sed -i s/a/b/ {kit / 'rules' / 'domain-routing.txt'}", kit, project) == 0
    assert _run(f"sed -i s/a/b/ {kit / 'agents' / 'api-domain.md'}", kit, project) == 0


def test_the_kit_own_repository_is_where_these_files_are_edited(tmp_path: Path) -> None:
    """Standalone layout: no `CLAUDE_PLUGIN_ROOT`, and the tree IS the work."""
    kit, project = _kit(tmp_path)
    import os
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
               "tool_input": {"command": f"sed -i s/a/b/ {kit / 'rules' / 'architecture.md'}"}}
    done = subprocess.run(  # noqa: PLW1510 — returncode is the assertion
        [sys.executable, str(REPO / "hooks" / "validate-command.py")],
        input=json.dumps(payload), capture_output=True, text=True, cwd=kit,
        env={"PATH": os.environ["PATH"], "HOME": str(kit),
             "CLAUDE_PROJECT_DIR": str(kit)})
    assert done.returncode == 0
