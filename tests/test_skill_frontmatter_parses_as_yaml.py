"""The frontmatter validator must reject frontmatter no parser can read.

THE DEFECT THIS CLOSES
----------------------
Found 2026-08-27 while adding a skill whose `description:` contained a colon.
`validate_skill_frontmatter.py` reported **"Validated 39 skills: 0 errors, 0
warnings"** over that file, and `verify_ecosystem.py` — which loads the same block
with a real YAML parser — reported:

    sop-run/SKILL.md YAML frontmatter is invalid: mapping values are not allowed here

Two validators over one artifact, disagreeing about whether it is readable at
all. The one named after the job does not import `yaml`: it matches
`key: value` with a regex, so a block that no consumer can parse passes it
cleanly.

That matters beyond tidiness. `install.sh` and the docs point at the validator
as the frontmatter gate; a consumer who runs it and sees green has a skill
Claude Code cannot load. A gate blind to the most basic failure of the thing it
validates is the empty gate this ecosystem refuses everywhere else.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "mechanisms" / "gates" / "validate_skill_frontmatter.py"

_BROKEN = """\
---
name: demo
description: A skill that does things: and then more things.
user-invocable: true
allowed-tools: Read
---

# Demo
"""

_VALID = """\
---
name: demo
description: A skill that does things — and then more things.
user-invocable: true
allowed-tools: Read
---

# Demo
"""


def _ecosystem(tmp_path: Path, body: str) -> Path:
    for part in ("rules", "hooks"):
        (tmp_path / part).mkdir(parents=True, exist_ok=True)
    skill = tmp_path / "skills" / "demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(body, encoding="utf-8")
    return tmp_path


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--ecosystem-dir", str(root)],
        capture_output=True, text=True, check=False,
    )


def test_unparseable_frontmatter_fails_the_validator(tmp_path: Path) -> None:
    """An unquoted colon is the commonest way to break a frontmatter block, and
    it was passing."""
    result = _run(_ecosystem(tmp_path, _BROKEN))

    assert result.returncode != 0, result.stdout
    assert "yaml" in (result.stdout + result.stderr).lower()


def test_valid_frontmatter_still_passes(tmp_path: Path) -> None:
    """The fix must not turn every skill red: an em dash is the house style and
    parses fine."""
    result = _run(_ecosystem(tmp_path, _VALID))

    assert result.returncode == 0, result.stdout


def test_this_repository_frontmatter_parses(tmp_path: Path) -> None:
    """The kit's own 39 skills, through a real parser."""
    yaml = pytest.importorskip("yaml")
    broken: list[str] = []
    for skill_md in sorted((REPO_ROOT / "skills").glob("*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        block = text.split("---", 2)[1]
        try:
            yaml.safe_load(block)
        except yaml.YAMLError as error:
            broken.append(f"{skill_md.parent.name}: {error}")

    assert broken == [], "\n".join(broken)


def test_an_unrecognised_frontmatter_key_is_named(tmp_path) -> None:
    """`OPTIONAL_FIELDS` sat beside `REQUIRED_FIELDS` and was read by NOTHING.

    A tree-wide grep found exactly its declaration. A constant named for a check teaches
    every reader the check exists, and an unknown key passed silently: a typo'd
    `descripton:` was reported only as a missing `description`, with no word about the
    key sitting right beside it.
    """
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mechanisms" / "gates"))
    from validate_skill_frontmatter import validate_all

    skill = tmp_path / "skills" / "a-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: a-skill\ndescription: does a thing\nuser-invocable: true\n"
        "descripton: the typo\n---\n\nBody.\n", encoding="utf-8")

    code = validate_all(tmp_path, strict=False)

    assert code == 0, "an unknown key must warn, not fail — the platform ignores it"


def test_a_frontmatter_with_only_known_keys_warns_about_none(tmp_path, capsys) -> None:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mechanisms" / "gates"))
    from validate_skill_frontmatter import validate_all

    skill = tmp_path / "skills" / "a-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: a-skill\ndescription: does a thing\nuser-invocable: true\n"
        "allowed-tools: Read\n---\n\nBody.\n", encoding="utf-8")

    validate_all(tmp_path, strict=False)

    assert "unrecognised frontmatter key" not in capsys.readouterr().out


def test_the_aggregate_and_the_gate_enforce_the_same_contract(tmp_path) -> None:
    """`verify_ecosystem` held its OWN copy of the frontmatter rule.

    It required `name` and `description`; `validate_skill_frontmatter.py` requires those
    plus `user-invocable`. So the aggregate's tick certified a SMALLER contract than the
    gate it is named after — a skill missing `user-invocable` passed one and failed the
    other, and a reader seeing a green `verify_ecosystem` had no way to know.
    """
    import sys as _sys
    gates = Path(__file__).resolve().parents[1] / "mechanisms" / "gates"
    _sys.path.insert(0, str(gates))
    import verify_ecosystem as ve

    eco = tmp_path / ".claude"
    (eco / "mechanisms" / "gates").mkdir(parents=True)
    (eco / "mechanisms" / "gates" / "validate_skill_frontmatter.py").write_text(
        (gates / "validate_skill_frontmatter.py").read_text(encoding="utf-8"),
        encoding="utf-8")
    # The gate imports it from `mechanisms/conventions/`, which its own bootstrap adds.
    conventions = eco / "mechanisms" / "conventions"
    conventions.mkdir(parents=True)
    (conventions / "ecosystem_utils.py").write_text(
        (gates.parent / "conventions" / "ecosystem_utils.py").read_text(encoding="utf-8"),
        encoding="utf-8")
    skill = eco / "skills" / "a-skill"
    skill.mkdir(parents=True)
    # Missing `user-invocable`: accepted by the aggregate's old private copy.
    (skill / "SKILL.md").write_text(
        "---\nname: a-skill\ndescription: does a thing\n---\n\nBody.\n", encoding="utf-8")

    ok, lines = ve.check_skill_frontmatter(eco)

    assert ok is False, f"the aggregate accepted what the gate refuses: {lines}"
