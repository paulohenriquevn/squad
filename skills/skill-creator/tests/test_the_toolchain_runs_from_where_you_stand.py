"""The skill-creator toolchain could not be run on the skills this kit ships.

Three defects, one symptom: the tooling worked only under conditions nobody meets.

1. `quick_validate` refused any frontmatter key outside a six-key allowlist. Every
   SKILL.md here also carries `version`, `requires`, `user-invocable` and
   `argument-hint` — and `requires` is load-bearing, read by the chain-precondition
   gate. So the validator rejected 39 of 39 skills, and `package_skill`, which calls
   it before writing, could package none of them.

2. `package_skill`, `run_loop` and `improve_description` import `scripts.…` with no
   bootstrap, so they resolve only when the process happens to start in
   `skills/skill-creator/`. `run_eval` fixed this for itself and left the reason:
   "a tool that only works from one directory is a tool nobody runs from the place
   they are standing." Its three siblings never got the same four lines.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS = _ROOT / "skills" / "skill-creator" / "scripts"

# Another skill also ships a `scripts` package, and whichever one a sibling test
# imported first stays in sys.modules. Load this one by its path so the test always
# measures the module it names.
_spec = importlib.util.spec_from_file_location(
    "skill_creator_quick_validate", _SCRIPTS / "quick_validate.py")
_quick_validate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_quick_validate)
validate_skill = _quick_validate.validate_skill


def _shipped_skills() -> list[Path]:
    return sorted(p.parent for p in (_ROOT / "skills").glob("*/SKILL.md"))


def test_every_shipped_skill_passes_the_validator() -> None:
    skills = _shipped_skills()
    assert skills, "no SKILL.md found — the test lost its subject"

    rejected = [(s.name, validate_skill(s)[1]) for s in skills if not validate_skill(s)[0]]

    assert rejected == [], f"the validator rejects skills this repository ships: {rejected}"


def test_the_load_bearing_frontmatter_keys_are_allowed() -> None:
    """`requires` drives the chain-precondition gate; rejecting it rejects the kit."""
    allowed = _quick_validate.ALLOWED_PROPERTIES

    for key in ("version", "requires", "user-invocable", "argument-hint"):
        assert key in allowed, f"{key} is shipped in this kit and must validate"


def _runs_by_path(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(_SCRIPTS / script), "--help"],
                          cwd=_ROOT, capture_output=True, text=True, timeout=120, check=False)


def test_the_scripts_import_when_run_from_the_repository_root() -> None:
    for script in ("run_loop.py", "improve_description.py"):
        result = _runs_by_path(script)
        assert "ModuleNotFoundError" not in result.stderr, (
            f"{script} cannot resolve its own package from the repository root:\n{result.stderr}")


def test_the_packager_imports_when_run_by_its_real_path(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(_SCRIPTS / "package_skill.py"), str(_ROOT / "skills" / "acceptance"),
         str(tmp_path)],
        cwd=_ROOT, capture_output=True, text=True, timeout=180, check=False)

    assert "ModuleNotFoundError" not in result.stderr, result.stderr
    assert list(tmp_path.glob("*.skill")), (
        f"the packager wrote no archive:\n{result.stdout}\n{result.stderr}")


def test_the_usage_text_names_a_path_that_exists() -> None:
    """The docstring told the reader to run `utils/package_skill.py`. There is no utils/."""
    source = (_SCRIPTS / "package_skill.py").read_text(encoding="utf-8")

    assert "utils/package_skill.py" not in source, "usage text points at a directory that does not exist"
