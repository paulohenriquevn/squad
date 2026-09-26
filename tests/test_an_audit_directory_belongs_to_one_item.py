"""Each item's audit writes to its own directory, so one item's audit is not another's.

`Auditor.output_dir` returned `.squad/records/audits/<plugin>` — per plugin, not per
item. The plugins' databases are append-only across runs (loop-code-review's
`init_db` is ten `CREATE TABLE IF NOT EXISTS` and drops nothing), so the next item's
audit reused the previous item's database and its findings, and the coverage gate —
which binds a report to its assignment by mtime only — could not tell.

Keying the directory by item removes the shared state rather than detecting it. An
assignment written before this change carries its own `output_dir` string, and the
gate reads that string, so an older assignment on disk still resolves where it was
written.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "tests"))
sys.path.insert(0, str(_REPO / "mechanisms" / "cycle"))
sys.path.insert(0, str(_REPO / "mechanisms" / "gates"))

from check_auditor_coverage import NOT_COVERED, check  # noqa: E402
from select_auditors import INVALID, assignment_path, select  # noqa: E402
from test_select_auditors import ALL_PLUGINS, _config, _project  # noqa: E402

REGISTRY = "auditor = always | loop-code-review | analysis-scoped\n"


def _assign(project: Path, cfg: Path, slug: str) -> dict:
    _, result = select(slug, [], project=project, config_dir=cfg, diff_base="develop")
    path = assignment_path(project, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result), encoding="utf-8")
    return result["required"][0]


def test_two_items_audit_into_different_directories(tmp_path: Path) -> None:
    project, cfg = _project(tmp_path, REGISTRY), _config(tmp_path, *ALL_PLUGINS)

    first, second = _assign(project, cfg, "B-014"), _assign(project, cfg, "B-015")

    assert first["output_dir"] != second["output_dir"]
    assert "B-014" in Path(first["output_dir"]).parts
    assert f"--output-dir {second['output_dir']}" in second["command"]


def test_the_gate_for_one_item_does_not_accept_the_other_items_report(tmp_path: Path) -> None:
    project, cfg = _project(tmp_path, REGISTRY), _config(tmp_path, *ALL_PLUGINS)
    first = _assign(project, cfg, "B-014")
    _assign(project, cfg, "B-015")
    Path(first["output_dir"]).mkdir(parents=True, exist_ok=True)
    (Path(first["output_dir"]) / "final_report.md").write_text("# report\n", encoding="utf-8")

    code, result = check("B-015", project=project, config_dir=cfg)

    assert code == NOT_COVERED
    assert result["auditors"][0]["state"] == "no_report"


def test_a_slug_that_would_leave_the_audits_directory_is_refused(tmp_path: Path) -> None:
    project, cfg = _project(tmp_path, REGISTRY), _config(tmp_path, *ALL_PLUGINS)

    code, result = select("../elsewhere", [], project=project, config_dir=cfg)

    assert code == INVALID
    assert "slug" in result["detail"]
