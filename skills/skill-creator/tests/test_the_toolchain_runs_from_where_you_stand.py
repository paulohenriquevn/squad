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
import re
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


#: The directory `skills/review/scripts/spawn_reviewers.py` writes each paired knowledge
#: skill into, `review-{slug}-{role}-knowledge`. Run output, not the kit's roster.
_GENERATED_KNOWLEDGE_SKILL = re.compile(r"^review-.+-knowledge$")


def _shipped_skills(root: Path = _ROOT) -> list[Path]:
    """The skills the kit ships in this tree — never what a `/review` run wrote beside them.

    A copy install carries `.kit-manifest.txt`, one `skills/<name>` line per skill the
    installer brought; that list is authoritative and also leaves out the project's own
    skills, which are not the kit's to grade. The kit's own tree has no manifest, and
    there the generator's naming is what separates its output from the roster.
    """
    present = sorted(p.parent for p in (root / "skills").glob("*/SKILL.md"))
    manifest = root / ".kit-manifest.txt"
    if manifest.is_file():
        listed = {line.split("#", 1)[0].strip()
                  for line in manifest.read_text(encoding="utf-8-sig").splitlines()}
        return [p for p in present if f"skills/{p.name}" in listed]
    return [p for p in present if not _GENERATED_KNOWLEDGE_SKILL.match(p.name)]


def test_every_shipped_skill_passes_the_validator() -> None:
    skills = _shipped_skills()
    assert skills, "no SKILL.md found — the test lost its subject"

    rejected = [(s.name, validate_skill(s)[1]) for s in skills if not validate_skill(s)[0]]

    assert rejected == [], f"the validator rejects skills this repository ships: {rejected}"


# ── the subject is what the kit ships, not what a run left beside it ─────────
#
# `/review` writes paired knowledge skills into the same `skills/` directory this test
# sweeps. Measured in a consumer 2026-09-24: 16 generated `review-…-knowledge` skills
# beside the shipped roster, 13 with names over the limit, and this test failing on
# run output while the identical file passed upstream.

_VALID_SKILL = "---\nname: {name}\ndescription: A skill.\n---\n\n# Body\n"
_GENERATED = "review-the-streamed-document-is-proved-by-execution-cross-validation-knowledge"


def _tree_with_a_generated_skill(root: Path) -> Path:
    for name in ("acceptance", _GENERATED):
        (root / "skills" / name).mkdir(parents=True)
        (root / "skills" / name / "SKILL.md").write_text(
            _VALID_SKILL.format(name=name), encoding="utf-8")
    return root


def test_a_copy_install_grades_the_skills_its_manifest_lists(tmp_path: Path) -> None:
    root = _tree_with_a_generated_skill(tmp_path / ".claude")
    (root / "skills" / "projects-own").mkdir()
    (root / "skills" / "projects-own" / "SKILL.md").write_text(
        _VALID_SKILL.format(name="projects-own"), encoding="utf-8")
    (root / ".kit-manifest.txt").write_text(
        "# Written by install.sh\nskills/acceptance\nrules/x.txt\n", encoding="utf-8")

    assert [p.name for p in _shipped_skills(root)] == ["acceptance"]


def test_a_generated_knowledge_skill_is_not_graded_as_shipped(tmp_path: Path) -> None:
    """The kit's own tree has no manifest; the generator's output is still not the kit's."""
    root = _tree_with_a_generated_skill(tmp_path / "kit")

    assert [p.name for p in _shipped_skills(root)] == ["acceptance"]


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
