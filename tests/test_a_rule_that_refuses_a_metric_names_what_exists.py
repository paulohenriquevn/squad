"""The rule refusing flow metrics listed four absences, and three had stopped being true.

`current-constraint.md` declined to gate on flow with a good argument — *a hard gate against
data that does not exist is answered by assertion* — and backed it with a blanket claim:
*"we do not currently instrument flow across the ecosystem. There is no per-stage lead time,
no wait time, no WIP series, no cumulative flow diagram."*

By 2026-09-22 the board computed throughput, WIP and item lead time. The sentence outlived
the fact that justified it, which is the class
`docs/wiki/decisions/a-claim-about-now-is-not-a-fact-that-survives.md` records — and it is
worse here than a missing metric, because a refusal is what somebody reads BEFORE deciding
not to measure. A reader acting on that paragraph would have rebuilt three measures the
system already had.

What this file pins is not the prose. It is the correspondence: every measure the rule calls
computed must actually be computed, and the refusal must stay specific rather than sliding
back to a blanket.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "skills" / "backlog-review" / "scripts"))

RULE = _ROOT / "rules" / "current-constraint.md"


def _rule() -> str:
    return RULE.read_text(encoding="utf-8")


def test_every_measure_the_rule_calls_computed_is_computed() -> None:
    """The three the old paragraph denied. A rule naming a field the code lacks is the
    same defect pointing the other way."""
    import board_state

    source = inspect.getsource(board_state)
    for field in ("throughput_per_day", "lead_time_p50_days", '"wip"'):
        assert field in source, f"the rule claims {field} is computed and it is not"


def test_the_rule_no_longer_denies_them() -> None:
    """The blanket claim may survive as a QUOTE of what was corrected, never as a claim.

    A first cut of this test refused the sentence anywhere in the file, which would have
    forced the correction to hide the thing it corrects — the same trap
    `check_backlog_structure` needed a marker for, and `check_evidence_freshness` a
    `dead-pointer-ok:`. An item whose subject is a retired statement has to be able to
    name it.
    """
    body = _rule()
    claim = "we do not currently instrument flow across the ecosystem"

    assert body.count(claim) <= 1, "the sentence appears more than once; one of them is live"
    if claim in body:
        sentence_start = body.rfind("Until 2026", 0, body.index(claim))
        assert sentence_start != -1 and body.index(claim) - sentence_start < 200, (
            "the sentence survives outside the record of its own correction"
        )
    assert "**computed**" in body, "the rule must name what exists, not only what does not"


def test_the_absences_that_remain_are_still_named() -> None:
    """Correcting a wrong absence must not delete the right ones.

    `wait time` and `cumulative flow` are genuinely missing, and a rule that stopped
    saying so would be the same error with the sign flipped.
    """
    body = _rule()

    for still_missing in ("wait time", "cumulative flow"):
        assert still_missing in body, f"{still_missing} is absent and the rule stopped saying so"
    assert "**absent**" in body


def test_the_dora_refusal_names_what_is_missing_per_metric() -> None:
    """A blanket refusal is what this whole correction is about.

    Each of the five has to carry the thing that would change the answer, or the next
    reader gets "not instrumented" again — one layer over, in a newer sentence.
    """
    body = _rule()

    for metric in ("change lead time", "deployment frequency", "change fail rate",
                   "failed deployment recovery time", "deployment rework rate"):
        assert metric in body, f"{metric} is refused without being named"


def test_the_refusal_says_what_would_change_it() -> None:
    body = _rule()

    assert "does not deploy" in body, (
        "four of the five measure a deployment, and that is the reason — not 'no data'"
    )
    assert "kit#163" in body, "the decision must point at where it was taken"
