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
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# The kit ships as loose scripts, so `squad` resolves only after sys.path is extended.
for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        sys.path.insert(0, str(_up))
        break

from squad.paths import rules_dir  # noqa: E402 — post-bootstrap import


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


#: The fallback set, used when the rule file cannot be read. It is the file's own
#: `retained_classes` line, copied — and that copy is exactly why the reader below
#: exists: the file declared `delegated_classes`, `retained_classes`, `on_no_match` and
#: `require_rationale` in the `rules/*.txt` layer `install.sh` preserves as the
#: CONSUMER's configuration, and nothing parsed any of them. A project that widened
#: what it delegates edited a file no code read, and the hardcoded set below answered
#: instead — silently, which is the shape a configuration knob must never have.
_RETAINED_FALLBACK = frozenset({
    DecisionClass.ACCESS,
    DecisionClass.ELAPSED,
    DecisionClass.LIVENESS,
    DecisionClass.GOVERNANCE,
})


def _configured_retained(project_root: Path | None = None) -> frozenset[DecisionClass]:
    """`retained_classes` as the project declares it, or the fallback above.

    Unknown names in the file are IGNORED rather than refused: this is a consumer's
    config, and a typo there must not stop a cycle. What it must not do is silently
    widen what gets delegated, which is why an unreadable file falls back to the
    stricter set rather than to an empty one.
    """
    root = Path(project_root) if project_root else Path.cwd()
    directory = rules_dir(root)
    path = (directory / "decision-delegation.txt") if directory else None
    if path is None or not path.is_file():
        return _RETAINED_FALLBACK
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return _RETAINED_FALLBACK
    by_value = {c.value: c for c in DecisionClass}
    for line in text.splitlines():
        key, _, value = line.partition("=")
        if key.strip() != "retained_classes":
            continue
        named = {by_value[n.strip()] for n in value.split(",")
                 if n.strip() in by_value}
        return frozenset(named) if named else _RETAINED_FALLBACK
    return _RETAINED_FALLBACK


_RETAINED = _configured_retained()


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
#: EVERY pattern carries both languages. The table was written from one consumer's
#: registry and was almost entirely Portuguese: of fifteen delegable patterns exactly
#: one could match English, and of eleven impediment patterns two. A classifier that
#: cannot read the consumer's prose answers `retain` for every wall, which is the
#: silent-default failure — the walls stay up and nothing says the reason is language.
#: The kit is open source and its registries are written in whichever language the
#: project uses, so the English half is not a translation courtesy; it is the half that
#: makes the mechanism work anywhere but here.
_IMPEDIMENT_PATTERNS: list[tuple[DecisionClass, str]] = [
    (DecisionClass.GOVERNANCE, r"loop\s+aut[ôo]nomo[^.]{0,80}bypass"),
    (DecisionClass.GOVERNANCE, r"autonomous\s+loop[^.]{0,80}bypass"),
    (DecisionClass.GOVERNANCE, r"bypass\s+que\s+a\s+governan[çc]a"),
    (DecisionClass.GOVERNANCE, r"bypass(es)?\s+(the\s+)?governance"),
    (DecisionClass.ACCESS, r"provisionamento\s+de\s+/|provisionar\s+/"),
    (DecisionClass.ACCESS, r"provisioning\s+of\s+/|provision\s+the\s+(host|machine|server)"),
    (DecisionClass.ACCESS, r"unit\s+files\s+systemd|instala[çc][ãa]o\s+de\s+unit\s+files"),
    (DecisionClass.ACCESS, r"systemd\s+unit\s+files?|installing\s+unit\s+files?"),
    (DecisionClass.ACCESS, r"n[ãa]o\s+[ée]\s+trabalho\s+de\s+c[óo]digo"),
    (DecisionClass.ACCESS, r"not\s+(a\s+)?code\s+work|is\s+not\s+code\s+work"),
    (DecisionClass.ACCESS, r"sibling\s+repo|cross-repo\s+work\s+fora\s+do\s+escopo"),
    (DecisionClass.ACCESS, r"cross-repo\s+work\s+out(side)?\s+of\s+scope"),
    (DecisionClass.ACCESS, r"(no|missing|lacks?)\s+(ssh\s+)?(access|credential|permission)s?\b"),
    (DecisionClass.ELAPSED, r"acumula[çc][ãa]o\s+de\s+~?\d+\s+dias"),
    (DecisionClass.ELAPSED, r"~?\d+\s+days?\s+of\s+accumulation"),
    (DecisionClass.ELAPSED, r"~?\d+\s+dias\s+de\s+s[ée]rie"),
    (DecisionClass.ELAPSED, r"~?\d+\s+days?\s+of\s+(series|history|data)"),
    (DecisionClass.ELAPSED, r"needs?\s+~?\d+\s+(more\s+)?days?\s+to\s+elapse"),
    (DecisionClass.LIVENESS, r"sess[ãa]o\s+LIVE"),
    (DecisionClass.LIVENESS, r"\bLIVE\s+session\b"),
    (DecisionClass.LIVENESS, r"exige\s+o\s+plano\s+de\s+build\s+de\s+p[ée]"),
    (DecisionClass.LIVENESS, r"requires?\s+(a\s+)?(running|standing)\s+(build|system|service)"),
    (DecisionClass.LIVENESS, r"n[ãa]o\s+[ée]\s+verific[áa]vel\s+desta\s+sess[ãa]o"),
    (DecisionClass.LIVENESS, r"not\s+verifiable\s+from\s+this\s+session"),
]

