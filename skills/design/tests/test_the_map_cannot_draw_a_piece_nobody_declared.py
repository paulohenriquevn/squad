"""Coverage ran one way: every piece must appear in the map, and the map was never read back.

`check_design_completeness` computes `uncovered` as *pieces declared and absent from the
map*, and reports each one — a responsibility with a boundary that the system as drawn has
no place for. That direction is right and carefully done: `_mentions` matches a WHOLE id
because `"PIECE-1" in body` is a substring test and `PIECE-1` is a substring of `PIECE-10`,
measured on a product with eleven pieces.

The opposite direction is not computed at all. A map naming `PIECE-99` that
`technical-pieces.md` never declared passes in silence, and the two readings mean different
things: a piece missing from the map is work the drawing forgot; **a piece in the map that
nobody declared is the map drawing something no one decided** — or a `technical-pieces.md`
that lost an entry. `cycle-design` exists to settle the shape before any item is filed
against it, and both answers are worth having then.

Third instance of one class found on 2026-09-22 — an identifier counted rather than
resolved. The first was the Coverage Matrix counting a row without opening the task it
named; the second was a review finding carrying a path nobody opened.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from check_design_completeness import check  # noqa: E402

_MERMAID = "```mermaid\nflowchart TD\n  A --> B\n  B --> C\n  C --> D\n  D --> E\n```\n"


def _project(tmp_path: Path, *, pieces: str, map_extra: str) -> Path:
    root = tmp_path / "p"
    product = root / ".squad" / "wiki" / "product"
    design = root / ".squad" / "wiki" / "design"
    product.mkdir(parents=True)
    design.mkdir(parents=True)
    (product / "technical-pieces.md").write_text(pieces, encoding="utf-8")
    filler = "\n".join(f"A sentence about the drawing, number {i}." for i in range(8))
    for name in ("states.md", "trust.md", "sequence.md", "durability.md"):
        (design / name).write_text(f"# {name}\n\n{filler}\n\n{_MERMAID}", encoding="utf-8")
    (design / "system-map.md").write_text(
        f"# Map\n\n{filler}\n\n{map_extra}\n\n{_MERMAID}", encoding="utf-8")
    return root


ONE_PIECE = "# Pieces\n\n## PIECE-1 — The only piece\n\nA responsibility with a boundary.\n"


def _codes(root: Path) -> list[str]:
    return [f.code for f in check(root).findings]


def test_a_piece_in_the_map_that_nobody_declared_is_reported(tmp_path: Path) -> None:
    root = _project(tmp_path, pieces=ONE_PIECE, map_extra="PIECE-1 and PIECE-99 both live here.")

    codes = _codes(root)

    assert "piece_not_declared" in codes, (
        "the map named a piece technical-pieces.md never declared and nothing said so"
    )


def test_a_map_naming_only_declared_pieces_is_silent(tmp_path: Path) -> None:
    """THE CONTROL. A check that fires on the conforming case reports nothing."""
    root = _project(tmp_path, pieces=ONE_PIECE, map_extra="PIECE-1 lives here.")

    assert "piece_not_declared" not in _codes(root)


def test_the_two_directions_keep_their_own_codes(tmp_path: Path) -> None:
    """A piece missing from the map and a piece missing from the list are different
    findings, and one number out of two questions is the defect this class is about."""
    pieces = ONE_PIECE + "\n## PIECE-2 — Forgotten by the map\n\nAnother one.\n"
    root = _project(tmp_path, pieces=pieces, map_extra="PIECE-1 and PIECE-99 live here.")

    codes = _codes(root)

    assert "piece_not_in_map" in codes, "PIECE-2 is declared and absent from the map"
    assert "piece_not_declared" in codes, "PIECE-99 is in the map and declared nowhere"


def test_the_id_is_matched_whole_in_this_direction_too(tmp_path: Path) -> None:
    """`PIECE-1` is a substring of `PIECE-10`, and the existing direction already says so.

    A map naming `PIECE-10` against a list declaring only `PIECE-1` must report — the
    substring test that would call it covered is the exact defect `_mentions` was written
    to avoid, pointing the other way.
    """
    root = _project(tmp_path, pieces=ONE_PIECE, map_extra="PIECE-10 is drawn here.")

    assert "piece_not_declared" in _codes(root)


def test_an_unreadable_piece_list_does_not_invent_the_finding(tmp_path: Path) -> None:
    """With no `technical-pieces.md`, coverage was NOT checked — in both directions.

    The existing code already says that about its own direction; reporting every id in
    the map as undeclared would turn an inability to measure into a measurement.
    """
    root = _project(tmp_path, pieces=ONE_PIECE, map_extra="PIECE-99 is here.")
    (root / ".squad" / "wiki" / "product" / "technical-pieces.md").unlink()

    codes = _codes(root)

    assert "piece_not_declared" not in codes
    assert "pieces_unreadable" in codes
