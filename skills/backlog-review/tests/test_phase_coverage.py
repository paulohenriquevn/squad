"""Which cycle phases left a record for each backlog item?

WHY THIS EXISTS
---------------
A stop gate and I spent four rounds disagreeing about whether every item had been through every
phase. Neither of us had measured it. The registry records an item's STATUS and says nothing about
which phases produced it, so "the loop ran" and "the loop did not run" were both assertions.

This turns that into a count. For each `B-NNN` it asks which cycle artifacts exist on disk —
opportunity, plan, code-quality audit, review, release record — and reports coverage.

WHAT IT CANNOT TELL YOU, stated first because it is the whole limit
-------------------------------------------------------------------
An artifact's EXISTENCE is not proof the phase was done well. A review file can be thin, a plan
can be a placeholder. This measures whether a phase left a record, which is the same distinction
`gate-scope.mjs` draws between "inspected N files" and "inspected them properly".

It also cannot see a phase that legitimately produced nothing. A one-line fix needs no plan, and
`cycle-plan.md` says so explicitly. So a missing artifact is a QUESTION, never a verdict — which
is why this reports and does not fail.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from phase_coverage import Phase, coverage_for_item, grade, scan_registry


def _kb(tmp_path: Path) -> Path:
    kb = tmp_path / "knowledge-base"
    for d in ("plans", "reviews", "audits", "releases", "discoveries/opportunities"):
        (kb / d).mkdir(parents=True)
    return kb


def test_an_item_with_no_artifacts_reports_every_phase_absent(tmp_path: Path) -> None:
    kb = _kb(tmp_path)
    assert coverage_for_item("B-001", kb) == set()


def test_a_plan_naming_the_item_in_its_frontmatter_counts(tmp_path: Path) -> None:
    kb = _kb(tmp_path)
    (kb / "plans" / "b001-thing-plan.md").write_text("---\nitem: B-001\n---\n# x\n")
    assert Phase.PLAN in coverage_for_item("B-001", kb)


def test_a_plan_naming_the_item_only_in_its_FILENAME_counts(tmp_path: Path) -> None:
    """Older plans predate the frontmatter convention; the slug is the only link they carry."""
    kb = _kb(tmp_path)
    (kb / "plans" / "b002-other-plan.md").write_text("# no frontmatter here\n")
    assert Phase.PLAN in coverage_for_item("B-002", kb)


def test_a_plan_for_a_DIFFERENT_item_does_not_count(tmp_path: Path) -> None:
    """B-010 must not be satisfied by B-100's plan — the prefix is a trap, not a match."""
    kb = _kb(tmp_path)
    (kb / "plans" / "b100-other-plan.md").write_text("---\nitem: B-100\n---\n")
    assert coverage_for_item("B-010", kb) == set()


def test_each_directory_maps_to_its_own_phase(tmp_path: Path) -> None:
    kb = _kb(tmp_path)
    (kb / "discoveries" / "opportunities" / "b003-x-opportunity.md").write_text("B-003\n")
    (kb / "audits" / "b003-x-code-quality.md").write_text("B-003\n")
    (kb / "reviews" / "b003-x-review.md").write_text("B-003\n")
    (kb / "releases" / "0.1.0-release.md").write_text("items | B-003\n")

    found = coverage_for_item("B-003", kb)
    assert found == {Phase.DISCOVER, Phase.CODE_QUALITY, Phase.REVIEW, Phase.RELEASE}


def test_scan_reports_every_item_and_never_fails(tmp_path: Path) -> None:
    """Reports, never fails — a missing artifact is a question, not a verdict."""
    kb = _kb(tmp_path)
    registry = tmp_path / "BACKLOG.md"
    registry.write_text(
        "## B-001 — a   [x]\n\nstatus: shipped\n\n"
        "## B-002 — b   [x]\n\nstatus: killed\n"
    )
    (kb / "plans" / "b001-a-plan.md").write_text("---\nitem: B-001\n---\n")

    report = scan_registry(registry, kb)

    assert [r.item for r in report] == ["B-001", "B-002"]
    assert report[0].phases == {Phase.PLAN}
    assert report[0].status == "shipped"
    assert report[1].phases == set()


