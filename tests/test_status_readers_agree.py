"""Five readers decide on `status:` and each keeps its own copy of the values.

`backlog_status.py` owns the transitions, `check_backlog_structure.py` gates the
registry, `select_backlog_item.py` decides what may start, `board_state.py` maps
status to phase, and `backlog_index.py` renders it. None imports the others —
deliberately, because each must read a registry written by anything and cannot
inherit another's assumptions.

That independence is why the set has to be pinned across them. A sixth status
added to four of five is a status the fifth silently drops: an item in it is
neither selectable nor blocked nor rendered, and every surface reports normally.
This kit has measured that shape five times in one day, one level down, on
`blocked_by` and on item-id width — this is the same test one level up.

Sibling of `test_item_id_readers_agree.py` and `test_blocked_by_readers_agree.py`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The contract. `rules/cycle-backlog.md § Item schema` is the authority; this
#: list is the executable copy, and the first test below holds the two together.
CONTRACT_STATUSES = frozenset(
    {"raw", "triaged", "approved", "planned", "shipped", "killed"}
)

#: Every file that DECIDES using a status value, and what each is for. A file
#: that merely mentions one in prose is not here — the invariant is about
#: readers whose behaviour changes with the value.
READERS = {
    "mechanisms/cycle/backlog_status.py": "owns the transitions",
    "skills/backlog-review/scripts/check_backlog_structure.py": "gates the registry",
    "skills/backlog-review/scripts/select_backlog_item.py": "decides what may start",
    "skills/backlog-review/scripts/board_state.py": "maps status to phase",
    "skills/backlog-review/scripts/backlog_index.py": "renders the index",
}


def _statuses_named_in(path: Path) -> set[str]:
    """Status values a file names as string literals."""
    text = path.read_text(encoding="utf-8")
    found = set()
    for candidate in CONTRACT_STATUSES:
        if re.search(rf'["\']{candidate}["\']', text):
            found.add(candidate)
    return found


@pytest.mark.parametrize("rel", sorted(READERS))
def test_the_reader_exists(rel: str) -> None:
    """A reader that moved silently stops being checked by everything below."""
    assert (REPO_ROOT / rel).is_file(), f"{rel} is gone — {READERS[rel]}"


def test_the_contract_document_lists_exactly_these_statuses() -> None:
    """The executable copy above must match the document that governs it.

    `rules/cycle-backlog.md` carries the schema row enumerating the values. If
    the document gains a status and this list does not, every test below passes
    while the readers are measured against the wrong set.
    """
    rule = (REPO_ROOT / "rules" / "cycle-backlog.md").read_text(encoding="utf-8")
    row = re.search(r"(?m)^\|\s*`status`\s*\|.*$", rule)
    assert row, "rules/cycle-backlog.md has no `status` schema row"

    in_document = set(re.findall(r"`(raw|triaged|approved|planned|shipped|killed)`", row.group(0)))
    assert in_document == set(CONTRACT_STATUSES), (
        f"the rule's schema row and this test disagree.\n"
        f"  document: {sorted(in_document)}\n"
        f"  test:     {sorted(CONTRACT_STATUSES)}"
    )


def test_no_reader_names_a_status_the_contract_does_not_have() -> None:
    """A value one reader accepts and the contract does not is a value nothing
    else will ever produce — dead handling that reads as coverage."""
    for rel in sorted(READERS):
        named = _statuses_named_in(REPO_ROOT / rel)
        assert named <= CONTRACT_STATUSES, (
            f"{rel} names statuses outside the contract: {sorted(named - CONTRACT_STATUSES)}"
        )


def test_every_terminal_and_open_status_is_known_to_the_transition_owner() -> None:
    """`backlog_status.py` writes the field, so it must know every value.

    A status it does not name cannot be reached through the mechanism, which
    leaves hand-editing as the only route — and hand-editing is the failure this
    module was written to end.
    """
    named = _statuses_named_in(REPO_ROOT / "mechanisms/cycle/backlog_status.py")
    missing = CONTRACT_STATUSES - named
    assert not missing, (
        f"backlog_status.py cannot write these: {sorted(missing)}. An item can "
        f"only reach them by hand, which is what this module exists to prevent."
    )


def test_the_gate_knows_every_status_the_transition_owner_can_write() -> None:
    """Anything writable must be gateable, or the gate sweeps past it."""
    writer = _statuses_named_in(REPO_ROOT / "mechanisms/cycle/backlog_status.py")
    gate = _statuses_named_in(
        REPO_ROOT / "skills/backlog-review/scripts/check_backlog_structure.py"
    )
    missing = writer - gate
    assert not missing, (
        f"check_backlog_structure.py does not know {sorted(missing)}, which "
        f"backlog_status.py can write. An item in one of those passes the gate "
        f"by not being looked at."
    )


def test_the_selector_classifies_every_status() -> None:
    """The selector must place every status somewhere: startable, or held.

    A status it does not name falls through to neither. The item is then absent
    from the queue AND absent from the reasons — invisible on both surfaces at
    once, which is the worst shape this registry can produce.
    """
    named = _statuses_named_in(
        REPO_ROOT / "skills/backlog-review/scripts/select_backlog_item.py"
    )
    missing = CONTRACT_STATUSES - named
    assert not missing, (
        f"select_backlog_item.py never names {sorted(missing)}. An item there is "
        f"neither offered nor explained."
    )


# ── killing a commitment is not killing a hypothesis ─────────────────────────

def _status_module():
    sys.path.insert(0, str(REPO_ROOT / "mechanisms" / "cycle"))
    import backlog_status
    return backlog_status


ITEM = """## B-001 — a title   [ ]

domain: engine
repo: theo
status: {status}
dod:
  - something falsifiable
"""


def test_killing_a_hypothesis_takes_any_stated_reason() -> None:
    """Before approval the item is a question and the measurement answered it.
    A reason that reports what the evidence showed is the whole requirement."""
    bs = _status_module()
    out = bs.advance(ITEM.format(status="triaged"), "B-001", "killed",
                     kill_reason="measured 2026-09-04: the leak does not reproduce")
    assert "status: killed" in out


def test_killing_a_commitment_needs_who_reversed_it() -> None:
    """After approval, somebody had decided. Reversing that is a decision, and a
    reason that only restates evidence does not name the decision being undone.

    This is the whole point of the `approved` state: without it, the cheapness of
    killing a hunch applied equally to work someone had committed to.
    """
    bs = _status_module()
    for status in ("approved", "planned"):
        with pytest.raises(bs.Refused) as excinfo:
            bs.advance(ITEM.format(status=status), "B-001", "killed",
                       kill_reason="the measurement did not hold up")
        assert "reversed" in str(excinfo.value).lower(), str(excinfo.value)


def test_a_commitment_killed_with_a_named_reverser_is_allowed() -> None:
    """The bar is higher, not impassable."""
    bs = _status_module()
    out = bs.advance(
        ITEM.format(status="approved"), "B-001", "killed",
        kill_reason="reversed by the sponsor 2026-09-04: the customer withdrew the "
                    "requirement this was approved for",
    )
    assert "status: killed" in out
