"""The item a plan answers to is DECLARED. A guess must never beat a declaration.

`_committed_work_id` returned the smallest id mentioned anywhere in the plan:

    items = sorted(set(_ITEM_RE.findall(content))); return f"B-{items[0]}"

and consulted the frontmatter only when that list was EMPTY — so the guess won whenever
the plan mentioned anything, which is always.

Measured by the consumer that reported it, on a real plan for `B-286` mentioning `B-286`
ten times, `B-271` seven, `B-288` four and `B-036` twice:

    _committed_work_id  ->  B-036
    classify depth B-286  ->  LOCAL
    classify depth B-036  ->  FULL      (it is blocked, and blocked forces FULL)

So a brief complete by the LOCAL contract was graded against the FULL rubric and scored
23/34 = 68%, hard cap 49, on a plan whose own `weighted_avg` was 99.2 with coverage 7/7 and
4/4 ADRs carrying alternatives. Two further items were dragged behind it, and a lane read
the message, concluded that every LOCAL item in every consumer was unbuildable, and stopped.

**Mentioning related items is what a well-written plan does**, so the defect fired hardest
on the best inputs. The consumer's workaround was to rename the related items in prose —
thirteen substitutions — which works and teaches the next author nothing.

THE ORDER IS THE FIX. Two declarations already exist and both are load-bearing elsewhere:
the frontmatter `milestone_id`, and the filename slug that `_brief_for` derives the brief
path from. A guess is only reached when neither is present, and only when it is
unambiguous — one distinct id. Several ids and no declaration returns None, which since
the depth fix renders as NOT MEASURED rather than silently grading the FULL rubric.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "skills" / "plan-confidence" / "scripts"))

from check_alignment_gate import _committed_work_id  # noqa: E402

#: The reported plan's shape: the subject mentioned most, a smaller related id mentioned least.
_REAL_SHAPE = (
    "# Plan: reach the deck's public seam\n\n"
    "`B-286` is the subject. " + "`B-286` again. " * 9 +
    "`B-271` is related. " * 7 + "`B-288` too. " * 4 + "`B-036` is mentioned twice. " * 2
)


def test_the_filename_beats_every_mention(tmp_path: Path) -> None:
    plan = tmp_path / "b-286-reach-the-seam-plan.md"
    plan.write_text(_REAL_SHAPE, encoding="utf-8")
    assert _committed_work_id(_REAL_SHAPE, plan) == "B-286"


def test_the_frontmatter_beats_the_filename(tmp_path: Path) -> None:
    """An author who declares it in the document means it more than the file name does."""
    body = "---\nmilestone_id: B-999\n---\n\n" + _REAL_SHAPE
    plan = tmp_path / "b-286-reach-the-seam-plan.md"
    plan.write_text(body, encoding="utf-8")
    assert _committed_work_id(body, plan) == "B-999"


def test_a_single_mention_is_still_read(tmp_path: Path) -> None:
    """The guess survives where it cannot be wrong."""
    body = "The plan implements `B-014` and nothing else.\n"
    plan = tmp_path / "some-plan.md"
    plan.write_text(body, encoding="utf-8")
    assert _committed_work_id(body, plan) == "B-014"


def test_several_mentions_and_no_declaration_is_not_guessed(tmp_path: Path) -> None:
    """None is the honest answer, and since the depth fix it is a visible one."""
    plan = tmp_path / "some-plan.md"
    plan.write_text(_REAL_SHAPE, encoding="utf-8")
    assert _committed_work_id(_REAL_SHAPE, plan) is None


def test_no_mention_and_no_declaration_is_none(tmp_path: Path) -> None:
    plan = tmp_path / "some-plan.md"
    plan.write_text("A plan about nothing in particular.\n", encoding="utf-8")
    assert _committed_work_id("A plan about nothing in particular.\n", plan) is None


def test_the_smallest_id_is_never_preferred(tmp_path: Path) -> None:
    """The regression itself, stated as the property rather than the example."""
    body = "`B-900` is the subject; `B-001` is mentioned once.\n"
    plan = tmp_path / "b-900-the-subject-plan.md"
    plan.write_text(body, encoding="utf-8")
    assert _committed_work_id(body, plan) == "B-900"
