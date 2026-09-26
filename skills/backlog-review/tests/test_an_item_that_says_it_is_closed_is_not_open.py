"""A block that declares itself closed, filed as open, is a registry contradicting itself.

Measured on a consumer 2026-09-18: **fourteen** items carried a dated remeasurement in their own
body — `remeasured 2026-08-21: **closed in code.**`, `**closed by deletion.**` — and every one of
them was still `status: triaged`. The structure report read SHIPPABLE across all 44 items.

The cause is not carelessness. `backlog_status.py` refuses `triaged -> shipped` ("from triaged it
may go to approved, killed"), and `approved` is a human decision the agent may not make. So whoever
remeasured wrote the finding where they could — the prose — and the status field had nowhere legal
to go. The registry then reports finished work as pending, which is the rot
`rules/cycle-maintenance.md` exists to prevent, arriving through the one door the state machine left
open.

The check is deliberately about the CONTRADICTION and not about whether the item is really done.
Nothing here can measure that. What it can say is that two halves of the same block disagree, and
that a reader has no way to know which half to believe.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from check_backlog_structure import check_backlog  # after the bootstrap above

_HEAD = """# BACKLOG

## Items

"""


def _block(item: str, status: str, note: str) -> str:
    return f"""## {item} — An item with a body and a status   [ ]

domain: alpha
repo: alpha-repo
suggested_mode: review
source: human
evidence: packages/alpha/src/thing.ts:12 — measured, and it resolves
why_now: something changed here
status: {status}
dod:
  - the endpoint answers within a stated budget, proved by a failing-first test

{note}
"""


def _project(tmp_path: Path, blocks: str) -> Path:
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "domain-routing.txt").write_text(
        "alpha | alpha-repo | agents/alpha.md\n", encoding="utf-8"
    )
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "alpha.md").write_text("# alpha\n", encoding="utf-8")
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(_HEAD + blocks, encoding="utf-8")
    return backlog


def _checks(report: dict) -> list[str]:
    return [f["check"] if isinstance(f, dict) else f.check for f in report["findings"]]


def test_open_status_plus_closed_in_code_body(tmp_path: Path) -> None:
    backlog = _project(
        tmp_path,
        _block("B-001", "triaged", "remeasured 2026-08-21: **closed in code.** The caller exists."),
    )
    report = check_backlog(backlog)
    assert "status_contradicts_body" in _checks(report), (
        "an item whose body says it is closed and whose status says triaged was not reported; "
        f"got {_checks(report)}"
    )


def test_closed_by_deletion_counts_too(tmp_path: Path) -> None:
    """`closed by deletion` is the same claim about a different remedy."""
    backlog = _project(
        tmp_path,
        _block("B-002", "raw", "remeasured 2026-08-21: **closed by deletion.** The file is gone."),
    )
    assert "status_contradicts_body" in _checks(check_backlog(backlog))


def test_a_terminal_status_with_the_same_note_is_NOT_reported(tmp_path: Path) -> None:
    """COUNTERPROOF. The finding is the disagreement, not the phrase — an item that says it is
    closed AND is filed closed is the state this check wants to see more of."""
    backlog = _project(
        tmp_path,
        _block("B-003", "shipped", "remeasured 2026-08-21: **closed in code.** The caller exists."),
    )
    assert "status_contradicts_body" not in _checks(check_backlog(backlog))


def test_an_open_item_with_no_such_note_is_NOT_reported(tmp_path: Path) -> None:
    """COUNTERPROOF against firing on ordinary prose: a remeasurement that found the item still
    open must not be read as a closure."""
    backlog = _project(
        tmp_path,
        _block("B-004", "triaged", "remeasured 2026-08-21: **not started**, and the reason is scope."),
    )
    assert "status_contradicts_body" not in _checks(check_backlog(backlog))
