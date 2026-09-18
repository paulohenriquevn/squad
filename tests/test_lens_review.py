"""The kit knows its own failure modes and applies them only in hindsight.

`kit_audit_workflow.js` carries six lenses, each a defect pattern this kit has
shipped more than once, each quoting the measurement that makes it concrete. It
runs over the whole repository, on a sweep, after the fact.

Measured 2026-09-03, in one session, all of them by the same author: a guard
whose predicate held in both directions so its success branch never ran; a
cleanup whose result was discarded so a leak could not be explained; a fetch
taken once and reused as if it were current; and a workstation path in a
versioned file, twice. Every one is on the list. The list was never pointed at
the diff that introduced them.

This points it there. Its findings do not block a landing — a model's opinion
about a diff is not grounds to stall an unattended fleet with nobody to override
it — they become issues, which is the same loop the sweep already feeds.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_FLEET = Path(__file__).resolve().parents[1] / "mechanisms" / "fleet"
if str(_FLEET) not in sys.path:
    sys.path.insert(0, str(_FLEET))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
import lens_review  # noqa: E402 — post-bootstrap import

_WORKFLOW = _FLEET / "kit_audit_workflow.js"


# ── one source for the lenses, and a loud failure if it moves ─────────────────


def test_the_lenses_are_read_from_the_workflow_not_copied(tmp_path: Path) -> None:
    """A second copy of a rule is this kit's second-most-found defect.

    Asserted behaviourally rather than by grepping for the key names: the module
    names two of them in prose, explaining which defect each caught, and a
    substring ban cannot tell that from a hard-coded list. Handing it a workflow
    with a lens the kit does not have can.
    """
    invented = tmp_path / "k.js"
    invented.write_text(
        "const LENSES = [\n  {\n    key: 'a-lens-this-kit-never-had',\n"
        "    prompt: `" + ("x" * 300) + "`,\n  },\n]\n", encoding="utf-8")
    assert [lens.key for lens in lens_review.lenses(invented)] == \
        ["a-lens-this-kit-never-had"]


def test_every_lens_in_the_workflow_is_found() -> None:
    lenses = lens_review.lenses(_WORKFLOW)
    keys = {lens.key for lens in lenses}
    assert keys == {"absence-as-answer", "rule-in-one-file", "guard-that-guards-nothing",
                    "mentioned-not-used", "prose-vs-mechanism", "unreachable-or-unrun"}
    assert all(len(lens.prompt) > 200 for lens in lenses), \
        "a lens without its measurements finds prose; the measurements ARE the lens"


def test_a_workflow_it_cannot_parse_raises_rather_than_returning_none(
        tmp_path: Path) -> None:
    """Returning an empty list would review a diff against zero lenses and report
    a clean result — the exact defect the first lens is about."""
    broken = tmp_path / "k.js"
    broken.write_text("const LENSES = 'moved to a data file'\n", encoding="utf-8")
    with pytest.raises(lens_review.LensesUnreadable):
        lens_review.lenses(broken)


def test_a_missing_workflow_raises_too(tmp_path: Path) -> None:
    with pytest.raises(lens_review.LensesUnreadable):
        lens_review.lenses(tmp_path / "absent.js")


# ── what it does with a diff ──────────────────────────────────────────────────


def test_an_empty_diff_is_not_reviewed() -> None:
    found, note = lens_review.review("", lenses=[], ask=None)
    assert found == []
    assert "no diff" in note


def test_a_lens_that_finds_nothing_contributes_nothing() -> None:
    lens = lens_review.Lens("absence-as-answer", "look for X")
    found, _ = lens_review.review("diff --git a/x b/x", lenses=[lens],
                                  ask=lambda _p: '{"findings": []}')
    assert found == []


def test_a_finding_carries_the_lens_that_caught_it() -> None:
    lens = lens_review.Lens("absence-as-answer", "look for X")
    payload = ('{"findings": [{"title": "the cleanup result is discarded", '
               '"file": "mechanisms/fleet/fleet_lander.py", "line": 180, '
               '"evidence": "run(...) in a finally, return ignored", '
               '"why_it_matters": "a leak cannot be explained"}]}')
    found, _ = lens_review.review("diff --git a/x b/x", lenses=[lens],
                                  ask=lambda _p: payload)
    assert len(found) == 1
    assert found[0]["lens"] == "absence-as-answer"
    assert found[0]["verdict"] == {"refuted": False}, \
        "file_findings decides what to file; this only says the lens was not refuted here"


def test_an_agent_that_answers_with_prose_is_reported_not_silently_dropped() -> None:
    """An unparseable answer means the lens did not run. Counting it as 'found
    nothing' is an absence published as a measurement."""
    lens = lens_review.Lens("absence-as-answer", "look for X")
    found, note = lens_review.review("diff --git a/x b/x", lenses=[lens],
                                     ask=lambda _p: "I looked and it seems fine")
    assert found == []
    assert "absence-as-answer" in note
    assert "did not return" in note


def test_an_agent_that_raises_does_not_take_the_other_lenses_with_it() -> None:
    # The marker must not occur in the prompt template itself. An earlier version
    # used "one", which appears in "teaches them to skim the next one" — so both
    # lenses raised and the test passed for the wrong reason before it failed.
    def flaky(prompt: str) -> str:
        if "LENS_ALPHA" in prompt:
            raise RuntimeError("the CLI fell over")
        return '{"findings": [{"title": "t", "file": "f.py", "line": 1, '\
               '"evidence": "e", "why_it_matters": "w"}]}'
    lenses = [lens_review.Lens("one", "LENS_ALPHA"), lens_review.Lens("two", "LENS_BETA")]
    found, note = lens_review.review("diff --git a/x b/x", lenses=lenses, ask=flaky)
    assert len(found) == 1
    assert "one" in note and "fell over" in note


def test_a_diff_that_could_not_be_produced_is_not_nothing_to_review(tmp_path) -> None:
    """`branch_diff` returned `""` whenever git exited non-zero.

    An unknown branch, a missing `origin/workspace`, a repository that is not there —
    each produced the empty string, `review()` reads that as "no diff to review", and
    `main` prints it as the result. The module's own docstring names this pattern as the
    first on its list: "a lens that did not run and a lens that ran clean are the same
    output otherwise". It applied to the diff itself.
    """
    import lens_review as lr

    not_a_repo = tmp_path / "nowhere"
    not_a_repo.mkdir()

    with pytest.raises(lr.DiffUnavailable):
        lr.branch_diff(not_a_repo, "some-branch")


def test_a_real_empty_diff_is_still_nothing_to_review() -> None:
    """The refusal above must not swallow the honest empty case."""
    import lens_review as lr

    found, note = lr.review("", lenses=[], ask=None)

    assert found == []
    assert note == "no diff to review"
