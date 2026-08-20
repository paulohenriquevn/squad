"""B-051 T1.3 — the cycle's validation asks the repository what "ready" means.

The measured defect: `run_validation.py` runs `eslint` and `tsc --noEmit` directly and never the
repository's own `gates` script. So a slice can be green by the cycle's definition and dirty by the
project's — and that is not hypothetical. `pnpm gates` was red from v0.54.0 through v0.62.0, ten
releases, while every slice in between passed validation. Three of the dirty files were written in
this session by slices that each ran `run_validation.py` and passed.

Two properties, and the second is the one that keeps the report honest: a project with no `gates`
script must SKIP with a reason, never PASS. Reporting PASS for a check that did not run is the
defect class B-019 and B-048 record elsewhere in this repository.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from run_validation import check_project_gates  # noqa: E402


def _project(tmp_path: Path, scripts: dict[str, str]) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "package.json").write_text(
        json.dumps({"name": "fixture", "version": "0.0.0", "scripts": scripts}),
        encoding="utf-8",
    )
    return root


def test_the_projects_own_gates_script_is_run(tmp_path: Path) -> None:
    # Arrange — a project whose `gates` script fails loudly, so a report of PASS could only mean
    # the script was never executed.
    root = _project(tmp_path, {"gates": "exit 3"})

    # Act
    report = check_project_gates(root)

    # Assert
    assert report["status"] == "FAIL"
    assert report["exit_code"] == 3


def test_a_missing_gates_script_skips_rather_than_passes(tmp_path: Path) -> None:
    # Arrange — a project that declares no `gates` script at all.
    root = _project(tmp_path, {"test": "true"})

    # Act
    report = check_project_gates(root)

    # Assert — SKIP with a reason. PASS here would claim a standard was met that was never checked.
    assert report["status"] == "SKIP"
    assert "gates" in report["reason"]
