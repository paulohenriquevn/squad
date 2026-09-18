"""Two contracts that name codes their code cannot produce, and one that omits a code
it produces four times.

* `panel_brief.py` separates "no contract for this phase" (1, a kit defect) from "no
  assignment on disk" (2, a state the caller clears by running `convene_panel`). Both
  were `raise SystemExit(<string>)`, which prints the string and exits **1**. The
  distinction the header makes exists so a caller can retry one and escalate the other,
  and both arrived as the same code.
* `dispatch_to_lane.sh` documents 0/1/2/3 and returns **64** from four invocation-error
  branches. `fleet_router.dispatch()` branches on the code under the comment "every exit
  code below is meaningful" and reports any non-zero as "<unit> was NOT delivered ...
  (exit N)" — so a typo in the arguments is reported as a delivery failure.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def test_no_assignment_on_disk_exits_two(tmp_path: Path) -> None:
    script = _ROOT / "mechanisms" / "cycle" / "panel_brief.py"

    result = subprocess.run(
        [sys.executable, str(script), "--slug", "nothing-here", "--phase", "plan",
         "--project", str(tmp_path)],
        capture_output=True, text=True, timeout=120, check=False)

    assert result.returncode == 2, (
        f"documented as 2, got {result.returncode}: {result.stderr.strip()[:200]}")


def test_an_undeclared_phase_exits_one(tmp_path: Path) -> None:
    """The other half: a kit defect, and it must NOT look like the retryable state."""
    script = _ROOT / "mechanisms" / "cycle" / "panel_brief.py"

    result = subprocess.run(
        [sys.executable, str(script), "--slug", "x", "--phase", "no-such-phase",
         "--project", str(tmp_path)],
        capture_output=True, text=True, timeout=120, check=False)

    assert result.returncode == 1, result.stderr.strip()[:200]


def test_every_exit_code_the_dispatcher_returns_is_documented() -> None:
    script = _ROOT / "mechanisms" / "fleet" / "dispatch_to_lane.sh"
    source = script.read_text(encoding="utf-8")

    header = source.split("Exit codes:", 1)[1].split("\nset -", 1)[0]
    documented = set(re.findall(r"^#\s+(\d+)\s", header, re.MULTILINE))
    returned = set(re.findall(r"\bexit (\d+)\b", source))

    assert returned - documented == set(), (
        f"returned and undocumented: {sorted(returned - documented)}; "
        f"documented: {sorted(documented)}")
