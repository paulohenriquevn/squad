"""Every gate that sweeps skills agrees on which of them are run artifacts.

`/review` writes `review-{slug}-{role}-knowledge` per reviewer, per run. They are
OUTPUT. `check_xrefs.py` knows this and exempts them, and `_is_auto_generated`'s
docstring states the reason the predicate was hoisted out of an inline check:

    It lives here rather than inline in a check because the first version exempted
    only `no_orphan_skills` and left `skill_has_cycle_contract` still charging — a
    half exemption that traded 26 WARN for 3 and looked like a fix. One definition,
    two consumers: that is what stops the next half from escaping.

The next half escaped. `check_skill_map.py` never learned it, and its own docstring
warns about exactly this shape while doing it. Measured on a consumer 2026-09-18,
post-install validation: 13 `missing_from_map` findings plus `missing_sop` and a
disagreeing count, every one of them about a file `/review` had just written. The
only available exemption is `rules/auxiliary-skills.txt`, which the consumer
maintains by hand — so the remedy on offer was to hand-list, after every review, the
artifacts the kit generates automatically.

Two consumers were never enough. The predicate now lives where the kit keeps what it
produces, and this test is written against the OWNER rather than against either
caller, so a fourth sweep inherits the answer instead of re-deriving it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "mechanisms" / "gates"))

from squad.paths import is_cycle_generated_skill  # noqa: E402

_GENERATED = [
    "review-b006-authorization-architecture-knowledge",
    "review-ci-coverage-domain-testing-knowledge",
    "review-composition-di-cross-validation-knowledge",
    "plan-slug-sepa-knowledge",  # retired producer; consumers still hold these
]
_AUTHORED = [
    "review", "implement", "backlog-review", "discover-plan",
    "frontend-design", "code-quality",
]


@pytest.mark.parametrize("name", _GENERATED)
def test_a_run_artifact_is_recognised_as_one(name: str) -> None:
    assert is_cycle_generated_skill(name) is True


@pytest.mark.parametrize("name", _AUTHORED)
def test_a_skill_somebody_wrote_is_not_a_run_artifact(name: str) -> None:
    assert is_cycle_generated_skill(name) is False


def test_both_gates_ask_the_owner_rather_than_carrying_a_copy() -> None:
    """The half that escaped did so because the answer was reachable from one gate.

    Asserted on the import rather than on behaviour: a gate that re-implements the
    predicate correctly today is a gate that drifts from it tomorrow, and drift is
    what produced the finding this test exists for.
    """
    for gate in ("check_xrefs.py", "check_skill_map.py"):
        text = (_REPO / "mechanisms" / "gates" / gate).read_text(encoding="utf-8")
        assert "is_cycle_generated_skill" in text, (
            f"{gate} sweeps skills and does not ask who owns the answer")
        # The EXPRESSION, not the word. A comment naming `-sepa-knowledge` to
        # explain why the exemption exists is the documentation working; a second
        # `endswith("-knowledge")` is a second definition, which is the thing.
        assert '.endswith("-knowledge")' not in text, (
            f"{gate} re-implements the predicate instead of importing it; that is "
            f"the half exemption the hoist out of an inline check was meant to end")


def test_the_map_gate_leaves_generated_skills_alone(tmp_path: Path) -> None:
    """The finding, end to end: a tree whose only unmapped skills are run artifacts."""
    from check_skill_map import check

    skills = tmp_path / "skills"
    (skills / "review").mkdir(parents=True)
    (skills / "review" / "SKILL.md").write_text("---\nname: review\n---\n", encoding="utf-8")
    (skills / "review" / "SOP.md").write_text("# sop\n", encoding="utf-8")
    generated = skills / "review-demo-architecture-knowledge"
    generated.mkdir()
    (generated / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")

    (skills / "map.md").write_text(
        "**1 skills.**\n\n| Skill | What |\n|---|---|\n| `review` | reviews |\n",
        encoding="utf-8")

    findings = check(tmp_path)
    assert findings == [], findings
