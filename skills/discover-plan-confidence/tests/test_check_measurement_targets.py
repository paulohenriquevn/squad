"""Tests for check_measurement_targets.py — verifies the fabricated-target hard cap."""
from __future__ import annotations

from pathlib import Path

import check_measurement_targets as cmt
import pytest
from check_measurement_targets import check_measurement_targets


@pytest.fixture
def rooted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Hermetic project root, so resolution never depends on the real repo's contents."""
    root = tmp_path / "project"
    (root / ".claude").mkdir(parents=True)
    monkeypatch.setattr(cmt, "_find_project_root", lambda _start: root)
    return root


def _plan(root: Path, body: str) -> Path:
    path = root / "plan.md"
    path.write_text(f"# Measurement Plan: Test\n\n{body}\n", encoding="utf-8")
    return path


def test_good_plan_targets_all_resolve(good_measurement_plan: Path) -> None:
    """The positive fixture points at real repo paths, not invented ones."""
    report = check_measurement_targets(good_measurement_plan)
    assert report["fabricated"] == 0
    assert report["verified"] > 0


def test_fabricated_target_detected(good_measurement_plan: Path, fixtures_dir: Path) -> None:
    report = check_measurement_targets(fixtures_dir / "fabricated-target-measurement-plan.md")
    assert report["fabricated"] >= 1
    assert any("does-not-exist" in t for t in report["fabricated_targets"])


def test_directory_target_is_valid(rooted: Path) -> None:
    """A plan points at what it INTENDS to open, so a directory is a legitimate target.

    This is the deliberate difference from the opportunity-side checker, where evidence
    is `file:line` and the line must exist because measurement already happened.
    """
    (rooted / "src" / "handlers").mkdir(parents=True)
    report = check_measurement_targets(_plan(rooted, "Sweep `src/handlers/` for the pattern."))
    assert report["verified"] == 1
    assert report["fabricated"] == 0


def test_blocked_target_not_counted_as_fabricated(rooted: Path) -> None:
    report = check_measurement_targets(
        _plan(rooted, "Target `src/gone/` <!-- BLOCKED: removed in the 2026-07 refactor -->")
    )
    assert report["fabricated"] == 0
    assert report["explicitly_blocked"] == 1


def test_undeclared_live_host_is_flagged(rooted: Path) -> None:
    """A plan naming a live URL no domain declares is planning a probe the cycle refuses.

    cycle-discover gate G-L refuses live-test on an undeclared domain. Catching it at
    plan time means the refusal lands while the plan is still cheap to change, rather
    than after someone has scheduled the measurement.
    """
    rules = rooted / "rules"
    rules.mkdir()
    (rules / "live-target.txt").write_text(
        "domain = frontend-dashboard\nkind = web\ntarget = https://app-dev.usetheo.dev\n",
        encoding="utf-8",
    )
    report = check_measurement_targets(_plan(rooted, "Probe https://staging.example.com/api"))
    assert report["undeclared_live_hosts"] == ["staging.example.com"]


def test_declared_live_host_passes(rooted: Path) -> None:
    rules = rooted / "rules"
    rules.mkdir()
    (rules / "live-target.txt").write_text(
        "domain = frontend-dashboard\nkind = web\ntarget = https://app-dev.usetheo.dev\n",
        encoding="utf-8",
    )
    report = check_measurement_targets(_plan(rooted, "Probe https://app-dev.usetheo.dev/api/traces"))
    assert report["undeclared_live_hosts"] == []
    assert len(report["live_targets"]) == 1


def test_no_live_target_file_does_not_flag(rooted: Path) -> None:
    """With nothing declared, the checker has no basis to call a host undeclared.

    Reporting every URL as undeclared when the declaration file is simply absent would
    be asserting a violation from missing data.
    """
    report = check_measurement_targets(_plan(rooted, "Probe https://anything.example.com/x"))
    assert report["undeclared_live_hosts"] == []


def test_backticked_prose_is_not_a_target(rooted: Path) -> None:
    """`SKIP` and other backticked words carry no slash and are not targets."""
    report = check_measurement_targets(_plan(rooted, "Method is `SKIP` for this question."))
    assert report["total"] == 0
    assert report["fabricated"] == 0


# --- B-017: an npm module specifier is not a repo path ---------------------------------
#
# `PATH_TARGET_RE` matched any backticked token containing a slash and resolved it against the
# repo root. `theokit/server/plugins` is a real npm subpath specifier — it has no extension and
# lives under node_modules — so it failed `Path.exists()` and fired `fabricated_target`, a HARD
# CAP that drops the plan to 49 and INVALID.
#
# Scoped specifiers passed, but by ACCIDENT: `@` was outside the first character class, so the
# regex never saw them. That is not the gate handling scopes; it is the gate never looking.
#
# The distinction is made by RESOLUTION, never by a list of known package names: a list needs
# maintaining, is wrong the moment a consumer adds a dependency, and would encode one repository's
# packages into a kit that others install.


def _install(root: Path, *specifiers: str) -> None:
    """Create node_modules entries the way a real install lays them out."""
    for spec in specifiers:
        (root / "node_modules" / spec).mkdir(parents=True, exist_ok=True)


def test_an_unscoped_module_specifier_is_not_fabricated(rooted: Path) -> None:
    _install(rooted, "theokit")

    report = check_measurement_targets(_plan(rooted, "Read `theokit/server/plugins` for the seam."))

    assert report["fabricated"] == 0, report["fabricated_targets"]


def test_a_scoped_module_specifier_is_recognised_rather_than_skipped(rooted: Path) -> None:
    # It must now be SEEN and classified, not merely absent from the match set.
    _install(rooted, "@theokit/sdk")

    report = check_measurement_targets(_plan(rooted, "Read `@theokit/sdk/server/auth` for the type."))

    assert report["fabricated"] == 0, report["fabricated_targets"]


def test_a_package_that_exists_only_in_the_pnpm_store_resolves(rooted: Path) -> None:
    # pnpm nests the real package two levels down. A top-level-only check misses every one of them,
    # which in this workspace is all of them.
    (rooted / "node_modules" / ".pnpm" / "theokit@0.48.8" / "node_modules" / "theokit").mkdir(
        parents=True
    )

    report = check_measurement_targets(_plan(rooted, "Read `theokit/server/plugins` for the seam."))

    assert report["fabricated"] == 0, report["fabricated_targets"]


def test_a_specifier_for_a_package_that_is_not_installed_is_still_fabricated(rooted: Path) -> None:
    # The cap stays armed. A plan naming a dependency the tree does not have points at nothing,
    # and saying so is the correct answer rather than a false positive.
    report = check_measurement_targets(_plan(rooted, "Read `absent-package/server/thing` for it."))

    assert report["fabricated"] == 1, report["fabricated_targets"]


def test_a_tree_without_node_modules_reports_a_miss_rather_than_raising(rooted: Path) -> None:
    report = check_measurement_targets(_plan(rooted, "Read `theokit/server/plugins` for the seam."))

    assert report["fabricated"] == 1, report["fabricated_targets"]
