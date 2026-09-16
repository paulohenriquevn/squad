"""The plan's impediment and the registry's must be the same edge."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_impediment_agrees import check_impediment_agrees  # noqa: E402


def _tree(tmp_path: Path, plan_front: str, registry_line: str) -> tuple[Path, Path]:
    plan = tmp_path / "B-018-plan.md"
    plan.write_text(f"---\nitem: B-018\n{plan_front}\n---\n\n# Plan\n", encoding="utf-8")
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(f"# Backlog\n\n## B-018 — a thing   [ ]\n\nstatus: approved\n"
                       f"{registry_line}\n", encoding="utf-8")
    return plan, backlog


def test_an_impediment_only_the_plan_declares_caps(tmp_path: Path) -> None:
    """Every scheduler resolves `blocked_by` from the REGISTRY — `select_backlog_item`,
    `board_state`, `pipeline_orchestrator`, `backlog_index`. An item whose plan says it is
    held therefore reads as free to start, and the impediment surfaces when the work hits
    it rather than when it is scheduled.

    Measured on a consumer 2026-09-16: SEVEN plans declared an impediment their registry
    block did not carry, all naming the same blocker. Nothing compared the two documents.
    """
    plan, backlog = _tree(tmp_path, "blocked_by: B-034", "")
    report = check_impediment_agrees(plan, backlog)
    assert report.missing_in_registry == ("B-034",)
    # Reported, NOT capped. A consumer refuted the cap before it ran on their tree: seven
    # of their plans declared an impediment cured two days after the plans were written,
    # and five of those score 100.0 with zero caps — which is the proof, since a plan
    # cannot reach 100.0 while the cap it names as blocking is live.
    assert not report.soft_floor
    assert any("predate its cure" in r for r in report.reasons)


def test_a_registry_edge_the_plan_omits_is_reported_not_charged(tmp_path: Path) -> None:
    """The registry is authoritative and a plan may have been written before the
    impediment was found. Capping on that direction would punish the correct order."""
    plan, backlog = _tree(tmp_path, "blocked_by: none", "blocked_by: B-034")
    report = check_impediment_agrees(plan, backlog)
    assert not report.soft_floor
    assert report.missing_in_plan == ("B-034",)


def test_an_id_in_the_reason_is_a_citation_not_an_edge(tmp_path: Path) -> None:
    """`blocked_by: B-034 — found by the B-018 panel` names ONE blocker and cites another
    item in its prose. Reading the whole line made B-018 block itself.

    The ids come before the reason; the reason is separated by an em dash, a colon or a
    semicolon, and everything after it is narrative.
    """
    plan, backlog = _tree(
        tmp_path, "blocked_by: B-034",
        "blocked_by: B-034 — declared in the plan since it was written; found by the "
        "B-018 panel, 2026-09-16")
    report = check_impediment_agrees(plan, backlog)
    assert report.registry_declares == ("B-034",)
    assert not report.soft_floor


def test_agreement_is_silent(tmp_path: Path) -> None:
    plan, backlog = _tree(tmp_path, "blocked_by: B-034", "blocked_by: B-034")
    report = check_impediment_agrees(plan, backlog)
    assert not report.soft_floor and not report.reasons
