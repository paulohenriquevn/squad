"""A BLOCKED report from the PLAN phase halted nothing, and it is the second such omission.

`squad_boss.HALT_DIRS` maps a phase's output directory to its phase, and `plans` was absent while
`rules/cycle-phases.txt` declares `plan`. Two contracts assert the halt works — `cycle-plan.md`
says a BLOCKED report blocks downstream, `cycle-maintenance.md` says SELECT holds the item until
the file is gone — and both were true for the four directories named and false for the plan phase.

Measured by a consumer with one real file moved between two directories:

    .squad/records/plans/B-271-…-BLOCKED.md         halt_reports -> does not find it
                                                    SELECT -> re-offers the halted item
    .squad/records/maintenance-runs/…-BLOCKED-….md  halt_reports -> finds it
                                                    SELECT -> withholds, naming the cause

Same file, same name. The gap was the directory set.

WHY THE SET IS THE DEFECT AND NOT THE ENTRY. `squad_boss` records the FIRST omission in its own
comment: `maintenance-runs` was missing, so *"a BLOCKED report from the cycle that ORCHESTRATES the
queue was invisible to the reader of that queue"*, measured by a consumer on 2026-08-31. A literal
set that has dropped two of the phases it covers is the shape.

AND THERE WERE TWO PARTIAL MAPS OF ONE RELATION, DISJOINT. `panel_brief.PHASE_SOURCES` names the
artifact directory for `design`, `discover`, `plan`, `alignment`; `HALT_DIRS` named
`implement`, `review`, `release`, `maintenance`. Neither complete, no overlap, and `plan` present
in one and missing from the other — which is how the defect was possible at all. This file holds
them to each other where they meet, and holds the halt map to the phase list that declares the
phases.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "mechanisms" / "cycle"))
sys.path.insert(0, str(_ROOT / "skills" / "backlog-review" / "scripts"))

PHASES_FILE = _ROOT / "rules" / "cycle-phases.txt"


def _declared_phases() -> list[str]:
    out = []
    for line in PHASES_FILE.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if "|" in line:
            out.append(line.split("|", 1)[0].strip())
    return [p for p in out if p]


def test_the_phase_list_was_read() -> None:
    """Without this, every assertion below runs over an empty list and passes."""
    assert len(_declared_phases()) > 5, _declared_phases()


def test_the_halt_map_covers_every_phase_that_writes_a_record() -> None:
    import squad_boss

    covered = set(squad_boss.HALT_DIRS.values())
    declared = set(_declared_phases())
    not_covered = declared - covered - set(getattr(squad_boss, "PHASES_WITHOUT_A_HALT_REPORT", {}))

    assert not_covered == set(), (
        f"these phases are declared in rules/cycle-phases.txt, write no halt directory in "
        f"HALT_DIRS, and are not declared as writing no halt report: {sorted(not_covered)}. "
        f"A BLOCKED report from any of them halts nothing.")


def test_no_declared_exemption_names_a_phase_that_left() -> None:
    """The other direction: an exemption for a phase that no longer exists stopped applying."""
    import squad_boss

    exempt = set(getattr(squad_boss, "PHASES_WITHOUT_A_HALT_REPORT", {}))
    stale = exempt - set(_declared_phases())

    assert stale == set(), f"exempt from a halt report and no longer a declared phase: {sorted(stale)}"


def test_the_two_maps_of_one_relation_agree_where_they_meet() -> None:
    """`PHASE_SOURCES` and `HALT_DIRS` both say where a phase writes. They must not disagree."""
    import squad_boss
    from panel_brief import PHASE_SOURCES

    halt = {phase: directory for directory, phase in squad_boss.HALT_DIRS.items()}
    disagreements = []
    for phase, source in PHASE_SOURCES.items():
        if phase not in halt:
            continue
        artifact = str(source["artifacts"][0])
        if f"/{halt[phase]}/" not in artifact and not artifact.endswith(f"/{halt[phase]}"):
            disagreements.append(f"{phase}: panel says {artifact!r}, halt map says {halt[phase]!r}")

    assert disagreements == [], disagreements


def test_a_blocked_plan_report_withholds_the_item(tmp_path: Path) -> None:
    """End to end, because `_item_of` and `halt_reports` exercised apart is the gap this kit
    measured in its own #187 fix — each half tested, the chain never run."""
    import squad_boss

    records = tmp_path / ".squad" / "records" / "plans"
    records.mkdir(parents=True)
    (records / "B-271-a-thing-BLOCKED.md").write_text("# blocked\n", encoding="utf-8")

    found = squad_boss.halt_reports(tmp_path)

    # `halt_reports` returns a dict KEYED by item. The first draft of this iterated it expecting
    # records and read `None` from each key — a harness reading the wrong shape, which fails in the
    # same direction as the defect and would have been indistinguishable from it.
    assert isinstance(found, dict), type(found)
    assert "B-271" in found, (
        f"a BLOCKED report in the plans directory was not found, so SELECT will re-offer the "
        f"halted item. Found: {found}")
