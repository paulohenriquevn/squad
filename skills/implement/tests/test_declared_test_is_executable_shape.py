"""A test function DECLARED is stronger evidence than a test function NAMED.

`_has_named_test_shape` already credits `RED: TestFoo` — the name alone. But the
function-shape patterns required an arrow or a verb after the parentheses, so
`def test_foo(tmp_path):` — how a Python test is actually written — matched none of
them. The same section's assertions did not match either: `[\\w.\\[\\]]+` cannot cross a
parenthesis and the call pattern required the operator adjacent to `)`, so
`assert f(x).attr == y` was invisible.

Measured on a consumer 2026-09-16 across 186 tasks carrying a TDD section: 29 blocked,
of which 6 carried a real declaration or a chained assertion and were reported as prose.
The remaining 23 are genuinely shapeless — most are a final `T4.1 — verify, CHANGELOG,
commit`, which is not a test task. The gate was right about those, and widening stops
here rather than reaching for them.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_tdd_shape import _has_assertion_shape, _has_test_fn_shape

_REAL_BLOCK = '''**Two RED tests, and the second is the one that makes the first safe.**

```python
def test_the_signature_spelling_is_not_invisible(tmp_path):
    b = _signed_brief(tmp_path)
    assert score_alignment(b).verdict == "AWAITING_REVIEW"
```
'''


def test_a_declared_python_test_is_a_shape() -> None:
    assert _has_test_fn_shape(_REAL_BLOCK), \
        "a real `def test_` inside a fence was reported as prose"


def test_a_declared_go_test_is_a_shape() -> None:
    assert _has_test_fn_shape("some prose\n\nfunc TestThing(t *testing.T) {\n")


def test_an_assertion_over_a_call_result_is_a_shape() -> None:
    assert _has_assertion_shape('assert score_alignment(b).verdict == "AWAITING_REVIEW"')
    assert _has_assertion_shape('assert parse(raw)["status"] == 200')


def test_prose_that_merely_mentions_the_words_is_not_a_shape() -> None:
    """The widening must not credit a sentence for containing `def` and `test`."""
    assert not _has_test_fn_shape("we should test foo and def things eventually")
    assert not _has_assertion_shape("the caller should assert the result is correct")


def test_the_anchor_matches_below_the_first_line() -> None:
    """The pattern anchors at line start, and a TDD block always has prose above its
    fence. Without MULTILINE the anchor matched only when the declaration opened the
    section, which never happens."""
    assert _has_test_fn_shape("intro\nmore intro\ndef test_x(a):\n")
