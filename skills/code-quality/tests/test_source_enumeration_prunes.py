"""Source enumeration PRUNES during the walk, it does not filter afterwards.

`_enumerate_source_files` descended into `node_modules`, `.git` and `.venv` whole and
and only then discarded what it had found. The result was the same; the cost was
not. Measured 2026-08-26 on a 56,128-file repository (40k of them in
`node_modules`): 326 ms walking everything against 0.4 ms pruning — 832x, once
per enabled language.

This is the same lesson the CHANGELOG already records for `check_wiring.py`
(1080 ms -> 13 ms, 83x). The tests below pin the SHAPE the speed comes from,
because a duration assertion is a flaky test on a loaded machine.
"""
from __future__ import annotations

import pathlib
from pathlib import Path

import pytest

from scripts.run_code_quality import _enumerate_source_files


def _tree(root: Path) -> None:
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    for skipped in ("node_modules", ".git", ".venv", "__pycache__", "dist"):
        d = root / skipped / "deep" / "deeper"
        d.mkdir(parents=True)
        (d / "noise.py").write_text("x = 1\n", encoding="utf-8")


def test_finds_project_sources(tmp_path):
    _tree(tmp_path)
    names = {p.name for p in _enumerate_source_files(tmp_path, "python")}
    assert names == {"app.py"}


def test_does_not_traverse_skipped_trees(tmp_path, monkeypatch):
    """No `rglob` over the whole tree — the pruning has to happen during it.

    An `rglob("*")` followed by a filter produces the right answer the wrong
    way: it has already descended into everything it was going to discard. Banning
    the primitive is what makes the pruning verifiable without a stopwatch.
    """
    _tree(tmp_path)

    def forbidden(self, *args, **kwargs):
        raise AssertionError(
            "rglob over the whole tree: pruning went back to happening after the walk"
        )

    monkeypatch.setattr(pathlib.Path, "rglob", forbidden)

    names = {p.name for p in _enumerate_source_files(tmp_path, "python")}
    assert names == {"app.py"}


@pytest.mark.parametrize(
    ("language", "filename"),
    [("typescript", "a.ts"), ("rust", "a.rs"), ("go", "a.go")],
)
def test_other_languages_keep_working(tmp_path, language, filename):
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "src" / filename).write_text("// x\n", encoding="utf-8")
    (tmp_path / "node_modules" / "dep").mkdir(parents=True)
    (tmp_path / "node_modules" / "dep" / filename).write_text("// x\n", encoding="utf-8")
    names = {p.name for p in _enumerate_source_files(tmp_path, language)}
    assert names == {filename}
