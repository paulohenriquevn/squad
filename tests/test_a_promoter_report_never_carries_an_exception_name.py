"""A report line naming a Python exception is the mechanism breaking, not measuring.

`_preflight` called `_verification(root)` and took no `root`. No module-level `root` existed
either, so the `NameError` was unconditional: **the verification-freshness check never ran
once, in any tree, since it was wired in** (#176).

It stayed invisible because the `except Exception` above it was written deliberately, with a
comment that reads:

    # noqa: BLE001 — a premise we cannot read is reported, not hidden

It failed safe, correctly. But what it PRINTS — `UNCHECKED` — is exactly what a consumer sees
when no verification record exists yet, which is an expected, harmless state. It does not read
as *this function is broken*. **The fail-safe worked and concealed the defect at the same
time.** Twelve lines above the call, a comment carefully explains that `stale` and
`unattributable` both mean the green a reader remembers is about a different tree — and the
check that produces those two states had never run.

The shape, named so it can be looked for: *a fail-safe that reports into the same vocabulary as
a legitimate state converts a defect into an expected condition*. It is not the recorded class
`a step that cannot fail loudly did not run` — this step DID fail loudly, into a channel where a
loud failure is indistinguishable from a quiet, normal one.

Origin: `_preflight`'s docblock says *"Extracted from `promote` … Pure code movement."* The
extraction dropped the parameter, and "pure code movement" is the claim that made nobody look.

So this test does not assert that `root` is passed. It asserts the general property: no line of
a promoter report may carry the name of a Python exception. That fails for `NameError`,
`AttributeError`, `KeyError` and anything a later refactor drops, without naming this bug.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "mechanisms" / "cycle"))

#: Any identifier ending in Error or Exception, the shape a traceback name takes.
_EXCEPTION_NAME = re.compile(r"\b[A-Z]\w*(?:Error|Exception)\b")


@pytest.fixture
def promoter():
    import promote_to_develop
    return promote_to_develop


def _report_lines(promoter, tmp_path: Path) -> list[str]:
    """Run `_preflight` over a tree with no verification record — the ordinary consumer state."""
    report = promoter.Report()

    #: `call(git, argv)` returns `(returncode, stdout)`. A harness returning some other
    #: shape makes `_preflight` raise before it reaches the branch under test, and the
    #: report would be empty — which passes the assertion below for the wrong reason.
    #: Measured while writing this: an object with `.returncode`/`.stdout` raised
    #: `TypeError: 'R' object is not subscriptable` at the first line of the function.
    answers = {
        "rev-parse --abbrev-ref HEAD": (0, promoter.SOURCE + "\n"),
        "status --porcelain": (0, ""),
    }

    def call(_runner, argv):
        return answers.get(" ".join(argv), (0, ""))

    promoter._preflight(call, object(), report, tmp_path)
    return list(report.lines)


def test_preflight_can_be_called_at_all(promoter, tmp_path: Path) -> None:
    """Without this, an exception in the harness would read as an empty report and pass."""
    assert _report_lines(promoter, tmp_path) is not None


def test_no_report_line_names_a_python_exception(promoter, tmp_path: Path) -> None:
    offenders = [ln for ln in _report_lines(promoter, tmp_path) if _EXCEPTION_NAME.search(ln)]
    assert offenders == [], (
        "a promoter report line carries a Python exception name, which means the mechanism "
        f"broke rather than measured: {offenders}")


def test_the_verification_check_is_reachable_from_preflight(promoter) -> None:
    """The narrow half: whatever `_preflight` needs to reach the check, it must have.

    Asserted against the signature rather than the call site, so a later refactor that moves
    the call still has to keep the parameter.
    """
    import inspect
    params = set(inspect.signature(promoter._preflight).parameters)
    source = inspect.getsource(promoter._preflight)
    for name in re.findall(r"_verification\((\w+)\)", source):
        assert name in params or hasattr(promoter, name), (
            f"`_preflight` calls `_verification({name})` and neither its parameters {sorted(params)} "
            f"nor the module define `{name}` — the call raises NameError on every run")
