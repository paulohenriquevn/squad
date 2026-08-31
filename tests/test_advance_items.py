"""ADVANCE: close what a release actually shipped, from the stream.

The last unimplemented phase of `cycle-maintenance.md`, and it waited because what it
consumes did not exist. Nothing emitted `RELEASED`, so an ADVANCE built earlier could
only have inferred the release from files — and it writes `shipped`, where the
contract's own anti-pattern is *if nothing was released, nothing shipped*.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from advance_items import advance, released_items


def _project(tmp_path: Path, rows: list[tuple[str, str]], events: list[dict] | None = None) -> Path:
    body = "# BACKLOG\n\n"
    for item_id, status in rows:
        extra = "kill_reason: measured otherwise\n" if status == "killed" else ""
        body += (f"## {item_id} — Thing   [ ]\n\ndomain: p\nrepo: r\nsuggested_mode: review\n"
                 f"source: human\nevidence: none-yet\nwhy_now: x\nstatus: {status}\n{extra}"
                 "dod:\n  - measurable\n\n")
    (tmp_path / "BACKLOG.md").write_text(body, encoding="utf-8")
    if events is not None:
        (tmp_path / "records").mkdir(exist_ok=True)
        (tmp_path / "records" / "cycle-events.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return tmp_path


def _released(slug: str) -> dict:
    return {"type": "cycle:phase:end", "cycle": "release", "slug": slug,
            "verdict": "RELEASED", "timestamp": "2026-08-31T13:00:00Z"}


def _status(project: Path, item: str) -> str:
    import backlog_status as bs
    content = (project / "BACKLOG.md").read_text(encoding="utf-8")
    start, end = bs._blocks(content)[item]
    return bs._status_of(content[start:end])


# ── the signal, and only the signal ───────────────────────────────────────────


def test_a_released_event_ships_the_item(tmp_path: Path) -> None:
    project = _project(tmp_path, [("B-001", "planned")], events=[_released("B-001")])
    result = advance(project / "BACKLOG.md", project, apply=True)
    assert result.shipped == ["B-001"]
    assert _status(project, "B-001") == "shipped"


def test_a_plan_slug_still_names_the_item(tmp_path: Path) -> None:
    project = _project(tmp_path, [("B-033", "planned")],
                       events=[_released("b033-prometheus-url-dev-public")])
    assert advance(project / "BACKLOG.md", project, apply=True).shipped == ["B-033"]


@pytest.mark.parametrize("event", [
    {"type": "cycle:phase:end", "cycle": "review", "slug": "B-001", "verdict": "RELEASED"},
    {"type": "cycle:phase:end", "cycle": "release", "slug": "B-001", "verdict": "PR_OPEN_AWAITING_APPROVAL"},
    {"type": "cycle:phase:start", "cycle": "release", "slug": "B-001", "verdict": "RELEASED"},
])
def test_nothing_but_an_explicit_release_verdict_counts(tmp_path: Path, event) -> None:
    """The one signal that means a person approved. Anything looser writes on a guess."""
    project = _project(tmp_path, [("B-001", "planned")], events=[event])
    assert advance(project / "BACKLOG.md", project, apply=True).shipped == []
    assert _status(project, "B-001") == "planned"


def test_no_stream_means_nothing_to_advance(tmp_path: Path) -> None:
    project = _project(tmp_path, [("B-001", "planned")])
    assert advance(project / "BACKLOG.md", project, apply=True).shipped == []


# ── it decides nothing ────────────────────────────────────────────────────────


def test_a_dry_run_writes_nothing(tmp_path: Path) -> None:
    project = _project(tmp_path, [("B-001", "planned")], events=[_released("B-001")])
    result = advance(project / "BACKLOG.md", project, apply=False)
    assert result.shipped == ["B-001"]
    assert _status(project, "B-001") == "planned"


def test_running_twice_changes_nothing_the_first_run_did(tmp_path: Path) -> None:
    project = _project(tmp_path, [("B-001", "planned")], events=[_released("B-001")])
    advance(project / "BACKLOG.md", project, apply=True)
    second = advance(project / "BACKLOG.md", project, apply=True)
    assert second.shipped == [] and second.already == ["B-001"]


def test_a_killed_item_is_refused_and_the_refusal_is_reported(tmp_path: Path) -> None:
    """A refusal usually means the registry knows something the stream does not."""
    project = _project(tmp_path, [("B-001", "killed")], events=[_released("B-001")])
    result = advance(project / "BACKLOG.md", project, apply=True)
    assert result.shipped == []
    assert result.refused and "B-001" in result.refused[0]


def test_a_blocked_item_is_refused(tmp_path: Path) -> None:
    """`backlog_status.py` owns that rule; this must not route around it."""
    import backlog_status as bs

    project = _project(tmp_path, [("B-001", "planned"), ("B-002", "raw")],
                       events=[_released("B-001")])
    backlog = project / "BACKLOG.md"
    backlog.write_text(bs.block(backlog.read_text(encoding="utf-8"), "B-001", ["B-002"]),
                       encoding="utf-8")
    result = advance(backlog, project, apply=True)
    assert result.shipped == [] and result.refused


def test_an_item_released_elsewhere_is_reported_not_invented(tmp_path: Path) -> None:
    project = _project(tmp_path, [("B-001", "planned")], events=[_released("B-999")])
    assert advance(project / "BACKLOG.md", project, apply=True).unknown == ["B-999"]


def test_one_refusal_does_not_stop_the_others(tmp_path: Path) -> None:
    project = _project(tmp_path, [("B-001", "killed"), ("B-002", "planned")],
                       events=[_released("B-001"), _released("B-002")])
    result = advance(project / "BACKLOG.md", project, apply=True)
    assert result.shipped == ["B-002"] and len(result.refused) == 1


# ── reading the stream ────────────────────────────────────────────────────────


def test_a_repeated_release_event_names_the_item_once(tmp_path: Path) -> None:
    project = _project(tmp_path, [("B-001", "planned")],
                       events=[_released("B-001"), _released("b-001-something")])
    assert released_items(project) == ["B-001"]


def test_a_truncated_last_line_does_not_break_it(tmp_path: Path) -> None:
    project = _project(tmp_path, [("B-001", "planned")], events=[_released("B-001")])
    stream = project / "records" / "cycle-events.jsonl"
    stream.write_text(stream.read_text(encoding="utf-8") + '{"type": "cycle', encoding="utf-8")
    assert released_items(project) == ["B-001"]
