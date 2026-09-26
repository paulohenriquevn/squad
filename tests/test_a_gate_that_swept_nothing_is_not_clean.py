"""A sweep that matched no file may not report the tree clean.

Measured 2026-09-17, each against an empty directory:

    check_emitted_verdicts.py --root <empty>   exit 0  CLEAN  nothing swept: ...
    check_prose_write_paths.py --root <empty>  exit 0  CLEAN  nothing swept: ...
    check_orphan_verdicts.py --repo <empty>    exit 0  swept 0 cycle rule(s) ...

Two of the three define an `UNCHECKED = 2` constant in the same file and use it for
`root is not a directory` — so the vocabulary for "could not measure" was already
there, and the zero-file branch simply did not reach it. That is the defect this
repository names most often in other people's code: a checker that could not look at
its subject reporting a pass.

It is not hypothetical here. A gate's glob goes stale every time a directory is
renamed — `check_phase_emitters.SEARCH_GLOBS` still carried `scripts/*.py` after the
2026-09-01 rename to `mechanisms/`, matching zero files — and the failure mode of a
stale glob is silence, not noise. The gate keeps exiting 0 and nobody is told the
sweep stopped covering anything.

Skipping stays legal where it is declared. Reporting a sweep that read nothing as a
clean one does not.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: (script, flag used to point it at a tree). Each of these sweeps a directory tree
#: and prints a verdict; each was measured returning 0 over an empty one.
SWEEPERS = (
    ("check_emitted_verdicts.py", "--root"),
    ("check_prose_write_paths.py", "--root"),
    ("check_orphan_verdicts.py", "--repo"),
)


@pytest.mark.parametrize("script,flag", SWEEPERS)
def test_an_empty_tree_is_not_reported_clean(script: str, flag: str, tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "mechanisms" / "gates" / script), flag, str(tmp_path)],
        capture_output=True, text=True, timeout=120,
     check=False)
    combined = result.stdout + result.stderr
    assert result.returncode != 0, (
        f"{script} swept nothing and returned 0, which a caller cannot tell from a "
        f"tree it examined and found clean.\n{combined}"
    )
    assert "CLEAN" not in result.stdout.upper().split("NOTHING")[0], (
        f"{script} printed CLEAN over a sweep that read no file:\n{combined}"
    )


def test_the_phase_emitter_sweep_still_reaches_the_mechanisms_tree() -> None:
    """`scripts/` became `mechanisms/<family>/` on 2026-09-01 and the glob did not.

    A glob that matches nothing is the quietest way for a gate to stop working: the
    sweep still runs, still prints, still exits 0, and covers one directory fewer
    every time one is renamed. Measured: `scripts/*.py` matched 0 files while
    `mechanisms/` held 89 of them, none of which the sweep could see.
    """
    import importlib.util

    path = ROOT / "mechanisms" / "gates" / "check_phase_emitters.py"
    spec = importlib.util.spec_from_file_location("_cpe", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_cpe"] = mod
    spec.loader.exec_module(mod)

    matched = {g: len(list(ROOT.glob(g))) for g in mod.SEARCH_GLOBS}
    dead = [g for g, n in matched.items() if n == 0]
    assert not dead, f"these globs match nothing and sweep nothing: {dead} (all: {matched})"

    reaches_mechanisms = any(
        ROOT / "mechanisms" in p.parents for g in mod.SEARCH_GLOBS for p in ROOT.glob(g)
    )
    assert reaches_mechanisms, (
        "no glob reaches mechanisms/, where the cycle mechanisms live — the sweep "
        "cannot see the emitters it exists to find"
    )


def test_a_phase_sweep_with_no_contract_to_read_is_not_a_pass(tmp_path: Path) -> None:
    """Zero declared phases is an unreadable contract, not a satisfied one.

    `check_phase_emitters` reads `rules/cycle-phases.txt` for the phases it must find
    an emitter for. Against a tree without that file it printed
    `0 declared phase(s): 0 have an emitter, 0 silent, 0 emitted but undeclared` and
    returned 0 — the arithmetic is true and the conclusion is empty, because the
    denominator came from a file that was not there.

    This is the sibling of the glob defect above: there the corpus went missing, here
    the contract did. Both end in a gate that exits 0 having measured nothing.
    """
    result = subprocess.run(
        [sys.executable, str(ROOT / "mechanisms" / "gates" / "check_phase_emitters.py"),
         "--repo-root", str(tmp_path)],
        capture_output=True, text=True, timeout=120,
     check=False)
    assert result.returncode != 0, (
        "no cycle-phases.txt to read, and the gate still returned 0:\n"
        + result.stdout + result.stderr
    )
