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

    # `source` is relative to the REPOSITORY, not to the directory marketplace.json sits
    # in. Resolving it from `.claude-plugin/` produced
    # `.claude-plugin/.claude-plugin/plugin.json`, which does not exist — so the test
    # computed a path, noticed it was wrong, and hard-coded the answer instead, leaving
    # the declared `source` unchecked (kit#62).
    plugin_path = (_REPO / squad["source"] / ".claude-plugin" / "plugin.json").resolve()
    assert plugin_path.is_file(), (
        f"marketplace.json declares source {squad['source']!r}, which resolves to "
        f"{plugin_path} — and no plugin.json is there"
    )
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


def test_the_copy_install_does_not_depend_on_the_marketplace() -> None:
    """The marketplace is an additional door, not a replacement for the existing one.

    42 consumers install by copy. If `install.sh` came to reference the manifest,
    the copy path would inherit the marketplace's failure modes and the addition
    would stop being additive.

    An earlier version of this test asserted `git diff --name-only HEAD` did not
    list `install.sh` — which measured whether the working tree was clean, not
    whether the two paths were independent. It failed the first time anyone edited
    the installer for an unrelated reason (adding a fifth squad agent), which is
    the tell: a test that forbids all future change to a file is pinning the file,
    not the property.
    """
    installer = (_REPO / "mechanisms" / "distribution" / "install.sh").read_text()
    assert "marketplace.json" not in installer, (
        "install.sh references the marketplace manifest; the copy install must "
        "stand alone or the addition is not additive"
    )
    assert ".claude-plugin/marketplace" not in installer

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