def test_a_killed_item_is_marked_so_its_missing_phases_are_not_read_as_a_gap(tmp_path: Path) -> None:
    """A killed item ends at DISCOVER by design — counting its absent phases as debt is noise."""
    kb = _kb(tmp_path)
    registry = tmp_path / "BACKLOG.md"
    registry.write_text("## B-009 — k   [x]\n\nstatus: killed\n")

    report = scan_registry(registry, kb)
    assert report[0].expects_full_loop is False


# ---------------------------------------------------------------------------
# ADR 0012 — three classes of record, not one. The strict per-item scan above stays exactly as it
# is; this grades it.


def test_evidence_in_the_registry_block_satisfies_discover(tmp_path: Path) -> None:
    """`cycle-discover.md` has two entry paths and only one writes an opportunity file.

    A `--sweep` finding registers directly with evidence attached, and `cycle-backlog.md` makes
    `evidence:` a required field. Demanding a second record for those items is ceremony.
    """
    kb = _kb(tmp_path)
    registry = tmp_path / "BACKLOG.md"
    registry.write_text("## B-001 — a   [x]\n\nstatus: shipped\nevidence: |\n  measured at src/a.ts:12\n")

    graded = grade(scan_registry(registry, kb), registry)
    assert Phase.DISCOVER in graded[0].satisfied


def test_evidence_none_yet_does_NOT_satisfy_discover(tmp_path: Path) -> None:
    """`none-yet` is the honest value for a hunch — it is the absence of a measurement, not one."""
    kb = _kb(tmp_path)
    registry = tmp_path / "BACKLOG.md"
    registry.write_text("## B-001 — a   [x]\n\nstatus: raw\nevidence: none-yet\n")

    graded = grade(scan_registry(registry, kb), registry)
    assert Phase.DISCOVER not in graded[0].satisfied


def test_a_release_record_naming_the_item_covers_it(tmp_path: Path) -> None:
    """One release carries many items; measuring it per item is a category error on the metric."""
    kb = _kb(tmp_path)
    (kb / "releases" / "0.9.0-release.md").write_text("| items | B-001, B-002 |\n")
    registry = tmp_path / "BACKLOG.md"
    registry.write_text("## B-002 — b   [x]\n\nstatus: shipped\n")

    graded = grade(scan_registry(registry, kb), registry)
    assert Phase.RELEASE in graded[0].satisfied


def test_plan_and_review_remain_mandatory_and_are_reported_when_absent(tmp_path: Path) -> None:
    kb = _kb(tmp_path)
    registry = tmp_path / "BACKLOG.md"
    registry.write_text("## B-003 — c   [x]\n\nstatus: shipped\nevidence: |\n  src/a.ts:1\n")

    graded = grade(scan_registry(registry, kb), registry)
    # RELEASE too: the fixture has no release record, and ADR 0012 says an item is covered
    # when a release record NAMES it. My first version of this assertion omitted it — the
    # expectation was incomplete, not the code.
    assert set(graded[0].gaps) == {Phase.PLAN, Phase.REVIEW, Phase.CODE_QUALITY, Phase.RELEASE}


def test_a_plan_declared_not_warranted_is_not_a_gap(tmp_path: Path) -> None:
    """`cycle-plan.md § When to skip` names single-line changes and pure refactors."""
    kb = _kb(tmp_path)
    registry = tmp_path / "BACKLOG.md"
    registry.write_text("## B-004 — d   [x]\n\nstatus: shipped\nplan: not-warranted\n")

    graded = grade(scan_registry(registry, kb), registry)
    assert Phase.PLAN not in graded[0].gaps
