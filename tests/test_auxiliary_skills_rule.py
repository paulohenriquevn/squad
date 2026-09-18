"""Project skills declared in a RULE, not edited inside the validator.

`AUXILIARY_SKILLS` is a constant in `check_xrefs.py`'s body. A consumer with
skills of its own had exactly one way out: editing the kit's Python. One adopter
did exactly that (`cnpg-audit`, `cnpg-design`,
`multi-cluster-fleet-specialist`), and that edit is what a future sync overwrites
— it only survived because the comparison was done file by file.

Measured on `speculative` (2026-08-20): 9 domain skills of its own, 18 WARN,
which were **100% of the checker's warnings** — and with `--strict`, which is how
the installer invokes it, that fails the entire installation. A validator that
always warns teaches people to ignore it; one that fails over the consumer's
design teaches them to run without `--strict`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO / "mechanisms" / "gates" / "check_xrefs.py"


def _eco(root: Path, *, skills: list[str], declared: list[str] | None) -> Path:
    eco = root / ".claude"
    (eco / "rules").mkdir(parents=True)
    (eco / "scripts").mkdir(parents=True)
    (eco / "hooks").mkdir(parents=True)
    (eco / "rules" / "cycle-implement.md").write_text(
        "# Cycle: IMPLEMENT\n\n## Cross-references\n\n- `skills/implement/SKILL.md`\n",
        encoding="utf-8")
    (eco / "skills" / "implement").mkdir(parents=True)
    (eco / "skills" / "implement" / "SKILL.md").write_text(
        "# Skill\n\n## Cycle contract\n\nSee `rules/cycle-implement.md`.\n", encoding="utf-8")
    for name in skills:
        (eco / "skills" / name).mkdir(parents=True)
        (eco / "skills" / name / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    if declared is not None:
        (eco / "rules" / "auxiliary-skills.txt").write_text(
            "# skills deste projeto\n" + "\n".join(declared) + "\n", encoding="utf-8")
    return eco


def _warns_about(eco: Path, skill: str) -> bool:
    """Is there any warning about THIS skill? (the minimal fixture generates others, irrelevant here)"""
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--ecosystem-dir", str(eco), "--json"],
        capture_output=True, text=True,
     check=False)
    import json
    findings = json.loads(result.stdout).get("findings", [])
    return any(skill in json.dumps(f) for f in findings)


def test_undeclared_project_skill_is_warned_about(tmp_path: Path) -> None:
    eco = _eco(tmp_path, skills=["collapse-detection-specialist"], declared=None)
    assert _warns_about(eco, "collapse-detection-specialist"), "this is today's state: 2 WARN per skill"


def test_declaring_it_in_the_rule_clears_both_warnings(tmp_path: Path) -> None:
    """BOTH checks — `no_orphan_skills` and `skill_has_cycle_contract`. Exempting only
    one is the half exemption the code itself documents as a false fix."""
    eco = _eco(tmp_path, skills=["collapse-detection-specialist"],
               declared=["collapse-detection-specialist"])
    assert not _warns_about(eco, "collapse-detection-specialist")


def test_a_declared_skill_that_does_not_exist_is_not_an_error(tmp_path: Path) -> None:
    """The list is a declaration of intent, not an inventory: a skill removed from the
    project must not break the validator."""
    eco = _eco(tmp_path, skills=["collapse-detection-specialist"],
               declared=["collapse-detection-specialist", "ja-removida"])
    assert not _warns_about(eco, "ja-removida")
    assert not _warns_about(eco, "collapse-detection-specialist")


# ---------------------------------------------------------------------------
# Grill kit-domain-agents-install, decision 2: the derived skeleton is a WARN
# while nobody has reviewed it. Without that it becomes "a specialist nobody
# finished" wearing the appearance of coverage — the defect D5 pursues.
# ---------------------------------------------------------------------------

def _eco_with_agent(root: Path, body: str, name: str = "a-domain") -> Path:
    eco = _eco(root, skills=[], declared=None)
    (eco / "agents").mkdir(parents=True, exist_ok=True)
    (eco / "agents" / f"{name}.md").write_text(body, encoding="utf-8")
    return eco


def test_an_unreviewed_skeleton_is_warned_about(tmp_path: Path) -> None:
    # `— OPEN`, the marker `scaffold_specialists.render` actually writes. The fixture
    # carried `<!-- TO BE FILLED IN: only a human knows this -->`, which only
    # `detect_domains.render_specialist` ever produced — a second template reachable
    # from nothing but its own tests, since removed. A fixture using a marker no
    # shipped writer emits tests the gate against a document nobody creates.
    eco = _eco_with_agent(tmp_path, """---
name: a-domain
derived: true
reviewed_by_human: false
---

# a-domain

## The domain's invariants — OPEN
""")
    assert _warns_about(eco, "a-domain"), (
        "a silent skeleton looks like a finished specialist")


def test_a_filled_specialist_is_not_warned_about(tmp_path: Path) -> None:
    eco = _eco_with_agent(tmp_path, """---
name: meu-dominio
---

# meu-dominio

## Invariantes

The index and the disk do not diverge.
""")
    assert not _warns_about(eco, "meu-dominio")
