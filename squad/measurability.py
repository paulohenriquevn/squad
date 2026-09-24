"""What counts as measurable — one definition, for every reader of that question.

`plan-alignment` scores requirements and `plan-confidence` scores acceptance criteria.
Both ask the same thing: does this carry something somebody can fail? They asked it with
two regexes written apart, and by 2026-09-24 those had drifted — `the command exits 0`
was measurable to one and not the other, because one had been widened that week by an
author who did not know the other existed.

The kit states this rule about its own roster: ONE parser, imported by everything that
reads the table, because two readers of one table drift apart silently. This is that.

## Why declaration counts are here, and more units are not

The original vocabulary was latency, throughput and size: `ms`, `rps`, `MB`, `p95`. A
change to a component's public API has no unit in that list. The only reachable form was
therefore a COMPARISON, and the only comparison an author can write before implementing
is a diff budget — a number nobody can know before implementing.

Measured by the session that reported it, over six panel rounds on one brief: three
refusals were about invented line budgets, none about the item, and every refusal in the
set was on a NON-behavioural criterion. No criterion naming observable behaviour — a
named test case, a counted `^ok`, a grep for a declaration — was ever refused. So what
was missing is the vocabulary of declarations and behaviour, not more ways to say fast.

The sharpest evidence that this was a defect and not a limitation: removing the invented
budget LOWERED the brief's score, because what remained (`exactly 1 prop`,
`0 dependencies added`) read as unmeasurable. The scorer penalised the honest requirement
and rewarded the inventable one.

## The property the widening must not destroy

A requirement with no number is still not measurable. `props are documented` names the
same noun as `exactly 1 prop` and states nothing anyone can fail. Every pattern here
requires a NUMBER next to its noun, which is why the count is the pattern's subject and
the noun is its qualifier — not the other way round.
"""
from __future__ import annotations

import re

#: Units of measure. A number and one of these is a claim somebody can check.
_UNITS = (
    r"\b\d+(?:\.\d+)?\s*"
    r"(?:ms|µs|us|ns|s|m|h|%|rps|qps|req/s|fps|px|MB|GB|KB|kb/s"
    r"|LoC|loc|lines?|users?|rows?|items?)\b"
)

#: Percentile names, which carry their own meaning without a unit.
_PERCENTILES = r"\b(?:p50|p95|p99|percentile)\b"

#: A comparison against a number: `<= 20`, `≤ 500`, `> 0`.
_COMPARISON = r"[<>≤≥]=?\s*\d"

#: Exit-code semantics, in the inflection authors actually write.
_EXIT = r"\bexits?\s+(?:code\s+)?[01]\b"

#: A counted DECLARATION or call — the vocabulary a structural change is written in.
#: The NUMBER is required: `2 call sites updated` is a claim, `call sites are updated`
#: is a wish. `no more than`/`at most`/`exactly`/`fewer than` are spelled out because an
#: author writing a bound in words is stating the same bound as `<=`.
_DECLARATIONS = (
    r"\b(?:exactly|at most|at least|no more than|no fewer than|fewer than|more than)?\s*"
    r"\d+\s+(?:new\s+|added\s+|removed\s+|changed\s+|updated\s+)*"
    r"(?:props?|fields?|exports?|imports?|arguments?|parameters?|call\s*sites?"
    r"|cases?|tests?|assertions?|files?|functions?|classes?|methods?|columns?"
    r"|endpoints?|dependenc(?:y|ies)|packages?|modules?)\b"
)

#: A bound written in words against a number and a unit — `no more than 40 added lines`.
#: Separate from `_UNITS` because the words sit BEFORE the number.
_WORDED_BOUND = (
    r"\b(?:at most|at least|no more than|no fewer than|fewer than|more than|exactly|up to)"
    r"\s+\d+\b"
)

PATTERNS: tuple[str, ...] = (
    _UNITS,
    _PERCENTILES,
    _COMPARISON,
    _DECLARATIONS,
    _EXIT,
    _WORDED_BOUND,
)

_COMPILED = tuple(re.compile(p, re.IGNORECASE) for p in PATTERNS)


def is_measurable(text: str) -> bool:
    """Does this text state something a reader could find false?

    False for prose, whatever nouns it uses. The absence of a number is the absence of
    a claim, and no vocabulary added here may change that.
    """
    return any(rx.search(text or "") for rx in _COMPILED)
