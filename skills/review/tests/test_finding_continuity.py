"""A finding that vanished between two reviews of the same slug.

WHY THIS REPLACED A GREP
------------------------
`test_the_contract_forbids_the_two_dishonest_ways_past_a_blocker` asserted
`"delete" in SKILL.md`. The thing it defended is real — `consolidate_findings.py`
scores from OPEN findings, so a re-review that deletes a finding, or lowers a
BLOCKER to MEDIUM, passes — and only the contract warned against it.

But a grep over a contract is not a guard. A synonym defeats it ("removing a
finding is forbidden" fails the check while saying the same thing) and an
unrelated occurrence satisfies it. `skills/_kit-rules/prompt-text-is-not-behaviour.md` names
that shape and says what to do instead: mechanise the guarantee, or admit it is
prose. This is the first half.

WHAT IT CAN AND CANNOT SEE
--------------------------
It compares two consolidated reports for one slug and reports findings that were
open in the earlier one and are neither present nor CLOSED in the later one.
It cannot tell an honest re-scope from a quiet deletion — that is judgement, and
the report says so rather than guessing.
"""
from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from check_finding_continuity import check_finding_continuity  # noqa: E402

EARLIER = """# Review: b-014

## BLOCKER findings (1)

### F-arch-1: the shard client leaks its cursor

## HIGH findings (2)

### F-perf-1: the merge is O(n^2)
### F-test-1: no regression test for the timeout
"""


def _write(tmp_path: Path, name: str, body: str) -> Path:
    d = tmp_path / "records" / "reviews"
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(body, encoding="utf-8")
    return p


def test_a_finding_that_disappeared_is_reported(tmp_path: Path) -> None:
    """The deletion path, which the contract could only warn about."""
    _write(tmp_path, "b-014-review-2026-08-01.md", EARLIER)
    _write(tmp_path, "b-014-review-2026-08-02.md",
           "# Review: b-014\n\n## HIGH findings (1)\n\n### F-perf-1: the merge is O(n^2)\n")

    report = check_finding_continuity(tmp_path, "b-014")
    assert "F-arch-1" in report.vanished
    assert "F-test-1" in report.vanished
    assert not report.is_clean


def test_a_finding_marked_closed_is_not_a_disappearance(tmp_path: Path) -> None:
    """Closing is the legitimate path and must stay cheap to take."""
    _write(tmp_path, "b-014-review-2026-08-01.md", EARLIER)
    _write(tmp_path, "b-014-review-2026-08-02.md",
           "# Review: b-014\n\n## BLOCKER findings (1)\n\n"
           "### F-arch-1: the shard client leaks its cursor  status: CLOSED\n\n"
           "## HIGH findings (2)\n\n### F-perf-1: x\n### F-test-1: y\n")

    report = check_finding_continuity(tmp_path, "b-014")
    assert "F-arch-1" not in report.vanished


def test_a_blocker_that_became_a_medium_is_reported(tmp_path: Path) -> None:
    """The cheaper of the two dishonest paths: the finding is still there, and
    no longer decides the verdict."""
    _write(tmp_path, "b-014-review-2026-08-01.md", EARLIER)
    _write(tmp_path, "b-014-review-2026-08-02.md",
           "# Review: b-014\n\n## MEDIUM findings (1)\n\n"
           "### F-arch-1: the shard client leaks its cursor\n\n"
           "## HIGH findings (2)\n\n### F-perf-1: x\n### F-test-1: y\n")

    report = check_finding_continuity(tmp_path, "b-014")
    assert any("F-arch-1" in d for d in report.downgraded)
    assert not report.is_clean


def test_a_first_review_has_nothing_to_compare(tmp_path: Path) -> None:
    """One report is not a trend. SKIP is the honest answer, not PASS."""
    _write(tmp_path, "b-014-review-2026-08-01.md", EARLIER)
    report = check_finding_continuity(tmp_path, "b-014")
    assert report.is_clean
    assert report.compared is False


def test_it_says_what_it_cannot_decide(tmp_path: Path) -> None:
    """An honest re-scope and a quiet deletion look identical on disk.

    Reporting one as the other would be the fabricated precision this kit
    refuses; the finding is surfaced for a human, not ruled on.
    """
    _write(tmp_path, "b-014-review-2026-08-01.md", EARLIER)
    _write(tmp_path, "b-014-review-2026-08-02.md", "# Review: b-014\n")
    report = check_finding_continuity(tmp_path, "b-014")
    assert report.judgement, "the report must name what it cannot decide"
