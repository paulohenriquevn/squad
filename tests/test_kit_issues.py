"""Where an idle fleet goes when the consumer's queue has nothing it may touch.

Measured on a real consumer on 2026-09-02: both remaining backlog items waited on
a governance decision, the queue read BACKLOG_BLOCKED, and a fleet of three lanes
and a lead had nothing it was allowed to work on. In the same hour the kit had two
open defects — and both had been filed that day by agents running inside that very
fleet. The capture half of self-evolution worked; nothing consumed what it caught.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mechanisms" / "fleet"))

import kit_issues
from kit_issues import Unavailable, fleet_work, open_issues


def _gh(monkeypatch, *, stdout: str = "[]", returncode: int = 0,
        stderr: str = "", raises: Exception | None = None) -> None:
    def fake(*_a, **_kw):
        if raises is not None:
            raise raises
        return subprocess.CompletedProcess([], returncode, stdout, stderr)
    monkeypatch.setattr(kit_issues.subprocess, "run", fake)


def test_open_issues_become_work_with_a_number_you_can_open(monkeypatch) -> None:
    _gh(monkeypatch, stdout=json.dumps([
        {"number": 12, "title": "scorer credits a denied class", "labels": [],
         "url": "https://github.com/o/r/issues/12"}]))

    [issue] = open_issues("o/r")

    assert issue.slug == "kit#12"
    assert issue.url.endswith("/12"), "an item nobody can open is not a work item"


def test_a_missing_gh_is_not_an_empty_registry(monkeypatch) -> None:
    """The one thing this must never do. "The kit has no known defects", said on
    the strength of an absent CLI, is this kit's most-found defect exactly."""
    _gh(monkeypatch, raises=FileNotFoundError("gh"))

    with pytest.raises(Unavailable) as excinfo:
        open_issues("o/r")

    assert "not the same as" in str(excinfo.value), "it says which two things differ"


@pytest.mark.parametrize("failure,expected", [
    ({"returncode": 1, "stderr": "HTTP 401: Bad credentials"}, "401"),
    ({"stdout": "not json at all"}, "not JSON"),
], ids=["unauthenticated", "garbage"])
def test_every_way_of_not_knowing_says_so_rather_than_returning_nothing(
        monkeypatch, failure: dict, expected: str) -> None:
    _gh(monkeypatch, **failure)

    with pytest.raises(Unavailable) as excinfo:
        open_issues("o/r")

    assert expected in str(excinfo.value)


def test_an_issue_waiting_on_a_person_is_not_handed_to_a_lane(monkeypatch) -> None:
    """The consumer queue blocked because its items wanted a human decision.
    Routing the same shape from the kit's registry rebuilds that one level up."""
    _gh(monkeypatch, stdout=json.dumps([
        {"number": 12, "title": "a defect", "labels": [], "url": "u"},
        {"number": 14, "title": "which way should this go?",
         "labels": [{"name": "needs-decision"}], "url": "u"}]))

    work, held = fleet_work("o/r")

    assert [i.number for i in work] == [12]
    assert [i.number for i in held] == [14]


def test_what_waits_on_a_person_is_returned_rather_than_dropped(monkeypatch) -> None:
    """An issue nobody can see is an issue nobody decides. Filtering it out
    silently would hide the thing that needs the decision it is waiting for."""
    _gh(monkeypatch, stdout=json.dumps([
        {"number": 14, "title": "q", "labels": [{"name": "question"}], "url": "u"}]))

    work, held = fleet_work("o/r")

    assert work == []
    assert len(held) == 1


def test_an_empty_registry_is_a_real_answer_and_reads_as_one(monkeypatch) -> None:
    """Distinct from Unavailable: `gh` answered, and the answer was none."""
    _gh(monkeypatch, stdout="[]")

    assert fleet_work("o/r") == ([], [])


def test_a_label_this_kit_has_never_seen_does_not_hold_the_issue(monkeypatch) -> None:
    """Held is an allowlist of reasons to hold, not a denylist of reasons to run.
    A gate naming what may NOT pass let five unsigned items through this morning."""
    _gh(monkeypatch, stdout=json.dumps([
        {"number": 12, "title": "a defect",
         "labels": [{"name": "some-new-label"}], "url": "u"}]))

    work, _ = fleet_work("o/r")

    assert [i.number for i in work] == [12]


def test_the_kits_real_registry_answers(monkeypatch) -> None:
    """Not mocked: the shape above must match what `gh` actually returns.

    Skipped where `gh` cannot reach it, because a network-dependent failure in
    the suite teaches nothing about this code.
    """
    try:
        work, held = fleet_work("paulohenriquevn/squad", timeout=30)
    except Unavailable as exc:
        pytest.skip(f"registry unreachable here: {exc}")

    for issue in work + held:
        assert issue.number > 0 and issue.title, "every row parsed into a real item"
