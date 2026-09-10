"""The fit diagnosis, and the three ways it lied before real data corrected it.

Every check here delegates its judgement to a mechanism that already owns it, so
these tests are not about routing or panels — they are about the seam. The three
regression tests at the top pin defects that a run against real consumer installs
exposed, each one a version of the same mistake: reporting a conclusion about
something that was never established.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from check_squad_fit import (  # noqa: E402
    EXIT,
    Finding,
    Section,
    _frontmatter,
    _kit_skill_names,
    diagnose,
    diagnose_agents,
    diagnose_panel,
    diagnose_skills,
    eco_dir,
    main,
    verdict_of,
)


def _install(root: Path, *, manifest: bool = True) -> Path:
    """A consumer install: kit under `.claude/`, with the manifest the installer writes."""
    eco = root / ".claude"
    (eco / "skills").mkdir(parents=True)
    (eco / "rules").mkdir(parents=True)
    (eco / "agents").mkdir(parents=True)
    if manifest:
        (eco / ".kit-manifest.txt").write_text(
            "# Written by scripts/install.sh\nskills/acceptance\nskills/review\n",
            encoding="utf-8")
    return eco


def _skill(eco: Path, name: str, *, sop: bool = True, invocable: bool = True,
           cycle: bool = False) -> None:
    d = eco / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    body = "\n## Cycle contract\n\nPart of cycle-x.\n" if cycle else "\nBody.\n"
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: does a thing\n"
        f"user-invocable: {'true' if invocable else 'false'}\n---\n{body}",
        encoding="utf-8")
    if sop:
        (d / "SOP.md").write_text("---\nsop: x\n---\n", encoding="utf-8")


# ---------------------------------------------------------------- regressions


def test_indistinguishable_kit_skills_are_not_all_reported_as_the_projects(tmp_path: Path) -> None:
    """The defect: no manifest and no map meant every kit skill was reported as the project's.

    Measured against a real consumer install: 51 major findings, every one against a
    skill the kit shipped, none actionable. The first version called this
    "over-reporting rather than under-reporting, the safe direction for a diagnostic".
    It is not a safe direction. It is the same substitution as passing, made against
    a different column, and a report of 51 items nobody can act on is read once.
    """
    eco = _install(tmp_path, manifest=False)
    _skill(eco, "acceptance", sop=False)
    _skill(eco, "review", sop=False)

    section = diagnose_skills(tmp_path)

    assert section.measured is False
    assert section.findings == []
    assert "kit-manifest" in section.unmeasured_because


def test_the_manifest_is_believed_over_anything_else(tmp_path: Path) -> None:
    """`.kit-manifest.txt` says it in its own header: anything not here is the project's."""
    eco = _install(tmp_path)
    _skill(eco, "acceptance", sop=False)   # kit — must be ignored
    _skill(eco, "our-thing", sop=False)    # ours — must be reported

    section = diagnose_skills(tmp_path)

    assert _kit_skill_names(tmp_path) == {"acceptance", "review"}
    reported = {f.subject for f in section.findings}
    assert "our-thing" in reported
    assert "acceptance" not in reported


def test_a_specialist_naming_its_repo_in_the_singular_is_not_thin(tmp_path: Path) -> None:
    """The defect: the presence test demanded the word `repos`, and files write `repo`.

    Six of six hand-written specialists in a real ecosystem were reported thin, every
    one of them false — including one whose first line reads `**Covers:** \\`theo\\``
    and which carries a verified multi-module build section. The check now compares
    against the repos the ROUTING TABLE assigns, which is a fact rather than a word.
    """
    eco = _install(tmp_path)
    (eco / "rules" / "domain-routing.txt").write_text(
        "engine | theo | `agents/engine-go.md`\n", encoding="utf-8")
    (eco / "agents" / "engine-go.md").write_text(
        "# engine-go\n\n**Covers:** `theo` (4419 commits).\n\n"
        "```bash\ncd theo && task quality:all\n```\n", encoding="utf-8")

    section = diagnose_agents(tmp_path)

    assert section.measured is True
    assert section.findings == [], [f.code for f in section.findings]


def test_a_generated_knowledge_skill_is_not_asked_for_an_operating_procedure(tmp_path: Path) -> None:
    """`/review` writes one per reviewer per plan, each `user-invocable: false`.

    Five in one measured consumer, each saying in its own body "not invoked directly".
    An SOP is the procedure a PERSON follows to operate the skill; for an act nobody
    performs there is no procedure to write.
    """
    eco = _install(tmp_path)
    _skill(eco, "review-slug-tests-knowledge", sop=False, invocable=False)

    section = diagnose_skills(tmp_path)

    assert [f.code for f in section.findings] == []
    assert section.facts["own_generated"] == 1


