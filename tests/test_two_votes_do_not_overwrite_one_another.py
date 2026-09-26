"""The panel seats three reviewers, and two votes at once lost one of them.

`cast()` read the panel record, refused a reviewer already in `panel["votes"]`, appended
and rewrote the whole file — with nothing serialising the three steps. A session can
issue the three seats' invocations at once, so two votes read the same `votes` list and
the second rewrite dropped the first. A panel short one vote is INCOMPLETE rather than
approved, which is the outcome the duplicate refusal three lines down exists to prevent.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import sys
from pathlib import Path

import pytest

_CYCLE = Path(__file__).resolve().parent.parent / "mechanisms" / "cycle"
sys.path.insert(0, str(_CYCLE))

REASON = ("I read the artifact against the contract it cites and checked every claim "
          "it makes about the measured evidence in the record")


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    panels = project / ".squad" / "records" / "panels"
    panels.mkdir(parents=True)
    (panels / "B-014-review.assignment.json").write_text(json.dumps({
        "slug": "B-014", "phase": "review", "author": "someone-else",
        "artifact": "plan.md",
        "assigned": ["seat-one", "seat-two", "seat-three"],
    }), encoding="utf-8")
    return project


def _vote(project: str, reviewer: str, barrier) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mechanisms" / "cycle"))
    from cast_vote import cast

    barrier.wait(timeout=60)
    cast(Path(project), slug="B-014", phase="review", reviewer=reviewer,
         model="a-model", verdict="approve", reason=REASON)


@pytest.mark.skipif(sys.platform == "win32", reason="flock is the POSIX guarantee here")
def test_three_seats_voting_at_once_all_reach_the_record(tmp_path: Path) -> None:
    project = _project(tmp_path)
    seats = ["seat-one", "seat-two", "seat-three"]

    ctx = mp.get_context("spawn")
    barrier = ctx.Barrier(len(seats))
    procs = [ctx.Process(target=_vote, args=(str(project), seat, barrier)) for seat in seats]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=120)

    record = project / ".squad" / "records" / "panels" / "B-014-review.json"
    assert record.is_file(), "no panel record was written at all"
    panel = json.loads(record.read_text(encoding="utf-8"))

    assert sorted(v["reviewer"] for v in panel["votes"]) == sorted(seats), (
        f"{len(panel['votes'])} of 3 votes survived: "
        f"{[v['reviewer'] for v in panel['votes']]}")
