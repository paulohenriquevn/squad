"""`/repo-backup` starts with `/repo`, and that was the whole check.

`confine` compared `str(target_abs).startswith(str(root_abs))`. A sibling directory
whose NAME extends the root's passes that test: `<root>-old` starts with
`<root>`. The function's own docstring says "verify *target* lives inside
*root*", and a string prefix is not containment — it is a coincidence of spelling.

It matters here because `init_quality_gates` now routes `--out` through this, and
`emit.py` writes executable hook scripts under whatever comes back.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "skills" / "quality-init" / "scripts"))

from gate_authoring.path_safety import (  # noqa: E402 — post-bootstrap import
    confine,
    confine_or_none,
)


def test_a_sibling_whose_name_extends_the_root_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    sibling = tmp_path / "project-old"
    sibling.mkdir()

    assert confine_or_none(str(root), str(sibling)) is None, (
        f"{sibling} is not inside {root}; only its spelling says so")
    with pytest.raises(SystemExit):
        confine(str(root), str(sibling))


def test_a_real_child_is_accepted(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / "hooks").mkdir(parents=True)

    assert confine_or_none(str(root), str(root / "hooks")) == str((root / "hooks").resolve())


def test_the_root_itself_is_inside_itself(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()

    assert confine_or_none(str(root), str(root)) == str(root.resolve())


def test_a_traversal_out_is_still_refused(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()

    assert confine_or_none(str(root), str(root / ".." / "elsewhere")) is None
