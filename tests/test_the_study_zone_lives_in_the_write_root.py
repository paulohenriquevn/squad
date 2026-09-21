r"""The read-only study zone is `.squad/study-material/`, and one module owns it.

`rules/reference-provenance.md` guards third-party material for a legal reason, not a
stylistic one: a literal copy carries its licence into this repository. The zone was a
TOP-LEVEL `study-material/`, which put third-party code in the same tree the project
versions — and `.gitignore` had to carry `study-material/**` to keep it out.

Inside the write root the licence question does not arise: `.squad/` is the project's
own run area, ignored whole, and nothing there is ever committed. The guard stays what
it was — nothing is written into the zone, nothing leaves it by command, no commit
message cites it — and it now guards a path that cannot be committed by accident.

The zone was also spelled THREE times, in three different shapes:

    hooks/boundary-check.py         (^|/)(\.claude/)?study-material/
    hooks/validate-command.py       (\./)?(\.claude/)?study-material/
    check_reference_leakage.py      ZONE_DIRS = ("study-material",)

`squad/boundaries.py` already says why that is the defect and not the style: *"a rule
living in one file and missing from another is how the gap reopens"*. Its own docstring
records the previous instance — `boundary-check` refused `Edit`/`Write` into an
installed kit while `validate-command` refused shell writes into the zone and knew
nothing about the kit, so `sed -i` reached the file `Edit` had just been refused.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from squad.boundaries import STUDY_ZONE, study_zone_re  # noqa: E402


def test_the_zone_is_inside_the_write_root() -> None:
    assert STUDY_ZONE == ".squad/study-material"


@pytest.mark.parametrize(
    "path",
    [
        ".squad/study-material/peer/main.go",
        "./.squad/study-material/peer/main.go",
        ".claude/.squad/study-material/x.md",
        "/abs/project/.squad/study-material/deep/nested/file.ts",
    ],
)
def test_a_path_in_the_zone_is_recognised(path: str) -> None:
    assert study_zone_re().search(path), path


@pytest.mark.parametrize(
    "path",
    [
        "squad/study-material/x.md",          # the package, not the write root
        ".squad/records/plans/a-plan.md",
        "docs/wiki/decisions/a.md",
        "study-material/legacy.md",           # the retired top-level zone
    ],
)
def test_a_path_outside_the_zone_is_not(path: str) -> None:
    assert not study_zone_re().search(path), path


def test_every_guard_reads_the_one_definition() -> None:
    """A fourth spelling is how the gap reopens."""
    guards = [
        REPO / "hooks" / "boundary-check.py",
        REPO / "hooks" / "validate-command.py",
        REPO / "mechanisms" / "gates" / "check_reference_leakage.py",
    ]
    private = [
        p.name for p in guards
        if "study-material" in p.read_text(encoding="utf-8")
        and "from squad.boundaries import" not in p.read_text(encoding="utf-8")
    ]

    assert private == [], f"{private} spell the zone themselves"


def test_the_top_level_zone_is_gone() -> None:
    """Two zones is worse than one in the wrong place: a guard reads one, the person
    putting a clone somewhere reads the other."""
    assert not (REPO / "study-material").exists()
    assert "study-material/**" not in (REPO / ".gitignore").read_text(encoding="utf-8")


def test_the_zone_cannot_be_committed_by_accident() -> None:
    """The reason the move is an improvement and not a rearrangement."""
    import subprocess

    candidate = REPO / ".squad" / "study-material" / "peer-project" / "LICENSE"
    done = subprocess.run(["git", "check-ignore", "-q", str(candidate)],
                          cwd=REPO, capture_output=True, check=False)

    assert done.returncode == 0, f"{candidate} is not ignored"
