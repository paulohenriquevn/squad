#!/usr/bin/env python3
"""Generate settings.plugin.json from settings.json.

Eliminates the DRY violation between the two files. The only difference
is the path prefix: settings.json uses ``$CLAUDE_PROJECT_DIR/`` (standalone)
while settings.plugin.json uses ``$CLAUDE_PROJECT_DIR/.claude/`` (plugin install).

Usage:
    python3 mechanisms/distribution/generate_plugin_settings.py          # writes settings.plugin.json
    python3 mechanisms/distribution/generate_plugin_settings.py --check   # exit 1 if out of sync
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

STANDALONE_PREFIX = "$CLAUDE_PROJECT_DIR/"
PLUGIN_PREFIX = "$CLAUDE_PROJECT_DIR/.claude/"

#: Paths that get the prefix rewrite (relative to $CLAUDE_PROJECT_DIR).
#:
#: EVERY tree the installer copies, plus `records/`. Not a curated subset: this
#: list named `scripts/` — renamed to `mechanisms/` on 2026-09-01 — and never
#: gained `mechanisms/`, so the status line shipped to plugin installs pointing at
#: `$CLAUDE_PROJECT_DIR/mechanisms/fleet/statusline.sh`, a path that exists only in
#: the standalone layout. `--check` could not see it: it compares the generated
#: output against the committed file, and both come from this table.
#:
#: `tests/test_generate_plugin_settings.py` reads the tree list out of
#: `install.sh` and confronts it with this one, so the next tree added to the
#: installer fails here instead of shipping a broken path.
REWRITE_DIRS = (
    "skills/", "rules/", "hooks/", "commands/", "mechanisms/", "squad/",
    "records/",
)


def rewrite_value(value: str) -> str:
    """Rewrite a standalone path to a plugin-install path."""
    for d in REWRITE_DIRS:
        standalone = f"{STANDALONE_PREFIX}{d}"
        plugin = f"{PLUGIN_PREFIX}{d}"
        value = value.replace(standalone, plugin)
    return value


def transform(obj: object) -> object:
    """Recursively rewrite all string values in a JSON structure."""
    if isinstance(obj, str):
        return rewrite_value(obj)
    if isinstance(obj, list):
        return [transform(item) for item in obj]
    if isinstance(obj, dict):
        return {k: transform(v) for k, v in obj.items()}
    return obj


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    source = repo_root / "settings.json"
    target = repo_root / "settings.plugin.json"

    with open(source, encoding="utf-8") as f:
        data = json.load(f)

    # Add the explanatory comment
    data["_comment_"] = (
        "Template for PLUGIN INSTALL layout (consumer project's .claude/ contains "
        "the Squad kit). Used by mechanisms/distribution/install.sh. For standalone "
        "use (the Squad repo itself), see settings.json."
    )

    transformed = transform(data)
    generated = json.dumps(transformed, indent=2, ensure_ascii=False) + "\n"

    if "--check" in sys.argv:
        if not target.exists():
            print(f"MISSING: {target} does not exist", file=sys.stderr)
            return 1
        current = target.read_text(encoding="utf-8")
        if current != generated:
            print(
                f"OUT OF SYNC: {target} differs from generated version. "
                f"Run: python3 mechanisms/distribution/generate_plugin_settings.py",
                file=sys.stderr,
            )
            return 1
        print("OK: settings.plugin.json is in sync")
        return 0

    target.write_text(generated, encoding="utf-8")
    print(f"Generated {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
