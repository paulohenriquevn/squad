"""The guard against a deleted finding is wired, not written down.

THE DEFECT THIS CLOSES
----------------------
`check_finding_continuity.py` exists, carries tests and sits in `rules/squad-map.md`,
and a sweep of `skills/`, `rules/`, `mechanisms/` and `hooks/` on 2026-09-21 found
**nothing that invokes it**. Its own docstring says why it was written:

    "`consolidate_findings.py` scores from OPEN findings. A re-review that deletes a
     finding, or lowers a BLOCKER to MEDIUM, therefore passes — and until now the only
     thing standing against either was a sentence in `skills/review/SKILL.md`, guarded
     by a test asserting `"delete" in text`. A grep over a contract is not a guard …
     **This is the mechanised half.**"

The mechanised half was written and never connected, so the guarantee stayed the prose
it was meant to replace. `check_record_scope.py` — 165 lines, also tested, also in the
map — was in the same state: it measured that 2 of 48 reviews declared what they read,
and nothing ran it.

Both enter `consolidate_findings.py` the way `check_upstream_gate` already does, which
is the shape `cycle-review.md` names: "entering `consolidate_findings.py` as findings so
the verdict cannot be computed while ignoring it".

WHAT SEVERITY, AND WHY NOT BLOCKER
-----------------------------------
HIGH. `check_finding_continuity` refuses to rule on intent — "an honest re-scope and a
quiet deletion look identical on disk" — so a BLOCKER would assert the judgement the
script declines to make. HIGH puts it in front of the reader and, through
`unregistered_high`, forces the disappearance to be named and owned before the review
can hand off.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONSOLIDATE = REPO / "skills" / "review" / "scripts" / "consolidate_findings.py"

EARLIER = """# Review: demo

**Verdict:** NEEDS_FIXES

## BLOCKER findings (1)

### F-001: token compared with ==

- **Found by:** security-auditor
"""

LATER_WITHOUT_IT = """# Review: demo

**Verdict:** READY_TO_MERGE

## HIGH findings (0)
"""


def _project(tmp_path: Path, *, with_history: bool) -> Path:
    reviews = tmp_path / ".squad" / "records" / "reviews"
    reviews.mkdir(parents=True)
    if with_history:
        (reviews / "b042-demo-review-2026-09-01.md").write_text(EARLIER, encoding="utf-8")
        (reviews / "b042-demo-review-2026-09-15.md").write_text(LATER_WITHOUT_IT, encoding="utf-8")
    # `_project_root_for` walks up looking for the records root, so the findings live
    # where `/review` puts them: under the project, not beside it.
    (tmp_path / "rules").mkdir()
    findings = tmp_path / "findings"
    findings.mkdir()
    (findings / "quiet-auditor.yaml").write_text(
        "agent: quiet-auditor\nfindings: []\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, capture_output=True)
    return tmp_path


def _consolidate(root: Path) -> tuple[dict, str]:
    """The JSON summary and the markdown a person reads.

    The summary exposes `findings_by_severity` and `unregistered_high`, not the finding
    list — so these assertions read what a consumer reads rather than an internal shape.
    """
    report = root / "report.md"
    proc = subprocess.run(
        [sys.executable, str(CONSOLIDATE), "--findings-dir", str(root / "findings"),
         "--output", str(report), "--slug", "b042-demo", "--repo-root", str(root)],
        capture_output=True, text=True)
    summary = json.loads(proc.stdout[proc.stdout.index("{"):])
    return summary, report.read_text(encoding="utf-8")


def test_a_finding_that_vanished_between_reviews_is_reported(tmp_path: Path) -> None:
    summary, markdown = _consolidate(_project(tmp_path, with_history=True))

    assert "F-001" in markdown and "vanished" in markdown, (
        "a BLOCKER present in the earlier review and absent from the later one is the "
        "case this gate was written for, and nothing was running it")
    assert any("F-001" in item for item in summary["unregistered_high"]), (
        "an unregistered HIGH is what stops the review handing off with the "
        "disappearance unexplained")


def test_the_continuity_finding_does_not_assert_intent(tmp_path: Path) -> None:
    """The script refuses to rule on intent, so the finding must not either."""
    _, markdown = _consolidate(_project(tmp_path, with_history=True))

    # The heading line itself carries the count, so the section starts after it.
    section = markdown.split("## HIGH findings")[1].split("\n## ")[0]
    assert "F-001" in section, "the disappearance is HIGH, not BLOCKER"
    assert "identical on disk" in section, (
        "the evidence must name the ambiguity rather than rule on it")


def test_a_first_review_is_not_penalised(tmp_path: Path) -> None:
    """Fewer than two reviews means nothing to compare, which is not a finding."""
    _, markdown = _consolidate(_project(tmp_path, with_history=False))

    assert "vanished" not in markdown


# ------------------------------------------ the record says what it covered
#
# `check_record_scope.py` — 165 lines, tested, in `rules/squad-map.md` — was invoked by
# nothing, the same state as the continuity gate. Its docstring records the measurement
# that produced it:
#
#     review files declaring a reviewed range   2 of 48
#     audit files mentioning a scope            3 of 16
#
# and the conclusion: *"the past is permanently unrecoverable, and the only honest move
# left is to stop the same hole opening again."* Wiring it as a finding about somebody
# else's old record would not do that. Emitting the declaration in the record this run
# writes does, and the check is then run against that record — the gate verifying the
# artifact its own phase produced.


def test_the_report_declares_which_item_it_covered(tmp_path: Path) -> None:
    import sys as _sys

    _sys.path.insert(0, str(REPO / "skills" / "review" / "scripts"))
    from check_record_scope import ScopeVerdict, check_record

    root = _project(tmp_path, with_history=False)
    _consolidate(root)

    result = check_record(root / "report.md")

    assert result.verdict is ScopeVerdict.DECLARED, result.reason
    assert result.items == ["B-042"], (
        "the slug carries the item id in this kit's convention, and that is what "
        "`check_record_scope` reads")
