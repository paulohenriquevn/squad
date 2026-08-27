"""The installed kit is not the consumer's writable territory.

THE DEFECT THIS FIXES
---------------------
Installed by copy, the kit lives in `<project>/.claude/`, and
`settings.plugin.json` allows `Edit`, `Write` and `Bash(*)`. No hook covered that
path: `boundary-check.sh` protected only `records/references/` and
`study-material/`, and `validate-command.sh` mentioned neither
`.claude/skills`, nor `.claude/rules`, nor `.claude/hooks`. The
`.kit-manifest.txt`, written by the installer precisely to say what came from the
kit, was read by no hook at all.

The result is on record in the repository itself, in
`scripts/check_install_drift.py`:

    "Twenty-two fixes to this kit lived for weeks inside one consumer's
     gitignored `.claude/` install and nowhere else. Nobody hid them.
     Nothing looked."

A fix written inside the installed kit protects exactly one machine, and vanishes
with the next `install.sh --force`.

WHAT STAYS WRITABLE, AND WHY
----------------------------
The boundary is not all of `.claude/` — that would break normal use. What belongs
to the PROJECT stays writable and is enumerated below in
`test_project_owned_paths_stay_writable`: the configuration (`rules/*.txt`), the
domain specialists (`agents/`), everything under `records/`, and
`settings.json`. What is the kit's CONTRACT — skills, normative rules, hooks,
scripts — is read-only.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "hooks" / "boundary-check.sh"

BLOCK = 2
ALLOW = 0


def _run(file_path: str, project: Path, plugin_root: Path | None = None) -> int:
    payload = json.dumps({"tool_input": {"file_path": file_path}})
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project)}
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    if plugin_root is not None:
        env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    proc = subprocess.run(  # noqa: PLW1510
        ["bash", str(HOOK)], input=payload, capture_output=True, text=True, env=env
    )
    return proc.returncode


@pytest.fixture()
def copy_install(tmp_path: Path) -> Path:
    """A project with the kit installed by copy, as `install.sh` writes it."""
    project = tmp_path / "consumer"
    eco = project / ".claude"
    for d in ("skills/review", "rules", "hooks/environment", "scripts", "commands",
              "agents", "records/plans"):
        (eco / d).mkdir(parents=True, exist_ok=True)
    (eco / "skills/review/SKILL.md").write_text("kit\n", encoding="utf-8")
    (eco / "rules/cycle-review.md").write_text("kit\n", encoding="utf-8")
    (eco / "rules/code-quality-languages.txt").write_text("# projeto\n", encoding="utf-8")
    (eco / ".kit-manifest.txt").write_text(
        "# escrito por install.sh\nskills/review\nrules/cycle-review.md\n"
        "rules/code-quality-languages.txt\n",
        encoding="utf-8",
    )
    return project


# --------------------------------------------------------------------------
# what the kit owns — read-only
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "rel",
    [
        ".claude/skills/review/SKILL.md",
        ".claude/rules/cycle-review.md",
        ".claude/hooks/stop-validation.sh",
        ".claude/hooks/environment/detect-layout.sh",
        ".claude/scripts/check_xrefs.py",
        ".claude/commands/plan-goal.md",
    ],
)
def test_kit_owned_paths_are_blocked(copy_install: Path, rel: str):
    """Editing the installed kit must be refused, not silently accepted."""
    assert _run(str(copy_install / rel), copy_install) == BLOCK, (
        f"{rel} accepted a write — a fix made here protects one machine and "
        "vanishes with the next install --force"
    )


def test_relative_paths_are_blocked_too(copy_install: Path):
    """The agent cites relative paths as often as absolute ones."""
    assert _run(".claude/skills/review/SKILL.md", copy_install) == BLOCK


# --------------------------------------------------------------------------
# what the project owns — writable
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "rel",
    [
        ".claude/rules/code-quality-languages.txt",  # the project's configuration
        ".claude/agents/my-domain.md",               # the project's specialist
        ".claude/records/plans/x-plan.md",    # the cycle's output
        ".claude/settings.json",                     # the project's wiring
        "src/app.py",                                # the consumer's code
        "README.md",
    ],
)
def test_project_owned_paths_stay_writable(copy_install: Path, rel: str):
    """The boundary is the kit's CONTRACT, not the whole `.claude/` directory."""
    assert _run(str(copy_install / rel), copy_install) == ALLOW, (
        f"{rel} foi bloqueado, mas pertence ao projeto"
    )


def test_a_project_skill_is_not_the_kits(copy_install: Path):
    """A skill the PROJECT wrote stays the project's.

    That is what `.kit-manifest.txt` is for: without it, the only way to
    separar seria adivinhar por nome.
    """
    own = copy_install / ".claude/skills/placement-algorithms/SKILL.md"
    own.parent.mkdir(parents=True, exist_ok=True)
    own.write_text("do projeto\n", encoding="utf-8")
    assert _run(str(own), copy_install) == ALLOW, (
        "a project skill was treated as the kit's — the manifest was not read"
    )


# --------------------------------------------------------------------------
# modo nativo
# --------------------------------------------------------------------------
def test_native_plugin_root_is_read_only(tmp_path: Path):
    """In native mode the kit sits outside the project — and stays read-only."""
    kit = tmp_path / "plugin-root"
    for d in ("skills", "rules", "hooks"):
        (kit / d).mkdir(parents=True)
    project = tmp_path / "consumer"
    project.mkdir()
    assert _run(str(kit / "skills" / "review" / "SKILL.md"), project, plugin_root=kit) == BLOCK


# --------------------------------------------------------------------------
# regression: the boundary that already existed
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "rel",
    ["records/references/outro-projeto.md", "study-material/argo-cd.md"],
)
def test_study_zone_stays_read_only(copy_install: Path, rel: str):
    assert _run(str(copy_install / ".claude" / rel), copy_install) == BLOCK


def test_a_project_without_the_kit_allows_everything(tmp_path: Path):
    """With no kit installed, this hook has no boundary to defend."""
    plain = tmp_path / "plain"
    plain.mkdir()
    assert _run(str(plain / "src" / "app.py"), plain) == ALLOW
