"""`public-copy-lint`, which had no test at all before the migration.

It reads what a stranger reads — README, PITCH, marketing and guide pages — and
warns about claims that measurement has not earned. Advisory by design: some of
these words are right sometimes, and a gate that blocks a README is one somebody
switches off.

Two checks are CONDITIONAL, and those are the ones worth pinning hardest: a
comparative claim is fine with a benchmark link, an SLA number is fine when
qualified as a target. If the excuse stopped working the hook would warn about
honest sentences, and the first fix anybody reaches for is to disable it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hook_harness import post_tool_use, run_hook  # noqa: E402


def _lint(path: str, content: str) -> str:
    result = run_hook("public-copy-lint",
                      post_tool_use("Edit", file_path=path, new_string=content))
    assert result.returncode == 0, "advisory: it must never block a README"
    return result.stdout


@pytest.mark.parametrize(("phrase", "marker"), [
    ("This is production-ready today.", "production-ready"),
    ("A production grade platform.", "production-ready"),
    ("Our battle-tested engine.", "battle-tested"),
    ("An enterprise-grade offering.", "enterprise"),
    ("It is a drop-in replacement for X.", "Drop-in replacement"),
    ("Zero downtime, always.", "Zero downtime"),
    ("Completely lock-in free.", "Lock-in"),
])
def test_an_unearned_claim_is_warned_about(phrase: str, marker: str) -> None:
    assert marker in _lint("README.md", f"# Project\n\n{phrase}\n")


def test_a_comparative_claim_needs_its_benchmark(tmp_path: Path) -> None:
    """The claim and the evidence have to travel together, or the reader gets
    only the half that flatters us."""
    assert "Faster than" in _lint("README.md", "# P\n\nFaster than Redis.\n")

    with_link = _lint("README.md", "# P\n\nFaster than Redis — see docs/benchmarks/x.md.\n")
    assert "Faster than" not in with_link


def test_an_sla_number_needs_its_qualifier() -> None:
    assert "SLA" in _lint("README.md", "# P\n\nWe deliver 99.99% uptime.\n")

    qualified = _lint("README.md", "# P\n\nDesigned to target 99.99% uptime.\n")
    assert "SLA" not in qualified


def test_honest_copy_produces_no_output() -> None:
    """A linter that warns about everything is one nobody reads."""
    clean = _lint("README.md",
                  "# Project\n\nDesigned for teams that measure before they claim.\n")

    assert clean.strip() == ""


@pytest.mark.parametrize("path", [
    "docs/benchmarks/redis.md",          # measuring IS the point here
    "docs/adr/0001-choose-x.md",
    "docs/exploration-reports/a.md",
])
def test_the_places_that_exist_to_report_measurement_are_exempt(path: str) -> None:
    assert _lint(path, "# R\n\nProduction-ready after the run.\n").strip() == ""


@pytest.mark.parametrize("path", ["src/main.py", "notes.md", "docs/internal/plan.md"])
def test_non_public_files_are_not_linted(path: str) -> None:
    """The rule is about what strangers read, not about how we write to ourselves."""
    assert _lint(path, "# x\n\nThis is production-ready and battle-tested.\n").strip() == ""


@pytest.mark.parametrize("path", ["README.md", "PITCH.md", "docs/marketing/launch.md",
                                  "docs/guides/start.md", "sub/dir/README.md"])
def test_every_declared_public_surface_is_covered(path: str) -> None:
    assert "battle-tested" in _lint(path, "# x\n\nOur battle-tested engine.\n")


def test_several_claims_are_all_reported() -> None:
    """Reporting only the first would send the writer back for each one in turn."""
    out = _lint("README.md",
                "# P\n\nProduction-ready, battle-tested, and a drop-in replacement.\n")

    assert out.count("[WARN]") >= 3
