"""The secret-file gate in `stop-validation`, which was the least-covered thing here.

Two test files existed for this hook and NEITHER ran. `hooks/tests/
test_stop_validation.py` sat outside `testpaths`; `tests/hooks/
test_stop_validation.sh` was executed by nothing at all and already failed.

Between them the split was uneven in the worst direction: the `.py` covers the
CHANGELOG gate in fourteen tests and mentions a credential once, while the
`.sh` — the one nothing ran — held every secret case. So the single most
expensive thing the hook prevents, a credential reaching a commit, had its only
proof in the file furthest from the suite.

These are those cases, in a file the suite collects. The CHANGELOG cases stay in
the `.py`, which now runs too.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

CHANGELOG = "# Changelog\n\n## [Unreleased]\n\n### Added\n- a thing (#1)\n"


def _hook() -> Path:
    found = sorted(p for p in (REPO / "hooks").glob("stop-validation.*")
                   if p.suffix in (".sh", ".py"))
    assert len(found) == 1, f"expected one implementation, found {found}"
    return found[0]


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True,
                   capture_output=True, text=True)


def _repo(tmp_path: Path) -> Path:
    for tree in ("skills", "rules", "hooks"):
        (tmp_path / tree).mkdir(parents=True, exist_ok=True)
    _git(tmp_path, "init", "-b", "workspace", "--quiet")
    _git(tmp_path, "config", "user.email", "test@test.invalid")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "README.md").write_text("# x\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "init", "--quiet")
    return tmp_path


def _run(root: Path, env_extra: dict | None = None) -> int:
    import os
    hook = _hook()
    cmd = ["bash", str(hook)] if hook.suffix == ".sh" else [sys.executable, str(hook)]
    env = {"PATH": os.environ["PATH"], "HOME": str(root), "CLAUDE_PROJECT_DIR": str(root)}
    env.update(env_extra or {})
    return subprocess.run(cmd, input=json.dumps({"hook_event_name": "Stop", "stop_hook_active": False}),
                          capture_output=True,  # noqa: PLW1510
                          text=True, cwd=root, env=env).returncode


def _commit_file(root: Path, name: str, body: str = "x\n") -> None:
    """Commit the file WITH a CHANGELOG entry, so only the secret gate can fire."""
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    (root / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "add", "--quiet")


@pytest.mark.parametrize("name", [
    ".env",
    ".env.production",
    "credentials.json",
    "server.pem",
    "private.key",
])
def test_a_committed_secret_blocks(tmp_path: Path, name: str) -> None:
    """The CHANGELOG is written too, so a failure here is the secret gate and
    nothing else — a test that could pass for the wrong reason proves nothing."""
    root = _repo(tmp_path)
    _commit_file(root, name, "SECRET=foo\n")

    assert _run(root) == 2, f"{name} reached a commit without being refused"


@pytest.mark.parametrize("name", [
    "src/environment.py",     # contains "env", is not one
    "keyboard.py",            # contains "key"
])
def test_a_file_that_merely_resembles_a_secret_is_allowed(tmp_path: Path, name: str) -> None:
    """A gate that fires on `keyboard.py` is one somebody switches off."""
    root = _repo(tmp_path)
    _commit_file(root, name, "print('hello')\n")

    assert _run(root) == 0, name


def test_a_clean_tree_exits_zero(tmp_path: Path) -> None:
    assert _run(_repo(tmp_path)) == 0


def test_warn_only_downgrades_the_block(tmp_path: Path) -> None:
    """The escape hatch exists; this pins that it is the ONLY thing that opens
    the gate, so a future change cannot open it by accident."""
    root = _repo(tmp_path)
    _commit_file(root, ".env", "SECRET=foo\n")

    assert _run(root) == 2
    assert _run(root, {"STOP_VALIDATION_WARN_ONLY": "1"}) == 0


def test_the_credentials_pattern_is_wider_than_the_secret_one(tmp_path: Path) -> None:
    """DOCUMENTED asymmetry, not a defect — and worth seeing before changing either.

    `credentials.*` matches any extension, so `docs/credentials.md` blocks even
    though it is documentation. `*secret*` matches only `.yaml|.json|.env|.txt`,
    so `docs/secrets.md` passes. Same intent, two different widths.

    The wide one is the conservative side of a gate whose message asks the reader
    to *verify they are intentionally NOT secrets*, so a false block costs one
    confirmation and a false pass costs a leaked credential. Pinned so that
    narrowing it is deliberate.
    """
    root = _repo(tmp_path)
    _commit_file(root, "docs/credentials.md", "how we handle credentials\n")
    assert _run(root) == 2, "credentials.md blocks — the wide side"

    root2 = _repo(tmp_path / "other")
    _commit_file(root2, "docs/secrets.md", "how we handle secrets\n")
    assert _run(root2) == 0, "secrets.md passes — the narrow side"
