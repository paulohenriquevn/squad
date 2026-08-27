"""A cycle with two hyphens was truncated, and the validator flagged the wrong file.

`CYCLE_REF_RE` was `` `?cycle-([a-z]+)`? `` — `[a-z]+` does not match a hyphen. So
`cycle-code-quality` was read as `cycle-code`, `cycle-idea-to-release` as `cycle-auto`
and `cycle-judge-codex` as `cycle-judge`. None of the three exists in `rules/`,
and Check 2 (`skill_cycle_contract_resolves`) reported FAIL against a name nobody
wrote.

Three of the kit's twelve cycle rules are multi-hyphen, so the defect covered a
quarter of the inventory. It stayed hidden because the two skills citing those
cycles no `## Cycle contract` mencionavam antes um cycle de nome simples — e
`_extract_cycle_contract_ref` retorna no PRIMEIRO match. `idea-to-release` cita
`cycle-discover` antes de `cycle-idea-to-release`; a primeira skill a citar um
multi-hyphen alone is what made the bug appear.

The failure mode is the worst kind for a validator: it flags a non-existent file
while the real file sits right there, and the natural reading — "the validator is
broken" — is the one that teaches people to ignore it.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO / "scripts" / "check_xrefs.py"

# Every multi-hyphen cycle rule in the kit. A new name here is a new case for free.
MULTI_HYPHEN_CYCLES = ["cycle-code-quality", "cycle-idea-to-release", "cycle-judge-codex"]


def _make_ecosystem(root: Path, cycle: str) -> Path:
    """Minimal ecosystem: a skill whose contract cites `cycle`, and the rule that exists."""
    eco = root / ".claude"
    skill = cycle.removeprefix("cycle-")
    (eco / "skills" / skill).mkdir(parents=True)
    (eco / "rules").mkdir(parents=True)
    (eco / "scripts").mkdir(parents=True)
    (eco / "hooks").mkdir(parents=True)
    (eco / "skills" / skill / "SKILL.md").write_text(
        f"# Skill\n\n## Cycle contract\n\nSee `rules/{cycle}.md`.\n", encoding="utf-8"
    )
    (eco / "rules" / f"{cycle}.md").write_text(
        f"# Cycle\n\n## Cross-references\n\n- `skills/{skill}/SKILL.md`\n",
        encoding="utf-8",
    )
    return eco


def _run(eco: Path) -> dict:
    proc = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(_SCRIPT), "--ecosystem-dir", str(eco), "--json"],
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


@pytest.mark.parametrize("cycle", MULTI_HYPHEN_CYCLES)
def test_multi_hyphen_cycle_contract_resolves(tmp_path: Path, cycle: str) -> None:
    # Arrange — the skill cites a multi-hyphen cycle that EXISTS on disk.
    eco = _make_ecosystem(tmp_path, cycle)

    # Act
    report = _run(eco)

    # Assert — no finding may claim the contract does not resolve.
    unresolved = [
        f for f in report["findings"] if f["check"] == "skill_cycle_contract_resolves"
    ]
    assert unresolved == [], (
        f"{cycle} existe em rules/ mas o validador o acusou como ausente: {unresolved}"
    )


@pytest.mark.parametrize("cycle", MULTI_HYPHEN_CYCLES)
def test_multi_hyphen_cycle_is_not_truncated(tmp_path: Path, cycle: str) -> None:
    # Arrange — same ecosystem, but now the real rule is REMOVED.
    eco = _make_ecosystem(tmp_path, cycle)
    (eco / "rules" / f"{cycle}.md").unlink()

    # Act
    report = _run(eco)

    # Assert — the validator must complain about the FULL name, not the truncated prefix.
    msgs = [
        f["message"]
        for f in report["findings"]
        if f["check"] == "skill_cycle_contract_resolves"
    ]
    assert msgs, f"remover rules/{cycle}.md deveria produzir um finding"
    truncated = cycle.rsplit("-", 1)[0]
    assert any(f"{cycle}.md" in m for m in msgs), (
        f"esperava o nome completo {cycle}.md na mensagem, veio: {msgs}"
    )
    assert not any(f"{truncated}.md" in m for m in msgs), (
        f"truncated name {truncated}.md leaked into the message: {msgs}"
    )
