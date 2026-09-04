"""Every place this kit hands an agent a worktree has to say what it does NOT isolate.

`git worktree` gives each tree its own index, its own HEAD and its own checkout.
`refs/stash` is not among them: it lives in the common git dir, so every tree
pushes and pops ONE stack and `git stash pop` returns the top entry no matter
which tree pushed it.

Measured 2026-09-04 (kit#31): two lanes in separate worktrees ran `git stash`
concurrently and each popped the other's entry. Their uncommitted work changed
places, and it was recovered only because one of them noticed — a swap that goes
unnoticed lands one agent's work under another agent's commit message, on another
agent's branch, reviewed as if it belonged there.

The trap is the isolation itself. Everything else a lane can see IS separate, so
"my worktree is mine" is true of every observation the lane makes and false of the
one thing that silently costs it its work. An instruction that hands out a
worktree and stops there is what taught the two lanes that.

So this is a property of the FLEET, not of any one brief: five separate places
tell an agent to cut a worktree, and the defect returns through whichever one is
silent. `hooks/validate-command.py` refuses the command mechanically — this file
is why the agent knows before it is refused.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_FLEET = REPO / "mechanisms" / "fleet"
if str(_FLEET) not in sys.path:
    sys.path.insert(0, str(_FLEET))

import fleet_router  # noqa: E402

#: Any absolute path will do, as long as it is not one workstation's.
_REPO = "/srv/example/kit"


def _briefs() -> dict[str, str]:
    """Every instruction that hands an agent a worktree, by the name of its source."""
    files = {
        "kit_repair_workflow.js": _FLEET / "kit_repair_workflow.js",
        "fleet_dispatch_workflow.js": _FLEET / "fleet_dispatch_workflow.js",
        "stage-implement.md": (REPO / "skills" / "pipeline" / "templates"
                               / "stage-implement.md"),
    }
    briefs = {name: path.read_text(encoding="utf-8") for name, path in files.items()}
    briefs["fleet_router:kit"] = fleet_router.brief(
        fleet_router.Unit("kit#19", "a defect", "kit"), repo=_REPO)
    briefs["fleet_router:backlog"] = fleet_router.brief(
        fleet_router.Unit("B-079", "a title", "backlog"), repo=_REPO, project="/consumer")
    return briefs


NAMES = sorted(_briefs())


def test_the_sources_are_all_still_there() -> None:
    """A brief that moved or was renamed would silently drop out of the loop below,
    and a parametrisation over four sources passes exactly as green as one over
    five. The count is asserted so a disappearance is a failure rather than a
    smaller test run."""
    assert len(NAMES) == 5, NAMES


@pytest.mark.parametrize("name", NAMES)
def test_the_brief_hands_out_a_worktree(name: str) -> None:
    """The premise. If this fails the brief stopped isolating its agent, which is
    a larger problem than the one below."""
    assert "worktree add" in _briefs()[name]


@pytest.mark.parametrize("name", NAMES)
def test_the_brief_says_the_stash_escapes_the_worktree(name: str) -> None:
    brief = _briefs()[name]

    assert "stash" in brief, f"{name} cuts a worktree and never names the stash"
    # Naming the hazard and not the substitute leaves the agent with a clean-tree
    # problem and no move, which is how a documented rule gets stepped around.
    assert "git restore" in brief, f"{name} names no alternative to the stash"
