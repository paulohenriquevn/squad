"""A reviewer who returned a document was frozen at the verdict it earned before the fix.

`cycle-plan.md` describes the loop plainly — a `return` sends the document back as
NEEDS_REVISION, it is revised and re-scored — and no mechanism completed it. `cast_vote`
refuses a second vote from one seat, by design, and the only other route was re-running
`convene_panel --write`, which `skills/panel/SKILL.md` lists as an anti-pattern in its
own words because it rewrites the assignment under votes already cast.

Re-voting nonetheless HAPPENED: four rounds of one PLAN panel survive as
`<slug>-plan.round1.json` .. `.round4.json`, and seats change verdict across them. It
was done by hand and written down nowhere — a convention that exists only as filenames a
previous session chose is one the next session re-derives, or files an overstated report
about.

What this pins is the supported path, and the shape `/review` already uses for the same
problem: a BLOCKER that is fixed and re-verified is marked CLOSED, keeping its severity,
rather than deleted. A superseded verdict stays readable, with the version of the text it
was about, because a panel that hides having returned a document once destroys the record
that the correction happened.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "mechanisms" / "cycle"))

REASON = ("I read the artifact against the contract it cites and checked every claim "
          "it makes about the measured evidence in the record")
FIXED = ("the four corrections I named are applied and I re-read each one against the "
         "evidence the plan cites for it")


def _project(tmp_path: Path, body: str = "round one\n") -> Path:
    project = tmp_path / "project"
    panels = project / ".squad" / "records" / "panels"
    panels.mkdir(parents=True)
    (panels / "B-014-plan.assignment.json").write_text(json.dumps({
        "slug": "B-014", "phase": "plan", "author": "someone-else",
        "artifact": "plan.md",
        "assigned": ["seat-one", "seat-two", "seat-three"],
    }), encoding="utf-8")
    (project / "plan.md").write_text(body, encoding="utf-8")
    return project


def _cast(project: Path, reviewer: str, verdict: str = "approve",
          *, supersede: bool = False, reason: str = REASON) -> dict:
    from cast_vote import cast

    return cast(project, slug="B-014", phase="plan", reviewer=reviewer,
                model="a-model", verdict=verdict, reason=reason, supersede=supersede)


def _record(project: Path) -> dict:
    path = project / ".squad" / "records" / "panels" / "B-014-plan.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _revise(project: Path, body: str = "round two, corrected\n") -> None:
    (project / "plan.md").write_text(body, encoding="utf-8")


def test_a_seat_that_returned_can_approve_the_corrected_text(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _cast(project, "seat-one", "return")
    _revise(project)

    _cast(project, "seat-one", "approve", supersede=True, reason=FIXED)

    live = {v["reviewer"]: v["verdict"] for v in _record(project)["votes"]}
    assert live["seat-one"] == "approve"


def test_the_seats_that_did_not_return_keep_their_votes(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _cast(project, "seat-two", "approve")
    _cast(project, "seat-one", "return")
    _revise(project)

    _cast(project, "seat-one", "approve", supersede=True, reason=FIXED)

    live = {v["reviewer"]: v["verdict"] for v in _record(project)["votes"]}
    assert live["seat-two"] == "approve", (
        "revising the document discarded the vote of a seat that never asked for a change"
    )


def test_a_carried_vote_says_which_round_it_was_cast_in(tmp_path: Path) -> None:
    """A vote about round one's text must not read as a vote about round two's.

    This is the whole reason the superseded round is archived rather than overwritten:
    `seat-two` approved text the corrections have since changed, and a tally that cannot
    tell the two apart reports three seats agreeing about one document when they agreed
    about two.
    """
    project = _project(tmp_path)
    _cast(project, "seat-two", "approve")
    _cast(project, "seat-one", "return")
    _revise(project)
    _cast(project, "seat-one", "approve", supersede=True, reason=FIXED)

    carried = next(v for v in _record(project)["votes"] if v["reviewer"] == "seat-two")
    assert carried.get("carried_from_round") == 1


def test_the_superseded_verdict_stays_readable_with_the_text_it_judged(tmp_path: Path) -> None:
    first = "round one\n"
    project = _project(tmp_path, first)
    _cast(project, "seat-one", "return")
    _revise(project)
    _cast(project, "seat-one", "approve", supersede=True, reason=FIXED)

    rounds = _record(project)["rounds"]
    assert len(rounds) == 1
    assert rounds[0]["artifact_sha256"] == hashlib.sha256(first.encode()).hexdigest()
    assert [v["verdict"] for v in rounds[0]["votes"]] == ["return"], (
        "the panel now reads as though it had never returned the document"
    )


def test_the_live_hash_follows_the_text_the_current_round_is_about(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _cast(project, "seat-one", "return")
    _revise(project, "corrected\n")
    _cast(project, "seat-one", "approve", supersede=True, reason=FIXED)

    assert _record(project)["artifact_sha256"] == hashlib.sha256(b"corrected\n").hexdigest()


def test_superseding_identical_text_is_refused_as_a_duplicate(tmp_path: Path) -> None:
    """Nothing was corrected, so there is nothing to judge again.

    Without this the flag becomes a way to overwrite a verdict one dislikes, which is the
    duplicate refusal with an extra argument rather than a revision loop.
    """
    project = _project(tmp_path)
    _cast(project, "seat-one", "return")

    with pytest.raises(SystemExit):
        _cast(project, "seat-one", "approve", supersede=True, reason=FIXED)


def test_superseding_a_seat_that_never_voted_is_refused(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _cast(project, "seat-one", "return")
    _revise(project)

    with pytest.raises(SystemExit):
        _cast(project, "seat-two", "approve", supersede=True, reason=FIXED)


def test_a_plain_second_vote_is_still_refused(tmp_path: Path) -> None:
    """The flag is the supported path; it does not make the unsupported one legal."""
    project = _project(tmp_path)
    _cast(project, "seat-one", "return")
    _revise(project)

    with pytest.raises(SystemExit):
        _cast(project, "seat-one", "approve", reason=FIXED)
