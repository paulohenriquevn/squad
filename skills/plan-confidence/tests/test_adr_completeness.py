"""Fix #4 — ADR completeness with expanded fallback patterns."""
from __future__ import annotations

from pathlib import Path

from check_adr_completeness import check_adr_completeness  # noqa: E402


def _write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "plan.md"
    p.write_text(content, encoding="utf-8")
    return p


def test_adr_with_inline_alternativa_keyword(tmp_path: Path) -> None:
    plan = _write(
        tmp_path,
        "# Plan\n\n## ADRs\n\n"
        "### D1 — toy\n"
        "- Rationale: The hooks alternative was rejected.\n"
        "- Consequences: OK\n",
    )
    report = check_adr_completeness(plan)
    assert report.with_alternatives == 1


def test_adr_with_trade_off_pattern(tmp_path: Path) -> None:
    plan = _write(
        tmp_path,
        "# Plan\n\n## ADRs\n\n"
        "### D1 — toy\n"
        "- Rationale: Trade-off entre simplicidade e performance.\n",
    )
    report = check_adr_completeness(plan)
    assert report.with_alternatives == 1


def test_adr_with_why_not_pattern(tmp_path: Path) -> None:
    plan = _write(
        tmp_path,
        "# Plan\n\n## ADRs\n\n"
        "### D1 — toy\n"
        "- Rationale: Why not use library X? Because Y.\n",
    )
    report = check_adr_completeness(plan)
    assert report.with_alternatives == 1


def test_adr_with_considered_pattern(tmp_path: Path) -> None:
    plan = _write(
        tmp_path,
        "# Plan\n\n## ADRs\n\n"
        "### D1 — toy\n"
        "- Rationale: Considered Approach X but chose Y because.\n",
    )
    report = check_adr_completeness(plan)
    assert report.with_alternatives == 1


def test_adr_with_pt_em_vez_de(tmp_path: Path) -> None:
    plan = _write(
        tmp_path,
        "# Plan\n\n## ADRs\n\n"
        "### D1 — toy\n"
        "- Rationale: We use X instead of Y because.\n",
    )
    report = check_adr_completeness(plan)
    assert report.with_alternatives == 1


def test_adr_without_alternatives_still_caught(tmp_path: Path) -> None:
    """Sanity: an ADR with zero alternative-mention should still be flagged."""
    plan = _write(
        tmp_path,
        "# Plan\n\n## ADRs\n\n"
        "### D1 — toy\n"
        "- Rationale: This is the right way.\n"
        "- Consequences: OK\n",
    )
    report = check_adr_completeness(plan)
    assert report.with_alternatives == 0
    assert "D1" in report.missing_alternatives


def test_adr_global_section_takes_precedence(tmp_path: Path) -> None:
    """Global 'Alternativas Rejeitadas' section still satisfies all ADRs."""
    plan = _write(
        tmp_path,
        "# Plan\n\n## ADRs\n\n"
        "### D1 — toy\n- Rationale: short.\n\n"
        "### D2 — toy\n- Rationale: short.\n\n"
        "## Alternativas Rejeitadas\n\n"
        "### Alt A: Some option\n"
        "Rejected by D1 because...\n",
    )
    report = check_adr_completeness(plan)
    assert report.completeness_ratio == 1.0


# ── cost-if-wrong: computed, then thrown away ────────────────────────────────
#
# `_has_cost_if_wrong` ran over every ADR block, `no_cost` collected the offenders,
# and the result went into `ADRReport.missing_cost_if_wrong` — a field no caller
# read, not even `run_structural.py`, which unpacks this report field by field. A
# check whose output reaches nobody is not a check.


def test_a_decision_with_no_cost_if_wrong_is_named(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(
        "# Plan\n\n## ADRs\n\n"
        "### D1 — pick a queue\n- Rationale: considered X. Cost if wrong: a rewrite.\n\n"
        "### D2 — pick a codec\n- Rationale: considered Y.\n",
        encoding="utf-8")

    report = check_adr_completeness(plan)

    assert report.missing_cost_if_wrong == ("D2",)


def test_a_global_alternatives_section_does_not_excuse_a_missing_cost(tmp_path: Path) -> None:
    """The comment in the source says why: a global section can hold the rejected
    alternatives for a whole plan, but the cost of being wrong belongs to one
    decision and cannot be shared. The early return for that section skipped the
    field entirely."""
    plan = tmp_path / "plan.md"
    plan.write_text(
        "# Plan\n\n## ADRs\n\n### D1 — pick a queue\n- We chose Kafka.\n\n"
        "## Rejected Alternatives\n\n- Alt A: RabbitMQ, rejected by ordering.\n",
        encoding="utf-8")

    report = check_adr_completeness(plan)

    assert report.completeness_ratio == 1.0
    assert report.missing_cost_if_wrong == ("D1",)


def test_a_plan_with_no_adrs_names_nobody(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text("# no ADRs here\n", encoding="utf-8")

    assert check_adr_completeness(plan).missing_cost_if_wrong == ()
