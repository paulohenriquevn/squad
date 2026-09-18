"""Moving an item back is a withdrawal, and the rule says it is never silent.

`cycle-maintenance.md § Rollback`:

    An item advanced in error is moved back with a note recording the advance and
    why it was withdrawn — never silently reset. An item whose `shipped` was
    withdrawn carries information a fresh-looking `triaged` item does not.

`backlog_status.ALLOWED` implements half of that and implements the half without
the note. Measured here:

    approved -> triaged   accepted, and the block afterwards carries `status:
                          triaged` and nothing else — a fresh-looking item, which
                          is the outcome the rule names as the thing to avoid
    planned  -> approved  same
    triaged  -> raw       refused outright, though it is the same move one step down

So an item could be walked back through the whole open chain leaving no trace,
while the one backward step the table omits was the one a consumer needed.

The mechanism already knows how to hold a reversal to a higher bar: `--kill-reason`
on a `COMMITTED_STATUS` item must name who reversed it and what changed, because
"a reason that only restates the evidence is what a hypothesis gets; a commitment
gets a person and a change of mind." A withdrawal is the same kind of event, so it
takes the same kind of reason and is written into the block where the next reader
finds it.

`shipped` stays terminal. The rule's sentence about a withdrawn `shipped` is the
argument for why the note matters, and reopening a shipped item changes what
shipped means to every reader that counts delivery — that is a decision for a
person, not a consequence of this fix.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "mechanisms" / "cycle"))

from backlog_status import ALLOWED, Refused, advance  # noqa: E402


def _block(status: str) -> str:
    return (
        "## B-001 — Reduce round-trips   [ ]\n\n"
        "domain: data-plane-ts\nrepo: web-console\nsuggested_mode: review\n"
        "source: human\nevidence: src/trace/list.py:31 — 4 round-trips per row\n"
        "why_now: the dashboard loads 30d by default\n"
        f"status: {status}\ndod:\n  - p95 under 800ms\n"
    )


@pytest.mark.parametrize(("frm", "to"), [("approved", "triaged"),
                                         ("planned", "approved"),
                                         ("triaged", "raw")])
def test_a_backward_move_without_a_reason_is_refused(frm: str, to: str) -> None:
    with pytest.raises(Refused) as exc:
        advance(_block(frm), "B-001", to)
    assert "withdraw" in str(exc.value).lower(), exc.value


@pytest.mark.parametrize(("frm", "to"), [("approved", "triaged"),
                                         ("planned", "approved"),
                                         ("triaged", "raw")])
def test_the_withdrawal_and_its_reason_are_written_into_the_block(frm: str, to: str) -> None:
    reason = f"Paulo withdrew the {frm} call: the measurement did not hold"
    out = advance(_block(frm), "B-001", to, withdraw_reason=reason)
    assert f"status: {to}" in out
    assert reason in out, "the reason was accepted and not recorded"
    assert frm in out, f"the block does not say it was ever {frm}"


def test_the_step_down_from_triaged_exists_at_all() -> None:
    """The gap a consumer hit: the rule prescribes the move and the table omitted it."""
    assert "raw" in ALLOWED["triaged"]


def test_a_reason_that_only_restates_the_evidence_is_refused() -> None:
    """Same bar `--kill-reason` holds a committed item to, for the same reason.

    A withdrawal is a decision being reversed. A sentence that repeats what was
    already measured does not say who changed their mind, which is the only part a
    later reader cannot reconstruct.
    """
    with pytest.raises(Refused):
        advance(_block("approved"), "B-001", "triaged",
                withdraw_reason="4 round-trips per row")


def test_a_forward_move_is_untouched() -> None:
    """Advancing is not a withdrawal and must not start demanding one."""
    out = advance(_block("triaged"), "B-001", "approved")
    assert "status: approved" in out


def test_shipped_stays_terminal() -> None:
    """Pinned deliberately: reopening it is a person's call, not this fix's."""
    assert ALLOWED["shipped"] == set()
    with pytest.raises(Refused):
        advance(_block("shipped"), "B-001", "planned", withdraw_reason="x withdrew y")
