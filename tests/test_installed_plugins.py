"""Where a Claude Code plugin lives, answered from disk instead of guessed.

`rules/review-panel.txt` recorded on 2026-09-09 that verifying a plugin-supplied
reviewer "means asking Claude Code which plugins are installed, which nothing in this
kit does yet". That was true of the kit and false of the machine — the manifest is on
disk, and every entry carries an `installPath`.

Every test here supplies its own manifest. A test that read the real one would pass or
fail on what happens to be installed, which is a bug rather than a measurement.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mechanisms" / "conventions"))

from installed_plugins import load, manifest_path, resolve


def _config(tmp_path: Path, plugins: dict) -> Path:
    """A fake `~/.claude` holding exactly these plugins."""
    cfg = tmp_path / "claude"
    (cfg / "plugins").mkdir(parents=True, exist_ok=True)
    body = {"version": 2, "plugins": {
        name: [{"scope": "user", "installPath": str(spec["path"]),
                "version": spec.get("version", "1.0.0")}]
        for name, spec in plugins.items()}}
    (cfg / "plugins" / "installed_plugins.json").write_text(json.dumps(body), encoding="utf-8")
    return cfg


def _tree(tmp_path: Path, name: str, agents: tuple[str, ...] = ()) -> Path:
    root = tmp_path / "installed" / name
    (root / "agents").mkdir(parents=True, exist_ok=True)
    for a in agents:
        (root / "agents" / f"{a}.md").write_text(f"---\nname: {a}\n---\n", encoding="utf-8")
    return root


def test_an_installed_plugin_resolves_to_its_tree(tmp_path: Path) -> None:
    path = _tree(tmp_path, "loop-security-audit", ("threat-modeler", "sast-runner"))
    cfg = _config(tmp_path, {"loop-security-audit@market": {"path": path, "version": "0.3.1"}})

    p = resolve("loop-security-audit", cfg)

    assert p is not None
    assert p.version == "0.3.1"
    assert p.agents() == ["sast-runner", "threat-modeler"]
    assert p.has_agent("threat-modeler")
    assert not p.has_agent("nobody")


def test_a_plugin_is_reachable_by_bare_and_qualified_name(tmp_path: Path) -> None:
    """The manifest keys by `name@marketplace`; callers name the plugin."""
    path = _tree(tmp_path, "judge-codex", ("discover-judge",))
    cfg = _config(tmp_path, {"judge-codex@marketplace": {"path": path}})

    assert resolve("judge-codex", cfg) is not None
    assert resolve("judge-codex@marketplace", cfg) is not None


def test_a_plugin_that_is_not_installed_is_none_not_an_error(tmp_path: Path) -> None:
    """The caller has a coverage gap to report; it does not have an exception to
    handle, and turning one into the other would hide which it was."""
    cfg = _config(tmp_path, {})

    assert resolve("loop-security-audit", cfg) is None


def test_an_unreadable_manifest_yields_nothing_rather_than_raising(tmp_path: Path) -> None:
    """A machine with no plugins and a machine whose manifest moved are the same fact
    to a caller: it cannot reach a plugin."""
    cfg = tmp_path / "empty"
    (cfg / "plugins").mkdir(parents=True)
    (cfg / "plugins" / "installed_plugins.json").write_text("{ not json", encoding="utf-8")

    assert load(cfg) == {}


def test_a_plugin_with_no_agents_directory_lists_none(tmp_path: Path) -> None:
    path = tmp_path / "installed" / "plain"
    path.mkdir(parents=True)
    cfg = _config(tmp_path, {"plain@m": {"path": path}})

    assert resolve("plain", cfg).agents() == []


def test_the_manifest_path_follows_the_config_dir(tmp_path: Path) -> None:
    assert manifest_path(tmp_path).parts[-2:] == ("plugins", "installed_plugins.json")
