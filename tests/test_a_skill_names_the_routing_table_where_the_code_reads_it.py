"""A skill that names the routing table must name where `route_domain.py` looks.

The table moved out of `rules/cycle-backlog.md` on 2026-09-11 and the prose did not follow,
three times in the same kit:

1. `route_domain.py`'s own docstring named the legacy location alone — it records this in
   the paragraph that now lists all five.
2. `skills/backlog-init/SKILL.md` prescribed writing the table into `BACKLOG.md`; that skill
   now warns about it by name.
3. `skills/backlog-item/SKILL.md` said the table "is parsed from `rules/cycle-backlog.md`,
   so there is one table and one truth" until 2026-09-23 (#172) — false twice over: five
   locations, and that one is read LAST.

Prose cannot be kept in step by remembering. This reads `_TABLE_LOCATIONS` from the source
and fails when a document teaches a location the resolver does not read first, which is the
failure that matters: a table written to a shadowed location works until someone adds a file
ahead of it, and then stops without anything saying why.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_RESOLVER = _ROOT / "mechanisms" / "cycle" / "route_domain.py"
#: Every document that tells a reader where the routing table lives.
_SPEAKERS = ("skills/backlog-item/SKILL.md", "skills/backlog-init/SKILL.md")


def _locations() -> list[str]:
    """The resolution order, read from the tuple the resolver actually uses."""
    src = _RESOLVER.read_text(encoding="utf-8")
    block = re.search(r"_TABLE_LOCATIONS = \((.*?)\n\)", src, re.S)
    assert block, "_TABLE_LOCATIONS not found; this test lost its subject"
    rows = re.findall(r"\(([^)]+)\)", block.group(1))
    assert rows, "the tuple parsed to nothing; this test lost its subject"
    return rows


def test_the_resolver_reads_more_than_one_location() -> None:
    """The premise of the claim this closes: 'one table and one truth' was never true."""
    assert len(_locations()) > 1, _locations()


def test_no_skill_calls_the_legacy_location_the_source() -> None:
    """`cycle-backlog.md` is the LAST fallback. A document calling it THE table misdirects.

    Matching is on the claim's shape rather than its wording — `parsed from`, `read from`,
    `lives in` followed by the legacy filename within the same sentence — so a rephrasing
    that keeps the error still fails.
    """
    claim = re.compile(
        r"(?:table is (?:parsed|read) from|table lives in|reads the table from)[^.\n]{0,80}"
        r"cycle-backlog\.md", re.I)

    offenders = []
    for rel in _SPEAKERS:
        text = (_ROOT / rel).read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            if claim.search(line):
                offenders.append(f"{rel}:{line_no}")
    assert offenders == [], (
        "these name the LAST fallback as the source of the routing table: "
        f"{offenders}. `route_domain.py` reads {len(_locations())} locations in order.")


def test_no_skill_claims_a_single_location() -> None:
    """The second half of #172: 'one table and one truth' asserts what the code denies."""
    single = re.compile(r"one table and one truth|only place the table|the single routing table", re.I)
    offenders = [f"{rel}:{n}" for rel in _SPEAKERS
                 for n, line in enumerate((_ROOT / rel).read_text(encoding="utf-8").splitlines(), 1)
                 if single.search(line)]
    assert offenders == [], (
        f"these claim one location while the resolver reads {len(_locations())}: {offenders}")


def test_a_skill_that_names_the_winning_location_names_the_right_one() -> None:
    """The positive half: the FIRST location must appear in whatever a skill does say.

    Without this, the two tests above pass by a document saying nothing at all — the
    failure mode of asserting only that a false claim disappeared.
    """
    first = _locations()[0]
    assert "ROUTING_TABLE" in first, first
    for rel in _SPEAKERS:
        text = (_ROOT / rel).read_text(encoding="utf-8")
        assert "domain-routing.txt" in text, (
            f"{rel} names no routing-table location at all; a reader learns nothing")
