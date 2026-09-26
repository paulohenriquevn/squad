"""TDD for check_architecture_compliance.py — verifies plans READ .claude/rules/."""
from __future__ import annotations

from pathlib import Path

import pytest

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from check_architecture_compliance import (  # noqa: E402 — post-bootstrap import
    ComplianceReport,
    check_architecture_compliance,
)

SKILL_ROOT = Path(__file__).parent.parent
PLANS_DIR = SKILL_ROOT.parent.parent / "records" / "plans"
COMPLETED_DIR = PLANS_DIR / "completed"


def _write(tmp_path: Path, content: str, name: str = "plan.md") -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# Project-rules detection

def test_reads_project_rules_when_present() -> None:
    """When invoked on a real project plan, finds .claude/rules/*.md."""
    real_plan = COMPLETED_DIR / "cli-tool-cohesion-remediation-plan.md"
    if not real_plan.exists():
        pytest.skip("real plan not found")
    report = check_architecture_compliance(real_plan)
    assert not report.fallback_to_defaults
    assert len(report.project_rules_found) > 0
    # A real project has many rules — at least these canonical ones
    rule_names = list(report.project_rules_found)
    assert "architecture.md" in rule_names
    assert "testing.md" in rule_names
    assert "domain-boundary.md" in rule_names


def test_falls_back_to_defaults_when_no_rules(tmp_path: Path) -> None:
    """Plan in a directory tree WITHOUT .claude/rules/ falls back to defaults."""
    # tmp_path is isolated; no .claude/rules/ exists above it
    plan = _write(tmp_path, "# Plan\n\n## Coverage Matrix\n\n| # | Gap | Task(s) | Resolution |\n|---|---|---|---|\n| 1 | x | T1.1 | y |\n")
    report = check_architecture_compliance(plan)
    assert report.fallback_to_defaults is True
    # Defaults dir has solid.md, dry.md, etc.
    rule_names = list(report.project_rules_found)
    assert any("solid" in n.lower() for n in rule_names)


# Rule-reference detection

def test_plan_referencing_rule_by_name_scores_higher(tmp_path: Path) -> None:
    """A plan naming a project rule is credited above one that names none.

    This test had NO assert on any path. It ended with
    `if report.fallback_to_defaults: pytest.skip(...)`, and in an isolated `tmp_path`
    that condition is always true — so it passed whatever the checker returned, under a
    name promising it checked scoring. What was missing was not an assertion but the
    fixture: the rules tree that makes the non-fallback branch reachable. It is built here.
    """
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    for name in ("architecture.md", "testing.md"):
        (rules / name).write_text(f"# {name}\n\nA project rule.\n", encoding="utf-8")

    matrix = ("## Coverage Matrix\n\n| # | Gap | Task(s) | Resolution |\n"
              "|---|---|---|---|\n| 1 | x | T1.1 | y |\n")
    naming = _write(
        tmp_path / ".claude",
        "# Plan\n\nThis plan respects `architecture.md` and `testing.md`.\n\n" + matrix,
        name="naming-plan.md")
    silent = _write(
        tmp_path / ".claude",
        "# Plan\n\nNothing is cited here at all.\n\n" + matrix,
        name="silent-plan.md")

    credited = check_architecture_compliance(naming)
    uncredited = check_architecture_compliance(silent)

    assert credited.fallback_to_defaults is False, (
        "the rules tree was not found, so the branch under test was never entered")
    assert set(credited.rules_referenced_in_plan) >= {"architecture.md", "testing.md"}
    assert credited.compliance_score > uncredited.compliance_score, (
        f"naming two rules scored {credited.compliance_score}, naming none scored "
        f"{uncredited.compliance_score} — the credit this test is named for is not given")


def test_plan_in_project_gets_credit_for_principles_even_without_rule_names() -> None:
    """Real plans typically cite principles (SOLID, DRY) rather than filenames.

    Both forms count as 'compliance signal'. This test documents that the
    checker correctly recognizes the principle-citation path.
    """
    real_plan = COMPLETED_DIR / "cli-tool-cohesion-remediation-plan.md"
    if not real_plan.exists():
        pytest.skip("real plan not found")
    report = check_architecture_compliance(real_plan)
    # The plan should get SOME credit — either via rule mention OR principle citation
    has_rule_ref = len(report.rules_referenced_in_plan) > 0
    has_principle = len(report.principles_cited) > 0
    assert has_rule_ref or has_principle, (
        f"plan should cite rules OR principles; rules: {report.rules_referenced_in_plan}, "
        f"principles: {report.principles_cited}"
    )
    # Score should be > 0 (some compliance signal present)
    assert report.compliance_score > 0


def test_plan_referencing_rule_filenames_explicitly_gets_full_credit(tmp_path: Path) -> None:
    """When a plan explicitly cites rule filenames AND principles AND DoD AND size,
    compliance_score is 1.0. This exercises the path the user wants to encourage."""
    plan = _write(
        tmp_path,
        "# Plan\n\n"
        "Per `architecture.md` and `testing.md`, this plan follows SOLID + DRY + KISS.\n"
        "All files ≤ 500 LoC.\n\n"
        "## Coverage Matrix\n\n| # | Gap | Task(s) | Resolution |\n|---|---|---|---|\n"
        "| 1 | x | T1.1 | y |\n\n"
        "## Global Definition of Done\n\n- [ ] cargo clippy passes\n",
    )
    # Real project rules dir; "architecture.md" and "testing.md" exist there.
    report = check_architecture_compliance(plan)
    if report.fallback_to_defaults:
        # tmp_path is isolated; fallback case has different rule names
        pytest.skip("test requires running inside the project, not isolated tmp_path")
    assert report.compliance_score == 1.0
    assert "architecture.md" in report.rules_referenced_in_plan


