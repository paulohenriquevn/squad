"""An opportunity cites an item. The gate asks whether the item is there.

THE DEFECT THIS CLOSES — AND WHERE IT WAS WRITTEN DOWN
------------------------------------------------------
`cycle-discover.md` lists "Sweeping without registering" as an anti-pattern: *"A
`--sweep` finding that stays in the run's output and never reaches `BACKLOG.md` is the
orphaned-finding failure the single registry exists to prevent."*

Nothing checked it. `grep BACKLOG` across every DISCOVER scorer returned nothing, and
`phase_coverage.py` only walks the other direction — item to file — noting in its own
source that *"two entry paths and only one writes an opportunity file"*.

The kit knew. `skills/discover-confidence/fixtures/good-opportunity.md`, shipped as the
EXAMPLE of a good opportunity, is an opportunity about this exact gap:

    "Neither checker opens BACKLOG.md, so a sweep that produces four well-formed
     opportunities and registers none of them scores exactly as well as one that
     registers all four. The gate that the anti-pattern implies does not exist."

Measured, written up, used to teach — and never closed. This is the gate.

WHAT IT ASKS, AND WHAT IT REFUSES TO ASSERT
-------------------------------------------
Every opportunity declares `**Item:** B-NNN`, already mandatory. The gate resolves that
id against the registry. With no `BACKLOG.md` reachable it reports NOT MEASURED rather
than calling every opportunity an orphan — the same rule `check_objective_coverage` and
`check_measurement_targets` follow, where `None` is not an empty set.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCORER = REPO / "skills" / "discover-confidence" / "scripts" / "run_opportunity_score.py"
FIXTURE = REPO / "skills" / "discover-confidence" / "fixtures" / "good-opportunity.md"

REGISTRY = """# Backlog

## B-004 — The sweep finding that was registered

domain: kit
repo: squad
suggested_mode: review
source: discover-review
evidence: rules/cycle-discover.md:20
why_now: measured during a sweep
status: triaged
dod:
  - the gate exists and a sweep without registration is refused
"""


def _opportunity(tmp_path: Path, *, item: str = "B-004") -> Path:
    src = FIXTURE.read_text(encoding="utf-8").replace("**Item:** B-004", f"**Item:** {item}", 1)
    (tmp_path / ".git").mkdir(exist_ok=True)
    path = tmp_path / "opportunity.md"
    path.write_text(src, encoding="utf-8")
    return path


def _score(path: Path) -> dict:
    proc = subprocess.run([sys.executable, str(SCORER), str(path), "--no-warn"],
                          capture_output=True, text=True, cwd=path.parent)
    return json.loads(proc.stdout[proc.stdout.index("{"):])


def test_an_opportunity_whose_item_is_not_in_the_registry_is_capped(tmp_path: Path) -> None:
    (tmp_path / "BACKLOG.md").write_text(REGISTRY, encoding="utf-8")

    report = _score(_opportunity(tmp_path, item="B-999"))

    assert "item_not_registered" in report["hard_caps_triggered"], (
        "a finding that never reached the registry is the orphaned-finding failure "
        "the single registry exists to prevent")


def test_an_opportunity_whose_item_is_registered_passes(tmp_path: Path) -> None:
    (tmp_path / "BACKLOG.md").write_text(REGISTRY, encoding="utf-8")

    report = _score(_opportunity(tmp_path))

    assert "item_not_registered" not in report["hard_caps_triggered"]


def test_with_no_registry_reachable_the_check_says_so(tmp_path: Path) -> None:
    """`None` is not an empty set. Without a registry the question is unanswered, and
    calling every opportunity an orphan would assert a violation the evidence does not
    support."""
    report = _score(_opportunity(tmp_path, item="B-999"))

    assert "item_not_registered" not in report["hard_caps_triggered"]
    blob = json.dumps(report).lower()
    assert "not checked" in blob or "no backlog" in blob or "not measured" in blob
