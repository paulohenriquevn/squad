"""`install.sh <project>` creates `<project>/.claude`. Given a `.claude`, it nested one.

Measured 2026-09-23: passing a consumer's `.claude` directory as the target produced
`<project>/.claude/.claude` with **917 files** — a complete second copy of the kit one level
down — plus a `.squad/` records scaffold beside it. Nothing warned. The run then reported a
post-install validation FAILURE whose log path contained `.claude/.claude/`, which was the
only sign that the argument had been read as a project root.

Worse than the litter: every other flag then operates on the wrong tree.
`--remove-withdrawn` ran against the freshly-created nested install, found none of the
withdrawn skills there, and reported nothing — while the real install one level up kept all
eight. A destructive flag that silently does nothing is the failure mode that makes an
operator believe the work is done.

`tests/test_install_refuses_an_unconfined_root.py` already refuses `$HOME`, the config dir
and `/` — targets whose blast radius is the machine. This is the complement: a target whose
blast radius is a duplicate, and which no existing check names.

The refusal reads `squad.layout.has_kit`, the same predicate `resolve()` uses to decide that
a directory IS an install, so the two cannot come to disagree about what one looks like.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
INSTALLER = _ROOT / "mechanisms" / "distribution" / "install.sh"


def _kit_shaped(root: Path) -> Path:
    """The three trees `squad.layout._KIT_TREES` requires to call something an install."""
    for tree in ("skills", "rules", "hooks"):
        (root / tree).mkdir(parents=True, exist_ok=True)
    return root


def _run(target: Path, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(INSTALLER), str(target), *flags],
                          capture_output=True, text=True, check=False)


def test_a_dot_claude_directory_is_refused(tmp_path: Path) -> None:
    project = tmp_path / "project"
    eco = _kit_shaped(project / ".claude")

    out = _run(eco, "--merge")

    combined = out.stdout + out.stderr
    assert out.returncode != 0, combined[-2000:]
    assert not (eco / ".claude").exists(), "a nested install was created anyway"
    assert ".claude" in combined


def test_the_refusal_names_the_directory_to_use_instead(tmp_path: Path) -> None:
    """An operator who mistyped needs the right command, not only a complaint."""
    project = tmp_path / "project"
    eco = _kit_shaped(project / ".claude")

    out = _run(eco, "--merge")

    assert str(project) in out.stdout + out.stderr


def test_any_install_shaped_target_is_refused_not_just_the_name(tmp_path: Path) -> None:
    """The predicate is the kit's shape, not the string `.claude`.

    A consumer may install into a differently-named directory; `has_kit` is what decides,
    and a check keyed on the basename would miss exactly those and pass on an empty
    directory that happens to be called `.claude`.
    """
    odd = _kit_shaped(tmp_path / "kit-lives-here")

    out = _run(odd, "--merge")

    assert out.returncode != 0, (out.stdout + out.stderr)[-2000:]
    assert not (odd / ".claude").exists()


def test_a_plain_project_directory_is_still_accepted(tmp_path: Path) -> None:
    """The guard must not refuse the one shape the installer exists for."""
    project = tmp_path / "fresh"
    project.mkdir()

    out = _run(project)

    assert (project / ".claude").is_dir(), (out.stdout + out.stderr)[-2000:]


def test_remove_withdrawn_does_not_reinstall(tmp_path: Path) -> None:
    """The flag was only reachable through a full install, which does far more than asked.

    Authorising the deletion of eight retired skills is not authorising every kit file to be
    replaced. Measured the same day: the only way to run it was `--merge --remove-withdrawn`,
    so the narrow, destructive, explicitly-authorised action could not be taken without the
    broad one nobody asked for. Here it stands alone and installs nothing.
    """
    project = tmp_path / "consumer"
    eco = project / ".claude"
    for tree in ("skills", "rules", "hooks"):
        (eco / tree).mkdir(parents=True, exist_ok=True)
    (eco / "skills" / "grill-me").mkdir()
    (eco / "skills" / "grill-me" / "SKILL.md").write_text("# retired\n", encoding="utf-8")
    (eco / "skills" / "ours").mkdir()
    (eco / "skills" / "ours" / "SKILL.md").write_text("# ours\n", encoding="utf-8")
    before = {p.name for p in (eco / "rules").iterdir()}

    out = _run(project, "--remove-withdrawn")

    assert out.returncode == 0, (out.stdout + out.stderr)[-2000:]
    assert not (eco / "skills" / "grill-me").exists(), "the declared name survived"
    assert (eco / "skills" / "ours").exists(), "a skill the kit never shipped was deleted"
    assert {p.name for p in (eco / "rules").iterdir()} == before, (
        "rules/ changed — this installed instead of only removing")
