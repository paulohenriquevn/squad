"""The fenced-code regex was redefined in eleven scripts, in two forms.

    ^```[^\\n]*\\n.*?^```           five scripts — backtick fences only
    ^(```|~~~)[^\\n]*\\n.*?^\\1     six scripts — backticks OR tildes

A plan whose example block used `~~~` — valid CommonMark, and what an author reaches for
when the block itself contains backticks — was masked by six readers and read as prose
by the other five. The five that could not see the fence counted every word inside it:
a `should` in a quoted example became a weak imperative, a `SELECT *` in a sample became
a smell. Same document, different score, depending on which checker asked.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from squad.markdown import (  # noqa: E402 — post-bootstrap import
    FENCED_CODE_RE,
    strip_code,
)

#: Anything compiling its own fenced-code pattern rather than importing the owner.
_OWN_PATTERN = re.compile(r"re\.compile\(\s*r?\"[^\"]*```[^\"]*\"")


@pytest.mark.parametrize("fence", ["```", "~~~", "````"])
def test_every_fence_form_is_masked(fence: str) -> None:
    document = f"before\n{fence}py\nshould not be counted\n{fence}\nafter\n"

    masked = strip_code(document)

    assert "should not be counted" not in masked, f"{fence} was read as prose"
    assert "before" in masked and "after" in masked


def test_line_numbers_survive_the_masking() -> None:
    """Every caller reports a line number; deleting a block moves findings onto lines
    the author never wrote."""
    document = "one\n```\ntwo\nthree\n```\nfour\n"

    assert strip_code(document).count("\n") == document.count("\n")


def test_a_longer_fence_closes_on_its_own_run() -> None:
    """Four backticks wrapping a three-backtick example: the inner one is content."""
    document = "before\n````\n```\ninner\n```\n````\nafter\n"

    masked = strip_code(document)

    assert "inner" not in masked
    assert "after" in masked, "the outer fence closed on the inner run"


def test_no_checker_compiles_its_own_fence_pattern() -> None:
    offenders: list[str] = []
    for path in sorted((_ROOT / "skills").rglob("scripts/*.py")):
        source = path.read_text(encoding="utf-8", errors="replace")
        if "FENCED_CODE_RE" not in source and "_FENCED_CODE_RE" not in source:
            continue
        if _OWN_PATTERN.search(source):
            offenders.append(str(path.relative_to(_ROOT)))

    assert offenders == [], (
        "these define a fenced-code pattern of their own instead of importing "
        f"`squad.markdown`: {offenders}")


def test_the_owner_matches_both_forms_directly() -> None:
    assert FENCED_CODE_RE.search("```\nx\n```\n")
    assert FENCED_CODE_RE.search("~~~\nx\n~~~\n")
