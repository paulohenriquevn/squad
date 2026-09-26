"""The board said an item was blocked and never who could unblock it.

Seven items held on one consumer, and the page rendered seven identical amber cards.
The reader's real question — *which of these is waiting on ME* — had no answer on
screen, and the difference is not cosmetic: three of those seven are the queue's own
work and four need a person. Reading "7 blocked" as "7 things I must do" is how an
owner concludes the system is stuck when it is not.

`mechanisms/cycle/delegated_decision.classify_wall` already answers this. It reads the
`blocked_by` prose and returns a class plus whether the sponsor delegated it, against
`rules/decision-delegation.txt`. The board carried the prose and not the verdict, so the
information existed one import away from the view built to show it.

WHAT THIS DOES NOT DO

It does not decide anything. `classify_wall` classifies; the board renders what it said.
An unmatched wall stays `unclassified` and renders as the person's, because
`on_no_match = retain` is the registry's rule and a view that softened it would be
claiming consent nobody gave.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from board_state import build_state  # after the bootstrap above

_REGISTRY = """# BACKLOG

## Items

## B-001 — Waits on another item   [ ]

domain: alpha
repo: r
suggested_mode: review
source: human
evidence: measured
why_now: it matters
status: planned
blocked_by: B-007 — its scheduler is a production caller by construction

## B-002 — Waits on a person   [ ]

domain: alpha
repo: r
suggested_mode: review
source: human
evidence: measured
why_now: it matters
status: planned
blocked_by: a work tenant is needed before Teams can be exercised end to end

## B-003 — Not blocked at all   [ ]

domain: alpha
repo: r
suggested_mode: review
source: human
evidence: measured
why_now: it matters
status: raw

## B-007 — The blocker itself, open   [ ]

domain: alpha
repo: r
suggested_mode: review
source: human
evidence: measured
why_now: it matters
status: raw
"""


def _project(tmp_path: Path) -> Path:
    (tmp_path / "BACKLOG.md").write_text(_REGISTRY, encoding="utf-8")
    (tmp_path / ".squad" / "records").mkdir(parents=True)
    return tmp_path


def _by_id(tmp_path: Path) -> dict:
    return {i["id"]: i for i in build_state(_project(tmp_path))["items"]}


def test_a_wall_the_system_can_clear_is_marked_as_the_systems(tmp_path: Path) -> None:
    """B-001 waits on another item. Nobody is going to decide that.

    B-007 is in the fixture and open on purpose: the board treats a wall naming a
    blocker that is closed or absent as no longer live, which is correct and is a
    different question from who owns a live one.
    """
    item = _by_id(tmp_path)["B-001"]

    assert item.get("blocked_owner") == "system", (
        f"an item waiting on another item was drawn as the person's: {item.get('blocked_owner')!r}")
    assert item.get("blocked_class") == "dependency"


def test_a_wall_only_a_person_can_clear_says_so(tmp_path: Path) -> None:
    """The half that must not go quiet: an access impediment is the person's, and
    drawing it as the system's would promise work that cannot happen."""
    item = _by_id(tmp_path)["B-002"]

    assert item.get("blocked_owner") == "person", (
        f"an access impediment was handed to the system: {item.get('blocked_owner')!r}")


def test_an_unblocked_item_carries_no_owner(tmp_path: Path) -> None:
    """No phantom field. An item with nothing in its way must not render a blocker
    chip at all."""
    item = _by_id(tmp_path)["B-003"]

    assert not item.get("blocked")
    assert not item.get("blocked_owner")


def test_the_page_renders_the_owner(tmp_path: Path) -> None:
    """The data reaching the state file is half the job; the card has to show it."""
    html = (Path(__file__).resolve().parents[1] / "scripts" / "board.html").read_text(
        encoding="utf-8")

    assert "blocked_owner" in html, (
        "the classification is computed and never drawn — the reader still cannot tell "
        "which blockers are theirs")
