"""DISCOVER is the remedy for an unmeasured item, not a toll on every one.

`cycle-phases.txt` declared `discover | required` while `cycle-plan.md` said the
opposite in its own pre-conditions — "A feature has a defined goal and known prior
art (otherwise, run DISCOVER first)". Otherwise. The rule already treated the
phase as the remedy for a missing measurement, and the chain declaration called it
mandatory, so the two disagreed about the same phase.

`required` is not decoration. `check_phase_drift --expect-complete` reports
`phase_declared_never_ran` for a required phase that left no event, and never for
a conditional one — so an item that arrived already measured was filed as an
incomplete run.

WHAT IS NOT LOST, and it is the whole reason this is safe. The thing that protects
against planning on a hunch was never the phase declaration: it is
`triaged_without_evidence`, a BLOCKER in `check_backlog_structure`, which asks for
the EVIDENCE rather than for the ceremony that usually produces it. Measured
2026-09-19 on an item at `status: triaged` with `evidence: none-yet`:

    [BLOCKER] B-001 triaged_without_evidence: triaged but evidence is still
    `none-yet`. Triaged means measured; without evidence the status is a claim
    nobody made.

That guard is unchanged here, and these tests assert it in the same breath as the
change — a relaxation whose companion protection is not pinned is a relaxation
nobody can audit later.

Such an item is still SELECTED, and that is correct rather than a gap: an item
with no evidence is exactly what DISCOVER exists to pick up. Optional is not
"skipped by default" — it is "absent when it has nothing to add".
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "mechanisms" / "gates"))
sys.path.insert(0, str(_REPO / "skills" / "backlog-review" / "scripts"))

from check_phase_drift import load_declared_phases  # noqa: E402

_PHASES = _REPO / "rules" / "cycle-phases.txt"


def _row(name: str) -> tuple[str, str]:
    for line in _PHASES.read_text(encoding="utf-8").splitlines():
        stripped = line.split("#", 1)[0].strip()
        if not stripped or "|" not in stripped:
            continue
        parts = [p.strip() for p in stripped.split("|")]
        if parts[0] == name:
            return parts[1], parts[2] if len(parts) > 2 else ""
    raise AssertionError(f"{name} is not declared in cycle-phases.txt")


def test_discover_is_declared_conditional() -> None:
    requirement, _ = _row("discover")
    assert requirement == "conditional", (
        "declared required while `cycle-plan.md` says 'otherwise, run DISCOVER "
        "first' — the two disagree about the same phase")


def test_the_note_says_when_it_is_absent_like_every_other_conditional() -> None:
    """A conditional phase whose note does not name the condition is a phase
    nobody can tell was legitimately skipped from one that was forgotten."""
    _, note = _row("discover")
    assert note, "no note"
    assert "absent" in note.lower(), note
    # It must point at what DOES guard the thing the phase used to guard.
    assert "evidence" in note.lower(), note


def test_the_evidence_guard_is_untouched(tmp_path: Path) -> None:
    """The protection that matters, pinned in the same file as the relaxation."""
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(
        "# Backlog\n\n## Items\n\n"
        "## B-001 — A hunch nobody measured   [ ]\n\n"
        "domain: data-plane\nrepo: web-console\nsuggested_mode: review\n"
        "source: human\nevidence: none-yet\nwhy_now: it feels slow\n"
        "status: triaged\ndod:\n  - faster\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable,
         str(_REPO / "skills" / "backlog-review" / "scripts" / "check_backlog_structure.py"),
         str(backlog)],
        capture_output=True, text=True, check=False)
    assert "triaged_without_evidence" in proc.stdout, proc.stdout
    assert "BLOCKER" in proc.stdout, proc.stdout


def test_an_unmeasured_item_is_still_handed_to_the_loop(tmp_path: Path) -> None:
    """Optional is not skipped-by-default. An item with no evidence is what
    DISCOVER exists to pick up, so it must still be selectable."""
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(
        "# Backlog\n\n## Items\n\n"
        "## B-001 — A hunch nobody measured   [ ]\n\n"
        "domain: data-plane\nrepo: web-console\nsuggested_mode: review\n"
        "source: human\nevidence: none-yet\nwhy_now: it feels slow\n"
        "status: triaged\ndod:\n  - faster\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable,
         str(_REPO / "skills" / "backlog-review" / "scripts" / "select_backlog_item.py"),
         str(backlog), "--json"],
        capture_output=True, text=True, check=False)
    assert '"ITEM_SELECTED"' in proc.stdout, proc.stdout


def test_a_run_without_discover_is_no_longer_an_incomplete_run() -> None:
    """The mechanical effect, asserted through the reader rather than the file."""
    phases = {p.name: p for p in load_declared_phases(_REPO)}
    assert "discover" in phases, sorted(phases)
    assert phases["discover"].required is False
