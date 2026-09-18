"""`/review` resolved its project root to `<project>/.squad` and every gate below it
was asked about the wrong tree.

`_project_root_for` walks up from the findings directory and returns the first ancestor
where `records_dir()` answers. `records_dir` falls back through `LEGACY_RECORDS_ROOTS`,
one of which is the bare `records` — and from inside `.squad`, `records` matches
`.squad/records`, the very directory whose existence makes the PARENT the root.

So the walk stops one level too deep, on a directory that is not a project:

    real root        /project
    returned         /project/.squad
    rules/review-auditors.txt found from it?   No

Measured consequence on a consumer, 2026-09-18: `auditor_coverage_findings` got that
root, `registry_path` looked under `.squad/rules/`, the file was not there, and the gate
returned zero findings. `/review` emitted `READY_TO_MERGE_WITH_FOLLOWUPS` on a change
whose two required audits had never run, with no mention of them in the report.
`cycle-review.md` requires those to enter "as BLOCKER findings so the verdict cannot be
computed while ignoring it".

The data directory is never a project root — `squad/paths.py` owns that name and the
walk can ask it rather than inferring from a legacy match.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "skills" / "review" / "scripts"))
sys.path.insert(0, str(_ROOT))

from consolidate_findings import _project_root_for  # noqa: E402 — post-bootstrap

from squad.paths import DATA_DIRNAME  # noqa: E402 — post-bootstrap


def test_the_walk_does_not_stop_inside_the_write_root(tmp_path: Path) -> None:
    """The exact layout `/review` produces: findings under `.squad/records/reviews/…`."""
    findings = tmp_path / DATA_DIRNAME / "records" / "reviews" / "slug" / "findings"
    findings.mkdir(parents=True)
    (tmp_path / "rules").mkdir()

    assert _project_root_for(findings) == tmp_path, (
        f"the walk stopped at {_project_root_for(findings)}; every gate below is now "
        f"being asked about a directory that is not a project")


def test_the_returned_root_can_see_the_projects_rules(tmp_path: Path) -> None:
    """The consequence that mattered, asserted directly rather than through the path."""
    findings = tmp_path / DATA_DIRNAME / "records" / "reviews" / "slug" / "findings"
    findings.mkdir(parents=True)
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "review-auditors.txt").write_text("# x\n", encoding="utf-8")

    root = _project_root_for(findings)
    assert (root / "rules" / "review-auditors.txt").is_file(), (
        "the root the review will use cannot see the auditor registry, which is how a "
        "required audit goes unmentioned instead of blocking")


def test_a_legacy_layout_still_resolves(tmp_path: Path) -> None:
    """The half that must not go quiet. A consumer that has not migrated keeps a bare
    `records/` at its root, and skipping the data dir must not skip that."""
    findings = tmp_path / "records" / "reviews" / "slug" / "findings"
    findings.mkdir(parents=True)

    assert _project_root_for(findings) == tmp_path


def test_a_plugin_layout_still_resolves(tmp_path: Path) -> None:
    """`.claude/records` — the documented plugin install."""
    findings = tmp_path / ".claude" / "records" / "reviews" / "slug" / "findings"
    findings.mkdir(parents=True)

    assert _project_root_for(findings) == tmp_path
