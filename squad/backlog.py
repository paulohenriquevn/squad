"""What an item block in `BACKLOG.md` IS — parsed one way, by every reader.

WHY THIS EXISTS
===============
Six modules read the `## B-NNN — Title` header and they did not agree. Measured
2026-09-20 on `## B-003 - Title`, written with a plain hyphen:

    check_backlog_structure.BLOCK_RE   (the canonical one)   did NOT see it
    backlog_status.BLOCK_HEADER_RE     (the WRITER)          did NOT see it
    detect_domains, phase_coverage                           did NOT see it
    build_approval_brief.ITEM_HEAD_RE                        saw it
    check_objective_coverage.ITEM_RE                         saw it
    apply_delegated_decisions.ITEM_RE                        saw it

An item could therefore enter the approval brief, be ticked and signed, and be
invisible to the only module allowed to write its status.

THE DAMAGE COMPOUNDS, WHICH IS WHY THE PARSER IS WIDE
=====================================================
A header the parser does not recognise does not OPEN a block, so the unseen item's
fields are read as the PREVIOUS item's. Measured with two items, the second written
with a hyphen:

    Items   : 1                                  (there are two)
    [BLOCKER] B-001 duplicate_field: `status` is declared 2 times
    [BLOCKER] B-001 self_block: `B-001` names itself in `blocked_by`
    [BLOCKER] B-001 blocker_cycle: B-001 -> B-001

Three blockers, all false, all on the wrong item, and one real item gone from the
count. That is the rule this module follows everywhere: **see the block, then judge
it**. A malformed item reported is a person's five minutes; a malformed item skipped
is three false findings on its neighbour.

`check_intake_gates.py` reached the same conclusion first and imports rather than
compiles: *"A second regex here would diverge silently, and the two would disagree
about what the registry contains."*
"""
from __future__ import annotations

import re

#: The separators a header may use. The schema in `rules/cycle-backlog.md` writes an
#: em dash; a keyboard offers a hyphen and an editor substitutes an en dash, and all
#: three name the same item. Accepting them is not laxity — the alternative was a
#: block that half the kit could see.
SEPARATORS = "—–-"

#: `## B-NNN — Title  [ ]` — the optional trailing checkbox is the approval marker
#: some registries carry. Groups: id, title, checkbox state.
#:
#: Deliberately `\d+` and not `\d{3,}`: an id of one or two digits is malformed, and
#: malformed is a thing to REPORT (`is_well_formed_id`), never a thing to skip. A
#: skipped header takes the next item's fields with it.
BLOCK_RE = re.compile(
    rf"^##\s+(B-\d+)\s*[{SEPARATORS}]\s*(.+?)\s*(?:\[( |x|X)\])?\s*$", re.MULTILINE)

#: An id standing alone, as a CLI argument or a table cell.
ITEM_ID_RE = re.compile(r"\AB-\d{3,}\Z")

#: An id mentioned inside prose — a `blocked_by` value, a slug, a report body.
#:
#: Three digits minimum, and that is a different rule from the header's on purpose:
#: `\bB-\d+\b` over free prose would turn "annex B-1" into a dependency edge. The
#: header is anchored to `^##` and can afford to be wide; a mention in a sentence
#: cannot.
ID_IN_TEXT_RE = re.compile(r"\bB-\d{3,}\b")

#: The width every registry in this ecosystem actually uses, and the one the
#: reference patterns require. An id below it parses as a block and is unreachable
#: from every citation — `blocked_by: B-15` names nothing, and the writer refuses
#: `B-15` on the command line while the block sits in the file.
MIN_ID_DIGITS = 3


def is_well_formed_id(item_id: str) -> bool:
    """Can every part of the kit reach this id?

    False for `B-15`: the block parses, and `ITEM_ID_RE` and `ID_IN_TEXT_RE` do not
    match it, so the item exists and nothing can cite it or move it.
    """
    return bool(ITEM_ID_RE.match(item_id))


def block_spans(content: str) -> dict[str, tuple[int, int]]:
    """Every item id mapped to the `[start, end)` span of its block body."""
    spans: dict[str, tuple[int, int]] = {}
    matches = list(BLOCK_RE.finditer(content))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        spans[match.group(1)] = (match.end(), end)
    return spans


#: Where one block ends and the next begins, for readers that slice the file into
#: strings rather than walking spans. Separate from `BLOCK_RE` because it answers a
#: narrower question — "does a block start here?" — and must therefore stay as wide as
#: the header pattern: a split that missed a header would glue two items into one
#: string, which is the same fields-leak-into-the-neighbour failure one layer up.
BLOCK_SPLIT_RE = re.compile(r"\n(?=##\s+B-\d+)")
