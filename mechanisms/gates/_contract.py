"""What every gate in this directory agrees to, so a caller need not know each one.

WHY THIS EXISTS
===============
Thirty-three files here do the same job — take a tree, sweep it, report findings, exit
0/1/2 — and nothing stated that as a contract. So the root flag, the JSON shape and the
exit vocabulary were per-gate facts, and each of THREE callers carried the whole table:

  * `verify_ecosystem.py` held hand-written adapters, each knowing one sibling's flag
    (`--ecosystem-dir` vs `--root`) and its private JSON keys, each repeating its own
    "not installed — skipping" string and its own parse-failure branch — and they did
    not agree on that branch: one returned False on unparseable JSON, another NOT_RUN.
  * `tests/test_gates_say_what_they_examined.py` held `ROOT_FLAG`, a 22-entry
    hand-maintained name-to-flag map whose own comments record the cost: "check_xrefs
    had been check_* all along and was missed only because it spells its flag
    `--ecosystem-dir`; it had been run by hand dozens of times that week while sitting
    outside the empty-sweep protection."
  * `squad/cli/run_checks.py` documents refusing to glob and run for exactly this
    reason — "eight take --root, four --repo-root, three --project-root, one --repo,
    one --ecosystem-dir, one a positional" — and parses `.github/workflows/ci.yml`
    instead.

Measured: eight spellings of one question across 33 gates, and seven gates with none.

WHAT THE CONTRACT IS
====================
Every gate accepts ``--root PATH`` — the tree to sweep, defaulting to the repository
the gate lives in. A gate that already had another name for it KEEPS that name as an
alias, because a consumer's script may pass it; `--root` is what a caller can rely on
without knowing which gate it is talking to.

Exit codes, already the kit's vocabulary everywhere else:

    0   swept, nothing found
    1   swept, found something
    2   COULD NOT SWEEP — no tree, no tool, nothing to measure

2 is the one that matters and the one this kit is organised around: an inability to
measure is not a pass.

NOT an abstract base class. The gates carry zero ABCs, zero Protocols and zero
`NotImplementedError` across the directory, and that restraint is deliberate — an
inheritance hierarchy here would be read by nobody. This module declares the shape and
`check_gate_mechanisms.py` enforces it; the gates stay plain scripts.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from squad.cli.report import FINDING, OK, UNMEASURED  # after the bootstrap above

#: The exit vocabulary, under the names this directory already uses. ALIASES, not a
#: second declaration: `squad/cli/report.py` owns these numbers and argues for the
#: third one at length, and the first draft of this module restated them — two owners
#: of one vocabulary, which is the shape of drift rather than a copy of a constant.
#:
#: The names differ because the readers do. A gate says CLEAN/UNCHECKED about a sweep;
#: an `sq` verb says OK/UNMEASURED about a command. Same numbers, and now one source.
CLEAN = OK
UNCHECKED = UNMEASURED

__all__ = ["CLEAN", "FINDING", "UNCHECKED", "ROOT_FLAG", "ROOT_ALIASES", "add_root"]

#: The flag every gate accepts, whatever else it also accepts.
ROOT_FLAG = "--root"

#: The names gates used for the same argument before the contract existed. Kept as
#: aliases so a consumer's existing invocation keeps working — and listed HERE rather
#: than in each caller's private table, which is the duplication this closes.
ROOT_ALIASES: tuple[str, ...] = (
    "--repo-root", "--project", "--project-root", "--repo", "--ecosystem-dir",
)


def add_root(parser: argparse.ArgumentParser, *, default: Path | None = None,
             aliases: tuple[str, ...] = ()) -> None:
    """Give `parser` the contract's `--root`, plus this gate's historical spellings.

    `aliases` are this gate's own older names. They write to the same destination, so
    the gate's body reads `args.root` whichever one the caller passed.
    """
    parser.add_argument(
        ROOT_FLAG, *aliases, dest="root", type=Path, default=default or Path.cwd(),
        help="the tree to sweep (default: the working directory)")
