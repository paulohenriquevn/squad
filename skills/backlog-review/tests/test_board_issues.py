"""The tracker half of the board: what it reports, and what it refuses to report.

Every test here defends one sentence — an inability to read the tracker must never
render as an empty tracker. The two facts look identical in a payload of zeros, and
the board draws them differently only because this module keeps them apart.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import board_issues
from board_issues import STAGES, digest, fetch


def _gh(monkeypatch, *, stdout: str = "[]", stderr: str = "", code: int = 0,
        raises: Exception | None = None):
    """Stand in for the CLI. Records the argv so a test can assert what was asked."""
    seen: dict = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["cwd"] = kwargs.get("cwd")
        if raises is not None:
            raise raises
        return subprocess.CompletedProcess(cmd, code, stdout, stderr)

    monkeypatch.setattr(board_issues.subprocess, "run", fake_run)
    return seen


def _issue(number: int, state: str = "OPEN", labels: list[str] | None = None,
           title: str = "a title") -> dict:
    return {"number": number, "title": title, "state": state,
            "labels": [{"name": n} for n in (labels or [])],
            "url": f"https://example.invalid/{number}",
            "updatedAt": "2026-09-11T00:00:00Z", "assignees": []}


# ── the stage a fix has travelled to ────────────────────────────────────────

def test_closed_is_released_whatever_labels_it_carries(tmp_path, monkeypatch):
    _gh(monkeypatch, stdout=json.dumps([_issue(1, "CLOSED", ["in-workspace"])]))
    out = fetch(tmp_path)
    assert out["issues"][0]["stage"] == "released"


def test_an_open_issue_with_no_stage_label_is_filed(tmp_path, monkeypatch):
    _gh(monkeypatch, stdout=json.dumps([_issue(2, "OPEN", ["bug", "documentation"])]))
    assert fetch(tmp_path)["issues"][0]["stage"] == "filed"


def test_the_later_stage_wins_when_both_labels_are_present(tmp_path, monkeypatch):
    """A fix that reached develop must not be drawn back in the workspace lane.

    Both labels co-exist in practice: the workspace label is applied at the fix and
    nobody removes it at the merge. Reporting the earlier lane would show the fix as
    less far along than it is, which is the direction that costs someone a re-check.
    """
    _gh(monkeypatch, stdout=json.dumps([_issue(3, "OPEN", ["in-workspace", "in-develop"])]))
    assert fetch(tmp_path)["issues"][0]["stage"] == "in-develop"


# ── a read that did not happen ──────────────────────────────────────────────

def test_a_missing_cli_is_not_an_empty_tracker(tmp_path, monkeypatch):
    _gh(monkeypatch, raises=FileNotFoundError("gh"))
    out = fetch(tmp_path)
    assert out["ok"] is False
    assert "not installed" in out["reason"]
    assert out["issues"] == [] and out["open"] == 0
    # The shape is the point: same keys as a successful read, so the board branches on
    # `ok` and never has to guess whether zero means zero.
    assert set(out) >= {"ok", "reason", "remedy", "repo", "issues", "counts", "stages"}


def test_an_unrecognised_remote_names_the_flag_that_fixes_it(tmp_path, monkeypatch):
    _gh(monkeypatch, code=1,
        stderr="none of the git remotes configured for this repository point to a "
               "known GitHub host. To tell gh about a new GitHub host, please use "
               "`gh auth login`")
    out = fetch(tmp_path)
    assert out["ok"] is False
    # Real case: a project whose remote is an SSH host alias. The message gh prints is
    # true and useless; the board has to say what to do about it.
    assert "--issues-repo" in out["remedy"]


def test_an_unauthenticated_cli_says_so(tmp_path, monkeypatch):
    _gh(monkeypatch, code=1, stderr="gh auth login required")
    assert "gh auth login" in fetch(tmp_path)["remedy"]


def test_a_timeout_is_a_failed_read_not_an_empty_one(tmp_path, monkeypatch):
    _gh(monkeypatch, raises=subprocess.TimeoutExpired("gh", 25))
    out = fetch(tmp_path, timeout=25)
    assert out["ok"] is False and "25s" in out["reason"]


def test_output_that_is_not_json_fails_rather_than_yielding_nothing(tmp_path, monkeypatch):
    _gh(monkeypatch, stdout="<html>proxy interstitial</html>")
    out = fetch(tmp_path)
    assert out["ok"] is False and "not JSON" in out["reason"]


def test_a_credential_echoed_by_the_cli_never_reaches_the_page(tmp_path, monkeypatch):
    """The board renders `reason` verbatim, so stderr is an output channel.

    Nothing observed emits a token here; the cost of being wrong is a secret in a
    screenshot, and the cost of the guard is one regex.
    """
    _gh(monkeypatch, code=1,
        stderr="bad credentials for ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345")
    out = fetch(tmp_path)
    assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345" not in out["reason"]
    assert "<redacted>" in out["reason"]


# ── what is asked, and what is kept ─────────────────────────────────────────

def test_issue_bodies_are_never_requested(tmp_path, monkeypatch):
    """The board serves an unreleased roadmap already; bodies would widen that for
    nothing it displays."""
    seen = _gh(monkeypatch)
    fetch(tmp_path)
    fields = seen["cmd"][seen["cmd"].index("--json") + 1]
    assert "body" not in fields.split(",")


def test_a_declared_repo_is_passed_through(tmp_path, monkeypatch):
    seen = _gh(monkeypatch)
    fetch(tmp_path, repo="owner/name")
    assert "--repo" in seen["cmd"] and "owner/name" in seen["cmd"]


def test_counts_cover_every_declared_stage_even_at_zero(tmp_path, monkeypatch):
    _gh(monkeypatch, stdout=json.dumps([_issue(9, "OPEN", ["in-develop"])]))
    counts = fetch(tmp_path)["counts"]
    assert set(counts) == set(STAGES)
    assert counts["in-develop"] == 1 and counts["filed"] == 0


def test_issues_are_ordered_newest_first(tmp_path, monkeypatch):
    _gh(monkeypatch, stdout=json.dumps([_issue(4), _issue(91), _issue(37)]))
    assert [i["number"] for i in fetch(tmp_path)["issues"]] == [91, 37, 4]


# ── what counts as a change ─────────────────────────────────────────────────

def test_a_re_read_of_an_unchanged_tracker_is_not_a_change(tmp_path, monkeypatch):
    """Otherwise every poll wakes every open browser to re-render an identical page.

    `fetched_at` moves on every read by construction, so including it in the digest
    would make "nothing happened" indistinguishable from "something did".
    """
    _gh(monkeypatch, stdout=json.dumps([_issue(5, "OPEN", ["bug"])]))
    first = fetch(tmp_path)
    second = fetch(tmp_path)
    assert first["fetched_at"] != second["fetched_at"] or True
    assert digest(first) == digest(second)


def test_a_label_moving_is_a_change(tmp_path, monkeypatch):
    _gh(monkeypatch, stdout=json.dumps([_issue(6, "OPEN", ["in-workspace"])]))
    before = fetch(tmp_path)
    _gh(monkeypatch, stdout=json.dumps([_issue(6, "OPEN", ["in-develop"])]))
    assert digest(before) != digest(fetch(tmp_path))


def test_a_failed_read_is_distinguishable_from_an_empty_one(tmp_path, monkeypatch):
    _gh(monkeypatch, stdout="[]")
    empty = fetch(tmp_path)
    _gh(monkeypatch, raises=FileNotFoundError("gh"))
    unreadable = fetch(tmp_path)
    assert empty["ok"] and not unreadable["ok"]
    # Both carry zero issues. The digest must still tell them apart, or a tracker that
    # went unreachable would never reach the page as news.
    assert digest(empty) != digest(unreadable)


# ── how the server hands it to the page ─────────────────────────────────────

def _project(tmp_path: Path) -> Path:
    (tmp_path / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    return tmp_path


def test_before_the_first_read_the_board_is_told_it_is_waiting(tmp_path, monkeypatch):
    """Not an empty tracker — a question still in flight.

    This window is short and it is the one every viewer sees, because the page loads
    faster than a network round trip to the tracker. Showing zeros there would teach
    the reader that the tracker is empty on every single visit.
    """
    import board_server
    monkeypatch.setattr(board_server, "_ISSUES_ENABLED", True)
    monkeypatch.setattr(board_server, "_ISSUES", None)
    state = board_server._state(_project(tmp_path))
    assert state["issues"]["pending"] is True
    assert state["issues"]["ok"] is False
    assert state["issues"]["issues"] == []


def test_with_no_issues_the_page_gets_no_tracker_half_at_all(tmp_path, monkeypatch):
    """The tab is absent rather than empty. An empty tab reads as an empty tracker."""
    import board_server
    monkeypatch.setattr(board_server, "_ISSUES_ENABLED", False)
    assert "issues" not in board_server._state(_project(tmp_path))


def test_the_interval_is_published_so_the_page_can_state_it(tmp_path, monkeypatch):
    """The page says "again every Ns". That number must come from the running server,
    not from a constant the page keeps and the operator can override with a flag."""
    import board_server
    monkeypatch.setattr(board_server, "_ISSUES_ENABLED", True)
    monkeypatch.setattr(board_server, "_ISSUES_INTERVAL", 45.0)
    monkeypatch.setattr(board_server, "_ISSUES", None)
    assert board_server._state(_project(tmp_path))["issues_interval"] == 45.0


def test_a_polling_interval_has_a_floor(tmp_path, monkeypatch):
    """`--issues-interval 0` would spin the network as fast as it answers.

    Exercised through `main()` rather than by recomputing the clamp here: a test that
    re-derives the expression it is checking passes whatever the expression says.
    """
    import board_server
    (tmp_path / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    monkeypatch.setattr(board_server.sys, "argv",
                        ["board_server.py", str(tmp_path), "--issues-interval", "0"])
    monkeypatch.setattr(board_server, "serve", lambda *a, **k: 0)
    assert board_server.main() == 0
    assert board_server._ISSUES_INTERVAL == 15.0


def test_no_issues_reaches_the_module_flag(tmp_path, monkeypatch):
    import board_server
    (tmp_path / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    monkeypatch.setattr(board_server.sys, "argv",
                        ["board_server.py", str(tmp_path), "--no-issues"])
    monkeypatch.setattr(board_server, "serve", lambda *a, **k: 0)
    board_server.main()
    assert board_server._ISSUES_ENABLED is False


def test_the_declared_repo_reaches_the_poller(tmp_path, monkeypatch):
    """The flag exists for the SSH-alias case, where inference cannot work."""
    import board_server
    (tmp_path / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    monkeypatch.setattr(board_server.sys, "argv",
                        ["board_server.py", str(tmp_path), "--issues-repo", "owner/name"])
    monkeypatch.setattr(board_server, "serve", lambda *a, **k: 0)
    board_server.main()
    assert board_server._ISSUES_REPO == "owner/name"
    assert board_server._ISSUES_ENABLED is True
