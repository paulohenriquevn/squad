"""B-108 — a review record that does not say what it covered cannot be checked afterwards.

MEASURED, which is why this exists. Across one consumer's knowledge-base:

    review files declaring a reviewed range   2 of 48
    audit files mentioning a scope            3 of 16

The `release` half of the same gap WAS derivable — the commit graph knows which tag contains which
commit, and 41 of 41 items resolved. Nothing equivalent exists for a review: its findings are
judgments made in a session, and if the file does not name the items or the range it read, no query
recovers it later.

So this closes the door going forward rather than retrofitting the past. Guessing what 46 old
records covered would fabricate the very coverage the check exists to make checkable.

This is B-084's defect one level up. That item closed "a gate that inspected zero and a gate that
inspected everything emit the same verdict"; B-102 added "…and it does not say what it skipped".
Here: **a review that covered seven items and one that covered a single item are indistinguishable
from the file.**
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from check_record_scope import ScopeVerdict, check_record  # noqa: E402


def _write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def test_a_record_naming_its_items_is_accepted(tmp_path: Path) -> None:
    p = _write(tmp_path, "b143-findings.yml", "review_target:\n  items: [B-074, B-083]\n")
    r = check_record(p)
    assert r.verdict is ScopeVerdict.DECLARED
    assert r.items == ["B-074", "B-083"]


def test_a_single_item_named_as_a_scalar_is_accepted(tmp_path: Path) -> None:
    """`item: B-107` is the shape a one-item review naturally takes; refusing it would push
    authors toward a list of one, which is ceremony rather than clarity."""
    p = _write(tmp_path, "b107-findings.yml", "review_target:\n  item: B-107\n")
    assert check_record(p).items == ["B-107"]


def test_a_record_with_no_item_declaration_is_refused(tmp_path: Path) -> None:
    p = _write(tmp_path, "some-findings.yml", "findings:\n  - id: R-1\n    severity: LOW\n")
    r = check_record(p)
    assert r.verdict is ScopeVerdict.UNDECLARED
    assert "does not say which items" in r.reason


def test_the_filename_alone_does_NOT_satisfy_it(tmp_path: Path) -> None:
    """The strongest temptation, and the one that would quietly re-open the hole.

    `b086-findings.yml` looks like it declares B-086, and a slice review covering seven items would
    look exactly the same. Inferring scope from a filename is how a record that covered one item
    gets read as covering the slice it was named after.
    """
    p = _write(tmp_path, "b086-findings.yml", "findings: []\n")
    assert check_record(p).verdict is ScopeVerdict.UNDECLARED


def test_a_declared_range_is_reported_but_does_not_replace_the_items(tmp_path: Path) -> None:
    """A range says what was READ; the item list says what it was read FOR. Both, or neither is
    enough — a diff range cannot be turned back into item ids without the commit convention that
    B-108 measured is only followed sometimes."""
    p = _write(
        tmp_path,
        "b143-findings.yml",
        "review_target:\n  items: [B-074]\n  head_reviewed: adf4cbf\n  diff_baseline: origin/develop\n",
    )
    r = check_record(p)
    assert r.verdict is ScopeVerdict.DECLARED
    assert r.head == "adf4cbf"


def test_malformed_yaml_is_refused_loudly_not_treated_as_empty(tmp_path: Path) -> None:
    """An unparseable record must not read as 'declared nothing' — that is the swallow this
    ecosystem keeps finding. It is its own verdict."""
    p = _write(tmp_path, "broken-findings.yml", "review_target:\n  items: [B-074\n")
    r = check_record(p)
    assert r.verdict is ScopeVerdict.UNREADABLE
    assert "parse" in r.reason.lower()


def test_a_markdown_record_declaring_items_in_frontmatter_is_accepted(tmp_path: Path) -> None:
    """Consolidated reports are markdown; the same rule has to reach them or half the records
    escape it."""
    p = _write(
        tmp_path,
        "b143-review-2026-08-20.md",
        "---\nitems: [B-074, B-058]\n---\n\n# Review\n\n**Verdict:** READY_TO_MERGE\n",
    )
    r = check_record(p)
    assert r.verdict is ScopeVerdict.DECLARED
    assert r.items == ["B-074", "B-058"]


def test_a_B_NNN_MENTIONED_IN_PROSE_is_not_a_declaration(tmp_path: Path) -> None:
    """Added because mutation testing found this hole in the tests above, not in the code.

    Replacing the declaration lookup with `findall(str(scope))` — infer an item from any B-NNN
    anywhere in the record — passed all seven earlier tests. None of them contained a B-NNN outside
    the declaration, so none could tell the two apart.

    That matters because review records are FULL of prose references: "same family as B-084",
    "supersedes B-050", "related: B-105". A checker that counted those would report a record as
    covering items it merely mentioned — the precise misreading B-108 exists to prevent, arriving
    through the checker built to prevent it.
    """
    p = _write(
        tmp_path,
        "some-findings.yml",
        "findings:\n"
        "  - id: R-1\n"
        "    summary: same family as B-084, and supersedes B-050\n",
    )
    r = check_record(p)
    assert r.verdict is ScopeVerdict.UNDECLARED
    assert r.items == []