#: Delegable walls must state the alternatives. "Aguardando decisão" alone is not
#: enough — a decision whose options are not written down is not a choice this
#: mechanism can make, it is research it would have to invent.
_DELEGABLE_PATTERNS: list[tuple[DecisionClass, str]] = [
    (DecisionClass.BINARY, r"decis[ãa]o\s+bin[áa]ria"),
    (DecisionClass.BINARY, r"binary\s+(decision|choice)"),
    (DecisionClass.STATUS, r"disposi[çc][ãa]o\s+de\s+status"),
    (DecisionClass.STATUS, r"status\s+disposition"),
    (DecisionClass.STATUS, r"nenhuma\s+transi[çc][ãa]o\s+can[ôo]nica"),  # english-only: the pattern matches Portuguese registry prose
    (DecisionClass.SCOPE, r"decis[ãa]o\s+de\s+escopo"),
    (DecisionClass.SCOPE, r"scope\s+(decision|call)"),
    (DecisionClass.THRESHOLD, r"decis[ãa]o\s+de\s+piso"),
    (DecisionClass.THRESHOLD, r"(threshold|floor)\s+decision"),
    (DecisionClass.OPTION, r"\bOU\b.{0,200}\bSe\s+(retire|manter)\b"),
    (DecisionClass.OPTION, r"\bEITHER\b.{0,200}\bOR\b"),
    #: A choice whose sides are both written down. "decisão entre X ou Y" is
    #: choosable; "aguardando decisão" alone is not, because the alternatives
    #: would have to be invented before one could be picked.
    (DecisionClass.OPTION, r"decis[ãa]o\s+entre\s+.{0,120}\bou\b"),
    (DecisionClass.OPTION, r"(decision|choice)\s+between\s+.{0,120}\bor\b"),
    (DecisionClass.OPTION, r"\b(duas|tr[êe]s|quatro)\s+op[çc][õo]es\b"),
    (DecisionClass.OPTION, r"\b(two|three|four)\s+options\b"),
    #: The sponsor named himself the decider and then delegated the seat. Both
    #: halves are required: without the delegation file this pattern must not
    #: exist, which is why it cites the rule rather than standing alone.
    (DecisionClass.SPONSOR, r"decis[ãa]o\s+de\s+sponsor"),
    (DecisionClass.SPONSOR, r"sponsor\s+decision"),
    (DecisionClass.SPONSOR, r"[ée]\s+decis[ãa]o\s+do\s+sponsor"),
    (DecisionClass.SPONSOR, r"is\s+(the\s+)?sponsor's\s+(decision|call)"),
    #: Not a decision in the first place — a measurement somebody has to take,
    #: and taking measurements is what the fleet is for.
    (DecisionClass.MEASUREMENT, r"re-?medi[çc][ãa]o|re-?medir"),
    (DecisionClass.MEASUREMENT, r"re-?measure(ment)?\b"),
    (DecisionClass.MEASUREMENT, r"confirma[çc][ãa]o\s+de\s+que"),
    (DecisionClass.MEASUREMENT, r"confirmation\s+that\b"),
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
        line += f" Supersedes obligation: {_clipped(supersedes, SUPERSEDES_CHARS)}."
    return line + f" Prior wall: {_clipped(wall, PRIOR_WALL_CHARS)}"


#: How much of each quoted string reaches the record. Named, because they were two
#: bare literals — 200 and 160 — inside an f-string, so a reader could not tell whether
#: they were chosen or typed, and neither could be cited in an argument about whether
#: they are right.
SUPERSEDES_CHARS = 200
PRIOR_WALL_CHARS = 160


def _clipped(text: str, limit: int) -> str:
    """`text` cut to `limit`, SAYING SO when it was cut.

    Both quotes used to be truncated silently. The record is the audit trail for a
    decision the system made on the sponsor's behalf, and a wall quoted as
    "the sponsor must confirm the migration window before we" reads as a sentence
    somebody wrote — not as one this function cut in half. A reader reconstructing
    the decision had no way to tell the two apart.
    """
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit].rstrip()}… [quoted to {limit} chars]"


def is_retained(klass: DecisionClass) -> bool:
    """Does this class stay walled no matter who delegates what?"""
    return klass in _RETAINED
