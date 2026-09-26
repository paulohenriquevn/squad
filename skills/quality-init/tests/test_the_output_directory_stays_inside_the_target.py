"""A path guard was written, tested, and applied to nothing.

`gate_authoring/path_safety.py` declares itself "prevent path traversal outside project
root" and exports `confine`. `init_quality_gates.py` never imported it, while resolving
a caller-supplied `--out` at line 385 and handing it to `emit.py`, which WRITES hook
scripts there. So `--out ../../../etc` wrote outside the target and nothing objected.

The guard existing but unwired is the worse of the two failures: a reader who finds
`path_safety.py` concludes the traversal case is handled.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "skills" / "quality-init" / "scripts" / "init_quality_gates.py"


def _run(target: Path, out: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), str(target), "--out", str(out),
         "--allow-missing-tools", "--skip-tests", "--no-settings-patch"],
        capture_output=True, text=True, timeout=300, check=False)


def test_an_out_outside_the_target_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "project"
    (target / "src").mkdir(parents=True)
    (target / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    escape = tmp_path / "somewhere-else"

    result = _run(target, escape)

    assert result.returncode != 0, (
        f"--out {escape} is outside {target} and was accepted:\n{result.stdout[-600:]}")
    assert "outside" in (result.stderr + result.stdout).lower()
    assert not escape.exists(), "the refusal came after something was already written"


def test_an_out_inside_the_target_is_accepted(tmp_path: Path) -> None:
    target = tmp_path / "project"
    (target / "src").mkdir(parents=True)
    (target / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    inside = target / "custom" / "hooks"

    result = _run(target, inside)

    assert result.returncode == 0, f"{result.stdout[-800:]}\n{result.stderr[-800:]}"
