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
        # REVIEW cuts a worktree to reproduce the pre-change test failure, so it
        # carries the same hazard even though it holds no Edit or Write: a `bash`
        # call can stash, and the rule is about the tree rather than the tool list.
        "stage-review.md": (REPO / "skills" / "pipeline" / "templates"
                            / "stage-review.md"),
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
    # Six since 2026-09-15: REVIEW joined the pipeline and cuts a worktree to
    # reproduce the pre-change test failure.
    assert len(NAMES) == 6, NAMES


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

def test_no_unenumerated_site_hands_out_a_worktree() -> None:
    """The count above catches a brief that DISAPPEARS. This catches one that arrives.

    An auditor found the gap: `_briefs()` is a hardcoded dict, so pinning its length
    fails when a source is renamed away and passes when a sixth is added — which is
    the direction that matters, because a new brief handing out a worktree without
    the stash warning reopens kit#31 through a door nobody is watching.

    So the tree is swept instead of trusted. Anything that tells an agent to cut a
    worktree must either carry the warning or be enumerated here as a known
    exception, with the reason.
    """
    import subprocess

    #: Files that mention `worktree add` for reasons other than briefing an agent.
    #: Each needs a reason, because an exemption nobody probes is a door.
    EXEMPT = {
        # Cuts its own scratch trees to run suites in. No agent reads it, and it
        # never stashes — it throws the tree away instead.
        "mechanisms/fleet/fleet_lander.py",
        # This file.
        "tests/test_worktree_briefs_name_the_stash.py",

        # --- read-only reviewers -------------------------------------------------
        # These five cut `--detach` trees to READ a diff. They are briefed to
        # review, never to edit, so there is no uncommitted work for a stash to
        # move. If a reviewer ever gains a writing tool, it stops being exempt and
        # this list is where that shows up.
        "skills/review/templates/agent-architecture-reviewer.md",
        "skills/review/templates/agent-cross-validation-reviewer.md",
        "skills/review/templates/agent-domain-reviewer.md",
        "skills/review/templates/agent-test-reviewer.md",
        "skills/review/templates/agent-wiring-reviewer.md",

        # --- mentions, not instructions ------------------------------------------
        # The guard itself: it names the command in its own refusal message.
        "hooks/validate-command.py",
        # The rule the briefs implement. It states the requirement and shows the
        # command that satisfies it, so it matches the sweep — but it is the
        # contract, not a brief handed to an agent, and it carries the stash
        # hazard at length in the same section (§ 2's table plus the paragraph
        # under it). Exempt from the brief check, not from the rule.
        "rules/git-safety.md",
        # A release procedure a PERSON follows, one tree at a time. The hazard is
        # concurrent agents; a human cutting one tree has nobody to swap with.
        "rules/acceptance-target.txt",
        "rules/templates/acceptance-target.txt",
        # Prose about what a worktree copies, in a wiring check.
        "skills/implement/scripts/check_wiring.py",
        # Asserts that `git-safety.md` § 2 still carries the requirement and the
        # command that satisfies it. It quotes `worktree add` to check for it, and
        # briefs nobody. Enumerated the moment it was committed, because until then
        # it was untracked and `git grep` could not see it — which is its own small
        # lesson about sweeps that read the index.
        "tests/test_git_safety_one_tree_per_lane.py",
        # Test fixtures and assertions that build worktrees to test other things.
        "skills/implement/tests/conftest.py",
        "skills/pipeline/tests/test_spawn_stages.py",
        "tests/test_fleet_router.py",
        "tests/test_session_ready.py",
    }

    found = subprocess.run(
        ["git", "grep", "-l", "worktree add", "--", ":!CHANGELOG.md", ":!*.lock"],
        cwd=REPO, capture_output=True, text=True,
        check=False,
    )
    if found.returncode not in (0, 1):
        raise AssertionError(f"git grep failed: {found.stderr}")

    sweep = {p for p in found.stdout.split() if p}
    covered = {
        "mechanisms/fleet/kit_repair_workflow.js",
        "mechanisms/fleet/fleet_dispatch_workflow.js",
        "mechanisms/fleet/fleet_router.py",
        "skills/pipeline/templates/stage-implement.md",
        "skills/pipeline/templates/stage-review.md",
    }

    unenumerated = sorted(sweep - covered - EXEMPT)
    assert not unenumerated, (
        "these hand out a worktree and are not covered by the stash-warning tests: "
        f"{unenumerated}. Either add the warning and enumerate it in _briefs(), or "
        "add it to EXEMPT with the reason it does not brief an agent."
    )
