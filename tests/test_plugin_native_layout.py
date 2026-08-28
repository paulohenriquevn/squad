"""The kit installed as a native plugin, without copying itself into the project.

THE DEFECT THIS FIXES
---------------------
`plugin.json` advertised an installable plugin, but the only installation path
that worked was `scripts/install.sh`, which `cp -r`s the kit into
`<project>/.claude/`. Three consequences, measured 2026-08-26:

1. **Installed by the native mechanism, no gate ran.** The manifest sat at the
   root, and Claude Code reads `.claude-plugin/plugin.json`; there was no
   `hooks/hooks.json`; and `settings.plugin.json`'s hooks pointed at
   `$CLAUDE_PROJECT_DIR/.claude/hooks/…`, a path that only exists in copy mode.
   `detect-layout.sh` then exited 0 without printing anything:
   `stop-validation.sh` and `sessionstart-context.sh` exited 0, mute.
   A silently disabled gate is indistinguishable from a gate that approved.

2. **O agente do consumidor editava o kit.** Vivendo em `.claude/`, com
   `Edit`/`Write`/`Bash(*)` allowed and no hook protecting the path, the kit was
   writable territory. `scripts/check_install_drift.py` itself records
   o resultado: "Twenty-two fixes to this kit lived for weeks inside one
   consumer's gitignored `.claude/` install and nowhere else."

3. **There was no "the system", there were N divergent copies.**

THE FIX, AND WHAT IT SEPARATES
------------------------------
`detect-layout.sh` now resolves TWO paths where there used to be one:

    KIT_DIR  — the kit's CODE (skills/, rules/, hooks/). Read-only.
    ECO      — the cycle's DATA (records/, .active_plan). Writable.

In native mode the two diverge — the code sits outside the project, under
`$CLAUDE_PLUGIN_ROOT` — and it is that divergence that makes the kit
non-editable by the consumer. In copy and standalone modes they coincide, as
they always did, and nothing changes for anyone who already installed.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / ".claude-plugin" / "plugin.json"
HOOKS_JSON = REPO / "hooks" / "hooks.json"
LEGACY_SETTINGS = REPO / "settings.plugin.json"
DETECT = REPO / "hooks" / "environment" / "detect-layout.sh"


# --------------------------------------------------------------------------
# manifesto
# --------------------------------------------------------------------------
def test_manifest_sits_where_claude_code_looks_for_it():
    """Claude Code reads `.claude-plugin/plugin.json`. At the root, the file is decorative."""
    assert MANIFEST.is_file(), (
        "without .claude-plugin/plugin.json the plugin is not recognised by the "
        "native mechanism, and the only possible installation is the copy one"
    )
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data.get("name"), "manifest without `name`"
    assert data.get("version"), "manifest without `version`"


def test_manifest_is_the_single_source_of_the_plugin_identity():
    """Two divergent manifests is worse than one in the wrong place."""
    root = REPO / "plugin.json"
    if not root.is_file():
        return  # removido — nada a conciliar
    a = json.loads(root.read_text(encoding="utf-8"))
    b = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for field in ("name", "version"):
        assert a.get(field) == b.get(field), (
            f"plugin.json e .claude-plugin/plugin.json divergem em `{field}`: "
            f"{a.get(field)!r} != {b.get(field)!r}"
        )


# --------------------------------------------------------------------------
# hooks.json
# --------------------------------------------------------------------------
def _hook_commands(doc: dict) -> list[str]:
    out: list[str] = []
    for entries in doc.get("hooks", {}).values():
        for entry in entries:
            for hook in entry.get("hooks", []) or []:
                if hook.get("command"):
                    out.append(hook["command"])
    return out


def test_hooks_json_exists_and_is_valid():
    assert HOOKS_JSON.is_file(), (
        "without hooks/hooks.json the native plugin registers no hook at all — "
        "every gate is off and silent"
    )
    json.loads(HOOKS_JSON.read_text(encoding="utf-8"))


def test_every_hook_resolves_through_plugin_root():
    """No command may resolve through `$CLAUDE_PROJECT_DIR/.claude/`.

    That path belongs to copy mode. A native plugin using it points at a directory
    that does not exist, and the hook fails silently.
    """
    doc = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    commands = _hook_commands(doc)
    assert commands, "hooks.json declares no command at all"
    for cmd in commands:
        assert "CLAUDE_PLUGIN_ROOT" in cmd, f"hook does not use CLAUDE_PLUGIN_ROOT: {cmd}"
        assert ".claude/hooks" not in cmd, (
            f"hook resolves through the copy layout instead of the plugin root: {cmd}"
        )


def test_every_declared_hook_script_exists():
    """A hook path that does not resolve is a gate that never runs."""
    doc = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    missing = []
    for cmd in _hook_commands(doc):
        for rel in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+)", cmd):
            if not (REPO / rel).is_file():
                missing.append(rel)
    assert not missing, f"hooks declared with no script on disk: {sorted(set(missing))}"


def test_native_and_copy_layouts_wire_the_same_events():
    """Installing one way or the other must not change WHICH gates exist.

    If copy mode protects `Stop` and native mode does not, the same kit version
    gives two different guarantees depending on the installer — and nobody is told.
    """
    native = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))["hooks"]
    legacy = json.loads(LEGACY_SETTINGS.read_text(encoding="utf-8"))["hooks"]
    assert set(native) == set(legacy), (
        "eventos divergentes entre hooks.json (nativo) e settings.plugin.json "
        f"(copy): native only={set(native) - set(legacy)}, "
        f"copy only={set(legacy) - set(native)}"
    )


# --------------------------------------------------------------------------
# detect-layout.sh
# --------------------------------------------------------------------------
def _resolve(project_dir: Path, env: dict | None = None) -> tuple[str, str, str]:
    """Run detect-layout.sh and return (KIT_DIR, ECO, stderr)."""
    script = f'source "{DETECT}"; echo "KIT=${{KIT_DIR:-}}"; echo "ECO=${{ECO:-}}"'
    full_env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)}
    full_env.pop("CLAUDE_PLUGIN_ROOT", None)
    if env:
        full_env.update(env)
    proc = subprocess.run(  # noqa: PLW1510
        ["bash", "-c", script], capture_output=True, text=True, env=full_env
    )
    kit = eco = ""
    for line in proc.stdout.splitlines():
        if line.startswith("KIT="):
            kit = line[4:]
        elif line.startswith("ECO="):
            eco = line[4:]
    return kit, eco, proc.stderr


def _fake_kit(root: Path) -> Path:
    for d in ("skills", "rules", "hooks"):
        (root / d).mkdir(parents=True, exist_ok=True)
    return root


def test_plugin_root_supplies_the_kit_and_the_project_supplies_the_data(tmp_path):
    """The case that did not exist: code outside the project, data inside."""
    kit = _fake_kit(tmp_path / "plugin-root")
    project = tmp_path / "consumer"
    (project / ".claude").mkdir(parents=True)

    kit_dir, eco, _ = _resolve(project, {"CLAUDE_PLUGIN_ROOT": str(kit)})
    assert kit_dir == str(kit), "KIT_DIR must come from CLAUDE_PLUGIN_ROOT"
    assert eco not in ("", str(kit)), "the cycle's DATA must not land inside the kit"


def test_a_corrupt_plugin_root_is_loud(tmp_path):
    """`CLAUDE_PLUGIN_ROOT` pointing at a tree without the kit must WARN.

    This is exactly where the silence hurt: with no recognisable structure, the
    script exited 0 without a line, and every gate was disabled while looking
    approved.
    """
    empty = tmp_path / "not-a-kit"
    empty.mkdir()
    project = tmp_path / "consumer"
    project.mkdir()

    _, _, stderr = _resolve(project, {"CLAUDE_PLUGIN_ROOT": str(empty)})
    assert stderr.strip(), (
        "a corrupt plugin install emitted no warning — the gates stay disabled and "
        "indistinguishable from approved"
    )


def test_copy_layout_still_resolves(tmp_path):
    """Regression: anyone who already installed by copy must not break."""
    project = tmp_path / "consumer"
    _fake_kit(project / ".claude")
    kit_dir, eco, _ = _resolve(project)
    assert kit_dir.endswith(".claude") and eco.endswith(".claude")


def test_standalone_layout_still_resolves(tmp_path):
    """Regression: the kit's own repository opened in Claude Code."""
    project = _fake_kit(tmp_path / "kit-repo")
    kit_dir, eco, _ = _resolve(project)
    assert kit_dir in (".", str(project))
    assert eco in (".", str(project))


def test_absent_kit_stays_quiet(tmp_path):
    """A project that simply does not use the kit should be told nothing.

    A contrapartida de `test_a_corrupt_plugin_root_is_loud`: o aviso vale
    when the kit should be there and is not, not when nobody installed it.
    """
    project = tmp_path / "plain-project"
    project.mkdir()
    kit_dir, eco, stderr = _resolve(project)
    assert kit_dir == "" and eco == ""
    assert stderr.strip() == "", f"noise in a project without the kit: {stderr!r}"
