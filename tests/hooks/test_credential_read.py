"""The deny list refused one tool, and not the one that can change the file.

`permissions.deny` carried `Read(**/.env)` and friends. `permissions.allow`
carried `Bash(*)`. So `cat .env` returned the file that `Read(.env)` had just
refused, and `Edit` was never denied on those paths at all — an agent could not
read a credential file and could rewrite it blind.

Measured in a consumer on 2026-09-02: 157 versioned paths refused to `Read`, 79
of them source code (51 `.go`, 24 `.sh`), and not one refusal a session could not
step around in a single command. It cost real work and bought nothing. Filed by
an agent running inside the fleet as kit#15.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]


def _hook():
    spec = importlib.util.spec_from_file_location(
        "validate_command_under_test", _REPO / "hooks" / "validate-command.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("command", [
    "cat .env",
    "head -5 config/app.key",
    "base64 ~/.ssh/id_rsa",
    "less deploy/tls.pem",
    "cat charts/service-api/templates/secret.yaml",
    "cp .env /tmp/x",
    "grep TOKEN .env.production",
], ids=lambda c: c.split()[0] + "-" + c.split()[-1])
def test_a_shell_command_cannot_return_what_read_is_denied(command: str) -> None:
    """The same bytes, through the door the deny rule left open."""
    reason = _hook().check_credential_read(command, _REPO)

    assert reason, f"{command!r} was allowed"
    assert "settings.json" in reason, "and the refusal says where the rule lives"


@pytest.mark.parametrize("command", [
    "cat README.md",
    "grep -rn TOKEN api/internal/routes/secrets/secrets.go",
    "ls -la",
    "head -20 api/cmd/setup_secret_fetch.go",
    "cat .env.example",
    "cat .env.sample",
    "git log --oneline -5",
], ids=lambda c: c.split()[0] + "-" + c.split()[-1].replace("/", "_"))
def test_source_code_that_merely_mentions_a_secret_is_not_refused(command: str) -> None:
    """The old glob was `**/*secret*`, which matches code. 79 source files in one
    consumer were unreadable, none of them holding a credential — while the
    credentials themselves sat gitignored and unmatched. A guard that costs this
    much and stops nothing is worse than none: it teaches people to route around
    guards."""
    assert _hook().check_credential_read(command, _REPO) is None, command


def test_the_hook_reads_the_globs_from_settings_rather_than_keeping_its_own() -> None:
    """Two lists of the same shapes, in JSON and in Python, is how this gap
    reopens. On the day this was written the kit found four separate cases of a
    rule living in one file and missing from another."""
    globs = _hook()._credential_globs(_REPO)
    declared = {r[5:-1] for r in
                json.loads((_REPO / "settings.json").read_text(encoding="utf-8"))
                ["permissions"]["deny"] if r.startswith("Read(")}

    assert set(globs) == declared and globs, "the hook must not keep a second copy"


def test_every_denied_read_path_is_also_denied_to_edit_and_write() -> None:
    """The original asymmetry: unreadable and freely rewritable. Whatever a
    consumer may not see, it may not blindly overwrite either."""
    for name in ("settings.json", "settings.plugin.json"):
        deny = json.loads((_REPO / name).read_text(encoding="utf-8"))["permissions"]["deny"]
        readable = {r[5:-1] for r in deny if r.startswith("Read(")}
        for tool in ("Edit", "Write"):
            covered = {r[len(tool) + 1:-1] for r in deny if r.startswith(f"{tool}(")}
            assert readable <= covered, (
                f"{name}: {sorted(readable - covered)} refused to Read and not to {tool}")


def test_the_guard_does_not_claim_to_be_a_sandbox() -> None:
    """It closes the common door and says so. A guard that reads as protection
    and is not is the exact defect it replaces, and this kit has shipped that
    shape often enough to write it down."""
    source = (_REPO / "hooks" / "validate-command.py").read_text(encoding="utf-8")

    # Comment prefixes stripped before joining: the sentences wrap across lines
    # and `#:` would land in the middle of them.
    prose = " ".join(
        line.lstrip("#: ").lower()
        for line in source.splitlines()).replace("  ", " ")
    prose = " ".join(prose.split())

    assert "not exhaustive and cannot be" in prose, \
        "the limit of the pattern must be stated where the pattern is"
    assert "does not make the deny list a sandbox" in prose, \
        "and the guard must not read as more than it is"
    assert "python3 -c" in source, "the named example of what still gets through"
