"""`convene_panel.py` says this module "refuses a record whose voters do not match".

For a long time nothing set `Panel.assigned`: `load()` deliberately does not read it
from the record — a document supplying the list it is checked against proves nothing —
and `main` had no other source. So the branch that enforces the claim was unreachable
from the CLI, which is how `skills/panel/SOP.md` step 5 invokes it, and a document could
be routed to the specialists its content demands and signed off by three others.

The assignment sits beside the record by construction (`convene_panel.assignment_path`
and the record share `panels_dir`), so the DOCUMENTED invocation — no extra flag —
has to find it. That is what this pins: not that the flag exists, but that the command
in the SOP performs the check.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "mechanisms" / "cycle" / "review_panel.py"


def _panel(panels: Path, voters: list[str], assigned: list[str] | None) -> Path:
    panels.mkdir(parents=True, exist_ok=True)
    record = panels / "a-slug-plan.json"
    record.write_text(json.dumps({
        "slug": "a-slug", "phase": "plan", "artifact": "a.md", "author": "someone",
        "votes": [{"reviewer": v, "model": "m", "verdict": "APPROVE", "reason": "ok"}
                  for v in voters],
    }), encoding="utf-8")
    if assigned is not None:
        (panels / "a-slug-plan.assignment.json").write_text(
            json.dumps({"assigned": assigned}), encoding="utf-8")
    return record


def _tally(record: Path) -> subprocess.CompletedProcess[str]:
    """Exactly the SOP's step 5: the record, and nothing else."""
    return subprocess.run([sys.executable, str(_SCRIPT), "--record", str(record)],
                          capture_output=True, text=True, timeout=120, check=False)


def test_a_panel_that_is_not_the_one_convened_is_refused(tmp_path: Path) -> None:
    record = _panel(tmp_path / "panels", voters=["x", "y", "z"], assigned=["a", "b", "c"])

    result = _tally(record)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "never voted" in combined or "voted unassigned" in combined, combined


def test_the_convened_panel_passes(tmp_path: Path) -> None:
    record = _panel(tmp_path / "panels", voters=["a", "b", "c"], assigned=["a", "b", "c"])

    result = _tally(record)

    assert "never voted" not in result.stdout + result.stderr


def test_no_assignment_says_nobody_checked(tmp_path: Path) -> None:
    """A weaker claim, reported as such — never silently treated as a match."""
    record = _panel(tmp_path / "panels", voters=["x", "y", "z"], assigned=None)

    result = _tally(record)

    assert "never voted" not in result.stdout + result.stderr
