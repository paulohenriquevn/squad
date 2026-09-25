#!/usr/bin/env python3
"""Independent re-verification of wiring pillar (a) by RE-RUNNING check_wiring.py.

The non-negotiable invariant of `/implement` is that every new public symbol has a
production caller (pillar a). Before this module, two consumers verified it two ways:

  - `mini_review.py` re-ran `check_wiring.py` per symbol (correct, independent).
  - `run_validation.py` (the FINAL gate) only READ the `wiring` field of the
    progress file — a value the LLM itself writes. A hallucinated or dishonest
    `"wiring": {"a": "pass"}` passed the final gate with zero verification.

This module is the single, shared, trust-nothing implementation: give it a set of
symbol names and it shells out to `check_wiring.py` for each, returning real counts.
"Symbol not found anywhere in the source tree" is distinguished from "symbol exists
but has no caller" — only the latter is a true wiring FAIL; the former is an
unresolved symbol the caller should report as inconclusive, never as PASS.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from check_wiring import production_search_roots

_CHECK_WIRING = Path(__file__).parent / "check_wiring.py"


@dataclass(frozen=True)
class PillarARecheck:
    symbols_checked: int           # symbols we attempted to verify
    symbols_resolved: int          # symbols actually found in the source tree
    pillar_a_fails: int            # resolved symbols with no production caller
    fail_symbols: tuple[str, ...]  # names of the failing symbols
    #: Symbols the checker could not LOCATE — not symbols with zero callers. The docstring above
    #: already tells the caller to report these as inconclusive and never as PASS, and there was
    #: no field to report them FROM: the loop dropped them with `continue`, so the caller was
    #: given an obligation and no way to meet it. The count was derivable as
    #: `checked - resolved`; the identities were not, and the identities are the finding.
    #:
    #: Measured on a consumer: a summary read `symbols_resolved: 17, pillar_a_fails: 0,
    #: status: PASS` where the 17 were local variables — `s` with 513 callers, `runs` with 196 —
    #: and the four exports of the file under review were among 11 dropped, because that module
    #: lives in `scripts/`, outside `PRODUCTION_DIR_NAMES`. Run directly against one of those
    #: exports the same checker returns HALT: two gates over one subject disagreeing, and the
    #: aggregate was the one reporting green (#190).
    unresolved_symbols: tuple[str, ...] = ()
    #: The directories the caller search covered, relative to the project root (`.` for the
    #: whole tree). Reported beside `unresolved_symbols`: "not located" only means something
    #: next to WHERE it was looked for.
    searched_roots: tuple[str, ...] = ()


def recheck_pillar_a(project_root: Path, symbols: set[str]) -> PillarARecheck:
    """Run check_wiring.py pillar (a) for each symbol; aggregate honestly.

    Never raises: a per-symbol subprocess or JSON error skips that symbol (treated
    as unresolved), so a flaky check on one symbol cannot mask the others.
    """
    if not _CHECK_WIRING.exists():
        return PillarARecheck(len(symbols), 0, 0, (), tuple(sorted(symbols)))
    searched = _searched_roots(project_root)

    resolved = 0
    fails: list[str] = []
    #: RECORDED, not dropped. Every symbol leaves this loop in exactly one bucket, and
    #: `test_every_symbol_is_accounted_for` asserts the arithmetic — a symbol that goes nowhere is
    #: how `symbols_resolved: 17` came to look like a measurement over a set of 28.
    unresolved: list[str] = []
    for sym in sorted(symbols):
        pillar = _run_one(project_root, sym)
        if pillar is None:
            # The flaky path the docstring already calls unresolved: a subprocess or JSON error
            # on one symbol must not mask the others, and must not pass for a clean answer.
            unresolved.append(sym)
            continue
        callers_count = pillar.get("callers_count", 0)
        def_only = pillar.get("definition_only_excluded", [])
        # callers==0 AND no definition site found => symbol not detectable in the
        # tree (wrong/derived name). Unresolved, not a fail.
        if callers_count == 0 and not def_only:
            unresolved.append(sym)
            continue
        resolved += 1
        if pillar.get("status") == "FAIL":
            fails.append(sym)

    return PillarARecheck(
        symbols_checked=len(symbols),
        symbols_resolved=resolved,
        pillar_a_fails=len(fails),
        fail_symbols=tuple(fails),
        unresolved_symbols=tuple(unresolved),
        searched_roots=searched,
    )


def _searched_roots(project_root: Path) -> tuple[str, ...]:
    """The scope `check_wiring.py` searches, from the function that decides it — a copy of the
    rule here would be a second answer to "where are callers looked for"."""
    return tuple(
        str(root.relative_to(project_root)) if root != project_root else "."
        for root in production_search_roots(project_root)
    )


def _run_one(project_root: Path, symbol: str) -> dict | None:
    """Return the pillar (a) payload from check_wiring.py for one symbol, or None."""
    try:
        result = subprocess.run(
            ["python3", str(_CHECK_WIRING), "--symbol", symbol,
             "--project-root", str(project_root)],
            capture_output=True, text=True, timeout=30,
         check=False)
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
    if result.returncode == 2 or not result.stdout.strip():
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    for pillar in payload.get("pillars", []):
        if pillar.get("pillar") == "a_static_caller":
            return pillar
    return None
