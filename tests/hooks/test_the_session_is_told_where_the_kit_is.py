"""The SessionStart block pointed at two paths the plugin layout does not have.

`chain_lines(layout.eco)` joined `rules/squad-map.md` and
`mechanisms/cycle/route_domain.py` to the cycle's DATA root. Both are the KIT's code,
and `squad/layout.py` says so: "kit_dir the kit's code (skills/, rules/, hooks/) ...
Under the native plugin layout it lives OUTSIDE the project."

So under a plugin install every session was handed two paths that do not exist, in the
block whose whole job is telling it where to look — and the map it names is the one a
session opens when it does not know the chain.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HOOK = Path(__file__).resolve().parents[2] / "hooks" / "sessionstart-context.py"
_spec = importlib.util.spec_from_file_location("sessionstart_context", _HOOK)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["sessionstart_context"] = _mod
_spec.loader.exec_module(_mod)


def _plugin_layout(tmp_path: Path):
    """The shape the finding is about: the kit OUTSIDE the project."""
    from squad.layout import Layout

    kit = tmp_path / "plugins" / "squad"
    for tree in ("skills", "rules", "hooks"):
        (kit / tree).mkdir(parents=True, exist_ok=True)
    project = tmp_path / "a-project"
    project.mkdir()
    return Layout(kit_dir=kit, eco=project, project_dir=project, kind="plugin")


def test_the_map_is_named_under_the_kit_not_the_data_root(tmp_path: Path) -> None:
    layout = _plugin_layout(tmp_path)

    block = "\n".join(_mod.chain_lines(layout.kit_dir))

    assert f"{layout.kit_dir}/rules/squad-map.md" in block
    assert f"{layout.eco}/rules/squad-map.md" not in block


def test_the_router_is_named_under_the_kit_too(tmp_path: Path) -> None:
    layout = _plugin_layout(tmp_path)

    block = "\n".join(_mod.chain_lines(layout.kit_dir))

    assert f"{layout.kit_dir}/mechanisms/cycle/route_domain.py" in block


def test_every_path_the_block_names_exists_in_a_copy_install(tmp_path: Path) -> None:
    """The layout where the two roots coincide: every named path must resolve."""
    from squad.layout import Layout

    root = tmp_path / "project"
    for tree in ("skills", "rules", "hooks", "mechanisms/cycle"):
        (root / ".claude" / tree).mkdir(parents=True, exist_ok=True)
    (root / ".claude" / "rules" / "squad-map.md").write_text("# map\n", encoding="utf-8")
    (root / ".claude" / "mechanisms" / "cycle" / "route_domain.py").write_text(
        "", encoding="utf-8")
    layout = Layout(kit_dir=root / ".claude", eco=root / ".claude",
                    project_dir=root, kind="copy")

    block = "\n".join(_mod.chain_lines(layout.kit_dir))

    for fragment in ("rules/squad-map.md", "mechanisms/cycle/route_domain.py"):
        named = next(part for line in block.splitlines() for part in line.split()
                     if fragment in part)
        assert Path(named.rstrip(";)")).exists(), named
