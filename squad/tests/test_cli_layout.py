"""Where each verb looks, when the kit is not the project.

In this repository `kit_dir`, `eco` and `project_dir` are the same directory, so a CLI
that confuses them works perfectly here and breaks on every consumer. That is the exact
shape of defect this kit keeps finding — `route_domain.py` resolved its root from its
own file and read the kit's empty table instead of the consumer's (kit#37), and
`attest_plan.sh` and `squad/plan.py` resolved two different roots so tamper detection
was inert (kit#36).

The distinction that matters here: the MECHANISMS live in `kit_dir`, and the
`.github/workflows` the CI verbs read lives in `project_dir`. Under a copy install those
are `<project>/.claude` and `<project>` — different directories.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from squad.cli import paths as cli_paths  # noqa: E402


def _fake_install(tmp_path: Path) -> Path:
    """A copy install: the kit under `.claude/`, the project around it."""
    project = tmp_path / "consumer"
    kit = project / ".claude"
    for tree in ("skills", "rules", "hooks", "mechanisms"):
        (kit / tree).mkdir(parents=True)
    (project / ".github" / "workflows").mkdir(parents=True)
    (project / ".github" / "workflows" / "ci.yml").write_text("on: push\n", encoding="utf-8")
    return project


def test_standalone_resolves_both_to_the_same_place() -> None:
    where = cli_paths.resolve_roots(ROOT)
    assert where.kit == ROOT
    assert where.project == ROOT


def test_a_copy_install_separates_the_kit_from_the_project(tmp_path: Path) -> None:
    """The mechanisms are under `.claude/`; the workflow is not."""
    project = _fake_install(tmp_path)
    where = cli_paths.resolve_roots(project / ".claude")
    assert where.kit == project / ".claude"
    assert where.project == project


def test_the_workflow_is_found_in_the_project_not_the_kit(tmp_path: Path) -> None:
    project = _fake_install(tmp_path)
    where = cli_paths.resolve_roots(project / ".claude")
    assert where.workflow() == project / ".github" / "workflows" / "ci.yml"


def test_a_project_with_no_workflow_returns_none_rather_than_a_wrong_path(tmp_path: Path) -> None:
    """Guessing a path that does not exist is how a gate reports on the wrong tree."""
    project = tmp_path / "bare"
    (project / ".claude" / "skills").mkdir(parents=True)
    where = cli_paths.resolve_roots(project / ".claude")
    assert where.workflow() is None
