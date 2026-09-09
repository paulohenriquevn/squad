"""`post-edit-check` fires linters after an edit — scoped to the file, not the project.

Ported from `tests/hooks/test_post_edit_check.sh`, which nothing executed. Its
descriptions were also in Portuguese, in a repository that is English-only by
rule — the gate never saw them, because a file nobody runs is a file nobody reads.

WHAT IS ACTUALLY AT STAKE
-------------------------
This runs after EVERY edit. A whole-project `tsc -p tsconfig.json` or a
`cargo check` on the owning crate turns each keystroke into a full build, and
the first thing a person does with a hook like that is switch it off. So the
scoping is the feature, and these tests watch the argv the hook produces rather
than its exit code: a hook that silently widened its scope would still exit 0.

`POST_EDIT_FULL_TYPECHECK=1` restores the expensive form on purpose, and both
halves are pinned — a flag that stopped working would leave no way back.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _hook() -> Path:
    found = sorted(p for p in (REPO / "hooks").glob("post-edit-check.*")
                   if p.suffix in (".sh", ".py"))
    assert len(found) == 1, f"expected one implementation, found {found}"
    return found[0]


class Harness:
    """A project with stubbed tools on PATH, each logging the argv it received."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.bin = root / "_bin"
        self.bin.mkdir(parents=True, exist_ok=True)
        self.log = root / "_argv.log"
        self.log.write_text("", encoding="utf-8")
        for tree in ("skills", "rules", "hooks"):
            (root / tree).mkdir(parents=True, exist_ok=True)

    def stub(self, *names: str, at: Path | None = None) -> None:
        """`at` puts the stub in a project-local bin — which is where the hook
        looks for `tsc` and `eslint`, since a node project ships them there."""
        target_dir = at or self.bin
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in names:
            script = target_dir / name
            script.write_text(f'#!/bin/bash\necho "{name} $*" >> "{self.log}"\nexit 0\n',
                              encoding="utf-8")
            script.chmod(0o755)

    def write(self, rel: str, body: str) -> None:
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")

    def run(self, rel: str, **env_extra: str) -> str:
        hook = _hook()
        cmd = ["bash", str(hook)] if hook.suffix == ".sh" else [sys.executable, str(hook)]
        env = {"PATH": f"{self.bin}:{os.environ['PATH']}", "HOME": str(self.root),
               "CLAUDE_PROJECT_DIR": str(self.root), **env_extra}
        payload = ('{"hook_event_name":"PostToolUse","tool_name":"Edit",'
                   f'"tool_input":{{"file_path":"{rel}"}}}}')
        subprocess.run(cmd, input=payload, capture_output=True, text=True,  # noqa: PLW1510
                       cwd=self.root, env=env)
        return self.log.read_text(encoding="utf-8")


@pytest.fixture()
def harness(tmp_path: Path) -> Harness:
    return Harness(tmp_path)


def test_go_vet_gets_the_package_and_does_not_recurse(harness: Harness) -> None:
    """`./...` would vet the whole module on every edit."""
    harness.stub("go", "gofmt")
    harness.write("internal/auth/a.go", "package auth\n")
    harness.write("go.mod", "module x\n")

    argv = harness.run("internal/auth/a.go")

    assert f"vet {harness.root}/internal/auth" in argv
    assert "/..." not in argv, "the whole module must not be vetted after one edit"


def test_typescript_is_linted_per_file_and_not_typechecked_per_project(
        harness: Harness) -> None:
    harness.stub("tsc", "eslint", at=harness.root / "node_modules" / ".bin")
    harness.write("src/a.ts", "export const a = 1\n")
    harness.write("tsconfig.json", "{}\n")

    argv = harness.run("src/a.ts")

    assert "-p tsconfig.json" not in argv, "a project typecheck on every keystroke"
    assert f"eslint {harness.root}/src/a.ts" in argv


def test_the_flag_restores_the_project_typecheck(harness: Harness) -> None:
    """The expensive form stays reachable — a scoping fix that removed it would
    leave no way to ask the original question."""
    harness.stub("tsc", at=harness.root / "node_modules" / ".bin")
    harness.write("src/a.ts", "export const a = 1\n")
    harness.write("tsconfig.json", "{}\n")

    argv = harness.run("src/a.ts", POST_EDIT_FULL_TYPECHECK="1")

    assert "-p tsconfig.json" in argv


def test_rust_is_formatted_per_file_and_not_checked_per_crate(harness: Harness) -> None:
    harness.stub("cargo", "rustfmt")
    harness.write("src/main.rs", "fn main() {}\n")
    harness.write("Cargo.toml", "[package]\nname = \"x\"\n")

    argv = harness.run("src/main.rs")

    assert "cargo check" not in argv, "a crate check on every edit"
    assert f"rustfmt --check {harness.root}/src/main.rs" in argv


def test_the_flag_restores_the_crate_check(harness: Harness) -> None:
    harness.stub("cargo", "rustfmt")
    harness.write("src/main.rs", "fn main() {}\n")
    harness.write("Cargo.toml", "[package]\nname = \"x\"\n")

    argv = harness.run("src/main.rs", POST_EDIT_FULL_TYPECHECK="1")

    assert f"--manifest-path {harness.root}/Cargo.toml" in argv


def test_python_stays_scoped_to_the_edited_file(harness: Harness) -> None:
    harness.stub("ruff")
    harness.write("pyproject.toml", '[project]\nname = "x"\n')
    harness.write("src/a.py", "x = 1\n")

    argv = harness.run("src/a.py")

    assert f"ruff check {harness.root}/src/a.py" in argv, "the file, not the tree"
