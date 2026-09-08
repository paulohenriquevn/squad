"""Merging a consumer's `settings.json` with the kit's: who owns which entry.

WHY THIS FILE EXISTS
--------------------
The merge lived as a 100-line heredoc inside `install.sh`, so nothing could run
it and nothing did. It is the most consequential code in the installer — it
rewrites a file in seventeen repositories — and the defect it shipped is exactly
the kind a test catches in a second (#34):

    for key in ("hooks", "statusLine", "env", …):
        if key in kit:
            mine[key] = kit[key]

`hooks` is not the kit's alone. A consumer that wires its own hook writes it into
the same key, and that wholesale replacement deleted it with no diff, no warning
and a success message. Measured in one consumer: its only mandatory pre-push
checkpoint sat on disk, unwired, for four days, while two tests asserting the
hook's existence stayed green — they read the file, and the file was never the
thing that went missing.

The kit's own comment stated the premise correctly and drew the wrong conclusion
from it: a stale KIT hook is indeed a gate that stopped running, which is why kit
entries are replaced. It does not follow that every entry is the kit's.

WHAT THE MERGE OWES, IN BOTH DIRECTIONS
---------------------------------------
Replacing everything loses the consumer's hooks. Keeping everything leaves the
kit's retired hooks wired forever. Neither is acceptable, and the shape that
answers both already existed one key over: `permissions` records what the kit
shipped last time (`.kit-permissions.json`) so that "the kit retired it" and "the
project added it" stop being the same observation. These tests hold `hooks` to
that same standard.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mechanisms.distribution import merge_settings as ms


def _hook(command: str, *, timeout: int = 10) -> dict:
    return {"type": "command", "command": command, "timeout": timeout}


def _kit_settings() -> dict:
    return {
        "$schema": "https://json.schemastore.org/claude-code-settings.json",
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [_hook("python3 kit/validate-command.py")]},
            ],
            "Stop": [{"hooks": [_hook("python3 kit/stop-validation.py")]}],
        },
        "permissions": {"deny": ["Read(**/.env)"], "allow": ["Bash(git status)"]},
    }


def _consumer_settings() -> dict:
    return {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [_hook("python3 kit/validate-command.py")]},
                {"matcher": "Bash", "hooks": [_hook('bash "$CLAUDE_PROJECT_DIR/.claude/hooks/my-gate.sh"',
                                                    timeout=600)]},
            ],
        },
        "permissions": {"allow": ["Bash(pnpm test:*)"]},
    }


def _commands(merged: dict, event: str) -> list[str]:
    return [h["command"]
            for group in merged.get("hooks", {}).get(event, [])
            for h in group.get("hooks", [])]


# ── the defect ────────────────────────────────────────────────────────────────

def test_a_consumers_own_hook_survives_the_merge(tmp_path: Path) -> None:
    """The repro from #34, as an assertion.

    Step 3 of that report is `grep -c my-gate.sh .claude/settings.json` → 0.
    """
    merged = ms.merge(_consumer_settings(), _kit_settings(), previous={})

    assert any("my-gate.sh" in c for c in _commands(merged, "PreToolUse"))


def test_the_kits_hook_is_refreshed_from_the_kit() -> None:
    """A stale kit hook is a gate that quietly stopped running — the original premise.

    The kit's entry is taken verbatim from the kit, so a consumer who edited its
    timeout, matcher or arguments gets the kit's version back.
    """
    consumer = _consumer_settings()
    consumer["hooks"]["PreToolUse"][0]["hooks"][0]["timeout"] = 99999

    merged = ms.merge(consumer, _kit_settings(), previous={})

    entries = [h for group in merged["hooks"]["PreToolUse"] for h in group["hooks"]
               if h["command"] == "python3 kit/validate-command.py"]
    assert len(entries) == 1, "the kit's hook was duplicated or lost"
    assert entries[0]["timeout"] == 10


def test_a_renamed_kit_hook_is_removed_only_when_the_baseline_names_it() -> None:
    """Renaming is retiring one command and shipping another, and the baseline is
    the only thing that can tell that from a consumer's own hook."""
    consumer = _consumer_settings()
    consumer["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = "python3 kit/OLD-NAME.py"
    baseline = {"PreToolUse": ["python3 kit/OLD-NAME.py"]}

    merged = ms.merge(consumer, _kit_settings(), hook_previous=baseline)

    commands = _commands(merged, "PreToolUse")
    assert "python3 kit/validate-command.py" in commands
    assert "python3 kit/OLD-NAME.py" not in commands
    assert any("my-gate.sh" in c for c in commands), "the consumer's hook went with it"


def test_a_kit_event_the_consumer_never_had_is_added(tmp_path: Path) -> None:
    merged = ms.merge(_consumer_settings(), _kit_settings(), previous={})

    assert _commands(merged, "Stop") == ["python3 kit/stop-validation.py"]


def test_a_consumer_event_the_kit_does_not_ship_is_untouched() -> None:
    consumer = _consumer_settings()
    consumer["hooks"]["SessionEnd"] = [{"hooks": [_hook("bash ours/farewell.sh")]}]

    merged = ms.merge(consumer, _kit_settings(), previous={})

    assert _commands(merged, "SessionEnd") == ["bash ours/farewell.sh"]


# ── retirement, which a plain union cannot express ────────────────────────────

def test_a_hook_the_kit_retired_is_removed_when_the_baseline_says_it_was_the_kits() -> None:
    """Without this, a union leaves every hook the kit ever shipped wired forever."""
    consumer = _consumer_settings()
    consumer["hooks"]["Stop"] = [{"hooks": [_hook("python3 kit/retired-gate.py")]}]
    baseline = {"Stop": ["python3 kit/retired-gate.py"]}

    merged = ms.merge(consumer, _kit_settings(), hook_previous=baseline)

    assert "python3 kit/retired-gate.py" not in _commands(merged, "Stop")
    assert "python3 kit/stop-validation.py" in _commands(merged, "Stop")


def test_with_no_baseline_nothing_is_removed() -> None:
    """First install under this scheme: every entry is indistinguishable from the
    project's own, and deleting a project's hook is the worse error by far."""
    consumer = _consumer_settings()
    consumer["hooks"]["Stop"] = [{"hooks": [_hook("python3 kit/retired-gate.py")]}]

    merged = ms.merge(consumer, _kit_settings(), previous={})

    assert "python3 kit/retired-gate.py" in _commands(merged, "Stop")


def test_the_baseline_records_the_kits_commands_not_the_merged_result() -> None:
    """Recording the merge would make every consumer hook look like the kit's, and
    hand the next install permission to delete it — the same trap `permissions`
    documents for its own provenance file."""
    baseline = ms.hook_baseline(_kit_settings())

    assert baseline == {
        "PreToolUse": ["python3 kit/validate-command.py"],
        "Stop": ["python3 kit/stop-validation.py"],
    }
    assert not any("my-gate.sh" in c for c in baseline["PreToolUse"])


def test_a_round_trip_is_stable() -> None:
    """Running the installer twice must not change the file the second time."""
    once = ms.merge(_consumer_settings(), _kit_settings(), previous={})
    baseline = ms.hook_baseline(_kit_settings())

    twice = ms.merge(json.loads(json.dumps(once)), _kit_settings(),
                     hook_previous=baseline)

    assert twice == once


# ── what it reports ───────────────────────────────────────────────────────────

def test_it_names_the_consumer_hooks_it_kept() -> None:
    """Suggestion 2 of #34: a silent deletion becomes a decision. It is now not a
    deletion at all, and saying what was kept is what makes that checkable."""
    merged, report = ms.merge_with_report(_consumer_settings(), _kit_settings(),
                                          previous={})

    assert any("my-gate.sh" in kept for kept in report["hooks_kept"])
    assert merged["hooks"]


def test_it_names_the_hooks_it_removed() -> None:
    consumer = _consumer_settings()
    consumer["hooks"]["Stop"] = [{"hooks": [_hook("python3 kit/retired-gate.py")]}]

    _, report = ms.merge_with_report(
        consumer, _kit_settings(),
        hook_previous={"Stop": ["python3 kit/retired-gate.py"]})

    assert any("retired-gate" in gone for gone in report["hooks_retired"])


# ── the other keys keep behaving exactly as they did ──────────────────────────

def test_the_consumers_permissions_survive_and_the_kits_are_a_floor() -> None:
    merged = ms.merge(_consumer_settings(), _kit_settings(), previous={})

    assert "Bash(pnpm test:*)" in merged["permissions"]["allow"]
    assert "Bash(git status)" in merged["permissions"]["allow"]
    assert "Read(**/.env)" in merged["permissions"]["deny"]


def test_deny_rules_are_inserted_before_the_consumers() -> None:
    """"an entry that forbids must be read before one that allows"."""
    consumer = _consumer_settings()
    consumer["permissions"]["deny"] = ["Read(ours/**)"]

    merged = ms.merge(consumer, _kit_settings(), previous={})

    assert merged["permissions"]["deny"][0] == "Read(**/.env)"


def test_a_retired_permission_is_removed_from_the_baseline() -> None:
    consumer = _consumer_settings()
    consumer["permissions"]["allow"].append("Bash(old-kit-rule)")

    merged = ms.merge(consumer, _kit_settings(),
                      previous={"allow": ["Bash(old-kit-rule)", "Bash(git status)"]})

    assert "Bash(old-kit-rule)" not in merged["permissions"]["allow"]
    assert "Bash(pnpm test:*)" in merged["permissions"]["allow"]


def test_a_declared_retired_permission_goes_even_with_no_baseline() -> None:
    """`rules/retired-permissions.txt` is what makes the FIRST migration possible."""
    consumer = _consumer_settings()
    consumer["permissions"]["allow"].append("Bash(withdrawn)")

    merged = ms.merge(consumer, _kit_settings(), previous={},
                      declared_retired={"Bash(withdrawn)"})

    assert "Bash(withdrawn)" not in merged["permissions"]["allow"]


def test_kit_owned_scalars_are_the_kits() -> None:
    kit = _kit_settings()
    kit["permissions"]["defaultMode"] = "bypassPermissions"
    consumer = _consumer_settings()
    consumer["permissions"]["defaultMode"] = "acceptEdits"

    merged = ms.merge(consumer, kit, previous={})

    assert merged["permissions"]["defaultMode"] == "bypassPermissions"


def test_a_key_the_kit_does_not_know_is_the_consumers() -> None:
    consumer = _consumer_settings()
    consumer["theirOwnKey"] = {"anything": True}

    merged = ms.merge(consumer, _kit_settings(), previous={})

    assert merged["theirOwnKey"] == {"anything": True}


def test_the_kit_owns_its_wiring_keys() -> None:
    kit = _kit_settings()
    kit["statusLine"] = {"type": "command", "command": "bash kit/statusline.sh"}
    consumer = _consumer_settings()
    consumer["statusLine"] = {"type": "command", "command": "bash stale.sh"}

    merged = ms.merge(consumer, kit, previous={})

    assert merged["statusLine"]["command"] == "bash kit/statusline.sh"


# ── the installer really uses this ────────────────────────────────────────────

def test_install_sh_calls_this_module_rather_than_carrying_its_own_copy() -> None:
    """The heredoc is what made the defect untestable. It must not come back."""
    installer = (Path(__file__).resolve().parents[1] / "mechanisms" / "distribution"
                 / "install.sh").read_text(encoding="utf-8")

    assert "merge_settings.py" in installer
    assert 'mine[key] = kit[key]' not in installer, (
        "the wholesale key replacement is back in the installer"
    )


def test_the_cli_merges_a_file_in_place(tmp_path: Path) -> None:
    target = tmp_path / "settings.json"
    source = tmp_path / "settings.plugin.json"
    target.write_text(json.dumps(_consumer_settings()), encoding="utf-8")
    source.write_text(json.dumps(_kit_settings()), encoding="utf-8")

    assert ms.main([str(target), str(source)]) == 0

    merged = json.loads(target.read_text(encoding="utf-8"))
    assert any("my-gate.sh" in c for c in _commands(merged, "PreToolUse"))
    assert (tmp_path / ".kit-hooks.json").is_file()
    assert (tmp_path / ".kit-permissions.json").is_file()


def test_the_cli_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "settings.json"
    source = tmp_path / "settings.plugin.json"
    target.write_text(json.dumps(_consumer_settings()), encoding="utf-8")
    source.write_text(json.dumps(_kit_settings()), encoding="utf-8")

    ms.main([str(target), str(source)])
    first = target.read_text(encoding="utf-8")
    ms.main([str(target), str(source)])

    assert target.read_text(encoding="utf-8") == first


def test_the_real_kit_settings_merge_onto_a_consumer_that_wired_its_own_hook(
    tmp_path: Path,
) -> None:
    """End to end, against the file the installer actually ships."""
    repo = Path(__file__).resolve().parents[1]
    kit = json.loads((repo / "settings.plugin.json").read_text(encoding="utf-8"))
    consumer = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash",
                 "hooks": [_hook('bash "$CLAUDE_PROJECT_DIR/.claude/hooks/delivery-gate.sh"',
                                 timeout=600)]},
            ],
        },
    }

    merged = ms.merge(consumer, kit, previous={})

    commands = _commands(merged, "PreToolUse")
    assert any("delivery-gate.sh" in c for c in commands), "the consumer's gate was dropped"
    assert any("validate-command.py" in c for c in commands), "the kit's gate is missing"
