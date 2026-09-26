r"""The chain must confirm that what it published exists.

`cycle-release.md` ends at `gh release create` and emits `RELEASED`. Nothing looked
afterwards. A release left as a draft, a `gh` call that failed after the tag was already
pushed, a tag that never propagated — each produces `RELEASED` over an artifact no
consumer can fetch, and the verdict is what `cycle-maintenance`'s ADVANCE reads to write
`shipped`.

This is the half of the gap an external review named. Its other half — that a `B-NNN`
with no milestone never reaches `/acceptance` — `cycle-acceptance.md` calls *"correct and
not a gap"*, and for PRODUCT acceptance it is: an item nobody promised a user has no
user-visible promise to exercise. What that argument does not cover is whether the thing
shipped at all, and that question has an answer for every item, milestone or not.

WHAT THIS DOES NOT CLAIM. Reaching a GitHub release is not reaching a package on npm or
PyPI, and it is not exercising the delivery. `cycle-acceptance` does the second, against
declared criteria. This gate answers the narrower question that was going unasked:
**does the release this run says it published exist, is it public, and does it point at
the tag that was cut?**
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "mechanisms" / "gates"))

from check_release_reachable import check_release_reachable  # noqa: E402


def _gh(payload: dict | None, *, returncode: int = 0, stderr: str = ""):
    def runner(argv: list[str]) -> tuple[int, str, str]:
        return returncode, json.dumps(payload) if payload is not None else "", stderr
    return runner


def test_a_published_release_holds() -> None:
    result = check_release_reachable("v1.2.0", gh=_gh({
        "tagName": "v1.2.0", "isDraft": False, "url": "https://github.com/o/r/releases/v1.2.0",
    }))

    assert result.exit_code == 0, result.detail


def test_a_draft_release_is_not_a_release() -> None:
    """A draft is visible to the publisher and to nobody else."""
    result = check_release_reachable("v1.2.0", gh=_gh({
        "tagName": "v1.2.0", "isDraft": True, "url": "https://github.com/o/r/releases/v1.2.0",
    }))

    assert result.exit_code == 1
    assert "draft" in result.detail.lower()


def test_a_release_for_another_tag_is_refused() -> None:
    """`gh release view` resolves loosely enough that the answer must be checked."""
    result = check_release_reachable("v1.2.0", gh=_gh({
        "tagName": "v1.1.0", "isDraft": False, "url": "https://github.com/o/r/releases/v1.1.0",
    }))

    assert result.exit_code == 1
    assert "v1.1.0" in result.detail


def test_a_missing_release_is_refused_not_skipped() -> None:
    """The tag was pushed and the release was not created: the exact partial failure."""
    result = check_release_reachable(
        "v1.2.0", gh=_gh(None, returncode=1, stderr="release not found"))

    assert result.exit_code == 1
    assert "not found" in result.detail.lower()


def test_an_absent_gh_could_not_measure_and_says_so() -> None:
    """`2`, never `0`. An inability to look is not a look that found nothing."""
    def missing(argv: list[str]) -> tuple[int, str, str]:
        raise FileNotFoundError("gh")

    result = check_release_reachable("v1.2.0", gh=missing)

    assert result.exit_code == 2
    assert "gh" in result.detail


def test_an_unparseable_answer_could_not_measure() -> None:
    def garbage(argv: list[str]) -> tuple[int, str, str]:
        return 0, "not json", ""

    assert check_release_reachable("v1.2.0", gh=garbage).exit_code == 2


# A test asserting that `skills/release/SKILL.md` invokes this gate stood here and was
# removed the same hour. `check_prose_tests` refused it, correctly: a grep over a
# contract is a SYMPTOM — the guarantee exists only as prose and somebody felt the need
# to guard it. Here it was worse than a symptom, it was a duplicate:
# `tests/test_every_gate_is_reachable.py::test_something_runs_this_gate` already holds
# EVERY gate to being invoked, reads `skills/**/SKILL.md` among its sources, and
# distinguishes a real invocation from a mention. One mechanised guarantee, not a
# hand-written echo of it per gate.
