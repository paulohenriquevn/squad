"""A lane told to write long text gets told where it may not write it.

The hazard is quiet, which is what earns it a test. `ssh host "… <<'QUOTED' …"`
looks protected — the heredoc IS quoted, so the REMOTE shell leaves it alone —
and the outer double quotes hand the whole thing to the LOCAL shell first.
Backticked words run here and arrive as empty strings. The command exits 0, the
file is written, and a sentence is missing two of its words in the middle.

Measured five times across 2026-09-04 and 05 by a coordinator driving a remote
host, the fifth while writing a comment about avoiding it. That is the argument
for a written rule over care: care was being applied at the moment it failed.

`rules/loop-engine-convention.md` already carried the principle for one caller —
ralph-loop's positional prompt is shell-evaluated, so the prompt goes to a file.
This asserts the generalisation stayed general, and that the brief which hands a
lane its instructions repeats it. A rule that only one caller knows about is a
rule the next caller re-derives from nothing, which is exactly how the worktree
requirement was lost.

Sibling of `test_worktree_briefs_name_the_stash.py` and
`test_git_safety_one_tree_per_lane.py`.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RULE = REPO / "rules" / "loop-engine-convention.md"

_FLEET = REPO / "mechanisms" / "fleet"
if str(_FLEET) not in sys.path:
    sys.path.insert(0, str(_FLEET))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
import fleet_router  # noqa: E402 — post-bootstrap import

_REPO = "/srv/example/kit"


def _consumer_brief() -> str:
    return fleet_router.brief(
        fleet_router.Unit("B-079", "a title", "backlog"),
        repo=_REPO,
        project="/consumer",
    )


def test_the_rule_states_the_general_form_not_only_the_loop_case() -> None:
    """It was written for ralph-loop's positional prompt and stayed there while
    the same hazard bit through ssh. The general statement is what makes it
    reachable from the second door."""
    text = RULE.read_text(encoding="utf-8")
    assert "second door" in text, (
        "the rule no longer names the ssh/heredoc form, so it reads as a "
        "ralph-loop quirk rather than a property of command lines"
    )
    assert "goes to a file" in text or "goes in a file" in text, (
        "the rule states the hazard and not the substitute"
    )


def test_the_rule_keeps_the_count_that_makes_it_a_finding() -> None:
    """Five occurrences is what separates this from a style preference. Strip the
    measurement and someone reasonably argues that careful escaping is enough —
    which is the position the fifth occurrence refuted."""
    assert "five times" in RULE.read_text(encoding="utf-8")


def test_the_consumer_brief_repeats_it() -> None:
    """A lane reads the brief, not the rules directory."""
    brief = _consumer_brief()
    assert "scp" in brief, "the brief hands out no substitute for the heredoc"
    assert "heredoc" in brief, "the brief never names the hazard"


def test_the_brief_points_at_the_rule_rather_than_replacing_it() -> None:
    """Two copies of a rule diverge; the brief carries the short form and the
    citation, so the next reader can find the measurement behind it."""
    assert "loop-engine-convention.md" in _consumer_brief(), (
        "the brief states the rule without saying where it is written down"
    )
