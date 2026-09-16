"""A registry four days idle and one working this minute rendered identically.

The board drew positions and never said WHEN, so "where is each item" was answerable and
"is anything happening" was not — and the second is why someone opens a live board.

And one position it drew was false. A `phase:start` was only closed by an end naming the
SAME cycle, so a lane that stopped without emitting its own end left the start hanging
forever. Measured on a consumer 2026-09-16: B-001 opened `plan` on 09-12, never closed
it, then ended `code-quality` on 09-14, 09-15 and again that morning — and four days
later the board still reported `running plan`. Seventeen events for that item, and the
page named the one phase none of them had finished.

A start with no end is a fact about the STREAM. Drawing it as running is a claim about
the WORK, and the two stop agreeing the moment a lane dies.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from board_state import build_state  # noqa: E402


def _registry(tmp_path: Path, *events: dict) -> Path:
    (tmp_path / "BACKLOG.md").write_text(
        "# Backlog\n\n## B-001 — an item\nstatus: approved\n", encoding="utf-8")
    records = tmp_path / ".squad" / "records"
    records.mkdir(parents=True)
    (records / "cycle-events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return tmp_path


def _start(cycle: str, at: str) -> dict:
    return {"type": "cycle:phase:start", "cycle": cycle, "slug": "B-001", "timestamp": at}


def _end(cycle: str, at: str, verdict: str = "PASS") -> dict:
    return {"type": "cycle:phase:end", "cycle": cycle, "slug": "B-001",
            "timestamp": at, "verdict": verdict}


def test_a_later_end_closes_an_abandoned_start(tmp_path: Path) -> None:
    state = build_state(_registry(
        tmp_path,
        _start("plan", "2026-09-12T11:12:13Z"),
        _end("code-quality", "2026-09-16T14:24:31Z", "PASS_WITH_CAVEATS"),
    ))
    assert state["running"] == [], \
        "a phase abandoned four days ago is still drawn as work in flight"
    assert state["items"][0]["phase"] == "code-quality"


def test_a_genuinely_open_phase_is_still_running(tmp_path: Path) -> None:
    """The fix must not silence the case the field exists for."""
    state = build_state(_registry(tmp_path, _start("implement", "2026-09-16T18:00:00Z")))
    assert state["running"] == ["B-001"]
    assert state["items"][0]["running_phase"] == "implement"


def test_the_state_says_when_the_cycle_last_touched_an_item(tmp_path: Path) -> None:
    state = build_state(_registry(
        tmp_path,
        _end("plan", "2026-09-12T11:00:00Z"),
        _end("code-quality", "2026-09-16T16:52:49Z", "PASS_WITH_CAVEATS"),
    ))
    act = state["last_activity"]
    assert act["item"] == "B-001"
    assert act["at"].startswith("2026-09-16T16:52:49")
    assert act["verdict"] == "PASS_WITH_CAVEATS"


def test_an_event_naming_no_item_is_not_activity(tmp_path: Path) -> None:
    """223 of 369 events on a consumer named no item. Counting those as activity lets a
    run that touched nothing report the cycle as busy — the same error as a gate passing
    on a sweep that examined nothing."""
    state = build_state(_registry(
        tmp_path,
        _end("code-quality", "2026-09-12T11:00:00Z"),
        {"type": "cycle:phase:end", "cycle": "code-quality", "slug": None,
         "timestamp": "2026-09-16T17:54:51Z", "verdict": "PASS_WITH_CAVEATS"},
    ))
    assert state["last_activity"]["at"].startswith("2026-09-12"), \
        "an unattributed event was reported as the cycle touching an item"


def test_a_stream_naming_no_item_at_all_says_nothing(tmp_path: Path) -> None:
    """None, not a zero: a stream with no item-attributed event is not a cycle that just
    went quiet, and the page must tell those apart."""
    state = build_state(_registry(tmp_path))
    assert state["last_activity"] is None


def test_a_trailing_end_for_an_earlier_phase_does_not_clear_it(tmp_path: Path) -> None:
    """The first fix closed on ANY later end, and a sibling test refused it.

    `implement` starts, then a trailing `plan` end arrives. An end for an EARLIER phase
    is an event catching up, not evidence the item moved on — clearing on it would hide
    work actually in flight, which is the opposite of the defect being fixed.
    """
    state = build_state(_registry(
        tmp_path,
        _start("implement", "2026-09-16T18:00:00Z"),
        _end("plan", "2026-09-16T18:05:00Z"),
    ))
    assert state["running"] == ["B-001"]
    assert state["items"][0]["running_phase"] == "implement"


def test_an_unknown_cycle_closes_nothing(tmp_path: Path) -> None:
    """A phase outside the chain carries no position, so it is not evidence of order."""
    state = build_state(_registry(
        tmp_path,
        _start("implement", "2026-09-16T18:00:00Z"),
        _end("something-else", "2026-09-16T18:05:00Z"),
    ))
    assert state["running"] == ["B-001"]


# ── the repository's own pulse ───────────────────────────────────────────────

def _checkout(tmp_path: Path) -> Path:
    import subprocess
    root = _registry(tmp_path)
    for args in (["init", "-q", "-b", "workspace"],
                 ["config", "user.email", "t@example.com"],
                 ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=root, check=True, timeout=120,
                       capture_output=True)
    (root / "a.txt").write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, timeout=120,
                   capture_output=True)
    subprocess.run(["git", "commit", "-qm", "feat(x): the first commit"], cwd=root,
                   check=True, timeout=120, capture_output=True)
    return root


def test_the_board_reads_the_repository_it_is_pointed_at(tmp_path: Path) -> None:
    """`read_lead` answers this question and needs a supervisor writing a marker. A
    board pointed at a repository nobody supervises answered `watching: false` and
    nothing else — while the session had sixteen unpushed commits, the newest from
    minutes earlier. The work was real, visible in git, and invisible on the board."""
    repo = build_state(_checkout(tmp_path))["repo"]
    assert repo["head"], "the board cannot say whether anyone is working in this tree"
    assert repo["subject"] == "feat(x): the first commit"
    assert repo["branch"] == "workspace"
    assert isinstance(repo["committed_at"], int)


def test_a_modified_tracked_file_counts_and_an_untracked_one_does_not(
        tmp_path: Path) -> None:
    """Counting build output as activity would report every repository as busy
    forever."""
    root = _checkout(tmp_path)
    (root / "a.txt").write_text("changed\n", encoding="utf-8")
    (root / "build.log").write_text("noise\n", encoding="utf-8")
    assert build_state(root)["repo"]["dirty_files"] == 1


def test_a_project_that_is_not_a_checkout_says_so(tmp_path: Path) -> None:
    """None rather than zero: "no commits" and "not a repository" are different
    answers, and a zero would read as a clean tree."""
    repo = build_state(_registry(tmp_path))["repo"]
    assert repo["head"] is None


def test_the_two_pulses_stay_separate(tmp_path: Path) -> None:
    """A commit is NOT a phase. Merging them would let a busy repository make an
    untouched backlog look like progress, which is the error this board refuses."""
    state = build_state(_checkout(tmp_path))
    assert state["last_activity"] is None, \
        "a commit was counted as the cycle touching an item"
    assert state["repo"]["head"] is not None
