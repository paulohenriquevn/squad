"""Every hook is declared in both places, or it does not run where it matters.

WHY THIS EXISTS
---------------
Two files declare hooks, for two install layouts:

- `hooks/hooks.json` — the native plugin layout, read via `$CLAUDE_PLUGIN_ROOT`.
- `settings.json` — the standalone layout, and the source `generate_plugin_settings.py`
  turns into `settings.plugin.json`, which is what a copy install receives.

Nothing checked that the two agree. Measured 2026-08-27, while adding the
english-only hook: it was declared in `hooks/hooks.json`, installed correctly
into a consumer, and **never invoked there** — because the consumer reads
`settings.json`, where it was absent. The file was present, executable, correct,
and dead.

That is the same defect the kit spent the day fixing from the other side: a
mechanism nothing calls is worth what an absent one is worth. It is worse here,
because `ls` shows the hook sitting in the consumer's tree and the tree looks
complete.

The third file, `settings.plugin.json`, is generated and already has its own
check (`generate_plugin_settings.py --check`). This covers the pair that has
none.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]

_SCRIPT_RE = re.compile(r"([a-z_-]+\.(?:sh|py))")


def _declared(path: Path) -> dict[str, set[str]]:
    """`{event: {script names}}` from a hooks declaration file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    # hooks.json wraps everything under a "hooks" key; settings.json does too.
    events = data.get("hooks", data)
    out: dict[str, set[str]] = {}
    for event, entries in events.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            for hook in entry.get("hooks", []):
                match = _SCRIPT_RE.search(str(hook.get("command", "")))
                if match:
                    out.setdefault(event, set()).add(match.group(1))
    return out


def test_both_layouts_declare_the_same_hooks() -> None:
    """A hook in one file and not the other runs in one layout and not the other.

    Which is worse than missing entirely: the tree looks complete, the file is
    there and executable, and the failure is silence.
    """
    plugin = _declared(PROJECT_ROOT / "hooks" / "hooks.json")
    standalone = _declared(PROJECT_ROOT / "settings.json")

    assert plugin.keys() == standalone.keys(), (
        f"events differ — hooks.json has {sorted(plugin)}, "
        f"settings.json has {sorted(standalone)}"
    )
    for event in sorted(plugin):
        only_plugin = plugin[event] - standalone[event]
        only_standalone = standalone[event] - plugin[event]
        assert not only_plugin, (
            f"{event}: {sorted(only_plugin)} declared in hooks.json only — "
            "installed into every consumer and never invoked there"
        )
        assert not only_standalone, (
            f"{event}: {sorted(only_standalone)} declared in settings.json only — "
            "absent from the native plugin layout"
        )


@pytest.mark.parametrize("declaration", ["hooks/hooks.json", "settings.json"])
def test_every_declared_hook_script_exists(declaration: str) -> None:
    """A declaration pointing at a missing script fails silently at runtime.

    The harness cannot run what is not there, and nothing surfaces it: the hook
    simply never fires, which reads exactly like a hook that found nothing.
    """
    declared = _declared(PROJECT_ROOT / declaration)
    missing = [
        script
        for scripts in declared.values()
        for script in scripts
        if not (PROJECT_ROOT / "hooks" / script).is_file()
        # `mechanisms/` is searched recursively: the families are subdirectories,
        # so a flat lookup would report every mechanism as missing.
        and not any((PROJECT_ROOT / "mechanisms").rglob(script))
    ]
    assert missing == [], f"{declaration} declares scripts that do not exist: {missing}"
