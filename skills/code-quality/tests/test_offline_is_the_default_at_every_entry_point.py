"""Which entry point you used is not a property of the code under test.

`cq_invoke.py` made offline the default on 2026-09-13, with the reasoning written out:
the Go symbol detector resolves imports against the module proxy, two consecutive
networked runs of one tree reported 4818 then 4777 fabrications against ONE offline, and
"a gate whose answer depends on what a proxy said that second is not a gate".

That reasoning was applied to the wrapper and not to the thing it wraps. Anyone typing
`run_code_quality.py` by hand still got the networked path.

Measured on a consumer 2026-09-16, one repository, minutes apart:

    with network      PASS_WITH_CAVEATS   hard_caps: ['symbol_fab_unverifiable_go']
    --no-network      PASS_WITH_CAVEATS   hard_caps: none

That cap is neither baselinable (its `file_path` is `.`) nor dismissible by ADR, so a
run that happened to reach the proxy held the work and a run that did not released it.

Third half-fix of the same day: a repair that lands in code and not in every caller of
it. The two files change together here for that reason.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_RUN = _SCRIPTS / "run_code_quality.py"
_INVOKE = _SCRIPTS / "cq_invoke.py"


def test_the_direct_cli_offers_an_explicit_network_opt_in() -> None:
    helped = subprocess.run([sys.executable, str(_RUN), "--help"],
                            capture_output=True, text=True, timeout=180)
    assert "--network" in helped.stdout, \
        "there is no way to ask for the networked path knowingly"
    assert "--no-network" in helped.stdout, \
        "an existing caller's flag disappeared"


def test_the_default_forces_offline_for_a_verdict_not_only_a_baseline() -> None:
    source = _RUN.read_text(encoding="utf-8")
    assert re.search(r"if not args\.network:\s*\n\s*args\.no_network = True", source), \
        "the verdict path can still reach the proxy by default"


def test_the_wrapper_asks_for_the_network_explicitly() -> None:
    """Passing nothing used to mean "networked" and now means "offline". An opt-in that
    silently stopped opting in is worse than one that never existed."""
    source = _INVOKE.read_text(encoding="utf-8")
    assert 'cmd.append("--network")' in source, \
        "CODE_QUALITY_NETWORK=1 would silently run offline"


def test_the_baseline_path_still_forces_offline() -> None:
    """The older guarantee must survive the wider one: a baseline recorded with the
    network on is worthless, and that is independent of `--network`."""
    source = _RUN.read_text(encoding="utf-8")
    assert re.search(r'write_baseline", False\):\s*\n\s*args\.no_network = True', source)