# ---------------------------------------------------------------- not measured


def test_a_section_that_was_not_measured_must_say_why() -> None:
    with pytest.raises(ValueError, match="does not say why"):
        Section("agents", measured=False)


def test_a_missing_routing_table_is_not_every_domain_uncovered(tmp_path: Path) -> None:
    """Reporting a violation from absent data asserts what the evidence cannot support."""
    _install(tmp_path)

    section = diagnose_agents(tmp_path)

    assert section.measured is False
    assert section.findings == []
    assert "detect_domains.py" in section.unmeasured_because


def test_an_unparseable_routing_table_is_unmeasured_rather_than_clean(tmp_path: Path) -> None:
    eco = _install(tmp_path)
    (eco / "rules" / "domain-routing.txt").write_text("nothing parseable\n", encoding="utf-8")

    section = diagnose_agents(tmp_path)

    assert section.measured is False
    assert "did not parse" in section.unmeasured_because


def test_a_clean_verdict_over_an_unmeasured_section_exits_two(tmp_path: Path, capsys, monkeypatch) -> None:
    """The doctrine, at the exit code: an inability to measure never becomes a pass.

    Every section that RAN was clean, so the verdict is SHIPPABLE and `EXIT` maps it
    to 0. Returning 0 would tell a caller the squad fits here, about an install where
    nothing looked at routing.
    """
    eco = _install(tmp_path)
    _skill(eco, "acceptance")   # kit skill; nothing of the project's to report

    # The panel gate reads the machine's PATH, so its answer varies by host. Pinned
    # here so this test asserts the exit rule and not the state of a laptop.
    monkeypatch.setattr("check_squad_fit.diagnose_panel",
                        lambda project, runner=None: Section("panel", measured=True))

    code = main([str(tmp_path)])
    out = capsys.readouterr().out

    assert code == 2
    assert "PARTIAL" in out
    assert "agents" in out


# ---------------------------------------------------------------- agents


def test_a_domain_routing_to_a_missing_specialist_is_a_blocker(tmp_path: Path) -> None:
    """The same fact `route_domain.py` reports as exit 3, asked of every domain at once."""
    eco = _install(tmp_path)
    (eco / "rules" / "domain-routing.txt").write_text(
        "payments | billing-api | `agents/payments.md`\n", encoding="utf-8")

    section = diagnose_agents(tmp_path)

    assert [f.code for f in section.findings] == ["domain_without_agent"]
    assert section.findings[0].severity == "blocker"
    assert "billing-api" in section.findings[0].detail


def test_a_specialist_naming_none_of_its_repos_is_reported(tmp_path: Path) -> None:
    eco = _install(tmp_path)
    (eco / "rules" / "domain-routing.txt").write_text(
        "payments | billing-api | `agents/payments.md`\n", encoding="utf-8")
    (eco / "agents" / "payments.md").write_text(
        "# payments\n\nHandles money.\n\n```bash\nmake test\n```\n", encoding="utf-8")

    codes = [f.code for f in diagnose_agents(tmp_path).findings]

    assert "agent_names_none_of_its_repos" in codes


def test_omitting_one_repo_of_several_is_a_minor_not_a_major(tmp_path: Path) -> None:
    """Partial knowledge and no knowledge take different actions and different readers."""
    eco = _install(tmp_path)
    (eco / "rules" / "domain-routing.txt").write_text(
        "payments | billing-api, ledger | `agents/payments.md`\n", encoding="utf-8")
    (eco / "agents" / "payments.md").write_text(
        "# payments\n\nCovers `billing-api`.\n\n```bash\nmake test\n```\n", encoding="utf-8")

    findings = {f.code: f for f in diagnose_agents(tmp_path).findings}

    assert "agent_omits_a_repo" in findings
    assert findings["agent_omits_a_repo"].severity == "minor"
    assert "ledger" in findings["agent_omits_a_repo"].detail


# ---------------------------------------------------------------- panel


@pytest.mark.parametrize("value,expect_code,expect_severity", [
    ("holds", None, None),
    ("violated", "panel_not_formable", "blocker"),
    ("unreachable", "panel_reviewer_unreachable", "major"),
])
def test_violated_and_unreachable_do_not_collapse(tmp_path: Path, value: str,
                                                  expect_code, expect_severity) -> None:
    """The gate separated these on 2026-09-08 and recorded what conflating them cost.

    A PATH with no `codex` reported VIOLATED, which would have failed CI for a
    repository with nothing wrong with it. A declaration that can form no panel
    anywhere is the project's defect; a reviewer missing on THIS machine is not.
    """
    eco = _install(tmp_path)
    (eco / "rules" / "review-panel.txt").write_text("reviewer = discover | a | m | builtin\n",
                                                    encoding="utf-8")

    class _Result:
        def __init__(self, v): self.value = v

    section = diagnose_panel(tmp_path, runner=lambda *a, **k: _Result(value))

    assert section.measured is True
    if expect_code is None:
        assert section.findings == []
    else:
        assert [f.code for f in section.findings] == [expect_code]
        assert section.findings[0].severity == expect_severity


