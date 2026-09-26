"""A kit withdrawal must reach the consumer holding the old copy.

`install.sh` preserves any skill directory the source kit does not ship — right for a
project's own skill, and exactly wrong for one the kit RETIRED. On disk the two are
indistinguishable, so a retirement removed the file upstream and removed nothing anywhere,
and the next install copied the old copy aside and put it back (#171).

Measured on one consumer: 30 skills present and absent from the kit, 103 of the 111 files
`check_install_drift` labels "consumer-local" belonging to them, and 0 of the 30 named in
`.kit-manifest.txt` — whose header states "Anything not here is the project's". False for
all 30, and false BECAUSE the manifest is regenerated on every install: the install that
withdrew a skill erased the only record that the kit ever shipped it.

The fix is a list that travels with the kit and is read BY NAME. Absence stays the
project's, always; only a name on `mechanisms/distribution/withdrawn.txt` is ever called a
withdrawal, and removing one is opt-in. Deleting by absence would delete somebody's work,
which is the outcome no convenience is worth.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
INSTALLER = _ROOT / "mechanisms" / "distribution" / "install.sh"
WITHDRAWN = "grill-me"          # declared in withdrawn.txt
PROJECTS_OWN = "our-own-skill"  # never shipped by the kit


def _consumer(tmp_path: Path) -> Path:
    """An install holding one withdrawn skill and one the project wrote."""
    target = tmp_path / "consumer"
    eco = target / ".claude"
    for tree in ("skills", "rules", "hooks"):
        (eco / tree).mkdir(parents=True, exist_ok=True)
    for name in (WITHDRAWN, PROJECTS_OWN):
        (eco / "skills" / name).mkdir(parents=True, exist_ok=True)
        # Valid frontmatter, or the installer prints `ERROR: <name>/SKILL.md has no
        # frontmatter` and the assertions below pass on THAT line instead of on a
        # withdrawal report. Measured while writing this: the first draft went green
        # against an error message naming the same skill.
        (eco / "skills" / name / "SKILL.md").write_text(
            f"---\nname: {name}\nversion: 0.1.0\nrequires: []\n"
            f"description: A skill for testing.\nuser-invocable: false\n---\n\n# {name}\n", encoding="utf-8")
    return target


def _run(target: Path, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(INSTALLER), str(target), "--merge", *flags],
                          capture_output=True, text=True, check=False)


def test_a_withdrawn_skill_is_named_in_the_output(tmp_path: Path) -> None:
    target = _consumer(tmp_path)

    out = _run(target)

    combined = out.stdout + out.stderr
    assert WITHDRAWN in combined, combined[-3000:]
    assert "withdraw" in combined.lower(), combined[-3000:]


def test_reporting_does_not_delete_it(tmp_path: Path) -> None:
    """Default is REPORT. A consumer may have kept a retired skill on purpose."""
    target = _consumer(tmp_path)

    _run(target)

    assert (target / ".claude" / "skills" / WITHDRAWN).exists()


def test_the_projects_own_skill_is_never_called_a_withdrawal(tmp_path: Path) -> None:
    """The invariant that makes removal safe: absence is not evidence of anything."""
    target = _consumer(tmp_path)

    out = _run(target)

    assert PROJECTS_OWN not in out.stdout + out.stderr


def test_remove_withdrawn_deletes_only_the_declared_name(tmp_path: Path) -> None:
    target = _consumer(tmp_path)

    out = _run(target, "--remove-withdrawn")

    assert out.returncode == 0, (out.stdout + out.stderr)[-3000:]
    assert not (target / ".claude" / "skills" / WITHDRAWN).exists(), "declared name survived"
    assert (target / ".claude" / "skills" / PROJECTS_OWN).exists(), (
        "a skill the kit never shipped was deleted — absence was treated as a withdrawal")
