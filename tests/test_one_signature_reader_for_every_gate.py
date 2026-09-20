"""Who signed, read one way, by every gate that asks.

THE DEFECT THIS CLOSES
----------------------
Three gates read a `<!-- signed-by: … -->` marker and each carried its own pattern and
its own rule about what the captured string means. Measured 2026-09-20, the three
disagreed in ways that pointed in opposite directions:

    score_alignment.py            ([^>]+?)     allowlist `human` / `human/…`
    score_product_alignment.py    ([^\\s>]+)    denylist of one: `judge/`
    check_design_completeness.py  ([^\\s>]+)    denylist of one: `judge/`

So the DESIGN gate returned `DESIGN_AGREED`, exit 0, for
`<!-- signed-by: daedalus-tech-lead -->` — the agent that draws the diagrams — while
refusing `<!-- signed-by: human/paulo (approved in session) -->`, because a pattern
that stops at the first space cannot see a route and captured nothing at all. A gate
that accepts the author and rejects the reviewer is worse than no gate: it is one that
reports the wrong answer confidently.

`squad/signoff.py` is now the one reader. This test refuses a second one.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: Every gate that decides something from a sign-off marker.
READERS = (
    "skills/brainstorm-pieces/scripts/score_product_alignment.py",
    "skills/design/scripts/check_design_completeness.py",
    "skills/plan-alignment/scripts/score_alignment.py",
)

#: A local `signed-by` pattern. The shared module is allowed to define one — it is
#: the definition — and nobody else is.
_LOCAL_PATTERN = re.compile(r"re\.compile\([^)]*signed-by", re.IGNORECASE)

#: The shape that reads as "everything except this one prefix". An open set of agent
#: names passes it, which is how an agent signed a product and a system design.
_DENYLIST = re.compile(r"startswith\(\s*[\"']judge/")


@pytest.mark.parametrize("rel", READERS)
def test_a_gate_does_not_carry_its_own_signature_pattern(rel: str) -> None:
    source = (REPO / rel).read_text(encoding="utf-8")

    assert not _LOCAL_PATTERN.search(source), (
        f"{rel} compiles its own `signed-by` pattern. Three of them drifted into two "
        f"different answers about the same marker — import squad.signoff instead")


@pytest.mark.parametrize("rel", READERS)
def test_a_gate_does_not_decide_who_signed_by_refusing_one_prefix(rel: str) -> None:
    source = (REPO / rel).read_text(encoding="utf-8")

    assert not _DENYLIST.search(source), (
        f"{rel} decides a signer by refusing the single prefix `judge/`, which accepts "
        f"every other name an agent could sign under. Use squad.signoff.is_human, "
        f"which is an allowlist")


def test_the_shared_reader_keeps_the_route() -> None:
    """`human/paulo (approved in session)` says more than `human/paulo`."""
    from squad.signoff import read

    sheet = read("- [x] one  <!-- signed-by: human/paulo (approved in session) -->\n")

    assert sheet.signers == ["human/paulo (approved in session)"]
    assert sheet.human_signed


def test_the_unsigned_marker_names_nobody() -> None:
    """`<!-- signed-by: -->` is what every template ships, and it is not a signer."""
    from squad.signoff import read

    assert read("<!-- signed-by: -->").signers == []


@pytest.mark.parametrize("signer, human", [
    ("human", True),
    ("human/paulo", True),
    ("human/paulo (approved in session)", True),
    ("judge/alignment-judge", False),
    ("daedalus-tech-lead", False),
    ("iris-product-designer", False),
    ("paulo", False),
    ("", False),
])
def test_only_a_declared_human_reads_as_one(signer: str, human: bool) -> None:
    from squad.signoff import is_human

    assert is_human(signer) is human


def test_a_deleted_checklist_is_not_a_ticked_one() -> None:
    """Zero boxes is zero unticked boxes, and it is not a review."""
    from squad.signoff import read

    sheet = read("## Sign-off\n\n<!-- signed-by: human/paulo -->\n")

    assert sheet.ticked == 0
    assert not sheet.complete
