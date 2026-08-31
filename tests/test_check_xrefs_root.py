"""The validator audits the ecosystem it BELONGS to, not the current directory's.

Before, without `--ecosystem-dir`, the root came from `Path.cwd()`. The effect was
a validator that lies by omission: running

    python3 <outro-projeto>/.claude/scripts/check_xrefs.py

de um cwd qualquer auditava silenciosamente o ecossistema DO CWD e imprimia o
its verdict — with the other project's name on the command line. Measured on
2026-08-03: three consumers reported as `PASS` actually had 3, 0 and 11 findings;
the `PASS` was the kit's own repo validating itself three times.

A validator that audits the wrong target is worse than none: none produces no
confidence, this one produces unfounded confidence — and the decision taken on top
of it ("all three are clean, go ahead") has already been taken.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO / "scripts" / "check_xrefs.py"


def _make_ecosystem(root: Path, *, skill: str, missing_rule: bool) -> Path:
    """Creates a minimal .claude/, optionally with a broken rule reference."""
    eco = root / ".claude"
    (eco / "skills" / skill).mkdir(parents=True)
    (eco / "rules").mkdir(parents=True)
    (eco / "scripts").mkdir(parents=True)
    (eco / "hooks").mkdir(parents=True)  # find_ecosystem_dir requires all three

    body = "# Skill\n\n## Cycle contract\n\nSee `rules/cycle-implement.md`.\n"
    if missing_rule:
        body += "\nAlso reads `rules/does-not-exist-anywhere.md`.\n"
    (eco / "skills" / skill / "SKILL.md").write_text(body, encoding="utf-8")
    (eco / "rules" / "cycle-implement.md").write_text(
        f"# cycle-implement\n\nChain: `implement`\n\nUses skills/{skill}/.\n", encoding="utf-8"
    )
    return eco


def _findings(script: Path, cwd: Path) -> list[dict]:
    proc = subprocess.run(
        [sys.executable, str(script), "--json"],
        cwd=str(cwd), capture_output=True, text=True, check=False,
    )
    return json.loads(proc.stdout)["findings"]


def test_raiz_vem_do_script_e_nao_do_cwd(tmp_path: Path) -> None:
    """The exact regression: a dirty project's script, called from a clean cwd."""
    sujo = tmp_path / "sujo"
    limpo = tmp_path / "limpo"
    eco_sujo = _make_ecosystem(sujo, skill="implement", missing_rule=True)
    _make_ecosystem(limpo, skill="implement", missing_rule=False)

    copia = eco_sujo / "scripts" / "check_xrefs.py"
    copia.write_bytes(_SCRIPT.read_bytes())
    for shared in (_REPO / "scripts").glob("*.py"):
        if shared.name != "check_xrefs.py":
            (eco_sujo / "scripts" / shared.name).write_bytes(shared.read_bytes())

    broken = [
        f for f in _findings(copia, cwd=limpo)
        if f.get("check") == "rules_reference_resolves"
    ]
    assert broken, (
        "the dirty project's script, called from a clean cwd, did not see the broken "
        "reference that exists in the project it belongs to — it is auditing the cwd"
    )
    assert broken[0]["missing_rule"] == "does-not-exist-anywhere.md"


def test_ecosystem_dir_explicito_continua_mandando(tmp_path: Path) -> None:
    """`--ecosystem-dir` is the only way to point at another target, and it wins."""
    outro = tmp_path / "outro"
    eco_outro = _make_ecosystem(outro, skill="implement", missing_rule=True)

    proc = subprocess.run(
        [sys.executable, str(_SCRIPT), "--json", "--ecosystem-dir", str(eco_outro)],
        cwd=str(_REPO), capture_output=True, text=True, check=False,
    )
    findings = json.loads(proc.stdout)["findings"]
    assert any(f.get("check") == "rules_reference_resolves" for f in findings)


def test_a_data_file_named_after_a_cycle_is_not_a_cycle_reference():
    """`records/cycle-events.jsonl` is a file, not a reference to a rule nobody wrote.

    The first fix backtracked: the name group gave up its last character so the
    extension lookahead would pass, and `cycle-event` matched instead. The name must
    be anchored before the extension is judged.
    """
    from check_xrefs import CYCLE_NAME_RE

    assert CYCLE_NAME_RE.findall("records/cycle-events.jsonl") == []
    assert CYCLE_NAME_RE.findall(".claude/records/cycle-events.jsonl") == []


def test_a_real_cycle_reference_still_resolves():
    """The mirror case: narrowing must not silence the check it exists for."""
    from check_xrefs import CYCLE_NAME_RE

    assert CYCLE_NAME_RE.findall("rules/cycle-plan.md") == ["plan"]
    assert CYCLE_NAME_RE.findall("cycle-idea-to-release") == ["idea-to-release"]
    assert CYCLE_NAME_RE.findall("cycle-review.md and cycle-plan") == ["review", "plan"]
