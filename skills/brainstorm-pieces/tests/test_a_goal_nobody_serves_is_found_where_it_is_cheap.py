"""The chain was checked forwards and never backwards, so an unserved goal reached DESIGN.

`score_product_alignment` resolves both citations that point UP the chain: a `REQ-N` whose
`serves:` names no declared objective caps under `requirement_serving_no_objective`, and a
`PIECE-N` whose `realises:` names no declared requirement caps under
`piece_realising_no_requirement`. Both are right and both point the same way.

The coverage question — *is every objective served by something?* — is asked nowhere in
this phase. Probed 2026-09-22 with two objectives and one requirement serving only `OBJ-1`:
no cap, no dangling entry, nothing.

IT IS ASKED, EVENTUALLY. `check_objective_coverage` reports an objective no ITEM serves and
exits 1 on it — so the gap is caught, at `/backlog-approve`, after DESIGN drew a system
without `OBJ-2` in it and BACKLOG filed items against that system. The kit's own argument
for `check_merge_autonomy` applies verbatim: *discovering it per-item costs the run, and
announcing it at intake costs one gate.*

This phase is where the four product documents are written and is the last place the answer
is cheap. A goal nothing serves is either a goal nobody meant, or a technical design that
forgot one — and both are answers worth having before a line is drawn.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))

sys.path.insert(0, str(Path(__file__).resolve().parent))

# The fixtures live beside this file and are the SAME ones the sibling test uses. A second
# copy of four product documents here would be a second contract to keep in step, and this
# sweep exists because one contract checked in two places drifts.
from test_score_product_alignment import (  # noqa: E402
    OBJECTIVES, PIECES, TRD, _product, _sign,
)

import score_product_alignment as spa  # noqa: E402


def _caps(root: Path, **overrides: str) -> list[str]:
    product = _product(root, **overrides)
    _sign(product)
    return list(spa.score(root).floor_caps)


def test_an_objective_no_requirement_serves_is_capped(tmp_path: Path) -> None:
    trd = TRD.split("## REQ-2")[0]  # REQ-2 served OBJ-2; drop it

    caps = _caps(tmp_path, **{"trd.md": trd,
                              "technical-pieces.md": PIECES.split("## PIECE-2")[0]})

    assert "objective_served_by_no_requirement" in caps, (
        "OBJ-2 is declared and nothing in the TRD serves it, and the phase that writes "
        "both said nothing"
    )


def test_a_requirement_no_piece_realises_is_capped(tmp_path: Path) -> None:
    """The mirror one rung down: a requirement the design will build nothing for."""
    caps = _caps(tmp_path, **{"technical-pieces.md": PIECES.split("## PIECE-2")[0]})

    assert "requirement_realised_by_no_piece" in caps


def test_a_complete_chain_caps_neither(tmp_path: Path) -> None:
    """THE CONTROL. The fixture serves every objective and realises every requirement."""
    caps = _caps(tmp_path)

    assert "objective_served_by_no_requirement" not in caps
    assert "requirement_realised_by_no_piece" not in caps


def test_a_dangling_citation_leaves_the_goal_unserved_too(tmp_path: Path) -> None:
    """Two findings out of one edit, and the kit already keeps them in different buckets.

    `serves: OBJ-99` is a citation with no referent — a HARD cap,
    `citation_without_referent`, because no edit to the TRD alone can fix it. It also
    leaves `OBJ-2` served by nothing, which is the coverage question and a FLOOR cap.

    Worth pinning together because the names invite confusion:
    `requirement_serving_no_objective` is a requirement with no `serves:` line AT ALL, not
    one whose `serves:` points nowhere. Three distinct states, three distinct reports.
    """
    product = _product(tmp_path, **{"trd.md": TRD.replace("serves: OBJ-2", "serves: OBJ-99")})
    _sign(product)
    rep = spa.score(tmp_path)

    assert "citation_without_referent" in rep.hard_caps, "REQ-2 points at a goal nobody declared"
    assert "objective_served_by_no_requirement" in rep.floor_caps, "and OBJ-2 is served by nothing"
    assert rep.objectives_unserved == ["OBJ-2"]


def test_an_unreadable_document_does_not_invent_the_gap(tmp_path: Path) -> None:
    """With no TRD, coverage was NOT checked — not that every objective failed it.

    Reporting two unserved objectives because the file is missing turns an inability to
    measure into a measurement, which is the defect this kit is organised around.
    """
    caps = _caps(tmp_path, **{"trd.md": ""})

    assert "objective_served_by_no_requirement" not in caps