def test_principle_citations_detected(tmp_path: Path) -> None:
    """Citing SOLID, DRY, KISS, etc. counts."""
    plan = _write(
        tmp_path,
        "# Plan\n\n## ADRs\n\n### D1 — toy\n- Rationale: We follow SOLID and DRY principles. KISS first.\n\n"
        "## Coverage Matrix\n\n| # | Gap | Task(s) | Resolution |\n|---|---|---|---|\n| 1 | x | T1.1 | y |\n",
    )
    report = check_architecture_compliance(plan)
    cited = [p.lower() for p in report.principles_cited]
    assert "solid" in cited
    assert "dry" in cited
    assert "kiss" in cited


def test_dod_quality_signal_detected(tmp_path: Path) -> None:
    plan = _write(
        tmp_path,
        "# Plan\n\n## Coverage Matrix\n\n| # | Gap | Task(s) | Resolution |\n|---|---|---|---|\n"
        "| 1 | x | T1.1 | y |\n\n"
        "## Global Definition of Done\n\n- [ ] cargo clippy passes\n- [ ] mypy strict 0 errors\n",
    )
    report = check_architecture_compliance(plan)
    assert report.has_dod_quality_signal is True


def test_size_budget_signal_detected(tmp_path: Path) -> None:
    plan = _write(
        tmp_path,
        "# Plan\n\nAll files MUST stay under 500 LoC budget.\n\n"
        "## Coverage Matrix\n\n| # | Gap | Task(s) | Resolution |\n|---|---|---|---|\n| 1 | x | T1.1 | y |\n",
    )
    report = check_architecture_compliance(plan)
    assert report.has_size_budget_signal is True


# Score composition

def test_compliance_score_is_zero_for_bare_plan(tmp_path: Path) -> None:
    """A plan with no rule references, no principles, no DoD signal, no size: score 0."""
    plan = _write(
        tmp_path,
        "# Plan\n\nNothing here.\n\n"
        "## Coverage Matrix\n\n| # | Gap | Task(s) | Resolution |\n|---|---|---|---|\n| 1 | x | T1.1 | y |\n",
    )
    report = check_architecture_compliance(plan)
    assert report.compliance_score == 0.0


def test_compliance_score_is_one_for_fully_compliant_plan(tmp_path: Path) -> None:
    """Plan citing rules, principles, DoD quality, AND size budget gets 1.0."""
    # In tmp_path fallback mode, we cite `solid.md` (a default rule name).
    plan = _write(
        tmp_path,
        "# Plan\n\nFollow SOLID (solid.md) and DRY. All files ≤ 500 LoC.\n\n"
        "## Coverage Matrix\n\n| # | Gap | Task(s) | Resolution |\n|---|---|---|---|\n| 1 | x | T1.1 | y |\n\n"
        "## Global Definition of Done\n\n- [ ] cargo clippy passes\n",
    )
    report = check_architecture_compliance(plan)
    # 0.40 (rule ref) + 0.30 (principle) + 0.15 (DoD) + 0.15 (size) = 1.00
    assert report.compliance_score == 1.0


def test_compliance_reasons_are_informative(tmp_path: Path) -> None:
    plan = _write(
        tmp_path,
        "# Plan\n\n## Coverage Matrix\n\n| # | Gap | Task(s) | Resolution |\n|---|---|---|---|\n| 1 | x | T1.1 | y |\n",
    )
    report = check_architecture_compliance(plan)
    assert len(report.reasons) >= 4
    # At least one reason should say "does NOT" since this plan has nothing
    assert any("does NOT" in m or "does not" in m.lower() for m in report.reasons)


def test_compliance_report_is_dataclass() -> None:
    r = ComplianceReport(compliance_score=0.5)
    assert r.compliance_score == 0.5
    assert r.fallback_to_defaults is False


def test_compliance_is_deterministic(tmp_path: Path) -> None:
    plan = _write(tmp_path, "# Plan\n\nSOLID and DRY.\n")
    r1 = check_architecture_compliance(plan)
    r2 = check_architecture_compliance(plan)
    assert r1 == r2


def test_a_consumer_rules_tree_outside_the_kit_does_not_crash(tmp_path: Path) -> None:
    """`rules_dir.relative_to(SKILL_ROOT.parent.parent.parent)` raised for every consumer.

    The call was unguarded on the "plan cites no rule" path, and a consumer's
    `.claude/rules/` is never under this kit's parent — so the skill this exists to serve
    got a ValueError traceback instead of a reason string. No test reached the branch,
    because the only test that built a rules tree ended in `pytest.skip`.
    """
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "house-style.md").write_text("# house style\n", encoding="utf-8")
    plan = _write(tmp_path / ".claude",
                  "# Plan\n\nCites nothing.\n\n## Coverage Matrix\n\n"
                  "| # | Gap | Task(s) | Resolution |\n|---|---|---|---|\n| 1 | x | T1.1 | y |\n",
                  name="quiet-plan.md")

    report = check_architecture_compliance(plan)

    assert report.fallback_to_defaults is False
    assert any("does NOT reference" in r for r in report.reasons), report.reasons
