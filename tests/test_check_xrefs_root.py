"""The validator audits the ecosystem it BELONGS to, not the current directory's.

Before, without `--ecosystem-dir`, the root came from `Path.cwd()`. The effect was
a validator that lies by omission: running

    python3 <another-project>/.claude/mechanisms/gates/check_xrefs.py

from an arbitrary cwd silently audited the ecosystem OF THE CWD and printed
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
_SCRIPT = _REPO / "mechanisms" / "gates" / "check_xrefs.py"


def _make_ecosystem(root: Path, *, skill: str, missing_rule: bool) -> Path:
    """Creates a minimal .claude/, optionally with a broken rule reference."""
    eco = root / ".claude"
    (eco / "skills" / skill).mkdir(parents=True)
    (eco / "rules").mkdir(parents=True)
    (eco / "mechanisms" / "gates").mkdir(parents=True)
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


def test_the_root_comes_from_the_script_and_not_from_the_cwd(tmp_path: Path) -> None:
    """The exact regression: a dirty project's script, called from a clean cwd."""
    sujo = tmp_path / "sujo"
    limpo = tmp_path / "limpo"
    eco_sujo = _make_ecosystem(sujo, skill="implement", missing_rule=True)
    _make_ecosystem(limpo, skill="implement", missing_rule=False)

    copia = eco_sujo / "mechanisms" / "gates" / "check_xrefs.py"
    copia.write_bytes(_SCRIPT.read_bytes())
    for shared in (_REPO / "mechanisms").rglob("*.py"):
        if shared.name != "check_xrefs.py":
            (eco_sujo / "mechanisms" / shared.relative_to(_REPO / "mechanisms")).parent.mkdir(
                parents=True, exist_ok=True)
            (eco_sujo / "mechanisms" / shared.relative_to(_REPO / "mechanisms")).write_bytes(
                shared.read_bytes())
    # The gate resolves data roots through the shared package rather than restating
    # them, so a synthetic ecosystem needs it. Without this the script cannot import
    # and the run produces no JSON at all — which reads as "no findings".
    for module in (_REPO / "squad").glob("*.py"):
        (eco_sujo / "squad").mkdir(parents=True, exist_ok=True)
        (eco_sujo / "squad" / module.name).write_bytes(module.read_bytes())

    broken = [
        f for f in _findings(copia, cwd=limpo)
        if f.get("check") == "rules_reference_resolves"
    ]
    assert broken, (
        "the dirty project's script, called from a clean cwd, did not see the broken "
        "reference that exists in the project it belongs to — it is auditing the cwd"
    )
    assert broken[0]["missing_rule"] == "does-not-exist-anywhere.md"


def test_an_explicit_ecosystem_dir_still_wins(tmp_path: Path) -> None:
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


# ── the kit has no standing over the project's own skills ─────────────────────
#
# `rules/auxiliary-skills.txt` is the right idea and ships EMPTY, so every consumer
# starts with all of its own skills flagged. Measured on 2026-08-31 across two live
# installs: `theo` had the file, empty, and 13 WARN; an adopter had 102 skills of which
# 66 are its own, no file at all, and 119 WARN — every warning the checker produced.
# `install.sh` runs this `--strict`, so both installs reported failure over the
# consumers' own design, and a validation that always fails is one nobody reads.


def _consumer(tmp_path: Path, kit_skills: list[str], own_skills: list[str],
              manifest: bool = True) -> Path:
    """A `.claude/`-style tree: some skills from the kit, some the project's."""

    (tmp_path / "rules").mkdir(parents=True, exist_ok=True)
    for skill in kit_skills + own_skills:
        d = tmp_path / "skills" / skill
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(f"# {skill}\n\nNo cycle contract here.\n", encoding="utf-8")
    if manifest:
        body = ["# Written by mechanisms/distribution/install.sh"] + [f"skills/{s}" for s in kit_skills]
        (tmp_path / ".kit-manifest.txt").write_text("\n".join(body) + "\n", encoding="utf-8")
    return tmp_path


def test_a_skill_the_manifest_does_not_claim_is_the_projects(tmp_path: Path) -> None:
    from check_xrefs import _kit_owned_skills

    root = _consumer(tmp_path, kit_skills=["acceptance", "review"], own_skills=["cnpg-audit"])
    assert _kit_owned_skills(root) == {"acceptance", "review"}


