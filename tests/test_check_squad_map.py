"""The map that is injected at SessionStart must describe the system on disk.

The tests that matter are the two DIRECTIONS. A map missing a phase under-reports;
a map naming a hook that was deleted sends a reader looking for a file that is not
there, and the second failure is quieter — nothing errors, the reader just finds
nothing and concludes they misread.

Verified by mutating a copy of the repository and watching each clause fire, which
is the only way to know a checker checks: a green checker over an intact tree is
indistinguishable from one that checks nothing.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "mechanisms" / "gates" / "check_squad_map.py"
MAP_REL = "rules/squad-map.md"


def _run(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--json"],
        capture_output=True,
        text=True,
     check=False)


@pytest.fixture
def kit(tmp_path: Path) -> Path:
    """A copy of what git carries, so the check measures the repository and not
    whatever untracked files happen to sit on this machine."""
    dest = tmp_path / "kit"
    dest.mkdir()
    listing = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout
    for rel in filter(None, listing.split("\0")):
        src = REPO / rel
        if not src.is_file():
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    # `.git` is needed: the kit-agent list is derived from `git ls-files`, never restated.
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True)
    subprocess.run(["git", "add", "-A"], cwd=dest, check=True)
    return dest


def test_the_intact_repository_passes(kit: Path) -> None:
    result = _run(kit)
    assert result.returncode == 0, result.stdout


def test_a_phase_missing_from_the_map_is_reported(kit: Path) -> None:
    """cycle-phases.txt is the declaration; a map that omits a phase hides a stage."""
    path = kit / MAP_REL
    path.write_text(path.read_text(encoding="utf-8").replace("CODE-QUALITY", "…"), encoding="utf-8")
    result = _run(kit)
    assert result.returncode == 1
    assert "code-quality" in result.stdout
    assert "absent_from_map" in result.stdout


def test_a_cycle_missing_from_the_map_is_reported(kit: Path) -> None:
    (kit / "rules" / "cycle-invented.md").write_text("# Cycle: INVENTED\n", encoding="utf-8")
    result = _run(kit)
    assert result.returncode == 1
    assert "cycle-invented" in result.stdout


def test_an_agent_missing_from_the_map_is_reported(kit: Path) -> None:
    """An agent absent from the map has no declared position in the flow."""
    path = kit / MAP_REL
    path.write_text(path.read_text(encoding="utf-8").replace("hermes-scrum-master", "—"), encoding="utf-8")
    result = _run(kit)
    assert result.returncode == 1
    assert "hermes-scrum-master" in result.stdout


def test_a_hook_missing_from_the_map_is_reported(kit: Path) -> None:
    """A hook runs outside the agent's turn; one nobody documented is one nobody expects."""
    path = kit / MAP_REL
    path.write_text(
        path.read_text(encoding="utf-8").replace("`boundary-check.py`", "`(removed)`"),
        encoding="utf-8",
    )
    result = _run(kit)
    assert result.returncode == 1
    assert "boundary-check.py" in result.stdout


def test_a_hook_the_map_invents_is_reported(kit: Path) -> None:
    """The quieter direction: nothing errors, the reader just finds nothing."""
    path = kit / MAP_REL
    path.write_text(
        path.read_text(encoding="utf-8") + "\n\nAlso: `imaginary-hook.sh` runs on Stop.\n",
        encoding="utf-8",
    )
    result = _run(kit)
    assert result.returncode == 1
    assert "imaginary-hook.sh" in result.stdout
    assert "absent_from_disk" in result.stdout


def test_a_missing_map_is_a_hard_error_not_a_pass(kit: Path) -> None:
    """An absent gate is not a passed one."""
    (kit / MAP_REL).unlink()
    result = _run(kit)
    assert result.returncode == 2


def test_it_does_not_duplicate_the_skill_inventory(kit: Path) -> None:
    """`check_skill_map.py` owns that fact; two checkers over one fact can disagree.

    A skill absent from the SQUAD map must NOT fail this checker — the squad map
    places phases, cycles, agents and hooks, and the skill index is a different
    document with a different checker.
    """
    (kit / "skills" / "phantom-skill").mkdir(parents=True)
    (kit / "skills" / "phantom-skill" / "SKILL.md").write_text(
        "---\nname: phantom-skill\nversion: 0.1.0\nrequires: []\n"
        "description: not in any map\nuser-invocable: true\n---\n\n# phantom\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=kit, check=True)
    assert _run(kit).returncode == 0, "the squad map must not police the skill inventory"
