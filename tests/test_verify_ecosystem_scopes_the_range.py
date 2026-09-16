"""The flag existed on the CLI for an hour before it reached the caller.

`check_contribution_conventions.py --introduced` was added, and the deadlock stayed
exactly where it was — because the pre-push chain does not go through that CLI. It goes
`.git/hooks/pre-push` -> `task quality:gates` -> `ecosystemvalidators` ->
`verify_ecosystem` -> `check(ecosystem_dir, "-40")`, hardcoded.

A fix that lands in code and not in the procedure that invokes it is half a fix. This
kit's own pipeline SKILL records that sentence about a different call site, and it
happened again one call site over, the same day.

The two callers ask genuinely different questions, which is why this is a parameter and
not a changed default:

  pre-push hook      may this push land          the introduced range
  standalone audit   does this repo conform      the last 40 commits

Measured on a consumer through the real chain: four violations in the window, THREE
already on `origin/workspace`, unreachable by amend. Nine verified commits sat behind it.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_GATE = (Path(__file__).resolve().parents[1] / "mechanisms" / "gates"
         / "verify_ecosystem.py")
_KIT = Path(__file__).resolve().parents[1]


def _run(*flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_GATE), "--ecosystem-dir", str(_KIT), *flags],
        capture_output=True, text=True, timeout=900)


def test_the_flag_reaches_the_aggregator_not_only_the_cli() -> None:
    out = _run("--introduced").stdout
    assert "Contribution conventions (what this push introduces)" in out, \
        "the aggregator still grades the last 40 commits for a pre-push caller"


def test_the_default_still_audits_history() -> None:
    """The audit caller keeps its reach. The fix separates two callers; it does not
    weaken one to serve the other."""
    assert "Contribution conventions (last 40 commits)" in _run().stdout


def test_the_label_never_names_a_range_it_did_not_grade() -> None:
    """The label was the string `(last 40 commits)` unconditionally, so an
    `--introduced` run would have reported a window it did not use — the same class as
    a gate claiming a universal property with no count behind it."""
    out = _run("--introduced").stdout
    assert "Contribution conventions (last 40 commits)" not in out


def test_the_help_names_the_flag() -> None:
    """A flag a caller cannot discover is a flag nobody passes — which is how the CLI
    half sat unused for an hour."""
    helped = subprocess.run([sys.executable, str(_GATE), "--help"],
                            capture_output=True, text=True, timeout=120)
    assert "--introduced" in helped.stdout
    assert "pre-push" in helped.stdout, "the help does not say which caller wants it"
