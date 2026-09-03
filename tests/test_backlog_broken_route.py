"""The structure report refuses a domain whose specialist is not on disk.

`route_domain.py` already treats that as a BROKEN ROUTE and exits 3 — "a defect in the
table itself". `check_backlog_structure.py` did not ask: gate G1 checks whether a repo
is IN the routing table, never whether the table's ANSWER exists. So a registry could
report SHIPPABLE while every one of its items resolved to a file nobody had written.

Measured on an adopter 2026-09-03: the table named `agents/theocode.md`, that file did
not exist, `route_domain.py` exited 3 for every repo, and the structure report was clean
across 136 items.

That is the failure the routing gate exists to prevent, one level up, and it failed in
the reassuring direction — which is the direction that gets a gate trusted while it is
reporting about nothing.

These tests name no repository and no domain of any particular project: the table is
DERIVED per project (`rules/cycle-backlog.md § Domain routing`), so asserting about a
concrete map would rot the moment an adopter re-derived theirs.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "backlog-review" / "scripts"))

from check_backlog_structure import check_backlog  # noqa: E402

BACKLOG = """# BACKLOG

## Items

## B-001 — An item that routes somewhere   [ ]

domain: alpha
repo: alpha-repo
suggested_mode: review
source: human
evidence: none-yet
why_now: something changed here
status: raw
dod:
  - the endpoint answers within a stated budget, proved by a failing-first test
"""


def _project(tmp_path: Path, *, specialist: bool) -> Path:
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "domain-routing.txt").write_text(
        "alpha | alpha-repo | agents/alpha.md\n", encoding="utf-8"
    )
    agents = tmp_path / "agents"
    agents.mkdir()
    if specialist:
        (agents / "alpha.md").write_text("# alpha\n", encoding="utf-8")
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(BACKLOG, encoding="utf-8")
    return backlog


def _kinds(report: dict) -> list[str]:
    """`Finding` is (check, kind, severity, item, message). `kind` is the deterministic/heuristic
    label, NOT the identifier — reading it returned "deterministic" for everything and made the first
    version of this test pass for the wrong reason."""
    return [f["check"] if isinstance(f, dict) else f.check for f in report["findings"]]


def test_a_domain_whose_specialist_is_missing_is_a_blocker(tmp_path: Path) -> None:
    """The finding. Without it the report is clean while every item routes to nobody."""
    report = check_backlog(_project(tmp_path, specialist=False))

    assert "broken_route" in _kinds(report), (
        "the specialist named by the routing table does not exist and the report said nothing"
    )


def test_a_domain_whose_specialist_exists_is_not_flagged(tmp_path: Path) -> None:
    """Anti-vacuity: flagging every domain would satisfy the assertion above."""
    report = check_backlog(_project(tmp_path, specialist=True))

    assert "broken_route" not in _kinds(report)


def test_the_blocker_names_the_file_that_is_missing(tmp_path: Path) -> None:
    """A gate that refuses without saying what to create is a gate people work around."""
    report = check_backlog(_project(tmp_path, specialist=False))

    messages = " ".join(
        f["message"] if isinstance(f, dict) else f.message for f in report["findings"]
    )
    assert "agents/alpha.md" in messages
