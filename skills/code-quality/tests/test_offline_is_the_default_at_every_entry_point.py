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

import argparse
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_RUN = _SCRIPTS / "run_code_quality.py"
_INVOKE = _SCRIPTS / "cq_invoke.py"


def test_the_direct_cli_offers_an_explicit_network_opt_in() -> None:
    helped = subprocess.run([sys.executable, str(_RUN), "--help"],
                            capture_output=True, text=True, timeout=180, check=False)
    assert "--network" in helped.stdout, \
        "there is no way to ask for the networked path knowingly"
    assert "--no-network" in helped.stdout, \
        "an existing caller's flag disappeared"


# The three tests below used to read these two files as TEXT and match regexes against
# them — `re.search(r"if not args\.network:\s*\n\s*args\.no_network = True", source)` and
# `'cmd.append("--network")' in source`. That fails on a reformatting that changes
# nothing and passes on a rewrite that changes everything, which is the wrong way round
# for the one file whose subject is what the code DOES by default.


def test_the_default_forces_offline_for_a_verdict_not_only_a_baseline() -> None:
    sys.path.insert(0, str(_SCRIPTS))
    from run_code_quality import settle_network_mode

    args = argparse.Namespace(write_baseline=False, network=False, no_network=False)
    settle_network_mode(args)

    assert args.no_network is True, "the verdict path can still reach the proxy by default"


def test_the_baseline_path_still_forces_offline() -> None:
    """The older guarantee must survive the wider one: a baseline recorded with the
    network on is worthless, and that is independent of `--network`."""
    sys.path.insert(0, str(_SCRIPTS))
    from run_code_quality import settle_network_mode

    args = argparse.Namespace(write_baseline=True, network=True, no_network=False)
    settle_network_mode(args)

    assert args.no_network is True


def _wrapper_command(monkeypatch, env: dict[str, str]) -> list[str]:
    """The argv `cq_invoke` builds, captured instead of executed."""
    sys.path.insert(0, str(_SCRIPTS))
    import cq_invoke

    seen: list[list[str]] = []

    class _Done:
        returncode = 0
        stdout = "{}"
        stderr = ""

    def _capture(cmd, **kw):
        seen.append(list(cmd))
        return _Done()

    for name in ("CODE_QUALITY_NETWORK", "CODE_QUALITY_NO_NETWORK"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(cq_invoke.subprocess, "run", _capture)
    cq_invoke.invoke("a-slug", _SCRIPTS.parents[2])
    return seen[0] if seen else []


def test_the_wrapper_asks_for_the_network_explicitly(monkeypatch) -> None:
    """Passing nothing used to mean "networked" and now means "offline". An opt-in that
    silently stopped opting in is worse than one that never existed."""
    cmd = _wrapper_command(monkeypatch, {"CODE_QUALITY_NETWORK": "1"})

    assert "--network" in cmd, f"CODE_QUALITY_NETWORK=1 would silently run offline: {cmd}"


def test_the_wrapper_is_offline_with_no_environment(monkeypatch) -> None:
    cmd = _wrapper_command(monkeypatch, {})

    assert "--no-network" in cmd, cmd


def test_asking_for_both_gets_offline(monkeypatch) -> None:
    """An install that sets both is asking for offline twice, not contradicting itself."""
    cmd = _wrapper_command(monkeypatch, {"CODE_QUALITY_NETWORK": "1",
                                         "CODE_QUALITY_NO_NETWORK": "1"})

    assert "--no-network" in cmd and "--network" not in cmd, cmd
