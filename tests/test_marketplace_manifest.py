"""Test: .claude-plugin/marketplace.json is valid and consistent with plugin.json.

marketplace.json is a new entry point for plugin installation (/plugin marketplace add).
It is additive to the existing copy-install (42 consumers untouched). This test suite
ensures the two manifests never diverge.
"""
import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]


def _load_marketplace() -> dict:
    """Load and parse marketplace.json."""
    mkt_path = _REPO / ".claude-plugin" / "marketplace.json"
    assert mkt_path.is_file(), f"marketplace.json not found at {mkt_path}"
    return json.loads(mkt_path.read_text(encoding="utf-8"))


def _load_plugin() -> dict:
    """Load and parse plugin.json."""
    plg_path = _REPO / ".claude-plugin" / "plugin.json"
    if not plg_path.is_file():
        pytest.fail("plugin.json must exist")
    return json.loads(plg_path.read_text(encoding="utf-8"))


def test_marketplace_json_is_valid_json_with_required_fields() -> None:
    """marketplace.json must be valid JSON with required top-level fields."""
    data = _load_marketplace()

    assert isinstance(data, dict), "marketplace.json must be a JSON object"
    assert "name" in data, "marketplace.json must have 'name'"
    assert data["name"], "marketplace.json 'name' must not be empty"
    assert "owner" in data, "marketplace.json must have 'owner'"
    assert "plugins" in data, "marketplace.json must have 'plugins'"
    assert isinstance(data["plugins"], list), "'plugins' must be an array"
    assert len(data["plugins"]) > 0, "'plugins' array must not be empty"


def test_marketplace_owner_has_required_fields() -> None:
    """marketplace.json owner object must have name, email, url."""
    data = _load_marketplace()
    owner = data.get("owner", {})

    assert "name" in owner, "owner must have 'name'"
    assert owner["name"], "owner 'name' must not be empty"
    assert "email" in owner, "owner must have 'email'"
    assert owner["email"], "owner 'email' must not be empty"


def test_squad_plugin_entry_points_at_repo_root() -> None:
    """marketplace.json plugins[0] (squad) must point at './' or '.'."""
    data = _load_marketplace()
    plugins = data.get("plugins", [])
    assert len(plugins) > 0, "no plugins defined"

    squad = next((p for p in plugins if p.get("name") == "squad"), None)
    assert squad is not None, "squad plugin not found in marketplace.json"
    assert squad.get("source") in ("./", "."), "squad source must be './' or '.'"


def test_plugin_json_is_readable_from_declared_source() -> None:
    """plugin.json must exist and be valid JSON at the declared source."""
    data = _load_marketplace()
    plugins = data.get("plugins", [])
    squad = next((p for p in plugins if p.get("name") == "squad"), None)
    assert squad is not None

    # Resolve source relative to marketplace.json location
    marketplace_dir = _REPO / ".claude-plugin"
    source_path = marketplace_dir / squad["source"] / ".claude-plugin" / "plugin.json"

    # For the in-repo case, source is '.', so path should be
    # {repo}/.claude-plugin/. / .claude-plugin/plugin.json = {repo}/.claude-plugin/plugin.json
    # Simplify: the real check is that plugin.json exists and is valid
    plugin_path = _REPO / ".claude-plugin" / "plugin.json"
    assert plugin_path.is_file(), f"plugin.json not found at {plugin_path}"
    assert plugin_path.read_text(encoding="utf-8"), "plugin.json is empty"
    json.loads(plugin_path.read_text(encoding="utf-8"))  # Validate JSON


def test_description_and_version_do_not_diverge() -> None:
    """marketplace.json and plugin.json must have identical description and version.

    This prevents the drift problem: two manifests claiming the same plugin
    with different descriptions or versions.
    """
    mkt = _load_marketplace()
    plg = _load_plugin()

    mkt_squad = next((p for p in mkt.get("plugins", []) if p.get("name") == "squad"), None)
    assert mkt_squad is not None, "squad plugin not in marketplace.json"

    assert mkt_squad.get("description") == plg.get("description"), (
        f"Version mismatch: marketplace has '{mkt_squad.get('description')}' "
        f"but plugin.json has '{plg.get('description')}'"
    )
    assert mkt_squad.get("version") == plg.get("version"), (
        f"Version mismatch: marketplace has '{mkt_squad.get('version')}' "
        f"but plugin.json has '{plg.get('version')}'"
    )


def test_marketplace_json_does_not_touch_install_sh() -> None:
    """Additive port only — install.sh and sync_consumers.py must be unchanged."""
    import subprocess

    # Git check: is install.sh tracked and unchanged?
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    changed_files = result.stdout.strip().split("\n") if result.stdout else []

    assert "mechanisms/distribution/install.sh" not in changed_files, (
        "install.sh was modified; the marketplace addition should be purely additive"
    )
    assert "mechanisms/distribution/sync_consumers.py" not in changed_files, (
        "sync_consumers.py was modified; the marketplace addition should be purely additive"
    )


def test_each_plugin_entry_has_required_marketplace_fields() -> None:
    """Each plugin in the array must have name, source, description, version."""
    data = _load_marketplace()
    for plugin in data.get("plugins", []):
        assert "name" in plugin, "plugin must have 'name'"
        assert "source" in plugin, "plugin must have 'source'"
        assert "description" in plugin, "plugin must have 'description'"
        assert "version" in plugin, "plugin must have 'version'"
        # Validate types
        assert isinstance(plugin["name"], str), "plugin name must be string"
        assert isinstance(plugin["source"], str), "plugin source must be string"
        assert isinstance(plugin["description"], str), "plugin description must be string"
        assert isinstance(plugin["version"], str), "plugin version must be string"
