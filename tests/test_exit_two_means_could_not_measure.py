"""Exit 2 is this kit's word for "could not measure". Three scripts promised it and
could not produce it, so the caller read "could not measure" as something else.

* `spawn_stages` reserved 2 for "no kit under --repo, so there is no data root", and
  raised `SystemExit` with a STRING. Python prints the string and exits **1** — the
  same code the docstring gives to a missing template. A caller distinguishing bad
  input from no data root got 1 for both.
* `run_validation` documented 2 in three places for "project root not found", and
  `_find_project_root` cannot fail: after twenty levels it returns `start.resolve()`.
  A run launched outside the project validated the wrong tree, SKIPped its way to
  PARTIAL and exited 0 — which SKILL.md reads as "proceed to Step 6".
* `run_structural` returned 2 for the three panel verdicts, which its own Exit Codes
  section maps to "Error (plan not found, malformed rubric)". A structurally perfect
  plan waiting on its panel was indistinguishable from a malformed invocation.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def test_spawn_stages_exits_two_when_there_is_no_data_root(tmp_path: Path) -> None:
    script = _ROOT / "skills" / "pipeline" / "scripts" / "spawn_stages.py"
    bare = tmp_path / "no-kit-here"
    bare.mkdir()

    result = subprocess.run(
        [sys.executable, str(script), "--item", "B-001", "--repo", str(bare)],
        capture_output=True, text=True, timeout=120, check=False)

    assert result.returncode == 2, (
        f"documented as 2 for 'no data root', got {result.returncode}:\n{result.stderr}")
    assert "no kit under" in result.stderr


def test_run_validation_refuses_a_root_it_could_not_find(tmp_path: Path) -> None:
    """The fallback made an unfindable root indistinguishable from a found one."""
    sys.path.insert(0, str(_ROOT / "skills" / "implement" / "scripts"))
    import run_validation

    assert run_validation._find_project_root(tmp_path) is None, (
        "a root that was never found must be reported as not found, not guessed")


def test_the_validation_gate_exits_two_when_the_root_is_unfindable(tmp_path: Path) -> None:
    script = _ROOT / "skills" / "implement" / "scripts" / "run_validation.py"

    result = subprocess.run([sys.executable, str(script), "--slug", "anything"],
                            cwd=tmp_path, capture_output=True, text=True, timeout=300, check=False)

    assert result.returncode == 2, (
        f"documented as 2 for 'project root not found', got {result.returncode}:\n"
        f"{result.stdout[-800:]}\n{result.stderr[-800:]}")
