"""A closed BLOCKER must lift the halt, and the contract must say so.

WHY THIS FILE EXISTS
--------------------
`consolidate_findings.py` has scored the verdict from OPEN findings since B-056:
a finding carrying `status: CLOSED` stays in the report, keeps its severity, and
does not count toward `NEEDS_FIXES`. That is the mechanism a re-review needs, and
it worked.

Nothing said so. `CLOSED` appeared zero times in `skills/review/SKILL.md` and
zero times in `rules/cycle-review.md`. A consumer session hit exactly the case
the mechanism exists for — a BLOCKER fixed, re-verified by the agent that raised
it, `ACTIONLINT_EXIT=0` with zero bytes of output — read `NEEDS_FIXES`, grepped
the consolidator for `outcome` (the field name the harness's `ReportFindings`
tool uses), found nothing, and concluded the capability was missing. It was about
to re-run four review agents at roughly 200k tokens each to work around something
that already worked.

This is the mirror of the defect fixed the same day in `cycle-code-quality.md`,
where the rule promised an ADR escape that no code implemented. Here the code
implements and the contract is silent. Both cost the same thing: a consumer
doing expensive work to route around the gap between the two.

So the tests below pin BOTH halves — the behaviour, and the sentence that makes
it findable.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SKILL_ROOT.parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from consolidate_findings import _classify_verdict  # noqa: E402


def _finding(severity: str, status: str = "") -> dict:
    return {"severity": severity, "status": status, "id": "F-1", "summary": "x"}


def test_a_closed_blocker_does_not_force_needs_fixes() -> None:
    """The behaviour the consumer could not find, pinned.

    `_classify_verdict` receives OPEN findings; the caller filters. This asserts
    the contract at that boundary: a list with no open BLOCKER does not return
    `NEEDS_FIXES` on account of one that was closed.
    """
    assert _classify_verdict([_finding("BLOCKER")], None, None) == "NEEDS_FIXES"
    assert _classify_verdict([], None, None) != "NEEDS_FIXES", (
        "with the closed BLOCKER filtered out, the halt must lift"
    )


def test_the_open_closed_split_is_what_the_caller_passes() -> None:
    """`status: CLOSED` is the exact token the filter keys on.

    A re-review writing `status: fixed`, or the harness's `outcome: fixed`, is
    NOT recognised — and silently counts as open. Pinning the token here is what
    makes the SKILL.md example authoritative rather than illustrative.
    """
    findings = [_finding("BLOCKER", "CLOSED"), _finding("HIGH")]
    open_findings = [f for f in findings if f.get("status") != "CLOSED"]
    assert [f["severity"] for f in open_findings] == ["HIGH"]
    assert _classify_verdict(open_findings, None, None) != "NEEDS_FIXES"


@pytest.mark.parametrize(
    "doc",
    [
        SKILL_ROOT / "SKILL.md",
        PROJECT_ROOT / "rules" / "cycle-review.md",
    ],
    ids=lambda p: p.name,
)
def test_the_contract_states_how_to_close_a_finding(doc: Path) -> None:
    """Both documents must name the field, or the mechanism is unreachable again.

    This is the half that actually failed. The code was right the whole time.
    """
    text = doc.read_text(encoding="utf-8")
    assert "status: CLOSED" in text or "`status: CLOSED`" in text, (
        f"{doc.name} does not tell a re-review how to close a finding — the mechanism "
        "exists in consolidate_findings.py and is unreachable from the contract"
    )


def test_the_two_dishonest_ways_past_a_blocker_are_MECHANISED() -> None:
    """What this used to be, and why it is not that any more.

    It asserted `"delete" in SKILL.md` and `"lower" in SKILL.md`. The concern was
    real — `consolidate_findings.py` scores from OPEN findings, so deleting a
    finding or lowering a BLOCKER to MEDIUM both pass — but a grep over a contract
    is not a guard. "Removing a finding is forbidden" says the same thing and
    fails the check; the word `delete` appearing anywhere else satisfies it. It
    failed when the sentence improved and passed when the thing broke.

    `skills/_kit-rules/prompt-text-is-not-behaviour.md` names that shape and says what to do
    with it: a grep over a contract is a SYMPTOM that the guarantee exists only as
    prose. So the guarantee moved. `check_finding_continuity.py` compares two
    consolidated reports for one slug and reports findings that were open and are
    now neither present nor CLOSED, and findings whose severity dropped.

    This test now asserts the MECHANISM exists and works, which is the thing the
    sentence was promising. The sentence may be rewritten freely.
    """
    import sys
    sys.path.insert(0, str(SKILL_ROOT / "scripts"))
    from check_finding_continuity import check_finding_continuity

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        reviews = root / "records" / "reviews"
        reviews.mkdir(parents=True)
        (reviews / "s-review-2026-01-01.md").write_text(
            "## BLOCKER findings (1)\n\n### F-a-1: a real defect\n", encoding="utf-8")
        (reviews / "s-review-2026-01-02.md").write_text(
            "## MEDIUM findings (1)\n\n### F-a-1: a real defect\n", encoding="utf-8")

        report = check_finding_continuity(root, "s")
        assert any("F-a-1" in d for d in report.downgraded), (
            "the downgrade path is not caught — the contract is alone again")

        (reviews / "s-review-2026-01-02.md").write_text("# nothing\n", encoding="utf-8")
        report = check_finding_continuity(root, "s")
        assert "F-a-1" in report.vanished, "the deletion path is not caught"
