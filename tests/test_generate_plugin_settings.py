"""`generate_plugin_settings.py --check` is a CI gate and had no test.

It exists to eliminate the duplication between settings.json and
settings.plugin.json. If the prefix rewrite stops happening, the plugin file points at
paths that do not exist in the installation — and `--check` keeps saying OK.

PORTED FROM THE SIBLING KIT, 2026-08-29
---------------------------------------
Both kits ship `mechanisms/distribution/generate_plugin_settings.py`; only one guarded it. Editing
`settings.json` and `settings.plugin.json` by hand desynchronised them here, the
sibling's suite failed within seconds, and this one stayed green over the same
drift — a generator with no drift check is a generator nobody runs.
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "mechanisms" / "distribution" / "generate_plugin_settings.py"

_spec = importlib.util.spec_from_file_location("generate_plugin_settings", SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def test_it_rewrites_the_hooks_prefix():
    assert (
        _mod.rewrite_value("$CLAUDE_PROJECT_DIR/hooks/validate-command.py")
        == "$CLAUDE_PROJECT_DIR/.claude/hooks/validate-command.py"
    )


def test_it_rewrites_every_directory_the_installer_copies():
    """The rewrite table must cover what actually lands in `.claude/`.

    It did not: `REWRITE_DIRS` named `scripts/`, renamed to `mechanisms/` on
    2026-09-01, and never gained `mechanisms/`. The one path affected was the
    status line, so a plugin install carried a `statusLine` command pointing at
    `$CLAUDE_PROJECT_DIR/mechanisms/...`, which does not exist there.
    """
    for directory in _installed_directories():
        value = f"$CLAUDE_PROJECT_DIR/{directory}/x"

        assert _mod.rewrite_value(value) == f"$CLAUDE_PROJECT_DIR/.claude/{directory}/x", (
            f"`{directory}/` is copied into .claude/ and is not rewritten"
        )


def test_it_rewrites_the_records_prefix():
    assert _mod.rewrite_value("$CLAUDE_PROJECT_DIR/records/y.md").startswith(
        "$CLAUDE_PROJECT_DIR/.claude/records/"
    )


def test_it_does_not_rewrite_a_path_outside_the_kit():
    """A project's own directory keeps its path. `src/` is nobody's kit tree."""
    value = "$CLAUDE_PROJECT_DIR/src/thing.txt"

    assert _mod.rewrite_value(value) == value


def test_transform_descends_into_lists_and_dicts():
    src = {"hooks": [{"command": "$CLAUDE_PROJECT_DIR/hooks/a.sh", "n": 1}]}

    out = _mod.transform(src)

    assert out["hooks"][0]["command"] == "$CLAUDE_PROJECT_DIR/.claude/hooks/a.sh"
    assert out["hooks"][0]["n"] == 1


def test_transform_preserves_non_string_types():
    assert _mod.transform({"a": [1, True, None]}) == {"a": [1, True, None]}


def test_check_reports_in_sync_for_this_repository():
    result = subprocess.run(  # noqa: PLW1510 — returncode is read below
        [sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True, cwd=REPO_ROOT
    )

    assert result.returncode == 0, result.stderr


def _installed_directories() -> list[str]:
    """The kit trees `install.sh` copies into `.claude/`, read from the installer.

    Derived rather than restated. A second hand-maintained list is what this test
    exists to catch — pinning it here would only move the drift one file over.
    """
    installer = (REPO_ROOT / "mechanisms" / "distribution" / "install.sh").read_text(
        encoding="utf-8"
    )
    match = re.search(r"^for item in ([a-z ]+); do$", installer, re.MULTILINE)
    assert match, "install.sh no longer declares the copied trees in a `for item in` loop"
    directories = match.group(1).split()
    assert directories, "the installer's tree list parsed to nothing"
    return directories


def test_the_generated_file_carries_no_standalone_kit_prefix():
    """The property, checked against the installer rather than the rewrite table.

    The previous version of this test looped over `_mod.REWRITE_DIRS`, so it could
    only ever confirm that the generator is self-consistent with its own table. It
    passed for the whole life of the `scripts/` → `mechanisms/` defect, exactly as
    `--check` did. The subject has to be the set of directories that really end up
    in `.claude/`.
    """
    blob = (REPO_ROOT / "settings.plugin.json").read_text(encoding="utf-8")

    for directory in [*_installed_directories(), "records"]:
        assert f"$CLAUDE_PROJECT_DIR/{directory}/" not in blob, (
            f"`{directory}/` kept its standalone prefix — that path does not exist "
            f"in a plugin install"
        )
