"""The confidence heuristic that decides whether DISCOVER runs at all.

`assess_confidence.py` is 298 lines and had no test. It is not a peripheral script:
`/idea-to-release` derives the chain's DEPTH from its verdict, and a score of 95 or
more returns depth `none` — the item goes to PLAN without ever being measured.
`skills/map.md` says of it *"the script is deterministic and its output is the
truth"*, and nothing checked what that truth was.

WHAT WAS WRONG, AND WHY THE WEIGHT CHANGED
-------------------------------------------
`references/` scored +30, the heaviest signal in the table, for a match under
`records/references/` — which the script itself defines as *"projects SIMILAR to
ours, kept as architectural inspiration: how did they solve it?"*.

That is prior art, and prior art is the one justification this kit refuses:

    README.md      "Prior art can never be evidence. Gate G5 rejects 'project X
                    does it this way' as a justification."
    cycle-backlog  "'Project X does it this way.' That is not an item."

So enough peer material raised the score until the orchestrator SKIPPED a phase
`cycle-phases.txt` declares **required**, on the strength of the one signal the
intake gate refuses as grounds for the work existing at all.

The weight was inherited from Cycle, whose DISCOVER asks how others solved it.
Squad inverted that question on purpose — README calls the peer-study version *"the
right question when building something new and the wrong one when maintaining
something that runs: it produces imitation, not maintenance"* — and the weights had
never followed.

It now scores **zero** and is still **reported**: knowing peer material exists helps
whoever writes the plan, it just cannot buy past the measurement. A peer project
cannot tell you what is true of your system.

The tests below pin every band boundary on both sides, that prior art contributes
nothing however much of it there is, and that a `LOW` verdict carries an explicit
`refuses` flag — because `recommended_depth` is `"full"` for LOW too, and a caller
branching on the depth would proceed at exactly the confidence the band exists to
stop.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from assess_confidence import (
    refuses,
    score_references,
    verdict_from_score,
)


@pytest.mark.parametrize(
    ("score", "verdict", "depth"),
    [
        (100, "HIGH", "none"),
        (95, "HIGH", "none"),
        (94, "MED-HIGH", "light"),
        (70, "MED-HIGH", "light"),
        (69, "MED-LOW", "full"),
        (30, "MED-LOW", "full"),
        (29, "LOW", "full"),
        (0, "LOW", "full"),
    ],
)
def test_the_bands_are_exactly_where_the_docstring_says(score: int, verdict: str, depth: str) -> None:
    """Every boundary, both sides. A band that drifts one point silently changes
    which phases run for a whole class of items."""
    got_verdict, got_depth, _ = verdict_from_score(score)
    assert (got_verdict, got_depth) == (verdict, depth)


def test_prior_art_is_reported_and_scores_nothing(tmp_path: Path) -> None:
    """The fix: a peer project cannot buy its way past the measurement.

    `records/references/` holds projects SIMILAR to ours. `README.md` — "Prior art
    can never be evidence" — and `cycle-phases.txt` declares `discover` required, so
    a signal gate G5 refuses as grounds for an item existing must not be what skips
    measuring it.
    """
    refs = tmp_path / "records" / "references" / "some-cache-project"
    refs.mkdir(parents=True)

    score, matches = score_references(tmp_path, ["cache"])

    assert matches == ["references/some-cache-project/"], "the match is still reported"
    assert score == 0, "prior art must buy no depth"


def test_a_repo_full_of_peer_material_cannot_reach_the_skip_band(tmp_path: Path) -> None:
    """The consequence, stated as a test rather than as a comment.

    Before the fix, references alone contributed 30 of the 95 needed to return
    depth `none`. It now contributes nothing, so peer material cannot move the
    verdict at all.
    """
    for name in ("cache-a", "cache-b", "cache-c"):
        (tmp_path / "records" / "references" / name).mkdir(parents=True)

    score, matches = score_references(tmp_path, ["cache"])

    assert len(matches) == 3
    assert score == 0


def test_low_confidence_carries_an_explicit_refusal_flag() -> None:
    """`recommended_depth` is "full" for LOW too, so a caller branching on it would
    proceed at exactly the confidence the band exists to stop.

    The refusal lives in SKILL.md — consistent with how this kit places judgement
    gates — but reading the JSON required knowing that. `refuses` makes it a field.
    """
    verdict, depth, reasoning = verdict_from_score(0)
    assert verdict == "LOW"
    assert depth == "full", "the depth is not a refusal signal"
    assert "REFUSE" in reasoning
    assert refuses(verdict) is True


def test_no_other_band_refuses() -> None:
    """Widening the flag must not stop work the bands allow."""
    for score in (30, 69, 70, 94, 95, 100):
        assert refuses(verdict_from_score(score)[0]) is False


def test_the_verdict_is_a_pure_function_of_the_score() -> None:
    """Deterministic is the claim `skills/map.md` makes about this script."""
    for score in range(0, 101):
        assert verdict_from_score(score) == verdict_from_score(score)