def test_the_kits_own_repository_has_no_manifest_and_keeps_every_check(tmp_path: Path) -> None:
    """Without a consumer there is no project half; the checks must apply in full."""
    from check_xrefs import _kit_owned_skills

    root = _consumer(tmp_path, kit_skills=["acceptance"], own_skills=[], manifest=False)
    assert _kit_owned_skills(root) is None


def test_an_empty_manifest_reads_as_absent(tmp_path: Path) -> None:
    """A manifest listing no skill cannot mean "every skill is the project's"."""
    from check_xrefs import _kit_owned_skills

    (tmp_path / ".kit-manifest.txt").write_text("# nothing here\n", encoding="utf-8")
    assert _kit_owned_skills(tmp_path) is None


def test_a_manifest_path_below_the_skill_still_names_the_skill(tmp_path: Path) -> None:
    from check_xrefs import _kit_owned_skills

    (tmp_path / ".kit-manifest.txt").write_text(
        "skills/review/SKILL.md\nskills/review/scripts/run.py\n", encoding="utf-8")
    assert _kit_owned_skills(tmp_path) == {"review"}


def test_a_skill_name_containing_cycle_is_not_a_cycle_reference() -> None:
    """`middleware-life` + `cycle-engineer` is one word, not a rule reference.

    Measured on 2026-08-31 in a live consumer: this produced a hard FAIL claiming the
    skill referenced `cycle-engineer.md`, a rule nobody wrote, on a skill that names
    no cycle at all. Reachable because a SKILL.md with no `## Cycle contract` section
    is scanned whole, and a file always contains its own name.
    """
    from check_xrefs import _extract_cycle_contract_ref

    body = "---\nname: middleware-lifecycle-engineer\n---\n\n# Middleware Lifecycle Engineer\n"
    try:
        assert _extract_cycle_contract_ref(body) is None
    except TypeError:                       # the sibling kit passes known skills too
        assert _extract_cycle_contract_ref(body, set()) is None


def test_a_cycle_contract_reference_still_resolves() -> None:
    """The fix must not blind the check it protects.

    Renamed: this shared a name with the `CYCLE_NAME_RE` test above, and in Python the
    second definition simply replaces the first — so the earlier test had never run.
    Two tests, one name, one of them silently absent from every green run.
    """
    from check_xrefs import _extract_cycle_contract_ref

    body = "## Cycle contract\n\nOwned by `cycle-plan.md`.\n"
    try:
        assert _extract_cycle_contract_ref(body) == "plan"
    except TypeError:
        assert _extract_cycle_contract_ref(body, set()) == "plan"


def test_a_broken_reference_in_the_projects_own_file_warns_rather_than_fails(tmp_path: Path) -> None:
    """The kit cannot fail its own installation over a line it did not write.

    Measured across three consumers on 2026-08-31: each carried skills of its own
    citing a cycle rule the SIBLING kit ships. They hold one kit's artefacts while
    installed with the other — worth telling them, and not a reason to call the
    install broken. `install.sh` runs this `--strict`.
    """
    from check_xrefs import validate_xrefs

    (tmp_path / "rules").mkdir(parents=True)
    (tmp_path / "rules" / "cycle-plan.md").write_text("# plan\n\n## Hard gates\n", encoding="utf-8")
    own = tmp_path / "skills" / "analysis"
    own.mkdir(parents=True)
    # Was `own.write_text if False else (own / "SKILL.md").write_text(...)` — a ternary
    # whose condition is the literal False, so the first branch was never evaluated.
    # It could not have been: `own` is a DIRECTORY, and `Path.write_text` on one raises.
    # vulture reported it as an unsatisfiable condition (kit#61).
    (own / "SKILL.md").write_text(
        "---\nname: analysis\ndescription: x\n---\n\nDriven by `cycle-roadmap`.\n",
        encoding="utf-8",
    )
    (tmp_path / ".kit-manifest.txt").write_text("skills/plan-confidence\n", encoding="utf-8")

    report = validate_xrefs(tmp_path, strict=True)
    broken = [f for f in report["findings"] if f.get("check") == "cycle_reference_resolves"]
    assert broken, "the defect must still be reported"
    assert all(f["severity"] == "WARN" for f in broken), broken


