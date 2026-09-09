"""Who signed, and the report must never blur it.

The operator asked to have the sign-off ticked on their behalf. Ticking it as
though a human had reviewed would make the artefact assert something false — the
one thing this artefact exists to carry. The operator had already chosen the
honest alternative: a judge agent signs, in the open.

So a signature carries its author. `ALIGNED` no longer means one thing: it means
either a human read the brief, or an agent did, and a reader must be able to tell
those apart without opening the file. `skills/_kit-rules/alignment-threshold.md` says the
agent that WRITES a brief may never sign it; a judge is a different agent, and
that distinction is the whole basis for allowing this at all.
"""
from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from alignment_judge import sign  # noqa: E402
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


def test_an_approving_signature_does_not_lower_the_score(tmp_path) -> None:
    """kit#17. The gate must score the artefact, not the reviewer's prose.

    `alignment_judge.py` appends the judge's `--reason` under `## Reviewer
    sign-off`, and the placeholder criterion scanned the whole document for the
    bare token `UNKNOWN`. So a judge writing "no unanswered UNKNOWN" as part of
    saying the brief was CLEAN made that criterion fail. Measured on a real brief:
    34/34 before the signature, 32/34 after. Nearer the threshold, an approving
    signature would have pushed the brief below 90% and turned ALIGNED back into
    a refusal.
    """
    brief = tmp_path / "b.md"
    body = ("# Alignment: X\n\n## Problem\n\n"
            + "the problem is stated as something observed here " * 5 + "\n\n"
            "## Reviewer sign-off\n\n- [ ] CHK001 the evidence holds\n")
    brief.write_text(body, encoding="utf-8")
    before = next(c for c in score_alignment(brief).criteria if c.key == "no_placeholders")

    brief.write_text(
        sign(brief, "judge/alignment-judge",
             "Checked every requirement against the tree: no unanswered UNKNOWN, "
             "no TODO, nothing left to decide."),
        encoding="utf-8")
    after = next(c for c in score_alignment(brief).criteria if c.key == "no_placeholders")

    assert before.score == 2, "the brief was clean before it was signed"
    assert after.score == 2, (
        f"the signature that APPROVED the brief lowered its score: {after.why}")


def test_a_placeholder_in_the_brief_itself_is_still_caught_after_signing(tmp_path) -> None:
    """The narrowing is scoped to the reviewer's section, not a pardon for the
    document. A hole in a requirement stays a hole after a judge signs."""
    brief = tmp_path / "b.md"
    brief.write_text(
        "# Alignment: X\n\n## Functional Requirements\n\n"
        "- FR-001: the system does TODO when the ledger is written.\n\n"
        "## Reviewer sign-off\n\n- [ ] CHK001 the evidence holds\n", encoding="utf-8")

    brief.write_text(sign(brief, "judge/alignment-judge", "clean"), encoding="utf-8")
    after = next(c for c in score_alignment(brief).criteria if c.key == "no_placeholders")

    assert after.score == 0, f"a TODO in an FR survived the signature: {after.why}"


# ---------------------------------------------------------------------------
# WHICH MODEL JUDGED — added 2026-09-08
#
# `signed_by` already separated a person from a judge. It did not say WHICH judge,
# and under `rules/review-panel.txt` that gap matters: the whole argument for an
# orthogonal reviewer is that correlated models share failure modes, and a record
# that does not name the model cannot be checked for correlation at all.
#
# A signature that says "a judge approved this" and cannot say which one is not
# auditable — it is the same claim `alignment_judge.py` makes about a tick.
# ---------------------------------------------------------------------------

def test_the_signature_records_which_model_judged(tmp_path: Path) -> None:
    brief = _write(tmp_path, "- [ ] CHK001 a judgement\n")
    out = sign(brief, "judge/alignment-judge", "checked the evidence and it holds up "
               "against every pointer cited in the brief", model="gpt-5-codex")

    assert "gpt-5-codex" in out, "the model that judged must appear in the record"


def test_an_unrecorded_model_is_visible_rather_than_absent(tmp_path: Path) -> None:
    """The honest failure mode: silence about the model reads as no model at all.

    A caller that omits it gets `unrecorded` written into the brief, not a blank —
    a reader can then see that the provenance is incomplete instead of assuming it
    was checked.
    """
    brief = _write(tmp_path, "- [ ] CHK001 a judgement\n")
    out = sign(brief, "judge/alignment-judge", "checked the evidence and it holds up "
               "against every pointer cited in the brief")

    assert "unrecorded" in out
