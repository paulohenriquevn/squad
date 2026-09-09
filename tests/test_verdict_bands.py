"""Every verdict declares which band it is in, in one place, with a dedicated owner.

WHY THIS EXISTS

`rules/blocking-verdicts.txt` was created because the list of "what holds an item"
had been written twice and the two copies disagreed. Its complement — the list of
what COUNTS AS CLEAN — was then born as `_CLEAN_VERDICTS`, a frozenset hardcoded
inside `mechanisms/gates/check_phase_drift.py`, with no owner and no file. The same
defect, one file along.

Measured 2026-09-08 before this registry existed:

    47 verdicts reachable in the event stream
    14 in blocking-verdicts.txt
    16 in _CLEAN_VERDICTS
    23 in neither

And the consequence was not theoretical. `check_phase_drift` decides whether a
return to an earlier phase is legitimate rework or disorder by asking whether the
previous verdict was clean. An unclassified verdict was assumed not-clean, so the
disorder check turned itself off silently:

    release -> RELEASED             then back to implement  ->  DETECTED
    release -> PRE_RELEASED         then back to implement  ->  SILENT
    release -> ITEM_VERIFIED_LOCAL  then back to implement  ->  SILENT
    release -> PRODUCT_ALIGNED      then back to implement  ->  SILENT

All three silent ones are SUCCESS verdicts. `cycle-rule-schema.md` says of
`ITEM_VERIFIED_LOCAL`: "that one is in the OK column on purpose — reporting it as
blocked would file finished work as outstanding." The only mechanism computing
bands disagreed with the document that declares them.

WHAT THIS IS NOT

It is not a renaming. `cycle-rule-schema.md § Why each vocabulary differs` argues
per cycle why the tokens diverge, and those arguments hold: collapsing
`ITEM_KILLED` into `INVALID` would file the cycle's most valuable result as a
failure. The names carry domain meaning; only their CLASSIFICATION is unified.

TWO AXES, NOT ONE

Band and blocking are independent, and conflating them would be wrong in both
directions. `FAIL_SOFT` is `redo` and does NOT block. `NEEDS_FIXES` is `redo` and
DOES block. This registry answers "what kind of outcome is this?";
`blocking-verdicts.txt` keeps answering "does it hold the item?".
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "mechanisms" / "cycle"))

from verdict_bands import (
    BANDS,
    Band,
    band_of,
    clean_verdicts,
    load_bands,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "rules" / "verdict-bands.txt"


# ---------------------------------------------------------------------------
# The five bands
# ---------------------------------------------------------------------------

def test_orthogonal_is_a_band_of_its_own() -> None:
    """The band that made the silence possible.

    `AWAITING_REVIEW`, `BACKLOG_EMPTY` and `AWAITING_HUMAN` grade nothing. Forcing
    them into one of the four scoring columns is what produced a classification
    nobody could state — so the fifth band is where they say so out loud.
    """
    assert Band.ORTHOGONAL in set(BANDS)
    assert band_of("AWAITING_REVIEW") is Band.ORTHOGONAL
    assert band_of("BACKLOG_EMPTY") is Band.ORTHOGONAL
    assert band_of("AWAITING_HUMAN") is Band.ORTHOGONAL


def test_killing_an_item_is_a_clean_outcome() -> None:
    """`cycle-rule-schema.md`: it sits in the OK column because a run that kills an
    item succeeded — it stopped work that would have been justified by a hunch.

    Classifying it anywhere else would create the standing incentive the schema
    names: ship weak findings rather than kill them.
    """
    assert band_of("ITEM_KILLED") is Band.CLEAN


def test_the_three_verdicts_the_drift_checker_used_to_miss() -> None:
    """The regression this whole registry exists for. All three are successes."""
    assert band_of("PRE_RELEASED") is Band.CAVEATS
    assert band_of("ITEM_VERIFIED_LOCAL") is Band.CLEAN
    assert band_of("PRODUCT_ALIGNED") is Band.CLEAN


@pytest.mark.parametrize(
    ("verdict", "band"),
    [
        ("SHIPPABLE", Band.CLEAN),
        ("READY_TO_MERGE", Band.CLEAN),
        ("RELEASED", Band.CLEAN),
        ("ACCEPTED", Band.CLEAN),
        ("SHIPPABLE_WITH_CAVEATS", Band.CAVEATS),
        ("PASS_WITH_CAVEATS", Band.CAVEATS),
        ("NEEDS_REVISION", Band.REDO),
        ("FAIL_SOFT", Band.REDO),
        ("NEEDS_FIXES", Band.REDO),
        ("INVALID", Band.STRUCTURAL),
        ("FAIL_HARD", Band.STRUCTURAL),
        ("NOT_VALIDATED", Band.STRUCTURAL),
    ],
)
def test_representative_classifications(verdict: str, band: Band) -> None:
    assert band_of(verdict) is band


# ---------------------------------------------------------------------------
# Band and blocking are independent axes
# ---------------------------------------------------------------------------

def test_band_does_not_imply_blocking() -> None:
    """`FAIL_SOFT` and `NEEDS_FIXES` share a band and differ on blocking.

    Deriving one from the other would either make every rework loop a wall, or let
    a real wall advance. `blocking-verdicts.txt` keeps its own answer.
    """
    blocking = {
        line.strip() for line in (ROOT / "rules" / "blocking-verdicts.txt")
        .read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }

    assert band_of("FAIL_SOFT") is Band.REDO
    assert band_of("NEEDS_FIXES") is Band.REDO
    assert "FAIL_SOFT" not in blocking
    assert "NEEDS_FIXES" in blocking


# ---------------------------------------------------------------------------
# The registry itself
# ---------------------------------------------------------------------------

def test_every_entry_carries_a_reason(tmp_path: Path) -> None:
    """A classification with no reasoning is a table nobody can argue with.

    Same floor the panel applies to a vote and the judge applies to a signature:
    the next reader has to be able to disagree with a specific claim.
    """
    entries = load_bands(REGISTRY)
    assert entries, "the registry parsed to nothing"
    for verdict, entry in entries.items():
        assert entry.reason.strip(), f"{verdict} is classified with no reason"


def test_an_unknown_verdict_raises_rather_than_defaulting() -> None:
    """The failure mode this replaces was a silent default.

    `check_phase_drift` treated anything it did not recognise as not-clean, and the
    disorder check disappeared for 23 verdicts with nothing in the output to notice.
    A registry that answers confidently about a token it has never seen would
    rebuild exactly that.
    """
    with pytest.raises(KeyError, match="NOT_A_REAL_VERDICT"):
        band_of("NOT_A_REAL_VERDICT")


def test_a_duplicate_classification_is_refused(tmp_path: Path) -> None:
    """One token, one band. Two rows for one verdict is the disagreement that
    `blocking-verdicts.txt` was created to end, reappearing inside its successor."""
    reg = tmp_path / "bands.txt"
    reg.write_text(
        "SHIPPABLE | clean | the document is complete and its pointers resolve\n"
        "SHIPPABLE | redo  | some other reading of the same token\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="SHIPPABLE"):
        load_bands(reg)


def test_an_unknown_band_name_is_refused(tmp_path: Path) -> None:
    reg = tmp_path / "bands.txt"
    reg.write_text("SHIPPABLE | excellent | not one of the five bands\n", encoding="utf-8")
    with pytest.raises(ValueError, match="excellent"):
        load_bands(reg)


def test_clean_verdicts_is_derived_from_the_registry() -> None:
    """What `check_phase_drift` reads instead of its own frozenset.

    CAVEATS counts as clean for the drift question — a caveat is a pass, and a
    return after one is disorder just as much as a return after a plain pass.
    """
    clean = clean_verdicts(REGISTRY)

    assert "RELEASED" in clean
    assert "PRE_RELEASED" in clean, "a caveated pass is still a pass for drift"
    assert "ITEM_KILLED" in clean
    assert "NEEDS_REVISION" not in clean
    assert "FAIL_HARD" not in clean
    assert "AWAITING_HUMAN" not in clean, "an orthogonal verdict grades nothing"
