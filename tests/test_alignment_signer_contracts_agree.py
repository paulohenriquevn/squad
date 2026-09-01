"""The three documents that say who may sign an alignment brief must agree.

`skills/_kit-rules/alignment-threshold.md § Amended 2026-09-01` allows a reviewer who
is not the author — a person, or `alignment_judge.py` when none is coming. It is the
authority; `score_alignment.py` implements it, turning the verdict on
`reviewer_signed_off` and reporting `signed_by_is_human` beside it rather than gating
on it.

Two places did not follow. `rules/cycle-implement.md` stated the precondition as
"a human's tick" **while citing the amended file**, and `score_alignment.py`'s own
docstring said "only a human can give it" above code that already accepted a judge.

The cost is not cosmetic. `/implement` reads that precondition, and honoured
literally it re-freezes every unattended run at `AWAITING_REVIEW` — precisely the
halt the amendment exists to end, reintroduced by prose.

This test is the mechanism. It does not judge the policy; it refuses the state where
one document says a human is required and the authority says otherwise.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
AUTHORITY = REPO / "skills" / "_kit-rules" / "alignment-threshold.md"

#: Wordings that assert a PERSON is required to sign. Narrow on purpose: the files
#: legitimately discuss humans elsewhere (the product sign-off in cycle-brainstorm
#: genuinely requires one), so only phrases tying a human to the alignment tick count.
HUMAN_ONLY = (
    re.compile(r"a human'?s tick", re.IGNORECASE),
    re.compile(r"only a human can give it", re.IGNORECASE),
    re.compile(r"ticked only by a human", re.IGNORECASE),
)

FOLLOWERS = (
    "rules/cycle-implement.md",
    "rules/cycle-plan.md",
    "skills/plan-alignment/scripts/score_alignment.py",
    "skills/implement/SKILL.md",
)


def test_the_authority_still_says_the_reviewer_need_not_be_a_person() -> None:
    """Guards the guard: if the amendment is ever reverted, this suite must be
    revisited rather than silently enforcing a rule that no longer holds."""
    body = AUTHORITY.read_text(encoding="utf-8")
    assert "Amended 2026-09-01" in body
    assert "need not be a person" in body


@pytest.mark.parametrize("rel", FOLLOWERS)
def test_no_follower_reasserts_a_human_only_signature(rel: str) -> None:
    path = REPO / rel
    if not path.is_file():
        pytest.skip(f"{rel} not present")
    body = path.read_text(encoding="utf-8")

    for pattern in HUMAN_ONLY:
        for match in pattern.finditer(body):
            line = body[: match.start()].count("\n") + 1
            # A file may QUOTE the old wording while explaining that it changed.
            window = body[max(0, match.start() - 400): match.end() + 400]
            if "2026-09-01" in window or "until" in window.lower():
                continue
            raise AssertionError(
                f"{rel}:{line} asserts an alignment signature must be human "
                f"({match.group(0)!r}), while alignment-threshold.md § Amended "
                f"2026-09-01 allows a judge. Honoured literally this re-freezes the "
                f"unattended loop at AWAITING_REVIEW."
            )


def test_the_scorer_gates_on_signed_off_not_on_being_human() -> None:
    """The behavioural half: the verdict must not turn on the signer being a person.

    `signed_by_is_human` exists to REPORT the weaker claim, not to refuse it.
    """
    src = (REPO / "skills" / "plan-alignment" / "scripts" / "score_alignment.py").read_text(
        encoding="utf-8")
    # The EXPRESSION, not prose describing it: the module docstring also contains a
    # sentence with both tokens, and matching it would test the comment.
    verdict_line = next(
        (ln for ln in src.splitlines()
         if "return" in ln and "ALIGNED" in ln and "AWAITING_REVIEW" in ln), "")
    assert verdict_line, "could not find the verdict expression"
    assert "reviewer_signed_off" in verdict_line
    assert "signed_by_is_human" not in verdict_line, (
        "the verdict must not gate on the signer being human — that is the amendment"
    )
