"""A gate that prints the wrong list teaches a reader that its messages cannot be trusted.

`check_concurrency_tests.py` refuses a task whose `#### Concurrency tests` subsection carries
no race-aware signal, and names the accepted signals so the reader can fix it. It named
`CONCURRENCY_SIGNALS` — the 39 tokens that DETECT that a task involves concurrency at all
(`mutex`, `SharedArrayBuffer`) — while acceptance is decided against `RACE_TEST_SIGNALS`, the
14 that describe a race-aware TEST (`go test -race`, `loom::`, `pytest-asyncio`). No overlap in
purpose. A reader who added a printed token failed again (#175).

Same class as `rules/code-quality-allowlist.txt` (#343), where the header documented a format
the parser never accepted and following the documentation produced a WORSE outcome than adding
nothing.

THE SHARPER HALF. `_accepted_signals()` exists to stop exactly this, and says so:

    DERIVED from `CONCURRENCY_SIGNALS`, never restated. The refusal used to carry a
    hand-written parenthetical naming six — "(race/loom/concurrent/parallel/
    atomic-counter/cancellation)" — while the matcher held thirty-nine.

Every one of those six is a `RACE_TEST_SIGNALS` member. **The frozen parenthetical was naming
the right list.** The fix that removed the drift risk pointed the renderer at the wrong
constant, so a mechanism built to stop a message from lying made it lie in a new way — while
asserting in the same docstring that it now derives rather than restates.

So the test below does not check WHICH constant is used. It checks the property that matters:
every token the message prints must be accepted by the decider. That fails whichever constant
a later edit points the renderer at, which is the only form that closes the class.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_ROOT / "skills" / "plan-confidence" / "scripts"))

import check_concurrency_tests as gate  # noqa: E402 — post-bootstrap import


def _printed_tokens() -> list[str]:
    rendered = gate._accepted_signals()
    return [t.strip() for t in rendered.split("·") if t.strip()]


def test_the_message_prints_something() -> None:
    """Without this, the parametrised test below runs over nothing and proves nothing."""
    assert _printed_tokens(), "the refusal names no signals; this test lost its subject"


@pytest.mark.parametrize("token", _printed_tokens(), ids=lambda t: t)
def test_a_token_the_refusal_prints_is_accepted_by_the_decider(token: str) -> None:
    r"""The invariant, independent of which constant the renderer reads.

    Both deciders, because `_race_aware` accepts either — `ESCAPE_RE.search(sub) or
    RACE_TEST_SIGNALS_RE.search(sub)`. Asserting against one alone would reject the escape
    marker, which is a legitimate way to pass.

    `<name>` is the renderer's placeholder for `\w+`: a pattern like `Atomics\.\w+` needs a
    word after the dot, and printing `Atomics.` alone would name a token that does not satisfy
    its own pattern. The substitution is what a reader does when they write a real method name.
    """
    written = token.replace("<name>", "wait")
    accepted = gate.RACE_TEST_SIGNALS_RE.search(written) or gate.ESCAPE_RE.search(written)
    assert accepted, (
        f"the refusal tells a reader `{token}` is an accepted signal and neither "
        f"RACE_TEST_SIGNALS_RE nor ESCAPE_RE — the two the decider consults — matches "
        f"`{written}`. Following the message cannot fix the finding.")


def test_the_escape_is_offered_alongside_the_signals() -> None:
    """There are two ways to pass. A message naming one hides the other.

    `(none — single-threaded)` is the honest answer for a task with no concurrency, and a
    reader choosing between the two needs both in front of them.
    """
    rendered = gate._accepted_signals()
    assert "single" in rendered or "none" in rendered.lower(), (
        "the escape marker is a way to pass and the message does not mention it")


def test_the_two_lists_are_not_interchangeable() -> None:
    """The premise of this whole file, asserted so it cannot quietly stop being true."""
    detects = set(gate.CONCURRENCY_SIGNALS)
    accepts = set(gate.RACE_TEST_SIGNALS)
    assert detects != accepts, "the two constants converged; this test lost its subject"
    only_detects = [p for p in detects if not gate.RACE_TEST_SIGNALS_RE.search(
        p.replace(r"\b", "").replace("\\", ""))]
    assert only_detects, (
        "every detection token is also an acceptance token, which would make the defect "
        "unobservable — re-read the constants before deleting this test")
