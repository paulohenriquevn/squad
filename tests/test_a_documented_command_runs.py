"""A command a skill tells the agent to run must be a command that runs.

Three of them were not. Each failed for a different reason, and all three failed
before doing any work, so the failure looked like a broken script rather than a
broken instruction:

* `quality-init` built its script path without the `skills/quality-init/` segment, so
  the documented run died file-not-found before stage 1 of 10.
* the same line passed the target as `--target`, an option the parser does not
  declare — argparse exits 2 on it.
* `release` captured `CURRENT_VERSION` from `detect_current_version.py --quiet`, a
  flag the parser did not declare. argparse exited 2, `CURRENT_VERSION` became the
  empty string, and the next documented command ran `bump_version.py --from ""` —
  under a heading that calls a non-zero exit blocking.

The check is deliberately mechanical: pull the command out of the SKILL.md, run it,
and require it not to die on argument parsing or a missing file.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _skill_text(skill: str) -> str:
    return (_ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")


def _script_paths(text: str) -> list[str]:
    """Every `.../scripts/<name>.py` a documented command names."""
    return re.findall(r'([\w./$\[\]() "|\\-]*?scripts/[\w_]+\.py)', text)


def test_the_quality_init_command_names_the_script_that_exists() -> None:
    text = _skill_text("quality-init")

    assert "/skills/quality-init/scripts/init_quality_gates.py" in text, (
        "the documented path omits the skill directory, so it resolves to nothing")


def test_the_quality_init_command_passes_the_target_the_way_the_parser_takes_it() -> None:
    script = _ROOT / "skills" / "quality-init" / "scripts" / "init_quality_gates.py"
    result = subprocess.run([sys.executable, str(script), "--target", "."],
                            cwd=_ROOT, capture_output=True, text=True, timeout=120, check=False)

    documented_as_option = '--target "$TARGET"' in _skill_text("quality-init")
    parser_takes_option = "unrecognized arguments" not in result.stderr

    assert documented_as_option == parser_takes_option, (
        "the SKILL.md and the parser disagree about whether the target is an option")


def test_detect_current_version_accepts_the_flag_the_release_step_passes() -> None:
    script = _ROOT / "skills" / "release" / "scripts" / "detect_current_version.py"
    result = subprocess.run([sys.executable, str(script), "--quiet"],
                            cwd=_ROOT, capture_output=True, text=True, timeout=120, check=False)

    assert result.returncode == 0, f"--quiet is documented and rejected:\n{result.stderr}"
    assert result.stdout.strip(), "the release step captures this stdout as CURRENT_VERSION"


def test_quiet_leaves_only_the_version_on_the_output() -> None:
    """The step assigns stdout to a shell variable; a note on it corrupts the value."""
    script = _ROOT / "skills" / "release" / "scripts" / "detect_current_version.py"
    result = subprocess.run([sys.executable, str(script), "--quiet"],
                            cwd=_ROOT, capture_output=True, text=True, timeout=120, check=False)

    assert result.stderr == "", f"--quiet still writes to stderr: {result.stderr!r}"
    assert len(result.stdout.strip().splitlines()) == 1, result.stdout
