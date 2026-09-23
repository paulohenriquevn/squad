"""A signature marker on a box's continuation line was invisible, and the tick read as human.

`score_alignment.py` paired each box's mark to its text with its own `_CHECKBOX_RE`, anchored
`^…$` under `re.MULTILINE`, so it captured ONE line. A `<!-- signed-by: … -->` on the next
line was outside the captured text, the per-box lookup found nothing, and the `else "human"`
fallback fired — reporting a brief as signed by a PERSON when every box was signed by an
agent. `signed_by_is_human` exists exactly to keep that distinction.

Measured in this repository: the same marker, the same judge, two positions.

    marker on the `- [x]` line          signed_by=judge/alignment-judge   is_human=False
    marker on a continuation line       signed_by=human                   is_human=True

Box authors wrap long text, and the natural place for a long `(verified: …)` clause is a line
of its own — so the failing shape is the one a careful reviewer produces.

THE ROOT CAUSE IS THE DUPLICATE READER, not the regex. `squad/signoff.py` declares itself the
one reader ("the one reader, since 2026-09-20") and its `read()` searches the WHOLE body, so it
never had this bug; `score_alignment.py` kept a second, line-wise reader beside it. Two readers
of one question is how they come to disagree — the multiplication
`check_install_drift._is_project_owned` refuses to add to in its own comment.

The default itself is NOT changed here. `"human"` on an unattributed tick is deliberate and
documented (`test_a_judge_signature_is_reported_as_the_judge`: *"An unattributed tick reads as
a human's"*), because a person editing the file by hand ticks without writing a marker.
Changing it would oblige every human to write `human/<name>` or be blocked, which is a contract
decision. What ships instead is the count: the report says how many ticks carried no marker, so
the assumption is legible rather than silent.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "skills" / "plan-alignment" / "scripts"))

BODY = "# Alignment: X\n\n## Problem\n" + ("word " * 40) + "\n"
MARKER = "<!-- signed-by: judge/alignment-judge -->"


def _brief(tmp_path: Path, signoff: str) -> Path:
    p = tmp_path / "brief.md"
    p.write_text(BODY + "\n## Reviewer sign-off\n" + signoff, encoding="utf-8")
    return p


def _score(path: Path):
    from score_alignment import score_alignment
    return score_alignment(path)


def test_a_marker_on_the_box_line_is_attributed(tmp_path: Path) -> None:
    """The control. Without it the test below passes on a reader that finds nothing at all."""
    report = _score(_brief(tmp_path, f"- [x] CHK001 a judgement  {MARKER}\n"))
    assert report.signed_by == "judge/alignment-judge"
    assert report.signed_by_is_human is False


def test_a_marker_on_a_continuation_line_is_attributed(tmp_path: Path) -> None:
    report = _score(_brief(tmp_path,
        "- [x] CHK001 a judgement that wraps over\n"
        "      two lines because it is long\n"
        f"      {MARKER}\n"))
    assert report.signed_by == "judge/alignment-judge", (
        "a marker inside the box was not attributed, so the tick read as a person's")
    assert report.signed_by_is_human is False


def test_a_marker_belongs_to_its_own_box_and_not_the_next(tmp_path: Path) -> None:
    """Attribution is per box. Reading the whole section would smear one signer over all."""
    report = _score(_brief(tmp_path,
        f"- [x] CHK001 first\n      {MARKER}\n"
        "- [x] CHK002 second  <!-- signed-by: human/paulo -->\n"))
    assert report.signed_by == "judge/alignment-judge", (
        "weakest-wins: a judge in the set makes the set an agent's")


def test_an_unticked_box_still_blocks(tmp_path: Path) -> None:
    report = _score(_brief(tmp_path,
        f"- [x] CHK001 done\n      {MARKER}\n"
        "- [ ] CHK002 not yet\n"))
    assert report.signed_by is None
    assert not report.reviewer_signed_off


def test_the_report_says_how_many_ticks_carried_no_marker(tmp_path: Path) -> None:
    """The silent assumption made legible. `human` on absence stays; unstated does not."""
    report = _score(_brief(tmp_path,
        "- [x] CHK001 no marker at all\n"
        f"- [x] CHK002 signed  {MARKER}\n"))
    assert report.unattributed_ticks == 1, (
        "a tick with no marker is counted as `human` by contract; the count is what tells a "
        "reader the value was assumed rather than read")


def test_every_tick_unattributed_is_still_human_and_counted(tmp_path: Path) -> None:
    """The documented default is NOT changed — only made visible."""
    report = _score(_brief(tmp_path, "- [x] CHK001 a\n- [x] CHK002 b\n"))
    assert report.signed_by == "human"
    assert report.unattributed_ticks == 2
