"""Who signed, and the report must never blur it.

The operator asked to have the sign-off ticked on their behalf. Ticking it as
though a human had reviewed would make the artefact assert something false — the
one thing this artefact exists to carry. The operator had already chosen the
honest alternative: a judge agent signs, in the open.

So a signature carries its author. `ALIGNED` no longer means one thing: it means
either a human read the brief, or an agent did, and a reader must be able to tell
those apart without opening the file. `rules/alignment-threshold.md` says the
agent that WRITES a brief may never sign it; a judge is a different agent, and
that distinction is the whole basis for allowing this at all.
"""
from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from score_alignment import score_alignment  # noqa: E402

BODY = "# Alignment: X\n\n## Problem\n" + ("word " * 40) + "\n"


def _write(tmp_path: Path, signoff: str) -> Path:
    p = tmp_path / "brief.md"
    p.write_text(BODY + "\n## Reviewer sign-off\n" + signoff, encoding="utf-8")
    return p


def test_a_human_signature_is_reported_as_human(tmp_path: Path) -> None:
    report = score_alignment(_write(tmp_path, "- [x] CHK001 a judgement\n"))
    assert report.reviewer_signed_off
    assert report.signed_by == "human"


def test_a_judge_signature_is_reported_as_the_judge(tmp_path: Path) -> None:
    """An unattributed tick reads as a human's. The marker is what keeps the
    record honest, so the report must surface it rather than count it the same."""
    report = score_alignment(_write(
        tmp_path,
        "- [x] CHK001 a judgement  <!-- signed-by: judge/alignment-judge -->\n"))
    assert report.reviewer_signed_off
    assert report.signed_by == "judge/alignment-judge"


def test_a_mixed_signature_set_reports_the_weakest(tmp_path: Path) -> None:
    """Three human ticks and one judge tick is not a human sign-off.

    A reader deciding how much to trust the verdict needs the weakest link, not
    the majority — the same reason a partially reviewed brief is unreviewed.
    """
    report = score_alignment(_write(
        tmp_path,
        "- [x] CHK001 one  <!-- signed-by: judge/alignment-judge -->\n"
        "- [x] CHK002 two\n"))
    assert report.signed_by == "judge/alignment-judge"


def test_an_unsigned_brief_names_nobody(tmp_path: Path) -> None:
    report = score_alignment(_write(tmp_path, "- [ ] CHK001 a judgement\n"))
    assert not report.reviewer_signed_off
    assert report.signed_by is None


def test_a_named_human_is_still_a_human(tmp_path: Path) -> None:
    """Provenance must not cost the distinction it exists to protect.

    The operator approved in conversation and the record should say so — who, and
    by what route. But the first cut treated any marker other than the bare word
    `human` as an agent, so naming the person would have downgraded their own
    signature to an agent's. A `human/` prefix keeps both: the record gains the
    route, and `ALIGNED` keeps meaning what it meant.
    """
    report = score_alignment(_write(
        tmp_path,
        "- [x] CHK001 a judgement  <!-- signed-by: human/paulo (approved in session) -->\n"))
    assert report.reviewer_signed_off
    assert report.signed_by.startswith("human/")
    assert report.signed_by_is_human


def test_a_judge_is_not_a_human(tmp_path: Path) -> None:
    report = score_alignment(_write(
        tmp_path, "- [x] CHK001 x  <!-- signed-by: judge/alignment-judge -->\n"))
    assert not report.signed_by_is_human


def test_a_human_tick_beside_a_judge_tick_is_not_a_human_signoff(tmp_path: Path) -> None:
    """Weakest wins, and naming the human does not change that."""
    report = score_alignment(_write(
        tmp_path,
        "- [x] CHK001 x  <!-- signed-by: human/paulo -->\n"
        "- [x] CHK002 y  <!-- signed-by: judge/alignment-judge -->\n"))
    assert not report.signed_by_is_human
