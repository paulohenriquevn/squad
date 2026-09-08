"""The permission mode the kit ships, and the merge that has to carry it.

WHY THIS FILE EXISTS
--------------------
`install.sh` splits ownership of `settings.json` by key: the kit owns its wiring
(`hooks`, `statusLine`, `env`), the project owns its `permissions`. That split is
right, and it had a hole — the permissions merge iterates the kit's entries and
skips anything that is not a list:

    if not isinstance(items, list):
        continue

`allow` and `deny` are lists and merge. `defaultMode` is a STRING, so it was
skipped in silence. Changing it in the template would therefore have reached
exactly the consumers that had no `settings.json` yet, and none of the seventeen
that already did — a change that looks applied, ships, and does nothing.

That is the same defect this kit has now measured under six names: a mechanism
with no contract, a contract with no mechanism, a hook declared in one of two
files, a rule implemented on one of two branches, a gate keyed to the wrong id,
a gate keyed to the wrong directory. It is caught before shipping this time.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ("settings.json", "settings.plugin.json")


@pytest.mark.parametrize("name", TEMPLATES)
def test_the_kit_ships_no_prompting(name: str) -> None:
    """The shipped posture, pinned. Changing it changes what every consumer does."""
    data = json.loads((ROOT / name).read_text(encoding="utf-8"))
    assert data["permissions"]["defaultMode"] == "bypassPermissions", name
    assert data.get("skipDangerousModePermissionPrompt") is True, (
        f"{name}: without this the harness still shows the bypass-mode acceptance "
        f"dialog, which is itself a prompt")


@pytest.mark.parametrize("name", TEMPLATES)
def test_the_deny_list_survives_the_mode(name: str) -> None:
    """`bypassPermissions` skips PROMPTS; it does not delete a refusal.

    Keeping `deny` is the difference between "never ask me" and "there is nothing
    you will not read". The first is what was requested; the second would put
    `.env` inside the blast radius of every session in seventeen repositories.
    """
    perms = json.loads((ROOT / name).read_text(encoding="utf-8"))["permissions"]
    assert any(".env" in rule for rule in perms.get("deny", [])), (
        f"{name}: the secret-file refusal is gone")


def test_the_merge_carries_the_mode_to_an_existing_consumer(tmp_path: Path) -> None:
    """The hole: a scalar key in `permissions` was skipped in silence.

    Simulates the seventeen installs that already carry `defaultMode: "default"`.
    Without the fix the assertion below fails and the shipped change is inert.
    """
    consumer = tmp_path / "settings.json"
    consumer.write_text(json.dumps({
        "permissions": {
            "defaultMode": "default",
            "allow": ["Bash(their-tool *)"],
            "deny": ["Read(secrets/**)"],
        },
        "theirOwnKey": {"keep": "me"},
    }), encoding="utf-8")

    subprocess.run([sys.executable,
                    str(ROOT / "mechanisms" / "distribution" / "merge_settings.py"),
                    str(consumer), str(ROOT / "settings.plugin.json")], check=True)

    out = json.loads(consumer.read_text(encoding="utf-8"))
    perms = out["permissions"]
    assert perms["defaultMode"] == "bypassPermissions", "the mode did not travel"
    assert "Bash(their-tool *)" in perms["allow"], "the consumer's allow was dropped"
    assert "Read(secrets/**)" in perms["deny"], "the consumer's deny was dropped"
    assert out["theirOwnKey"] == {"keep": "me"}, "an unknown key was not preserved"


def test_the_installer_runs_the_same_merge_this_test_does() -> None:
    """Run the real merge, not a copy — and prove the installer runs that one.

    This test used to EXTRACT the heredoc out of `install.sh` and exec it, because
    the merge had no other entry point. That worked and it hid the cost: 100 lines
    of the most consequential code in the installer were reachable only by string
    surgery, so almost nothing was tested and #34 shipped inside them. The merge is
    now `merge_settings.py`, and what this pins is that the installer calls it.
    """
    installer = (ROOT / "mechanisms" / "distribution" / "install.sh").read_text(
        encoding="utf-8")

    assert "merge_settings.py" in installer
