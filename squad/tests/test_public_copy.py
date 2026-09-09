"""The claims a README may not make, asked of the module both hooks read.

`public-copy-lint` asks after an edit, `stop-validation` at the end of the
session. They carried separate lists until 2026-09-08, and the shorter one was
the one that ran last: seven of nine checks never reached the Stop gate.

Two checks are CONDITIONAL, and those are the ones worth pinning hardest. A
comparative claim is honest WITH a benchmark link; an SLA number is honest when
qualified as a target. If an excuse stopped working the hooks would warn about
honest sentences, and the first fix anybody reaches for is to switch them off.
"""
from __future__ import annotations

import pytest

from squad.public_copy import CHECKS, is_public, warnings


@pytest.mark.parametrize(("text", "marker"), [
    ("This is production-ready today.", "production-ready"),
    ("A production grade platform.", "production-ready"),
    ("Our battle-tested engine.", "battle-tested"),
    ("An enterprise-grade offering.", "enterprise"),
    ("A drop-in replacement for X.", "Drop-in replacement"),
    ("Zero downtime, always.", "Zero downtime"),
    ("Completely lock-in free.", "Lock-in"),
    ("Faster than Redis.", "Faster than"),
    ("We deliver 99.99% uptime.", "SLA"),
])
def test_a_claim_nothing_backs_is_reported(text: str, marker: str) -> None:
    assert any(marker in w for w in warnings(text)), f"{text!r} passed unremarked"


def test_a_comparative_claim_is_honest_with_the_artifact_beside_it() -> None:
    assert warnings("Faster than Redis.")
    assert not warnings("Faster than Redis — see docs/benchmarks/redis.md.")


def test_an_sla_number_is_honest_when_it_is_stated_as_a_target() -> None:
    assert warnings("We deliver 99.99% uptime.")
    assert not warnings("Designed to target 99.99% uptime.")


def test_zero_downtime_is_honest_when_its_scope_is_named() -> None:
    assert warnings("Zero downtime, always.")
    assert not warnings("Minor upgrades are zero-downtime; major ones have "
                        "measured downtime.")


def test_the_excuse_is_looked_for_across_the_whole_text() -> None:
    """The evidence rarely sits in the same sentence as the claim, and the hooks
    hand over a whole file precisely so it does not have to."""
    assert not warnings("# Thing\n\nMeasured in docs/benchmarks/x.md.\n\n"
                        "Squad is faster than the manual process.\n")


def test_every_claim_in_a_paragraph_is_reported_not_just_the_first() -> None:
    """Reporting one at a time sends the writer back for each in turn."""
    found = warnings("Production-ready, battle-tested, and a drop-in replacement.")
    assert len(found) >= 3


def test_honest_copy_produces_nothing() -> None:
    assert warnings("Alpha. The pipeline and its gates are covered by tests; no "
                    "item has yet run end to end through this version.") == []


@pytest.mark.parametrize("path", [
    "README.md", "sub/dir/README.md", "PITCH.md",
    "docs/marketing/launch.md", "docs/guides/start.md",
])
def test_what_a_stranger_reads_is_linted(path: str) -> None:
    assert is_public(path)


@pytest.mark.parametrize("path", ["src/main.py", "notes.md", "docs/internal/plan.md"])
def test_what_we_write_to_ourselves_is_not(path: str) -> None:
    """The rule is about claims made to people who cannot check them."""
    assert not is_public(path)


@pytest.mark.parametrize("path", [
    "docs/benchmarks/redis.md",
    "docs/adr/0001-choose-x.md",
    "docs/ADR/0025-hierarchy.md",
    "docs/exploration-reports/a.md",
])
def test_the_places_that_exist_to_REPORT_measurement_are_exempt(path: str) -> None:
    """A benchmark report exists to say what was measured. Linting it for
    confidence would be backwards."""
    assert not is_public(path)


def test_each_check_says_what_to_write_instead() -> None:
    """A lint that only forbids leaves the writer guessing, and guessing here
    produces the next banned phrase."""
    for check in CHECKS:
        assert len(check.message) > 60, f"{check.message!r} states no alternative"
