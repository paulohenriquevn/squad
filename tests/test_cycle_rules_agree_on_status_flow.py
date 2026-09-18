"""The two rules that describe how an item reaches a plan must not contradict each other.

#81: `cycle-backlog.md` owns the status flow and forbids `triaged → planned` in its own
words — *"Nothing reaches a plan without passing DISCOVER's measurement AND being
approved — the two are separate questions"*. `cycle-maintenance.md`'s chain prescribed
exactly that transition, one file away.

The code side was already correct — `select_backlog_item.py` answers `approved` with
`ITEM_AWAITING_PLAN` — so a reader following the macro loop was the only one misled,
which is the worst place for a contradiction to sit.
"""
from __future__ import annotations

import re
from pathlib import Path

_RULES = Path(__file__).resolve().parents[1] / "rules"


def _read(name: str) -> str:
    return (_RULES / name).read_text(encoding="utf-8")


def test_the_macro_loop_does_not_hand_a_triaged_item_to_a_plan() -> None:
    """The exact line that contradicted the schema: `status triaged → /idea-to-release`.
    `/idea-to-release` runs `cycle-plan`, which produces a `planned` item."""
    chain = _read("cycle-maintenance.md")

    offending = [ln for ln in chain.splitlines()
                 if re.search(r"status\s+triaged\s*(→|->)\s*/idea-to-release", ln)]

    assert not offending, offending


def test_the_macro_loop_names_the_approval_step() -> None:
    """`approved` appeared ZERO times in this file — not in the chain, not in the phase
    table, not in the verdict matrix. A status the loop never names is a status the
    loop never reaches."""
    chain = _read("cycle-maintenance.md")

    assert "approved" in chain
    assert re.search(r"status\s+approved\s*(→|->)\s*/idea-to-release", chain), (
        "the chain must hand a plan an APPROVED item, which is the transition "
        "cycle-backlog.md permits")


def test_the_prohibition_is_still_stated_where_it_is_owned() -> None:
    """`cycle-backlog.md` is the declared source of truth for the item schema. If the
    prohibition ever moves out of it, this test should fail rather than the two files
    silently agreeing on the wrong thing."""
    schema = _read("cycle-backlog.md")

    assert "forbidden" in schema
    # `|` binds loosest in a regex, so this pattern used to read as
    # `(triaged → planned.*forbidden)` OR the bare literal `forbidden` — and the line
    # above already asserts that literal is present. The second assert could not fail
    # while the first passed: it asserted nothing the first had not. Grouped, and
    # `[^\n]*` rather than `.*` so the two halves must be on ONE line, which is what
    # "the prohibition is stated here" means.
    assert re.search(r"triaged\s*(→|->)\s*planned[^\n]*forbidden", schema), (
        "`cycle-backlog.md` no longer states the `triaged → planned` prohibition on one "
        "line; the two files may now silently agree on the wrong thing")


def test_every_status_the_rules_name_is_one_the_mechanism_accepts() -> None:
    """A prose status the mechanism refuses is a chain nobody can walk."""
    import sys
    sys.path.insert(0, str(_RULES.parent / "mechanisms" / "cycle"))
    from backlog_status import LEGAL_STATUS

    named = set()
    for rule in ("cycle-backlog.md", "cycle-maintenance.md"):
        named |= {m.group(1) for m in
                  re.finditer(r"status\s+([a-z]+)\s*(?:→|->)", _read(rule))}

    assert named, "no status transition found in either rule"
    assert named <= set(LEGAL_STATUS), named - set(LEGAL_STATUS)