def test_an_absent_declaration_is_not_reported_as_a_roster_to_edit(tmp_path: Path) -> None:
    """The gate calls both VIOLATED; the person reading this takes opposite actions.

    Measured across three real consumer installs: all three had no `review-panel.txt`
    at all, because they predate the declaration. A report saying "a phase has fewer
    than three seats" would have sent three people to open a file that was not there.
    """
    _install(tmp_path)   # no rules/review-panel.txt

    section = diagnose_panel(tmp_path, runner=lambda *a, **k: pytest.fail(
        "the gate must not be consulted about a file that does not exist"))

    assert [f.code for f in section.findings] == ["panel_not_declared"]
    assert section.findings[0].severity == "blocker"
    assert "copy" in section.findings[0].detail


def test_an_unparseable_panel_declaration_is_unmeasured(tmp_path: Path) -> None:
    eco = _install(tmp_path)
    (eco / "rules" / "review-panel.txt").write_text("garbage\n", encoding="utf-8")

    class _Result:
        value = "unchecked"

    section = diagnose_panel(tmp_path, runner=lambda *a, **k: _Result())

    assert section.measured is False
    assert section.findings == []


def test_a_gate_that_raises_is_not_a_pass(tmp_path: Path) -> None:
    eco = _install(tmp_path)
    (eco / "rules" / "review-panel.txt").write_text("reviewer = x\n", encoding="utf-8")

    def _boom(*a, **k):
        raise RuntimeError("registry vanished")

    section = diagnose_panel(tmp_path, runner=_boom)

    assert section.measured is False
    assert "RuntimeError" in section.unmeasured_because


# ---------------------------------------------------------------- verdict


@pytest.mark.parametrize("severities,expected", [
    ([], "SHIPPABLE"),
    (["minor"], "SHIPPABLE_WITH_CAVEATS"),
    (["major", "minor"], "NEEDS_REVISION"),
    (["blocker", "major"], "INVALID"),
])
def test_the_verdict_is_derived_from_the_worst_finding(severities, expected) -> None:
    section = Section("x", measured=True, findings=[
        Finding("c", sev, "deterministic", "s", "d") for sev in severities])

    assert verdict_of([section]) == expected


def test_findings_in_an_unmeasured_section_cannot_reach_the_verdict() -> None:
    """A section with `measured=False` has no findings by construction; assert the seam."""
    measured = Section("a", measured=True, findings=[])
    unmeasured = Section("b", measured=False, unmeasured_because="could not read")
    unmeasured.findings.append(Finding("x", "blocker", "deterministic", "s", "d"))

    assert verdict_of([measured, unmeasured]) == "SHIPPABLE"


def test_every_verdict_token_is_declared_in_the_bands_registry() -> None:
    """Tokens are never invented. `rules/verdict-bands.txt` is where they are declared."""
    bands = Path(__file__).resolve().parents[3] / "rules" / "verdict-bands.txt"
    declared = {line.split("|")[0].strip() for line in bands.read_text(encoding="utf-8").splitlines()
                if "|" in line and not line.lstrip().startswith("#")}

    assert set(EXIT) <= declared, set(EXIT) - declared


# ---------------------------------------------------------------- layout


def test_both_install_layouts_resolve(tmp_path: Path) -> None:
    """A plugin install nests the kit under `.claude/`; a standalone copy is the project."""
    nested = tmp_path / "nested"
    _install(nested)
    assert eco_dir(nested) == nested / ".claude"

    flat = tmp_path / "flat"
    (flat / "skills").mkdir(parents=True)
    assert eco_dir(flat) == flat


def test_frontmatter_without_pyyaml(tmp_path: Path) -> None:
    """Consumer installs may have no PyYAML; the question is whether fields exist."""
    assert _frontmatter("---\nname: x\nuser-invocable: false\n---\nbody") == {
        "name": "x", "user-invocable": "false"}
    assert _frontmatter("no frontmatter") is None
    assert _frontmatter("---\nunterminated\n") is None


def test_the_report_names_every_section_it_could_not_measure(tmp_path: Path) -> None:
    _install(tmp_path)

    report = diagnose(tmp_path)

    assert report["partial"] is True
    assert "agents" in report["unmeasured_sections"]
