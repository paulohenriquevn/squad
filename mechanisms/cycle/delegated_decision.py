#!/usr/bin/env python3
"""The line between a decision a sponsor can delegate and an impediment nobody can.

`select_backlog_item.py` reports AWAITING_HUMAN for any item whose `blocked_by`
names no other item. That single verdict covers two different situations, and
treating them alike is what leaves a backlog walled: one is a choice waiting for
authority, the other is a machine, a data series, or a running system that is
absent. Authority moves the first and does nothing to the second.

This module decides which is which, and REFUSES when it cannot tell. The refusal
is the point. Its predecessor matched the substring "config" inside an item that
asks an operator to provision `/opt/theo` and install systemd units, called it
resolvable, and reported 42.9% autonomy — a number that measured nothing but its
own matcher. An item wrongly cleared is handed to a lane that cannot do it, and
the lane then fabricates the work or stalls.

See `rules/decision-delegation.txt` for what the sponsor delegated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class DecisionClass(Enum):
    """What kind of wall this is."""

    # Retained — delegation does not move these.
    ACCESS = "access"          # a machine, credential or repo the process lacks
    ELAPSED = "elapsed"        # time must pass: a series, a soak, a deadline
    LIVENESS = "liveness"      # a system must be standing, and is not
    GOVERNANCE = "governance"  # the item names autonomy itself as the bypass

    # Delegated — the sponsor handed these over.
    SCOPE = "scope"
    STATUS = "status"
    THRESHOLD = "threshold"
    BINARY = "binary"
    OPTION = "option"
    SPONSOR = "sponsor"          # the item names the sponsor as decider
    MEASUREMENT = "measurement"  # not a decision at all: work the system can do

    # Neither — the fail-safe.
    UNCLASSIFIED = "unclassified"


_RETAINED = {
    DecisionClass.ACCESS,
    DecisionClass.ELAPSED,
    DecisionClass.LIVENESS,
    DecisionClass.GOVERNANCE,
}


@dataclass(frozen=True)
class WallVerdict:
    """What a `blocked_by` string turned out to be."""

    klass: DecisionClass
    delegated: bool
    evidence: str  # the phrase that decided it, so the reader can disagree


#: Impediments are matched FIRST and win outright. A wall that is both a choice
#: and an impediment is an impediment: the choice can be made and the item still
#: cannot move. Reading the delegable half first is precisely how the previous
#: mechanism cleared B-139, whose prose says "não é trabalho de código" in the  # english-only: verbatim quotation from item B-139
#: same breath as naming a migration.
_IMPEDIMENT_PATTERNS: list[tuple[DecisionClass, str]] = [
    (DecisionClass.GOVERNANCE, r"loop\s+aut[ôo]nomo[^.]{0,80}bypass"),
    (DecisionClass.GOVERNANCE, r"bypass\s+que\s+a\s+governan[çc]a"),
    (DecisionClass.ACCESS, r"provisionamento\s+de\s+/|provisionar\s+/"),
    (DecisionClass.ACCESS, r"unit\s+files\s+systemd|instala[çc][ãa]o\s+de\s+unit\s+files"),
    (DecisionClass.ACCESS, r"n[ãa]o\s+[ée]\s+trabalho\s+de\s+c[óo]digo"),
    (DecisionClass.ACCESS, r"sibling\s+repo|cross-repo\s+work\s+fora\s+do\s+escopo"),
    (DecisionClass.ELAPSED, r"acumula[çc][ãa]o\s+de\s+~?\d+\s+dias"),
    (DecisionClass.ELAPSED, r"~?\d+\s+dias\s+de\s+s[ée]rie"),
    (DecisionClass.LIVENESS, r"sess[ãa]o\s+LIVE"),
    (DecisionClass.LIVENESS, r"exige\s+o\s+plano\s+de\s+build\s+de\s+p[ée]"),
    (DecisionClass.LIVENESS, r"n[ãa]o\s+[ée]\s+verific[áa]vel\s+desta\s+sess[ãa]o"),
]

#: Delegable walls must state the alternatives. "Aguardando decisão" alone is not
#: enough — a decision whose options are not written down is not a choice this
#: mechanism can make, it is research it would have to invent.
_DELEGABLE_PATTERNS: list[tuple[DecisionClass, str]] = [
    (DecisionClass.BINARY, r"decis[ãa]o\s+bin[áa]ria"),
    (DecisionClass.STATUS, r"disposi[çc][ãa]o\s+de\s+status"),
    (DecisionClass.STATUS, r"nenhuma\s+transi[çc][ãa]o\s+can[ôo]nica"),  # english-only: the pattern matches Portuguese registry prose
    (DecisionClass.SCOPE, r"decis[ãa]o\s+de\s+escopo"),
    (DecisionClass.THRESHOLD, r"decis[ãa]o\s+de\s+piso"),
    (DecisionClass.OPTION, r"\bOU\b.{0,200}\bSe\s+(retire|manter)\b"),
    #: A choice whose sides are both written down. "decisão entre X ou Y" is
    #: choosable; "aguardando decisão" alone is not, because the alternatives
    #: would have to be invented before one could be picked.
    (DecisionClass.OPTION, r"decis[ãa]o\s+entre\s+.{0,120}\bou\b"),
    (DecisionClass.OPTION, r"\b(duas|tr[êe]s|quatro)\s+op[çc][õo]es\b"),
    #: The sponsor named himself the decider and then delegated the seat. Both
    #: halves are required: without the delegation file this pattern must not
    #: exist, which is why it cites the rule rather than standing alone.
    (DecisionClass.SPONSOR, r"decis[ãa]o\s+de\s+sponsor"),
    (DecisionClass.SPONSOR, r"sponsor\s+decision"),
    (DecisionClass.SPONSOR, r"[ée]\s+decis[ãa]o\s+do\s+sponsor"),
    #: Not a decision in the first place — a measurement somebody has to take,
    #: and taking measurements is what the fleet is for.
    (DecisionClass.MEASUREMENT, r"re-?medi[çc][ãa]o|re-?medir"),
    (DecisionClass.MEASUREMENT, r"confirma[çc][ãa]o\s+de\s+que"),
]


def classify_wall(wall: str) -> WallVerdict:
    """Decide whether this `blocked_by` prose is delegable.

    Impediments are tested first and win. Anything unmatched is retained: no
    match is not consent.
    """
    if not wall or not wall.strip():
        return WallVerdict(DecisionClass.UNCLASSIFIED, False, "empty wall")

    for klass, pattern in _IMPEDIMENT_PATTERNS:
        found = re.search(pattern, wall, re.IGNORECASE)
        if found:
            return WallVerdict(klass, False, found.group(0))

    for klass, pattern in _DELEGABLE_PATTERNS:
        found = re.search(pattern, wall, re.IGNORECASE | re.DOTALL)
        if found:
            return WallVerdict(klass, True, found.group(0))

    return WallVerdict(DecisionClass.UNCLASSIFIED, False, "no pattern matched")


#: Classes that change what SUCCESS MEANS rather than how it is reached. A `scope`
#: decision narrows the obligation; a `threshold` decision moves the bar. Both can turn
#: a failure into a pass without anything failing — and neither is refused, because both
#: are legitimately delegated. What is refused is doing it silently.
REDEFINES_SUCCESS = frozenset({DecisionClass.SCOPE, DecisionClass.THRESHOLD})


def rewrite_wall(*, wall: str, decision: str, rationale: str,
                 klass: DecisionClass | None = None,
                 supersedes: str = "") -> str:
    """Replace a wall with the decision that retired it.

    Never returns a `blocked_by` line, and never returns nothing: an item whose
    wall was deleted with no decision in its place is indistinguishable from an
    item nobody ever walled, and the next reader has no way to learn a choice was
    made or on what evidence.

    WHY `supersedes` IS REQUIRED FOR SCOPE AND THRESHOLD
    ---------------------------------------------------
    An external reviewer put the sequence plainly: fail a requirement, delegate the
    requirement away or lower its target, approve everything that remains, declare
    success. Every step is individually legitimate and the result is a pass nothing
    earned.

    The rationale requirement did not stop it — a rationale is a sentence, and the
    sentence can be true. What stops it is refusing to let the ORIGINAL obligation
    disappear: a narrowing decision must name what it narrowed, so the next reader sees
    an obligation that was moved rather than an obligation that was never there.

    This does not decide whether the narrowing was right. It makes the narrowing
    legible, which is the difference between a scope call and a quiet retreat.
    """
    if not decision.strip():
        raise ValueError("a delegated decision must state what was decided")
    if not rationale.strip():
        raise ValueError(
            "a delegated decision must carry its rationale — a wall removed with "
            "no reasoning in its place reads as a wall never written"
        )
    if klass in REDEFINES_SUCCESS and not supersedes.strip():
        raise ValueError(
            f"a `{klass.value}` decision changes what success means, so it must name "
            "the obligation it supersedes. Without that, a failed requirement can be "
            "narrowed away and the remaining criteria approved, and the record shows a "
            "pass with nothing marking what stopped being required"
        )
    line = (
        f"decided_by: system under sponsor delegation "
        f"(rules/decision-delegation.txt) — {decision.strip()}. "
        f"Rationale: {rationale.strip()}."
    )
    if supersedes.strip():
        line += f" Supersedes obligation: {supersedes.strip()[:200]}."
    return line + f" Prior wall: {wall.strip()[:160]}"


def is_retained(klass: DecisionClass) -> bool:
    """Does this class stay walled no matter who delegates what?"""
    return klass in _RETAINED
