"""`git-safety.md` § 2 gained a rule, and the rule makes a claim about another file.

The rule says two agents must never share a working tree, and then says where the
instruction already lived: the consumer brief in `mechanisms/fleet/fleet_router.py`.
That sentence is the reason the section is short — it does not restate the brief, it
points at it — and a pointer is exactly the shape that rots without anyone noticing.

This kit spent 2026-09-04 finding dead citations: an ADR naming an item that did not
exist, a doc-comment citing a document nobody wrote, an installer header describing
behaviour replaced in August, a test reading the file a routing table had left. Every
one of them was written by someone being careful. So a new rule that cites a file gets
a test on the citation the same day, rather than joining them.

Sibling of `test_worktree_briefs_name_the_stash.py`, which pins what the briefs say.
This pins what the RULE says, and that the thing the rule points at is still true.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RULE = REPO / "rules" / "git-safety.md"

_FLEET = REPO / "mechanisms" / "fleet"
if str(_FLEET) not in sys.path:
    sys.path.insert(0, str(_FLEET))

import fleet_router  # noqa: E402

#: Any absolute path will do, as long as it is not one workstation's.
_REPO = "/srv/example/kit"


def _rule_text() -> str:
    return RULE.read_text(encoding="utf-8")


def test_the_rule_states_the_one_tree_per_lane_requirement() -> None:
    """Without this sentence the section is about stashes only, which is what it
    was before 2026-09-04 — and the collision that day was not a stash."""
    text = _rule_text()
    assert "never share a working tree" in text, (
        "git-safety.md no longer requires one working tree per lane"
    )
    assert "worktree add" in text, (
        "the rule states the requirement and not the command that satisfies it"
    )


def test_the_rule_keeps_the_measurement_that_produced_it() -> None:
    """A safety rule with the evidence trimmed off reads as preference, and
    preferences get argued with. The 35 paths are what makes it a finding."""
    text = _rule_text()
    assert "2026-09-04" in text
    assert "35" in text, (
        "the measured cost of the collision is gone; without it the rule is an opinion"
    )


def test_the_rule_does_not_cite_a_brief_that_stopped_saying_it() -> None:
    """The rule points at `fleet_router.py`'s consumer brief instead of restating
    it. If that brief stops handing out a worktree, the rule becomes a pointer to
    nothing — and it would still read as authoritative, which is worse than being
    absent.
    """
    text = _rule_text()
    assert "fleet_router.py" in text, "the rule stopped naming where the brief lives"

    brief = fleet_router.brief(
        fleet_router.Unit("B-079", "a title", "backlog"),
        repo=_REPO,
        project="/consumer",
    )
    assert "worktree add" in brief, (
        "git-safety.md § 2 says the consumer brief carries the worktree instruction, "
        "and it no longer does. Either the brief regressed or the rule now lies."
    )


def test_the_anti_pattern_names_the_branch_confusion() -> None:
    """The collision happened under the belief that a branch per lane is isolation.
    Refuting the specific wrong belief is what the § 4 list is for; a general
    "use worktrees" would not have caught the person who thought they had."""
    text = _rule_text()
    assert "a branch names a commit" in text, (
        "§ 4 no longer refutes 'each lane is on its own branch, so they cannot collide'"
    )
