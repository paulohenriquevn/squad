"""An id named three times in one sentence is one impediment, not three.

`parse_blocked_by` extracts ids from prose rather than parsing a fixed shape, and that is
right: of the eight items carrying `blocked_by` when the field was measured, seven named a
sponsor decision or an external action and only one named an item, so demanding `B-NNN`
would have reported seven honest impediments as malformed. The prose form is not the bug.

The bug is that it returns one entry per OCCURRENCE. Reported by a consumer, reproduced
here in both copies:

    raw = 'B-270 — B-270 — measured... cannot pass until B-270 does.'
    gate  : ['B-270', 'B-270', 'B-270']
    writer: ['B-270', 'B-270', 'B-270']

So the board printed `blocks B-229, B-229, B-229` and the selector printed
`B-229 <- B-270, B-270, B-270` — one impediment counted three times, on both sides of the
edge. Any count derived from the list is wrong by however many times an author repeated
the id while explaining it, which is most often in the items that explain it best.

Two copies, deliberately: the gate must review a registry written by anything, so it cannot
import the writer and inherit its assumptions. Both are asserted here, because a fix in one
is the half-applied shape this repository has measured repeatedly.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "skills" / "backlog-review" / "scripts"))
sys.path.insert(0, str(_ROOT / "mechanisms" / "cycle"))
sys.path.insert(0, str(_ROOT))

from backlog_status import parse_blocked_by as writer_parse  # noqa: E402
from check_backlog_structure import parse_blocked_by as gate_parse  # noqa: E402

_REPEATED = "B-270 — B-270 — measured against the bundle; cannot pass until B-270 does."
_TWO = "B-270 and B-271 both have to land first."
_PROSE_ONLY = "waiting on the sponsor to sign the data-processing agreement."


def test_both_readers_count_a_repeated_id_once() -> None:
    assert gate_parse(_REPEATED) == ["B-270"], gate_parse(_REPEATED)
    assert writer_parse(_REPEATED) == ["B-270"], writer_parse(_REPEATED)


def test_distinct_ids_survive_in_the_order_written() -> None:
    """Dedup must not become dedup-to-one."""
    assert gate_parse(_TWO) == ["B-270", "B-271"]
    assert writer_parse(_TWO) == ["B-270", "B-271"]


def test_prose_naming_no_item_is_still_an_impediment_with_no_ids() -> None:
    """The seven-of-eight case the prose form exists for."""
    assert gate_parse(_PROSE_ONLY) == []
    assert writer_parse(_PROSE_ONLY) == []


def test_the_two_readers_agree_on_every_shape() -> None:
    """A fix applied to one copy is the half-applied shape, so the agreement is asserted."""
    for raw in (_REPEATED, _TWO, _PROSE_ONLY,
                "B-001 B-001 B-002 B-001",
                "blocked on B-300; see B-300 for the measurement"):
        assert gate_parse(raw) == writer_parse(raw), raw
