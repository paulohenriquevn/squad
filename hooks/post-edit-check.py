#!/usr/bin/env python3
"""PostToolUse — run the language's linter on the file that was just edited.

**Scope is the whole design.** This fires after EVERY edit, so a whole-project
`tsc -p tsconfig.json` or a `cargo check` over the owning crate turns each
keystroke into a build, and the first thing anybody does with a hook like that is
switch it off. Everything here is scoped to the edited file or its package, and
the expensive forms are reachable only through `POST_EDIT_FULL_TYPECHECK=1`.

Advisory throughout: it reports and exits 0. The edit already happened, and a
linter warning is not grounds for refusing work already done.

A tool that is not installed produces nothing — deliberately. A project without
`ruff` is not a project doing something wrong, and saying so on every Python edit
would be noise about the environment rather than about the code.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from squad import PostToolUseContext, create_context  # noqa: E402

FULL = os.environ.get("POST_EDIT_FULL_TYPECHECK", "0") == "1"


def _run(*command: str) -> str:
    """The tool's output, or empty when it is absent or unusable.

    Absence returns empty rather than raising because a missing linter is a fact
    about the machine. What it must NOT do is claim the file is clean — nothing
    here prints a positive verdict, so silence never reads as approval.
    """
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=60)  # noqa: PLW1510
    except (OSError, subprocess.SubprocessError):
        return ""
    return (done.stdout + done.stderr).strip()


def _report(title: str, output: str, limit: int, footer: str | None = None) -> None:
    if not output:
        return
    print(f"{title} — first {limit} lines:")
    print("\n".join(output.splitlines()[:limit]))
    if footer:
        print()
        print(footer)
    print()


def crate_manifest(start: Path, root: Path) -> Path:
    """The Cargo.toml that owns this file, not the one at the top of the repo."""
    current = start
    while current != current.parent and root in current.parents or current == root:
        if (current / "Cargo.toml").is_file():
            return current / "Cargo.toml"
        if current == root:
            break
        current = current.parent
    return root / "Cargo.toml"


def check_go(target: Path, root: Path) -> None:
    if not (root / "go.mod").is_file():
        return
    package = str(target.parent)
    # `go vet <dir>` and never `./...`: vetting the module on every edit is the
    # cost that gets the hook disabled.
    _report(f"go vet warnings on {package}", _run("go", "vet", package), 8)
    _report(f"gofmt would reformat {target}", _run("gofmt", "-d", str(target)), 12,
            footer=f"Run 'gofmt -w {target}' to apply.")


def check_python(target: Path, root: Path) -> None:
    if not any((root / marker).is_file()
               for marker in ("pyproject.toml", "setup.py", "setup.cfg")):
        return
    _report(f"ruff warnings on {target}", _run("ruff", "check", str(target)), 8)


def check_typescript(target: Path, root: Path) -> None:
    if not (root / "tsconfig.json").is_file():
        return
    tsc, eslint = root / "node_modules/.bin/tsc", root / "node_modules/.bin/eslint"
    if FULL and os.access(tsc, os.X_OK):
        _report("tsc warnings (whole project, POST_EDIT_FULL_TYPECHECK=1)",
                _run(str(tsc), "--noEmit", "-p", "tsconfig.json"), 12)
    elif os.access(eslint, os.X_OK):
        _report(f"eslint warnings on {target}", _run(str(eslint), str(target)), 12)


def check_rust(target: Path, root: Path) -> None:
    if not (root / "Cargo.toml").is_file():
        return
    if FULL:
        manifest = crate_manifest(target.parent, root)
        _report(f"cargo check (crate {manifest}, POST_EDIT_FULL_TYPECHECK=1)",
                _run("cargo", "check", "--manifest-path", str(manifest),
                     "--message-format=short"), 12)
    else:
        _report(f"rustfmt would reformat {target}",
                _run("rustfmt", "--check", str(target)), 12)


BY_SUFFIX = {
    ".go": check_go,
    ".py": check_python,
    ".ts": check_typescript, ".tsx": check_typescript,
    ".js": check_typescript, ".jsx": check_typescript,
    ".rs": check_rust,
}


def main() -> None:
    c = create_context(PostToolUseContext)
    raw = c.tool_input.get("file_path") or c.tool_input.get("filePath")
    if not raw:
        return

    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or ".").resolve()
    if not root.is_dir():
        c.output.exit_non_block(f"post-edit-check: cannot enter project directory: {root}")
    os.chdir(root)

    target = Path(raw)
    if not target.is_absolute():
        target = root / target

    check = BY_SUFFIX.get(target.suffix.lower())
    if check:
        check(target, root)


if __name__ == "__main__":
    main()
