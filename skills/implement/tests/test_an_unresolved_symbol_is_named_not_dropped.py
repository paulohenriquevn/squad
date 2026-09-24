"""A symbol the checker could not locate was discarded silently, so a summary read PASS over it.

`wiring_recheck` returns `symbols_resolved` and `pillar_a_fails`, and its own docstring states the
obligation it made impossible:

    "Symbol not found anywhere in the source tree" is distinguished from "symbol exists but has no
    caller" — only the latter is a true wiring FAIL; the former is an unresolved symbol the caller
    should report as inconclusive, never as PASS.

The loop then did `continue`, and `PillarARecheck` carried no field for them — so the caller was
told to report something it was never given. The count was derivable as `checked - resolved`; the
IDENTITIES were not, and the identities are the finding.

Measured on a consumer: `{"symbols_resolved": 17, "pillar_a_fails": 0, "status": "PASS"}` where the
17 were local variables — `s` (513 callers), `runs` (196), `body` (173), `r` (51) — plus `byName`, a
variable **that very diff deleted**, resolving with 5. The four exports of the file under review
were among the **11 discarded**, because the module lives in `scripts/`, outside
`PRODUCTION_DIR_NAMES = ("src", "lib", "packages")`. Run directly against one of those exports the
same checker returns HALT, exit 1 — two gates over one subject disagreeing, and the aggregate is the
one that reported green.

WHY NOT WIDEN THE TUPLE. `check_wiring.py:203-208` already records why narrowing is not simply
right: *"a repo that keeps its source at the root would report every symbol as unwired."* Widening
is a guess about other people's layouts, and enumerating directory names is a list that will be
short again. Naming the unresolved generalises to any layout.

WHY NOT MAKE A PARTIAL RESOLUTION INCONCLUSIVE. A derived or dynamic symbol name legitimately does
not resolve, and a gate that fires on ordinary work is one somebody switches off —
`code-quality-golden-rule.md § 4.1`. The all-unresolved case is ALREADY honest: both callers return
`N/A` at `symbols_resolved == 0`, with `run_validation` saying why in its own comment, *"so the gate
never launders an unverified claim."* What was missing is the PARTIAL case, where 17 resolved and 11
vanished.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SCRIPT = _ROOT / "skills" / "implement" / "scripts" / "wiring_recheck.py"


@pytest.fixture(scope="module")
def mod():
    sys.path.insert(0, str(_SCRIPT.parent))
    spec = importlib.util.spec_from_file_location(_SCRIPT.stem, _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[_SCRIPT.stem] = module
    spec.loader.exec_module(module)
    return module


def test_the_report_has_a_field_for_the_unresolved(mod) -> None:
    import dataclasses

    fields = {f.name for f in dataclasses.fields(mod.PillarARecheck)}

    assert "unresolved_symbols" in fields, (
        "the docstring tells the caller to report unresolved symbols as inconclusive and the "
        f"return type carries no field for them: {sorted(fields)}")


def test_an_unresolved_symbol_is_named(mod, monkeypatch, tmp_path: Path) -> None:
    """The identities, not only the count. `checked - resolved` was already derivable."""
    def _one(_root, symbol):
        if symbol == "findable":
            return {"callers_count": 3, "definition_only_excluded": ["x.ts"], "status": "PASS"}
        return {"callers_count": 0, "definition_only_excluded": []}

    monkeypatch.setattr(mod, "_run_one", _one)
    report = mod.recheck_pillar_a(tmp_path, {"findable", "ghost", "phantom"})

    assert report.symbols_resolved == 1, report
    assert set(report.unresolved_symbols) == {"ghost", "phantom"}, report.unresolved_symbols


def test_a_symbol_with_no_caller_is_still_a_fail_and_not_unresolved(mod, monkeypatch,
                                                                    tmp_path: Path) -> None:
    """The control. Exists with zero callers is a FAIL; the two must not merge back."""
    monkeypatch.setattr(mod, "_run_one", lambda _r, _s: {
        "callers_count": 0, "definition_only_excluded": ["src/a.ts"], "status": "FAIL"})

    report = mod.recheck_pillar_a(tmp_path, {"orphan"})

    assert report.symbols_resolved == 1
    assert report.pillar_a_fails == 1
    assert report.unresolved_symbols == ()


def test_a_symbol_the_subprocess_could_not_read_is_unresolved(mod, monkeypatch,
                                                              tmp_path: Path) -> None:
    """`_run_one` returning None is the flaky path the docstring already calls unresolved."""
    monkeypatch.setattr(mod, "_run_one", lambda _r, _s: None)

    report = mod.recheck_pillar_a(tmp_path, {"unreadable"})

    assert report.symbols_resolved == 0
    assert report.unresolved_symbols == ("unreadable",)


def test_every_symbol_is_accounted_for(mod, monkeypatch, tmp_path: Path) -> None:
    """The invariant that makes a partial result readable: nothing vanishes."""
    def _mixed(_root, symbol):
        if symbol.startswith("ok"):
            return {"callers_count": 2, "definition_only_excluded": ["src/a.ts"], "status": "PASS"}
        return {"callers_count": 0, "definition_only_excluded": []}

    monkeypatch.setattr(mod, "_run_one", _mixed)
    symbols = {"ok1", "ok2", "gone1", "gone2", "gone3"}
    report = mod.recheck_pillar_a(tmp_path, symbols)

    assert report.symbols_checked == len(symbols)
    assert report.symbols_resolved + len(report.unresolved_symbols) == report.symbols_checked, (
        f"resolved {report.symbols_resolved} + unresolved {len(report.unresolved_symbols)} "
        f"!= checked {report.symbols_checked} — a symbol went nowhere")
