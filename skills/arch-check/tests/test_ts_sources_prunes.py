"""`_ts_sources` prunes during the walk instead of filtering afterwards.

The same defect measured in `run_code_quality._enumerate_source_files`: 326 ms
against 0.4 ms on a 56,000-file repository. It weighs more here, because a
TypeScript monorepo is exactly where `node_modules` is large.
"""
from __future__ import annotations

import pathlib
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from propose_rules import _ts_sources  # noqa: E402 — post-bootstrap import


def _tree(root: Path) -> None:
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.ts").write_text("export const a = 1\n", encoding="utf-8")
    (root / "src" / "app.test.ts").write_text("test('x', () => {})\n", encoding="utf-8")
    for skipped in ("node_modules", ".git", "dist", "vendor"):
        d = root / skipped / "deep"
        d.mkdir(parents=True)
        (d / "noise.ts").write_text("export const b = 2\n", encoding="utf-8")


def test_finds_project_sources_and_skips_tests(tmp_path):
    _tree(tmp_path)
    assert {p.name for p in _ts_sources(tmp_path)} == {"app.ts"}


def test_does_not_traverse_skipped_trees(tmp_path, monkeypatch):
    _tree(tmp_path)

    def forbidden(self, *args, **kwargs):
        raise AssertionError(
            "rglob over the whole tree: pruning went back to happening after the walk"
        )

    monkeypatch.setattr(pathlib.Path, "rglob", forbidden)
    assert {p.name for p in _ts_sources(tmp_path)} == {"app.ts"}
