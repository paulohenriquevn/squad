"""What counts as measurable is one piece of knowledge and had two definitions.

`score_alignment._MEASURABLE_RE` and `check_criterion_executability.MEASURABLE_PATTERNS`
both answer "does this requirement carry something somebody can fail". They were written
apart and had already drifted: measured 2026-09-24, `the command exits 0` was measurable
to one and not to the other. One of them had been widened that same week — `LoC`,
`lines`, `≤`, `≥`, `exits` — by an author who did not know the other existed.

The kit makes this argument about its own roster: "ONE parser, imported by everything
that reads the table. Two readers of the same table drift apart silently." It is the
same argument, and this is the same failure.

The vocabulary was also latency, throughput and size — `ms`, `rps`, `MB`, `p95`. A
structural change has no unit in that list, so the only reachable form was a comparison,
and the only comparison an author can write BEFORE implementing is a diff budget: a
number nobody can know before implementing. Reported by a peer session that paid six
panel rounds for it, three of whose refusals were about invented line budgets and none
about the item. The remaining requirements — `exactly 1 prop`, `0 dependencies added` —
scored as unmeasurable, so removing the invented budget LOWERED the score. The scorer
penalised the honest requirement and rewarded the inventable one.

That session's own measurement points at the fix: all six refusals were on
non-behavioural criteria, and no criterion naming observable behaviour was ever refused.
So the vocabulary to add is declarations and behaviour, not more units of measure.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("", "skills/plan-alignment/scripts", "skills/plan-confidence/scripts"):
    sys.path.insert(0, str(_ROOT / _p) if _p else str(_ROOT))

from squad.measurability import is_measurable  # noqa: E402

#: (text, measurable). The first four are the control the reporting session recorded.
CASES = (
    ("exactly 1 field and exactly 1 prop", True),
    ("0 dependencies added", True),
    ("<= 20 changed lines", True),
    ("2 call sites updated", True),
    ("no more than 40 added lines", True),
    ("the command exits 0", True),
    ("p95 under 200ms at 1000 rps", True),
    ("3 exports removed", True),
    # The DoD the reporting session asked for: widening must not become "accepts prose".
    ("the system should be fast", False),
    ("improves clarity", False),
    ("the component is easier to reason about", False),
    ("dependencies are kept low", False),
    ("props are documented", False),
)


def test_the_shared_definition_answers_every_case() -> None:
    wrong = [(text, want) for text, want in CASES if is_measurable(text) is not want]
    assert not wrong, "\n".join(
        f"{text!r}: expected {'measurable' if want else 'NOT measurable'}"
        for text, want in wrong)


def test_prose_without_a_number_is_never_measurable() -> None:
    """Stated separately because it is the property the widening could destroy.

    A declaration count is only a measurement when it carries the count. `props are
    documented` names the same noun as `exactly 1 prop` and states nothing to fail.
    """
    for text, want in CASES:
        if not want:
            assert not is_measurable(text), text


def test_both_readers_answer_from_the_shared_definition() -> None:
    """The anti-drift property, and the reason this module exists.

    Asserted through each reader's own public entry point rather than by comparing
    imports: a reader that imported the module and kept its own regex would pass an
    import check and still disagree.

    The criterion reader is deliberately BROADER — see the next test. It agrees on every
    case here because these are the numeric core, which is the half that drifted.
    """
    from check_criterion_executability import _has_measurable_object
    from score_alignment import _is_measurable_requirement

    for text, want in CASES:
        assert _has_measurable_object(text) is want, f"plan-confidence: {text!r}"
        assert _is_measurable_requirement(text) is want, f"plan-alignment: {text!r}"


def test_the_criterion_reader_is_broader_and_says_by_how_much() -> None:
    """One definition was the wrong answer, and the measurement said so.

    `equals <x>`, `contains <x>`, `returns true` and a backticked command make an
    ACCEPTANCE CRITERION measurable: it is written to be executed and each names
    something a runner compares. None of them makes a REQUIREMENT measurable, and a
    backtick around any word would have made every requirement mentioning code pass.

    So the shared module holds the numeric core — the half that had two definitions and
    drifted — and this reader adds four shapes the other never had. Pinned here so the
    extra set stays a decision somebody made rather than a difference that reappeared.
    """
    from check_criterion_executability import _CRITERION_ASSERTIONS, MEASURABLE_PATTERNS

    from squad.measurability import PATTERNS as SHARED

    assert MEASURABLE_PATTERNS == SHARED + _CRITERION_ASSERTIONS
    assert len(_CRITERION_ASSERTIONS) == 4

    # Each extra must actually discriminate, or it is documentation of nothing.
    from check_criterion_executability import _has_measurable_object
    from score_alignment import _is_measurable_requirement
    for text in ("equals the expected JSON shape", "contains the header",
                 "returns true", "`curl /healthz` succeeds"):
        assert _has_measurable_object(text), f"criterion reader lost: {text!r}"
        assert not _is_measurable_requirement(text), (
            f"requirement reader gained a shape it never had: {text!r}")


def test_every_example_a_refusal_prints_is_itself_measurable() -> None:
    """A refusal that quotes an example the reader then gets refused for is worse than none.

    One example per pattern, so a pattern with no example — or one whose example stopped
    matching — fails here rather than in a caller's next run.
    """
    from squad import measurability

    assert len(measurability.EXAMPLES) == len(measurability.PATTERNS)
    for example, pattern in zip(measurability.EXAMPLES, measurability.PATTERNS):
        assert re.search(pattern, example, re.IGNORECASE), (example, pattern)
