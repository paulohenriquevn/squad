"""A `Write(path)` permission rule looks like a guard and enforces nothing.

Claude Code matches file permission rules on `Edit(path)` only — an `Edit` rule covers
every file-editing tool, `Write` included. A `Write(path)` rule is accepted by the
schema, reads like protection, and is never consulted. The harness now says so at
startup, once per rule.

Measured 2026-09-07 in `settings.json`: 49 deny rules spelled `Write(...)`, covering
`.env` and its nine environment variants, private keys, keystores, `kubeconfig`,
`credentials.json`, `secrets.y*ml` and `study-material/**`. Every one of them was
**already** paired with an exact `Edit(...)` twin, so nothing was unprotected — the
Write rules were dead weight producing 49 startup warnings. That is why they were
deleted rather than rewritten: converting `Write(X)` to `Edit(X)` would have produced
49 duplicates of rules already in the file.

The twinning is what makes deletion safe, so this file asserts it rather than assuming
it: if a future `Write(...)` rule is added WITHOUT an `Edit(...)` twin, deleting it
would open a real hole, and the first test below is what makes that visible instead of
letting a blanket sweep remove protection.

`settings.plugin.json` is generated from `settings.json`
(`mechanisms/distribution/generate_plugin_settings.py`), so it is checked too — a
regeneration is what carries the fix into a plugin install.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_FILES = ("settings.json", "settings.plugin.json")
_ARRAYS = ("allow", "deny", "ask")


def _permissions(name: str) -> dict:
    return json.loads((_ROOT / name).read_text(encoding="utf-8")).get("permissions", {})


def _paths(rules: list[str], tool: str) -> set[str]:
    out = set()
    for rule in rules:
        m = re.fullmatch(rf"{tool}\((.*)\)", rule)
        if m:
            out.add(m.group(1))
    return out


@pytest.mark.parametrize("name", _FILES)
def test_the_file_has_permissions_to_check(name: str) -> None:
    """Vacuity is a failure: an empty permissions block passes every assertion below."""
    perms = _permissions(name)
    assert sum(len(perms.get(k, [])) for k in _ARRAYS) > 50


@pytest.mark.parametrize("name", _FILES)
def test_no_permission_rule_is_spelled_write(name: str) -> None:
    perms = _permissions(name)
    offenders = [
        f"{k}: {rule}"
        for k in _ARRAYS
        for rule in perms.get(k, [])
        if rule.startswith("Write(")
    ]
    assert offenders == [], (
        f"{name} carries {len(offenders)} rule(s) spelled Write(path). File permission "
        f"checks match Edit(path) only, so each is inert and each costs a startup "
        f"warning: {offenders}"
    )


@pytest.mark.parametrize("name", _FILES)
def test_every_denied_path_is_covered_by_an_edit_rule(name: str) -> None:
    """The protection the deleted Write rules appeared to give must actually be there.

    Asserting the absence of Write rules alone would be satisfied by a file with no
    file-permission rules at all. This pins the other half: the paths that matter are
    denied through the spelling the harness honours.
    """
    denied = _permissions(name).get("deny", [])
    edits = _paths(denied, "Edit")
    for required in (".env", "**/.env", "**/*.pem", "**/id_rsa", "**/credentials.json",
                     "**/kubeconfig", "**/secrets.yaml", "study-material/**"):
        assert required in edits, f"{name} does not deny Edit({required})"
