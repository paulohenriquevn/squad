"""`next_item` justified shelling out on layout grounds and then hardcoded one layout.

Its docstring: "the selector lives in the installed kit beside the project, and
importing it would bind the lead to one layout." The next statement joined a literal
`.claude/skills/...` to the project root — which binds it to one layout by a different
route. `squad/layout.py` defines three, and under the plugin install the kit sits
OUTSIDE the project, so there the lead returned "SELECT is not installed at
<project>/.claude/skills/..." on every single turn and never selected anything.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "mechanisms" / "fleet"))
sys.path.insert(0, str(_ROOT))

from squad_lead import Lead  # noqa: E402 — post-bootstrap import

_SELECTOR = "skills/backlog-review/scripts/select_backlog_item.py"


def _install(root: Path, under: str) -> Path:
    path = root / under / _SELECTOR if under else root / _SELECTOR
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("print('{}')\n", encoding="utf-8")
    for tree in ("skills", "rules", "hooks"):
        ((root / under) if under else root).joinpath(tree).mkdir(exist_ok=True)
    return path


def test_the_standalone_layout_is_found(tmp_path: Path) -> None:
    expected = _install(tmp_path, "")
    (tmp_path / "BACKLOG.md").write_text("# backlog\n", encoding="utf-8")

    assert Lead(session="t", project=tmp_path)._selector_path() == expected


def test_the_copy_install_layout_is_found(tmp_path: Path) -> None:
    expected = _install(tmp_path, ".claude")
    (tmp_path / "BACKLOG.md").write_text("# backlog\n", encoding="utf-8")

    assert Lead(session="t", project=tmp_path)._selector_path() == expected


def test_a_tree_with_no_selector_says_so(tmp_path: Path) -> None:
    item, why = Lead(session="t", project=tmp_path).next_item()

    assert item is None
    assert "SELECT is not installed" in why, why