def test_the_same_reference_in_a_kit_file_still_fails(tmp_path: Path) -> None:
    """Severity depends on authorship, not on the defect being less real."""
    from check_xrefs import validate_xrefs

    (tmp_path / "rules").mkdir(parents=True)
    (tmp_path / "rules" / "cycle-plan.md").write_text("# plan\n\n## Hard gates\n", encoding="utf-8")
    kit = tmp_path / "skills" / "review"
    kit.mkdir(parents=True)
    (kit / "SKILL.md").write_text(
        "---\nname: review\ndescription: x\n---\n\nDriven by `cycle-roadmap`.\n", encoding="utf-8")
    (tmp_path / ".kit-manifest.txt").write_text("skills/review\n", encoding="utf-8")

    report = validate_xrefs(tmp_path, strict=True)
    broken = [f for f in report["findings"] if f.get("check") == "cycle_reference_resolves"]
    assert broken and all(f["severity"] == "FAIL" for f in broken), broken


def test_a_projects_own_rules_file_is_not_the_kits(tmp_path: Path) -> None:
    """The manifest lists `rules/` per FILE, so the raw paths answer for it.

    Reading only the skills half left a consumer's own `rules/*.md` looking like the
    kit's, and its broken references kept failing the kit's install on three
    repositories after the skills half was already fixed.
    """
    from check_xrefs import validate_xrefs

    (tmp_path / "rules").mkdir(parents=True)
    (tmp_path / "rules" / "cycle-plan.md").write_text("# plan\n\n## Hard gates\n", encoding="utf-8")
    (tmp_path / "rules" / "analysis-golden-rule.md").write_text(
        "Driven by `cycle-roadmap`.\n", encoding="utf-8")
    (tmp_path / ".kit-manifest.txt").write_text(
        "rules/cycle-plan.md\nskills/review\n", encoding="utf-8")

    report = validate_xrefs(tmp_path, strict=True)
    broken = [f for f in report["findings"] if f.get("check") == "cycle_reference_resolves"]
    assert broken and all(f["severity"] == "WARN" for f in broken), broken


def test_a_kit_rules_file_with_a_broken_reference_still_fails(tmp_path: Path) -> None:
    from check_xrefs import validate_xrefs

    (tmp_path / "rules").mkdir(parents=True)
    (tmp_path / "rules" / "cycle-plan.md").write_text(
        "# plan\n\n## Hard gates\n\nSee `cycle-roadmap`.\n", encoding="utf-8")
    (tmp_path / ".kit-manifest.txt").write_text("rules/cycle-plan.md\n", encoding="utf-8")

    report = validate_xrefs(tmp_path, strict=True)
    broken = [f for f in report["findings"] if f.get("check") == "cycle_reference_resolves"]
    assert broken and all(f["severity"] == "FAIL" for f in broken), broken


def test_strict_does_not_fail_over_the_projects_own_content(tmp_path: Path) -> None:
    """`--strict` is rigour about the KIT.

    After the severity fix, three consumers reported zero FAIL and five WARN — and
    `install.sh --strict` still called every one of them broken, because strict
    promotes any warning. Promoting a project-owned finding means the kit refuses to
    install over content it did not write, which is the shape the whole check was
    corrected for. The finding is unchanged and still printed; what changes is who it
    can fail.
    """
    from check_xrefs import validate_xrefs

    (tmp_path / "rules").mkdir(parents=True)
    # A COMPLETE kit rule: an incomplete one raises warnings of its own, owned by the
    # kit, and those would fail the run for a reason this test is not about.
    (tmp_path / "rules" / "cycle-plan.md").write_text(
        "# plan\n\n## Hard gates\n\n## Cross-references\n\n- none\n", encoding="utf-8")
    (tmp_path / "rules" / "own-rule.md").write_text("Driven by `cycle-roadmap`.\n", encoding="utf-8")
    (tmp_path / ".kit-manifest.txt").write_text("rules/cycle-plan.md\n", encoding="utf-8")

    report = validate_xrefs(tmp_path, strict=True)
    assert report["overall"] == "PASS", report["findings"]
    assert any(f.get("owner") == "project" for f in report["findings"]), "still reported"


def test_strict_still_fails_over_the_kits_own_content(tmp_path: Path) -> None:
    from check_xrefs import validate_xrefs

    (tmp_path / "rules").mkdir(parents=True)
    (tmp_path / "rules" / "cycle-plan.md").write_text(
        "# plan\n\n## Hard gates\n\nSee `cycle-roadmap`.\n", encoding="utf-8")
    (tmp_path / ".kit-manifest.txt").write_text("rules/cycle-plan.md\n", encoding="utf-8")

    assert validate_xrefs(tmp_path, strict=True)["overall"] == "FAIL"
